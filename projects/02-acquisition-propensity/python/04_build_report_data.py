"""
04_build_report_data.py
Collects the numbers behind the deck and the demo into one JavaScript file,
so every figure shown traces back to a pipeline output.
"""
import json

import numpy as np
import pandas as pd

from common import COST_PER_CONTACT, COST_PER_LEAD, LEVELS, OUT, WORK

m = json.loads((OUT / "model_metrics.json").read_text())
e = json.loads((OUT / "economics.json").read_text())
scores = pd.read_parquet(WORK / "test_scores.parquet")

report = {
    "rows": m["rows"], "conversion_rate": m["conversion_rate"], "period": m["period"],
    "models": {k: {x: m[k][x] for x in ["auc", "top_decile_lift", "top_decile_rate", "bottom_decile_rate", "capture_top_30pct"]}
               for k in ["web_visits_rule", "lookalike", "scorecard", "boosting"]},
    "scorecard": {k: m["scorecard"][k] for k in ["intercept", "mean_predicted_before_refresh", "mean_predicted_after_refresh", "actual_rate", "brier"]},
    "lift": m["scorecard"]["lift_table"], "calibration": m["scorecard"]["calibration"],
    "ground_truth": m["ground_truth"], "effects": m["effects"], "levels": LEVELS,
    # score cut-offs between deciles, lowest to highest, for the prospect scorer in the demo
    "decile_cuts": [round(float(v), 5) for v in np.quantile(scores.p_scorecard, np.linspace(0.1, 0.9, 9))],
    "cost_per_contact": COST_PER_CONTACT, "cost_per_lead": COST_PER_LEAD, **{k: e[k] for k in [
        "prospects_per_year", "converters_per_year", "value", "curves", "budget_scenarios", "deciles",
        "incrementality_scenarios", "sources", "source_by_score", "value_by_score", "test_design"]},
    "qc": json.loads((OUT / "qc_log.json").read_text()),
}
(OUT / "report_data.js").write_text("window.P2 = " + json.dumps(report, default=float) + ";\n")
print("report_data.js written,", len(json.dumps(report, default=float)) // 1024, "KB")
