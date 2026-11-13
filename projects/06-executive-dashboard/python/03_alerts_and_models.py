"""
03_alerts_and_models.py
Two things a KPI page usually lacks.

  1. A short, ranked list of what actually needs attention this week, written in
     sentences, with the owner attached. Everything else stays on the page but
     stays quiet.
  2. The output of the models built elsewhere in this portfolio, so the dashboard
     reports what is about to happen as well as what has happened.
"""
import json

import numpy as np
import pandas as pd

from common import OUT, REPO, WORK

P = REPO / "projects"


def money(v):
    return f"${abs(v):,.0f}"


def main():
    sig = json.loads((OUT / "signals.json").read_text())
    d = pd.read_parquet(WORK / "kpi_week.parquet").sort_values("t").reset_index(drop=True)
    as_of = sig["as_of_week"]
    metrics = sig["metrics"]
    res = {"as_of_date": sig["as_of_date"]}

    # ---------------------------------------------------------------- models
    models = {}

    # Project 1: who is about to lapse, and what that is worth
    ret = json.loads((P / "01-churn-retention" / "outputs" / "retention_metrics.json").read_text())
    churn = json.loads((P / "01-churn-retention" / "outputs" / "churn_metrics.json").read_text())
    var = ret["value_at_risk"]
    models["retention"] = {
        "title": "Customers at risk", "source": "Project 1: churn and retention value",
        "headline": money(var["margin_at_risk"]), "headline_label": "12-month margin at risk",
        "detail": [
            {"label": "Active customers scored", "value": f"{var['active_customers']:,.0f}"},
            {"label": "Lapsing in six months", "value": f"{var['expected_churners']:,.0f}"},
            {"label": "Risk in the top 10%", "value": f"{var['top10pct_share_of_margin_at_risk']:.0%}"},
            {"label": "Model accuracy", "value": f"AUC {churn['gbm']['auc']:.2f}"}],
        "action": "Rank the monthly offer list by value at risk, not by risk alone.",
        "value_at_stake": var["margin_at_risk"]}

    # Project 2: acquisition
    econ = json.loads((P / "02-acquisition-propensity" / "outputs" / "economics.json").read_text())
    b40 = [b for b in econ["budget_scenarios"] if b["share"] == 40][0]
    models["acquisition"] = {
        "title": "Acquisition", "source": "Project 2: acquisition propensity",
        "headline": money(b40["extra_first_year_margin"]), "headline_label": "First-year margin available a year",
        "detail": [
            {"label": "New members a week", "value": f"{metrics['new_customers']['latest']['value']:,.0f}"},
            {"label": "Value of one", "value": f"${econ['value']['first_year_margin_mean']:,.0f}"},
            {"label": "Extra customers a year", "value": f"{b40['extra_customers']:,.0f}"},
            {"label": "Cost per customer", "value": f"${b40['cost_per_customer_scorecard']:,.0f}, was ${b40['cost_per_customer_random']:,.0f}"}],
        "action": "Order the outreach list by the propensity scorecard before the next campaign.",
        "value_at_stake": b40["extra_first_year_margin"]}

    # Project 3: how much of the base can be personalised
    seg = json.loads((P / "03-segmentation-personas" / "outputs" / "segmentation_metrics.json").read_text())
    use = json.loads((P / "03-segmentation-personas" / "outputs" / "usefulness.json").read_text())
    models["personas"] = {
        "title": "Who we can personalise to", "source": "Project 3: segmentation and personas",
        "headline": f"{seg['assignment']['share_with_persona']:.0%}", "headline_label": "of active customers carry a persona",
        "detail": [
            {"label": "Personas", "value": ", ".join(use["personas"])},
            {"label": "Still the same a year on", "value": f"{seg['stability']['stayed_when_both_confident']:.0%}"},
            {"label": "Offer relevance", "value": f"{use['relevance']['weighted_lift']:.1f}x"},
            {"label": "With two years of data", "value": f"{seg['assignment']['share_with_persona_24m']:.0%}"}],
        "action": "Extend the purchase window to two years before the next content refresh.",
        "value_at_stake": None}

    # Project 4: is the forecast holding?
    fc = json.loads((P / "04-demand-forecasting" / "outputs" / "backtest.json").read_text())
    tot = fc["final_forecast"]["Total"]
    champ = fc["champion"]["Total"]
    actual = np.array(tot["actual"][0], float)
    pred = np.array(tot["preds"][champ][0], float)
    err = np.abs(actual - pred).sum() / actual.sum()
    models["forecast"] = {
        "title": "Forecast against actual", "source": "Project 4: demand forecasting",
        "headline": f"{err:.1%}", "headline_label": "error over the last 13 forecast weeks",
        "detail": [
            {"label": "Method", "value": champ},
            {"label": "Company level", "value": f"{fc['winner_wape']['Total']:.1%}"},
            {"label": "Store and category level", "value": f"{fc['winner_wape']['Store x Category']:.1%}"},
            {"label": "Weeks forecast ahead", "value": f"{fc['max_horizon']}"}],
        "action": "Order to the 63% service level, not to the forecast itself.",
        "value_at_stake": None,
        "series": {"weeks": tot["weeks"], "actual": [float(v) for v in actual], "forecast": [float(v) for v in pred]}}

    # Project 5: media
    mmm = json.loads((P / "05-marketing-mix-model" / "outputs" / "validation_optimisation.json").read_text())
    plan = mmm["optimisation"]["plans"][3]
    models["media"] = {
        "title": "Media", "source": "Project 5: marketing mix model",
        "headline": money(plan["true_gain"]), "headline_label": "a year from reallocating the same budget",
        "detail": [
            {"label": "Media spend a year", "value": f"${mmm['optimisation']['annual_budget']/1e6:.1f}M"},
            {"label": "Media's share of sales", "value": f"{mmm['truth']['total_incremental_share']:.1%}"},
            {"label": "Margin per media dollar", "value": f"${mmm['optimisation']['current_annual_margin_roi_true']:.2f}"},
            {"label": "Biggest move", "value": "Flyer +48%, Display -38%"}],
        "action": "Run two-depth holdouts before acting on any channel-level number.",
        "value_at_stake": plan["true_gain"]}
    res["models"] = models

    # ---------------------------------------------------------------- alerts
    alerts = []
    for key, m in metrics.items():
        lat, p13 = m["latest"], m["periods"]["13"]
        if lat["flag"]:
            direction = "above" if lat["z"] > 0 else "below"
            good = (lat["z"] > 0) == (m["good"] == "up")
            alerts.append({
                "severity": "high" if abs(lat["z"]) >= 3 else "medium",
                "kind": "Control signal", "metric": m["label"], "owner": m["owner"],
                "title": f"{m['label']} is {direction} its seasonal baseline",
                "body": f"{m['label']} is {lat['flag']}. The latest week is {fmt(lat['value'], m['unit'])} "
                        f"against an expected {fmt(lat['expected'], m['unit'])}. This is a pattern, not a single odd week.",
                "good_news": bool(good), "score": abs(lat["z"]) * 2})
        elif p13["is_real"]:
            good = (p13["change"] > 0) == (m["good"] == "up")
            alerts.append({
                "severity": "medium" if not good else "low",
                "kind": "Sustained change", "metric": m["label"], "owner": m["owner"],
                "title": f"{m['label']} is {abs(p13['change_pct']):.1%} {'up' if p13['change'] > 0 else 'down'} on the quarter",
                "body": f"The last 13 weeks averaged {fmt(p13['current'], m['unit'])} against "
                        f"{fmt(p13['previous'], m['unit'])} in the 13 before. The gap is larger than normal "
                        f"week-to-week variation would produce.",
                "good_news": bool(good), "score": abs(p13["t"])})

    for s in sig["slices"]:
        if s["flag"]:
            alerts.append({
                "severity": "medium", "kind": "Where it is happening", "metric": f"{s['dimension']}: {s['slice']}",
                "owner": "Commercial", "title": f"{s['slice']} is behaving unusually for the time of year",
                "body": f"{s['slice']} revenue is {abs(s['z']):.1f} standard deviations "
                        f"{'above' if s['z'] > 0 else 'below'} its own seasonal baseline ({s['flag']}). "
                        f"It is {s['share']:.1%} of {s['dimension'].lower()} revenue.",
                "good_news": bool(s["z"] > 0), "score": abs(s["z"]) * 1.5})

    # the seasonal trap, stated explicitly: a big move that is entirely normal
    worst = min(sig["slices"], key=lambda s: s["change_13w_pct"])
    if worst["change_13w_pct"] < -0.2 and abs(worst["z"]) < 1:
        alerts.append({
            "severity": "info", "kind": "Not a problem", "metric": f"{worst['dimension']}: {worst['slice']}",
            "owner": "Commercial",
            "title": f"{worst['slice']} is down {abs(worst['change_13w_pct']):.0%} and that is normal",
            "body": f"{worst['slice']} revenue has fallen {abs(worst['change_13w_pct']):.0%} against the previous "
                    f"quarter, which looks alarming on a standard report. Against its own seasonal pattern it is "
                    f"{abs(worst['z']):.1f} standard deviations from where it should be, which is to say exactly where "
                    f"it should be. No action needed.",
            "good_news": True, "score": 0.5})

    # model-driven items
    alerts.append({"severity": "medium", "kind": "Model", "metric": "Customers at risk", "owner": "Marketing",
                   "title": f"{money(models['retention']['value_at_stake'])} of margin sits with customers likely to lapse",
                   "body": f"The churn model expects {var['expected_churners']:,.0f} active customers to stop buying "
                           f"within six months. Nearly half that value sits with the top tenth, so the list is workable.",
                   "good_news": False, "score": 3.0})
    alerts.append({"severity": "low", "kind": "Model", "metric": "Media", "owner": "Marketing",
                   "title": f"{money(models['media']['value_at_stake'])} a year available from the same media budget",
                   "body": "The mix model, calibrated on in-market tests, puts more weight on flyer and email and "
                           "less on display. The gain is real but modest, and depends on the tests being repeated.",
                   "good_news": True, "score": 2.0})

    alerts.sort(key=lambda a: (-a["score"]))
    res["alerts"] = alerts
    res["alert_counts"] = {s: sum(1 for a in alerts if a["severity"] == s) for s in ["high", "medium", "low", "info"]}

    (OUT / "alerts_models.json").write_text(json.dumps(res, indent=2, default=float))
    print("as of", res["as_of_date"], "| alerts", res["alert_counts"])
    for a in alerts:
        print(f"  [{a['severity']:6}] {a['kind']:22} {a['title']}")
    for k, m in models.items():
        print(f"\n{m['title']}: {m['headline']} {m['headline_label']}")


def fmt(v, unit):
    if unit == "cad":
        return f"${v:,.0f}"
    if unit == "pct":
        return f"{v:.1%}"
    return f"{v:,.0f}"


if __name__ == "__main__":
    main()
