# Tindawise ML

Demand forecasting experiments: baselines and a LightGBM forecaster. Not connected to the API or
the web app yet.
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
# Score the baselines and LightGBM on the test period (last 84 days), daily and as 7-day totals,
# next to the oracle floor. About 10 s; --baselines-only skips LightGBM.
.venv/Scripts/python -m tindawise_ml backtest
.venv/Scripts/python -m tindawise_ml backtest --seed 3 --by-sku

# Score the LightGBM settings grid on the validation period (the 84 days before the test period).
# A few minutes. Copy the winner into gbm.DEFAULT_PARAMS, then run `backtest` once.
.venv/Scripts/python -m tindawise_ml tune

# Write the synthetic history to a CSV, e.g. to explore it in a notebook. --end makes it end on
# a given day (used to seed the API's sample store so its history ends yesterday).
.venv/Scripts/python -m tindawise_ml generate --out history.csv
.venv/Scripts/python -m tindawise_ml generate --end 2026-11-21 --out history.csv

# Run on a table exported from the database (services/api scripts.export_demand) instead.
# No oracle row: that needs the generator's formula.
.venv/Scripts/python -m tindawise_ml backtest --csv demand.csv
```

From the repo root: `npm run backtest:ml`, `npm run tune:ml`, `npm run test:ml`, `npm run lint:ml`.

## Layout

| Module | What it does |
|---|---|
| `data.py` | The daily demand table contract (one zero-filled row per product per day), its validator, the CSV loader, and `History` (what a forecaster sees) |
| `synthetic.py` | Seeded sample history for the 17 demo SKUs, with deliveries, closing stock and stockouts that cap sales; the oracle floor |
| `baselines.py` | Naive, seasonal naive (7 days), moving average (28 days) |
| `features.py` | Feature rows for the direct multi-horizon model (only days up to the origin) |
| `gbm.py` | The LightGBM forecaster and its tuned settings |
| `tuning.py` | The settings grid, scored on the validation period only |
| `metrics.py` | MAE, RMSE, WAPE, bias |
| `backtest.py` | Rolling-origin backtest; daily and window-total scoring (stockout days skipped) |
| `__main__.py` | The `generate`, `backtest` and `tune` commands |
