"""
04_build_report_data.py
Collects everything the deck and the persona explorer display into one JavaScript
file, so every figure shown traces back to a pipeline output.
"""
import json

import joblib
import numpy as np

from common import CATEGORIES, OUT, PROJECT, UNIT_COLS, WORK

seg = json.loads((OUT / "segmentation_metrics.json").read_text())
use = json.loads((OUT / "usefulness.json").read_text())
qc = json.loads((OUT / "qc_log.json").read_text())
m = joblib.load(WORK / "personas.joblib")

report = {
    "rows": seg["rows"], "snapshots": seg["snapshots"], "settings": seg["settings"],
    "everything_clustering": seg["everything_clustering"], "category_clustering": seg["category_clustering"],
    "assignment": seg["assignment"], "reproducibility": seg["reproducibility"],
    "stability": {k: v for k, v in seg["stability"].items() if k != "migration"},
    "migration": seg["stability"]["migration"], "value_check": seg["value_check"],
    "ground_truth": seg["ground_truth"], "rfm": seg["rfm_benchmark"],
    "personas": use["personas"], "leading_category": use["leading_category"], "profiles": use["profiles"],
    "no_persona_profile": use["no_persona_profile"], "next_year": use["next_year"],
    "offer_response": use["offer_response"], "relevance": use["relevance"],
    "with_project_1": use.get("with_project_1"), "base_mix": use["base_mix"], "categories": CATEGORIES,
    "qc": qc,
    # the classifier itself, so the explorer can label a basket in the browser
    "classifier": {"centres": [[float(v) for v in row] for row in m["centres"]],
                   "base": [float(v) for v in m["base"]], "names": m["names"],
                   "min_log_odds": m["min_log_odds"], "unit_cols": UNIT_COLS},
}
(OUT / "report_data.js").write_text("window.P3 = " + json.dumps(report, default=float) + ";\n")
print("report_data.js written,", len(json.dumps(report, default=float)) // 1024, "KB")
