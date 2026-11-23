"""Shrinkage: stock that goes missing without a record. SYNTHETIC DATA ONLY.

Why a store cares: units that leave the shelf without a sale or a recorded loss (shoplifting,
staff taking items, damage nobody wrote down, deliveries short of what was signed for) are lost
profit, and they make the recorded stock wrong. A shelf the system thinks holds 5 can be empty
("phantom stock"), so it isn't reordered and customers leave without buying.

The only place shrinkage shows up in Tindawise is a **stock count**: the owner counts the shelf
and records the difference as an `adjustment`. Recorded damage is a separate reason and is
explained loss, not shrinkage. So the question is: which products' count corrections show more
missing stock than normal?

The demo store has no counts, so `simulate_store` makes up a store's records, keeping two stock
levels per product:

- **true stock**, what's on the shelf, and **recorded stock**, what Tindawise thinks.
- Every product loses a little stock unrecorded (`base_loss_rate` of expected sales).
  A planted share of products get a "problem" from a random day: a much higher rate. These are
  the labels the detectors must find.
- Some loss is recorded as damage (explained; both levels drop).
- A sale needs the unit on the shelf *and* in the records (the app refuses a sale it thinks
  there's no stock for), so sales stop when either runs out.
- The owner reorders by recorded stock, as they would by looking at the app.
- Every `count_every_days` (staggered per product) the shelf is counted, sometimes off by one,
  and the difference is recorded as an adjustment. Recorded stock becomes the count.

Demand is drawn as in `synthetic.py`, but from separate random streams, so `generate_history`
and every earlier experiment are unchanged. All rates are assumptions, not measurements.

Detectors score each product every week from the adjustments and sales in the last 56 days, as
the app could. Thresholds are chosen on a validation period and scored once on the test period.
"""

from __future__ import annotations

import zlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd
from scipy import stats

from tindawise_ml.anomalies import Outcome, average_precision, best_threshold
from tindawise_ml.synthetic import (
    DEFAULT_DAYS,
    DEFAULT_SEED,
    DEFAULT_START,
    DEMO_PROFILES,
    ProductProfile,
    StockPolicy,
    expected_demand,
)

WINDOW_DAYS = 56  # 8 weeks: four counts at a 14-day rhythm
CHECK_EVERY_DAYS = 7  # the detectors run weekly
BASELINE_DAYS = 182  # the store's usual loss rate is learnt from the half-year before the window
MIN_BASELINE_RATE = 0.005  # a store with no recorded losses yet still expects a little


@dataclass(frozen=True)
class ShrinkageConfig:
    """Assumed loss and counting behaviour of the simulated store."""

    count_every_days: int = 14
    # Unrecorded loss every product has, as a share of expected sales, drawn per product: some
    # items (small, easy to pocket, fragile) normally lose more than others.
    base_loss_rate: tuple[float, float] = (0.005, 0.02)
    problem_share: float = 0.25  # share of products that get a shrinkage problem
    problem_loss_rate: tuple[float, float] = (0.03, 0.15)  # extra rate, drawn per problem
    damage_rate: float = 0.005  # recorded (explained) damage, as a share of expected sales
    miscount_probability: float = 0.10  # a count is off by one unit


@dataclass(frozen=True)
class StoreRecords:
    """What the simulation produced.

    - `daily`: date, sku, units_sold, stockout (recorded stock at 0, the app's rule),
      true_stock and recorded_stock at the end of the day (true_stock is synthetic only).
    - `movements`: date, sku, reason ("adjustment" or "damage"), change. What the ledger shows
      besides sales and deliveries.
    - `labels`: sku, onset (first day of the problem), loss_rate (the extra rate).
    """

    daily: pd.DataFrame
    movements: pd.DataFrame
    labels: pd.DataFrame


def _rng(seed: int, *parts: str) -> np.random.Generator:
    key = tuple(zlib.crc32(p.encode()) for p in ("shrinkage", *parts))
    return np.random.default_rng(np.random.SeedSequence(seed, spawn_key=key))


def _simulate_product(
    profile: ProductProfile,
    days: pd.DatetimeIndex,
    policy: StockPolicy,
    config: ShrinkageConfig,
    seed: int,
    problem: tuple[int, float] | None,  # (onset day index, extra loss rate)
) -> tuple[pd.DataFrame, list[dict]]:
    rng = _rng(seed, profile.sku)
    mean = expected_demand(profile, days)
    k = profile.dispersion
    demand = rng.poisson(rng.gamma(shape=k, scale=mean / k))
    count_offset = int(rng.integers(config.count_every_days))
    base_rate = float(rng.uniform(*config.base_loss_rate))

    order_up_to = max(round(policy.order_up_to_multiple * profile.reorder_level), 6)
    true_stock = recorded = order_up_to
    arrivals: dict[int, int] = {}
    n = len(days)
    sold = np.zeros(n, dtype=np.int64)
    stockout = np.zeros(n, dtype=bool)
    true_close = np.zeros(n, dtype=np.int64)
    recorded_close = np.zeros(n, dtype=np.int64)
    movements: list[dict] = []

    for i in range(n):
        received = arrivals.pop(i, 0)
        true_stock += received
        recorded += received

        sold[i] = min(int(demand[i]), true_stock, recorded)
        true_stock -= sold[i]
        recorded -= sold[i]

        rate = base_rate
        if problem is not None and i >= problem[0]:
            rate += problem[1]
        true_stock -= min(int(rng.poisson(rate * mean[i])), true_stock)  # nobody notices

        damaged = min(int(rng.poisson(config.damage_rate * mean[i])), true_stock, recorded)
        if damaged:
            true_stock -= damaged
            recorded -= damaged
            movements.append(
                {"date": days[i], "sku": profile.sku, "reason": "damage", "change": -damaged}
            )

        if i % config.count_every_days == count_offset:
            counted = true_stock
            if rng.random() < config.miscount_probability:
                counted = max(true_stock + int(rng.choice([-1, 1])), 0)
            if counted != recorded:
                movements.append(
                    {
                        "date": days[i],
                        "sku": profile.sku,
                        "reason": "adjustment",
                        "change": counted - recorded,
                    }
                )
                recorded = counted

        true_close[i], recorded_close[i] = true_stock, recorded
        stockout[i] = recorded == 0
        low = recorded <= profile.reorder_level and not arrivals
        if low and rng.random() >= policy.forget_probability:
            lead = int(rng.integers(policy.min_lead_days, policy.max_lead_days + 1))
            arrivals[i + lead] = order_up_to - recorded

    daily = pd.DataFrame(
        {
            "date": days,
            "sku": profile.sku,
            "units_sold": sold,
            "stockout": stockout,
            "true_stock": true_close,
            "recorded_stock": recorded_close,
        }
    )
    return daily, movements


def simulate_store(
    *,
    start: date = DEFAULT_START,
    days: int = DEFAULT_DAYS,
    seed: int = DEFAULT_SEED,
    problems_from: date | None = None,
    problems_until: date | None = None,
    config: ShrinkageConfig | None = None,
    profiles: tuple[ProductProfile, ...] = DEMO_PROFILES,
    policy: StockPolicy | None = None,
) -> StoreRecords:
    """A store's records with planted shrinkage problems. Problems start on a random day from
    `problems_from` to `problems_until` (default: the whole history). Same arguments, same
    records."""
    if days < 1:
        raise ValueError("days must be at least 1")
    config = config or ShrinkageConfig()
    policy = policy or StockPolicy()
    calendar_days = pd.date_range(pd.Timestamp(start), periods=days, freq="D")
    first = calendar_days.get_loc(pd.Timestamp(problems_from)) if problems_from else 0
    last = calendar_days.get_loc(pd.Timestamp(problems_until)) if problems_until else days - 1

    plan = _rng(seed, "plan")
    count = round(config.problem_share * len(profiles))
    chosen = set(plan.choice(len(profiles), size=count, replace=False).tolist()) if count else set()
    problems: dict[str, tuple[int, float]] = {}
    for index in sorted(chosen):
        low, high = config.problem_loss_rate
        problems[profiles[index].sku] = (
            int(plan.integers(first, last + 1)),
            float(plan.uniform(low, high)),
        )

    frames, movements = [], []
    for profile in profiles:
        daily, moved = _simulate_product(
            profile, calendar_days, policy, config, seed, problems.get(profile.sku)
        )
        frames.append(daily)
        movements.extend(moved)

    labels = pd.DataFrame(
        [
            {"sku": sku, "onset": calendar_days[onset], "loss_rate": rate}
            for sku, (onset, rate) in sorted(problems.items())
        ],
        columns=["sku", "onset", "loss_rate"],
    )
    return StoreRecords(
        daily=pd.concat(frames, ignore_index=True).sort_values(["date", "sku"], ignore_index=True),
        movements=pd.DataFrame(movements, columns=["date", "sku", "reason", "change"]),
        labels=labels,
    )


# ── Detectors ───────────────────────────────────────────────────────────────
#
# Each scores every product at a checkpoint from what the app would know: sales and count
# adjustments in the window (checkpoint - 56 days, checkpoint]. Missing units = the net of the
# adjustments, when it's a loss (a count that finds extra stock offsets one that found less).
# Damage never counts: it's explained.


@dataclass(frozen=True)
class Window:
    missing: pd.Series  # units, by sku
    sold: pd.Series  # units sold, by sku
    baseline_rate: float  # the store's missing units per unit sold before the window


def window_at(records: StoreRecords, checkpoint: pd.Timestamp) -> Window:
    start = checkpoint - pd.Timedelta(days=WINDOW_DAYS - 1)
    before = start - pd.Timedelta(days=BASELINE_DAYS)
    skus = sorted(records.daily["sku"].unique())

    adjustments = records.movements[records.movements["reason"] == "adjustment"]

    def missing_between(low: pd.Timestamp, high: pd.Timestamp) -> pd.Series:
        rows = adjustments[(adjustments["date"] >= low) & (adjustments["date"] <= high)]
        net = rows.groupby("sku")["change"].sum().reindex(skus, fill_value=0)
        return (-net).clip(lower=0)

    def sold_between(low: pd.Timestamp, high: pd.Timestamp) -> pd.Series:
        daily = records.daily
        rows = daily[(daily["date"] >= low) & (daily["date"] <= high)]
        return rows.groupby("sku")["units_sold"].sum().reindex(skus, fill_value=0)

    day_before = start - pd.Timedelta(days=1)
    past_sold = sold_between(before, day_before).sum()
    past_missing = missing_between(before, day_before).sum()
    rate = past_missing / past_sold if past_sold else 0.0
    return Window(
        missing=missing_between(start, checkpoint),
        sold=sold_between(start, checkpoint),
        baseline_rate=max(float(rate), MIN_BASELINE_RATE),
    )


def units_score(window: Window) -> pd.Series:
    """Baseline: units missing in the window."""
    return window.missing.astype(float)


def share_score(window: Window) -> pd.Series:
    """Missing units per unit sold (the retail "shrink %"), +1 so a product that sold nothing
    doesn't divide by zero."""
    return window.missing / (window.sold + 1)


def poisson_score(window: Window) -> pd.Series:
    """-log10 P(this many or more missing) if the product lost stock at the store's usual rate:
    Poisson with mean = usual rate x units sold. 2 means "about a 1-in-100 window"."""
    expected = np.maximum(window.baseline_rate * window.sold.to_numpy(dtype=float), 0.1)
    missing = window.missing.to_numpy(dtype=float)
    tail = stats.poisson.sf(missing - 1, expected)
    score = -np.log10(np.clip(tail, 1e-300, 1.0))
    return pd.Series(np.where(missing > 0, score, 0.0), index=window.missing.index)


Detector = Callable[[Window], pd.Series]

DETECTORS: dict[str, Detector] = {
    "missing units (baseline)": units_score,
    "share of sales": share_score,
    "poisson vs store rate": poisson_score,
}


# ── Evaluation ──────────────────────────────────────────────────────────────


def checkpoints(first: pd.Timestamp, last: pd.Timestamp) -> list[pd.Timestamp]:
    """Weekly checkpoints ending on `last`, none before `first`."""
    points, day = [], last
    while day >= first:
        points.append(day)
        day -= pd.Timedelta(days=CHECK_EVERY_DAYS)
    return sorted(points)


def label_at(onset: pd.Timestamp | None, checkpoint: pd.Timestamp) -> bool | None:
    """True: the problem ran through the whole window. False: no problem by the checkpoint.
    None: it started inside the window, so only part of the window shows it; not scored."""
    if onset is None or onset > checkpoint:
        return False
    if onset <= checkpoint - pd.Timedelta(days=WINDOW_DAYS - 1):
        return True
    return None


FIRST_CHECK_DAY = 300  # leaves room for the baseline half-year and a full window
PROBLEMS_FROM_DAY = 200  # problems start from here to 2 weeks before the end
SMALL_PROBLEM = 0.06  # problems adding less than 6% of sales are reported separately


def simulate_stores(seeds: list[int], config: ShrinkageConfig | None = None) -> list[StoreRecords]:
    """One simulated two-year store per seed, problems starting from day 200."""
    start = pd.Timestamp(DEFAULT_START)
    return [
        simulate_store(
            seed=seed,
            problems_from=(start + pd.Timedelta(days=PROBLEMS_FROM_DAY)).date(),
            problems_until=(start + pd.Timedelta(days=DEFAULT_DAYS - 15)).date(),
            config=config,
        )
        for seed in seeds
    ]


def store_checkpoints(records: StoreRecords) -> list[pd.Timestamp]:
    first = records.daily["date"].min() + pd.Timedelta(days=FIRST_CHECK_DAY)
    return checkpoints(first, records.daily["date"].max())


def _outcome(rows: pd.DataFrame, threshold: float) -> Outcome:
    alerts = rows["score"] >= threshold
    return Outcome(
        threshold=threshold,
        alerts=int(alerts.sum()),
        true_alerts=int((alerts & rows["anomaly"]).sum()),
        anomalies=int(rows["anomaly"].sum()),
        weeks=rows[["store", "date"]].drop_duplicates().shape[0],  # store-weeks
    )


def detection_delays(records: StoreRecords, scores: pd.DataFrame, threshold: float) -> list[float]:
    """For each problem starting on or after the first checkpoint: days from its start to the
    first checkpoint that flags it (inf if none does). `scores`: this store's rows for one
    detector, partly affected windows included."""
    first = scores["date"].min()
    delays = []
    for sku, onset in zip(records.labels["sku"], records.labels["onset"], strict=True):
        if onset < first:
            continue
        hits = scores[(scores["sku"] == sku) & (scores["date"] >= onset)]
        hits = hits[hits["score"] >= threshold]
        delays.append(float((hits["date"].min() - onset).days) if len(hits) else float("inf"))
    return delays


def _all_scores(records: StoreRecords, detectors: dict[str, Detector], store: int) -> pd.DataFrame:
    """Every product at every checkpoint, partly affected windows included (for delays)."""
    rows = []
    for point in store_checkpoints(records):
        window = window_at(records, point)
        for name, detector in detectors.items():
            for sku, score in detector(window).items():
                rows.append(
                    {"detector": name, "store": store, "date": point, "sku": sku,
                     "score": float(score)}
                )  # fmt: skip
    return pd.DataFrame(rows, columns=["detector", "store", "date", "sku", "score"])


def evaluate(
    validation: list[StoreRecords],
    test: list[StoreRecords],
    *,
    detectors: dict[str, Detector] = DETECTORS,
) -> pd.DataFrame:
    """Per detector: the threshold with the best F1 on the validation stores' weekly
    checkpoints, then on the test stores (never used to choose anything): precision, recall,
    false alarms per store-week, average precision, and days to detect problems that started
    after checking began."""

    def labelled(stores: list[StoreRecords]) -> pd.DataFrame:
        frames = [_label(_all_scores(r, detectors, n), r) for n, r in enumerate(stores)]
        return pd.concat(frames, ignore_index=True)

    validation_rows = labelled(validation)
    test_all = labelled(test)
    rows = []
    for name in detectors:
        tuning = validation_rows[(validation_rows["detector"] == name)].dropna(subset=["anomaly"])
        threshold = best_threshold(tuning.astype({"anomaly": bool}))
        mine = test_all[test_all["detector"] == name]
        scored = mine.dropna(subset=["anomaly"]).astype({"anomaly": bool})
        result = _outcome(scored, threshold)
        delays = [
            d
            for n, records in enumerate(test)
            for d in detection_delays(records, mine[mine["store"] == n], threshold)
        ]
        found = [d for d in delays if np.isfinite(d)]
        small = scored[scored["anomaly"] & (scored["problem_rate"] < SMALL_PROBLEM)]
        rows.append(
            {
                "detector": name,
                "threshold": threshold,
                "problem_weeks": result.anomalies,
                "alerts": result.alerts,
                "precision": result.precision,
                "recall": result.recall,
                "recall_small": (small["score"] >= threshold).mean() if len(small) else np.nan,
                "f1": result.f1,
                "false_per_week": result.false_alarms_per_week,
                "avg_precision": average_precision(
                    scored["score"].to_numpy(), scored["anomaly"].to_numpy()
                ),
                "new_problems": len(delays),
                "detected": len(found),
                "median_days_to_detect": float(np.median(found)) if found else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def _label(scores: pd.DataFrame, records: StoreRecords) -> pd.DataFrame:
    """Add `anomaly` (True, False, or None for partly affected windows, which aren't scored)
    and `problem_rate` (the planted extra loss rate; 0 without a problem)."""
    onsets = dict(zip(records.labels["sku"], records.labels["onset"], strict=True))
    rates = dict(zip(records.labels["sku"], records.labels["loss_rate"], strict=True))
    labels = [
        label_at(onsets.get(sku), day)
        for sku, day in zip(scores["sku"], scores["date"], strict=True)
    ]
    return scores.assign(
        anomaly=pd.Series(labels, index=scores.index, dtype="object"),
        problem_rate=scores["sku"].map(rates).fillna(0.0),
    )
