# Project 3: Segmentation and personas

**Question:** can Maple & Main group its active customers by what they want to buy, in a way that holds up well
enough to run content against?

**Answer:** yes, for one customer in five. Five needs-based personas are reproducible, stable a year later, and
predict where next year's spending lands. The other four in five do not buy enough for a label to mean anything,
and the honest answer is to leave them on general content rather than guess.

- [Client deck](deck/) ([PDF](deck/deck.pdf))
- [Persona explorer](demo/) — build a basket and watch the label appear, or refuse to
- [Analytics plan](docs/analytics_plan.md) · [Segmentation card](docs/segmentation_card.md) · [QC log](docs/qc_log.md)

## What makes this more than a clustering exercise

1. **It separates two questions that are usually mixed.** One clustering of all behaviour explains 77% of the
   variation in which channel people use and 12% of the variation in what they buy. It is a channel report wearing
   the word "persona". Category mix and channel habit are modelled as separate axes.
2. **A label has to earn its place.** Customers are labelled by multinomial likelihood and left unlabelled when the
   basket does not support a persona. That is 81% of the base, and saying so is the main finding.
3. **Three tests, each with a baseline.** Split-half reproducibility 0.95, twelve-month stability 82% against 21%
   for chance, and 5% of the variation in spend explained, so these are not value tiers.
4. **The labels are scored for accuracy.** The synthetic data was generated from five hidden shopper types, so
   purity can be measured: 75% against 20% for chance. The stability test and the truth agree, which is what
   licenses using the stability test on real data.
5. **It says where personas do not reach.** They do not predict offer response (spread 2.2 points against a margin
   of error of 3.8), and they are scarcest among the customers most at risk of leaving.

## Results

| | |
|---|---|
| Active customers segmented | 96,371 |
| Customers given a persona | 19% (33% with two years of history) |
| Reproducibility, split-half | 0.95 adjusted Rand index |
| Stability over twelve months | 82%, against 21% for chance |
| Accuracy against the latent shopper types | 75% pure, against 20% for chance |
| Next year's items in the persona's own aisle | 1.66x the base rate (1.00x for unlabelled customers) |
| Relevance of a persona-led offer | 2.3x more of the customer's buying |

## Run it

```
pip install -r requirements.txt
python data/generate_maple_main.py                     # full data
cd projects/03-segmentation-personas/python
python 01_build_features.py        # SQL: behaviour features at two snapshots
python 02_fit_and_test.py          # personas, assignment rule, three tests, ground truth
python 03_usefulness.py            # next-year test, offer response, relevance, overlap with project 1
python 04_build_report_data.py     # numbers for the deck and explorer
```

Outputs are identical on every run with the same package versions.

## Layout

| Folder | Contents |
|---|---|
| `sql/` | Behaviour features at two snapshots, two-year window, next-year purchases (DuckDB SQL) |
| `python/` | Pipeline scripts |
| `sas/` | Clustering and the likelihood labelling rule in SAS (not executed in this build) |
| `docs/` | Analytics plan, segmentation card, QC log |
| `outputs/` | Metrics as JSON and the data file behind the deck and explorer |
| `deck/` | Client deck, HTML and PDF |
| `demo/` | Interactive persona explorer |

## Disclaimer

Personal demonstration portfolio. All projects use synthetic data created to illustrate methods and contain no client,
employer or proprietary information. Not affiliated with or endorsed by any current or former employer or client.
