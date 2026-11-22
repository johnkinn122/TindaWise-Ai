import math

import pytest

from tindawise_ml.metrics import mae, rmse, wape


def test_hand_computed_values():
    actual = [10, 0, 4, 6]
    forecast = [8, 1, 4, 9]
    # errors: 2, 1, 0, 3
    assert mae(actual, forecast) == pytest.approx(6 / 4)
    assert rmse(actual, forecast) == pytest.approx(math.sqrt((4 + 1 + 0 + 9) / 4))
    assert wape(actual, forecast) == pytest.approx(6 / 20)


def test_perfect_forecast_scores_zero():
    assert mae([3, 5], [3, 5]) == 0
    assert rmse([3, 5], [3, 5]) == 0
    assert wape([3, 5], [3, 5]) == 0


def test_rmse_punishes_one_big_miss_more_than_mae():
    actual = [0, 0, 0, 0]
    spread = [1, 1, 1, 1]
    one_big = [4, 0, 0, 0]
    assert mae(actual, spread) == mae(actual, one_big)
    assert rmse(actual, one_big) > rmse(actual, spread)


def test_wape_is_undefined_when_nothing_sold():
    assert math.isnan(wape([0, 0], [1, 2]))


def test_wape_handles_zero_days_that_would_break_mape():
    # MAPE would divide by the zero on day 1; WAPE pools the totals instead.
    assert wape([0, 10], [2, 10]) == pytest.approx(0.2)


@pytest.mark.parametrize("metric", [mae, rmse, wape])
def test_rejects_bad_input(metric):
    with pytest.raises(ValueError, match="shape"):
        metric([1, 2], [1])
    with pytest.raises(ValueError, match="no values"):
        metric([], [])
    with pytest.raises(ValueError, match="NaN"):
        metric([1, float("nan")], [1, 2])
