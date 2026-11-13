# Project 4: Demand forecasting

**Question:** how accurate is a weekly demand forecast at the levels Maple & Main plans on, and what is better
accuracy actually worth?

**Answer:** accuracy is a property of the level, not the model: 2.2% error at company level and 23.1% at store and
category level. Forecasting properly rather than repeating last year saves $2.2M a year in markdown and lost
margin, and ordering to the right service level instead of to the forecast adds another $256,000.

- [Client deck](deck/) ([PDF](deck/deck.pdf))
- [Forecast explorer](demo/) — the forecast against what happened, and an ordering rule you can set yourself
- [Analytics plan](docs/analytics_plan.md) · [Model card](docs/model_card.md) · [QC log](docs/qc_log.md)

## What makes this more than a forecasting exercise

1. **Benchmarks come first, and sometimes they win.** At company and category level, last year's shape reset to the
   recent level beats every model tested. The project says so instead of burying it.
2. **Four levels, not one number.** Error roughly doubles at each step down the hierarchy, and the best method
   changes with it. A forecasting system is a portfolio of methods, not a model.
3. **Each input is priced.** Knowing the trading calendar cuts company error by 11.6%. Knowing media spend by
   channel adds nothing, and hurts thin series.
4. **Ranges, tested out of sample.** Intervals are fitted on the first five origins and checked on the last five;
   80% bands cover 80% to 94% of weeks depending on the level.
5. **The forecast ends in a decision.** Error is converted to markdown and lost margin, which shows that ordering to
   the forecast is a $256,000 mistake and that halving the remaining error would be worth $3.35M a year.

## Results

| | |
|---|---|
| Weekly series forecast | 549 across four levels |
| Backtest | 10 origins, 13 weeks ahead, Nov 2025 to Oct 2026 |
| Error, company level | 2.2% (benchmark 13.7%) |
| Error, store by category | 23.1% (benchmark 30.2%) |
| Cost of forecast uncertainty | $6.6M a year, 7.4% of revenue at store level |
| Value of the model over the benchmark | $2.2M a year |
| Value of ordering to the service level | $256,000 a year |

## Run it

```
pip install -r requirements.txt
python data/generate_maple_main.py                     # full data
cd projects/04-demand-forecasting/python
python 01_build_series.py              # SQL: weekly series at four levels, calendar and media
python 02_backtest.py                  # rolling-origin backtest, six methods, feature ablation
python 03_intervals_and_ordering.py    # prediction intervals, reconciliation, newsvendor economics
python 04_build_report_data.py         # numbers for the deck and explorer
```

Outputs are identical on every run with the same package versions.

## Layout

| Folder | Contents |
|---|---|
| `sql/` | Weekly series at four levels, trading calendar and media plan (DuckDB SQL) |
| `python/` | Pipeline scripts and the feature builder |
| `sas/` | Rolling-origin backtest in SAS (not executed in this build) |
| `docs/` | Analytics plan, model card, QC log |
| `outputs/` | Metrics as JSON and the data file behind the deck and explorer |
| `deck/` | Client deck, HTML and PDF |
| `demo/` | Interactive forecast explorer |

## Disclaimer

Personal demonstration portfolio. All projects use synthetic data created to illustrate methods and contain no client,
employer or proprietary information. Not affiliated with or endorsed by any current or former employer or client.
