"""Unusual product-days: sales far above or below what the product normally sells.

Why a store cares: a spike can be a bulk buyer (good to know) or a duplicate entry (an error);
a day with no sales for a product that sells every day, while it was in stock, can mean sales
went unrecorded. Either is worth a second look; most days are not.

How this is evaluated, since the synthetic data has no real anomalies:

1. `inject_anomalies` plants labelled ones into the synthetic history: spikes (a bulk purchase
   or duplicate entry) and drops to zero on in-stock days of products that normally sell several
   a day. Only in-stock days are touched, so an empty shelf is never mistaken for an anomaly.
2. Each detector scores every product-day using **only earlier days** (rolling windows shifted
   by one day), as it would run each night on real data.
3. A threshold is chosen per detector on the validation period (best F1), then scored once on
   the test period: precision, recall, false alarms per week, and average precision.

The data's own patterns (paydays, Christmas, noise) are not labelled anomalies, so flagging them
counts as a false alarm. That's deliberate: an owner wouldn't want an alert every payday.
"""

from __future__ import annotations

import zlib
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

from tindawise_ml.data import to_wide, validate_demand_frame

WINDOW_DAYS = 28
MIN_IN_STOCK_DAYS = 14  # fewer in-stock days in the window: no score (too little history)

# ── Planting labelled anomalies ─────────────────────────────────────────────


def inject_anomalies(
    frame: pd.DataFrame,
    *,
    rate: float = 0.02,
    seed: int = 0,
    start: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (frame with anomalies, labels). Labels have date, sku, kind, original, injected.

    About `rate` of eligible product-days from `start` on get an anomaly, half spikes and half
    drops. Spikes add max(5, 3 x the product's usual daily sales) units. Drops set an in-stock
    day to 0, only for products that usually sell 3+ a day (for a slow seller a zero day is
    normal). "Usual" is the product's average over the whole history, which only the test
    harness uses; detectors never see it.

    The injected rows no longer match `closing_stock`, so don't feed this table to the seeder.
    """
    validate_demand_frame(frame)
    rng = np.random.default_rng(np.random.SeedSequence(seed, spawn_key=(zlib.crc32(b"anom"),)))
    out = frame.copy()
    usual = out.groupby("sku")["units_sold"].transform("mean")
    eligible = ~out["stockout"]
    if start is not None:
        eligible &= out["date"] >= start
    picked = eligible & (rng.random(len(out)) < rate)
    kinds = np.where(rng.random(len(out)) < 0.5, "spike", "drop")
    # A drop on a slow seller isn't an anomaly; such picks become spikes instead.
    kinds = np.where((kinds == "drop") & (usual < 3), "spike", kinds)

    rows = out.index[picked]
    original = out.loc[rows, "units_sold"].to_numpy()
    spike_size = np.maximum(5, np.round(3 * usual.loc[rows].to_numpy())).astype(np.int64)
    injected = np.where(kinds[picked] == "spike", original + spike_size, 0)
    out.loc[rows, "units_sold"] = injected.astype(np.int64)

    labels = pd.DataFrame(
        {
            "date": out.loc[rows, "date"].to_numpy(),
            "sku": out.loc[rows, "sku"].to_numpy(),
            "kind": kinds[picked],
            "original": original,
            "injected": injected,
        }
    )
    # A drop on a day that already sold 0 changes nothing: not a real anomaly, so not a label.
    keep = labels["original"] != labels["injected"]
    out.loc[rows[~keep.to_numpy()], "units_sold"] = labels.loc[~keep, "original"].to_numpy()
    return out, labels[keep].reset_index(drop=True)


# ── Detectors ───────────────────────────────────────────────────────────────
#
# Each returns two dates x SKUs score tables: "high" (unusually many sold) and "low" (unusually
# few). Higher = more unusual. They are separate alerts with separate thresholds: a duplicate
# entry and missing sales are different problems, and one combined ranking would let whichever
# direction a detector's scale favours crowd out the other.


def _history(sold: pd.DataFrame, stockout: pd.DataFrame) -> pd.DataFrame:
    """In-stock sales, NaN on stockout days, shifted one day: row d only holds days before d."""
    return sold.astype(float).where(~stockout).shift(1)


def _enough(past: pd.DataFrame) -> pd.DataFrame:
    return past.rolling(WINDOW_DAYS, min_periods=1).count() >= MIN_IN_STOCK_DAYS


Scores = tuple[pd.DataFrame, pd.DataFrame]


def ratio_score(sold: pd.DataFrame, stockout: pd.DataFrame) -> Scores:
    """Baseline: times above or below the recent in-stock average, on a log scale
    (log((y+1)/(m+1)) for high, its negative for low)."""
    past = _history(sold, stockout)
    mean = past.rolling(WINDOW_DAYS, min_periods=1).mean()
    log_ratio = np.log((sold + 1) / (mean + 1)).where(_enough(past))
    return log_ratio, -log_ratio


def robust_z_score(sold: pd.DataFrame, stockout: pd.DataFrame) -> Scores:
    """(y - median) / (1.4826 x MAD + 0.5) over recent in-stock days. Median and MAD ignore the
    odd extreme day in the window; the +0.5 keeps slow sellers (MAD 0) from scoring infinity."""
    past = _history(sold, stockout)
    rolling = past.rolling(WINDOW_DAYS, min_periods=1)
    median = rolling.median()
    mad = rolling.apply(lambda w: np.nanmedian(np.abs(w - np.nanmedian(w))), raw=True)
    z = ((sold - median) / (1.4826 * mad + 0.5)).where(_enough(past))
    return z, -z


def count_tail_score(sold: pd.DataFrame, stockout: pd.DataFrame) -> Scores:
    """-log10 of the tail probability of today's count, under a negative binomial with the recent
    in-stock mean and variance (Poisson when the variance isn't above the mean): P(Y >= y) for
    high, P(Y <= y) for low. 3 means "about a 1-in-1,000 day" for this product."""
    past = _history(sold, stockout)
    rolling = past.rolling(WINDOW_DAYS, min_periods=1)
    mean = np.maximum(
        rolling.mean().to_numpy(), 0.05
    )  # never sold: a sale is unusual, not impossible
    var = rolling.var(ddof=0).to_numpy()
    y = sold.to_numpy(dtype=float)

    overdispersed = var > mean * 1.0001
    k = np.where(overdispersed, mean**2 / np.where(overdispersed, var - mean, 1.0), np.inf)
    with np.errstate(invalid="ignore", divide="ignore"):
        # Negative binomial with n = k, p = k / (k + mean); Poisson where k is infinite.
        finite = np.isfinite(k)
        p = np.where(finite, k / (k + mean), 1.0)
        upper = np.where(finite, stats.nbinom.sf(y - 1, k, p), stats.poisson.sf(y - 1, mean))
        lower = np.where(finite, stats.nbinom.cdf(y, k, p), stats.poisson.cdf(y, mean))
    enough = _enough(past)

    def table(tail: np.ndarray) -> pd.DataFrame:
        score = -np.log10(np.clip(tail, 1e-300, 1.0))
        return pd.DataFrame(score, index=sold.index, columns=sold.columns).where(enough)

    return table(upper), table(lower)


Detector = Callable[[pd.DataFrame, pd.DataFrame], Scores]

DETECTORS: dict[str, Detector] = {
    "ratio (baseline)": ratio_score,
    "robust_z": robust_z_score,
    "count_tail": count_tail_score,
}

DIRECTIONS = {"spike": 0, "drop": 1}  # which of a detector's two tables each kind uses


# ── Evaluation ──────────────────────────────────────────────────────────────


def scored_days(
    frame: pd.DataFrame, labels: pd.DataFrame, detector: Detector, kind: str
) -> pd.DataFrame:
    """Long table for one kind of anomaly ("spike" or "drop"): date, sku, score, anomaly (bool:
    a planted anomaly of this kind). Stockout days and days without enough history are left
    out: there's nothing to judge."""
    validate_demand_frame(frame)
    sold, stockout = to_wide(frame, "units_sold"), to_wide(frame, "stockout")
    table = detector(sold, stockout)[DIRECTIONS[kind]]
    # dropna: pandas 3's stack() keeps empty cells, and stockout / warm-up days have no score.
    scores = table.where(~stockout).stack().dropna().rename("score").reset_index()
    scores.columns = ["date", "sku", "score"]
    marked = labels[labels["kind"] == kind].assign(anomaly=True)[["date", "sku", "anomaly"]]
    out = scores.merge(marked, on=["date", "sku"], how="left")
    out["anomaly"] = out["anomaly"].fillna(False).astype(bool)
    return out


def average_precision(scores: np.ndarray, truth: np.ndarray) -> float:
    """Mean precision at each true anomaly when days are ranked by score (threshold-free)."""
    if truth.sum() == 0:
        return float("nan")
    order = np.argsort(-scores, kind="stable")
    hits = truth[order]
    precision_at = np.cumsum(hits) / np.arange(1, len(hits) + 1)
    return float(precision_at[hits].mean())


@dataclass(frozen=True)
class Outcome:
    threshold: float
    alerts: int
    true_alerts: int
    anomalies: int
    weeks: float

    @property
    def precision(self) -> float:
        return self.true_alerts / self.alerts if self.alerts else float("nan")

    @property
    def recall(self) -> float:
        return self.true_alerts / self.anomalies if self.anomalies else float("nan")

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0

    @property
    def false_alarms_per_week(self) -> float:
        return (self.alerts - self.true_alerts) / self.weeks


def outcome_at(days: pd.DataFrame, threshold: float) -> Outcome:
    alerts = days["score"] >= threshold
    weeks = days["date"].nunique() / 7
    return Outcome(
        threshold=threshold,
        alerts=int(alerts.sum()),
        true_alerts=int((alerts & days["anomaly"]).sum()),
        anomalies=int(days["anomaly"].sum()),
        weeks=weeks,
    )


def best_threshold(days: pd.DataFrame) -> float:
    """The score cut-off with the best F1 on these days (ties: the higher, fewer alerts)."""
    candidates = np.unique(days.loc[days["anomaly"], "score"].to_numpy())
    if candidates.size == 0:
        return float("inf")
    best = max(candidates, key=lambda t: (outcome_at(days, t).f1, t))
    return float(best)


def evaluate(
    frame: pd.DataFrame,
    labels: pd.DataFrame,
    *,
    validation_start: pd.Timestamp,
    test_start: pd.Timestamp,
    detectors: dict[str, Detector] = DETECTORS,
) -> pd.DataFrame:
    """Per detector and kind: the threshold chosen on validation days [validation_start,
    test_start), then precision, recall, F1, false alarms per week and average precision on the
    test days (test_start onwards). The test days are never used to choose anything."""
    rows = []
    for name, detector in detectors.items():
        for kind in DIRECTIONS:
            days = scored_days(frame, labels, detector, kind)
            validation = days[(days["date"] >= validation_start) & (days["date"] < test_start)]
            test = days[days["date"] >= test_start]
            threshold = best_threshold(validation)
            result = outcome_at(test, threshold)
            rows.append(
                {
                    "detector": name,
                    "kind": kind,
                    "threshold": threshold,
                    "anomalies": result.anomalies,
                    "alerts": result.alerts,
                    "precision": result.precision,
                    "recall": result.recall,
                    "f1": result.f1,
                    "false_per_week": result.false_alarms_per_week,
                    "avg_precision": average_precision(
                        test["score"].to_numpy(), test["anomaly"].to_numpy()
                    ),
                }
            )
    return pd.DataFrame(rows)


def evaluate_fixed(
    frame: pd.DataFrame,
    labels: pd.DataFrame,
    *,
    test_start: pd.Timestamp,
    multiples: dict[str, float],
) -> pd.DataFrame:
    """The ratio rule at fixed, plain cut-offs, scored on the test days only. This is the rule
    the app runs (services/api `app/services/anomalies.py`), so it needs one set of numbers for
    every store instead of a threshold tuned per dataset.

    `multiples` per kind: a spike is (sold + 1) >= m x (usual + 1); a drop is
    (usual + 1) >= m x (sold + 1). On the log scale that's a threshold of log(m)."""
    rows = []
    for kind, multiple in multiples.items():
        days = scored_days(frame, labels, ratio_score, kind)
        test = days[days["date"] >= test_start]
        # Rounding keeps log(m) computed two ways from splitting an exact tie.
        result = outcome_at(test.assign(score=test["score"].round(9)), round(np.log(multiple), 9))
        rows.append(
            {
                "kind": kind,
                "multiple": multiple,
                "anomalies": result.anomalies,
                "alerts": result.alerts,
                "true_alerts": result.true_alerts,
                "precision": result.precision,
                "recall": result.recall,
                "f1": result.f1,
                "false_per_week": result.false_alarms_per_week,
            }
        )
    return pd.DataFrame(rows)
