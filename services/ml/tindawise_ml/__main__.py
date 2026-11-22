"""Command line: `python -m tindawise_ml <command>`.

- generate: write the synthetic history to a CSV file
- backtest: score the baselines on the synthetic history and print Markdown tables
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

import pandas as pd

from tindawise_ml.backtest import run_backtest, score, tiling_origins
from tindawise_ml.baselines import BASELINES
from tindawise_ml.synthetic import DEFAULT_DAYS, DEFAULT_SEED, DEFAULT_START, generate_history


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

    backtest = commands.add_parser("backtest", help="score the baselines on synthetic history")
    _history_args(backtest)
    backtest.add_argument("--test-days", type=int, default=84)
    backtest.add_argument("--horizon", type=int, default=7)
    backtest.add_argument("--by-sku", action="store_true", help="also print one row per product")

    args = parser.parse_args(argv)
    history = generate_history(start=args.start, days=args.days, seed=args.seed)

    if args.command == "generate":
        history.to_csv(args.out, index=False)
        print(f"Wrote {len(history):,} rows to {args.out}")
        print(_describe(history))
        return 0

    origins = tiling_origins(history, test_days=args.test_days, horizon=args.horizon)
    forecasts = run_backtest(history, BASELINES, origins, horizon=args.horizon)
    print(_describe(history))
    print(
        f"\nTest period: {(origins[0] + pd.Timedelta(days=1)).date()} to "
        f"{(origins[-1] + pd.Timedelta(days=args.horizon)).date()}, "
        f"{len(origins)} origins, {args.horizon}-day horizon, seed {args.seed}\n"
    )
    print(_markdown(score(forecasts).sort_values("wape")))
    if args.by_sku:
        print()
        print(_markdown(score(forecasts, by=["sku"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
