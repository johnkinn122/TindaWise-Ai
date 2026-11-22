import itertools
import math

import numpy as np
import pandas as pd
import pytest

from tindawise_ml.baselines import moving_average
from tindawise_ml.data import History
from tindawise_ml.inventory import (
    CurrentRule,
    ForecastPolicy,
    PolicyContext,
    simulate,
)
from tindawise_ml.synthetic import DEMO_PROFILES, generate_history

LEVELS = {p.sku: p.reorder_level for p in DEMO_PROFILES}


@pytest.fixture(scope="module")
def history() -> pd.DataFrame:
    return generate_history(days=200)


def start_of_last(frame: pd.DataFrame, days: int) -> pd.Timestamp:
    return frame["date"].max() - pd.Timedelta(days=days - 1)


def context(stock, sold_rows, *, day=0, level=None, stockout_rows=None) -> PolicyContext:
    sold = pd.DataFrame(sold_rows, index=pd.date_range("2025-01-01", periods=len(sold_rows)))
    flags = (
        pd.DataFrame(stockout_rows, index=sold.index, columns=sold.columns)
        if stockout_rows is not None
        else pd.DataFrame(False, index=sold.index, columns=sold.columns)
    )
    return PolicyContext(
        day=day,
        stock=np.array(stock),
        history=History(sold=sold, stockout=flags),
        reorder_level=np.array(level if level is not None else [5] * len(stock)),
    )


class NeverOrder:
    name = "never order"

    def order(self, ctx):
        return np.zeros_like(ctx.stock)


class Recorder:
    """Orders 5 of everything every day and records what it was shown."""

    name = "recorder"

    def __init__(self):
        self.seen = []

    def order(self, ctx):
        self.seen.append((ctx.day, ctx.history.sold.index[-1], ctx.history.sold.iloc[-1].copy()))
        return np.full_like(ctx.stock, 5)


# ── The app's rule ──────────────────────────────────────────────────────────


def test_current_rule_matches_the_apps_formula():
    # 20 days of sales: 3 a day for product 0, 0 a day for product 1. Last 14 days: 42 and 0.
    ctx = context([4, 2], [[3, 0]] * 20, level=[5, 6])
    # Product 0: low (4 <= 5); target max(10, 42) = 42; order 38.
    # Product 1: low (2 <= 6); target max(12, 0) = 12; order 10.
    assert CurrentRule().order(ctx).tolist() == [38, 10]


def test_current_rule_waits_until_stock_is_at_the_reorder_level():
    ctx = context([6, 5], [[3, 3]] * 20, level=[5, 5])
    assert CurrentRule().order(ctx).tolist() == [0, 37]


# ── Forecast policy ─────────────────────────────────────────────────────────


def constant(rate: float):
    calls = []

    def forecaster(history: History, horizon: int) -> pd.DataFrame:
        calls.append(history.sold.index[-1])
        index = pd.date_range(history.sold.index[-1] + pd.Timedelta(days=1), periods=horizon)
        return pd.DataFrame(rate, index=index, columns=history.sold.columns)

    forecaster.calls = calls
    return forecaster


def test_forecast_policy_reorder_point_and_quantity_without_buffer():
    policy = ForecastPolicy("p", constant(2.0), cover_days=7, safety=0, lead_days=3)
    # Lead-time demand 6, cover demand 2 x 10 = 20.
    ctx = context([6, 7], [[2, 2]] * 30)
    assert policy.order(ctx).tolist() == [14, 0]  # 6 <= 6: order 20 - 6; 7 > 6: wait


def test_forecast_policy_buffer_uses_the_spread_of_in_stock_days():
    policy = ForecastPolicy("p", constant(2.0), cover_days=7, safety=1, lead_days=3)
    rows = [[0], [4]] * 14  # 28 days alternating 0 and 4: std 2
    stockouts = [[False]] * 28
    stockouts[-1] = [True]  # a capped day is left out of the spread: 13 zeros, 14 fours
    ctx = context([9], rows, stockout_rows=stockouts)
    buffer = np.array([0, 4] * 13 + [0]).std() * math.sqrt(3)
    assert buffer == pytest.approx(3.461, abs=1e-3)
    # Reorder point 6 + 3.461 >= 9 on the shelf, so it orders ceil(20 + 3.461 - 9) = 15.
    assert policy.order(ctx).tolist() == [15]
    # Without the stockout day left out, the spread (and the order) would differ.
    assert np.array([0, 4] * 14).std() != pytest.approx(buffer / math.sqrt(3))


def test_forecast_is_refreshed_every_refresh_days(history):
    forecaster = constant(1.0)
    policy = ForecastPolicy("p", forecaster, refresh_days=7)
    simulate(history, policy, start=start_of_last(history, 21), reorder_level=LEVELS)
    assert len(forecaster.calls) == 3  # days 0, 7, 14
    gaps = [(later - earlier).days for earlier, later in itertools.pairwise(forecaster.calls)]
    assert gaps == [7, 7]


def test_forecast_horizon_covers_the_last_day_before_a_refresh():
    policy = ForecastPolicy("p", constant(1.0), cover_days=7, lead_days=3, refresh_days=7)
    assert policy.horizon == 6 + 3 + 7


# ── Simulation ──────────────────────────────────────────────────────────────


def test_stock_is_conserved_and_sales_never_exceed_demand_or_shelf(history):
    outcome = simulate(
        history, CurrentRule(), start=start_of_last(history, 60), reorder_level=LEVELS
    )
    assert (outcome.sold <= outcome.demand).all()
    assert (outcome.stock >= 0).all()
    # Selling less than wanted only happens when the shelf ran out.
    short = outcome.sold < outcome.demand
    assert (outcome.stock[short] == 0).all()
    assert (outcome.stockout == (outcome.stock == 0)).all()


def test_every_order_arrives_exactly_its_lead_time_later(history):
    """Closing stock = yesterday's closing + deliveries due today - today's sales."""
    start = start_of_last(history, 40)
    outcome = simulate(history, CurrentRule(), start=start, reorder_level=LEVELS)
    days, products = outcome.stock.shape
    due = np.zeros((days, products), dtype=np.int64)
    for d, p in zip(*np.nonzero(outcome.orders), strict=True):
        if d + outcome.lead_days[d, p] < days:
            due[d + outcome.lead_days[d, p], p] += outcome.orders[d, p]
    wide = history.pivot(index="date", columns="sku", values="closing_stock")
    previous = np.vstack([wide.loc[start - pd.Timedelta(days=1)].to_numpy(), outcome.stock[:-1]])
    assert (outcome.stock == previous + due - outcome.sold).all()
    assert due.sum() > 0


def test_no_new_order_while_one_is_on_the_way(history):
    recorder = Recorder()  # wants to order every single day
    outcome = simulate(history, recorder, start=start_of_last(history, 30), reorder_level=LEVELS)
    placed = outcome.orders > 0
    assert placed[0].all()  # nothing on order at the start, so everything is ordered on day 0
    for p in range(placed.shape[1]):
        days = np.flatnonzero(placed[:, p])
        # A policy that always wants more reorders the evening its delivery arrives: never before.
        for earlier, later in itertools.pairwise(days):
            assert later - earlier == outcome.lead_days[earlier, p]


def test_policies_see_today_and_their_own_sales_but_not_tomorrow(history):
    recorder = Recorder()
    start = start_of_last(history, 10)
    outcome = simulate(history, recorder, start=start, reorder_level=LEVELS)
    for day, last_seen, sold_row in recorder.seen:
        assert last_seen == start + pd.Timedelta(days=day)
        # The history holds the simulated sales, not the original ones.
        assert sold_row.to_numpy().tolist() == outcome.sold[day].tolist()


def test_same_inputs_same_outcome_and_shared_delivery_delays(history):
    start = start_of_last(history, 40)
    a = simulate(history, CurrentRule(), start=start, reorder_level=LEVELS, seed=3)
    b = simulate(history, CurrentRule(), start=start, reorder_level=LEVELS, seed=3)
    assert (a.sold == b.sold).all() and (a.orders == b.orders).all()
    c = simulate(history, CurrentRule(), start=start, reorder_level=LEVELS, seed=4)
    assert not (a.stock == c.stock).all()  # other delays, other stock path


def test_never_ordering_runs_the_shelves_down(history):
    outcome = simulate(
        history, NeverOrder(), start=start_of_last(history, 60), reorder_level=LEVELS
    )
    assert (np.diff(outcome.stock, axis=0) <= 0).all()
    assert outcome.summary()["fill_rate"] < 0.9
    assert outcome.summary()["orders"] == 0


def test_summary_figures(history):
    outcome = simulate(
        history, CurrentRule(), start=start_of_last(history, 30), reorder_level=LEVELS
    )
    s = outcome.summary()
    assert s["fill_rate"] == pytest.approx(outcome.sold.sum() / outcome.demand.sum())
    assert s["lost_units"] == outcome.demand.sum() - outcome.sold.sum()
    assert s["days_of_stock"] == pytest.approx(
        outcome.stock.mean(axis=0).sum() / outcome.demand.mean(axis=0).sum()
    )
    assert s["orders"] == (outcome.orders > 0).sum()


def test_a_forecast_policy_runs_end_to_end(history):
    policy = ForecastPolicy("ma", moving_average, cover_days=10, safety=1)
    s = simulate(history, policy, start=start_of_last(history, 28), reorder_level=LEVELS).summary()
    assert 0.5 < s["fill_rate"] <= 1
    assert s["orders"] > 0


def test_real_data_without_true_demand_is_refused(history):
    exported = history[["date", "sku", "units_sold", "stockout"]]
    with pytest.raises(ValueError, match="demand"):
        simulate(exported, CurrentRule(), start=start_of_last(history, 10), reorder_level=LEVELS)


def test_start_must_leave_some_history(history):
    with pytest.raises(ValueError, match="after its first day"):
        simulate(history, CurrentRule(), start=history["date"].min(), reorder_level=LEVELS)
