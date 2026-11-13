# Analytics plan: churn and retention value

**Client:** Maple & Main (fictional Canadian omnichannel retailer)
**Prepared by:** Krish Dash
**Status:** delivered

## 1. Business question

Maple & Main sends about 25,000 retention offers in each of 13 CRM campaigns a year. Marketing wants to know three
things: which active customers are about to stop buying, how much margin is at stake, and who should receive an offer
so the program makes the most money.

## 2. Decisions this work supports

| Decision | Owner | What the analysis provides |
|---|---|---|
| Who goes on the monthly offer list | CRM manager | A ranked audience and a do-not-contact rule |
| How big the retention budget should be | VP Marketing | Net profit by audience size, in CAD |
| Where to invest beyond offers | Customer experience lead | The drivers of churn that offers do not fix |

## 3. Hypotheses

1. Churn can be predicted from behaviour well before a customer goes silent.
2. Customers at highest risk are not the customers most worth contacting.
3. Offers produce incremental orders but may not change longer-term retention.
4. Ranking by expected net value beats ranking by risk at the same budget.

## 4. Approach

| Step | Method | Output |
|---|---|---|
| Data preparation | SQL: de-duplicate, standardise dates and provinces, rebuild order amounts from order lines | Clean tables and a QC log |
| Churn definition | Test inactivity windows of 60 to 240 days against the true churn dates | 180-day definition with known error rates |
| Feature build | SQL, point-in-time: only data dated before each snapshot | 33 features per customer per snapshot |
| Churn model | Recency rule and logistic scorecard as benchmarks, gradient boosting as champion, isotonic calibration | Calibrated churn probability |
| Validation | Train on Nov 2024 to Aug 2025 snapshots, calibrate on Nov 2025, test once on May 2026 | AUC, lift, calibration, stability |
| Uplift model | Trained on randomised campaign holdouts from Nov 2024 to Jan 2026 | Predicted change in response if contacted |
| Back-test | Replay four targeting rules on nine campaigns from Feb to Oct 2026 | Measured uplift and net profit per rule |
| Business case | Incremental margin less offer cost less contact cost | Annual CAD impact with intervals |

## 5. Success criteria

- Churn model: top-decile lift of at least 3x on the out-of-time test, and calibration within three points per score band.
- Uplift model: predicted uplift deciles ordered the same way as measured uplift in held-out campaigns.
- Business case: a targeting rule that beats current practice by more than the sampling error.

## 6. Risks and how they are handled

| Risk | Mitigation |
|---|---|
| Leakage from future data | Every feature is filtered to dates before the snapshot; the test snapshot is used once |
| Churn label is noisy with no contracts | Label accuracy is measured against ground truth and reported |
| Uplift estimates are noisy | All strategy results come from measured holdout differences, with 95% intervals |
| Offer cost is not recorded | Stated as an assumption and adjustable in the simulator |
| Results look better than real life | Data is synthetic; this is disclosed on every deliverable |

## 7. Deliverables

Client deck (HTML and PDF), interactive retention simulator, SQL, Python and SAS code, model card, QC log.
