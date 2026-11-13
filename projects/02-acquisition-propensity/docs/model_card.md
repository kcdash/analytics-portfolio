# Model card: acquisition propensity scorecard

| | |
|---|---|
| Purpose | Probability that a prospect joins the loyalty program within 45 days of first contact |
| Population | Prospects first contacted 1 January 2024 to 15 September 2026 |
| Algorithm | Logistic regression, no regularisation, 17 terms |
| Inputs | Lead source, age band, household income band, web visits in 30 days (capped at 8), distance to nearest store, children at home, email engagement |
| Training data | 89,433 prospects, January 2024 to September 2025, 8.2% converted |
| Test data | 49,937 prospects, October 2025 to mid-September 2026, 10.2% converted |
| Alternatives tested | Gradient boosting, look-alike index, web-visits rule |

## Performance on the test period

| Method | AUC | Top-decile lift | Top-decile conversion | Converters in top 30% | Share of achievable signal |
|---|---|---|---|---|---|
| Web visits only | 0.58 | 1.7x | 17.5% | 41% | 46% |
| Look-alike index | 0.68 | 2.2x | 22.7% | 53% | 97% |
| Gradient boosting | 0.68 | 2.3x | 23.7% | 52% | 97% |
| Propensity scorecard | 0.68 | 2.3x | 23.8% | 53% | 100% |

- The bottom score decile converts at 2.9%, about one eighth of the top decile.
- Brier score is 0.088.
- "Share of achievable signal" is (AUC - 0.5) divided by (ceiling AUC - 0.5). The ceiling, 0.685, is the AUC of the
  true conversion rule on the same prospects. Conversion is partly chance, so no model can score higher with these inputs.

## Checked against ground truth

- All 17 estimated effects lie within their 95% interval of the true effect built into the data.
- Correlation between the scorecard and the true log-odds is 0.997.
- Gradient boosting scores slightly lower than the scorecard. The true rule is additive, so the extra flexibility only adds noise.

## Calibration and drift

- Conversion rose from 8.2% in the training period to 10.2% in the test period.
- Before a baseline refresh the scorecard predicts 8.3% on the test period. After refreshing the intercept on the
  latest training quarter it predicts 9.3%, still 0.9 points low.
- Ranking is unaffected. The intercept should be refreshed every quarter.

## Business results

- New customer value: $412 mean first-year margin (median $255), measured on 7,456 converted prospects. 10% never ordered.
- At 40% of prospects contacted (about 20,800 a year), the scorecard list finds 3,368 customers against 2,121 for a
  random list: 1,247 more, worth about $514,000 in first-year margin. Outreach cost per customer falls from $59 to $37.
- The look-alike index finds 3,364 at the same budget.
- Break-even share of conversions that outreach must cause: 6% in the top decile, 51% in the bottom decile.

## Assumptions

- Outreach costs $6.00 per prospect.
- Cost per lead: web lead $8, partner list $5, event $15, referral $20, purchased list $2.
- "Extra customers" compares ranked and random lists of contacted prospects and assumes outreach is what converts them.

## Limitations

- **Synthetic data.** Results illustrate the method. They are not evidence about any real retailer.
- **Incrementality is unknown.** No outreach holdout exists, so the model predicts who converts, not who converts because of outreach.
- **First-year margin only.** Lifetime value would be higher.
- **One average customer value.** Top-third prospects become customers worth about 9% more than bottom-third prospects; this is not modelled.
- **Fairness.** Age band, income band and children at home are inputs. A real deployment should review whether
  using them to prioritise marketing outreach is appropriate and lawful in each province.

## Monitoring plan

- Quarterly: refresh the intercept; compare predicted and actual conversion by decile.
- Refit when top-decile lift falls below 2x or when a lead source is added or changes its mix.
- Keep a permanent outreach holdout once the first test has reported.
