# QC log

Produced by `sql/01_behaviour_features.sql`. Counts come from `outputs/qc_log.json`.

## Feature build

| Check | Result |
|---|---|
| Customers active at the current snapshot (4 May 2026) | 96,371 |
| Customers active at the prior snapshot (5 May 2025) | 90,669 |
| Active at both snapshots, used for the stability test | 71,259 |
| Category shares that do not add to 1, or are missing | 0 |
| Channel shares that do not add to 1, or are missing | 0 |
| Category unit counts that do not add up to the total | 0 |
| Missing value in any clustering input | 0 |
| Orders counted outside the twelve-month window | 0 |

A category a customer never bought from reads as a zero share, not a missing value. An early version of the SQL
returned nulls for those customers, which made the "shares add to 1" check pass without testing anything. Both the
feature and the check were fixed; the counts above come from the corrected version.

The customer and order tables are cleaned by the shared script from project 1
(`projects/01-churn-retention/sql/01_clean.sql`); its fixes are listed in that project's QC log.

## Modelling checks

| Check | Result |
|---|---|
| Spend, margin and recency excluded from the clustering inputs | Yes, by construction |
| Prior-snapshot features use only data before 5 May 2025 | Yes |
| Next-year purchases measured after the snapshot that assigned the persona | Yes, 5 May 2025 to 4 May 2026 |
| Campaigns used for the response test start after the personas were assigned | Yes, 13 campaigns in the following twelve months |
| Reruns give identical outputs | Yes: fixed seeds, fixed row order, single-threaded SQL |

## Data generator change made for this project

The generator previously drew each order line's category from a seasonal distribution shared by every customer, so
category mix carried no persistent customer-level signal and a needs-based segmentation could not exist. The
generator now gives every customer a latent shopper type with a strength, and category choice is seasonality times
that customer's affinity. The latent type is written to `data/full/truth/customer_truth.csv`, which is what makes
the accuracy check in the segmentation card possible.

This changed `order_items.csv` and therefore order totals and margins. Projects 1 and 2 were re-run on the new data
and their results, decks and documents were updated. Their conclusions did not change.

## Known gaps

- The SAS program has not been executed in this build.
- The pipeline needs the full data set. The 1% sample in the repository is too small for these models.
