# Analytics plan: marketing mix model and budget optimiser

**Client:** Maple & Main (fictional Canadian omnichannel retailer)
**Prepared by:** Krish Dash
**Status:** delivered

## 1. Business question

Maple & Main spends about $8.4M a year across six media channels. Finance wants to know what that money produces,
and marketing wants to know where the next dollar should go.

## 2. Decisions this work supports

| Decision | Owner | What the analysis provides |
|---|---|---|
| How the media budget is split | CMO | A reallocation on an unchanged total, with the gain it is expected to deliver |
| Whether the total budget should change | CFO | Incremental margin per dollar at several budget levels |
| Where to spend research money | Marketing effectiveness | Which channels the model cannot measure without an experiment, and what test design to use |

## 3. Hypotheses

1. Media effects carry over between weeks and saturate, so spend cannot be judged linearly.
2. Channel effects are weakly identified because media is planned around the same calendar the model controls for.
3. A well-fitting model can still be badly wrong about individual channels.
4. In-market tests are worth more than modelling refinements, and tests at two spend depths are worth more than tests at one.

## 4. Approach

| Step | Method | Output |
|---|---|---|
| Base table | SQL: weekly sales from order lines, media by channel, trading calendar, realised price against list | 156 weekly rows |
| Transforms | Geometric adstock and Hill saturation, searched per channel on four expanding-window folds | Carry-over and saturation per channel |
| Model | Sales = base x (1 + sum of channel lifts), fitted by alternating least squares with positive channel effects | Contribution that adds to sales exactly |
| Identification test | Refit from four honest starting points | The range of answers the data permits |
| Collinearity | Variance of each channel explained by the base terms and by other channels | Which channels need an experiment |
| Calibration | Simulated in-market holdouts, at one depth and at two | Models with the tested channels pinned |
| Optimisation | Constrained reallocation on an unchanged budget | Recommended weekly spend by channel |
| Scoring | Every recommendation evaluated on the true response curves | Whether the advice would have worked |

## 5. Success criteria

- Contribution reconciles to sales exactly and the model holds up out of time.
- The reported uncertainty reflects the identification problem, not just the standard errors.
- The recommended reallocation produces a real gain when judged against the true curves.

## 6. Risks and how they are handled

| Risk | Mitigation |
|---|---|
| The model looks precise and is not | Multi-start identification test, reported in the deck before any recommendation |
| Seasonality absorbs media, or media absorbs seasonality | Collinearity measured per channel; the worst offenders are the ones sent to test |
| The optimiser extrapolates beyond observed spend | Movement capped at half a channel's current spend |
| A recommendation that cannot be checked | Every plan scored on the true curves; in a real engagement, on a holdout region |
| Results look better than real life | Data is synthetic; disclosed on every deliverable |

## 7. Deliverables

Client deck (HTML and PDF), interactive budget planner, SQL, Python and SAS code, model card, QC log.
