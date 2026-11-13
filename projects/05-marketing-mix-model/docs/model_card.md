# Model card: marketing mix model

| | |
|---|---|
| Purpose | Attribute weekly sales to media and the base business, and set the media budget split |
| Data | 156 weeks, 6 November 2023 to 26 October 2026; $25.2M of media against $423M of sales |
| Form | Sales = base x (1 + sum of channel lifts). Base is log-linear; each channel lift is a Hill saturation of geometrically adstocked spend |
| Channels | TV, Paid Search, Paid Social, Display, Flyer, Email |
| Base controls | Trend, three annual Fourier harmonics, holiday peak, back-to-school, realised price against list |
| Estimation | Alternating least squares: base by regression, channel effects by non-negative least squares |
| Transforms | Carry-over (9 values), saturation shape (5), half-saturation (7), searched per channel by coordinate descent on four expanding-window folds |
| Prior | Contribution split pulled gently toward spend split, which prevents the fit collapsing onto one channel |

## Fit

| | |
|---|---|
| R-squared | 0.937 |
| Out-of-time error, four folds | 3.5% |
| Durbin-Watson | 1.56 |
| Contribution reconciliation | Exact by construction |

## The identification problem

The same data, transforms and controls, fitted from four different starting points:

| Starting assumption | Media contribution | R-squared |
|---|---|---|
| No media to begin with | $65M | 0.940 |
| A modest effect, split like spend | $81M | 0.939 |
| A large effect, split like spend | $159M | 0.930 |
| Every channel equal | $99M | 0.938 |

Less than one point of R-squared separates answers that differ by 2.4 times. The true figure is $47M, or 11.1% of sales.

Why: media is planned around the trading calendar the model already controls for. The share of each channel's
pattern reproducible from the base terms alone is Flyer 95%, Paid Social 51%, Paid Search 46%, Display 24%,
Email 23%, TV 20%. TV runs in flights that cut across the season, which is why it is the best-measured channel.

## Accuracy against the truth

The synthetic data was generated from known response curves, so every estimate can be scored.

| Version | Average error in channel return | Error in total media contribution |
|---|---|---|
| Model alone | 109% | +72% |
| Plus 1 single-depth test | 82% | +51% |
| Plus 2 single-depth tests | 75% | +50% |
| Plus 4 single-depth tests | 58% | +41% |
| Plus 5 single-depth tests | 7% | +7% |
| Plus two-depth tests on every channel | 7% | +6% |

Final model returns against the truth: TV $1.90 against $1.78, Paid Search $1.76 against $1.74, Paid Social $1.60
against $1.45, Display $0.96 against $0.97, Flyer $2.75 against $2.37, Email $7.01 against $7.20.

## Levels are not shapes

A single holdout measures what a channel is worth at today's spend. It says nothing about what happens if the spend
moves, and reallocation depends entirely on that. Weekly spend at which each channel reaches half its maximum effect:

| Channel | Model alone | With two-depth tests | Truth | Today's spend |
|---|---|---|---|---|
| TV | $98k | $24k | $41k | $43k |
| Paid Search | $69k | $20k | $37k | $40k |
| Paid Social | $31k | $18k | $30k | $32k |
| Display | $7k | $9k | $17k | $18k |
| Flyer | $14k | $16k | $20k | $24k |
| Email | $4k | $2k | $4k | $5k |

## The optimiser, judged on the true curves

Reallocating the same $8.4M budget, with each channel free to move by half its current spend:

| Plan | Promised gain | Actual gain | Share of what was available |
|---|---|---|---|
| Model alone, no test | $5,901k | -$258k | -41% |
| Plus two single-depth tests | $4,375k | -$436k | -69% |
| Plus five single-depth tests | $2,837k | -$441k | -70% |
| Plus two-depth tests on every channel | $588k | $523k | 83% |
| Best possible, knowing the true curves | n/a | $630k | 100% |

Acting on an uncalibrated mix model is worse than doing nothing. Calibrating the levels is not enough; the curve
shape has to be measured too.

## Recommended plan

TV +1%, Paid Search -13%, Paid Social -7%, Display -38%, Flyer +48%, Email +48%, on an unchanged total.
Every channel already sits between 59% and 67% of its maximum effect, so the gain is a 3.2% improvement in
media-driven sales, not a step change.

## Assumptions

- Gross margin on incremental sales is 42%.
- The optimiser assumes steady weekly spend and ignores flighting, minimum buys and contractual commitments.
- Holdouts are simulated from the true response curves with the sampling error a 13-week geo test would carry. In a
  real engagement these numbers are read off the test.

## Limitations

- **Synthetic data.** Results illustrate the method and are not evidence about any real retailer.
- **No competitor activity, distribution change or creative quality**, none of which exist in this dataset either.
  On real data these are first-order omissions.
- **Price is controlled, not modelled.** The model cannot answer what happens if prices change.
- **National weekly data.** No geographic variation, which is exactly what makes experiments necessary here.
- **No channel interactions** and no brand effect beyond the carry-over window.
- **The model answers the mix question, not the scale question.** On immediate gross margin the budget returns
  $0.83 per dollar, so the case for its size rests on customer lifetime value, which the acquisition and retention
  models in this portfolio carry.

## Monitoring plan

- Every quarter: refit, and re-run the multi-start identification test before publishing any number.
- Every reallocation: hold back a region or a set of weeks so the move itself is measured.
- Rolling test programme: two-depth holdouts on each channel in turn, starting with the ones the calendar hides.
- Retire a calibration after a year; response curves move with creative, competition and channel maturity.
