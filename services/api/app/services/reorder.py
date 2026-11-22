"""Reorder suggestions from recent demand and delivery time.

The rule was chosen by simulation (docs/ml/EXPERIMENTS.md, 2026-11-23). On six synthetic
datasets, at about the same number of orders and stock as the previous fixed rule, it lost 45-73%
fewer sales. An average did as well there as LightGBM, so no model is involved.

Per active product, from the last 28 complete store days:

    rate      = average units sold per day on days it was in stock (empty-shelf days left out,
                so a stockout doesn't read as "nobody wants it")
    spread    = how much daily sales vary on those days (standard deviation)
    lead time = the supplier's delivery days (supplier on the product's latest purchase order),
                or the store default
    buffer    = 1 x spread x sqrt(lead time)
    position  = stock on hand + units on open purchase orders (draft, approved, part-received)

    suggest when   position <= rate x lead time + buffer
    order          rate x (lead time + 10 days) + buffer - position, rounded up

Products with fewer than 7 in-stock days in the window (new, or empty for weeks) have too little
history for a rate; they fall back to the reorder level: when position <= reorder level, order up
to twice the reorder level. Seven days is a judgment call, not something the simulation tested.
A product with 7+ in-stock days and no sales on them gets no suggestion: nobody is buying it.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from app.models import Organization, Product, PurchaseOrder, PurchaseOrderLine, Supplier
from app.services.demand_history import daily_demand

WINDOW_DAYS = 28
COVER_DAYS = 10
SAFETY = 1.0
MIN_IN_STOCK_DAYS = 7
OPEN_STATUSES = ("draft", "approved", "partially_received")

Basis = Literal["recent_sales", "reorder_level"]
LeadSource = Literal["supplier", "store_default"]


@dataclass(frozen=True)
class ReorderCandidate:
    product: Product
    quantity: int
    basis: Basis
    daily_rate: float | None  # None when the reorder level was used instead
    in_stock_days: int
    lead_time_days: int
    lead_time_source: LeadSource
    supplier_name: str | None
    on_order: int

    @property
    def position(self) -> int:
        return self.product.stock_on_hand + self.on_order


def _on_order(db: Session, org_id: uuid.UUID) -> dict[uuid.UUID, int]:
    rows = db.execute(
        select(
            PurchaseOrderLine.product_id,
            func.sum(PurchaseOrderLine.quantity_ordered - PurchaseOrderLine.quantity_received),
        )
        .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderLine.purchase_order_id)
        .where(PurchaseOrder.organization_id == org_id, PurchaseOrder.status.in_(OPEN_STATUSES))
        .group_by(PurchaseOrderLine.product_id)
    )
    return {product_id: int(units) for product_id, units in rows if units}


def _latest_suppliers(db: Session, org_id: uuid.UUID) -> dict[uuid.UUID, Supplier]:
    """Each product's supplier on its most recent purchase order that has one (not cancelled)."""
    latest = (
        select(PurchaseOrderLine.product_id, PurchaseOrder.supplier_id)
        .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderLine.purchase_order_id)
        .where(
            PurchaseOrder.organization_id == org_id,
            PurchaseOrder.supplier_id.is_not(None),
            PurchaseOrder.status != "cancelled",
        )
        .ext(distinct_on(PurchaseOrderLine.product_id))
        .order_by(
            PurchaseOrderLine.product_id, PurchaseOrder.created_at.desc(), PurchaseOrder.id.desc()
        )
        .subquery()
    )
    rows = db.execute(
        select(latest.c.product_id, Supplier).join(Supplier, Supplier.id == latest.c.supplier_id)
    )
    return {product_id: supplier for product_id, supplier in rows}


def _rate_and_spread(units: list[int]) -> tuple[float, float]:
    mean = sum(units) / len(units)
    spread = math.sqrt(sum((u - mean) ** 2 for u in units) / len(units))
    return mean, spread


def suggest(
    *,
    stock_on_hand: int,
    on_order: int,
    reorder_level: int,
    in_stock_units: list[int],
    lead_time_days: int,
) -> tuple[int, Basis, float | None]:
    """(units to order, basis, daily rate) for one product; 0 units means no suggestion."""
    position = stock_on_hand + on_order
    if len(in_stock_units) < MIN_IN_STOCK_DAYS:
        if position > reorder_level:
            return 0, "reorder_level", None
        return max(2 * reorder_level - position, 0), "reorder_level", None
    rate, spread = _rate_and_spread(in_stock_units)
    buffer = SAFETY * spread * math.sqrt(lead_time_days)
    if position > rate * lead_time_days + buffer:
        return 0, "recent_sales", rate
    wanted = rate * (lead_time_days + COVER_DAYS) + buffer - position
    # Round before ceil so float noise (9.000000001) doesn't add a unit.
    return max(math.ceil(round(wanted, 6)), 0), "recent_sales", rate


def reorder_candidates(db: Session, org: Organization, now: datetime) -> list[ReorderCandidate]:
    """Every product worth ordering now, most urgent first: out of stock, then fewest days of
    stock left (stock + on order over the daily rate), then name. Shared by the Overview and by
    "create a purchase order from suggestions", so both always agree."""
    today = now.astimezone(ZoneInfo(org.timezone)).date()
    start, end = today - timedelta(days=WINDOW_DAYS), today - timedelta(days=1)
    in_stock: dict[str, list[int]] = {}
    for row in daily_demand(db, org, start, end):
        units = in_stock.setdefault(row.sku, [])
        if not row.stockout:
            units.append(row.units_sold)

    products = db.scalars(
        select(Product).where(Product.organization_id == org.id, Product.is_active.is_(True))
    ).all()
    on_order = _on_order(db, org.id)
    suppliers = _latest_suppliers(db, org.id)

    candidates = []
    for product in products:
        supplier = suppliers.get(product.id)
        if supplier is not None and supplier.lead_time_days is not None:
            lead, source = supplier.lead_time_days, "supplier"
        else:
            lead, source = org.default_lead_time_days, "store_default"
        units = in_stock.get(product.sku, [])
        ordered = on_order.get(product.id, 0)
        quantity, basis, rate = suggest(
            stock_on_hand=product.stock_on_hand,
            on_order=ordered,
            reorder_level=product.reorder_level,
            in_stock_units=units,
            lead_time_days=lead,
        )
        if quantity > 0:
            candidates.append(
                ReorderCandidate(
                    product=product,
                    quantity=quantity,
                    basis=basis,
                    daily_rate=rate,
                    in_stock_days=len(units),
                    lead_time_days=lead,
                    lead_time_source=source,
                    supplier_name=supplier.name if supplier is not None else None,
                    on_order=ordered,
                )
            )

    def urgency(c: ReorderCandidate) -> tuple:
        days_left = (
            c.position / c.daily_rate
            if c.daily_rate
            else c.position / max(c.product.reorder_level, 1)
        )
        return (c.product.stock_on_hand > 0, days_left, c.product.name)

    return sorted(candidates, key=urgency)
