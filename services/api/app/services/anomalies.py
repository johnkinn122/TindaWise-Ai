"""Unusual sales days: a short "worth a look" list for owners and managers.

The rule was chosen by experiment (docs/ml/EXPERIMENTS.md, 2026-11-23). On six synthetic
datasets with planted anomalies, a plain ratio against the recent average beat a robust
z-score and a negative binomial model. The two multiples below are the six validation-period
thresholds' medians, rounded (spike e^1.14 = 3.1, drop e^2.03 = 7.6), and were then scored once on
the test periods: about 1 false alarm a week for a 17-product store.

For each of the last 7 complete store days and each active product that was in stock that day
(the shelf never reached zero):

    usual = average units sold per day over the 28 days before it, counting only days it was
            in stock and the store was open (at least 14 of them; otherwise there's too little
            history to judge)

    spike when  (sold + 1) >= 3   x (usual + 1)   "sold far more than usual"
    drop  when  (usual + 1) >= 7.5 x (sold + 1)   "sold far less than usual, while in stock"

The +1 keeps slow sellers quiet: a product that usually sells 0.5 a day needs 4+ sales to spike,
and a drop needs a product that usually sells about 6.5+ a day to sell nothing.

A spike can be a bulk buyer or a sale rung up twice; a drop can mean sales went unrecorded, or
a product that was on the shelf but not where customers could find it. The list says what
happened and leaves the cause to the person who knows the store.

Alerts aren't stored. They're recomputed from sales and the stock ledger, so they always match
the records (a refunded duplicate sale still counts as sold: refunds aren't subtracted, as in
the demand table). Only dismissals are stored, in `anomaly_dismissals`.

Not checked:
- Today: it isn't over, and every product would look like a drop in the morning.
- Days the whole store sold nothing (closed, or the till wasn't used). Without this, a holiday
  flags every regular seller at once. The experiment's synthetic data has no closed days; this
  was found on the sample history store, whose sales stop the day before it was seeded.
  "Open" is judged from active products' sales only.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models import AnomalyDismissal, AuditAction, Organization, Product
from app.services import shrinkage
from app.services.audit import record
from app.services.demand_history import daily_demand

WINDOW_DAYS = 28
MIN_IN_STOCK_DAYS = 14
LOOKBACK_DAYS = 7
SPIKE_MULTIPLE = 3.0
DROP_MULTIPLE = 7.5

Kind = Literal["spike", "drop"]
DismissKind = Literal["spike", "drop", "shrinkage"]


@dataclass(frozen=True)
class Alert:
    product: Product
    day: date
    kind: Kind
    units_sold: int
    usual: float  # average units a day on the in-stock days before `day`
    in_stock_days: int  # how many days `usual` is based on


def check_day(units_sold: int, history: list[int]) -> tuple[Kind | None, float | None]:
    """(kind or None, usual) for one product-day, given in-stock sales on the days before it.
    Usual is None when there are too few in-stock days to judge."""
    if len(history) < MIN_IN_STOCK_DAYS:
        return None, None
    usual = sum(history) / len(history)
    # Rounded so an exact multiple (15 sold against 4 a day is exactly 3x) isn't lost to float
    # noise.
    if round(units_sold + 1 - SPIKE_MULTIPLE * (usual + 1), 9) >= 0:
        return "spike", usual
    if round(usual + 1 - DROP_MULTIPLE * (units_sold + 1), 9) >= 0:
        return "drop", usual
    return None, usual


def checked_days(org: Organization, now: datetime) -> tuple[date, date]:
    """First and last store day checked: the 7 complete days before today."""
    today = now.astimezone(ZoneInfo(org.timezone)).date()
    return today - timedelta(days=LOOKBACK_DAYS), today - timedelta(days=1)


def _all_alerts(db: Session, org: Organization, now: datetime) -> list[Alert]:
    first, last = checked_days(org, now)
    rows = daily_demand(db, org, first - timedelta(days=WINDOW_DAYS), last)
    # A day the whole store sold nothing was a closed day, or a day the till wasn't used. Either
    # way it's one fact about the store, not a drop for every product, and it isn't a normal
    # day to learn "usual" from.
    open_days = {row.day for row in rows if row.units_sold > 0}
    by_sku: dict[str, dict[date, tuple[int, bool]]] = {}
    for row in rows:
        by_sku.setdefault(row.sku, {})[row.day] = (row.units_sold, row.stockout)
    products = {
        p.sku: p
        for p in db.scalars(
            select(Product).where(Product.organization_id == org.id, Product.is_active.is_(True))
        )
    }

    alerts = []
    for sku, days in by_sku.items():
        product = products.get(sku)
        if product is None:  # archived between the two queries
            continue

        def judgeable(day: date) -> bool:
            """Open, and this product was in stock all day."""
            return day in open_days and not days[day][1]  # noqa: B023 (used inside the loop)

        day = first
        while day <= last:
            if judgeable(day):
                earlier = (day - timedelta(days=n) for n in range(1, WINDOW_DAYS + 1))
                history = [days[d][0] for d in earlier if judgeable(d)]
                sold = days[day][0]
                kind, usual = check_day(sold, history)
                if kind is not None and usual is not None:
                    alerts.append(Alert(product, day, kind, sold, usual, len(history)))
            day += timedelta(days=1)
    return alerts


def _dismissed(
    db: Session, org: Organization, first: date, last: date
) -> set[tuple[uuid.UUID, date, str]]:
    rows = db.execute(
        select(AnomalyDismissal.product_id, AnomalyDismissal.day, AnomalyDismissal.kind).where(
            AnomalyDismissal.organization_id == org.id,
            AnomalyDismissal.day.between(first, last),
        )
    )
    return {(product_id, day, kind) for product_id, day, kind in rows}


def find_alerts(db: Session, org: Organization, now: datetime) -> tuple[list[Alert], int]:
    """(alerts not yet dismissed, how many were dismissed). Newest day first; on the same day,
    drops before spikes (possibly unrecorded sales matter more than a busy day), then name."""
    first, last = checked_days(org, now)
    dismissed = _dismissed(db, org, first, last)
    alerts, dismissed_count = [], 0
    for alert in _all_alerts(db, org, now):
        if (alert.product.id, alert.day, alert.kind) in dismissed:
            dismissed_count += 1
        else:
            alerts.append(alert)
    alerts.sort(key=lambda a: (-a.day.toordinal(), a.kind != "drop", a.product.name))
    return alerts, dismissed_count


def describe(alert: Alert) -> str:
    """One plain sentence, used for the audit log."""
    # Same wording as the Overview panel: "Nov 21", "about 9" (one decimal only when needed).
    when = f"{alert.day:%b} {alert.day.day}"
    usual = f"usually about {f'{alert.usual:.1f}'.removesuffix('.0')} a day"
    if alert.kind == "spike":
        return f"{alert.product.name} sold {alert.units_sold} on {when} ({usual})"
    return f"{alert.product.name} sold {alert.units_sold} on {when} while in stock ({usual})"


def _existing(
    db: Session, org: Organization, product_id: uuid.UUID, day: date, kind: str
) -> AnomalyDismissal | None:
    return db.scalar(
        select(AnomalyDismissal).where(
            AnomalyDismissal.organization_id == org.id,
            AnomalyDismissal.product_id == product_id,
            AnomalyDismissal.day == day,
            AnomalyDismissal.kind == kind,
        )
    )


def dismiss(
    db: Session,
    org: Organization,
    *,
    actor_id: uuid.UUID,
    product_id: uuid.UUID,
    day: date,
    kind: DismissKind,
    note: str | None,
    now: datetime | None = None,
) -> tuple[AnomalyDismissal, bool]:
    """Set an alert aside. Returns (dismissal, created). Dismissing one already dismissed returns
    the first dismissal unchanged, so a double click or retry is harmless and logged once.

    Sales alerts ("spike", "drop") are keyed by their day; stock going missing ("shrinkage") by
    the day of the latest count that found stock missing (services/shrinkage.py).

    Only an alert that's on the current list can be dismissed: this stops dismissals being
    stored in advance for days or products that haven't been flagged."""
    existing = _existing(db, org, product_id, day, kind)
    if existing is not None:
        return existing, False

    now = now or datetime.now(ZoneInfo("UTC"))
    if kind == "shrinkage":
        loss = shrinkage.find_loss(db, org, now, product_id, day)
        if loss is None:
            raise NotFoundError("That alert isn't on the list any more. Refresh to see the latest.")
        sku = loss.product.sku
        summary = f"Dismissed a missing-stock alert: {shrinkage.describe(loss)}"
        figures = {"missing": loss.missing, "units_sold": loss.units_sold}
    else:
        match = next(
            (
                a
                for a in _all_alerts(db, org, now)
                if a.product.id == product_id and a.day == day and a.kind == kind
            ),
            None,
        )
        if match is None:
            raise NotFoundError("That alert isn't on the list any more. Refresh to see the latest.")
        sku = match.product.sku
        summary = f"Dismissed an unusual-sales alert: {describe(match)}"
        figures = {"units_sold": match.units_sold, "usual": round(match.usual, 1)}

    dismissal = AnomalyDismissal(
        organization_id=org.id,
        product_id=product_id,
        day=day,
        kind=kind,
        dismissed_by=actor_id,
        note=note,
    )
    db.add(dismissal)
    record(
        db,
        org_id=org.id,
        actor_id=actor_id,
        action=AuditAction.ANOMALY_DISMISSED,
        entity_type="product",
        entity_id=product_id,
        summary=summary,
        details={"sku": sku, "day": day.isoformat(), "kind": kind, **figures, "note": note},
    )
    try:
        db.commit()
    except IntegrityError:
        # Someone dismissed it at the same moment: theirs stands, and was logged once.
        db.rollback()
        winner = _existing(db, org, product_id, day, kind)
        if winner is None:
            raise
        return winner, False
    db.refresh(dismissal)
    return dismissal, True
