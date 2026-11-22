import math

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from tindawise_ml import anomalies
from tindawise_ml.anomalies import (
    DETECTORS,
    Outcome,
    average_precision,
    best_threshold,
    count_tail_score,
    evaluate,
    inject_anomalies,
    outcome_at,
    ratio_score,
    robust_z_score,
    scored_days,
)
from tindawise_ml.synthetic import generate_history


@pytest.fixture(scope="module")
def history() -> pd.DataFrame:
    return generate_history(days=200)


def wide(values: list[float], stockout: list[bool] | None = None):
    index = pd.date_range("2025-01-01", periods=len(values), freq="D")
    sold = pd.DataFrame({"A": values}, index=index)
    flags = pd.DataFrame({"A": stockout or [False] * len(values)}, index=index)
    return sold, flags


# ── Planting ────────────────────────────────────────────────────────────────


def test_injection_is_labelled_and_only_on_in_stock_days(history):
    start = history["date"].max() - pd.Timedelta(days=60)
    planted, labels = inject_anomalies(history, rate=0.05, seed=1, start=start)
    assert len(labels) > 10
    merged = labels.merge(history, on=["date", "sku"])
    assert (merged["date"] >= start).all()
    assert not merged["stockout"].any()
    assert (merged["original"] == merged["units_sold"]).all()  # labels keep the true value

    changed = planted["units_sold"] != history["units_sold"]
    assert changed.sum() == len(labels)  # every change is labelled, nothing else moved
    after = planted.merge(labels, on=["date", "sku"])
    assert (after["units_sold"] == after["injected"]).all()


def test_spikes_add_at_least_five_and_drops_go_to_zero_on_regular_sellers(history):
    _, labels = inject_anomalies(history, rate=0.1, seed=2)
    spikes, drops = labels[labels["kind"] == "spike"], labels[labels["kind"] == "drop"]
    assert (spikes["injected"] >= spikes["original"] + 5).all()
    assert (drops["injected"] == 0).all() and (drops["original"] > 0).all()
    usual = history.groupby("sku")["units_sold"].mean()
    assert (usual[drops["sku"]] >= 3).all()  # a zero day for a slow seller is normal


def test_same_seed_same_anomalies(history):
    a = inject_anomalies(history, seed=5)[1]
    pd.testing.assert_frame_equal(a, inject_anomalies(history, seed=5)[1])
    assert not a.equals(inject_anomalies(history, seed=6)[1])


# ── Detectors ───────────────────────────────────────────────────────────────


def test_scores_use_only_earlier_days(history):
    """Changing day d and everything after it must not change any score before d."""
    sold = history.pivot(index="date", columns="sku", values="units_sold")
    flags = history.pivot(index="date", columns="sku", values="stockout")
    cut = sold.index[150]
    tampered = sold.copy()
    tampered.loc[cut:] = tampered.loc[cut:] * 7 + 3
    for name, detector in DETECTORS.items():
        for before, after in zip(detector(sold, flags), detector(tampered, flags), strict=True):
            earlier = sold.index[149]
            pd.testing.assert_frame_equal(before.loc[:earlier], after.loc[:earlier], obj=name)


def test_too_little_history_is_not_scored():
    sold, flags = wide([3.0] * 20)
    for detector in DETECTORS.values():
        for table in detector(sold, flags):
            assert table["A"].iloc[:14].isna().all()  # needs 14 earlier in-stock days
            assert table["A"].iloc[14:].notna().all()


def test_stockout_days_are_not_history():
    # 20 in-stock days at 4, then 10 empty-shelf days at 0, then a normal day of 4.
    sold, flags = wide([4.0] * 20 + [0.0] * 10 + [4.0], [False] * 20 + [True] * 10 + [False])
    high, low = ratio_score(sold, flags)
    # 4 vs a usual 4 in both directions: the empty-shelf zeros weren't counted as sales.
    assert (high["A"].iloc[-1], low["A"].iloc[-1]) == (pytest.approx(0.0), pytest.approx(0.0))


def test_ratio_score_by_hand():
    sold, flags = wide([2.0, 4.0] * 14 + [15.0, 0.0])
    high, low = ratio_score(sold, flags)
    # The last 28 earlier days average 3: high = log(16/4) for 15 sold, low = log(4/1) for 0.
    assert high["A"].iloc[-2] == pytest.approx(math.log(16 / 4))
    window = [2.0, 4.0] * 13 + [4.0, 15.0]  # day 30's window: days 2-29
    assert low["A"].iloc[-1] == pytest.approx(math.log((np.mean(window) + 1) / 1))


def test_robust_z_by_hand_ignores_one_extreme_day():
    history = [5.0] * 27 + [60.0]  # one huge day in the window
    sold, flags = wide([*history, 9.0])
    high, _ = robust_z_score(sold, flags)
    # Median 5, MAD 0: z = (9 - 5) / (0 + 0.5) = 8, the 60 doesn't move it.
    assert high["A"].iloc[-1] == pytest.approx(8.0)


def test_count_tail_by_hand_poisson_when_no_spread():
    sold, flags = wide([4.0] * 28 + [10.0, 0.0])
    high, low = count_tail_score(sold, flags)
    # Constant history: variance 0, so Poisson with mean 4.
    assert high["A"].iloc[-2] == pytest.approx(-math.log10(stats.poisson.sf(9, 4)))
    # Next day's window has the 10 in it, but its variance (1.24) is still below its mean (4.21),
    # so it stays Poisson: P(Y <= 0) = exp(-mean).
    window = [4.0] * 27 + [10.0]
    assert np.var(window) < np.mean(window)
    assert low["A"].iloc[-1] == pytest.approx(np.mean(window) / math.log(10))


def test_count_tail_uses_a_negative_binomial_when_sales_are_noisy():
    window = [0.0, 8.0] * 14  # mean 4, variance 16: overdispersed
    sold, flags = wide([*window, 12.0])
    high, _ = count_tail_score(sold, flags)
    mean, var = 4.0, 16.0
    k = mean**2 / (var - mean)
    expected = -math.log10(stats.nbinom.sf(11, k, k / (k + mean)))
    assert high["A"].iloc[-1] == pytest.approx(expected)
    # The same 12 under a Poisson with mean 4 would look far more unusual.
    assert high["A"].iloc[-1] < -math.log10(stats.poisson.sf(11, mean))


def test_directions_are_separate():
    sold, flags = wide([5.0] * 28 + [30.0, 0.0])
    for detector in DETECTORS.values():
        high, low = detector(sold, flags)
        assert high["A"].iloc[-2] > high["A"].iloc[-1]  # 30 is high, 0 isn't
        assert low["A"].iloc[-1] > low["A"].iloc[-2]  # 0 is low, 30 isn't


# ── Metrics and evaluation ──────────────────────────────────────────────────


def days_table(scores, truth):
    dates = pd.date_range("2025-01-01", periods=len(scores), freq="D")
    return pd.DataFrame({"date": dates, "sku": "A", "score": scores, "anomaly": truth})


def test_outcome_and_threshold_by_hand():
    days = days_table([9, 8, 7, 1, 0.5, 6, 0.2], [True, False, True, False, False, True, False])
    result = outcome_at(days, 6)
    assert (result.alerts, result.true_alerts, result.anomalies) == (4, 3, 3)
    assert (result.precision, result.recall) == (0.75, 1.0)
    assert result.false_alarms_per_week == pytest.approx(1.0)  # 7 days = 1 week
    assert best_threshold(days) == 6  # F1 0.857, better than 7 (0.8) or 9 (0.5)


def test_outcome_with_no_alerts_or_anomalies():
    empty = Outcome(threshold=1, alerts=0, true_alerts=0, anomalies=0, weeks=1)
    assert math.isnan(empty.precision) and math.isnan(empty.recall)
    assert best_threshold(days_table([1, 2], [False, False])) == math.inf


def test_average_precision_by_hand():
    # Ranked: hit, miss, hit, miss: precisions at the hits 1/1 and 2/3.
    scores = np.array([0.9, 0.8, 0.7, 0.1])
    truth = np.array([True, False, True, False])
    assert average_precision(scores, truth) == pytest.approx((1 + 2 / 3) / 2)
    assert math.isnan(average_precision(scores, np.zeros(4, bool)))


def test_scored_days_keep_only_judgeable_days(history):
    planted, labels = inject_anomalies(history, seed=3, start=history["date"].min())
    days = scored_days(planted, labels, ratio_score, "spike")
    merged = days.merge(history[["date", "sku", "stockout"]], on=["date", "sku"])
    assert not merged["stockout"].any()
    assert days["score"].notna().all()
    spikes = labels[labels["kind"] == "spike"].set_index(["date", "sku"]).index
    flagged = days[days["anomaly"]].set_index(["date", "sku"]).index
    assert flagged.isin(spikes).all()


def test_thresholds_are_chosen_without_the_test_days(history, monkeypatch):
    last = history["date"].max()
    test_start = last - pd.Timedelta(days=27)
    validation_start = test_start - pd.Timedelta(days=28)
    planted, labels = inject_anomalies(history, rate=0.05, seed=4, start=validation_start)
    seen = []

    def spy(days):
        seen.append((days["date"].min(), days["date"].max()))
        return best_threshold(days)

    monkeypatch.setattr(anomalies, "best_threshold", spy)
    result = evaluate(planted, labels, validation_start=validation_start, test_start=test_start)
    assert len(result) == len(DETECTORS) * 2
    assert all(low >= validation_start and high < test_start for low, high in seen)
    assert set(result["kind"]) == {"spike", "drop"}
