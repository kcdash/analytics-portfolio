"""
04_build_report_data.py
Collects the numbers behind the deck and the forecast explorer into one
JavaScript file, so every figure shown traces back to a pipeline output.
"""
import json

import numpy as np
import pandas as pd

from common import LEVELS, OUT, PROJECT, WORK

back = json.loads((OUT / "backtest.json").read_text())
io = json.loads((OUT / "intervals_ordering.json").read_text())
qc = json.loads((OUT / "qc_log.json").read_text())
cal = pd.read_parquet(WORK / "calendar.parquet").sort_values("t")

# the last forecast, with the band around it, for every level
ff = back["final_forecast"]
series_out = {}
for level in LEVELS:
    f = ff[level]
    champ = back["champion"][level]
    q = io["intervals"][level]["quantiles"]
    hist_weeks = 26
    s = pd.read_parquet(WORK / "series.parquet")
    s = s[s.level == level]
    piv = s.pivot(index="series_id", columns="t", values="revenue")
    first_t = int(s.t.max()) - len(f["weeks"]) - hist_weeks + 1
    dates = [str(d.date()) if hasattr(d, "date") else str(d) for d in cal.week_start]
    pick = f["ids"][:12] if level == "Store x Category" else f["ids"]
    rows = []
    for name in pick:
        i = f["ids"].index(name)
        hist = piv.loc[name].to_numpy()[first_t:first_t + hist_weeks]
        pred = np.array(f["preds"][champ][i])
        rows.append({"id": name, "history": [round(float(v)) for v in hist],
                     "actual": [round(float(v)) for v in f["actual"][i]],
                     "forecast": [round(float(v)) for v in pred],
                     "lo": [round(float(v * q["0.1"])) for v in pred],
                     "hi": [round(float(v * q["0.9"])) for v in pred]})
    series_out[level] = {"champion": champ, "weeks": [dates[first_t + k] for k in range(hist_weeks)] + f["weeks"],
                         "history_weeks": hist_weeks, "series": rows}

report = {
    "levels": LEVELS, "origins": back["origins"], "backtest_dates": back["backtest_dates"],
    "max_horizon": back["max_horizon"], "summary": back["summary"], "by_horizon": back["by_horizon"],
    "champion": back["champion"], "champion_by_horizon": back["champion_by_horizon"],
    "winner_wape": back["winner_wape"], "seasonal_naive_wape": back["seasonal_naive_wape"],
    "knowledge_ladder": back["knowledge_ladder"],
    "intervals": {k: {"quantiles": v["quantiles"], "coverage": v["coverage_out_of_sample"],
                      "band": v["band_80_pct_of_forecast"]} for k, v in io["intervals"].items()},
    "reconciliation": io["reconciliation"], "ordering": io["ordering"], "assumptions": io["assumptions"],
    "forecasts": series_out, "qc": qc,
    "series_counts": {"Total": 1, "Category": 8, "Store": 60, "Store x Category": 480},
}
(OUT / "report_data.js").write_text("window.P4 = " + json.dumps(report, default=float) + ";\n")
print("report_data.js written,", len(json.dumps(report, default=float)) // 1024, "KB")
