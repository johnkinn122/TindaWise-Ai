"""Store settings."""

from sqlalchemy.orm import Session

from app.models import Organization
from app.schemas.store import StoreUpdate


def update_store(db: Session, org: Organization, data: StoreUpdate) -> Organization:
    """Apply only the fields that were sent. Null means "not sent" here: every field is required
    on the organization, so there is nothing to clear."""
    for field, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(org, field, value)
    db.commit()
    db.refresh(org)
    return org
