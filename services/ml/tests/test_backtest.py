import math

import pandas as pd
import pytest

from tindawise_ml.backtest import run_backtest, score, tiling_origins
from tindawise_ml.baselines import BASELINES, naive
from tindawise_ml.data import DemandFrameError
from tindawise_ml.synthetic import generate_history


@pytest.fixture(scope="module")
def history() -> pd.DataFrame:
    return generate_history(days=200)


def tiny_frame(units: list[int], stockout: list[bool] | None = None) -> pd.DataFrame:
    days = pd.date_range("2025-01-01", periods=len(units), freq="D")
    return pd.DataFrame(
        {
            "date": days,
            "sku": "A",
            "units_sold": pd.array(units, dtype="int64"),
            "stockout": stockout or [False] * len(units),
        }
    )


def test_origins_tile_the_test_period(history):
    origins = tiling_origins(history, test_days=28, horizon=7)
    last = history["date"].max()
    assert len(origins) == 4
    assert origins[0] == last - pd.Timedelta(days=28)
    assert origins[-1] + pd.Timedelta(days=7) == last


@pytest.mark.parametrize(("test_days", "horizon"), [(10, 7), (0, 7), (7, 0)])
def test_origins_reject_uneven_periods(history, test_days, horizon):
    with pytest.raises(ValueError):
        tiling_origins(history, test_days=test_days, horizon=horizon)


def test_every_test_day_is_forecast_once_per_model(history):
    origins = tiling_origins(history, test_days=28, horizon=7)
    forecasts = run_backtest(history, BASELINES, origins, horizon=7)
    products = history["sku"].nunique()
    assert len(forecasts) == len(BASELINES) * 28 * products
    assert not forecasts.duplicated(["model", "date", "sku"]).any()
    assert forecasts["h"].between(1, 7).all()
    assert (forecasts["date"] > forecasts["origin"]).all()


def test_no_leakage_changing_the_future_does_not_change_forecasts(history):
    """A forecast made at an origin must be identical whatever happened after that origin."""
    origins = tiling_origins(history, test_days=28, horizon=7)
    first = origins[0]
    tampered = history.copy()
    after = tampered["date"] > first
    tampered.loc[after, "units_sold"] = tampered.loc[after, "units_sold"] * 10 + 99

    original = run_backtest(history, BASELINES, [first], horizon=7)
    changed = run_backtest(tampered, BASELINES, [first], horizon=7)
    pd.testing.assert_series_equal(original["forecast"], changed["forecast"])
    # ...while the actuals it is scored against did change, so the test can tell the difference.
    assert not original["actual"].equals(changed["actual"])


def test_the_true_demand_column_is_never_read(history):
    without_demand = history.drop(columns="demand")
    origins = tiling_origins(history, test_days=14, horizon=7)
    pd.testing.assert_frame_equal(
        run_backtest(history, BASELINES, origins, horizon=7),
        run_backtest(without_demand, BASELINES, origins, horizon=7),
    )


def test_stockout_days_are_skipped_in_scoring():
    # Days 1-7 known; naive forecasts 5 for days 8-10. Day 9 sold 0 because the shelf was empty.
    frame = tiny_frame([5] * 7 + [5, 0, 7], stockout=[False] * 8 + [True, False])
    origin = frame["date"][6]
    scored = score(run_backtest(frame, {"naive": naive}, [origin], horizon=3)).iloc[0]
    assert scored["scored_days"] == 2
    assert scored["skipped_stockout_days"] == 1
    assert scored["mae"] == pytest.approx((0 + 2) / 2)
    assert scored["wape"] == pytest.approx(2 / 12)


def test_score_by_sku(history):
    origins = tiling_origins(history, test_days=14, horizon=7)
    forecasts = run_backtest(history, BASELINES, origins, horizon=7)
    per_sku = score(forecasts, by=["sku"])
    assert len(per_sku) == len(BASELINES) * history["sku"].nunique()
    assert set(per_sku.columns) >= {"model", "sku", "mae", "rmse", "wape", "scored_days"}


def test_a_group_with_only_stockout_days_scores_nan():
    frame = tiny_frame([3] * 7 + [0, 0], stockout=[False] * 7 + [True, True])
    scored = score(run_backtest(frame, {"naive": naive}, [frame["date"][6]], horizon=2)).iloc[0]
    assert scored["scored_days"] == 0
    assert math.isnan(scored["mae"])


def test_an_origin_too_close_to_the_end_is_refused(history):
    last = history["date"].max()
    with pytest.raises(ValueError, match="runs past"):
        run_backtest(history, BASELINES, [last - pd.Timedelta(days=3)], horizon=7)


def test_invalid_tables_are_refused():
    gappy = tiny_frame([1, 2, 3, 4]).drop(index=2)
    gappy = pd.concat([gappy, tiny_frame([1, 2, 3, 4]).assign(sku="B")], ignore_index=True)
    with pytest.raises(DemandFrameError, match="missing days"):
        run_backtest(gappy, {"naive": naive}, [pd.Timestamp("2025-01-02")], horizon=1)
