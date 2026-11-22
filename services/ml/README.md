# Tindawise ML

Demand forecasting experiments. Not connected to the API or the web app yet.
See [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md) ("Machine learning") and the results in
[`docs/ml/EXPERIMENTS.md`](../../docs/ml/EXPERIMENTS.md).

> The only data so far is **synthetic sample data** made by `tindawise_ml/synthetic.py`. The demo
> store has no real sales history. Results show the code works and how methods compare on that
> made-up data. They are not accuracy claims for a real store.

## Setup (Windows, from `services/ml`)

```bash
py -3.13 -m venv .venv                            # macOS/Linux: python3.13 -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # macOS/Linux: .venv/bin/python
```

No database needed.

## Use

```bash
# Score the baselines (naive, seasonal naive, 28-day moving average) on synthetic history
.venv/Scripts/python -m tindawise_ml backtest
.venv/Scripts/python -m tindawise_ml backtest --seed 3 --by-sku

# Write the synthetic history to a CSV, e.g. to explore it in a notebook
.venv/Scripts/python -m tindawise_ml generate --out history.csv
```

From the repo root: `npm run backtest:ml`, `npm run test:ml`, `npm run lint:ml`.

## Layout

| Module | What it does |
|---|---|
| `data.py` | The daily demand table contract (one zero-filled row per product per day) and its validator |
| `synthetic.py` | Seeded sample history for the 17 demo SKUs, with stockouts that cap sales |
| `baselines.py` | Naive, seasonal naive (7 days), moving average (28 days) |
| `metrics.py` | MAE, RMSE, WAPE |
| `backtest.py` | Rolling-origin backtest and scoring (stockout days skipped) |
| `__main__.py` | The `generate` and `backtest` commands |
