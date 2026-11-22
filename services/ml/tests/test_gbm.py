import numpy as np
import pandas as pd
import pytest

from tindawise_ml.data import History
from tindawise_ml.gbm import make_lightgbm_forecaster
from tindawise_ml.synthetic import generate_history


@pytest.fixture(scope="module")
def history() -> History:
    return History.from_frame(generate_history(days=200))


def test_forecast_shape_dates_and_products(history):
    forecast = make_lightgbm_forecaster()(history, 7)
    assert forecast.shape == (7, history.sold.shape[1])
    assert list(forecast.columns) == list(history.sold.columns)
    assert forecast.index[0] == history.sold.index[-1] + pd.Timedelta(days=1)
    assert (forecast.to_numpy() >= 0).all()  # Poisson objective: never negative


def test_same_data_same_forecast(history):
    first = make_lightgbm_forecaster()(history, 7)
    second = make_lightgbm_forecaster()(history, 7)
    pd.testing.assert_frame_equal(first, second)


def test_learns_a_weekly_pattern_a_moving_average_cannot_show():
    # Weekends sell 20, weekdays 2, with a little noise: the model must predict the difference.
    rng = np.random.default_rng(0)
    index = pd.date_range("2025-01-06", periods=200, freq="D")  # starts on a Monday
    base = np.where(index.day_of_week >= 5, 20, 2)
    sold = pd.DataFrame({"A": base + rng.integers(0, 2, 200), "B": base + rng.integers(0, 2, 200)})
    sold.index = index
    history = History(sold=sold, stockout=pd.DataFrame(False, index=index, columns=sold.columns))
    forecast = make_lightgbm_forecaster()(history, 7)
    weekend = forecast[forecast.index.day_of_week >= 5]
    weekday = forecast[forecast.index.day_of_week < 5]
    assert weekend.to_numpy().min() > 3 * weekday.to_numpy().max()


def test_too_little_history_is_refused(history):
    with pytest.raises(ValueError, match="at least"):
        make_lightgbm_forecaster()(history.until(history.sold.index[50]), 7)
