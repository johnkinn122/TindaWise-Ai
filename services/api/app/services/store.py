"""Store settings."""

import uuid

from sqlalchemy.orm import Session

from app.models import AuditAction, Organization
from app.schemas.store import StoreUpdate
from app.services.audit import record

LABELS = {
    "name": "name",
    "timezone": "time zone",
    "default_lead_time_days": "default delivery time",
}


def update_store(
    db: Session, org: Organization, data: StoreUpdate, *, actor_id: uuid.UUID
) -> Organization:
    """Apply only the fields that were sent. Null means "not sent" here: every field is required
    on the organization, so there is nothing to clear. Audited when something actually changes."""
    changes: dict[str, list] = {}
    for field, value in data.model_dump(exclude_unset=True).items():
        if value is not None and getattr(org, field) != value:
            changes[field] = [getattr(org, field), value]
            setattr(org, field, value)
    if changes:
        record(
            db,
            org_id=org.id,
            actor_id=actor_id,
            action=AuditAction.STORE_UPDATED,
            entity_type="store",
            entity_id=org.id,
            summary="Changed store settings: " + ", ".join(LABELS[f] for f in changes),
            details={"changes": changes},
        )
    db.commit()
    db.refresh(org)
    return org
