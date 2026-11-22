# ML experiments

Newest first. Each entry records the data, the setup, the actual numbers and what they do and don't
show. Commands are from `services/ml` with its virtual environment.

---

## 2026-11-22 — Baselines on synthetic history (`feature/ml-baselines`)

### Why
CLAUDE.md §7: trained models must be compared against simple baselines. These numbers are the bar a
future model (LightGBM is next) has to clear on the same data and the same test period.

### Data: synthetic, not real
`tindawise_ml.synthetic.generate_history()` with defaults: 17 demo SKUs, 2024-01-01 to 2025-12-30
(730 days), seed 42. Demand follows assumed weekday, payday (15th/16th, last day/1st), month,
hot-season and Christmas effects, plus an 8%/year trend and negative binomial noise. A stock
simulation (reorder at the reorder level, 1-3 day lead time, 25% chance per low-stock day of not
reordering yet) turns demand into sales.

- 53,366 units sold of 55,522 wanted: **3.9% of demand lost to stockouts**
- 3.7% of product-days are stockout days

### Setup
- Rolling origin, 7-day horizon, 12 weekly origins tiling the last 84 days (2025-10-08 to 2025-12-30).
  Each forecast sees only sales up to its origin.
- Scored on product-days, pooled over all products. Stockout days (77 of 1,428) are skipped
  because their sales are below demand.
- Command: `python -m tindawise_ml backtest`

### Results (seed 42)

| model | scored days | MAE | RMSE | WAPE |
|---|---|---|---|---|
| moving_average_28 | 1351 | 2.56 | 3.89 | 50.5% |
| naive | 1351 | 3.33 | 5.02 | 65.8% |
| seasonal_naive_7 | 1351 | 3.50 | 5.29 | 69.1% |

Same setup, other seeds (WAPE): moving average 52.7 / 51.8 / 49.6 / 50.6 / 49.2% (seeds 1-5);
naive and seasonal naive stay between 64.9% and 71.9% and swap places from seed to seed.

### What this shows
- **The 28-day moving average is the baseline to beat**, by about 15 WAPE points, on every seed
  tried. One product-day is noisy (many items sell 1-10 units), so averaging four weeks beats
  copying a single day.
- Seasonal naive doesn't win here because the assumed weekday effect is mild (about ±10%) next
  to the day-to-day noise. On a store with stronger weekly patterns it could.
- Slow movers (condiments, SkyFlakes 10-pack, soap) have WAPE of 79-89% even for the moving
  average: at about one unit a day, most of the error is noise no forecast can remove. Per-product
  numbers: `--by-sku`.

### What this does not show
- Anything about a real store. The patterns and their sizes are assumptions written into
  `synthetic.py`, so a model that learns them is learning our assumptions.
- How good the forecasts are for *ordering*. Under-forecasting empties the shelf while
  over-forecasting ties up cash, and these metrics weigh both the same.
- The effect of censored history. Baselines read stockout days as they were recorded, which pulls
  them down; that bias is part of the numbers above.

### Next
1. LightGBM with lag, weekday, payday and month features, tuned on the 84 days *before* this test
   period, then run once on the test period and compared with the table above.
2. A loader that builds the same daily table from the real `sale_lines` and `stock_movements`.
