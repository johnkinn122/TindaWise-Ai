"""Command line: `python -m tindawise_ml <command>`.

- generate: write the synthetic history to a CSV file
- backtest: score the baselines and LightGBM on the test period and print Markdown tables
- tune: score LightGBM settings on the validation period (never the test period)
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

import pandas as pd

from tindawise_ml.backtest import run_backtest, score, score_totals, tiling_origins
from tindawise_ml.baselines import BASELINES
from tindawise_ml.gbm import make_lightgbm_forecaster
from tindawise_ml.synthetic import (
    DEFAULT_DAYS,
    DEFAULT_SEED,
    DEFAULT_START,
    generate_history,
    oracle_forecasts,
)
from tindawise_ml.tuning import tune as run_tune


def _history_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--start", type=date.fromisoformat, default=DEFAULT_START)


def _markdown(table: pd.DataFrame) -> str:
    """A small Markdown table without the optional `tabulate` dependency."""
    shown = table.copy()
    for column in ("mae", "rmse"):
        if column in shown:
            shown[column] = shown[column].map(lambda v: f"{v:.2f}")
    if "wape" in shown:
        shown["wape"] = shown["wape"].map(lambda v: "n/a" if pd.isna(v) else f"{v:.1%}")
    if "bias" in shown:
        shown["bias"] = shown["bias"].map(lambda v: "n/a" if pd.isna(v) else f"{v:+.1%}")
    header = "| " + " | ".join(shown.columns) + " |"
    rule = "|" + "|".join("---" for _ in shown.columns) + "|"
    body = ["| " + " | ".join(str(v) for v in row) + " |" for row in shown.itertuples(index=False)]
    return "\n".join([header, rule, *body])


def _describe(history: pd.DataFrame) -> str:
    sold = int(history["units_sold"].sum())
    wanted = int(history["demand"].sum())
    return "\n".join(
        [
            "SYNTHETIC SAMPLE DATA, not real sales.",
            f"- {history['sku'].nunique()} products, {history['date'].min().date()} to "
            f"{history['date'].max().date()} ({history['date'].nunique()} days)",
            f"- {sold:,} units sold of {wanted:,} wanted "
            f"({1 - sold / wanted:.1%} lost to stockouts)",
            f"- stockout product-days: {history['stockout'].mean():.1%}",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tindawise_ml")
    commands = parser.add_subparsers(dest="command", required=True)

    generate = commands.add_parser("generate", help="write the synthetic history to CSV")
    _history_args(generate)
    generate.add_argument("--out", required=True, help="CSV file to write")

    backtest = commands.add_parser("backtest", help="score the forecasters on the test period")
    _history_args(backtest)
    backtest.add_argument("--test-days", type=int, default=84)
    backtest.add_argument("--horizon", type=int, default=7)
    backtest.add_argument("--by-sku", action="store_true", help="also print one row per product")
    backtest.add_argument(
        "--baselines-only", action="store_true", help="skip LightGBM (much faster)"
    )

    tune = commands.add_parser("tune", help="score LightGBM settings on the validation period")
    _history_args(tune)
    tune.add_argument("--period-days", type=int, default=84)
    tune.add_argument("--horizon", type=int, default=7)

    args = parser.parse_args(argv)
    history = generate_history(start=args.start, days=args.days, seed=args.seed)

    if args.command == "generate":
        history.to_csv(args.out, index=False)
        print(f"Wrote {len(history):,} rows to {args.out}")
        print(_describe(history))
        return 0

    if args.command == "tune":
        print(_describe(history))
        print(f"\nValidation period: the {args.period_days} days before the test period\n")
        print(_markdown(run_tune(history, period_days=args.period_days, horizon=args.horizon)))
        return 0

    origins = tiling_origins(history, test_days=args.test_days, horizon=args.horizon)
    forecasters = dict(BASELINES)
    if not args.baselines_only:
        forecasters["lightgbm"] = make_lightgbm_forecaster()
    forecasts = run_backtest(history, forecasters, origins, horizon=args.horizon)
    forecasts = pd.concat([forecasts, oracle_forecasts(forecasts, start=args.start)])
    print(_describe(history))
    print(
        f"\nTest period: {(origins[0] + pd.Timedelta(days=1)).date()} to "
        f"{(origins[-1] + pd.Timedelta(days=args.horizon)).date()}, "
        f"{len(origins)} origins, {args.horizon}-day horizon, seed {args.seed}\n"
    )
    print("Daily, per product (stockout days skipped):\n")
    print(_markdown(score(forecasts).sort_values("wape")))
    print(f"\n{args.horizon}-day totals, per product (what a reorder depends on):\n")
    print(_markdown(score_totals(forecasts).sort_values("wape")))
    print(
        "\nThe oracle knows the generator's true mean demand. Its error is pure noise: the floor."
    )
    if args.by_sku:
        print()
        print(_markdown(score(forecasts, by=["sku"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
