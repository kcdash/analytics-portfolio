# Analytics plan: segmentation and personas

**Client:** Maple & Main (fictional Canadian omnichannel retailer)
**Prepared by:** Krish Dash
**Status:** delivered

## 1. Business question

Marketing wants to move from one message for everyone to content built around what customers actually want. That
needs a segmentation of the active base that merchandising and CRM can both use, and an honest answer about how
many customers it can really cover.

## 2. Decisions this work supports

| Decision | Owner | What the analysis provides |
|---|---|---|
| What goes in the message and the catalogue | CRM and merchandising | A persona per customer, where the evidence supports one |
| Who gets personalised content at all | CRM manager | A confidence rule and the share of the base it covers |
| How much history to keep for targeting | Data and martech | The gain from a two-year window over a one-year window |

## 3. Hypotheses

1. Customers differ in what they buy, not only in how much they spend.
2. One clustering of all behaviour will be dominated by channel use and will not answer the merchandising question.
3. Most customers do not buy enough in a year for their category mix to be read reliably.
4. A persona will predict next year's shopping; it will not predict response to an offer.

## 4. Approach

| Step | Method | Output |
|---|---|---|
| Behaviour features | SQL, two snapshots a year apart: category units and spend, channel mix, promotion use, trip rhythm, browsing | One row per customer per snapshot |
| Naive segmentation | K-means on all 22 behaviour measures | Evidence for separating the two questions |
| Personas | K-means on category unit shares, shrunk toward the average shopper | Five persona centres |
| Assignment | Multinomial likelihood against each persona and against the average shopper, with a minimum margin | A persona, or none |
| Test 1 | Split-half: two halves of the base segmented independently | Adjusted Rand index |
| Test 2 | Same customers segmented a year apart | Share keeping their persona |
| Test 3 | Variance in spend explained by persona | Proof these are not value tiers |
| Test 4 | Persona at one snapshot against purchases over the next twelve months | Predictive lift |
| Ground truth | Comparison with the latent shopper types the data was generated from | Purity and agreement |
| Usefulness | Campaign holdouts by persona; overlap with the value-at-risk score from project 1 | What personas can and cannot decide |

## 5. Success criteria

- The same five groups appear when the base is split in half.
- Customers keep their persona from one year to the next far more often than chance.
- Persona explains much more of the variation in category mix than a classic RFM segmentation does, and much less of
  the variation in spend.
- A persona assigned a year earlier predicts where next year's purchases land.

## 6. Risks and how they are handled

| Risk | Mitigation |
|---|---|
| Clustering returns groups that are really value tiers | Spend is excluded from the inputs and the overlap is measured |
| A small basket looks like a strong taste | Shares are shrunk toward the average shopper and a likelihood margin is required |
| Segments look neat but do not persist | Twelve-month stability is measured and reported alongside a chance baseline |
| Labels are used for decisions they cannot support | Offer response is measured by persona and reported as no meaningful difference |
| Results look better than real life | Data is synthetic; disclosed on every deliverable |

## 7. Deliverables

Client deck (HTML and PDF), interactive persona explorer, SQL, Python and SAS code, segmentation card, QC log.
