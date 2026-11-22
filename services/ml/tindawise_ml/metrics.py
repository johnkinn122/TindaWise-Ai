"""Forecast error measures. All take arrays of actual units and forecast units of equal length.

- MAE  (mean absolute error): average units the forecast is off by. Easy to read per product.
- RMSE (root mean squared error): like MAE but punishes big misses more. Matters for stock,
  because one big under-forecast empties the shelf.
- WAPE (weighted absolute percentage error): total units off / total units sold. Unlike MAPE it
  doesn't blow up on zero-sales days, and it lets products of different volumes be pooled.
  0.30 means the forecasts were off by 30% of what was sold.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike


def _pair(actual: ArrayLike, forecast: ArrayLike) -> tuple[np.ndarray, np.ndarray]:
    a = np.asarray(actual, dtype=float)
    f = np.asarray(forecast, dtype=float)
    if a.shape != f.shape:
        raise ValueError(f"actual and forecast differ in shape: {a.shape} vs {f.shape}")
    if a.size == 0:
        raise ValueError("no values to score")
    if np.isnan(a).any() or np.isnan(f).any():
        raise ValueError("values contain NaN")
    return a, f


def mae(actual: ArrayLike, forecast: ArrayLike) -> float:
    a, f = _pair(actual, forecast)
    return float(np.mean(np.abs(a - f)))


def rmse(actual: ArrayLike, forecast: ArrayLike) -> float:
    a, f = _pair(actual, forecast)
    return float(np.sqrt(np.mean((a - f) ** 2)))


def wape(actual: ArrayLike, forecast: ArrayLike) -> float:
    """NaN when nothing was sold at all: a percentage of zero isn't defined."""
    a, f = _pair(actual, forecast)
    total = np.sum(np.abs(a))
    if total == 0:
        return float("nan")
    return float(np.sum(np.abs(a - f)) / total)
