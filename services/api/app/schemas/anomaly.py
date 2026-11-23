"""Unusual sales days ("worth a look"): see `services/anomalies.py` for the rule."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints, field_validator

from app.schemas.common import ORMModel
from app.schemas.supplier import _blank_to_none

AnomalyKind = Literal["spike", "drop"]


class AnomalyAlert(BaseModel):
    product_id: uuid.UUID
    name: str
    sku: str
    unit: str
    day: date  # store-local day
    # "spike": sold far more than usual. "drop": sold far less than usual while in stock.
    kind: AnomalyKind
    units_sold: int
    usual_daily: Decimal  # average units a day on recent in-stock days, one decimal
    in_stock_days: int  # how many days that average is based on


class Anomalies(BaseModel):
    as_of: datetime
    timezone: str
    first_day: date  # the days checked: the 7 complete store days before today
    last_day: date
    window_days: int
    spike_multiple: Decimal
    drop_multiple: Decimal
    alerts: list[AnomalyAlert]  # not dismissed; newest day first
    dismissed_count: int  # alerts in the same days that someone dismissed


class AnomalyDismissRequest(BaseModel):
    product_id: uuid.UUID
    day: date
    kind: AnomalyKind
    note: Annotated[str, StringConstraints(max_length=280)] | None = None

    _blank = field_validator("note", mode="before")(_blank_to_none)


class AnomalyDismissalRead(ORMModel):
    id: uuid.UUID
    product_id: uuid.UUID
    day: date
    kind: AnomalyKind
    note: str | None
    dismissed_by: uuid.UUID
    created_at: datetime
