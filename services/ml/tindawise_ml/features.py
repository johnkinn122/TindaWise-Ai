"""Feature rows for the direct multi-horizon forecaster.

One row = (origin day i, horizon h, product). Its features use only days <= i, and its label is
units sold on day i + h. "Direct" means one model predicts any h straight from the origin, instead
of predicting tomorrow and feeding that back in to predict the day after (recursive), which
compounds errors and makes leakage harder to rule out.

Features, per product, as of the origin:
    last, last_was_stockout         the origin day itself
    mean_7, mean_28, mean_91        recent averages (91 = 13 weeks, the longest window)
    std_28                          how noisy the product is
    in_stock_mean_28                average over the last 28 days *excluding* stockout days,
                                    an estimate of demand that the stockouts didn't cap
    stockout_share_28               share of the last 28 days that were stockout days
    same_weekday_last               the target's weekday, most recent known week
    same_weekday_mean_4             the target's weekday, mean of the 4 most recent known weeks
and about the target day: h, weekday, day of month, payday, month; plus the product (categorical).
"""

from __future__ import annotations

import calendar

import numpy as np
import pandas as pd

from tindawise_ml.data import History

MIN_HISTORY_DAYS = 91  # the longest window; the first usable origin is the 91st day

FEATURES = (
    "sku_code",
    "h",
    "last",
    "last_was_stockout",
    "mean_7",
    "mean_28",
    "mean_91",
    "std_28",
    "in_stock_mean_28",
    "stockout_share_28",
    "same_weekday_last",
    "same_weekday_mean_4",
    "weekday",
    "day_of_month",
    "is_payday",
    "month",
)
CATEGORICAL = ("sku_code",)


class _Windows:
    """Rolling statistics for every origin at once (arrays of days x products)."""

    def __init__(self, history: History) -> None:
        sold = history.sold.astype(float)
        in_stock = ~history.stockout.to_numpy()
        self.y = sold.to_numpy()
        self.stockout = history.stockout.to_numpy()
        self.dates = history.sold.index
        self.mean_7 = sold.rolling(7).mean().to_numpy()
        self.mean_28 = sold.rolling(28).mean().to_numpy()
        self.mean_91 = sold.rolling(91).mean().to_numpy()
        self.std_28 = sold.rolling(28).std(ddof=0).to_numpy()
        kept = pd.DataFrame(np.where(in_stock, self.y, 0.0)).rolling(28).sum().to_numpy()
        kept_days = pd.DataFrame(in_stock.astype(float)).rolling(28).sum().to_numpy()
        with np.errstate(invalid="ignore", divide="ignore"):
            # NaN when all 28 days were stockouts; LightGBM treats NaN as "unknown".
            self.in_stock_mean_28 = kept / kept_days
        self.stockout_share_28 = 1.0 - kept_days / 28.0


def _payday(dates: pd.DatetimeIndex) -> np.ndarray:
    last = np.array([calendar.monthrange(d.year, d.month)[1] for d in dates])
    day = dates.day.to_numpy()
    return (day == 1) | (day == 15) | (day == 16) | (day == last)


def _rows(w: _Windows, origins: np.ndarray, h: int) -> pd.DataFrame:
    """Features for origin rows `origins` (indexes into history) at horizon h, origin-major."""
    n_products = w.y.shape[1]
    # The target's weekday in the most recent week that is fully known at the origin.
    weeks_back = -(-h // 7)  # ceil(h / 7)
    same = origins + h - 7 * weeks_back
    same_mean = np.mean([w.y[same - 7 * k] for k in range(4)], axis=0)

    target_dates = w.dates[origins] + pd.Timedelta(days=h)
    calendar_cols = {
        "weekday": target_dates.day_of_week.to_numpy(),
        "day_of_month": target_dates.day.to_numpy(),
        "is_payday": _payday(target_dates).astype(int),
        "month": target_dates.month.to_numpy(),
    }

    def per_product(values: np.ndarray) -> np.ndarray:
        return values.reshape(-1)  # (origins, products) -> origin-major flat

    def per_origin(values: np.ndarray) -> np.ndarray:
        return np.repeat(values, n_products)

    columns = {
        "sku_code": np.tile(np.arange(n_products), len(origins)),
        "h": np.full(len(origins) * n_products, h),
        "last": per_product(w.y[origins]),
        "last_was_stockout": per_product(w.stockout[origins]).astype(int),
        "mean_7": per_product(w.mean_7[origins]),
        "mean_28": per_product(w.mean_28[origins]),
        "mean_91": per_product(w.mean_91[origins]),
        "std_28": per_product(w.std_28[origins]),
        "in_stock_mean_28": per_product(w.in_stock_mean_28[origins]),
        "stockout_share_28": per_product(w.stockout_share_28[origins]),
        "same_weekday_last": per_product(w.y[same]),
        "same_weekday_mean_4": per_product(same_mean),
        **{name: per_origin(values) for name, values in calendar_cols.items()},
    }
    return pd.DataFrame(columns, columns=list(FEATURES))


def training_set(history: History, horizon: int) -> tuple[pd.DataFrame, np.ndarray]:
    """Every (origin, h, product) whose label day is inside `history` and not a stockout day.

    Stockout days are dropped as labels because their sales are below demand: training on them
    would teach the model to predict empty shelves.
    """
    if len(history) < MIN_HISTORY_DAYS + horizon:
        raise ValueError(
            f"need at least {MIN_HISTORY_DAYS + horizon} days of history, got {len(history)}"
        )
    w = _Windows(history)
    frames, labels = [], []
    for h in range(1, horizon + 1):
        origins = np.arange(MIN_HISTORY_DAYS - 1, len(history) - h)
        rows = _rows(w, origins, h)
        label = w.y[origins + h].reshape(-1)
        keep = ~w.stockout[origins + h].reshape(-1)
        frames.append(rows[keep])
        labels.append(label[keep])
    return pd.concat(frames, ignore_index=True), np.concatenate(labels)


def prediction_rows(history: History, horizon: int) -> pd.DataFrame:
    """Rows for the last day of `history` as the origin, h = 1..horizon, h-major."""
    if len(history) < MIN_HISTORY_DAYS:
        raise ValueError(f"need at least {MIN_HISTORY_DAYS} days of history, got {len(history)}")
    w = _Windows(history)
    origin = np.array([len(history) - 1])
    return pd.concat([_rows(w, origin, h) for h in range(1, horizon + 1)], ignore_index=True)
