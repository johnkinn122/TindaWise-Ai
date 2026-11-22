"""Simple forecasts that any trained model has to beat to be worth using.

Each baseline takes `history`, a dates x SKUs table of units sold that ends on the forecast
origin (the last day whose sales are known), and returns a `horizon` x SKUs table for the
following days. A baseline only ever sees `history`, so it can't peek at the days it forecasts.

History includes stockout days as they were recorded (sales below demand). That drags these
baselines down after a stockout; a later model can learn to correct for it.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

Forecaster = Callable[[pd.DataFrame, int], pd.DataFrame]


def _future_index(history: pd.DataFrame, horizon: int) -> pd.DatetimeIndex:
    if horizon < 1:
        raise ValueError("horizon must be at least 1")
    if history.empty:
        raise ValueError("history is empty")
    return pd.date_range(history.index[-1] + pd.Timedelta(days=1), periods=horizon, freq="D")


def _need(history: pd.DataFrame, days: int, name: str) -> None:
    if len(history) < days:
        raise ValueError(f"{name} needs at least {days} days of history, got {len(history)}")


def naive(history: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Every future day sells what the last known day sold."""
    index = _future_index(history, horizon)
    values = np.tile(history.iloc[-1].to_numpy(dtype=float), (horizon, 1))
    return pd.DataFrame(values, index=index, columns=history.columns)


def seasonal_naive(history: pd.DataFrame, horizon: int, season: int = 7) -> pd.DataFrame:
    """Each future day sells what the same weekday sold in the most recent known week."""
    index = _future_index(history, horizon)
    _need(history, season, "seasonal naive")
    last_season = history.iloc[-season:].to_numpy(dtype=float)
    # Day h ahead (1-based) copies the day `season` before it, wrapping for horizons > season.
    rows = [(h - 1) % season for h in range(1, horizon + 1)]
    return pd.DataFrame(last_season[rows], index=index, columns=history.columns)


def moving_average(history: pd.DataFrame, horizon: int, window: int = 28) -> pd.DataFrame:
    """Every future day sells the average of the last `window` days (28 = four full weeks, so
    each weekday counts equally)."""
    index = _future_index(history, horizon)
    _need(history, window, f"{window}-day moving average")
    mean = history.iloc[-window:].to_numpy(dtype=float).mean(axis=0)
    return pd.DataFrame(np.tile(mean, (horizon, 1)), index=index, columns=history.columns)


BASELINES: dict[str, Forecaster] = {
    "naive": naive,
    "seasonal_naive_7": seasonal_naive,
    "moving_average_28": moving_average,
}
