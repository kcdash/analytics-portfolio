# Project 5: Marketing mix model and budget optimiser

**Question:** what do Maple & Main's six media channels produce, and where should the next dollar go?

**Answer:** the model fits well and, on its own, cannot be trusted. Four equally good versions of it put media's
contribution anywhere between $65M and $159M. Acting on the uncalibrated model would have lost $258k a year. With
in-market tests that measure the shape of each response curve, the same optimiser captures 83% of the gain that was
actually available: $523k a year on an unchanged $8.4M budget.

- [Client deck](deck/) ([PDF](deck/deck.pdf))
- [Budget planner](demo/) — move the budget, and switch between the calibrated and uncalibrated model
- [Analytics plan](docs/analytics_plan.md) · [Model card](docs/model_card.md) · [QC log](docs/qc_log.md)

## What makes this more than a mix model

1. **It is built properly first.** Carry-over and saturation searched per channel on out-of-time error; a structural
   form where contributions add to sales exactly; positive effects only; four expanding-window validation folds.
2. **Then it is broken on purpose.** Refitting from four honest starting points gives answers that differ by 2.4
   times with less than one point of R-squared between them. That spread is the real uncertainty and no standard
   error reports it.
3. **The cause is diagnosed, not hand-waved.** 95% of the flyer variable is reproducible from the trading calendar
   alone. The model itself names the channels that need an experiment.
4. **Experiments are priced.** Each in-market test is added in turn and the error measured: 109% average error in
   channel returns with no tests, 7% with five.
5. **The crucial distinction is proved.** Tests at one spend depth fix how much a channel is worth but not the shape
   of its curve, and reallocation depends on shape. The optimiser still loses money after five single-depth tests,
   and captures 83% of the achievable gain after two-depth tests.
6. **Every recommendation is scored against the truth.** The synthetic data has known response curves, so each plan
   is judged on what it would really have earned, not on what the model promised.

## Results

| | |
|---|---|
| Weeks modelled | 156 ($25.2M media, $423M sales) |
| Fit | R-squared 0.937, out-of-time error 3.5% |
| Range of answers the data permits | $65M to $159M of media contribution |
| Average error in channel return, model alone | 109% |
| Average error after two-depth tests | 7% |
| Recommended reallocation | $523k a year, 83% of what was available |
| Media's return on immediate gross margin | $0.83 per dollar |

## Run it

```
pip install -r requirements.txt
python data/generate_maple_main.py                     # full data
cd projects/05-marketing-mix-model/python
python 01_build_base.py                 # SQL: weekly sales, media, calendar and price controls
python 02_fit_mmm.py                    # transforms, structural fit, identification test, calibration
python 03_validate_and_optimise.py      # truth scoring, curve recovery, optimiser, budget scenarios
python 04_build_report_data.py          # numbers for the deck and planner
```

Outputs are identical on every run with the same package versions.

## Layout

| Folder | Contents |
|---|---|
| `sql/` | Weekly sales, media by channel, price and promotion controls (DuckDB SQL) |
| `python/` | Pipeline scripts, the transform library and the simulated experiment |
| `sas/` | Adstock, saturation and a constrained mix model with PROC NLIN (not executed in this build) |
| `docs/` | Analytics plan, model card, QC log |
| `outputs/` | Metrics as JSON and the data file behind the deck and planner |
| `deck/` | Client deck, HTML and PDF |
| `demo/` | Interactive budget planner |

## Disclaimer

Personal demonstration portfolio. All projects use synthetic data created to illustrate methods and contain no client,
employer or proprietary information. Not affiliated with or endorsed by any current or former employer or client.
