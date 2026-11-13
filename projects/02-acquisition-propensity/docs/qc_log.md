# QC log

Produced by `sql/01_prospect_base.sql`. Counts come from `outputs/qc_log.json`.

## Prospect file

| Check | Rows | Action |
|---|---|---|
| Prospects in raw file | 150,000 | |
| Duplicate `prospect_id` | 0 | |
| First contact before 1 January 2024 | 8,138 | Dropped. The customer file starts in November 2023, so the earliest prospects are over-represented by converters |
| First contact after 15 September 2026 | 2,492 | Dropped. Their 45-day conversion window was still open when the data ends |
| Kept for modelling | 139,370 | |
| Missing value in any model input | 0 | |
| Distance below 0 or above 150 km | 0 | |
| Converted flag without a customer id | 0 | |
| Customer id without a converted flag | 0 | |
| Converted customer id not found in the customer file | 0 | |
| Converted before first contact | 0 | |
| Converted more than 45 days after first contact | 0 | |

The customer and order tables are cleaned by the shared script from project 1
(`projects/01-churn-retention/sql/01_clean.sql`); its fixes are listed in that project's QC log.

## Modelling checks

| Check | Result |
|---|---|
| Test period is later than the training period | Yes: split at 1 October 2025 |
| Customer value uses a full year of orders | Yes: only customers who joined by 1 November 2025 |
| Web visits capped at 8 | Yes: fewer than 0.1% of prospects have more |
| Reruns give identical outputs | Yes: fixed seeds and single-threaded SQL |

## Data generator change made for this project

Converted prospects previously had their age band overwritten with the linked customer's age band, which erased the
age effect on conversion. The generator now keeps the prospect's own age band. Only `prospects.csv` changed; every
other table is identical, so project 1 results are unaffected.

## Known gaps

- The SAS program has not been executed in this build.
- The pipeline needs the full data set. The 1% sample in the repository is too small for these models.
