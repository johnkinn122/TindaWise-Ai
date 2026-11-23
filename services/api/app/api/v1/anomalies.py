from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Response, status

from app.api.deps import CanReviewAnomalies, DbSession
from app.schemas.anomaly import Anomalies, AnomalyAlert, AnomalyDismissalRead, AnomalyDismissRequest
from app.services import anomalies as service

router = APIRouter(prefix="/anomalies", tags=["anomalies"])


@router.get("", response_model=Anomalies)
def list_anomalies(db: DbSession, auth: CanReviewAnomalies):
    """Owners and managers: unusual sales days in the last 7 complete store days."""
    org = auth.organization
    now = datetime.now(ZoneInfo("UTC"))
    alerts, dismissed_count = service.find_alerts(db, org, now)
    first, last = service.checked_days(org, now)
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
