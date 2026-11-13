"""
03_uplift_and_value.py
From "who will churn" to "who is worth contacting".

  1. Uplift model   : trained on randomised campaign holdouts (Nov 2024 to Jan 2026)
  2. Back-test      : four targeting strategies replayed on nine later campaigns (Feb to Oct 2026)
                      and scored only with measured treatment-vs-holdout differences
  3. Business case  : incremental margin less offer and contact cost, in CAD
  4. Exports        : outputs/retention_metrics.json and demo/demo_data.json
"""
import json

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

from common import FEATURES, LABELS, OUT, PROJECT, REPO, WORK, prep

SEED = 42
TEST_START = pd.Timestamp("2026-02-01")
VALID_START = pd.Timestamp("2025-10-01")          # last training campaigns, used to pick the learner
CAMPAIGNS_PER_YEAR = 13
# Offer cost as a share of the responder's basket. These are stated assumptions, not data.
OFFER_COST = {"10% off": 0.10, "5x bonus points": 0.04, "$15 off $75": 0.12, "Free shipping": 0.05, "Win-back 20% off": 0.20}
CHANNEL_COST = {"Email": 0.02, "SMS": 0.06, "Direct Mail": 0.95}
UP_FEATURES = FEATURES + ["channel", "offer"]


def xu(df, treated=None):
    x = prep(df)
    x["channel"] = pd.Categorical(df["channel"], categories=list(CHANNEL_COST))
    x["offer"] = pd.Categorical(df["offer"], categories=list(OFFER_COST))
    if treated is not None:
        x["treated"] = treated
    return x


def hgb():
    return HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=300,
                                          l2_regularization=5.0, categorical_features="from_dtype",
                                          early_stopping=True, validation_fraction=0.1, random_state=SEED)


class TLearner:
    """Two models: response if contacted, response if not. Uplift is the difference."""
    def fit(self, d):
        self.m1 = hgb().fit(xu(d[d.treated == 1]), d.responded_flag[d.treated == 1])
        self.m0 = hgb().fit(xu(d[d.treated == 0]), d.responded_flag[d.treated == 0])
        return self

    def predict(self, d):
        return self.m1.predict_proba(xu(d))[:, 1], self.m0.predict_proba(xu(d))[:, 1]


class SLearner:
    """One model with the treatment flag as a feature."""
    def fit(self, d):
        self.m = hgb().fit(xu(d, d.treated.values), d.responded_flag)
        return self

    def predict(self, d):
        return self.m.predict_proba(xu(d, 1))[:, 1], self.m.predict_proba(xu(d, 0))[:, 1]


def measured(d):
    """Treatment-vs-holdout results for a group of contacts. Nothing here is modelled."""
    t, h = d[d.treated == 1], d[d.treated == 0]
    if len(t) == 0 or len(h) == 0:
        return None
    p1, p0 = t.responded_flag.mean(), h.responded_flag.mean()
    resp = t[t.responded_flag == 1]
    return {"contacts": len(d), "holdout_n": len(h), "treated_response": p1, "holdout_response": p0, "uplift": p1 - p0,
            "uplift_se": float(np.sqrt(p1 * (1 - p1) / len(t) + p0 * (1 - p0) / len(h))),
            "margin_per_response": resp.margin_14d.mean() if len(resp) else 0.0,
            "basket_per_response": resp.net_14d.mean() if len(resp) else 0.0,
            "offer_rate": d.offer_rate.mean(), "contact_cost": d.cost_per_contact_cad.mean()}


def economics(m, offer_scale=1.0):
    """CAD per contact: incremental margin, less the offer given to every responder, less contact cost."""
    inc_margin = m["uplift"] * m["margin_per_response"]
    offer = m["treated_response"] * m["basket_per_response"] * m["offer_rate"] * offer_scale
    return {"incremental_margin": inc_margin, "offer_cost": offer, "contact_cost": m["contact_cost"],
            "net": inc_margin - offer - m["contact_cost"],
            "net_se": m["uplift_se"] * m["margin_per_response"]}      # sampling error from the holdout comparison


def qini(d, score):
    """Area between the cumulative uplift curve and a random-targeting line (higher is better)."""
    d = d.assign(s=score).sort_values("s", ascending=False)
    n = np.arange(1, len(d) + 1)
    ct, cc = d.treated.cumsum().values, (1 - d.treated).cumsum().values
    rt, rc = (d.responded_flag * d.treated).cumsum().values, (d.responded_flag * (1 - d.treated)).cumsum().values
    gain = rt - rc * ct / np.maximum(cc, 1)
    return float((gain - gain[-1] * n / len(d)).mean() / d.treated.sum())


def reasons(r):
    """Plain-English reasons behind a customer's risk, from the features the model weighs most."""
    out = []
    if r.web_sessions_3m == 0:
        out.append("No web visits in 3 months")
    elif r.web_sessions_3m < 0.5 * r.web_sessions_prev_3m:
        out.append("Web visits down by more than half")
    if pd.notna(r.overdue_ratio) and r.overdue_ratio >= 2:
        out.append(f"Order overdue: {r.overdue_ratio:.1f}x usual gap")
    elif r.recency_days >= 90:
        out.append(f"{int(r.recency_days)} days since last order")
    if r.complaints_180d >= 1:
        out.append(f"{int(r.complaints_180d)} complaint(s) in 6 months")
    if r.unresolved_180d >= 1:
        out.append("Unresolved service issue")
    if r.orders_90d < r.orders_prev_90d:
        out.append("Fewer orders than prior quarter")
    if r.loyalty_tier == "Bronze":
        out.append("Bronze tier")
    return out[:3] or ["No strong warning signs"]


def main():
    ab = pd.read_parquet(WORK / "uplift_abt.parquet")
    ab["as_of_date"] = pd.to_datetime(ab["as_of_date"])
    ab["offer_rate"] = ab.offer.map(OFFER_COST)
    churn = joblib.load(WORK / "churn_model.joblib")
    ab["churn_prob"] = churn["iso"].predict(churn["gbm"].predict_proba(prep(ab))[:, 1])
    train, test = ab[ab.as_of_date < TEST_START], ab[ab.as_of_date >= TEST_START].reset_index(drop=True)
    res = {"train_campaigns": int(train.campaign_id.nunique()), "test_campaigns": int(test.campaign_id.nunique()),
           "train_rows": len(train), "test_rows": len(test), "assumptions": {"offer_cost_share_of_basket": OFFER_COST}}

    # ---- 1. pick the uplift learner on the last training campaigns, then refit on all training data
    fit_part, val_part = train[train.as_of_date < VALID_START], train[train.as_of_date >= VALID_START]
    scores = {}
    for name, cls in [("t_learner", TLearner), ("s_learner", SLearner)]:
        m1, m0 = cls().fit(fit_part).predict(val_part)
        scores[name] = qini(val_part, m1 - m0)
    best = max(scores, key=scores.get)
    model = {"t_learner": TLearner, "s_learner": SLearner}[best]().fit(train)
    test["p_treated"], test["p_control"] = model.predict(test)
    test["uplift_pred"] = test.p_treated - test.p_control
    res["uplift_model"] = {"validation_qini": scores, "selected": best, "test_qini": qini(test, test.uplift_pred),
                           "test_qini_churn_risk_ranking": qini(test, test.churn_prob)}

    # expected net value of contacting each customer (the decision score)
    margin_rate = (test.margin_365d / test.spend_365d.replace(0, np.nan)).fillna(0.4).clip(0.1, 0.7)
    basket = test.avg_basket_365d.fillna(test.avg_basket_365d.median())
    test["net_value_pred"] = (test.uplift_pred * basket * margin_rate
                              - test.p_treated * basket * test.offer_rate - test.cost_per_contact_cad)

    # ---- 2. ground truth check: does predicted uplift track the true uplift built into the data?
    truth = pd.read_csv(REPO / "data" / "full" / "truth" / "customer_truth.csv")
    gt = json.loads((REPO / "data" / "full" / "truth" / "ground_truth.json").read_text())["uplift"]
    e = test.merge(truth, on="customer_id", how="left").engagement.values
    true_up = 0.045 * np.exp(-((e - 0.2) ** 2) / 0.8) * test.channel.map(gt["channel_factor"]).values * test.offer.map(gt["offer_factor"]).values
    true_up = np.where((test.channel == "SMS") & (e < -1.2), -0.010, true_up)
    test["true_uplift"] = true_up
    res["uplift_model"]["corr_with_true_uplift"] = float(np.corrcoef(test.uplift_pred, true_up)[0, 1])
    res["uplift_model"]["corr_churn_risk_with_true_uplift"] = float(np.corrcoef(test.churn_prob, true_up)[0, 1])
    test["uplift_decile"] = 10 - pd.qcut(test.uplift_pred.rank(method="first"), 10, labels=False)
    res["uplift_by_predicted_decile"] = [
        {"decile": int(k), "predicted": float(g.uplift_pred.mean()), "true": float(g.true_uplift.mean()), **measured(g)}
        for k, g in test.groupby("uplift_decile")]

    # ---- 3. the central finding, model-free: measured uplift by churn-risk decile
    test["risk_decile"] = 10 - pd.qcut(test.churn_prob.rank(method="first"), 10, labels=False)
    res["uplift_by_risk_decile"] = [
        {"decile": int(k), "avg_churn_prob": float(g.churn_prob.mean()), **measured(g), **economics(measured(g))}
        for k, g in test.groupby("risk_decile")]

    # ---- 4. does a campaign change 6-month retention? (campaigns with a full follow-up window)
    fu = ab[ab.as_of_date <= pd.Timestamp("2026-04-20")]
    a1, a0 = fu.active_next_180d[fu.treated == 1], fu.active_next_180d[fu.treated == 0]
    res["retention_effect"] = {"treated_active_next_180d": a1.mean(), "holdout_active_next_180d": a0.mean(),
                               "difference": a1.mean() - a0.mean(),
                               "se": float(np.sqrt(a1.var() / len(a1) + a0.var() / len(a0)))}

    # ---- 5. strategy back-test on the nine test campaigns
    rng = np.random.default_rng(SEED)
    strategies = {"Everyone (current practice)": rng.random(len(test)), "Highest churn risk": test.churn_prob,
                  "Highest value at risk": test.churn_prob * test.margin_365d, "Highest net uplift value": test.net_value_pred}
    scale = CAMPAIGNS_PER_YEAR / test.campaign_id.nunique()
    curves, headline = {}, {}
    for name, s in strategies.items():
        order = s.rank(method="first", ascending=False, pct=True) if hasattr(s, "rank") else pd.Series(s).rank(pct=True)
        pts = []
        for k in range(5, 101, 5):
            m = measured(test[order.values <= k / 100])
            pts.append({"share": k, **m, **economics(m)})
        curves[name] = pts
    res["strategy_curves"] = curves
    for name, pts in curves.items():
        at30 = pts[5]
        best_pt = max(pts, key=lambda p: p["net"] * p["contacts"])
        headline[name] = {
            "top30_uplift": at30["uplift"], "top30_uplift_se": at30["uplift_se"], "top30_net_per_contact": at30["net"],
            "top30_annual_net": at30["net"] * at30["contacts"] * scale,
            "best_share": best_pt["share"], "best_annual_net": best_pt["net"] * best_pt["contacts"] * scale,
            "all_annual_net": pts[-1]["net"] * pts[-1]["contacts"] * scale}
    res["headline"] = headline
    res["annual_contacts_current"] = len(test) * scale

    # Like-for-like budget test: keep 25,000 contacts per campaign, but choose them from the whole
    # eligible base instead of at random. Each audience was a random draw from that base, so the top
    # slice of the audience stands in for the top slice of the base.
    snap = pd.read_parquet(WORK / "churn_abt.parquet")
    snap = snap[snap.role == "test"].merge(pd.read_parquet(WORK / "churn_test_scores.parquet")[["customer_id", "churn_prob"]], on="customer_id")
    pool = {"Email": int(snap.email_opt_in.sum()), "SMS": int(snap.sms_opt_in.sum()), "Direct Mail": len(snap)}
    keep_share = test.channel.map({c: min(1.0, 25000 / n) for c, n in pool.items()})
    same_budget = {}
    for name, s in strategies.items():
        within = pd.Series(np.asarray(s)).groupby(test.campaign_id.values).rank(method="first", ascending=False, pct=True)
        sel = test[within.values <= keep_share.values] if name != "Everyone (current practice)" else test
        m = measured(sel)
        ec = economics(m)
        same_budget[name] = {"uplift": m["uplift"], "uplift_se": m["uplift_se"], **ec,
                             "annual_net": ec["net"] * res["annual_contacts_current"],
                             "annual_net_se": ec["net_se"] * res["annual_contacts_current"]}
    res["same_budget"] = same_budget
    res["eligible_pool"] = pool

    # profit rule: contact only where expected net value is positive
    pos = test[test.net_value_pred > 0]
    m = measured(pos)
    res["profit_rule"] = {"share_contacted": len(pos) / len(test), **m, **economics(m),
                          "annual_net": economics(m)["net"] * len(pos) * scale}

    # ---- 6. value at risk on the May 2026 snapshot
    snap["margin_at_risk"] = snap.churn_prob * snap.margin_365d
    top = snap.sort_values("margin_at_risk", ascending=False)
    res["value_at_risk"] = {"active_customers": len(snap), "margin_12m_total": snap.margin_365d.sum(),
                            "margin_at_risk": snap.margin_at_risk.sum(), "expected_churners": snap.churn_prob.sum(),
                            "top10pct_share_of_margin_at_risk": top.margin_at_risk.head(len(top) // 10).sum() / snap.margin_at_risk.sum()}

    # ---- 7. customer-level action list for the demo (May 2026 snapshot, standard 10% email / SMS / mail offer)
    samp = snap.sample(400, random_state=SEED).reset_index(drop=True)
    best_net, best_ch, best_up = np.full(len(samp), -np.inf), np.array(["None"] * len(samp), dtype=object), np.zeros(len(samp))
    b = samp.avg_basket_365d.fillna(snap.avg_basket_365d.median())
    mr = (samp.margin_365d / samp.spend_365d.replace(0, np.nan)).fillna(0.4).clip(0.1, 0.7)
    for ch, cost in CHANNEL_COST.items():
        ok = np.ones(len(samp), bool) if ch == "Direct Mail" else samp["email_opt_in" if ch == "Email" else "sms_opt_in"].values == 1
        p1, p0 = model.predict(samp.assign(channel=ch, offer="10% off"))
        net = (p1 - p0) * b * mr - p1 * b * 0.10 - cost
        better = ok & (net.values > best_net)
        best_net[better], best_ch[better], best_up[better] = net.values[better], ch, (p1 - p0)[better]
    samp["action"] = np.where(best_net > 0, best_ch, "Do not contact")
    risk_cut = snap.churn_prob.quantile(0.7)
    samp["segment"] = np.select(
        [(best_net > 0) & (samp.churn_prob >= risk_cut), best_net > 0, samp.churn_prob >= risk_cut],
        ["At risk and persuadable", "Persuadable, lower risk", "At risk, offer will not pay back"], "Leave alone")
    people = [{"id": f"MM-{int(r.customer_id) % 100000:05d}", "tier": r.loyalty_tier, "province": r.province,
               "risk": round(float(r.churn_prob), 3), "margin": round(float(r.margin_365d)), "uplift": round(float(best_up[i]), 4),
               "net": round(float(best_net[i]), 2), "action": r.action, "segment": r.segment, "reasons": reasons(r)}
              for i, r in samp.iterrows()]
    res["segments_in_sample"] = samp.segment.value_counts(normalize=True).round(3).to_dict()

    (OUT / "retention_metrics.json").write_text(json.dumps(res, indent=2, default=float))
    churn_m = json.loads((OUT / "churn_metrics.json").read_text())
    demo = {"curves": {k: [{f: round(float(p[f]), 5) for f in ["share", "contacts", "treated_response", "uplift", "margin_per_response",
                                                               "basket_per_response", "offer_rate", "contact_cost"]} for p in v]
                       for k, v in curves.items()},
            "campaigns_per_year": CAMPAIGNS_PER_YEAR, "test_campaigns": res["test_campaigns"],
            "same_budget": same_budget, "eligible_pool": pool,
            "risk_deciles": [{k: round(float(d[k]), 5) for k in ["decile", "avg_churn_prob", "treated_response", "holdout_response", "uplift", "uplift_se", "net", "net_se"]} for d in res["uplift_by_risk_decile"]],
            "lift": [{k: round(float(d[k]), 4) for k in ["decile", "churn_rate", "lift", "cum_capture"]} for d in churn_m["gbm"]["lift_table"]],
            "importance": churn_m["gbm"]["importance"][:8], "people": people,
            "value_at_risk": res["value_at_risk"], "labels": LABELS}
    (PROJECT / "demo" / "demo_data.json").write_text(json.dumps(demo, default=float))

    # ---- console summary
    print("uplift model", res["uplift_model"])
    print(pd.DataFrame(res["uplift_by_predicted_decile"])[["decile", "predicted", "true", "uplift", "uplift_se", "holdout_n"]].round(4))
    print(pd.DataFrame(res["uplift_by_risk_decile"])[["decile", "avg_churn_prob", "treated_response", "holdout_response", "uplift", "uplift_se", "incremental_margin", "offer_cost", "contact_cost", "net"]].round(4))
    print("retention effect", res["retention_effect"])
    print(pd.DataFrame(headline).T.round(4))
    print(pd.DataFrame(same_budget).T.round(3)); print(pool)
    print("profit rule", {k: round(v, 4) for k, v in res["profit_rule"].items()})
    print("value at risk", res["value_at_risk"])
    print("segments", res["segments_in_sample"], samp.action.value_counts().to_dict())
    for n, pts in curves.items():
        print(n, [(p["share"], round(p["net"], 2)) for p in pts[::2]])


if __name__ == "__main__":
    main()
