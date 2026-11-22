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

from dataclasses import dataclass
from pathlib import Path

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


def load_demand_csv(path: str | Path) -> pd.DataFrame:
    """Read a daily demand CSV (for example from services/api `scripts.export_demand`) and check
    it against the contract. Extra columns are kept; `date` is parsed as a calendar day."""
    raw = pd.read_csv(path, dtype={"sku": str}, keep_default_na=False)
    missing = [c for c in REQUIRED_COLUMNS if c not in raw.columns]
    if missing:
        raise DemandFrameError(f"missing columns: {', '.join(missing)}")
    frame = raw.copy()
    try:
        frame["date"] = pd.to_datetime(frame["date"], format="%Y-%m-%d")
    except ValueError as error:
        raise DemandFrameError("`date` must be YYYY-MM-DD") from error
    stockout = frame["stockout"].astype(str).str.lower()
    if not stockout.isin(["true", "false"]).all():
        raise DemandFrameError("`stockout` must be True/False")
    frame["stockout"] = stockout == "true"
    units = pd.to_numeric(frame["units_sold"], errors="coerce")
    if units.isna().any() or (units != units.round()).any():
        raise DemandFrameError("`units_sold` must be whole units")
    frame["units_sold"] = units.astype("int64")
    validate_demand_frame(frame)
    return frame.sort_values(["date", "sku"], ignore_index=True)


def to_wide(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    """Pivot one column to a dates x SKUs table (rows sorted by date, columns by SKU)."""
    return frame.pivot(index="date", columns="sku", values=column).sort_index().sort_index(axis=1)


@dataclass(frozen=True)
class History:
    """What a forecaster may see: dates x SKUs tables of units sold and stockout flags, ending on
    the forecast origin. Built by the backtest, which cuts it at the origin."""

    sold: pd.DataFrame
    stockout: pd.DataFrame

    @classmethod
    def from_frame(cls, frame: pd.DataFrame) -> History:
        validate_demand_frame(frame)
        return cls(sold=to_wide(frame, "units_sold"), stockout=to_wide(frame, "stockout"))

    def until(self, origin: pd.Timestamp) -> History:
        """Only the days up to and including `origin`."""
        return History(sold=self.sold.loc[:origin], stockout=self.stockout.loc[:origin])

    def __len__(self) -> int:
        return len(self.sold)
