"""Simple forecasts that any trained model has to beat to be worth using.

Each forecaster takes a `History` (units sold and stockout flags, dates x SKUs, ending on the
forecast origin: the last day whose sales are known) and returns a `horizon` x SKUs table for the
following days. A forecaster only ever sees `history`, so it can't peek at the days it forecasts.

The baselines read units sold only, stockout days included as recorded (sales below demand).
That drags them down after a stockout.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

from tindawise_ml.data import History

Forecaster = Callable[[History, int], pd.DataFrame]


def future_index(sold: pd.DataFrame, horizon: int) -> pd.DatetimeIndex:
    if horizon < 1:
        raise ValueError("horizon must be at least 1")
    if sold.empty:
        raise ValueError("history is empty")
    return pd.date_range(sold.index[-1] + pd.Timedelta(days=1), periods=horizon, freq="D")


def _need(sold: pd.DataFrame, days: int, name: str) -> None:
    if len(sold) < days:
        raise ValueError(f"{name} needs at least {days} days of history, got {len(sold)}")


def naive(history: History, horizon: int) -> pd.DataFrame:
    """Every future day sells what the last known day sold."""
    sold = history.sold
    index = future_index(sold, horizon)
    values = np.tile(sold.iloc[-1].to_numpy(dtype=float), (horizon, 1))
    return pd.DataFrame(values, index=index, columns=sold.columns)


def seasonal_naive(history: History, horizon: int, season: int = 7) -> pd.DataFrame:
    """Each future day sells what the same weekday sold in the most recent known week."""
    sold = history.sold
    index = future_index(sold, horizon)
    _need(sold, season, "seasonal naive")
    last_season = sold.iloc[-season:].to_numpy(dtype=float)
    # Day h ahead (1-based) copies the day `season` before it, wrapping for horizons > season.
    rows = [(h - 1) % season for h in range(1, horizon + 1)]
    return pd.DataFrame(last_season[rows], index=index, columns=sold.columns)


def moving_average(history: History, horizon: int, window: int = 28) -> pd.DataFrame:
    """Every future day sells the average of the last `window` days (28 = four full weeks, so
    each weekday counts equally)."""
    sold = history.sold
    index = future_index(sold, horizon)
    _need(sold, window, f"{window}-day moving average")
    mean = sold.iloc[-window:].to_numpy(dtype=float).mean(axis=0)
    return pd.DataFrame(np.tile(mean, (horizon, 1)), index=index, columns=sold.columns)


def in_stock_moving_average(history: History, horizon: int, window: int = 28) -> pd.DataFrame:
    """Like `moving_average`, but averages only the days the product was in stock, so a stretch
    of empty shelf doesn't read as "nobody wants it". A product out of stock for the whole
    window falls back to the plain average (there's nothing else to go on)."""
    sold = history.sold
    index = future_index(sold, horizon)
    _need(sold, window, f"{window}-day in-stock moving average")
    values = sold.iloc[-window:].to_numpy(dtype=float)
    in_stock = ~history.stockout.iloc[-window:].to_numpy()
    days = in_stock.sum(axis=0)
    plain = values.mean(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        kept = np.where(days > 0, (values * in_stock).sum(axis=0) / days, plain)
    return pd.DataFrame(np.tile(kept, (horizon, 1)), index=index, columns=sold.columns)


BASELINES: dict[str, Forecaster] = {
    "naive": naive,
    "seasonal_naive_7": seasonal_naive,
    "moving_average_28": moving_average,
}
