import math

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from tindawise_ml import shrinkage
from tindawise_ml.shrinkage import (
    DETECTORS,
    WINDOW_DAYS,
    ShrinkageConfig,
    StoreRecords,
    Window,
    checkpoints,
    detection_delays,
    evaluate,
    label_at,
    poisson_score,
    share_score,
    simulate_store,
    simulate_stores,
    units_score,
    window_at,
)
from tindawise_ml.synthetic import generate_history

QUIET = ShrinkageConfig(
    base_loss_rate=(0.0, 0.0), problem_share=0.0, damage_rate=0.0, miscount_probability=0.0
)


def adjustments(records: StoreRecords) -> pd.DataFrame:
    return records.movements[records.movements["reason"] == "adjustment"]


# ── Simulation ──────────────────────────────────────────────────────────────


def test_nothing_missing_means_no_corrections_and_records_match_the_shelf():
    records = simulate_store(days=200, config=QUIET)
    assert records.movements.empty and records.labels.empty
    daily = records.daily
    assert (daily["true_stock"] == daily["recorded_stock"]).all()


def test_a_count_brings_the_records_back_to_the_shelf():
    config = ShrinkageConfig(
        problem_share=0.0, damage_rate=0.0, miscount_probability=0.0, base_loss_rate=(0.05, 0.05)
    )
    records = simulate_store(days=300, config=config)
    counted = adjustments(records)
    assert len(counted) > 0 and (counted["change"] < 0).all()  # only losses, never found stock
    days = records.daily.merge(counted[["date", "sku"]], on=["date", "sku"])
    assert (days["true_stock"] == days["recorded_stock"]).all()


def test_stock_never_goes_negative_and_recorded_damage_is_on_both_levels():
    records = simulate_store(days=300)
    daily = records.daily
    assert (daily["true_stock"] >= 0).all() and (daily["recorded_stock"] >= 0).all()
    damage = records.movements[records.movements["reason"] == "damage"]
    assert len(damage) > 0 and (damage["change"] < 0).all()


def test_stockout_follows_the_records_and_phantom_stock_happens():
    # A heavy unnoticed loss and almost no counts: the shelf empties while the records don't.
    config = ShrinkageConfig(
        count_every_days=1000, base_loss_rate=(0.3, 0.3), problem_share=0.0, damage_rate=0.0
    )
    daily = simulate_store(days=300, config=config).daily
    assert (daily["stockout"] == (daily["recorded_stock"] == 0)).all()
    phantom = daily[(daily["true_stock"] == 0) & (daily["recorded_stock"] > 0)]
    assert len(phantom) > 0


def test_problems_are_planted_within_the_dates_and_rates():
    config = ShrinkageConfig(problem_share=0.25, problem_loss_rate=(0.03, 0.15))
    records = simulate_store(
        days=400, seed=7, problems_from=pd.Timestamp("2024-06-01").date(),
        problems_until=pd.Timestamp("2024-12-01").date(), config=config,
    )  # fmt: skip
    labels = records.labels
    assert len(labels) == round(0.25 * 17)
    assert labels["sku"].is_unique
    assert labels["onset"].between(pd.Timestamp("2024-06-01"), pd.Timestamp("2024-12-01")).all()
    assert labels["loss_rate"].between(0.03, 0.15).all()


def test_a_problem_shows_as_missing_stock_after_it_starts():
    records = simulate_store(days=500, seed=3, problems_from=pd.Timestamp("2024-08-01").date())
    sku, onset = records.labels.iloc[0][["sku", "onset"]]
    lost = adjustments(records)
    mine = lost[lost["sku"] == sku]
    before = -mine[mine["date"] < onset]["change"].sum() / max(
        (onset - records.daily["date"].min()).days, 1
    )
    after = (
        -mine[mine["date"] >= onset]["change"].sum() / (records.daily["date"].max() - onset).days
    )
    assert after > before  # units missing per day go up


def test_same_seed_same_records_and_earlier_experiments_untouched():
    first, second = simulate_store(days=150, seed=5), simulate_store(days=150, seed=5)
    pd.testing.assert_frame_equal(first.daily, second.daily)
    pd.testing.assert_frame_equal(first.movements, second.movements)
    pd.testing.assert_frame_equal(first.labels, second.labels)
    assert not simulate_store(days=150, seed=6).daily.equals(first.daily)
    # generate_history (used by every earlier experiment) is the same before and after
    # simulating a store: its random streams are separate.
    before = generate_history(days=60)
    simulate_store(days=60)
    pd.testing.assert_frame_equal(before, generate_history(days=60))


def test_simulate_stores_makes_one_per_seed():
    stores = simulate_stores([1, 2])
    assert len(stores) == 2
    assert not stores[0].daily.equals(stores[1].daily)


# ── Windows and detectors ───────────────────────────────────────────────────


def tiny_store(movements: list[tuple[str, str, str, int]], sold_per_day: int = 2) -> StoreRecords:
    days = pd.date_range("2025-01-01", periods=300, freq="D")
    daily = pd.DataFrame(
        [
            {"date": d, "sku": sku, "units_sold": sold_per_day, "stockout": False,
             "true_stock": 10, "recorded_stock": 10}
            for d in days for sku in ("A", "B")
        ]
    )  # fmt: skip
    moved = pd.DataFrame(
        [{"date": pd.Timestamp(d), "sku": s, "reason": r, "change": c} for d, s, r, c in movements],
        columns=["date", "sku", "reason", "change"],
    )
    labels = pd.DataFrame(columns=["sku", "onset", "loss_rate"])
    return StoreRecords(daily=daily, movements=moved, labels=labels)


def test_window_nets_count_corrections_and_ignores_damage():
    checkpoint = pd.Timestamp("2025-10-01")
    inside = checkpoint - pd.Timedelta(days=10)
    store = tiny_store(
        [
            (inside, "A", "adjustment", -5),
            (inside, "A", "adjustment", 2),  # a later count found 2 back
            (inside, "A", "damage", -9),  # explained: not missing
            (inside, "B", "adjustment", 3),  # found more than recorded: nothing missing
            (checkpoint - pd.Timedelta(days=WINDOW_DAYS), "A", "adjustment", -50),  # too old
        ]
    )
    window = window_at(store, checkpoint)
    assert window.missing.to_dict() == {"A": 3, "B": 0}
    assert window.sold.to_dict() == {"A": 2 * WINDOW_DAYS, "B": 2 * WINDOW_DAYS}
    # The half-year before the window: 50 missing over 2 products x 2 a day x 182 days.
    assert window.baseline_rate == pytest.approx(50 / (2 * 2 * 182))


def test_baseline_rate_has_a_floor():
    window = window_at(tiny_store([]), pd.Timestamp("2025-10-01"))
    assert window.baseline_rate == shrinkage.MIN_BASELINE_RATE


def test_scores_by_hand():
    window = Window(
        missing=pd.Series({"A": 6, "B": 0}), sold=pd.Series({"A": 99, "B": 40}), baseline_rate=0.01
    )
    assert units_score(window).to_dict() == {"A": 6.0, "B": 0.0}
    assert share_score(window).to_dict() == {"A": 0.06, "B": 0.0}
    poisson = poisson_score(window)
    assert poisson["A"] == pytest.approx(-math.log10(stats.poisson.sf(5, 0.99)))
    assert poisson["B"] == 0.0  # nothing missing is never unusual


# ── Evaluation ──────────────────────────────────────────────────────────────


def test_checkpoints_are_weekly_and_end_on_the_last_day():
    points = checkpoints(pd.Timestamp("2025-01-01"), pd.Timestamp("2025-01-29"))
    assert points == [pd.Timestamp(d) for d in ("2025-01-01", "2025-01-08", "2025-01-15",
                                                 "2025-01-22", "2025-01-29")]  # fmt: skip


def test_labels_leave_out_partly_affected_windows():
    point = pd.Timestamp("2025-06-30")
    full = point - pd.Timedelta(days=WINDOW_DAYS - 1)
    assert label_at(None, point) is False
    assert label_at(point + pd.Timedelta(days=1), point) is False  # not started yet
    assert label_at(full, point) is True  # the whole window is affected
    assert label_at(full + pd.Timedelta(days=1), point) is None  # only part of it


def test_delays_count_from_the_start_to_the_first_alert():
    store = tiny_store([])
    store = StoreRecords(
        store.daily,
        store.movements,
        pd.DataFrame({"sku": ["A", "B"], "onset": pd.to_datetime(["2025-02-03", "2025-02-03"]),
                      "loss_rate": [0.1, 0.1]}),
    )  # fmt: skip
    scores = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-02-01", "2025-02-08", "2025-02-15"] * 2),
            "sku": ["A"] * 3 + ["B"] * 3,
            "score": [9, 0, 9, 0, 0, 0],  # A: flagged before its start, then 12 days after
        }
    )
    assert detection_delays(store, scores, threshold=5) == [12.0, math.inf]


def test_thresholds_are_chosen_on_the_validation_stores_only(monkeypatch):
    validation, test = simulate_stores([11]), simulate_stores([12])
    seen = []

    def spy(rows):
        seen.append(set(rows["store"]))
        return 1e9 if rows.empty else float(np.quantile(rows["score"], 0.9))

    monkeypatch.setattr(shrinkage, "best_threshold", spy)
    original = shrinkage._all_scores
    stores_scored = []

    def tracking(records, detectors, store):
        stores_scored.append(records is validation[0])
        return original(records, detectors, store)

    monkeypatch.setattr(shrinkage, "_all_scores", tracking)
    result = evaluate(validation, test)
    assert len(result) == len(DETECTORS)
    assert len(seen) == len(DETECTORS)
    assert stores_scored == [True, False]  # validation scored first, then test, once each
    assert set(result.columns) >= {"precision", "recall", "recall_small", "median_days_to_detect"}
