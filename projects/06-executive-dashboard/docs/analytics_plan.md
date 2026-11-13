# Analytics plan: executive KPI dashboard

**Client:** Maple & Main (fictional Canadian omnichannel retailer)
**Prepared by:** Krish Dash
**Status:** delivered

## 1. Business question

The executive team meets weekly in front of a KPI page nobody trusts. Numbers move every week, the same questions
get asked every week, and the models built elsewhere in the business never reach the room. They want a page that
tells them what changed, whether it matters, and what to do.

## 2. Decisions this work supports

| Decision | Owner | What the dashboard provides |
|---|---|---|
| What the weekly meeting discusses | Chief executive | A ranked list of items that broke a rule, with the owner attached |
| Whether to act on a movement | Metric owner | Whether the movement is larger than the metric's own normal variation |
| Where to look when revenue moves | Commercial | A decomposition into customers, visit frequency and basket, plus the slices that are unusual |
| What to do next | Functional leads | The output of the churn, acquisition, persona, demand and media models, each with its action |

## 3. Hypotheses

1. Most week-on-week movement in these metrics is noise, and a page that highlights it trains people to ignore it.
2. Seasonal metrics produce alarming period-over-period changes that need no action at all.
3. A short list of sentences will be used; a wall of tiles will not.
4. The models are more useful on the page people already read than in a report nobody opens.

## 4. Approach

| Step | Method | Output |
|---|---|---|
| Metric definitions | SQL: one weekly fact table, every measure defined once | 10 company metrics, three slice dimensions |
| Baselines | Per metric and week, a regression on trend, annual harmonics and trading events, fitted only on earlier weeks | Expected level and normal variation |
| Control rules | Three standard deviations; two of three beyond two; eight weeks one side | Flagged weeks |
| Period comparison | Last N weeks against the N before, with a standard error from both | "Real" or "within normal" |
| Decomposition | Revenue split into customers, orders per customer and basket on a log scale | Three parts that add to the total |
| Slices | The same baseline and rules applied to every category, channel and province | Where it is happening |
| Alerts | Ranked, written as sentences, with owner and severity | The agenda |
| Model panel | Outputs of projects 1 to 5 | What is about to happen |

## 5. Success criteria

- The number of items raised reflects the data, not a target length.
- A large seasonal movement is explicitly marked as normal rather than left to be explained in the meeting.
- Every metric on the page has an owner and a decision attached.
- Slice revenue reconciles to the company total exactly.

## 6. Risks and how they are handled

| Risk | Mitigation |
|---|---|
| A baseline that has seen the week it judges | Fitted only on earlier weeks, every week, for every metric |
| False alarms from multiple rules on multiple metrics | Rate quantified and stated: roughly one metric-week in a hundred |
| A step change treated as a permanent problem | Documented behaviour; the baseline absorbs it within a year |
| The page implying causation | An explicit limits slide; causal questions are routed to the holdout designs in projects 1 and 5 |
| Definitions drifting from the finance pack | Every measure defined once in SQL, in one file |

## 7. Deliverables

The dashboard itself, a design-notes deck (HTML and PDF), SQL, Python and SAS code, a metric dictionary and QC log.
