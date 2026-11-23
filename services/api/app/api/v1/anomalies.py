from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Response, status

from app.api.deps import CanReviewAnomalies, DbSession
from app.schemas.anomaly import (
    Anomalies,
    AnomalyAlert,
    AnomalyDismissalRead,
    AnomalyDismissRequest,
    StockLossAlert,
)
from app.services import anomalies as service
from app.services import shrinkage

router = APIRouter(prefix="/anomalies", tags=["anomalies"])


@router.get("", response_model=Anomalies)
def list_anomalies(db: DbSession, auth: CanReviewAnomalies):
    """Owners and managers: unusual sales days in the last 7 complete store days, and products
    whose stock counts found 5%+ of sales missing in the last 8 weeks."""
    org = auth.organization
    now = datetime.now(ZoneInfo("UTC"))
    alerts, dismissed_count = service.find_alerts(db, org, now)
    first, last = service.checked_days(org, now)
    losses, losses_dismissed = shrinkage.find_losses(db, org, now)
    stock_first, stock_last = shrinkage.checked_window(org, now)
    return Anomalies(
        as_of=now,
        timezone=org.timezone,
        first_day=first,
        last_day=last,
        window_days=service.WINDOW_DAYS,
        spike_multiple=Decimal(str(service.SPIKE_MULTIPLE)),
        drop_multiple=Decimal(str(service.DROP_MULTIPLE)),
        alerts=[
            AnomalyAlert(
                product_id=a.product.id,
                name=a.product.name,
                sku=a.product.sku,
                unit=a.product.unit,
                day=a.day,
                kind=a.kind,
                units_sold=a.units_sold,
                usual_daily=Decimal(str(round(a.usual, 1))),
                in_stock_days=a.in_stock_days,
            )
            for a in alerts
        ],
        dismissed_count=dismissed_count,
        stock_window_first_day=stock_first,
        stock_window_last_day=stock_last,
        stock_window_days=shrinkage.WINDOW_DAYS,
        missing_share_threshold=Decimal(str(shrinkage.MISSING_SHARE)),
        stock_losses=[
            StockLossAlert(
                product_id=loss.product.id,
                name=loss.product.name,
                sku=loss.product.sku,
                unit=loss.product.unit,
                day=loss.last_loss_day,
                missing_units=loss.missing,
                units_sold=loss.units_sold,
                missing_share=Decimal(str(round(loss.share, 4))),
            )
            for loss in losses
        ],
        stock_losses_dismissed=losses_dismissed,
    )


@router.post(
    "/dismissals", response_model=AnomalyDismissalRead, status_code=status.HTTP_201_CREATED
)
def dismiss_anomaly(
    payload: AnomalyDismissRequest, db: DbSession, auth: CanReviewAnomalies, response: Response
):
    """Set an alert aside. 201 when dismissed now; 200 with the earlier dismissal if it was
    already dismissed. 404 if the alert isn't on the current list."""
    dismissal, created = service.dismiss(
        db,
        auth.organization,
        actor_id=auth.user.id,
        product_id=payload.product_id,
        day=payload.day,
        kind=payload.kind,
        note=payload.note,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return dismissal
