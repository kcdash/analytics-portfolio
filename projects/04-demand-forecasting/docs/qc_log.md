# QC log

Produced by `sql/01_weekly_series.sql`. Counts come from `outputs/qc_log.json`.

## Series build

| Check | Result |
|---|---|
| Weeks in the series | 156 |
| Weeks with no media row, treated as zero spend | 0 |
| Order lines falling outside the 156 complete weeks | 0 |
| Series at company level | 1 |
| Series at category level | 8 |
| Series at store level | 60 |
| Series at store-by-category level | 480 |
| Series with a missing week | 0 |
| Weeks where category revenue does not reconcile to the company total (tolerance $1) | 0 |

The order and customer tables are cleaned by the shared script from project 1
(`projects/01-churn-retention/sql/01_clean.sql`); its fixes are listed in that project's QC log. The two media weeks
missing from the raw extract belong to the Display channel and were planted deliberately; they fall outside this
project's media aggregate and are reported above as zero-spend weeks.

## Backtest checks

| Check | Result |
|---|---|
| Every feature known before the forecast week begins | Yes: calendar and plan data only, no actuals from the forecast period |
| Models refitted at every origin | Yes, all ten |
| Test weeks never used in fitting | Yes, by construction of the rolling origin |
| Interval quantiles fitted and tested on different origins | Yes: first five fit, last five test |
| Store-level forecasts rescaled before being compared with category totals | Yes: store series exclude online demand |
| Reruns give identical outputs | Yes: fixed seeds, fixed row order, single-threaded SQL |

## Known gaps

- The SAS program has not been executed in this build.
- The pipeline needs the full data set. The 1% sample in the repository produces series too sparse to forecast.
- `work/calendar.csv`, referenced by the SAS program, is written by the Python build alongside `series.csv`.
