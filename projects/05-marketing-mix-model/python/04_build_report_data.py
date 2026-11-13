"""
04_build_report_data.py
Collects the numbers behind the deck and the budget planner into one JavaScript
file, so every figure shown traces back to a pipeline output.
"""
import json

import numpy as np

from common import CHANNELS, CHANNEL_NAMES, MARGIN_RATE, OUT, WORK

fit = json.loads((OUT / "mmm_fit.json").read_text())
val = json.loads((OUT / "validation_optimisation.json").read_text())
qc = json.loads((OUT / "qc_log.json").read_text())
final = json.loads((WORK / "final_model.json").read_text())

dec = val["final_model"]["decomposition"]
step = 1
report = {
    "period": fit["period"], "weeks": fit["weeks"], "channels": [CHANNEL_NAMES[c] for c in CHANNELS],
    "transforms": fit["transform_search"]["chosen"], "cv_wape": fit["transform_search"]["cv_wape"],
    "fit": fit["fit"], "validation": fit["validation"], "collinearity": fit["collinearity"],
    "identification": fit["identification"], "coefficient_stability": fit["coefficient_stability"],
    "specification_sensitivity": fit["specification_sensitivity"],
    "channels_needing_a_test": fit["channels_needing_a_test"], "qc": qc,
    "uncalibrated": fit["uncalibrated"]["channels"],
    "truth": val["truth"], "accuracy": val["accuracy_vs_truth"],
    "dose": [{k: v for k, v in r.items() if k != "beta"} for r in val["experiment_dose_response"]],
    "curve_recovery": val["curve_recovery"], "response_curves": val["response_curves"],
    "optimisation": val["optimisation"], "budget_scenarios": val["budget_scenarios"],
    "final_model": {k: v for k, v in val["final_model"].items() if k != "decomposition"},
    "decomposition": {"weeks": dec["weeks"][::step], "revenue": [round(v) for v in dec["revenue"][::step]],
                      "base": [round(v) for v in dec["base"][::step]],
                      "channels": {k: [round(x) for x in v[::step]] for k, v in dec["channels"].items()}},
    "margin_rate": MARGIN_RATE,
    # the fitted curves, so the planner can price any budget in the browser
    "planner": {"beta": final["beta"], "halfs": [final["halfs"][c] for c in CHANNELS],
                "decay": [final["params"][c]["decay"] for c in CHANNELS],
                "shape": [final["params"][c]["shape"] for c in CHANNELS],
                "base_week": float(np.mean(dec["base"])),
                "current": [val["optimisation"]["current_allocation"][CHANNEL_NAMES[c]] for c in CHANNELS],
                "recommended": [val["optimisation"]["recommended"][CHANNEL_NAMES[c]] for c in CHANNELS]},
}
(OUT / "report_data.js").write_text("window.P5 = " + json.dumps(report, default=float) + ";\n")
print("report_data.js written,", len(json.dumps(report, default=float)) // 1024, "KB")
