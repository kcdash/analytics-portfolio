# Model card: weekly demand forecast

| | |
|---|---|
| Purpose | Forecast weekly demand up to thirteen weeks ahead, with a range, to drive ordering |
| Levels | Company (1 series), category (8), store (60), store by category (480) |
| History | 156 complete Monday weeks, 6 November 2023 to 1 November 2026 |
| Target | Weekly revenue at line level. Store series count in-store sales only |
| Inputs | Trend, five annual Fourier harmonics, flyer weeks, holiday peak, back to school, planned media spend by channel |
| Backtest | Ten origins four weeks apart from week 104, each forecasting thirteen weeks; refitted at every origin |
| Evaluation window | 3 November 2025 to 5 October 2026 |

## Which method wins where

| Level | Method chosen | Error | Repeat last year | Skill |
|---|---|---|---|---|
| Company | Average of last year adjusted and the calendar regression | 2.2% | 13.7% | 84% |
| Category | Last year, reset to the last eight weeks | 3.7% | 13.7% | 73% |
| Store | Ridge on trend, seasonality and the trading calendar | 11.5% | 18.1% | 36% |
| Store by category | Ridge on trend and seasonality | 23.1% | 30.2% | 24% |

Error is the weighted absolute percentage error across the whole backtest. The boosted model was worst at every
level (7.0%, 9.0%, 14.3%, 26.7%): with 150 weekly observations per series there is nothing left for it to learn.

## What each input is worth

Company-level error as inputs are added to the same regression:

| Inputs | Company | Category | Store by category |
|---|---|---|---|
| Trend and seasonality | 3.5% | 5.8% | 23.1% |
| Plus the trading calendar | 3.1% | 5.4% | 23.1% |
| Plus the media plan | 3.0% | 5.6% | 23.8% |
| Plus a recent-level anchor | 3.0% | 5.7% | 24.4% |

Knowing when the flyer drops is worth an 11.6% cut in company-level error. Knowing how much is being spent on each
channel adds nothing beyond that, and makes thin series slightly worse.

## Horizon

Error at company level is 2.1% one week ahead and 1.4% thirteen weeks ahead. Accuracy does not decay with the
horizon because every driver in the model is known months in advance. A forecast that leans on recent demand is
poor at every horizon: repeating last week averages 11.8%.

## Prediction intervals

Empirical quantiles of actual divided by forecast, estimated on the first five origins and tested on the last five.

| Level | 80% range, as a share of the forecast | Weeks actually inside it |
|---|---|---|
| Company | 97% to 106% | 94% |
| Category | 95% to 107% | 80% |
| Store | 83% to 122% | 80% |
| Store by category | 68% to 149% | 81% |

Coverage is honest at every level and slightly conservative at company level.

## Hierarchy

Category-level error by how the number is produced: forecasting each category directly 3.6%, adding up store-level
forecasts 5.9%, splitting the company forecast by last year's shares 15.7%. Categories peak at different times of
year, so a single share flattens the seasonality. Forecast each level directly and reconcile the published figures.

## Ordering economics

Assumptions: 42% gross margin on a unit sold, 25% markdown to clear an overstock. The optimal service level is
therefore 42 / (42 + 25) = 63%.

| Ordering rule | Cost a year | Fill rate |
|---|---|---|
| Repeat last year, best quantile | $8.79M | 87.1% |
| Order to the forecast | $6.83M | 87.7% |
| Order to the 63% service level | $6.57M | 91.9% |

- Using the model rather than the benchmark is worth $2.22M a year.
- Ordering to the service level rather than to the forecast is worth a further $256,000 a year.
- Total cost of forecast uncertainty is $6.57M a year, or 7.4% of revenue at this level.
- Halving the remaining error would be worth $3.35M a year. That is the budget any further forecasting work has to earn.

## Limitations

- **Synthetic data.** Results illustrate the method and are not evidence about any real retailer.
- **The ordering model has no inventory.** Each week is independent, with no carryover, no lead time and no minimum
  order quantity. A real replenishment system would soften both shortfalls and markdowns, so these costs are an
  upper bound on what accuracy is worth.
- **No price or promotion response.** Demand is forecast as it occurred under the actual plan, not as a response to
  a changed one. The model cannot answer what happens if a promotion is moved.
- **Two seasonal cycles only.** Three years of history is thin for annual seasonality, which is part of why simple
  seasonal methods do so well at aggregate levels.
- **Store series exclude online demand**, so bottom-up totals need rescaling before they can be compared with
  category figures.

## Monitoring plan

- Weekly: error by level against the forecast issued thirteen weeks earlier.
- Quarterly: re-run the method comparison. The winner at each level can change as history accumulates.
- Watch interval coverage: if fewer than 70% of weeks fall inside the 80% range, refit the quantiles before
  touching the model.
