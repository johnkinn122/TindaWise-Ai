"""The sales report: one period, compared with the period of equal length just before it.

Money is Decimal (serialized as a string); gross_margin is a Decimal fraction (0.2240 = 22.4%).
The report is for owners and managers, so cost-derived figures are always present.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

Preset = Literal["today", "yesterday", "last_7_days", "last_30_days", "this_month", "last_month"]
Granularity = Literal["day", "week", "month"]
ProductSort = Literal["sales", "gross_profit", "quantity"]


class Period(BaseModel):
    start: date  # inclusive, store-local calendar days
    end: date  # inclusive
    days: int


class ReportSummary(BaseModel):
    sales: Decimal
    transactions: int
    average_sale: Decimal | None  # null with no sales
    gross_profit: Decimal
    gross_margin: Decimal | None  # null with no sales
    items_sold: int


class SeriesPoint(BaseModel):
    """One bucket. `start` is the first day of the day/week/month; zero-filled, never missing."""

    start: date
    sales: Decimal
    transactions: int
    gross_profit: Decimal


class ProductRow(BaseModel):
    product_id: uuid.UUID
    name: str
    sku: str
    unit: str
    quantity: int
    sales: Decimal
    gross_profit: Decimal
    gross_margin: Decimal | None


class CategoryRow(BaseModel):
    category_id: uuid.UUID | None  # null = products with no category
    name: str
    quantity: int
    sales: Decimal
    gross_profit: Decimal


class PaymentRow(BaseModel):
    method: Literal["cash", "e_wallet"]
    sales: Decimal
    transactions: int


class SupplierRow(BaseModel):
    supplier_id: uuid.UUID
    name: str
    received_value: Decimal
    deliveries: int


class SalesReport(BaseModel):
    timezone: str
    currency: str
    period: Period
    previous_period: Period
    granularity: Granularity
    summary: ReportSummary
    previous_summary: ReportSummary
    series: list[SeriesPoint]
    products: list[ProductRow]
    product_count: int
    product_sort: ProductSort
    categories: list[CategoryRow]
    payments: list[PaymentRow]
    suppliers: list[SupplierRow]
    purchases_total: Decimal
