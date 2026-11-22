"""Replay a stretch of days with different reorder policies and compare what a store would see.

Forecast accuracy alone doesn't say whether forecasting helps a store. What matters is the result
of the orders it leads to: how much demand was served, how often the shelf was empty, how much
stock sat there, and how many orders were placed. This module simulates that, on synthetic data,
because only synthetic data knows the true demand (including what customers would have bought
from an empty shelf).

Every policy faces the same customers (the synthetic `demand`) and the same delivery delays
(drawn once per day and product, shared by all policies), so differences come from the policy.
Policies see only what a store would see: units sold and stockout flags up to today, including
the sales their own earlier decisions produced.

Daily cycle, per product: deliveries arrive in the morning -> customers buy what's on the
shelf -> after closing, the policy may place an order, which arrives 1-3 days later. Like the
store simulated in synthetic.py, nobody reorders a product that already has an order on the way.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

import numpy as np
import pandas as pd

from tindawise_ml.baselines import Forecaster
from tindawise_ml.data import History, to_wide, validate_demand_frame

REORDER_LOOKBACK_DAYS = 14  # same as the app's rule (services/api overview.py)


@dataclass(frozen=True)
class PolicyContext:
    """What a policy may look at after the store closes on `day`."""

    day: int  # 0 = first simulated day
    stock: np.ndarray  # units on the shelf now, per product
    history: History  # sold and stockout flags up to and including today
    reorder_level: np.ndarray


class Policy(Protocol):
    name: str

    def order(self, ctx: PolicyContext) -> np.ndarray:
        """Units to order per product (only applied where nothing is already on order)."""
        ...


class CurrentRule:
    """The app's rule today (services/api `suggested_quantity`): when stock is at or below the
    reorder level, order up to max(2 x reorder level, units sold in the last 14 days)."""

    name = "current rule (app)"

    def order(self, ctx: PolicyContext) -> np.ndarray:
        sold_recently = ctx.history.sold.iloc[-REORDER_LOOKBACK_DAYS:].to_numpy().sum(axis=0)
        target = np.maximum(2 * ctx.reorder_level, sold_recently)
        low = ctx.stock <= ctx.reorder_level
        return np.where(low, np.maximum(target - ctx.stock, 0), 0)


class ForecastPolicy:
    """Order from a forecast.

    Reorder when stock won't cover forecast demand over the longest lead time plus a safety
    buffer; then order enough to also cover `cover_days` more days. The buffer is
    `safety` x (day-to-day spread of recent in-stock sales) x sqrt(lead time): with safety = 1
    the shelf holds about one standard deviation of lead-time demand more than forecast.

    The forecast is refreshed every `refresh_days` (a weekly job), not every day.
    """

    def __init__(
        self,
        name: str,
        forecaster: Forecaster,
        *,
        cover_days: int = 7,
        safety: float = 1.0,
        lead_days: int = 3,
        refresh_days: int = 7,
    ) -> None:
        self.name = name
        self.forecaster = forecaster
        self.cover_days = cover_days
        self.safety = safety
        self.lead_days = lead_days
        self.refresh_days = refresh_days
        self._forecast: np.ndarray | None = None
        self._made_on = 0

    @property
    def horizon(self) -> int:
        # The last day used is (refresh_days - 1) days after the forecast was made, looking
        # lead + cover days ahead from the day after.
        return self.refresh_days - 1 + self.lead_days + self.cover_days

    def order(self, ctx: PolicyContext) -> np.ndarray:
        if self._forecast is None or ctx.day - self._made_on >= self.refresh_days:
            self._forecast = self.forecaster(ctx.history, self.horizon).to_numpy()
            self._made_on = ctx.day
        # Row 0 of the forecast is the day after it was made; tomorrow is row (day - made_on).
        ahead = self._forecast[ctx.day - self._made_on :][: self.lead_days + self.cover_days]
        lead_demand = ahead[: self.lead_days].sum(axis=0)
        cover_demand = ahead.sum(axis=0)

        recent = ctx.history.sold.iloc[-28:].to_numpy(dtype=float)
        in_stock = ~ctx.history.stockout.iloc[-28:].to_numpy()
        spread = np.array(
            [recent[in_stock[:, p], p].std() if in_stock[:, p].sum() > 1 else 0.0
             for p in range(recent.shape[1])]
        )  # fmt: skip
        buffer = self.safety * spread * math.sqrt(self.lead_days)

        reorder = ctx.stock <= lead_demand + buffer
        wanted = np.ceil(cover_demand + buffer - ctx.stock)
        return np.where(reorder, np.maximum(wanted, 0), 0).astype(np.int64)


@dataclass(frozen=True)
class Outcome:
    """Daily results of one policy (days x products)."""

    policy: str
    demand: np.ndarray
    sold: np.ndarray
    stock: np.ndarray  # on the shelf after closing
    stockout: np.ndarray
    orders: np.ndarray  # units ordered that evening (0 = no order)
    lead_days: np.ndarray  # delivery delay an order placed that evening would get (shared draws)

    def summary(self) -> dict[str, float | int | str]:
        demand = self.demand.sum()
        return {
            "policy": self.policy,
            "fill_rate": float(self.sold.sum() / demand) if demand else float("nan"),
            "lost_units": int(demand - self.sold.sum()),
            "stockout_days": float(self.stockout.mean()),
            # Average units on the shelf / average units wanted per day, pooled over products.
            "days_of_stock": float(self.stock.mean(axis=0).sum() / self.demand.mean(axis=0).sum()),
            "orders": int((self.orders > 0).sum()),
        }


def simulate(
    frame: pd.DataFrame,
    policy: Policy,
    *,
    start: pd.Timestamp,
    reorder_level: dict[str, int],
    min_lead_days: int = 1,
    max_lead_days: int = 3,
    seed: int = 0,
) -> Outcome:
    """Replay `frame` (synthetic: needs `demand` and `closing_stock`) from `start` to its last
    day under `policy`. Days before `start` are the history the policy starts with; the shelf
    starts with that day's opening stock and nothing on order."""
    validate_demand_frame(frame)
    for column in ("demand", "closing_stock"):
        if column not in frame.columns:
            raise ValueError(f"simulation needs the synthetic `{column}` column")
    sold_all = to_wide(frame, "units_sold")
    flags_all = to_wide(frame, "stockout")
    demand_all = to_wide(frame, "demand")
    if start not in sold_all.index or start == sold_all.index[0]:
        raise ValueError("start must be a day in the data after its first day")
    first = sold_all.index.get_loc(start)
    products = list(sold_all.columns)
    levels = np.array([reorder_level[sku] for sku in products])

    # Working copies: days before `start` are history; the rest get the simulated results.
    sold_hist = sold_all.to_numpy().copy()
    flags_hist = flags_all.to_numpy().copy()
    demand = demand_all.to_numpy()[first:]
    days, n = demand.shape

    # Delivery delays, drawn once so every policy gets the same ones.
    rng = np.random.default_rng(seed)
    leads = rng.integers(min_lead_days, max_lead_days + 1, size=(days, n))

    stock = to_wide(frame, "closing_stock").to_numpy()[first - 1].copy()
    arriving = np.zeros((days + max_lead_days + 1, n), dtype=np.int64)
    out_sold = np.zeros((days, n), dtype=np.int64)
    out_stock = np.zeros((days, n), dtype=np.int64)
    out_flags = np.zeros((days, n), dtype=bool)
    out_orders = np.zeros((days, n), dtype=np.int64)

    for d in range(days):
        stock += arriving[d]
        sold = np.minimum(demand[d], stock)
        stock -= sold
        out_sold[d], out_stock[d], out_flags[d] = sold, stock, stock == 0
        sold_hist[first + d], flags_hist[first + d] = sold, stock == 0

        history = History(
            sold=pd.DataFrame(sold_hist[: first + d + 1], index=sold_all.index[: first + d + 1],
                              columns=products),
            stockout=pd.DataFrame(flags_hist[: first + d + 1],
                                  index=sold_all.index[: first + d + 1], columns=products),
        )  # fmt: skip
        on_order = arriving[d + 1 :].sum(axis=0) > 0
        wanted = policy.order(PolicyContext(d, stock.copy(), history, levels))
        placed = np.where(on_order, 0, np.maximum(wanted, 0)).astype(np.int64)
        for p in np.flatnonzero(placed):
            arriving[d + leads[d, p], p] += placed[p]
        out_orders[d] = placed

    return Outcome(policy.name, demand, out_sold, out_stock, out_flags, out_orders, leads)
