# QC log

Produced by `sql/01_clean.sql`. Counts come from `outputs/qc_log.json`.

## Issues found and fixed

| Check | Rows | Fix | Matches planted count |
|---|---|---|---|
| Duplicate customer rows | 800 | Kept one row per `customer_id` | Yes (800) |
| Province spelled out instead of coded | 2,061 | Recoded to two-letter codes | Yes (2,061) |
| Missing postal FSA | 6,059 | Left missing; not used as a model input | 6,096 planted rows; 37 were resolved by de-duplication |
| Duplicate order rows | 2,329 | Kept one row per `order_id` | Yes (2,329) |
| Order dates in DD/MM/YYYY | 46,521 | Parsed with a second date format | Yes (46,521) |
| Negative net amounts | 1,423 | Replaced with the total of the order lines | Yes (1,423) |
| Amounts 100x too large | 751 | Replaced with the total of the order lines | Yes (751) |

Dates that could not be parsed: 0. Orders without order lines: 0.

Two planted issues sit in tables this project does not use (loyalty tier codes and missing media weeks). They are
left for the QC agent and marketing mix projects.

## Row counts after cleaning

| Table | Rows |
|---|---|
| customers | 200,000 |
| orders | 2,328,684 |
| churn analytical base table | 629,233 |
| uplift analytical base table | 625,000 |

## Modelling checks

| Check | Result |
|---|---|
| Features use only data before the snapshot date | Enforced in every join in `sql/03_features.sql` |
| Test snapshot untouched by training and calibration | Yes: trained to Aug 2025, calibrated Nov 2025, tested May 2026 |
| Uplift test campaigns start after churn-model training labels end | Yes: labels end 1 Feb 2026, test campaigns start 9 Feb 2026 |
| Reruns give identical outputs | Yes: fixed seeds, fixed row order, single-threaded SQL |
| Treatment and holdout groups comparable | Holdouts were assigned at random, 10% per campaign |

## Known gaps

- The SAS program has not been executed in this build.
- The pipeline needs the full data set. The 1% sample in the repository is too small for these models.
