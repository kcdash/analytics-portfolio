# Project 1: Churn and retention value

**Question:** which Maple & Main customers are about to stop buying, and who is worth sending a retention offer?

**Answer:** the churn model works, but churn risk is the wrong way to pick an offer audience. Ranking the same
25,000 contacts per campaign by value at risk or uplift raises CRM profit from about $339,000 to about $545,000 a
year. The most loyal 10% of customers should not receive offers at all.

- [Client deck](deck/) ([PDF](deck/deck.pdf))
- [Retention simulator](demo/)
- [Analytics plan](docs/analytics_plan.md) · [Model card](docs/model_card.md) · [QC log](docs/qc_log.md)

## What makes this more than a churn model

1. **The churn definition is tested, not assumed.** Five inactivity windows are scored against the true churn dates.
   The 180-day rule is wrong about 42% of the customers it flags.
2. **The model is tested on a later period.** Trained to August 2025, tested once on May 2026: AUC 0.83, top-decile lift 3.6x.
3. **Offers are judged by experiment.** Every campaign kept a 10% holdout, so the analysis measures what an offer
   changes. The highest-risk customers respond at half the rate of mid-risk customers, and the lowest-risk customers
   lose $3.46 per contact.
4. **The business case counts costs.** Net profit is incremental margin less the discount given to every responder
   less contact cost, with 95% intervals.
5. **It reports what did not work.** Offers show no effect on six-month retention, and a simple risk-times-value
   ranking does as well as the uplift model.

## Results

| | |
|---|---|
| Active customers scored (May 2026) | 112,946 |
| 12-month margin at risk | $5.2M of $59.4M |
| Churn model AUC, out of time | 0.83 (recency rule 0.69) |
| Top-decile lift | 3.6x |
| Profit, random audience | $339,000 a year |
| Profit, value-at-risk or uplift audience | $544,000 to $555,000 a year |

## Run it

```
pip install -r requirements.txt
python data/generate_maple_main.py                                   # full data, about 400 MB
cd projects/01-churn-retention/python
python 01_build_features.py        # SQL: clean, spine, features
python 02_train_churn_model.py     # churn model and validation
python 03_uplift_and_value.py      # uplift model, back-test, business case
python 04_build_report_data.py     # numbers for the deck and simulator
```

Takes a few minutes. Outputs are identical on every run with the same package versions.

## Layout

| Folder | Contents |
|---|---|
| `sql/` | Cleaning, scoring spine and point-in-time features (DuckDB SQL) |
| `python/` | Pipeline scripts |
| `sas/` | Logistic scorecard in SAS (not executed in this build) |
| `docs/` | Analytics plan, model card, QC log |
| `outputs/` | Metrics as JSON and the data file behind the deck and simulator |
| `deck/` | Client deck, HTML and PDF |
| `demo/` | Interactive retention simulator |

## Disclaimer

Personal demonstration portfolio. All projects use synthetic data created to illustrate methods and contain no client,
employer or proprietary information. Not affiliated with or endorsed by any current or former employer or client.
