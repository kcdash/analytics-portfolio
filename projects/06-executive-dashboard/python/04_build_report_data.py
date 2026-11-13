"""
04_build_report_data.py
Collects everything the dashboard and the deck display into one JavaScript file,
so every figure shown traces back to a pipeline output.
"""
import json

from common import METRICS, OUT, PROJECT

sig = json.loads((OUT / "signals.json").read_text())
am = json.loads((OUT / "alerts_models.json").read_text())
qc = json.loads((OUT / "qc_log.json").read_text())

report = {
    "as_of_week": sig["as_of_week"], "as_of_date": sig["as_of_date"], "weeks": sig["weeks"],
    "rules": sig["rules"], "baseline_terms": sig["baseline_terms"], "min_history_weeks": sig["min_history_weeks"],
    "metrics": sig["metrics"], "noise_audit": sig["noise_audit"],
    "revenue_decomposition": sig["revenue_decomposition"], "slices": sig["slices"],
    "alerts": am["alerts"], "alert_counts": am["alert_counts"], "models": am["models"],
    "metric_order": [m["key"] for m in METRICS], "qc": qc,
}
(OUT / "report_data.js").write_text("window.P6 = " + json.dumps(report, default=float) + ";\n")
print("report_data.js written,", len(json.dumps(report, default=float)) // 1024, "KB")
