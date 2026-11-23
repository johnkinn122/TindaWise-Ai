# ML experiments

Newest first. Each entry records the data, the setup, the actual numbers and what they do and don't
show. Commands are from `services/ml` with its virtual environment.

---

## 2026-11-23 — Shrinkage: finding stock that goes missing (`feature/ml-shrinkage`)

### Why
CLAUDE.md §7: detect unusual inventory patterns. Shrinkage (shoplifting, items taken by staff,
damage nobody records, short deliveries) is lost profit, and it makes recorded stock wrong:
a shelf the app thinks holds 5 can be empty, so it isn't reordered. The only place it shows in
Tindawise is a stock count, recorded as an `adjustment`. Which products' counts show more
missing stock than normal?

### Setup
- `simulate_store` (`shrinkage.py`) keeps **true** and **recorded** stock for the 17 demo
  products. Demand is drawn as in `synthetic.py` from separate random streams, so earlier
  experiments are unchanged (a test checks this).
  - Every product loses some stock unrecorded: a normal rate drawn per product, 0.5-2% of
    expected sales. A quarter of the products (4) get a **planted problem** from a random day:
    an extra 3-15%. These are the labels.
  - Recorded damage (0.5%) is explained loss and never counts.
  - A sale needs the unit on the shelf and in the records. Reorders follow recorded stock.
  - Each product is counted every 14 days (staggered), 10% of counts off by one, and the
    difference is recorded as an adjustment.
- Detectors run weekly from day 300 on the last **56 days** (four counts): missing units = the
  net of the adjustments, when it's a loss.
  - **missing units (baseline):** the units.
  - **share of sales:** missing / (units sold + 1), the retail "shrink %".
  - **poisson vs store rate:** -log10 P(this many missing) at the store's own loss rate over the
    half-year before the window.
- **Split by store, not by time:** thresholds (best F1) are chosen on 10 validation stores
  (seeds 1001-1010), then scored once on 6 test stores (seeds 42, 1-5; 24 problems). Windows
  that a problem only partly covers aren't scored. Days to detect: from a problem's start to the
  first weekly check that flags it, for the 18 problems that started after checking began.
- Command: `python -m tindawise_ml shrinkage [--count-every N]`.

### A first setup was too easy, and was changed before drawing conclusions
The first run had the same 1% normal loss on every product and problems of +8-20%. All three
detectors scored average precision 0.93-1.00. Real shrinkage is usually 1-2% of sales and
varies by product, so problems were made smaller (+3-15%) and normal loss varied per product
(0.5-2%). Only the second setup's results are used below.

### Results (6 test stores, counts every 14 days)

| detector | threshold | precision | recall | recall, problems under +6% | false alarms / store-week | avg precision | days to detect (median) |
|---|---|---|---|---|---|---|---|
| missing units (baseline) | 10 units | 67% | 64% | 45% | 0.59 | 0.74 | 20 (15 of 18 found) |
| **share of sales** | **5%** | **93%** | **88%** | **70%** | **0.12** | **0.96** | 29 (18 of 18) |
| poisson vs store rate | 1.91 | 93% | 81% | 58% | 0.12 | 0.93 | 28 (16 of 18) |

How often the store counts (`--count-every`):

| counted every | share of sales: precision / recall / small | false alarms / store-week | days to detect |
|---|---|---|---|
| 7 days | 93% / 91% / 75% | 0.14 | 30 |
| 14 days | 93% / 88% / 70% | 0.12 | 29 |
| 28 days | 95% / 86% / 63% | 0.08 | 33 |

### What this shows
- **The plain shrink % is best again:** "more than 5% of units sold went missing over the last
  8 weeks". It found every new problem, with about one false alarm per store every 8 weeks.
  It's also the rule an owner already understands.
- **Counting missing units alone doesn't work:** a fast seller's normal loss passes any count a
  slow seller's problem would reach. The Poisson test is close to the share but misses more
  small problems, probably because one store-wide rate fits products with a high normal loss
  badly (not tested separately).
- **Detection takes about a month:** the loss has to build up to 5% of 8 weeks of sales.
- **Counting more often barely helps** over an 8-week window: it adds a little recall for small
  problems. What matters is counting regularly at all. Without counts there is nothing to see.

### What this does not show
- Real stores. Every rate here is an assumption, and real problems may come and go (a
  shoplifter who stops) instead of running steadily.
- Small stores' noise at small numbers: a product selling 1 a day sells 56 in a window, so
  3 missing units is already 5%. Miscounts are only modelled as off by one.
- Short deliveries recorded as full, and refunds put back on the shelf, aren't modelled.

---

## 2026-11-23 — Fixed multiples for the app's anomaly rule (`feature/anomaly-alerts`)

### Why
The experiment below chose each threshold per dataset on its validation period. The app needs
one fixed rule for every store, written as plain multiples an owner can read.

### Setup
- The six validation-period thresholds for the ratio rule (log scale) were drops 1.74-2.13,
  median 2.03, and spikes 1.03-1.33, median 1.14. Rounded to plain multiples **before
  looking at any test score**: drop e^2.03 = 7.6 → **7.5×**, spike e^1.14 = 3.1 → **3×**.
- Spike: (sold + 1) ≥ 3 × (usual + 1). Drop: (usual + 1) ≥ 7.5 × (sold + 1).
- Scored once on the same six test periods. No other values were tried.
- Command: `python -m tindawise_ml anomalies --seed N --fixed 3 7.5` (seeds 42, 1-5).

### Results (test periods)

| seed | spike: alerts / true / planted | drop: alerts / true / planted |
|---|---|---|
| 42 | 24 / 10 / 19 | 7 / 7 / 11 |
| 1 | 22 / 13 / 21 | 9 / 3 / 6 |
| 2 | 23 / 11 / 18 | 5 / 2 / 7 |
| 3 | 24 / 9 / 13 | 5 / 5 / 8 |
| 4 | 25 / 10 / 21 | 4 / 3 / 4 |
| 5 | 17 / 10 / 24 | 6 / 3 / 6 |

Pooled over the six test periods (72 weeks in total):

| kind | rule | precision | recall | false alarms / week |
|---|---|---|---|---|
| spike | fixed 3× | 47% | 54% | 1.00 |
| spike | tuned per dataset | 50% | 49% | 0.79 |
| drop | fixed 7.5× | 64% | 55% | 0.18 |
| drop | tuned per dataset | 56% | 52% | 0.24 |

### What this shows
- One fixed rule does about as well as thresholds tuned per dataset: slightly better for drops,
  and for spikes a few more catches for about 0.2 more false alarms a week. The app uses 3×
  and 7.5× (`services/api/app/services/anomalies.py`).
- About 1.2 false alarms a week for a 17-product store. Fine for a short list someone glances at
  and dismisses, too many for push notifications.

### What this does not show
- Real stores. These are the same planted anomalies and synthetic data as below.
- How it scales with store size. False alarms grow with the number of products, so a store
  with 500 products would see many more. The list may need a cap or a stricter spike multiple
  then.

---

## 2026-11-23 — Anomaly detection on planted anomalies (`feature/ml-anomalies`)

### Why
CLAUDE.md §7: detect unusual sales patterns. A spike can be a bulk buyer or a duplicate entry.
A day with no sales for a product that sells every day, while it was in stock, can mean sales
went unrecorded. Both are worth a second look, and most days are not.

### Setup
- Synthetic history (17 products, 730 days). From the start of the validation period, 2% of
  in-stock product-days get a labelled anomaly:
  - **Spike:** + max(5, 3 × the product's usual daily sales).
  - **Drop:** the day's sales set to 0, only for products that usually sell 3+ a day (for a
    slow seller a zero day is normal).
- Three detectors score each product-day from the **previous 28 days, in-stock days only**
  (at least 14 needed). High and low are separate alerts with separate thresholds:
  - **ratio (baseline):** log((y + 1) / (recent average + 1)).
  - **robust_z:** (y − median) / (1.4826 × MAD + 0.5).
  - **count_tail:** −log10 of the negative binomial tail probability with the recent mean and
    variance (Poisson when not overdispersed).
- The threshold for each detector and kind (best F1) is chosen on the validation period (84
  days), then scored once on the test period (the last 84 days). The data's own patterns
  (paydays, Christmas, noise) aren't labelled, so flagging them counts as a false alarm.
- Command: `python -m tindawise_ml anomalies [--seed N]`. Six datasets (seeds 42, 1-5).

### Results (test periods, six datasets)

| kind | detector | avg precision, mean (range) | precision | recall | false alarms / week |
|---|---|---|---|---|---|
| drop | **ratio (baseline)** | **0.66** (0.39-0.86) | 56% | 52% | 0.24 |
| drop | count_tail | 0.52 (0.36-0.79) | 43% | 43% | 0.33 |
| drop | robust_z | 0.29 (0.06-0.58) | 16% | 24% | 0.72 |
| spike | **ratio (baseline)** | **0.50** (0.40-0.63) | 50% | 49% | 0.79 |
| spike | count_tail | 0.45 (0.32-0.56) | 45% | 47% | 0.94 |
| spike | robust_z | 0.30 (0.22-0.34) | 33% | 32% | 1.06 |

Precision and recall are pooled over the six test periods (42 drops, 116 spikes in total).
False alarms are for the whole store (17 products).

The ratio baseline had the best average precision on 5 of 6 datasets for drops, and on 4 of 6
for spikes. count_tail won the rest.

### What this shows
- **The simple ratio is the best detector here**, the third time in this phase that a plain
  method matched or beat a fancier one. Its seed-42 thresholds read as plain rules: "a product
  that usually sells about 6.5+ a day sold nothing while in stock", and "sold more than about
  3× its usual".
- **Drops are easier than spikes.** A zero day stands out against a steady seller, while a
  spike competes with the data's real heavy-tailed big days (paydays, December, noise).
- **The robust z-score does worst** despite resisting outliers. MAD is often 0 or 1 for low
  counts, so its scale is crude. The count model handles low counts properly but estimates
  its variance from a window that contains earlier anomalies and big days.
- At these thresholds, a store would see about 1 false alarm a week in total. That's a
  tolerable level for a "worth a look" list.

### What this does not show
- **Real anomalies.** The planted ones follow rules I chose, and a real duplicate entry or
  missing sale may look different.
- **Stable numbers.** There are only 4-11 drops per test period, so one dataset's figures
  swing widely (drop F1 from 0.00 to 0.78). The six-dataset averages are the figures to quote.
- **Weekday effects.** No detector adjusts for them; the synthetic weekday effect is mild.
- **Stock anomalies** (shrinkage, theft). They need a simulation of count corrections first.

### Next
Show the ratio check in the app as a short nightly "worth a look" list. That needs somewhere to
show alerts and to dismiss them.

---

## 2026-11-23 — In-stock average for the app's reorder rule (`feature/forecast-reorder`)

### Why
The app's new reorder rule needed a daily rate that doesn't treat an empty shelf as "no demand".
A plain 28-day average falls after a stockout, so a product that's been out for a while would
get a small suggestion or none. Averaging only the in-stock days avoids that. Before building on
it, I ran it through the same simulation.

### Setup
As in the entry below: cover 10, safety 1, same test period, same seeds and delivery delays.
`in_stock_moving_average` in `baselines.py`. Reproduce with
`python -m tindawise_ml policies --cover 10 --safety 1 --baselines-only --seed N --lead-seed N`
(seed 42 uses `--lead-seed 0`).

### Results: lost units / orders / days of stock

| seed | current rule | plain average | in-stock average |
|---|---|---|---|
| 42 | 169 / 134 / 6.8 | 94 / 147 / 6.7 | **61** / 149 / 7.0 |
| 1 | 118 / 132 / 6.9 | 67 / 144 / 7.1 | **65** / 145 / 7.2 |
| 2 | 151 / 135 / 6.7 | 76 / 147 / 6.8 | **69** / 144 / 7.1 |
| 3 | 172 / 139 / 6.8 | 73 / 152 / 6.9 | **66** / 152 / 6.9 |
| 4 | 153 / 138 / 6.7 | 56 / 144 / 7.2 | **41** / 145 / 7.3 |
| 5 | 81 / 135 / 6.7 | 44 / 149 / 6.8 | **38** / 151 / 6.8 |

### What this shows
- The in-stock average lost fewer units than the plain average on all six datasets, with about
  the same number of orders and 0.0 to 0.3 more days of stock. The app uses it.
- Against the current rule, the in-stock version lost 45-73% fewer units.

### Not covered
- The app's extra rules: fewer than 7 in-stock days → reorder-level fallback, and subtracting
  open orders instead of waiting for them. With 28 days of history and no overlapping orders, the
  simulation never reaches either.

---

## 2026-11-23 — Does forecasting make better orders? (`feature/ml-reorder-policy`)

### Why
Forecast accuracy (WAPE) isn't what a store owner feels. Empty shelves, cash tied up in
stock, and trips to the supplier are. This replays the test period with different reorder
policies and measures those.

### Setup
- `python -m tindawise_ml policies` (`inventory.py`). Synthetic data, seed 42, replaying the
  same 84-day test period as the forecasting entries (2025-10-08 to 2025-12-30). The shelf
  starts at that morning's synthetic stock, with nothing on order.
- Every policy faces the same customers (the synthetic *true* demand, including what an
  empty shelf turned away) and the same random 1-3 day delivery delays.
- **Current rule (app):** when stock ≤ reorder level, order up to max(2 × reorder level,
  units sold in the last 14 days). That's the Overview's suggestion today.
- **Forecast policy:** reorder when stock ≤ forecast demand over the 3-day lead time + a buffer
  (safety × spread of recent in-stock daily sales × √3). Then order up to that plus `cover`
  more days of forecast. Forecasts are refreshed weekly from the sales the policy itself
  produced.
- Nobody reorders a product that already has an order on the way.
- The settings (cover 7/10/14 days × safety 0/1) were fixed before running. **All are reported;
  none was chosen by its result.**

### Results (seed 42)

| policy | fill rate | lost units | stockout days | days of stock | orders |
|---|---|---|---|---|---|
| current rule (app) | 97.8% | 169 | 2.7% | 6.8 | 134 |
| moving_average_28, cover 7, safety 0 | 97.6% | 184 | 5.2% | 4.4 | 193 |
| moving_average_28, cover 7, safety 1 | 98.6% | 106 | 2.5% | 5.2 | 193 |
| moving_average_28, cover 10, safety 0 | 97.9% | 160 | 3.4% | 5.9 | 146 |
| moving_average_28, cover 10, safety 1 | 98.8% | 94 | 2.1% | 6.7 | 147 |
| moving_average_28, cover 14, safety 0 | 98.7% | 100 | 3.4% | 7.5 | 108 |
| moving_average_28, cover 14, safety 1 | 99.4% | 48 | 0.9% | 8.7 | 110 |
| lightgbm, cover 7, safety 0 | 97.6% | 187 | 4.5% | 4.4 | 187 |
| lightgbm, cover 7, safety 1 | 98.8% | 92 | 2.2% | 5.4 | 190 |
| lightgbm, cover 10, safety 0 | 97.6% | 186 | 3.1% | 5.8 | 140 |
| lightgbm, cover 10, safety 1 | 99.0% | 76 | 1.3% | 6.9 | 143 |
| lightgbm, cover 14, safety 0 | 98.8% | 94 | 2.8% | 7.6 | 104 |
| lightgbm, cover 14, safety 1 | 99.7% | 26 | 0.9% | 8.6 | 109 |

Fill rate = units sold / units wanted. Days of stock = average units on the shelf / average
units wanted per day.

**Like for like:** cover 10 with safety 1 places about as many orders and holds about as much
stock as the current rule. I picked it for that match, not for its fill rate. It ran on five
more synthetic datasets, each with its own delivery delays (`--seed N --lead-seed N`):

| seed | current rule: lost / orders / days of stock | moving average | lightgbm |
|---|---|---|---|
| 42 | 169 / 134 / 6.8 | 94 / 147 / 6.7 | 76 / 143 / 6.9 |
| 1 | 118 / 132 / 6.9 | 67 / 144 / 7.1 | 69 / 145 / 7.1 |
| 2 | 151 / 135 / 6.7 | 76 / 147 / 6.8 | 77 / 141 / 7.2 |
| 3 | 172 / 139 / 6.8 | 73 / 152 / 6.9 | 71 / 147 / 7.0 |
| 4 | 153 / 138 / 6.7 | 56 / 144 / 7.2 | 59 / 142 / 7.1 |
| 5 | 81 / 135 / 6.7 | 44 / 149 / 6.8 | 36 / 145 / 6.9 |

### What this shows
- **Forecast-based ordering loses 40-65% fewer sales than the current rule** on all six
  datasets. It does that with 3-10% more orders and about the same stock (−0.1 to +0.5 days).
- **The policy matters more than the forecaster.** The moving average and LightGBM tie inside
  this policy: each loses fewer units on three of the six datasets. LightGBM's better
  7-day-total accuracy (1.4 to 2.6 WAPE points) doesn't turn into fewer lost sales here. The gain comes
  from ordering against lead-time demand with a buffer sized to each product's noise, where
  the current rule uses a fixed threshold.
- **The buffer is the lever:** safety 1 instead of 0 cuts lost units by 40-70% at every cover
  level, for about one extra day of stock.
- There's no free lunch. Longer cover means fewer orders but more stock, and shorter cover means
  the reverse. A store chooses where to sit. The current rule sits at one point without
  saying so.

### What this does not show
- **Real stores.** Demand, delivery delays (1-3 days, uniform) and "never reorder while an
  order is on the way" are all assumptions.
- **The best fixed rule.** I didn't search for better reorder levels for the current rule. A
  higher fixed reorder level would also lose less, at the cost of more stock.
- **Money.** Orders, stock and lost sales aren't priced, so this doesn't say which point on
  the trade-off is best for a given store.
- **Order costs or minimum order sizes,** neither of which is modelled.

### Next
A forecast-based reorder suggestion in the app, starting with the moving average. It's as good
as LightGBM here and needs no model infrastructure. That needs lead times per supplier or
product, which the app doesn't record yet.

---

## 2026-11-22 — Same pipeline through the database (`feature/ml-real-data`)

### Why
Before trusting a forecast on a real store, check that a table built from the database
(sales, refunds, stock ledger, store time zone) means the same thing as the table the models
were developed on.

### Setup
1. `python -m tindawise_ml generate --end 2026-11-21`: synthetic history ending yesterday
   (2024-11-22 to 2026-11-21, seed 42).
2. `python -m scripts.seed_sample_history`: written into the sample store as 21,667 receipts,
   48,429 lines and 49,920 stock movements.
3. `python -m scripts.export_demand`: the table rebuilt from the database.
4. `python -m tindawise_ml backtest --csv export.csv` vs the same backtest on the generated table.

### Results
- **Identical tables:** 12,410 rows each, 0 differences in `units_sold`, 0 in `stockout`.
- **Identical backtest scores** on both. Test period 2026-08-30 to 2026-11-21 (a different
  window from the entries below, because this history ends later):

| model | daily WAPE | 7-day WAPE | bias |
|---|---|---|---|
| lightgbm | 50.8% | 21.0% | −3.5% |
| moving_average_28 | 51.4% | 22.1% | −4.3% |

  LightGBM is ahead again, by less than on the December test period. This window has no
  Christmas build-up for the moving average to lag behind.

### What this does not show
- Accuracy on a real store. The data that went in is still synthetic. This checks that the
  path from the database is faithful, not that the model is.

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
