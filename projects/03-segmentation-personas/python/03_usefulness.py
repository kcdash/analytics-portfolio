"""
03_usefulness.py
A segmentation earns its place by changing a decision. Four tests.

  1. Does a persona predict what someone buys next year?
  2. Does a persona predict how they respond to an offer?   (campaign holdouts)
  3. How much more relevant does a category-led offer become?
  4. Where does the persona sit next to the churn-and-value score from project 1?
"""
import json

import duckdb
import joblib
import numpy as np
import pandas as pd

from common import CATEGORIES, OUT, REPO, SEED, UNIT_COLS, WORK

NEXT_COLS = ["n_apparel", "n_home", "n_outdoor", "n_electronics", "n_beauty", "n_grocery", "n_toys", "n_sports"]


def assign(df, centres, base, min_log_odds):
    c = df[UNIT_COLS].to_numpy(float)
    ll = c @ np.log(np.vstack([centres, base])).T
    o = np.argsort(-ll, axis=1)
    margin = ll[np.arange(len(c)), o[:, 0]] - ll[np.arange(len(c)), o[:, 1]]
    return np.where((o[:, 0] < len(centres)) & (margin >= min_log_odds), o[:, 0], -1)


def measured(d):
    """Treated minus holdout, straight from the campaign records."""
    t, h = d[d.treated == 1], d[d.treated == 0]
    if len(t) < 100 or len(h) < 100:
        return None
    p1, p0 = t.responded_flag.mean(), h.responded_flag.mean()
    return {"contacts": int(len(d)), "holdout_n": int(len(h)), "treated_response": float(p1), "holdout_response": float(p0),
            "uplift": float(p1 - p0), "uplift_se": float(np.sqrt(p1 * (1 - p1) / len(t) + p0 * (1 - p0) / len(h)))}


def main():
    m = joblib.load(WORK / "personas.joblib")
    centres, base, names, mlo = m["centres"], m["base"], m["names"], m["min_log_odds"]
    f = pd.read_parquet(WORK / "seg_features.parquet")
    cur = pd.read_parquet(WORK / "current_segmented.parquet")
    pri = f[f.snapshot == "prior"].reset_index(drop=True)
    lead = [int(np.argmax(centres[g] / base)) for g in range(len(names))]      # the aisle each persona over-indexes on
    res = {"personas": names, "leading_category": {names[g]: CATEGORIES[lead[g]] for g in range(len(names))}}

    # ---- 1. does a persona predict next year's shopping? ----------------------
    pri = pri.assign(persona_id=assign(pri, centres, base, mlo))
    nxt = pd.read_parquet(WORK / "seg_next_year.parquet")
    fwd = pri.merge(nxt, on="customer_id")
    N = fwd[NEXT_COLS].to_numpy(float)
    tot = N.sum(1)
    keep = tot >= 5                                                            # enough next-year purchases to judge
    fwd, N, tot = fwd[keep].reset_index(drop=True), N[keep], tot[keep]
    base_next = N.sum(0) / N.sum()
    top_next = N.argmax(1)
    rows = []
    for g in range(len(names)):
        sel = (fwd.persona_id == g).to_numpy()
        if sel.sum() < 200:
            continue
        rows.append({"persona": names[g], "customers": int(sel.sum()),
                     "share_in_leading_category": float(N[sel, lead[g]].sum() / tot[sel].sum()),
                     "base_share": float(base_next[lead[g]]),
                     "lift": float((N[sel, lead[g]].sum() / tot[sel].sum()) / base_next[lead[g]]),
                     "top_category_is_leading": float((top_next[sel] == lead[g]).mean()),
                     "base_top_rate": float((top_next == lead[g]).mean())})
    unassigned = (fwd.persona_id < 0).to_numpy()
    res["next_year"] = {
        "customers_tested": int(len(fwd)), "by_persona": rows,
        "weighted_lift": float(sum(r["lift"] * r["customers"] for r in rows) / sum(r["customers"] for r in rows)),
        "hit_rate": float(np.mean([r["top_category_is_leading"] for r in rows])),
        "hit_rate_base": float(np.mean([r["base_top_rate"] for r in rows])),
        "unassigned_lift": float(np.mean([N[unassigned, lead[g]].sum() / tot[unassigned].sum() / base_next[lead[g]]
                                          for g in range(len(names))])),
        "note": "personas fixed at May 2025, purchases measured over the following twelve months"}

    # ---- 2. does a persona predict response to an offer? ----------------------
    con = duckdb.connect(str(WORK / "segmentation.duckdb"), read_only=True)
    cc = con.execute("""
        SELECT cc.customer_id, cc.campaign_id, cp.channel, cp.offer,
               CASE WHEN cc.treatment_group = 'Treatment' THEN 1 ELSE 0 END AS treated,
               cc.responded_flag
        FROM raw_campaign_contacts cc JOIN campaigns cp USING (campaign_id)
        WHERE cp.start_date > DATE '2025-05-05' AND cp.start_date <= DATE '2026-05-04'""").df()
    con.close()
    cc = cc.merge(pri[["customer_id", "persona_id"]], on="customer_id")
    by = []
    for g in range(len(names)):
        r = measured(cc[cc.persona_id == g])
        if r:
            by.append({"persona": names[g], **r})
    all_conf, none_conf = measured(cc[cc.persona_id >= 0]), measured(cc[cc.persona_id < 0])
    spread = max(b["uplift"] for b in by) - min(b["uplift"] for b in by)
    se_spread = float(np.sqrt(sum(sorted([b["uplift_se"] for b in by], reverse=True)[:2]) ** 2))
    res["offer_response"] = {
        "campaigns": int(cc.campaign_id.nunique()), "contacts": int(len(cc)), "by_persona": by,
        "with_persona": all_conf, "without_persona": none_conf,
        "spread_between_personas": float(spread), "spread_se": se_spread,
        "difference_is_meaningful": bool(spread > 1.96 * se_spread),
        "note": "personas fixed at May 2025, campaigns over the following twelve months, each with a 10% random holdout"}

    # ---- 3. how much more relevant is a category-led offer? -------------------
    U = cur[UNIT_COLS].to_numpy(float)
    conf = cur.persona_id >= 0
    rel = []
    for g in range(len(names)):
        sel = (cur.persona_id == g).to_numpy()
        rel.append({"persona": names[g], "customers": int(sel.sum()),
                    "share_of_units_in_leading_category": float(U[sel, lead[g]].sum() / U[sel].sum()),
                    "base": float(base[lead[g]]),
                    "relevance_lift": float((U[sel, lead[g]].sum() / U[sel].sum()) / base[lead[g]])})
    res["relevance"] = {"by_persona": rel,
                        "weighted_lift": float(sum(r["relevance_lift"] * r["customers"] for r in rel) / sum(r["customers"] for r in rel))}

    # ---- 4. persona next to the churn-and-value score from project 1 ----------
    p1 = REPO / "projects" / "01-churn-retention" / "work" / "churn_test_scores.parquet"
    if p1.exists():
        sc = pd.read_parquet(p1)[["customer_id", "churn_prob"]]
        j = cur.merge(sc, on="customer_id")
        j["value_at_risk"] = j.churn_prob * j.margin_365d
        j["priority"] = j.value_at_risk >= j.value_at_risk.quantile(0.7)
        res["with_project_1"] = {
            "customers_matched": int(len(j)),
            "share_with_persona_overall": float((j.persona_id >= 0).mean()),
            "share_with_persona_in_priority_group": float((j.persona_id[j.priority] >= 0).mean()),
            "churn_prob_by_persona": j[j.persona_id >= 0].groupby("persona").churn_prob.mean().round(4).to_dict(),
            "churn_prob_no_persona": float(j.churn_prob[j.persona_id < 0].mean()),
            "churn_prob_with_persona": float(j.churn_prob[j.persona_id >= 0].mean()),
            "churn_prob_overall": float(j.churn_prob.mean()),
            "note": "value at risk is churn probability times twelve-month margin, from project 1"}

    # ---- profile table used by the deck and the explorer ----------------------
    prof = []
    for g in range(len(names)):
        d = cur[cur.persona_id == g]
        mix = d[UNIT_COLS].sum().to_numpy(float)
        prof.append({
            "persona": names[g], "customers": int(len(d)), "share_of_assigned": float(len(d) / max(conf.sum(), 1)),
            "share_of_all": float(len(d) / len(cur)), "leading_category": CATEGORIES[lead[g]],
            "spend_365d": float(d.spend_365d.mean()), "margin_365d": float(d.margin_365d.mean()),
            "orders_365d": float(d.orders_365d.mean()), "avg_basket": float(d.avg_basket.mean()),
            "units_total": float(d.units_total.mean()), "distinct_categories": float(d.distinct_categories.mean()),
            "promo_line_share": float(d.promo_line_share.mean()), "private_label_share": float(d.share_private_label.mean()),
            "q4_share": float(d.q4_share.mean()), "weekend_share": float(d.weekend_share.mean()),
            "gold_share": float((d.loyalty_tier == "Gold").mean()), "email_opt_in": float(d.email_opt_in.mean()),
            "tenure_years": float(d.tenure_years.mean()), "top_age_band": d.age_band.value_counts().idxmax(),
            "channel_mix": d.dominant_channel.value_counts(normalize=True).round(4).to_dict(),
            "mix": {c: float(v) for c, v in zip(CATEGORIES, mix / mix.sum())},
            "tilt": {c: float(v / b) for c, v, b in zip(CATEGORIES, mix / mix.sum(), base)}})
    d = cur[cur.persona_id < 0]
    mix = d[UNIT_COLS].sum().to_numpy(float)
    res["profiles"] = prof
    res["no_persona_profile"] = {
        "customers": int(len(d)), "share_of_all": float(len(d) / len(cur)), "spend_365d": float(d.spend_365d.mean()),
        "orders_365d": float(d.orders_365d.mean()), "units_total": float(d.units_total.mean()),
        "distinct_categories": float(d.distinct_categories.mean()),
        "mix": {c: float(v) for c, v in zip(CATEGORIES, mix / mix.sum())}}
    res["channel_by_persona"] = pd.crosstab(cur.persona, cur.dominant_channel, normalize="index").round(4).to_dict()
    res["base_mix"] = {c: float(v) for c, v in zip(CATEGORIES, base)}

    (OUT / "usefulness.json").write_text(json.dumps(res, indent=2, default=float))
    pd.set_option("display.width", 220)
    print("next year:", {k: round(v, 3) for k, v in res["next_year"].items() if isinstance(v, float)})
    print(pd.DataFrame(rows).round(3).to_string())
    print("\noffer response:", {k: v for k, v in res["offer_response"].items() if isinstance(v, (int, float, bool))})
    print(pd.DataFrame(by).round(4).to_string())
    print("with persona", all_conf, "\nwithout", none_conf)
    print("\nrelevance", round(res["relevance"]["weighted_lift"], 3))
    print(pd.DataFrame(rel).round(3).to_string())
    print("\nwith project 1:", {k: v for k, v in res.get("with_project_1", {}).items() if isinstance(v, (int, float))})
    print(res.get("with_project_1", {}).get("churn_prob_by_persona"), round(res.get("with_project_1", {}).get("churn_prob_no_persona", 0), 4))
    print(pd.DataFrame(prof)[["persona", "customers", "share_of_assigned", "spend_365d", "orders_365d", "units_total", "gold_share", "top_age_band"]].round(3).to_string())
    print(pd.DataFrame(res["channel_by_persona"]).round(3).to_string())


if __name__ == "__main__":
    main()
