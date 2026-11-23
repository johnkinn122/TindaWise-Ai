"""The "Worth a look" list: unusual sales days (`services/anomalies.py`) and stock going
missing (`services/shrinkage.py`)."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints, field_validator

from app.schemas.common import ORMModel
from app.schemas.supplier import _blank_to_none

AnomalyKind = Literal["spike", "drop"]
DismissKind = Literal["spike", "drop", "shrinkage"]


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


class StockLossAlert(BaseModel):
    """A product whose stock counts found 5%+ of its sales missing in the last 8 weeks."""

    product_id: uuid.UUID
    name: str
    sku: str
    unit: str
    day: date  # store day of the latest count that found stock missing (the dismissal key)
    missing_units: int  # net units removed by stock count corrections in the window
    units_sold: int  # units rung up in the window
    missing_share: Decimal  # missing / (sold + 1), four decimals (0.0612 = 6.1%)


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
    stock_window_first_day: date  # stock going missing: the 56 complete store days before today
    stock_window_last_day: date
    stock_window_days: int
    missing_share_threshold: Decimal
    stock_losses: list[StockLossAlert]  # not dismissed; largest share first
    stock_losses_dismissed: int


class AnomalyDismissRequest(BaseModel):
    product_id: uuid.UUID
    day: date
    kind: DismissKind
    note: Annotated[str, StringConstraints(max_length=280)] | None = None

    _blank = field_validator("note", mode="before")(_blank_to_none)


class AnomalyDismissalRead(ORMModel):
    id: uuid.UUID
    product_id: uuid.UUID
    day: date
    kind: DismissKind
    note: str | None
    dismissed_by: uuid.UUID
    created_at: datetime
