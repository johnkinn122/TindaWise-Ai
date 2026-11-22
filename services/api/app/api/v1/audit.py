import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CanReviewAudit, DbSession
from app.models import AuditAction
from app.schemas.audit import AuditEventRead
from app.schemas.common import Page
from app.services import audit as service

router = APIRouter(prefix="/audit-events", tags=["audit"])


@router.get("", response_model=Page[AuditEventRead])
def list_audit_events(
    db: DbSession,
    auth: CanReviewAudit,
    action: AuditAction | None = None,
    actor_id: Annotated[uuid.UUID | None, Query(description="Who did it")] = None,
    start: Annotated[date | None, Query(description="First day, store time")] = None,
    end: Annotated[date | None, Query(description="Last day, included")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Owner only: the log records what managers do too, so the owner is the one who reviews it."""
    filters = service.EventFilters(action=action, actor_id=actor_id, start=start, end=end)
    rows, total = service.list_events(db, auth.organization, filters, limit=limit, offset=offset)
    items = [
        AuditEventRead(
            id=event.id,
            action=event.action,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
            summary=event.summary,
            details=event.details,
            actor_user_id=event.actor_user_id,
            actor_name=name,
            created_at=event.created_at,
        )
        for event, name in rows
    ]
    return Page(items=items, total=total, limit=limit, offset=offset)
