import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, StringConstraints, field_validator

from app.schemas.common import ORMModel

SupplierName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)
]


def _blank_to_none(value: object) -> object:
    """An empty optional field means "not given", never an empty string in the database."""
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


class _SupplierFields(BaseModel):
    contact_name: Annotated[str, StringConstraints(max_length=120)] | None = None
    phone: Annotated[str, StringConstraints(max_length=40)] | None = None
    email: EmailStr | None = None
    notes: Annotated[str, StringConstraints(max_length=500)] | None = None

    _blanks = field_validator("contact_name", "phone", "email", "notes", mode="before")(
        _blank_to_none
    )


class SupplierCreate(_SupplierFields):
    name: SupplierName


class SupplierUpdate(_SupplierFields):
    """Partial update: only fields that are sent change (send null to clear an optional one)."""

    name: SupplierName | None = None
    is_active: bool | None = None


class SupplierRead(ORMModel):
    id: uuid.UUID
    name: str
    contact_name: str | None
    phone: str | None
    email: str | None
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
