# Segmentation card: Maple & Main personas

| | |
|---|---|
| Purpose | Describe what an active customer wants to buy, so content and merchandising can be matched to it |
| Population | Customers of at least a year's standing with two or more orders in the previous twelve months |
| Size | 96,371 active customers at 4 May 2026; 90,669 at 5 May 2025; 71,259 active at both |
| Method | K-means (k=5) on category unit shares, shrunk toward the average shopper by 20 items |
| Inputs | Units bought in each of eight merchandise categories in the previous twelve months |
| Deliberately excluded | Spend, margin, recency, frequency, channel. Value belongs in a score, not a persona |
| Assignment | Multinomial likelihood against each persona and against the average shopper; a persona is given only when it beats the runner-up by a factor of about seven |
| Refresh | Monthly scoring; refit annually |

## The five personas

| Persona | Over-indexes on | Share of labelled customers | Spend a year | Items a year |
|---|---|---|---|---|
| Beauty & Apparel | Beauty and wellness, apparel | 26% | $2,027 | 40 |
| Electronics | Electronics | 24% | $2,796 | 36 |
| Home & Outdoor | Home, outdoor and garden | 20% | $2,462 | 42 |
| Grocery & Toys | Grocery and pantry, toys and seasonal | 17% | $1,798 | 42 |
| Sports | Sports and fitness | 13% | $2,357 | 37 |

19% of active customers carry a persona. The other 81% do not buy enough, or buy too evenly, for a label to mean
anything. They are reported as "no clear persona" rather than forced into a group.

## How it was tested

| Test | Result | Baseline |
|---|---|---|
| Reproducible: two halves of the base segmented independently | Adjusted Rand index 0.95 | 0 is chance |
| Stable: same customers segmented a year apart | 82% keep their persona | 21% if labels were shuffled |
| Not value tiers: variation in spend explained | 5% | RFM explains 52% |
| About what people buy: variation in category mix explained | 38% | RFM explains 1% |
| Predictive: next year's items in the persona's own aisle | 1.66x the base rate | 1.00x for unlabelled customers |
| Predictive: next year's top aisle is the persona's | 30% | 11% base rate |

## Checked against the latent shopper types

The synthetic data was generated from five hidden shopper types of varying strength. A real project never sees these.

- 75% of confidently labelled customers belong to the type their persona points at; chance would give 20%.
- Agreement with the hidden types is 0.50 (adjusted Rand index) among labelled customers, and 0.01 if every customer
  is force-labelled. The confidence rule is doing the work.
- Labelled customers have stronger latent tastes on average (0.54 against 0.46 on a 0-to-1 scale).
- Per persona: Beauty & Apparel 79%, Home & Outdoor 79%, Grocery & Toys 77%, Electronics 75%, Sports 61%.

## What the personas do not do

- **They do not predict offer response.** Across 13 campaigns and 207,905 contacts with random holdouts, measured
  uplift ranges from 1.2 to 3.5 points across the five personas, a spread of 2.2 points against a margin of error of
  3.8. Audience selection belongs to the churn-and-value model in project 1.
- **They are scarcest where retention effort goes.** Labelled customers have an average churn probability of 8%
  against 16% for unlabelled customers, because a label comes from buying a lot. Among the top 30% of customers by
  value at risk, only 17% carry a persona.
- **Channel is not part of a persona.** It is kept as a separate attribute (store-first, web-first, app-first, or no
  single channel) and in this data is uncorrelated with persona, so the two carry different information.

## Assumptions

- Twelve months of purchases defines a customer's current taste.
- Shrinkage of 20 items and a likelihood margin of exp(2), about seven to one, set the bar for a label. Both are
  judgement calls; the explorer shows the effect of moving the bar.
- Category is the right unit of "need". Subcategory or brand would be finer but thinner per customer.

## Limitations

- **Synthetic data.** Results illustrate the method and are not evidence about any real retailer.
- **Fit statistics are weak by nature.** The silhouette score is 0.14. Shopping behaviour has no natural gaps;
  segments are constructed, and reproducibility, stability and prediction are the tests that matter.
- **Labels lapse.** Of customers labelled in 2025, 35% still qualified in 2026; the rest bought too little to keep
  a label, not necessarily because their taste changed.
- **Relevance is measured, revenue is not.** A persona-led offer addresses 2.3 times more of a customer's buying
  than a generic one, but the revenue effect of acting on it needs a test with a control group.
- **Fairness.** Personas are built from purchases only, with no demographic inputs. Age and province are reported
  for profiling but never used to assign a persona.

## Monitoring plan

- Monthly: share of the base carrying a persona, and the split across the five.
- Quarterly: stability of labels against the previous quarter; investigate if it falls below 70%.
- Annually: refit, then re-run the split-half and next-year tests before replacing the live centres.
