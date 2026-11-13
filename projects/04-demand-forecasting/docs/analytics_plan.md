# Analytics plan: demand forecasting

**Client:** Maple & Main (fictional Canadian omnichannel retailer)
**Prepared by:** Krish Dash
**Status:** delivered

## 1. Business question

Buying and allocation teams commit to stock about a quarter ahead. They want a weekly demand forecast they can order
against, and an answer to a question the current process ducks: how much accuracy is actually worth paying for.

## 2. Decisions this work supports

| Decision | Owner | What the analysis provides |
|---|---|---|
| How much to order for each store and category | Buying and allocation | A forecast with a range, and the service level to order to |
| Which forecast to publish at each level | Demand planning | A method per level, chosen on measured accuracy |
| Whether to invest further in forecasting | Finance | The cost of current error and the value of halving it |

## 3. Hypotheses

1. Accuracy depends more on the level being forecast than on the model used.
2. Simple benchmarks will beat a regression where series are thick, and lose where they are thin.
3. Knowing the trading calendar matters more than knowing media spend.
4. Ordering to the forecast rather than to a service level is a systematic and costly mistake.

## 4. Approach

| Step | Method | Output |
|---|---|---|
| Series build | SQL: every order line aggregated to Monday weeks at four levels | 549 weekly series over 156 weeks |
| Features | Trend, five Fourier harmonics, trading-calendar flags, media plan | Known before the week starts, by construction |
| Benchmarks | Repeat last week; repeat last year; repeat last year reset to the current level | The bar a model has to clear |
| Models | Ridge on log demand per series; a boosted model pooled across series; a two-method average | Candidate forecasts |
| Backtest | Ten origins four weeks apart, thirteen weeks ahead, refitting at every origin | Error by level, method and horizon |
| Ranges | Empirical quantiles of actual over forecast, fitted on the first five origins | Prediction intervals with an out-of-sample coverage check |
| Hierarchy | Direct against bottom-up against top-down at category level | Which level should generate which number |
| Economics | Newsvendor costs on markdown and lost margin | Optimal service level and the cost of the current rule |

## 5. Success criteria

- A method that beats the seasonal benchmark at every level.
- Prediction intervals whose stated coverage holds on origins not used to build them.
- A business case expressed in markdown and lost margin, not in accuracy points.

## 6. Risks and how they are handled

| Risk | Mitigation |
|---|---|
| A feature that would not have been known at forecast time | Every input is calendar or plan data; no actuals from the forecast period |
| One lucky holdout period | Ten rolling origins, with error reported by origin as well as on average |
| Intervals fitted and judged on the same data | Fitted on the first five origins, tested on the last five |
| Accuracy improvements that do not pay for themselves | Error is converted to CAD before any recommendation is made |
| Results look better than real life | Data is synthetic; disclosed on every deliverable |

## 7. Deliverables

Client deck (HTML and PDF), interactive forecast explorer, SQL, Python and SAS code, model card, QC log.
