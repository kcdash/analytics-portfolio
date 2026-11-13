"""
02_train_models.py
Who converts? Three ways to rank prospects, tested on a later period.

  - Scorecard : logistic regression, readable and deployable in SQL or SAS
  - Boosting  : gradient boosting, to check whether the scorecard leaves signal behind
  - Look-alike: profile index built from converters only, the method used when there
                is no record of who did not convert (for example, bought-in audiences)

Train: first contact Jan 2024 to Sep 2025.  Test: Oct 2025 to mid-Sep 2026.
"""
import json

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score

from common import CATEGORICAL, LABELS, LEVELS, NUMERIC, OUT, REFERENCE, SEED, WORK


def design(df):
    """Scorecard design matrix: reference-coded categories, distance per 10 km."""
    x = pd.DataFrame(index=df.index)
    for c in CATEGORICAL:
        for lv in LEVELS[c][1:]:
            x[f"{c}={lv}"] = (df[c] == lv).astype(float)
    for c in NUMERIC:
        x[c] = df[c].astype(float) / (10.0 if c == "distance_to_store_km" else 1.0)
    return x


def sigmoid(z):
    return 1 / (1 + np.exp(-z))


def lift_table(y, s, bins=10):
    d = pd.DataFrame({"y": np.asarray(y), "s": np.asarray(s)})
    d["decile"] = bins - pd.qcut(d.s.rank(method="first"), bins, labels=False)
    t = d.groupby("decile").agg(prospects=("y", "size"), converters=("y", "sum")).reset_index()
    t["conversion_rate"] = t.converters / t.prospects
    t["lift"] = t.conversion_rate / d.y.mean()
    t["cum_capture"] = t.converters.cumsum() / d.y.sum()
    return t


def summary(y, s):
    t = lift_table(y, s)
    return {"auc": roc_auc_score(y, s), "top_decile_lift": float(t.lift[0]), "top_decile_rate": float(t.conversion_rate[0]),
            "bottom_decile_rate": float(t.conversion_rate[9]), "capture_top_30pct": float(t.cum_capture[2])}


def lookalike(train, score_df):
    """Sum of log profile indices: share of converters with a trait / share of all prospects with it."""
    def traits(d):
        return pd.DataFrame({
            "lead_source": d.lead_source, "age_band": d.age_band, "income": d.household_income_band,
            "children": d.has_children, "email": d.email_engaged_flag,
            "visits": d.web_visits_30d.clip(upper=4),
            "distance": pd.cut(d.distance_to_store_km, [-1, 5, 10, 15, 20, 30, 1e9], labels=False)})
    tr, sc, conv = traits(train), traits(score_df), train.converted_flag == 1
    total, index = np.zeros(len(sc)), {}
    for c in tr.columns:
        idx = (tr.loc[conv, c].value_counts(normalize=True) / tr[c].value_counts(normalize=True)).fillna(1.0)
        index[c] = {str(k): round(float(v), 3) for k, v in idx.items()}
        total += np.log(sc[c].map(idx).astype(float).fillna(1.0).values)
    return total, index


def main():
    abt = pd.read_parquet(WORK / "prospect_abt.parquet")
    abt["first_contact_date"] = pd.to_datetime(abt.first_contact_date)
    train, test = abt[abt.role == "train"].reset_index(drop=True), abt[abt.role == "test"].reset_index(drop=True)
    y_tr, y_te = train.converted_flag, test.converted_flag
    res = {"rows": {"train": len(train), "test": len(test)}, "conversion_rate": {"train": y_tr.mean(), "test": y_te.mean()},
           "period": {"train": [str(train.first_contact_date.min().date()), str(train.first_contact_date.max().date())],
                      "test": [str(test.first_contact_date.min().date()), str(test.first_contact_date.max().date())]}}

    # ---- scorecard (no regularisation, so coefficients are directly interpretable)
    X_tr, X_te = design(train), design(test)
    lr = LogisticRegression(C=1e8, max_iter=2000).fit(X_tr, y_tr)
    beta, b0 = lr.coef_[0], float(lr.intercept_[0])
    p_tr = lr.predict_proba(X_tr)[:, 1]
    A = np.c_[np.ones(len(X_tr)), X_tr.values]
    se = np.sqrt(np.diag(np.linalg.inv(A.T @ (A * (p_tr * (1 - p_tr))[:, None]))))[1:]      # standard errors from the Hessian
    logit_te = b0 + X_te.values @ beta

    # ---- the conversion rate drifts upward over time: refresh the intercept on the latest training quarter
    recent = train.first_contact_date >= "2025-07-01"
    z_recent, target = b0 + X_tr[recent].values @ beta, y_tr[recent].mean()
    lo, hi = -2.0, 2.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if sigmoid(z_recent + mid).mean() < target else (lo, mid)
    shift = (lo + hi) / 2
    p_raw, p_te = sigmoid(logit_te), sigmoid(logit_te + shift)
    res["scorecard"] = {**summary(y_te, p_te), "brier": brier_score_loss(y_te, p_te),
                        "mean_predicted_before_refresh": p_raw.mean(), "mean_predicted_after_refresh": p_te.mean(),
                        "actual_rate": y_te.mean(), "intercept": b0 + shift, "intercept_shift": shift,
                        "lift_table": lift_table(y_te, p_te).round(4).to_dict("records")}
    cal = pd.DataFrame({"y": y_te, "p": p_te})
    cal["bin"] = pd.qcut(cal.p.rank(method="first"), 10, labels=False)
    res["scorecard"]["calibration"] = cal.groupby("bin").agg(predicted=("p", "mean"), actual=("y", "mean")).round(4).to_dict("records")

    # ---- gradient boosting benchmark
    def gx(d):
        x = d[["lead_source", "age_band", "household_income_band", "province", "has_children", "distance_to_store_km",
               "web_visits_30d", "email_engaged_flag"]].copy()
        for c in ["lead_source", "age_band", "household_income_band", "province"]:
            x[c] = x[c].astype("category")
        return x
    gbm = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=200,
                                         l2_regularization=2.0, categorical_features="from_dtype", early_stopping=True,
                                         validation_fraction=0.1, random_state=SEED).fit(gx(train), y_tr)
    s_gbm = gbm.predict_proba(gx(test))[:, 1]
    res["boosting"] = summary(y_te, s_gbm)

    # ---- look-alike index and a single-rule benchmark
    s_look, index = lookalike(train, test)
    res["lookalike"] = {**summary(y_te, s_look), "index": index}
    res["web_visits_rule"] = summary(y_te, test.web_visits_30d + np.random.default_rng(SEED).random(len(test)) * 1e-6)

    # ---- ground truth: the conversion rule built into the synthetic data
    true_effect = {"lead_source=Event": 0.0, "lead_source=Purchased list": -0.60, "lead_source=Referral": 0.55, "lead_source=Web lead": 0.35,
                   "age_band=18-24": 0.0, "age_band=25-34": 0.30, "age_band=35-44": 0.30, "age_band=55-64": 0.0, "age_band=65+": 0.0,
                   "household_income_band=50-75k": 0.12, "household_income_band=75-100k": 0.24,
                   "household_income_band=100-150k": 0.36, "household_income_band=150k+": 0.48,
                   "web_visits_capped": 0.16, "distance_to_store_km": -0.25, "has_children": 0.25, "email_engaged_flag": 0.65}
    true_logit = X_te.values @ np.array([true_effect[c] for c in X_te.columns])
    ceiling = roc_auc_score(y_te, true_logit)
    res["ground_truth"] = {
        "auc_ceiling": ceiling,       # the best any model could do: the rest is chance
        "share_of_signal_captured": {k: (res[k]["auc"] - 0.5) / (ceiling - 0.5) for k in ["scorecard", "boosting", "lookalike", "web_visits_rule"]},
        "corr_scorecard_vs_true_logit": float(np.corrcoef(logit_te, true_logit)[0, 1]),
        "effects_within_95pct_interval": int(sum(abs(b - true_effect[c]) <= 1.96 * s for c, b, s in zip(X_te.columns, beta, se))),
        "effects_total": len(beta)}

    def nice(c):
        return LABELS[c] if c in LABELS else c.split("=")[1] + {"lead_source": " (vs partner list)", "age_band": " (vs age 45-54)",
                                                               "household_income_band": " income (vs under 50k)"}[c.split("=")[0]]
    res["effects"] = [{"term": c, "label": nice(c), "estimate": float(b), "se": float(s), "true": true_effect[c]}
                      for c, b, s in zip(X_te.columns, beta, se)]

    scores = test[["prospect_id", "first_contact_date", "lead_source", "converted_flag"]].assign(
        p_scorecard=p_te, s_boosting=s_gbm, s_lookalike=s_look)
    scores.to_parquet(WORK / "test_scores.parquet")
    (OUT / "model_metrics.json").write_text(json.dumps(res, indent=2, default=float))

    for k in ["web_visits_rule", "lookalike", "scorecard", "boosting"]:
        print(f"{k:<16}", {m: round(v, 4) for m, v in res[k].items() if isinstance(v, float)})
    print("truth", res["ground_truth"])
    print(pd.DataFrame(res["effects"])[["label", "estimate", "se", "true"]].round(3).to_string())
    print(pd.DataFrame(res["scorecard"]["lift_table"]).to_string())
    print(pd.DataFrame(res["scorecard"]["calibration"]).T.to_string())


if __name__ == "__main__":
    main()
