# Metric dictionary

Every measure on the dashboard is defined once, in `sql/01_kpi_mart.sql`. If another report disagrees with the
dashboard, it is not using this mart.

## Grain and scope

- One row per week, Monday to Sunday, aligned to 6 November 2023.
- 156 complete weeks, to 26 October 2026.
- Slices by category, channel and province reconcile to the company total to the dollar.

## Company metrics

| Metric | Definition | Owner | Decision it supports | Good |
|---|---|---|---|---|
| Revenue | Sum of quantity x unit price across order lines | Chief executive | Is the business on plan this quarter? | Up |
| Gross margin | Sum of quantity x (unit price - unit cost) | Finance | Is growth being bought with discount? | Up |
| Active customers | Distinct customers with an order in the week | Marketing | Is the base growing or just spending more? | Up |
| New customers | Members whose join date falls in the week | Acquisition | Is acquisition keeping pace with lapsing? | Up |
| Average basket | Revenue divided by distinct orders | Merchandising | Are people buying more per trip? | Up |
| Margin rate | Gross margin divided by revenue | Merchandising | Is the discount plan holding? | Up |
| Realised price | Revenue divided by the same units at list price | Merchandising | How much of list price are we keeping? | Up |
| Digital share | Share of revenue from web and app orders | Digital | Is the channel shift continuing? | Up |
| Media spend | Total media spend from the plan | Marketing | Are we spending to plan? | Flat |
| Service contacts | Customer service contacts in the week | Customer service | Is service load rising faster than orders? | Down |

## Definitions worth arguing about

- **New customers** are counted in the week they joined the loyalty programme, not the week of their first order.
  The first-order definition places all 110,301 pre-existing members in the first week of the extract and invents an
  acquisition spike of ten thousand. 89,699 members joined inside the window.
- **Active customers** counts distinct buyers in the week, so a customer who buys twice counts once. The weekly
  figure is therefore not comparable with a monthly active count.
- **Realised price** is the best available control for promotional depth: it compares what was charged with what the
  same units would have cost at list.
- **Province** attributes in-store revenue to the store's province and everything else to "Online", because an online
  order has no store.

## Derived measures

| Measure | Definition |
|---|---|
| Expected level | Prediction from a regression on trend, three annual harmonics, holiday peak, back-to-school and flyer weeks, fitted only on weeks before the one being judged |
| Normal variation | Standard deviation of that model's residuals on the same earlier weeks |
| Signal | A week breaking one of three rules: beyond three standard deviations; two of three beyond two; eight consecutive weeks on one side |
| Real change | A period-over-period difference larger than twice its standard error |
| Revenue decomposition | Log change in revenue split into customers, orders per customer and average basket |

## Rules of use

- A metric needs 52 weeks of history before it is judged. Before that the page shows the value and no verdict.
- A genuine step change will be flagged for several weeks until the baseline absorbs it. This is intended.
- Roughly one metric-week in a hundred will break a rule by chance. With ten metrics that is about one spurious flag
  a quarter.
