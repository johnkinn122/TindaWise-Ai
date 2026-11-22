"""Store settings: the organization's name, time zone and reorder default."""

import uuid
from datetime import datetime
from functools import cache
from typing import Annotated
from zoneinfo import available_timezones

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.schemas.common import ORMModel

StoreName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]


@cache
def known_time_zones() -> frozenset[str]:
    """IANA time zone names (from the tzdata package, so Windows has them too). "Factory" and
    "localtime" are placeholders, not places."""
    return frozenset(available_timezones() - {"Factory", "localtime"})


class StoreRead(ORMModel):
    id: uuid.UUID
    name: str
    currency: str
    timezone: str
    default_lead_time_days: int
    updated_at: datetime


class StoreUpdate(BaseModel):
    """Partial update: only fields that are sent change. Currency can't change here: every price,
    cost and receipt is stored in it."""

    name: StoreName | None = None
    timezone: str | None = None
    default_lead_time_days: Annotated[int, Field(ge=0, le=60)] | None = None

    @field_validator("timezone")
    @classmethod
    def _known_zone(cls, value: str | None) -> str | None:
        if value is not None and value not in known_time_zones():
            raise ValueError("Choose a time zone from the list, e.g. Asia/Manila")
        return value
