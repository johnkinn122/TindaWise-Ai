"""LightGBM demand forecaster: one gradient-boosted tree model for all products.

At every forecast origin it trains a fresh model on the history up to that origin (see
features.py) and predicts the next `horizon` days. Retraining per origin is slower than training
once, but it is exactly what would run live, and the model can never have seen the days it is
scored on.

- One model for all products, with the product as a categorical feature. Slow movers have too
  little data for a model of their own, and they share patterns (weekday, payday, season) with
  the fast movers.
- Poisson objective: the target is a count of units, never negative. The model predicts on a log
  scale, so effects multiply (a payday lifts a fast mover by more units than a slow one).
- Deterministic settings (fixed seed, one thread), so a rerun gives the same numbers.

DEFAULT_PARAMS and DEFAULT_ROUNDS were chosen with `python -m tindawise_ml tune`, which scores a
small grid on the validation period only. See docs/ml/EXPERIMENTS.md.
"""

from __future__ import annotations

from typing import Any

import lightgbm as lgb
import pandas as pd

from tindawise_ml.baselines import Forecaster, future_index
from tindawise_ml.data import History
from tindawise_ml.features import CATEGORICAL, prediction_rows, training_set

BASE_PARAMS: dict[str, Any] = {
    "objective": "poisson",
    "learning_rate": 0.05,
    "feature_fraction": 0.9,
    "lambda_l2": 1.0,
    "verbosity": -1,
    "seed": 0,
    "deterministic": True,
    "force_row_wise": True,
    "num_threads": 1,
}

# Chosen on the validation period (see the module docstring).
DEFAULT_PARAMS: dict[str, Any] = {**BASE_PARAMS, "num_leaves": 7, "min_data_in_leaf": 200}
DEFAULT_ROUNDS = 300


def make_lightgbm_forecaster(
    params: dict[str, Any] | None = None, rounds: int = DEFAULT_ROUNDS
) -> Forecaster:
    """A forecaster with the given LightGBM settings (defaults: the tuned ones)."""
    settings = {**(params if params is not None else DEFAULT_PARAMS)}

    def forecast(history: History, horizon: int) -> pd.DataFrame:
        features, labels = training_set(history, horizon)
        data = lgb.Dataset(features, labels, categorical_feature=list(CATEGORICAL))
        booster = lgb.train(settings, data, num_boost_round=rounds)
        predicted = booster.predict(prediction_rows(history, horizon))
        products = history.sold.columns
        return pd.DataFrame(
            predicted.reshape(horizon, len(products)),  # rows come h-major, products in order
            index=future_index(history.sold, horizon),
            columns=products,
        )

    return forecast
