# QC log

Produced by `sql/01_kpi_mart.sql`. Counts come from `outputs/qc_log.json`.

## Mart

| Check | Result |
|---|---|
| Weeks in the mart | 156 |
| Weeks with missing revenue | 0 |
| Weeks with no media figure | 0 |
| Weeks with no service contacts recorded | 0 |
| Slice revenue that does not reconcile to the company total (tolerance $1) | 0 |
| Customers counted as new more than once | 0 |
| Members who joined before the window, excluded from new customers | 110,301 |
| New customers inside the window | 89,699 |
| Orders counted in more than one week | 0 |

The order and customer tables are cleaned by the shared script from project 1
(`projects/01-churn-retention/sql/01_clean.sql`); the weekly calendar comes from project 4.

## Method checks

| Check | Result |
|---|---|
| Baselines fitted only on weeks before the one being judged | Yes, refitted for every metric and every week |
| Metrics judged only after 52 weeks of history | Yes |
| Control rules applied identically to company metrics and slices | Yes |
| Period comparisons use the variation of both periods | Yes |
| Decomposition parts add to the total change | Yes, log decomposition rescaled to the arithmetic total |
| Reruns give identical outputs | Yes: fixed seeds, fixed row order, single-threaded SQL |

## What the audit found

Across 10 metrics and 104 judged weeks each (1,040 metric-weeks):

- 786 metric-weeks moved more than 2% against the previous week.
- 112 broke one of the three control rules.
- A "highlight anything over 2%" rule would therefore raise about seven times as many flags as the data supports.

Signals are not spread evenly. Service contacts accounts for 51 of the 112 and realised price for 19; both are
genuinely drifting. Revenue, gross margin and digital share behave as they always do.

## Known gaps

- The SAS program has not been executed in this build; it requires SAS/QC for `PROC SHEWHART`.
- The pipeline needs the full data set. The 1% sample has too few weekly orders for a stable baseline.
- The dashboard reads a static file produced by the pipeline. A production build would point the same calculations
  at a warehouse view and schedule them weekly.
