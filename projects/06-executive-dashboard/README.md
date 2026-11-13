# Project 6: Executive KPI dashboard

**Question:** can a weekly KPI page tell an executive team what to care about, instead of showing them everything?

**Answer:** yes, by putting a seasonal baseline behind every metric and only speaking when a movement leaves it.
Of 786 weekly movements a conventional dashboard would highlight, 112 are outside normal variation. This week's page
raises 9 items, ranked and written as sentences, one of which exists purely to take something off the agenda.

- [Open the dashboard](demo/) — the deliverable
- [Design notes deck](deck/) ([PDF](deck/deck.pdf))
- [Analytics plan](docs/analytics_plan.md) · [Metric dictionary](docs/metric_dictionary.md) · [QC log](docs/qc_log.md)

## What makes this more than a KPI page

1. **Every number is tested before it is shown.** For each metric and each week, a baseline is fitted on earlier
   weeks only, and three control rules decide whether the page speaks up. Nothing is judged against a baseline that
   has already seen it.
2. **The noise is quantified.** 786 movements over 2% against 112 real signals, so a conventional threshold rule
   would raise seven times as many flags as the data supports.
3. **It takes items off the agenda.** Outdoor and garden revenue is down 45% on the quarter and sits 0.1 standard
   deviations from its seasonal norm. The page says so explicitly, in green.
4. **It answers the first follow-up question before it is asked.** Revenue is decomposed into customers, visit
   frequency and basket: the year's 15.6% growth is almost entirely more customers, while the last quarter is flat
   because a 3.8% rise in customers was cancelled by a 5.0% fall in basket.
5. **Every metric has an owner and a decision.** A measure that supports no decision is not on the page.
6. **The other five projects report here.** Churn risk, acquisition value, persona coverage, forecast accuracy and
   media return each appear with the action they imply, so the page says what is about to happen as well as what has.

## Results

| | |
|---|---|
| Weeks in the mart | 156, to 26 October 2026 |
| Metrics, each with an owner and a decision | 10 |
| Slices, reconciling to the company total | 8 categories, 3 channels, 11 regions |
| Metric-weeks judged | 1,040 |
| Movements over 2% a conventional page would flag | 786 |
| Weeks actually outside normal variation | 112 (10.8%) |
| Items on this week's agenda | 9, of which 5 need a decision |

## Run it

```
pip install -r requirements.txt
python data/generate_maple_main.py                  # full data
cd projects/06-executive-dashboard/python
python 01_build_mart.py             # SQL: the weekly KPI mart and its slices
python 02_signals.py                # baselines, control limits, run rules, decomposition
python 03_alerts_and_models.py      # the ranked alert list and the five-model panel
python 04_build_report_data.py      # numbers for the dashboard and the deck
```

Outputs are identical on every run with the same package versions.

## Layout

| Folder | Contents |
|---|---|
| `sql/` | The weekly KPI mart, every measure defined once (DuckDB SQL) |
| `python/` | Baselines, control rules, decomposition, alert engine, model panel |
| `sas/` | Seasonal baselines and control charts with PROC SHEWHART (not executed in this build) |
| `docs/` | Analytics plan, metric dictionary, QC log |
| `outputs/` | Metrics as JSON and the data file behind the dashboard |
| `deck/` | Design notes, HTML and PDF |
| `demo/` | **The dashboard itself** |

## Disclaimer

Personal demonstration portfolio. All projects use synthetic data created to illustrate methods and contain no client,
employer or proprietary information. Not affiliated with or endorsed by any current or former employer or client.
