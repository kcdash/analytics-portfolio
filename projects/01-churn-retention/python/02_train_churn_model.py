"""
02_train_churn_model.py
Trains and validates the churn model.

  - Trains on four snapshots (Nov 2024 to Aug 2025)
  - Calibrates probabilities on the Nov 2025 snapshot
  - Tests once on the May 2026 snapshot, which no model decision ever saw
  - Benchmarks against a recency rule and a logistic scorecard
  - Checks the churn label and the model against the generator's ground truth
"""
import json

import duckdb
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from common import CATEGORICAL, LABELS, NUMERIC, OUT, REPO, WORK, prep

SEED = 42


def lift_table(y, p, bins=10):
    d = pd.DataFrame({"y": y, "p": p})
    d["decile"] = bins - pd.qcut(d["p"].rank(method="first"), bins, labels=False)
    t = d.groupby("decile").agg(customers=("y", "size"), churners=("y", "sum"), avg_score=("p", "mean")).reset_index()
    t["churn_rate"] = t["churners"] / t["customers"]
    t["lift"] = t["churn_rate"] / d["y"].mean()
    t["cum_capture"] = t["churners"].cumsum() / d["y"].sum()
    return t


def psi(a, b, bins=10):
    cuts = np.quantile(a, np.linspace(0, 1, bins + 1))[1:-1]
    pa = np.bincount(np.searchsorted(cuts, a), minlength=bins) / len(a)
    pb = np.bincount(np.searchsorted(cuts, b), minlength=bins) / len(b)
    pa, pb = np.clip(pa, 1e-6, None), np.clip(pb, 1e-6, None)
    return float(((pa - pb) * np.log(pa / pb)).sum())


def summary(y, p):
    t = lift_table(y, p)
    return {"auc": roc_auc_score(y, p), "pr_auc": average_precision_score(y, p), "brier": brier_score_loss(y, p),
            "top_decile_lift": float(t.loc[0, "lift"]), "capture_top_20pct": float(t.loc[1, "cum_capture"])}


def main():
    abt = pd.read_parquet(WORK / "churn_abt.parquet")
    train, valid, test = (abt[abt.role == r].reset_index(drop=True) for r in ["train", "validate", "test"])
    y_tr, y_va, y_te = train.churn_180d, valid.churn_180d, test.churn_180d
    res = {"rows": {"train": len(train), "validate": len(valid), "test": len(test)},
           "churn_rate": {"train": y_tr.mean(), "validate": y_va.mean(), "test": y_te.mean()}}

    # --- Benchmark 1: the rule of thumb (longest since last order = highest risk)
    res["recency_rule"] = summary(y_te, test.recency_days.rank(pct=True))

    # --- Benchmark 2: logistic scorecard (same form as the SAS PROC LOGISTIC version)
    logit = make_pipeline(
        ColumnTransformer([
            ("num", make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler()), NUMERIC),
            ("cat", OneHotEncoder(handle_unknown="ignore", drop="first"), CATEGORICAL)]),
        LogisticRegression(C=0.5, max_iter=500))
    logit.fit(train[NUMERIC + CATEGORICAL], y_tr)
    res["logistic"] = summary(y_te, logit.predict_proba(test[NUMERIC + CATEGORICAL])[:, 1])
    names = logit[0].get_feature_names_out()
    coef = pd.Series(logit[-1].coef_[0], index=[n.split("__")[1] for n in names]).sort_values()
    res["logistic_coefficients"] = coef.round(4).to_dict()

    # --- Champion: gradient boosting, calibrated on the validation snapshot
    gbm = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.06, max_leaf_nodes=31, min_samples_leaf=200,
                                         l2_regularization=1.0, categorical_features="from_dtype",
                                         early_stopping=True, validation_fraction=0.1, random_state=SEED)
    gbm.fit(prep(train), y_tr)
    iso = IsotonicRegression(out_of_bounds="clip").fit(gbm.predict_proba(prep(valid))[:, 1], y_va)
    raw_te = gbm.predict_proba(prep(test))[:, 1]
    p_te = iso.predict(raw_te)
    res["gbm"] = summary(y_te, p_te)
    res["gbm"]["brier_uncalibrated"] = brier_score_loss(y_te, raw_te)
    res["gbm"]["score_psi_train_vs_test"] = psi(gbm.predict_proba(prep(train))[:, 1], raw_te)
    res["gbm"]["lift_table"] = lift_table(y_te, p_te).round(4).to_dict("records")
    cal = pd.DataFrame({"y": y_te, "p": p_te})
    cal["bin"] = pd.qcut(cal.p.rank(method="first"), 20, labels=False)
    res["gbm"]["calibration"] = cal.groupby("bin").agg(predicted=("p", "mean"), actual=("y", "mean")).round(4).to_dict("records")

    # --- What drives the score (permutation importance on the test snapshot)
    samp = test.sample(40000, random_state=SEED)
    pi = permutation_importance(gbm, prep(samp), samp.churn_180d, scoring="roc_auc", n_repeats=3, random_state=SEED)
    imp = pd.Series(pi.importances_mean, index=prep(samp).columns).sort_values(ascending=False)
    res["gbm"]["importance"] = [{"feature": f, "label": LABELS[f], "auc_drop": round(float(v), 5)} for f, v in imp.head(12).items()]

    # --- Ground truth: how good is the 180-day label, and does the model find real churners?
    truth = pd.read_csv(REPO / "data" / "full" / "truth" / "customer_truth.csv", parse_dates=["churn_date"])
    t = test.merge(truth, on="customer_id")
    true_churn = (t.churn_date <= t.as_of_date + pd.Timedelta(days=180)).astype(int)
    res["ground_truth"] = {
        "true_churn_rate": true_churn.mean(),
        "label_precision": float(true_churn[t.churn_180d == 1].mean()),      # labelled churners who really left
        "label_recall": float(t.churn_180d[true_churn == 1].mean()),         # real leavers the label catches
        "gbm_auc_vs_true_churn": roc_auc_score(true_churn, p_te),
        "logistic_auc_vs_true_churn": roc_auc_score(true_churn, logit.predict_proba(test[NUMERIC + CATEGORICAL])[:, 1]),
        "recency_auc_vs_true_churn": roc_auc_score(true_churn, test.recency_days),
    }
    # false alarms by buying frequency: quiet customers who had not actually left
    t["freq_band"] = pd.cut(t.orders_365d, [0, 2, 5, 10, 1000], labels=["1-2 orders", "3-5 orders", "6-10 orders", "11+ orders"])
    fa = t[t.churn_180d == 1].assign(false_alarm=lambda d: 1 - true_churn[d.index]).groupby("freq_band", observed=True)
    res["ground_truth"]["false_alarm_by_frequency"] = fa.false_alarm.agg(["size", "mean"]).round(4).reset_index().to_dict("records")

    # --- Churn definition: test inactivity windows against the truth (Nov 2025 snapshot)
    con = duckdb.connect(str(WORK / "churn.duckdb"), read_only=True)
    rows = []
    for h in [60, 90, 120, 180, 240]:
        d = con.execute(f"""
            SELECT s.customer_id,
                   CASE WHEN EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = s.customer_id
                                     AND o.order_date >= s.as_of_date AND o.order_date < s.as_of_date + {h})
                        THEN 0 ELSE 1 END AS label
            FROM churn_spine s WHERE s.as_of_date = DATE '2025-11-03'""").df().merge(truth, on="customer_id")
        gone = (d.churn_date <= pd.Timestamp("2025-11-03") + pd.Timedelta(days=h)).astype(int)
        rows.append({"window_days": h, "labelled_churn_rate": d.label.mean(),
                     "precision": float(gone[d.label == 1].mean()), "recall": float(d.label[gone == 1].mean())})
    con.close()
    res["definition_test"] = rows

    # --- Save
    test_scores = test[["customer_id", "as_of_date", "churn_180d"]].assign(churn_prob=p_te, true_churn=true_churn.values)
    test_scores.to_parquet(WORK / "churn_test_scores.parquet")
    joblib.dump({"gbm": gbm, "iso": iso}, WORK / "churn_model.joblib")
    (OUT / "churn_metrics.json").write_text(json.dumps(res, indent=2, default=float))
    for k in ["recency_rule", "logistic", "gbm"]:
        print(k, {m: round(v, 4) for m, v in res[k].items() if isinstance(v, float)})
    print("ground truth", {k: v for k, v in res["ground_truth"].items() if k != "false_alarm_by_frequency"})
    print(pd.DataFrame(res["ground_truth"]["false_alarm_by_frequency"]))
    print(pd.DataFrame(rows).round(3))
    print(pd.DataFrame(res["gbm"]["importance"]))
    print(coef.round(3).to_string())


if __name__ == "__main__":
    main()
