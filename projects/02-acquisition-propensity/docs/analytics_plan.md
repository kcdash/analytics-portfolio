# Analytics plan: acquisition propensity and look-alike

**Client:** Maple & Main (fictional Canadian omnichannel retailer)
**Prepared by:** Krish Dash
**Status:** delivered

## 1. Business question

Maple & Main collects about 52,000 prospects a year from five lead sources. Roughly one in ten joins the loyalty
program within 45 days. Marketing wants to know which prospects to prioritise, which lead sources to buy, and
whether the outreach budget should grow.

## 2. Decisions this work supports

| Decision | Owner | What the analysis provides |
|---|---|---|
| Order of the outreach list | Acquisition manager | A scorecard that ranks every prospect |
| Which leads to buy | Media and partnerships lead | Conversion and cost per customer by source and profile |
| Size of the outreach budget | VP Marketing | Return at each budget level, and the test needed to trust it |

## 3. Hypotheses

1. A small number of profile and behaviour signals separate likely converters from the rest.
2. A simple scorecard will perform as well as a complex model on this data.
3. A look-alike index built only from converters can stand in when non-converter records are missing.
4. Profile matters more than lead source.
5. The return on outreach depends on how many conversions outreach causes, which has not been measured.

## 4. Approach

| Step | Method | Output |
|---|---|---|
| Data preparation | SQL: trim prospects whose 45-day conversion window is not fully observed; integrity checks against the customer file | Prospect base table and QC log |
| Customer value | SQL: first-year margin for converted prospects with a full year of orders | Value per new customer |
| Propensity models | Logistic scorecard, gradient boosting, look-alike index, single-rule benchmark | Ranked prospects |
| Validation | Train on January 2024 to September 2025, test on October 2025 to September 2026 | AUC, lift, calibration |
| Ground truth | Compare estimated effects and AUC with the conversion rule built into the data | Share of achievable signal captured |
| Business case | Customers found at each budget, ranked against random | Extra customers and first-year margin |
| Sensitivity | Break-even share of conversions caused by outreach, by score decile | Which contacts are safe and which are unproven |
| Test design | Power calculation for an outreach holdout | Holdout size and duration |

## 5. Success criteria

- Top score decile converts at least twice the average rate on the later period.
- The scorecard is within a point of AUC of the best model, so it can be deployed as a formula.
- The business case separates what is measured from what is assumed.

## 6. Risks and how they are handled

| Risk | Mitigation |
|---|---|
| Recent prospects look like non-converters because they have not had time | Last 45 days excluded |
| Conversion rate drifts over time | Out-of-time test; baseline refreshed on the latest training quarter |
| Conversions credited to outreach that would have happened anyway | Stated as unknown; break-even analysis and a holdout test design |
| Costs are not in the data | Stated as assumptions and adjustable in the simulator |
| Results look better than real life | Data is synthetic; disclosed on every deliverable |

## 7. Deliverables

Client deck (HTML and PDF), interactive simulator with a prospect scorer, SQL, Python and SAS code, model card, QC log.
