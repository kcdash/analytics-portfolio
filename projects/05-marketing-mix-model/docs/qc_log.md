# QC log

Produced by `sql/01_mmm_base.sql`. Counts come from `outputs/qc_log.json`.

## Base table

| Check | Result |
|---|---|
| Weeks in the model | 156 |
| Weeks with an incomplete media row | 2 |
| Weeks with zero spend in any channel | 2 |
| Weeks with missing revenue | 0 |
| Weeks where the price index falls outside 0.5 to 1.0 | 0 |
| Total media spend in the window | $25,201,490 |
| Total sales in the window | $423,243,502 |

The two incomplete weeks are the Display rows planted as a data-quality defect in the generator. They are
interpolated from the surrounding weeks rather than read as zero: a zero would tell the model that Display was
switched off for a fortnight, inventing a natural experiment that never happened. That single decision moves
Display's estimated return materially, which is why it is recorded here rather than buried in the code.

The order and customer tables are cleaned by the shared script from project 1
(`projects/01-churn-retention/sql/01_clean.sql`); the weekly calendar comes from project 4.

## Modelling checks

| Check | Result |
|---|---|
| Contributions reconcile to fitted sales | Exact, by construction |
| Category revenue reconciles to the company total | Inherited from project 4: exact to the dollar |
| Every model input known before the week begins | Yes: spend plans and calendar only |
| Transforms chosen on out-of-time error, not fit | Yes, four expanding-window folds |
| Model refitted inside each validation fold | Yes |
| Identification tested from multiple starting points | Yes, four starts; the spread is reported in the deck |
| Collinearity measured per channel | Yes, against the base terms and against other channels |
| Reruns give identical outputs | Yes: fixed seeds, fixed row order, single-threaded SQL |

## Specification sensitivity

Channel returns were re-estimated with parts of the base removed, to show how much of each answer is a modelling
choice rather than a finding. Dropping the holiday flags inflates Paid Search and Email sharply; dropping the price
control moves every channel. The full table is in `outputs/mmm_fit.json` under `specification_sensitivity`.

## Known gaps

- The SAS program has not been executed in this build.
- The pipeline needs the full data set. The 1% sample in the repository has too little media variation to fit.
- The in-market tests are simulated from the data-generating process. On real data they are an input, not an output.
