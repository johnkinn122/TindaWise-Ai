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
from tindawise_ml.data import History
from tindawise_ml.metrics import bias, mae, rmse, wape


def tiling_origins(
    frame: pd.DataFrame, *, test_days: int, horizon: int, before_days: int = 0
) -> list[pd.Timestamp]:
    """Origins whose forecast windows exactly cover a period of `test_days` days that ends
    `before_days` days before the last day of `frame`.

    With `before_days=0` that is the test period. With `before_days=test_days` it is the
    validation period just before it, used for tuning so the test period stays unseen.
    """
    if horizon < 1 or test_days < horizon or test_days % horizon:
        raise ValueError("test_days must be a positive multiple of horizon")
    if before_days < 0:
        raise ValueError("before_days can't be negative")
    period_end = frame["date"].max() - pd.Timedelta(days=before_days)
    first_origin = period_end - pd.Timedelta(days=test_days)
    if first_origin < frame["date"].min():
        raise ValueError("period starts before the data")
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
    full = History.from_frame(frame)  # validates the table
    sold, stockout = full.sold, full.stockout
    last_day = sold.index[-1]

    rows = []
    for origin in origins:
        if origin + pd.Timedelta(days=horizon) > last_day:
            raise ValueError(f"origin {origin.date()} + {horizon} days runs past the data")
        history = full.until(origin)  # up to and including the origin, nothing after
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


def _measures(actual: pd.Series, forecast: pd.Series) -> dict[str, float]:
    if actual.empty:
        return dict.fromkeys(("mae", "rmse", "wape", "bias"), float("nan"))
    return {
        "mae": mae(actual, forecast),
        "rmse": rmse(actual, forecast),
        "wape": wape(actual, forecast),
        "bias": bias(actual, forecast),
    }


def _keyed(keys: list[str], key: object) -> dict[str, object]:
    return dict(zip(keys, key if isinstance(key, tuple) else (key,), strict=True))


def score(forecasts: pd.DataFrame, by: list[str] | None = None) -> pd.DataFrame:
    """Daily MAE, RMSE, WAPE and bias per model (and per `by` columns), skipping stockout days.

    `scored_days` is how many product-days counted; `skipped_stockout_days` how many were left out.
    """
    keys = ["model", *(by or [])]
    out = []
    for key, group in forecasts.groupby(keys, sort=True):
        usable = group[~group["stockout"]]
        row = _keyed(keys, key)
        row["scored_days"] = len(usable)
        row["skipped_stockout_days"] = len(group) - len(usable)
        row.update(_measures(usable["actual"], usable["forecast"]))
        out.append(row)
    return pd.DataFrame(out)


def score_totals(forecasts: pd.DataFrame, by: list[str] | None = None) -> pd.DataFrame:
    """The same measures on each forecast window's total per product (a week, for a 7-day
    horizon), which is what a reorder decision depends on. Stockout days are left out of both
    the forecast and the actual total, so a window is compared over the same days.

    Daily noise partly cancels in a total, so this shows differences in level, trend and season
    that daily scores bury under noise.
    """
    usable = forecasts[~forecasts["stockout"]]
    totals = usable.groupby(["model", "origin", "sku"], as_index=False)[
        ["forecast", "actual"]
    ].sum()
    keys = ["model", *(by or [])]
    out = []
    for key, group in totals.groupby(keys, sort=True):
        row = _keyed(keys, key)
        row["scored_windows"] = len(group)
        row.update(_measures(group["actual"], group["forecast"]))
        out.append(row)
    return pd.DataFrame(out)
