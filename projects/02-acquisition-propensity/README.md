# Project 2: Acquisition propensity and look-alike

**Question:** which prospects should Maple & Main prioritise, which leads should it buy, and should the outreach budget grow?

**Answer:** a 17-term scorecard finds 59% more new customers than a random list at the same budget (about 1,250 more
a year at 40% reach, worth roughly $514,000 in first-year margin). Whether to extend outreach to low-scoring
prospects depends on a number nobody has measured: how many conversions outreach actually causes.

- [Client deck](deck/) ([PDF](deck/deck.pdf))
- [Acquisition simulator and prospect scorer](demo/)
- [Analytics plan](docs/analytics_plan.md) · [Model card](docs/model_card.md) · [QC log](docs/qc_log.md)

## What makes this more than a propensity model

1. **It knows when to stop modelling.** The scorecard's AUC of 0.68 looks modest, but it equals the ceiling set by
   the true conversion rule. Gradient boosting does slightly worse. A better ranking needs new data, not a bigger model.
2. **The drivers are verified.** All 17 estimated effects fall within their margin of error of the true effects.
3. **Look-alike is tested against propensity.** A profile index built only from converters captures 97% of the
   achievable signal, so a ranked list is possible even without non-converter records.
4. **It separates measured from assumed.** Customer value is measured from orders. Costs are stated assumptions.
   Incrementality is flagged as unknown, with the break-even worked out for each score decile.
5. **It ends with an experiment.** The deck includes the holdout design (10% for two quarters) needed to settle the budget question.

## Results

| | |
|---|---|
| Prospects scored in the test year | 49,937 |
| Conversion, top decile against bottom decile | 23.8% against 2.9% |
| Scorecard AUC, later period | 0.68 (ceiling 0.68) |
| First-year margin per new customer | $412 |
| Extra customers at 40% reach | 1,247 a year |
| Break-even incrementality, bottom decile | 51% |

## Run it

```
pip install -r requirements.txt
python data/generate_maple_main.py                    # full data
cd projects/02-acquisition-propensity/python
python 01_build_base.py            # SQL: prospect base, customer value, QC
python 02_train_models.py          # scorecard, boosting, look-alike, ground-truth checks
python 03_economics.py             # budget scenarios, incrementality, lead sources, test design
python 04_build_report_data.py     # numbers for the deck and simulator
```

Outputs are identical on every run with the same package versions.

## Layout

| Folder | Contents |
|---|---|
| `sql/` | Prospect base table with QC checks, first-year customer value (DuckDB SQL) |
| `python/` | Pipeline scripts |
| `sas/` | Logistic scorecard in SAS (not executed in this build) |
| `docs/` | Analytics plan, model card, QC log |
| `outputs/` | Metrics as JSON and the data file behind the deck and simulator |
| `deck/` | Client deck, HTML and PDF |
| `demo/` | Interactive simulator and prospect scorer |

## Disclaimer

Personal demonstration portfolio. All projects use synthetic data created to illustrate methods and contain no client,
employer or proprietary information. Not affiliated with or endorsed by any current or former employer or client.
