# ML experiments

Newest first. Each entry records the data, the setup, the actual numbers and what they do and don't
show. Commands are from `services/ml` with its virtual environment.

---

## 2026-11-22 — LightGBM forecaster (`feature/ml-lightgbm`)

### Model
One LightGBM model for all 17 products (product as a categorical feature), Poisson objective,
direct multi-horizon: each row is (origin, h = 1-7, product), with features from days up to the
origin only (recent means, same weekday in past weeks, an in-stock-only mean, stockout share)
plus the target day's weekday, day of month, payday and month. Stockout days are dropped as
training labels. It is retrained at every origin on all history before it. Details:
`tindawise_ml/features.py`, `tindawise_ml/gbm.py`.

### Tuning: validation period only
`python -m tindawise_ml tune`: 18 settings (num_leaves 7/15/31 × min_data_in_leaf 50/200 ×
rounds 150/300/600) scored on the 84 days *before* the test period (2025-07-16 to 2025-10-07).

- Every setting scored a daily WAPE between 49.7% and 50.6%. The moving average scored 50.7%.
  The settings barely matter on this data.
- An **oracle** that knows the generator's true mean demand scores **49.6%** on the same days.
  That is the noise floor: nearly all daily error is randomness no forecast can remove.
- Because daily scores can't separate the methods, I also scored **7-day totals per product**
  (what a reorder depends on), still on validation: oracle 20.7%, LightGBM 20.8%, moving
  average 22.0%.
- Chosen: `num_leaves=7, min_data_in_leaf=200, rounds=300`. It tied for best (49.7%) with
  `min_data_in_leaf=50`, and I took the more regularised of the two.

### Test period: run once with those settings (seed 42, 2025-10-08 to 2025-12-30)

Command: `python -m tindawise_ml backtest`.

| model | daily MAE | daily RMSE | daily WAPE | 7-day WAPE | bias |
|---|---|---|---|---|---|
| oracle (true mean, synthetic only) | 2.51 | 3.71 | 49.7% | 20.0% | +0.6% |
| **lightgbm** | **2.51** | **3.80** | **49.7%** | **20.8%** | **−4.4%** |
| moving_average_28 | 2.56 | 3.89 | 50.5% | 22.6% | −6.1% |
| seasonal_naive_7 | 3.50 | 5.29 | 69.1% | 28.6% | −3.9% |
| naive | 3.33 | 5.02 | 65.8% | 49.7% | −19.0% |

Same settings on five other synthetic datasets (no re-tuning), 7-day WAPE:

| seed | oracle | lightgbm | moving_average_28 |
|---|---|---|---|
| 1 | 20.9% | 21.4% | 23.5% |
| 2 | 18.7% | 19.6% | 21.0% |
| 3 | 20.3% | 21.8% | 24.4% |
| 4 | 20.8% | 21.5% | 23.6% |
| 5 | 20.0% | 20.4% | 22.3% |

On daily WAPE, LightGBM beat the moving average on 5 of 6 datasets. On seed 2 the moving
average was 0.3 points better (51.8% vs 52.1%).

### What this shows
- **LightGBM beats the best baseline on 7-day totals on all 6 datasets**, by 1.4 to 2.6 points.
  It ends up 0.4 to 1.5 points from the floor, where the moving average is 2.3 to 4.1 points
  from it. On seed 42 it closes about 70% of the gap between the moving average and the floor.
- **It under-forecasts less** (−1.9% to −4.8% vs −4.6% to −9.1% for the moving average). The
  moving average lags behind the trend and the Christmas build-up, and reading stockout days as
  low sales pulls it down further.
- **The daily gain is small (about 1 point) because the noise floor is close.** On this data,
  "no better than the moving average" and "nearly perfect" are only about 1 WAPE point apart.
- Naive's −19% bias: every test origin falls on a Tuesday (a slow day), so "repeat the last day"
  copies a slow day into the whole week.

### What this does not show
- **Real-store accuracy.** The model learns the patterns written into `synthetic.py`, and its
  features (weekday, payday, month) match the effects the generator uses. That makes the
  synthetic data friendly to it. A real store has effects the generator doesn't (holidays that
  move, promotions, weather, new products).
- **Only one prior December.** The test period ends in December and the model has seen one
  December before it. Its month effect for December rests on a single year.
- **Skipping stockout days is slightly biased.** Stockouts happen more on high-demand days, so
  the days left to score lean low. The oracle's positive bias (+0.6% to +5.2%) shows this, and
  every model's bias is measured against those leaner days.
- **Cost.** One fit takes about 0.7 s, and the backtest retrains at each of 12 origins, so a full
  backtest takes about 11 s and tuning about 3 minutes. That's fine for 17 products and two years
  of data. It wasn't measured for a large catalogue.

### Next
1. A loader that builds the same daily table from the real `sale_lines` and `stock_movements`.
2. Turn the forecast into stockout risk and reorder quantities (forecast over the lead time
   against stock on hand), and compare with the current fixed reorder rule.

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
