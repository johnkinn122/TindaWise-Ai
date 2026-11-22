from datetime import date

import numpy as np
import pandas as pd
import pytest

from tindawise_ml.backtest import run_backtest, tiling_origins
from tindawise_ml.baselines import BASELINES
from tindawise_ml.data import validate_demand_frame
from tindawise_ml.synthetic import (
    DEFAULT_START,
    DEMO_PROFILES,
    ORACLE,
    ProductProfile,
    StockPolicy,
    expected_demand,
    generate_history,
    is_payday,
    oracle_forecasts,
)

# The SKUs seeded by services/api/scripts/seed.py, so synthetic history can later be attached to
# the demo store's products.
SEEDED_SKUS = {
    "NDL-001", "NDL-002", "NDL-003", "BEV-001", "BEV-002", "BEV-003", "DRY-001", "DRY-002",
    "CND-001", "CND-002", "CND-003", "CAN-001", "CAN-002", "SNK-001", "SNK-002", "HSE-001",
    "HSE-002",
}  # fmt: skip


@pytest.fixture(scope="module")
def history() -> pd.DataFrame:
    return generate_history()


def test_follows_the_daily_demand_contract(history):
    validate_demand_frame(history)
    assert history["date"].nunique() == 730
    assert len(history) == 730 * len(DEMO_PROFILES)


def test_covers_exactly_the_seeded_products(history):
    assert set(history["sku"]) == SEEDED_SKUS


def test_same_seed_same_history_different_seed_different_history(history):
    pd.testing.assert_frame_equal(history, generate_history())
    assert not history["units_sold"].equals(generate_history(seed=7)["units_sold"])


def test_a_products_history_does_not_depend_on_the_other_products():
    alone = generate_history(profiles=(DEMO_PROFILES[3],), days=200)
    together = generate_history(days=200)
    sku = DEMO_PROFILES[3].sku
    pd.testing.assert_frame_equal(
        alone.reset_index(drop=True),
        together[together["sku"] == sku].reset_index(drop=True),
    )


def test_sales_never_exceed_demand_and_shortfalls_are_flagged(history):
    assert (history["units_sold"] <= history["demand"]).all()
    short = history[history["units_sold"] < history["demand"]]
    assert not short.empty, "the stock simulation should cause some stockouts"
    # Selling less than wanted only happens when the shelf ran empty.
    assert short["stockout"].all()


def test_stock_columns_add_up_day_by_day(history):
    """closing = previous closing + received - sold, so the history can be replayed as a ledger."""
    for _, rows in history.groupby("sku"):
        closing = rows["closing_stock"].to_numpy()
        change = rows["received"].to_numpy() - rows["units_sold"].to_numpy()
        assert (closing[1:] == closing[:-1] + change[1:]).all()
        assert (closing >= 0).all()
        assert (rows["stockout"] == (rows["closing_stock"] == 0)).all()


def test_adding_stock_columns_did_not_change_the_history(history):
    # Fingerprint of the seed-42 history from before `received`/`closing_stock` existed.
    assert int(history["units_sold"].sum()) == 53_366
    assert int(history["demand"].sum()) == 55_522


def test_stockouts_are_occasional_not_constant(history):
    rate = history["stockout"].mean()
    assert 0.01 < rate < 0.10


def test_a_store_that_never_forgets_to_reorder_runs_out_less(history):
    careful = generate_history(policy=StockPolicy(forget_probability=0.0))
    assert careful["stockout"].mean() < history["stockout"].mean()


def test_paydays():
    assert is_payday(date(2025, 2, 15))
    assert is_payday(date(2025, 2, 16))
    assert is_payday(date(2025, 2, 28))  # last day of a short month
    assert is_payday(date(2025, 3, 1))
    assert not is_payday(date(2025, 2, 27))
    assert not is_payday(date(2025, 3, 30))  # March has 31 days


def test_expected_demand_applies_the_documented_effects():
    profile = ProductProfile("X", base_daily=10.0, dispersion=5.0, reorder_level=5, season={12: 2})
    days = pd.date_range("2025-12-01", "2025-12-31", freq="D")
    mean = pd.Series(expected_demand(profile, days), index=days)

    def trend(day_of_month: int) -> float:  # +8% a year from the first day of `days`
        return 1 + 0.08 * (day_of_month - 1) / 365

    # Saturday 6 Dec vs Tuesday 2 Dec: same month, neither is a payday.
    assert mean["2025-12-06"] / mean["2025-12-02"] == pytest.approx(
        (1.12 * trend(6)) / (0.92 * trend(2))
    )
    # Payday Monday 15 Dec vs Monday 8 Dec: +25% (the default lift).
    assert mean["2025-12-15"] / mean["2025-12-08"] == pytest.approx(1.25 * trend(15) / trend(8))
    # Tuesday x December store factor 1.25 x the product's own December factor 2.
    assert mean["2025-12-02"] == pytest.approx(10 * 0.92 * 1.25 * 2 * trend(2))


def test_oracle_forecasts_are_the_true_mean_with_the_trend_from_the_first_day():
    history = generate_history(days=120)
    origins = tiling_origins(history, test_days=14, horizon=7)
    forecasts = run_backtest(history, BASELINES, origins, horizon=7)
    oracle = oracle_forecasts(forecasts)
    assert (oracle["model"] == ORACLE).all()
    assert len(oracle) == len(forecasts) / len(BASELINES)  # one row per product-day

    profile = DEMO_PROFILES[0]
    days = pd.date_range(DEFAULT_START, periods=120, freq="D")
    truth = pd.Series(expected_demand(profile, days), index=days)
    rows = oracle[oracle["sku"] == profile.sku].set_index("date")["forecast"]
    np.testing.assert_allclose(rows.to_numpy(), truth.loc[rows.index].to_numpy())


def test_expected_demand_trend_counts_from_start():
    profile = DEMO_PROFILES[0]
    one_day = pd.DatetimeIndex([pd.Timestamp("2025-01-01")])
    a_year_in = expected_demand(profile, one_day, start=date(2024, 1, 1))
    first_day = expected_demand(profile, one_day)
    assert a_year_in[0] / first_day[0] == pytest.approx(1 + 0.08 * 366 / 365)


def test_rejects_an_empty_range():
    with pytest.raises(ValueError):
        generate_history(days=0)
