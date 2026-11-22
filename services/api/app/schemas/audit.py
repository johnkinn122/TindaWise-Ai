import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditEventRead(BaseModel):
    id: uuid.UUID
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    summary: str
    details: dict[str, Any]
    actor_user_id: uuid.UUID | None
    actor_name: str | None  # None for actions without a signed-in person
    created_at: datetime
