import numpy as np
import pandas as pd
import pytest

from tindawise_ml.data import History
from tindawise_ml.features import (
    FEATURES,
    MIN_HISTORY_DAYS,
    prediction_rows,
    training_set,
)

START = "2025-01-06"  # a Monday


def make_history(sold: dict[str, list[int]], stockout_days: dict[str, list[int]] | None = None):
    length = len(next(iter(sold.values())))
    index = pd.date_range(START, periods=length, freq="D")
    sold_frame = pd.DataFrame(sold, index=index)
    flags = pd.DataFrame(False, index=index, columns=sold_frame.columns)
    for sku, rows in (stockout_days or {}).items():
        flags.iloc[rows, flags.columns.get_loc(sku)] = True
    return History(sold=sold_frame, stockout=flags)


def test_prediction_rows_are_h_major_with_products_in_column_order():
    history = make_history({"A": list(range(100)), "B": [5] * 100})
    rows = prediction_rows(history, 3)
    assert list(rows.columns) == list(FEATURES)
    assert rows["h"].tolist() == [1, 1, 2, 2, 3, 3]
    assert rows["sku_code"].tolist() == [0, 1, 0, 1, 0, 1]


def test_window_features_use_only_days_up_to_the_origin():
    values = list(range(100))  # day i sold i units; the origin is day 99
    rows = prediction_rows(make_history({"A": values}), 1).iloc[0]
    assert rows["last"] == 99
    assert rows["mean_7"] == pytest.approx(np.mean(values[-7:]))
    assert rows["mean_28"] == pytest.approx(np.mean(values[-28:]))
    assert rows["mean_91"] == pytest.approx(np.mean(values[-91:]))
    assert rows["std_28"] == pytest.approx(np.std(values[-28:]))


def test_same_weekday_features_look_back_whole_weeks():
    values = list(range(100))
    rows = prediction_rows(make_history({"A": values}), 7)
    for h in range(1, 8):
        row = rows[rows["h"] == h].iloc[0]
        target = 99 + h
        assert row["same_weekday_last"] == target - 7
        assert row["same_weekday_mean_4"] == pytest.approx(
            np.mean([target - 7 * k for k in (1, 2, 3, 4)])
        )


def test_calendar_features_describe_the_target_day():
    history = make_history({"A": [1] * 100})  # 6 Jan 2025 + 99 days = 15 Apr 2025 (Tuesday)
    rows = prediction_rows(history, 2)
    first, second = rows.iloc[0], rows.iloc[1]
    assert (first["day_of_month"], first["month"], first["weekday"]) == (16, 4, 2)  # Wed 16 Apr
    assert first["is_payday"] == 1  # the 16th
    assert (second["day_of_month"], second["is_payday"]) == (17, 0)


def test_stockout_features_ignore_capped_days():
    values = [4] * 100
    values[-3:] = [0, 0, 0]  # the shelf was empty for the last three days
    history = make_history({"A": values}, {"A": [97, 98, 99]})
    row = prediction_rows(history, 1).iloc[0]
    assert row["mean_28"] == pytest.approx(4 * 25 / 28)  # pulled down by the empty days
    assert row["in_stock_mean_28"] == pytest.approx(4)  # what customers actually bought
    assert row["stockout_share_28"] == pytest.approx(3 / 28)
    assert row["last_was_stockout"] == 1


def test_stockout_days_are_never_training_labels():
    values = [3] * 120
    stockouts = [100, 101, 110]
    for day in stockouts:
        values[day] = 0
    features, labels = training_set(make_history({"A": values}, {"A": stockouts}), 2)
    assert (labels == 3).all()
    # Origins 90..118 at h=1 and 90..117 at h=2, minus labels on the three stockout days.
    assert len(labels) == (120 - MIN_HISTORY_DAYS) + (119 - MIN_HISTORY_DAYS) - 3 * 2
    assert len(features) == len(labels)


def test_training_labels_stay_inside_history():
    values = list(range(120))
    features, labels = training_set(make_history({"A": values}), 7)
    assert labels.max() == 119  # the last known day, never beyond
    # A label is the day `h` after the row's origin, whose `last` is the origin's value.
    assert (labels == features["last"].to_numpy() + features["h"].to_numpy()).all()


def test_too_little_history_is_refused():
    short = make_history({"A": [1] * (MIN_HISTORY_DAYS - 1)})
    with pytest.raises(ValueError, match="at least"):
        prediction_rows(short, 1)
    with pytest.raises(ValueError, match="at least"):
        training_set(make_history({"A": [1] * MIN_HISTORY_DAYS}), 7)
