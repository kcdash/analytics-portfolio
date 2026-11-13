"""
02_fit_and_test.py
Builds the segmentation and then tries to break it.

The project treats "what a customer wants" and "how a customer shops" as two
separate questions, because one clustering of everything only answers the second.

  Part 1  One clustering of all behaviour  -> rediscovers the channel someone uses
  Part 2  Personas from category mix       -> five needs-based groups
  Part 3  A label is only as good as its evidence: personas are assigned by
          likelihood, and left off when the basket does not support one
  Part 4  Three tests: reproducible, stable, and not just value tiers
  Part 5  Checked against the latent shopper types built into the data
  Part 6  Classic RFM rules put through the same tests
"""
import json

import joblib
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler

from common import (CATEGORIES, LABELS, MIN_LOG_ODDS, OUT, REPO, SEED, SHAPE,
                    SHRINKAGE_UNITS, UNIT_COLS, WORK)

K = 5


def shape_frame(df):
    """Everything about how a customer shops. Logged where a long tail would dominate."""
    x = df.copy()
    x["log_basket"] = np.log1p(x.avg_basket)
    x["log_gap"] = np.log1p(x.avg_gap_days)
    x["log_sessions_per_order"] = np.log1p(x.sessions_per_order)
    return x[SHAPE]


SHORT = {"Apparel": "Apparel", "Home": "Home", "Outdoor & Garden": "Outdoor", "Electronics": "Electronics",
         "Beauty & Wellness": "Beauty", "Grocery & Pantry": "Grocery", "Toys & Seasonal": "Toys",
         "Sports & Fitness": "Sports"}


def persona_name(tilt):
    """Name a persona after the aisles it over-indexes on, not the ones it spends most in."""
    top = np.argsort(-tilt)
    first = SHORT[CATEGORIES[top[0]]]
    second = SHORT[CATEGORIES[top[1]]]
    return f"{first} & {second}" if tilt[top[1]] >= 0.85 * tilt[top[0]] else first


def shrunk_shares(df, base):
    """Category mix, pulled toward the average shopper in proportion to how little is known."""
    c = df[UNIT_COLS].to_numpy(float)
    return (c + SHRINKAGE_UNITS * base) / (c.sum(1, keepdims=True) + SHRINKAGE_UNITS)


def assign_persona(df, centres, base):
    """
    Give each customer the persona that best explains the items they actually bought.

    The score is a multinomial log-likelihood, so twenty items count for more than two.
    When the best persona does not beat the runner-up by MIN_LOG_ODDS, no persona is
    assigned: the basket is simply too ordinary, or too small, to tell.
    """
    c = df[UNIT_COLS].to_numpy(float)
    ll = c @ np.log(np.vstack([centres, base])).T          # last column: the average shopper
    order = np.argsort(-ll, axis=1)
    best, second = order[:, 0], order[:, 1]
    margin = ll[np.arange(len(c)), best] - ll[np.arange(len(c)), second]
    confident = (best < len(centres)) & (margin >= MIN_LOG_ODDS)
    return np.where(confident, best, -1), margin, ll


def best_match_share(a, b, k):
    """Share of customers two different segmentations place together, after lining up labels."""
    m = np.zeros((k, k))
    for i in range(k):
        for j in range(k):
            m[i, j] = np.sum((a == i) & (b == j))
    r, c = linear_sum_assignment(-m)
    return float(m[r, c].sum() / len(a))


def eta_squared(values, labels):
    """Share of the variation in a measure that segment membership explains."""
    grand = values.mean()
    between = sum(len(values[labels == g]) * (values[labels == g].mean() - grand) ** 2 for g in np.unique(labels))
    return float(between / ((values - grand) ** 2).sum())


def rfm_segments(df):
    """Classic rules: recency, frequency and spend scored 1-5, then named cells."""
    r = 5 - pd.qcut(df.recency_days.rank(method="first"), 5, labels=False)
    fm = (pd.qcut(df.orders_365d.rank(method="first"), 5, labels=False)
          + pd.qcut(df.spend_365d.rank(method="first"), 5, labels=False)) / 2 + 1
    return pd.Series(np.where((r >= 4) & (fm >= 4), "Champions",
                     np.where((r >= 3) & (fm >= 3), "Loyal",
                     np.where((r >= 4) & (fm < 3), "Promising",
                     np.where((r <= 2) & (fm >= 4), "At risk",
                     np.where((r <= 2) & (fm < 3), "Hibernating", "Needs attention"))))), index=df.index)


def main():
    f = pd.read_parquet(WORK / "seg_features.parquet")
    cur = f[f.snapshot == "current"].reset_index(drop=True)
    pri = f[f.snapshot == "prior"].reset_index(drop=True)
    rng = np.random.default_rng(SEED)
    res = {"rows": {"current": len(cur), "prior": len(pri)},
           "snapshots": {"prior": str(pri.as_of_date.iloc[0]), "current": str(cur.as_of_date.iloc[0])},
           "settings": {"k": K, "shrinkage_units": SHRINKAGE_UNITS, "min_log_odds": MIN_LOG_ODDS}}

    # ---------------------------------------------------------------- Part 1
    # One clustering of everything, to show what it does and does not answer.
    sc_all = StandardScaler().fit(shape_frame(cur))
    Xall = sc_all.transform(shape_frame(cur))
    km_all = KMeans(K, n_init=20, random_state=SEED).fit(Xall)
    centres_all = pd.DataFrame(sc_all.inverse_transform(km_all.cluster_centers_), columns=SHAPE)
    sd = shape_frame(cur).std()
    overall = shape_frame(cur).mean()
    res["everything_clustering"] = {
        "silhouette": float(silhouette_score(Xall[::5], km_all.labels_[::5])),
        "variance_explained_channel": float(np.mean([eta_squared(cur[c].values, km_all.labels_)
                                                     for c in ["store_share", "web_share", "app_share"]])),
        "variance_explained_category_mix": float(np.mean([eta_squared(cur[c].values, km_all.labels_)
                                                          for c in SHAPE if c.startswith("share_") and c != "share_private_label"])),
        "groups": [{"share": float((km_all.labels_ == g).mean()),
                    "distinctive": [{"label": LABELS[c], "value": float(centres_all.loc[g, c]),
                                     "overall": float(overall[c]), "z": float((centres_all.loc[g, c] - overall[c]) / sd[c])}
                                    for c in ((centres_all.loc[g] - overall) / sd).sort_values(key=abs, ascending=False).index[:3]]}
                   for g in range(K)]}

    # ---------------------------------------------------------------- Part 2
    # Personas from category mix alone.
    base = cur[UNIT_COLS].sum().to_numpy(float)
    base = base / base.sum()
    S = shrunk_shares(cur, base)
    sc_cat = StandardScaler().fit(S)
    Xcat = sc_cat.transform(S)
    km = KMeans(K, n_init=50, random_state=SEED).fit(Xcat)
    centres = sc_cat.inverse_transform(km.cluster_centers_)
    centres = np.clip(centres, 1e-4, None)
    centres = centres / centres.sum(1, keepdims=True)
    order = np.argsort(-(centres / base).max(1))                     # strongest tilt first, for stable naming
    centres = centres[order]
    names = [persona_name(centres[g] / base) for g in range(K)]
    assert len(set(names)) == K, names
    res["persona_centres"] = [{"persona": names[g], "mix": {c: float(v) for c, v in zip(CATEGORIES, centres[g])},
                               "tilt": {c: float(v / b) for c, v, b in zip(CATEGORIES, centres[g], base)}} for g in range(K)]
    res["category_clustering"] = {"silhouette": float(silhouette_score(Xcat[::5], km.labels_[::5])),
                                  "base_mix": {c: float(v) for c, v in zip(CATEGORIES, base)}}

    # ---------------------------------------------------------------- Part 3
    # Assign only where the basket supports it.
    lab, margin, _ = assign_persona(cur, centres, base)
    cur["persona"] = [names[i] if i >= 0 else "No clear persona" for i in lab]
    cur["persona_id"], cur["persona_margin"] = lab, margin
    cur["dominant_channel"] = np.select(
        [cur.store_share >= 0.5, cur.web_share >= 0.5, cur.app_share >= 0.5],
        ["Store-first", "Web-first", "App-first"], "No single channel")
    res["assignment"] = {
        "share_with_persona": float((lab >= 0).mean()),
        "by_persona": cur.persona.value_counts(normalize=True).round(4).to_dict(),
        "by_channel": cur.dominant_channel.value_counts(normalize=True).round(4).to_dict(),
        "share_with_persona_by_units": [
            {"units_band": str(b), "customers": int(len(d)), "assigned": float((d.persona_id >= 0).mean())}
            for b, d in cur.groupby(pd.cut(cur.units_total, [0, 10, 20, 30, 50, 10_000],
                                           labels=["1-10", "11-20", "21-30", "31-50", "51+"]), observed=True)],
    }
    cur["rfm"], pri["rfm"] = rfm_segments(cur), rfm_segments(pri)

    # How much more of the base could be labelled with two years of history?
    u24 = pd.read_parquet(WORK / "seg_units_24m.parquet")
    base24 = u24[UNIT_COLS].sum().to_numpy(float)
    base24 = base24 / base24.sum()
    lab24, _, _ = assign_persona(u24, centres, base24)
    res["assignment"]["share_with_persona_24m"] = float((lab24 >= 0).mean())
    res["assignment"]["median_units_12m"] = float(cur.units_total.median())
    res["assignment"]["median_units_24m"] = float(u24.units_total.median())

    # ---------------------------------------------------------------- Part 4
    # Test 1: reproducibility. Two halves of the base, segmented independently.
    half = rng.permutation(len(cur))
    A, B = half[: len(half) // 2], half[len(half) // 2:]
    ka = KMeans(K, n_init=20, random_state=SEED).fit(Xcat[A])
    kb = KMeans(K, n_init=20, random_state=SEED).fit(Xcat[B])
    res["reproducibility"] = {
        "adjusted_rand_index": float(adjusted_rand_score(ka.predict(Xcat[B]), kb.labels_)),
        "same_group_share": best_match_share(ka.predict(Xcat[B]), kb.labels_, K)}

    # Test 2: stability. A segmentation built a year ago, applied to the same customers today.
    base_p = pri[UNIT_COLS].sum().to_numpy(float)
    base_p = base_p / base_p.sum()
    sc_p = StandardScaler().fit(shrunk_shares(pri, base_p))
    km_p = KMeans(K, n_init=50, random_state=SEED).fit(sc_p.transform(shrunk_shares(pri, base_p)))
    cen_p = np.clip(sc_p.inverse_transform(km_p.cluster_centers_), 1e-4, None)
    cen_p = cen_p / cen_p.sum(1, keepdims=True)
    lab_then_all, _, _ = assign_persona(pri, cen_p, base_p)
    lab_now_all, _, _ = assign_persona(cur, cen_p, base_p)
    pri_lab = pd.Series(lab_then_all, index=pri.customer_id)
    cur_lab = pd.Series(lab_now_all, index=cur.customer_id)
    shared = pri_lab.index.intersection(cur_lab.index)
    then, now = pri_lab[shared].to_numpy(), cur_lab[shared].to_numpy()
    both_conf = (then >= 0) & (now >= 0)
    conf_then = then >= 0
    shares = np.bincount(then[then >= 0], minlength=K) / max((then >= 0).sum(), 1)
    res["stability"] = {
        "customers_tested": int(len(shared)),
        "stayed_all": float((then == now).mean()),
        "stayed_when_both_confident": float((then[both_conf] == now[both_conf]).mean()),
        "pairs_both_confident": int(both_conf.sum()),
        "kept_a_persona": float((now[conf_then] >= 0).mean()),
        "stayed_if_random": float((shares ** 2).sum()),
        "migration": pd.crosstab(pd.Series(then[both_conf]).map(dict(enumerate(names))),
                                 pd.Series(now[both_conf]).map(dict(enumerate(names))),
                                 normalize="index").round(4).to_dict()}

    # Test 3: are personas just value tiers?
    conf = cur[cur.persona_id >= 0]
    res["value_check"] = {
        "variance_in_spend_explained": eta_squared(conf.spend_365d.values, conf.persona_id.values),
        "variance_in_category_mix_explained": float(np.mean([eta_squared(conf[c].values, conf.persona_id.values)
                                                             for c in SHAPE if c.startswith("share_") and c != "share_private_label"])),
        "spend_by_persona": conf.groupby("persona").spend_365d.mean().round(1).to_dict(),
        "top_decile_spender_share": conf.assign(t=conf.spend_365d >= cur.spend_365d.quantile(0.9))
            .groupby("persona").t.mean().round(4).to_dict()}

    # ---------------------------------------------------------------- Part 5
    # Against the latent shopper types the data was generated from.
    truth = pd.read_csv(REPO / "data" / "full" / "truth" / "customer_truth.csv",
                        usecols=["customer_id", "shopper_type", "type_strength"])
    tc = cur.merge(truth, on="customer_id")
    conf_m = tc.persona_id >= 0
    res["ground_truth"] = {
        "true_types": tc.shopper_type.value_counts(normalize=True).round(4).to_dict(),
        "ari_all": float(adjusted_rand_score(tc.shopper_type, tc.persona_id)),
        "ari_confident_only": float(adjusted_rand_score(tc.shopper_type[conf_m], tc.persona_id[conf_m])),
        "ari_by_units": [{"units_band": str(b), "customers": int(len(d)),
                          "ari": float(adjusted_rand_score(d.shopper_type, d.persona_id))}
                         for b, d in tc.groupby(pd.cut(tc.units_total, [0, 15, 30, 60, 10_000],
                                                       labels=["1-15", "16-30", "31-60", "61+"]), observed=True)],
        "ari_by_strength": [{"strength_at_least": s, "customers": int((tc.type_strength >= s).sum()),
                             "ari": float(adjusted_rand_score(tc.shopper_type[tc.type_strength >= s],
                                                              tc.persona_id[tc.type_strength >= s]))}
                            for s in [0.0, 0.25, 0.5, 0.75]],
        "crosstab": pd.crosstab(tc.persona[conf_m], tc.shopper_type[conf_m], normalize="index").round(4).to_dict(),
        "mean_strength": {"assigned": float(tc.type_strength[conf_m].mean()),
                          "not_assigned": float(tc.type_strength[~conf_m].mean())}}
    # purity: each persona is paired with the latent type it mostly contains, and we ask
    # what share of its members really are that type
    ct = pd.crosstab(tc.persona[conf_m], tc.shopper_type[conf_m])
    r, c = linear_sum_assignment(-ct.values)
    pairs = {ct.index[i]: ct.columns[j] for i, j in zip(r, c)}
    res["ground_truth"]["persona_to_true_type"] = pairs
    res["ground_truth"]["purity_by_persona"] = {p: float(ct.loc[p, t] / ct.loc[p].sum()) for p, t in pairs.items()}
    res["ground_truth"]["purity_overall"] = float(ct.values[r, c].sum() / ct.values.sum())
    res["ground_truth"]["purity_if_random"] = float((tc.shopper_type.value_counts(normalize=True) ** 2).sum())

    # ---------------------------------------------------------------- Part 6
    rl_p, rl_c = pri.set_index("customer_id").rfm, cur.set_index("customer_id").rfm
    res["rfm_benchmark"] = {
        "shares": cur.rfm.value_counts(normalize=True).round(4).to_dict(),
        "stayed": float((rl_p[shared] == rl_c[shared]).mean()),
        "stayed_if_random": float((cur.rfm.value_counts(normalize=True) ** 2).sum()),
        "variance_in_spend_explained": eta_squared(cur.spend_365d.values, cur.rfm.values),
        "variance_in_category_mix_explained": float(np.mean([eta_squared(cur[c].values, cur.rfm.values)
                                                             for c in SHAPE if c.startswith("share_") and c != "share_private_label"])),
        "ari_vs_true_type": float(adjusted_rand_score(tc.shopper_type, tc.rfm))}

    joblib.dump({"centres": centres, "base": base, "names": names,
                 "min_log_odds": MIN_LOG_ODDS, "shrinkage_units": SHRINKAGE_UNITS}, WORK / "personas.joblib")
    cur.to_parquet(WORK / "current_segmented.parquet")
    (OUT / "segmentation_metrics.json").write_text(json.dumps(res, indent=2, default=float))

    pd.set_option("display.width", 220)
    print("everything-clustering:", {k: round(v, 3) for k, v in res["everything_clustering"].items() if isinstance(v, float)})
    for g in res["everything_clustering"]["groups"]:
        print("   ", round(g["share"], 3), [(d["label"], round(d["z"], 2)) for d in g["distinctive"]])
    print("\npersonas", names, "silhouette", round(res["category_clustering"]["silhouette"], 3))
    print(pd.DataFrame([p["tilt"] for p in res["persona_centres"]], index=names).round(2).to_string())
    print("\nassigned", round(res["assignment"]["share_with_persona"], 3), res["assignment"]["by_persona"])
    print(pd.DataFrame(res["assignment"]["share_with_persona_by_units"]).to_string())
    print("\nreproducibility", res["reproducibility"])
    print("stability", {k: v for k, v in res["stability"].items() if k != "migration"})
    print("value check", {k: v for k, v in res["value_check"].items() if not isinstance(v, dict)}, res["value_check"]["spend_by_persona"])
    print("\n24-month window:", round(res["assignment"]["share_with_persona_24m"], 3),
          "median units", res["assignment"]["median_units_12m"], res["assignment"]["median_units_24m"])
    print("ground truth ari all", round(res["ground_truth"]["ari_all"], 3), "confident", round(res["ground_truth"]["ari_confident_only"], 3),
          "purity", round(res["ground_truth"]["purity_overall"], 3), "vs random", round(res["ground_truth"]["purity_if_random"], 3),
          res["ground_truth"]["mean_strength"])
    print(res["ground_truth"]["purity_by_persona"])
    print(pd.DataFrame(res["ground_truth"]["ari_by_units"]).to_string())
    print(pd.DataFrame(res["ground_truth"]["ari_by_strength"]).to_string())
    print(pd.DataFrame(res["ground_truth"]["crosstab"]).round(3).to_string())
    print("rfm", {k: v for k, v in res["rfm_benchmark"].items() if not isinstance(v, dict)})


if __name__ == "__main__":
    main()
