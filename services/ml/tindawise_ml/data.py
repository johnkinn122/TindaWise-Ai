"""The daily demand table every forecasting step reads.

One row per product per store-local day, zero-filled, so a day with no sales is a row with 0
rather than a missing row. Missing rows would make "the same weekday last week" silently point at
the wrong day.

Columns:
    date        store-local calendar day (datetime64, midnight)
    sku         product SKU
    units_sold  whole units sold that day (>= 0)
    stockout    True when the product ran out that day, so `units_sold` may be lower than what
                customers wanted (censored demand). Scoring skips these days.

The synthetic generator also adds `demand` (what customers actually wanted). Real data can't
observe that column, so no model or baseline may read it.
"""

from __future__ import annotations

import pandas as pd

REQUIRED_COLUMNS = ("date", "sku", "units_sold", "stockout")


class DemandFrameError(ValueError):
    """The table breaks the daily demand contract."""


def validate_demand_frame(frame: pd.DataFrame) -> None:
    """Raise DemandFrameError unless `frame` follows the contract described above."""
    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise DemandFrameError(f"missing columns: {', '.join(missing)}")
    if frame.empty:
        raise DemandFrameError("no rows")
    if not pd.api.types.is_datetime64_any_dtype(frame["date"]):
        raise DemandFrameError("`date` must be a datetime column")
    if (frame["date"] != frame["date"].dt.normalize()).any():
        raise DemandFrameError("`date` must be whole days (midnight)")
    if not pd.api.types.is_integer_dtype(frame["units_sold"]):
        raise DemandFrameError("`units_sold` must be whole units")
    if (frame["units_sold"] < 0).any():
        raise DemandFrameError("`units_sold` can't be negative")
    if not pd.api.types.is_bool_dtype(frame["stockout"]):
        raise DemandFrameError("`stockout` must be True/False")
    if frame.duplicated(["sku", "date"]).any():
        raise DemandFrameError("more than one row for the same product and day")

    # Every product must cover every day of the table's range: zero-filled, no gaps.
    days = pd.date_range(frame["date"].min(), frame["date"].max(), freq="D")
    counts = frame.groupby("sku")["date"].nunique()
    short = counts[counts != len(days)]
    if not short.empty:
        raise DemandFrameError(
            f"products missing days (rows must be zero-filled): {', '.join(short.index[:5])}"
        )


def to_wide(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    """Pivot one column to a dates x SKUs table (rows sorted by date, columns by SKU)."""
    return frame.pivot(index="date", columns="sku", values=column).sort_index().sort_index(axis=1)
