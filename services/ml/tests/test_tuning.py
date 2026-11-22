import pandas as pd

from tindawise_ml import tuning
from tindawise_ml.synthetic import generate_history


def test_tuning_scores_only_the_validation_period(monkeypatch):
    monkeypatch.setattr(
        tuning, "GRID", {"num_leaves": (7,), "min_data_in_leaf": (50, 200), "rounds": (20,)}
    )
    seen_origins: list[pd.Timestamp] = []
    real_backtest = tuning.run_backtest

    def spy(frame, forecasters, origins, *, horizon):
        seen_origins.extend(origins)
        return real_backtest(frame, forecasters, origins, horizon=horizon)

    monkeypatch.setattr(tuning, "run_backtest", spy)
    history = generate_history(days=140)
    results = tuning.tune(history, period_days=14, horizon=7)

    # Two grid points plus the reference baseline, best WAPE first.
    assert len(results) == 3
    assert results["model"].str.contains("moving_average_28").sum() == 1
    assert results["wape"].is_monotonic_increasing
    # Every forecast window ends before the test period (the last 14 days) begins.
    test_start = history["date"].max() - pd.Timedelta(days=14)
    assert max(seen_origins) + pd.Timedelta(days=7) <= test_start
