"""Choose LightGBM settings on the validation period, never on the test period.

The data is split by date into three parts:

    |------------- training -------------|-- validation (84 d) --|---- test (84 d) ----|

Tuning scores each candidate on the validation period (every model there trains only on days
before its origin). The winner is written into gbm.DEFAULT_PARAMS by hand and then run on the
test period once. Picking settings by their test score would make the test score optimistic:
it would partly measure luck in the choice, not how the model does on unseen weeks.
"""

from __future__ import annotations

from itertools import product

import pandas as pd

from tindawise_ml.backtest import run_backtest, score, tiling_origins
from tindawise_ml.baselines import moving_average
from tindawise_ml.gbm import BASE_PARAMS, make_lightgbm_forecaster

GRID = {
    "num_leaves": (7, 15, 31),
    "min_data_in_leaf": (50, 200),
    "rounds": (150, 300, 600),
}


def tune(frame: pd.DataFrame, *, period_days: int = 84, horizon: int = 7) -> pd.DataFrame:
    """Validation scores for every grid combination, best WAPE first, with the best baseline
    on the same period as a reference row."""
    origins = tiling_origins(frame, test_days=period_days, horizon=horizon, before_days=period_days)
    forecasters = {"moving_average_28 (reference)": moving_average}
    for leaves, min_leaf, rounds in product(*GRID.values()):
        params = {**BASE_PARAMS, "num_leaves": leaves, "min_data_in_leaf": min_leaf}
        name = f"lightgbm leaves={leaves} min_leaf={min_leaf} rounds={rounds}"
        forecasters[name] = make_lightgbm_forecaster(params, rounds)
    results = score(run_backtest(frame, forecasters, origins, horizon=horizon))
    return results.sort_values("wape", ignore_index=True)
