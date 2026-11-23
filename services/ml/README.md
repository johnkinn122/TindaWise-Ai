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

# Replay the test period with the app's current reorder rule and forecast-based ordering
# (moving average and LightGBM; cover 7/10/14 days x safety 0/1). A few minutes;
# --baselines-only skips LightGBM. Synthetic data only: it needs the true demand.
.venv/Scripts/python -m tindawise_ml policies
.venv/Scripts/python -m tindawise_ml policies --cover 10 --safety 1 --seed 3 --lead-seed 3

# Plant labelled anomalies (sales spikes, zero-sale days) and score three detectors: thresholds
# chosen on the validation period, scored on the test period. Synthetic data only.
.venv/Scripts/python -m tindawise_ml anomalies
.venv/Scripts/python -m tindawise_ml anomalies --seed 3 --rate 0.05
# Also score the ratio rule at the fixed multiples the app uses (spike 3x, drop 7.5x).
.venv/Scripts/python -m tindawise_ml anomalies --fixed 3 7.5

# Simulate stores with stock counts and planted shrinkage (stock going missing unrecorded);
# thresholds chosen on 10 validation stores, scored on separate test stores. Synthetic only.
.venv/Scripts/python -m tindawise_ml shrinkage
.venv/Scripts/python -m tindawise_ml shrinkage --count-every 28 --seeds 42 1 2

# Run on a table exported from the database (services/api scripts.export_demand) instead.
# No oracle row: that needs the generator's formula.
.venv/Scripts/python -m tindawise_ml backtest --csv demand.csv
```

From the repo root: `npm run backtest:ml`, `npm run tune:ml`, `npm run policies:ml`, `npm run anomalies:ml`, `npm run shrinkage:ml`, `npm run test:ml`, `npm run lint:ml`.

## Layout

| Module | What it does |
|---|---|
| `data.py` | The daily demand table contract (one zero-filled row per product per day), its validator, the CSV loader, and `History` (what a forecaster sees) |
| `synthetic.py` | Seeded sample history for the 17 demo SKUs, with deliveries, closing stock and stockouts that cap sales; the oracle floor |
| `baselines.py` | Naive, seasonal naive (7 days), moving average (28 days) |
| `features.py` | Feature rows for the direct multi-horizon model (only days up to the origin) |
| `gbm.py` | The LightGBM forecaster and its tuned settings |
| `tuning.py` | The settings grid, scored on the validation period only |
| `inventory.py` | Reorder policy simulation: the app's current rule vs forecast-based ordering |
| `anomalies.py` | Labelled anomaly injection, three detectors (ratio, robust z, count tail), evaluation |
| `shrinkage.py` | Store simulation with true vs recorded stock, counts and planted losses; three shrinkage detectors; evaluation on separate stores |
| `metrics.py` | MAE, RMSE, WAPE, bias |
| `backtest.py` | Rolling-origin backtest; daily and window-total scoring (stockout days skipped) |
| `__main__.py` | The `generate`, `backtest`, `tune`, `policies`, `anomalies` and `shrinkage` commands |
