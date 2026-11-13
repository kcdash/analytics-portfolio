"""
04_build_report_data.py
Collects the numbers the deck and demo display into one small JavaScript file,
so every figure on a slide traces back to a pipeline output.
"""
import json

from common import OUT, PROJECT

churn = json.loads((OUT / "churn_metrics.json").read_text())
ret = json.loads((OUT / "retention_metrics.json").read_text())
demo = json.loads((PROJECT / "demo" / "demo_data.json").read_text())
qc = json.loads((OUT / "qc_log.json").read_text())

report = {
    "rows": churn["rows"], "churn_rate": churn["churn_rate"],
    "models": {k: {m: churn[k][m] for m in ["auc", "pr_auc", "brier", "top_decile_lift", "capture_top_20pct"]}
               for k in ["recency_rule", "logistic", "gbm"]},
    "psi": churn["gbm"]["score_psi_train_vs_test"], "ground_truth": churn["ground_truth"],
    "definition_test": churn["definition_test"], "calibration": churn["gbm"]["calibration"],
    "uplift_model": ret["uplift_model"], "uplift_by_predicted_decile": ret["uplift_by_predicted_decile"],
    "retention_effect": ret["retention_effect"], "profit_rule": ret["profit_rule"],
    "annual_contacts": ret["annual_contacts_current"], "qc": qc, **demo,
}
(PROJECT / "outputs" / "report_data.js").write_text("window.P1 = " + json.dumps(report, default=float) + ";\n")
(PROJECT / "demo" / "demo_data.json").unlink()      # folded into report_data.js
print("report_data.js written,", len(json.dumps(report)) // 1024, "KB")
