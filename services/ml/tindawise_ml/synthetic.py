"""Synthetic daily sales history for the demo store. SAMPLE DATA, NOT REAL SALES.

The demo store starts with no sales, and you can't build or test a forecaster on an empty table.
This module makes up a believable, repeatable history for the 17 seeded demo products (same SKUs
as services/api/scripts/seed.py) so the forecasting code has something to work on.

Every number here is an assumption chosen to look like a small Philippine mini-mart, not a
measurement. Results on this data show that the code works and how methods compare on *these*
patterns. They say nothing about accuracy on a real store.

How a day's demand is drawn (per product):

    expected = base rate x weekday x payday x month x product's own season x trend
    demand   ~ NegativeBinomial(mean=expected, dispersion=k)

Negative binomial instead of Poisson because real item sales are noisier than Poisson, and more
so for slow movers. Lower k means noisier. A small k gives the many zero days a slow item has.

Then a simple stock simulation turns demand into *sales*: the shelf holds limited stock, the owner
reorders when stock falls to the reorder level (sometimes forgetting), and deliveries take 1-3 days.
When the shelf runs out, sales are capped at what was there and the day is flagged `stockout`.
That censoring is the main thing a real store's data has that a plain demand curve doesn't.
"""

from __future__ import annotations

import calendar
import zlib
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

# Monday = 0. Weekends are busier for a neighbourhood store.
WEEKDAY_FACTOR = (0.94, 0.92, 0.95, 0.98, 1.06, 1.12, 1.03)

# Store-wide month effect: post-holiday dip in January, "ber months" build-up, Christmas peak.
MONTH_FACTOR = {
    1: 0.92,
    2: 0.95,
    3: 1.00,
    4: 1.00,
    5: 1.00,
    6: 0.97,
    7: 0.97,
    8: 0.97,
    9: 1.04,
    10: 1.04,
    11: 1.06,
    12: 1.25,
}

ANNUAL_TREND = 0.08  # +8% a year, straight line from the first day

DEFAULT_START = date(2024, 1, 1)
DEFAULT_DAYS = 730
DEFAULT_SEED = 42


@dataclass(frozen=True)
class ProductProfile:
    """Assumed demand pattern for one product."""

    sku: str
    base_daily: float  # average units a day before any effect
    dispersion: float  # negative binomial k: lower = noisier
    reorder_level: int  # matches the seeded product
    payday_lift: float = 0.25  # extra demand on paydays (0.25 = +25%)
    season: dict[int, float] = field(default_factory=dict)  # month -> extra factor


HOT_SEASON = {3: 1.2, 4: 1.3, 5: 1.25}  # March-May: cold drinks sell more

DEMO_PROFILES: tuple[ProductProfile, ...] = (
    ProductProfile("NDL-001", 9.0, 6.0, 24, payday_lift=0.10),
    ProductProfile("NDL-002", 7.0, 6.0, 24, payday_lift=0.10),
    ProductProfile("NDL-003", 2.5, 3.0, 12),
    ProductProfile("BEV-001", 4.0, 4.0, 12, payday_lift=0.35, season={**HOT_SEASON, 12: 1.3}),
    ProductProfile("BEV-002", 2.5, 3.0, 12, payday_lift=0.30, season=HOT_SEASON),
    ProductProfile("BEV-003", 3.0, 5.0, 10),
    ProductProfile("DRY-001", 8.0, 6.0, 24, payday_lift=0.10),
    ProductProfile("DRY-002", 2.5, 3.0, 12, season={12: 1.6}),  # Christmas fruit salad
    ProductProfile("CND-001", 1.2, 2.5, 6),
    ProductProfile("CND-002", 1.0, 2.5, 6),
    ProductProfile("CND-003", 1.0, 2.0, 6, season={12: 1.3}),
    ProductProfile("CAN-001", 6.0, 5.0, 24, payday_lift=0.05),
    ProductProfile("CAN-002", 2.0, 3.0, 12, payday_lift=0.35),
    ProductProfile("SNK-001", 4.0, 4.0, 20, payday_lift=0.30),
    ProductProfile("SNK-002", 0.8, 1.5, 6),
    ProductProfile("HSE-001", 1.5, 2.5, 6),
    ProductProfile("HSE-002", 10.0, 6.0, 30, payday_lift=0.15),
)


@dataclass(frozen=True)
class StockPolicy:
    """How the simulated owner restocks."""

    order_up_to_multiple: float = 3.0  # order enough to reach 3 x reorder level
    min_lead_days: int = 1
    max_lead_days: int = 3
    forget_probability: float = 0.25  # chance, each day stock is low, of not reordering yet


def is_payday(day: date) -> bool:
    """Semi-monthly paydays (15th and last day of the month) and the day after each."""
    last = calendar.monthrange(day.year, day.month)[1]
    return day.day in (1, 15, 16, last)


def expected_demand(profile: ProductProfile, days: pd.DatetimeIndex) -> np.ndarray:
    """Mean demand for each day before noise."""
    start = days[0]
    weekday = np.array([WEEKDAY_FACTOR[d.weekday()] for d in days])
    payday = np.array([1.0 + profile.payday_lift if is_payday(d.date()) else 1.0 for d in days])
    month = np.array([MONTH_FACTOR[d.month] * profile.season.get(d.month, 1.0) for d in days])
    trend = 1.0 + ANNUAL_TREND * ((days - start).days.to_numpy() / 365.0)
    return profile.base_daily * weekday * payday * month * trend


def _rng_for(seed: int, sku: str) -> np.random.Generator:
    # One stream per SKU, keyed by the SKU's text, so adding or reordering products doesn't change
    # the history of the others. (Python's hash() is randomised per process, so crc32 instead.)
    return np.random.default_rng(
        np.random.SeedSequence(seed, spawn_key=(zlib.crc32(sku.encode()),))
    )


def _simulate_product(
    profile: ProductProfile, days: pd.DatetimeIndex, policy: StockPolicy, seed: int
) -> pd.DataFrame:
    rng = _rng_for(seed, profile.sku)
    mean = expected_demand(profile, days)
    k = profile.dispersion
    # Negative binomial as a gamma-Poisson mixture: the gamma has mean `mean`, variance mean²/k.
    demand = rng.poisson(rng.gamma(shape=k, scale=mean / k))

    order_up_to = max(round(policy.order_up_to_multiple * profile.reorder_level), 6)
    stock = order_up_to
    arrivals: dict[int, int] = {}  # day index -> units arriving that morning
    sold = np.zeros(len(days), dtype=np.int64)
    stockout = np.zeros(len(days), dtype=bool)

    for i in range(len(days)):
        stock += arrivals.pop(i, 0)
        sold[i] = min(int(demand[i]), stock)
        stock -= sold[i]
        # Same rule real data can use: the product reached zero on the shelf that day.
        stockout[i] = stock == 0
        low = stock <= profile.reorder_level and not arrivals  # nothing already on order
        if low and rng.random() >= policy.forget_probability:
            lead = int(rng.integers(policy.min_lead_days, policy.max_lead_days + 1))
            arrivals[i + lead] = order_up_to - stock

    return pd.DataFrame(
        {
            "date": days,
            "sku": profile.sku,
            "units_sold": sold,
            "stockout": stockout,
            "demand": demand.astype(np.int64),
        }
    )


def generate_history(
    *,
    start: date = DEFAULT_START,
    days: int = DEFAULT_DAYS,
    seed: int = DEFAULT_SEED,
    profiles: tuple[ProductProfile, ...] = DEMO_PROFILES,
    policy: StockPolicy | None = None,
) -> pd.DataFrame:
    """A zero-filled daily table (see tindawise_ml.data) plus the true `demand` column.

    The same arguments always give the same table.
    """
    if days < 1:
        raise ValueError("days must be at least 1")
    calendar_days = pd.date_range(pd.Timestamp(start), periods=days, freq="D")
    policy = policy or StockPolicy()
    frames = [_simulate_product(p, calendar_days, policy, seed) for p in profiles]
    return pd.concat(frames, ignore_index=True).sort_values(["date", "sku"], ignore_index=True)
