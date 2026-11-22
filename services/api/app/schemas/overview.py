"""The Overview dashboard: one response with everything the first screen needs.

Money is Decimal (serialized as a string). Ratios such as gross margin are Decimal fractions
(0.2240 = 22.4%). Cost-derived fields are null when the viewer's role may not see costs.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.schemas.product import StockStatus


class SalesFigures(BaseModel):
    sales: Decimal  # net: sales rung up minus refunds given that day
    refunds: Decimal  # refunds given that day (already subtracted from `sales`)
    transactions: int
    # (net sales - net cost) / net sales. Null with no net sales or hidden costs.
    gross_margin: Decimal | None


class OverviewDay(BaseModel):
    date: date
    # Net sales. Null for days later this week that haven't happened yet.
    sales: Decimal | None
    last_week_sales: Decimal


class StockWatchItem(BaseModel):
    id: uuid.UUID
    name: str
    category: str | None
    unit: str
    stock_on_hand: int
    reorder_level: int
    stock_status: StockStatus


class ReorderLine(BaseModel):
    product_id: uuid.UUID
    name: str
    unit: str
    stock_on_hand: int
    reorder_level: int
    sold_recently: int
    suggested_quantity: int
    unit_cost: Decimal | None


class ReorderSuggestions(BaseModel):
    """Rule-based, not a forecast: see `services/overview.py` for the formula."""

    lines: list[ReorderLine]
    total_count: int
    lookback_days: int
    estimated_cost: Decimal | None


class Overview(BaseModel):
    as_of: datetime
    timezone: str
    currency: str
    # "mine" for cashiers: their own sales only, like the sales list.
    sales_scope: Literal["store", "mine"]
    costs_visible: bool
    today: SalesFigures
    same_day_last_week: SalesFigures
    # Sunday to Saturday of the current week, in the store's time zone.
    week: list[OverviewDay]
    low_stock_count: int
    out_of_stock_count: int
    stock_to_watch: list[StockWatchItem]
    reorder: ReorderSuggestions
