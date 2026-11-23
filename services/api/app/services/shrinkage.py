"""Stock going missing: products whose stock counts keep finding less than the records say.

The rule was chosen by experiment (docs/ml/EXPERIMENTS.md, "Shrinkage", 2026-11-23). On
simulated stores with planted losses, the plain share of sales beat a count of missing units
and a Poisson test: 93% precision, 88% recall, about one false alarm per store every 8 weeks.

Per active product, over the last 56 complete store days (8 weeks):

    missing  = units removed by stock count corrections (`adjustment` movements, "Stock count
               correction" in the app), net of any a count found, when that's a loss
    sold     = units rung up (refunds aren't subtracted, as in the demand table)

    flag when  missing >= 5% x (sold + 1)

Recorded damage never counts: it's explained loss. A product nobody counted has nothing to
show, so the list depends on the store counting regularly (every 7 to 28 days made little
difference in the experiment; counting at all is what matters).

Alerts aren't stored; dismissals are (`anomaly_dismissals`, kind "shrinkage"), keyed by the
store day of the latest count that found stock missing. A dismissed product comes back only
when a later count finds more missing.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import AnomalyDismissal, Organization, Product, Sale, SaleLine, StockMovement
from app.services.demand_history import store_day_bounds

WINDOW_DAYS = 56
MISSING_SHARE = 0.05


@dataclass(frozen=True)
class StockLoss:
    product: Product
    missing: int
    units_sold: int
    last_loss_day: date  # store day of the latest count in the window that found stock missing

    @property
    def share(self) -> float:
        """Missing units per unit sold, as compared with the 5% (sold + 1 avoids dividing by 0)."""
        return self.missing / (self.units_sold + 1)


def is_flagged(missing: int, units_sold: int) -> bool:
    # Rounded so an exact 5% isn't lost to float noise.
    return missing > 0 and round(missing - MISSING_SHARE * (units_sold + 1), 9) >= 0


def checked_window(org: Organization, now: datetime) -> tuple[date, date]:
    """First and last store day: the 56 complete days before today."""
    today = now.astimezone(ZoneInfo(org.timezone)).date()
    return today - timedelta(days=WINDOW_DAYS), today - timedelta(days=1)


def _all_losses(db: Session, org: Organization, now: datetime) -> list[StockLoss]:
    first, last = checked_window(org, now)
    since, until = store_day_bounds(org, first, last)

    local_day = func.date(func.timezone(org.timezone, StockMovement.created_at))
    corrections = {
        product_id: (int(net), latest_loss)
        for product_id, net, latest_loss in db.execute(
            select(
                StockMovement.product_id,
                func.sum(StockMovement.quantity_change),
                func.max(case((StockMovement.quantity_change < 0, local_day))),
            )
            .where(
                StockMovement.organization_id == org.id,
                StockMovement.reason == "adjustment",
                StockMovement.created_at >= since,
                StockMovement.created_at < until,
            )
            .group_by(StockMovement.product_id)
        )
    }
    if not corrections:
        return []

    sold = dict(
        db.execute(
            select(SaleLine.product_id, func.sum(SaleLine.quantity))
            .join(Sale, Sale.id == SaleLine.sale_id)
            .where(
                Sale.organization_id == org.id,
                Sale.created_at >= since,
                Sale.created_at < until,
                SaleLine.product_id.in_(corrections),
            )
            .group_by(SaleLine.product_id)
        ).all()
    )
    products = db.scalars(
        select(Product).where(
            Product.organization_id == org.id,
            Product.is_active.is_(True),
            Product.id.in_(corrections),
        )
    )

    losses = []
    for product in products:
        net, latest_loss = corrections[product.id]
        missing, units = max(-net, 0), int(sold.get(product.id, 0))
        if is_flagged(missing, units) and latest_loss is not None:
            losses.append(StockLoss(product, missing, units, latest_loss))
    return losses


def find_losses(db: Session, org: Organization, now: datetime) -> tuple[list[StockLoss], int]:
    """(products losing stock, not dismissed; how many were dismissed). Largest share first."""
    first, _ = checked_window(org, now)
    dismissed = {
        (product_id, day)
        for product_id, day in db.execute(
            select(AnomalyDismissal.product_id, AnomalyDismissal.day).where(
                AnomalyDismissal.organization_id == org.id,
                AnomalyDismissal.kind == "shrinkage",
                AnomalyDismissal.day >= first,
            )
        )
    }
    losses, dismissed_count = [], 0
    for loss in _all_losses(db, org, now):
        if (loss.product.id, loss.last_loss_day) in dismissed:
            dismissed_count += 1
        else:
            losses.append(loss)
    losses.sort(key=lambda loss: (-loss.share, loss.product.name))
    return losses, dismissed_count


def find_loss(
    db: Session, org: Organization, now: datetime, product_id: uuid.UUID, day: date
) -> StockLoss | None:
    """The current alert for this product and latest-count day, if there is one."""
    return next(
        (
            loss
            for loss in _all_losses(db, org, now)
            if loss.product.id == product_id and loss.last_loss_day == day
        ),
        None,
    )


def describe(loss: StockLoss) -> str:
    """One plain sentence, used for the audit log."""
    when = f"{loss.last_loss_day:%b} {loss.last_loss_day.day}"
    return (
        f"{loss.product.name}: {loss.missing} {loss.product.unit} missing in stock counts, "
        f"{loss.share:.1%} of {loss.units_sold} sold in 8 weeks (latest count {when})"
    )
