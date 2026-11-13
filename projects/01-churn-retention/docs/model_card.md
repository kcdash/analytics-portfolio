# Model card: churn and uplift models

## Churn model

| | |
|---|---|
| Purpose | Probability that an active customer places no order in the next 180 days |
| Population | Joined at least 30 days before the snapshot and ordered in the prior 180 days |
| Algorithm | Gradient boosting (scikit-learn `HistGradientBoostingClassifier`), isotonic calibration |
| Benchmarks | Recency rule; logistic scorecard (also provided in SAS) |
| Inputs | 33 point-in-time features: purchases, web activity, service contacts, CRM history, profile |
| Training data | 409,773 customer-snapshots, four snapshots from Nov 2024 to Aug 2025 |
| Calibration data | 105,452 customers, Nov 2025 snapshot |
| Test data | 112,946 customers, May 2026 snapshot, used once |

### Performance on the May 2026 test snapshot

| Model | AUC | PR-AUC | Top-decile lift | Churners in top 20% |
|---|---|---|---|---|
| Recency rule | 0.69 | 0.32 | 2.4x | 41% |
| Logistic scorecard | 0.81 | 0.50 | 3.3x | 52% |
| Gradient boosting, calibrated | 0.83 | 0.55 | 3.6x | 55% |

- Churn rate in the test snapshot is 16.9%.
- Brier score is 0.106. Predicted and actual churn rates differ by at most 2.6 points across 20 score bands.
- Population stability index between training and test scores is 0.004.

### Checked against ground truth

The synthetic data carries each customer's true churn date, which a real project would not have.

- 58% of customers labelled as churned by the 180-day rule had truly left; 42% were between purchases.
- The 180-day rule catches 67% of customers who truly left in the window.
- Scored against true churn, the model's AUC is 0.78 (logistic 0.76, recency rule 0.68).
- The logistic coefficients have the same signs as the mechanism that generated the data: paid-social acquisition,
  complaints and unresolved issues raise risk; higher tiers and web activity lower it.

### Top drivers

Web sessions in the last three months, loyalty tier, days since last order, share of orders online, orders in the
last 12 months.

## Uplift model

| | |
|---|---|
| Purpose | Change in the chance of ordering within 14 days if the customer is sent an offer |
| Design | Single gradient-boosting model with the treatment flag, channel and offer as inputs |
| Selection | Chosen over a two-model design on the last training campaigns (Qini 0.0040 against 0.0038) |
| Training data | 400,000 contacts in 16 campaigns, Nov 2024 to Jan 2026, each with a 10% random holdout |
| Test data | 225,000 contacts in 9 campaigns, Feb to Oct 2026 |

- Measured uplift falls from 4.8 points in the top predicted decile to 0.5 points in the bottom decile.
- Qini on the test campaigns is 0.0038, against 0.0008 when ranking by churn risk.
- Correlation between predicted uplift and the true uplift built into the data is 0.54. Churn risk has a correlation
  of -0.02 with true uplift.

## Business results (nine test campaigns, scaled to a year)

| Audience rule, 25,000 contacts per campaign | Net profit a year | 95% interval |
|---|---|---|
| Random draw (current practice) | $339,000 | ±$87,000 |
| Highest churn risk | $374,000 | ±$103,000 |
| Highest value at risk (risk x 12-month margin) | $555,000 | ±$111,000 |
| Highest net uplift value | $544,000 | ±$123,000 |

- The lowest-risk decile loses $3.46 per contact, about $112,000 a year at current volumes.
- Offers show no effect on activity in the following six months: 87.3% treated against 87.3% holdout
  (difference 0.04 points, ±0.32).

## Assumptions

- Offer cost is not recorded in the data. It is assumed as a share of the responder's basket: 10% off 10%, 5x bonus
  points 4%, $15 off $75 12%, free shipping 5%, win-back 20% off 20%. It applies to every treated responder.
- The annual figures assume 13 campaigns of 25,000 contacts, selected from the eligible base (about 84,000 for email,
  39,000 for SMS, 113,000 for direct mail).

## Limitations

- **Synthetic data.** Results illustrate the method. They are not evidence about any real retailer.
- **Loyalty tier is not point-in-time.** The customer table holds the current tier. A production build should use tier history.
- **Contact fatigue is not modelled.** Selecting the same top customers every month may reduce response.
- **Intervals cover holdout sampling only**, not model or assumption uncertainty.
- **Overlapping training rows.** The same customer appears in several snapshots, so training rows are not independent.
- **Fairness.** Age band and province are model inputs. They carry little weight here, but a real deployment should
  review whether using them for offer eligibility is appropriate.

## Monitoring plan

- Monthly: score distribution stability (PSI above 0.1 triggers a review), churn rate by decile once labels mature.
- Every campaign: keep the 10% holdout and track measured uplift by predicted-uplift decile.
- Retrain when top-decile lift falls below 3x or the uplift deciles stop ordering correctly.
