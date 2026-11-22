"""Rolling-origin backtest: replay the past as if forecasting live.

For each origin (a past day), a forecaster sees only the sales up to and including that day and
predicts the next `horizon` days. Those predictions are compared with what was actually sold.
Origins step forward one horizon at a time, so the forecast windows tile the test period without
overlapping. Data is always split by date, never shuffled: shuffling would let a model learn from
days that come after the ones it is scored on (leakage).

Scoring skips stockout days. On those days `units_sold` is only what was on the shelf, not what
customers wanted, so a forecast above it may be right and a forecast below it may look better
than it is.
"""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

from tindawise_ml.baselines import Forecaster
from tindawise_ml.data import to_wide, validate_demand_frame
from tindawise_ml.metrics import mae, rmse, wape


def tiling_origins(frame: pd.DataFrame, *, test_days: int, horizon: int) -> list[pd.Timestamp]:
    """Origins whose forecast windows exactly cover the last `test_days` days of `frame`."""
    if horizon < 1 or test_days < horizon or test_days % horizon:
        raise ValueError("test_days must be a positive multiple of horizon")
    last = frame["date"].max()
    first_origin = last - pd.Timedelta(days=test_days)
    if first_origin < frame["date"].min():
        raise ValueError("test period is longer than the data")
    return [first_origin + pd.Timedelta(days=d) for d in range(0, test_days, horizon)]


def run_backtest(
    frame: pd.DataFrame,
    forecasters: Mapping[str, Forecaster],
    origins: list[pd.Timestamp],
    *,
    horizon: int,
) -> pd.DataFrame:
    """Long table of every forecast: model, origin, date, h (days ahead), sku, forecast,
    actual, stockout."""
    validate_demand_frame(frame)
    sold = to_wide(frame, "units_sold")
    stockout = to_wide(frame, "stockout")
    last_day = sold.index[-1]

    rows = []
    for origin in origins:
        if origin + pd.Timedelta(days=horizon) > last_day:
            raise ValueError(f"origin {origin.date()} + {horizon} days runs past the data")
        history = sold.loc[:origin]  # up to and including the origin, nothing after
        for name, forecaster in forecasters.items():
            forecast = forecaster(history, horizon)
            long = forecast.stack().rename("forecast").reset_index()
            long.columns = ["date", "sku", "forecast"]
            long["model"] = name
            long["origin"] = origin
            rows.append(long)

    result = pd.concat(rows, ignore_index=True)
    result["h"] = (result["date"] - result["origin"]).dt.days
    actual = sold.stack().rename("actual")
    flagged = stockout.stack().rename("stockout")
    result = result.join(actual, on=["date", "sku"]).join(flagged, on=["date", "sku"])
    return result[["model", "origin", "date", "h", "sku", "forecast", "actual", "stockout"]]


def score(forecasts: pd.DataFrame, by: list[str] | None = None) -> pd.DataFrame:
    """MAE, RMSE and WAPE per model (and per `by` columns), skipping stockout days.

    `scored_days` is how many product-days counted; `skipped_stockout_days` how many were left out.
    """
    keys = ["model", *(by or [])]
    out = []
    for key, group in forecasts.groupby(keys, sort=True):
        usable = group[~group["stockout"]]
        row = dict(zip(keys, key if isinstance(key, tuple) else (key,), strict=True))
        row["scored_days"] = len(usable)
        row["skipped_stockout_days"] = len(group) - len(usable)
        if usable.empty:
            row.update(mae=float("nan"), rmse=float("nan"), wape=float("nan"))
        else:
            row.update(
                mae=mae(usable["actual"], usable["forecast"]),
                rmse=rmse(usable["actual"], usable["forecast"]),
                wape=wape(usable["actual"], usable["forecast"]),
            )
        out.append(row)
    return pd.DataFrame(out)
