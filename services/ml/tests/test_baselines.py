import numpy as np
import pandas as pd
import pytest

from tindawise_ml.baselines import BASELINES, moving_average, naive, seasonal_naive


def make_history(values_by_sku: dict[str, list[int]], start: str = "2025-03-03") -> pd.DataFrame:
    length = len(next(iter(values_by_sku.values())))
    index = pd.date_range(start, periods=length, freq="D")
    return pd.DataFrame(values_by_sku, index=index)


def test_naive_repeats_the_last_day():
    history = make_history({"A": [1, 2, 3], "B": [9, 8, 7]})
    forecast = naive(history, 3)
    assert forecast["A"].tolist() == [3, 3, 3]
    assert forecast["B"].tolist() == [7, 7, 7]


def test_forecast_dates_start_the_day_after_the_origin():
    history = make_history({"A": list(range(28))})  # 3 to 30 March
    for name, forecaster in BASELINES.items():
        forecast = forecaster(history, 2)
        assert forecast.index.tolist() == [
            pd.Timestamp("2025-03-31"),
            pd.Timestamp("2025-04-01"),
        ], name


def test_seasonal_naive_copies_the_same_weekday_last_week():
    week1 = [10, 11, 12, 13, 14, 15, 16]
    week2 = [20, 21, 22, 23, 24, 25, 26]
    history = make_history({"A": week1 + week2})
    assert seasonal_naive(history, 7)["A"].tolist() == week2
    # Beyond one week it wraps around to the same last known week.
    assert seasonal_naive(history, 9)["A"].tolist() == [*week2, 20, 21]


def test_moving_average_uses_only_the_last_window():
    history = make_history({"A": [1000] * 5 + [2] * 28})
    assert moving_average(history, 2)["A"].tolist() == [2.0, 2.0]
    assert moving_average(history, 1, window=3)["A"].tolist() == [2.0]


def test_too_little_history_is_refused():
    short = make_history({"A": [1, 2, 3]})
    with pytest.raises(ValueError, match="at least 7"):
        seasonal_naive(short, 1)
    with pytest.raises(ValueError, match="at least 28"):
        moving_average(short, 1)
    with pytest.raises(ValueError, match="horizon"):
        naive(short, 0)


def test_forecasts_are_never_negative_for_non_negative_history():
    rng = np.random.default_rng(1)
    history = make_history({"A": rng.integers(0, 5, 60).tolist()})
    for name, forecaster in BASELINES.items():
        assert (forecaster(history, 7).to_numpy() >= 0).all(), name
