"""
03_economics.py
Turns the scores into decisions.

  1. What a new customer is worth (measured first-year margin)
  2. How many more customers a ranked list finds at any outreach budget
  3. What happens to the business case if only part of the conversions are caused by outreach
  4. Lead-source economics, and whether source or profile matters more
  5. The holdout test needed to measure incrementality
"""
import json

import numpy as np
import pandas as pd

from common import COST_PER_CONTACT, COST_PER_LEAD, OUT, SEED, WORK


def main():
    s = pd.read_parquet(WORK / "test_scores.parquet")
    val = pd.read_parquet(WORK / "new_customer_value.parquet")
    metrics = json.loads((OUT / "model_metrics.json").read_text())
    y, n = s.converted_flag.values, len(s)
    days = (s.first_contact_date.max() - s.first_contact_date.min()).days + 1
    annual = 365 / days                                          # scale the test period to a year
    V = float(val.margin_first_year.mean())
    res = {"assumptions": {"cost_per_contact": COST_PER_CONTACT, "cost_per_lead": COST_PER_LEAD},
           "prospects_per_year": n * annual, "converters_per_year": y.sum() * annual, "test_days": days,
           "value": {"first_year_margin_mean": V, "first_year_margin_median": float(val.margin_first_year.median()),
                     "standard_error": float(val.margin_first_year.sem()), "customers_measured": len(val),
                     "never_ordered": float((val.orders_first_year == 0).mean()),
                     "active_in_second_half": float(val.active_second_half.mean()),
                     "by_source": val.groupby("lead_source").margin_first_year.agg(["size", "mean", "sem"]).round(2).reset_index().to_dict("records")}}

    # ---- 2. cumulative converters found, by ranking method
    rng = np.random.default_rng(SEED)
    rankers = {"Random list": rng.random(n), "Look-alike index": s.s_lookalike.values,
               "Propensity scorecard": s.p_scorecard.values, "Gradient boosting": s.s_boosting.values}
    curves = {}
    for name, score in rankers.items():
        cum = np.cumsum(y[np.argsort(-score, kind="stable")])
        curves[name] = [{"share": k, "contacts": int(n * k / 100), "converters": int(cum[int(n * k / 100) - 1])} for k in range(5, 101, 5)]
    for pt in curves["Random list"]:                              # use the expected value for random, not one noisy draw
        pt["converters"] = round(y.sum() * pt["share"] / 100)
    res["curves"] = curves
    res["budget_scenarios"] = []
    for k in [20, 40, 60, 80]:
        i = k // 5 - 1
        r, m = curves["Random list"][i]["converters"], curves["Propensity scorecard"][i]["converters"]
        res["budget_scenarios"].append({
            "share": k, "contacts_per_year": n * k / 100 * annual, "customers_random": r * annual, "customers_scorecard": m * annual,
            "customers_lookalike": curves["Look-alike index"][i]["converters"] * annual,
            "extra_customers": (m - r) * annual, "extra_first_year_margin": (m - r) * annual * V,
            "cost_per_customer_random": n * k / 100 * COST_PER_CONTACT / r, "cost_per_customer_scorecard": n * k / 100 * COST_PER_CONTACT / m})

    # ---- 3. decile economics and the incrementality question
    d = s.assign(decile=10 - pd.qcut(s.p_scorecard.rank(method="first"), 10, labels=False))
    dec = d.groupby("decile").agg(prospects=("converted_flag", "size"), conversion_rate=("converted_flag", "mean"),
                                  predicted=("p_scorecard", "mean")).reset_index()
    dec["breakeven_incrementality"] = COST_PER_CONTACT / (dec.conversion_rate * V)     # share of conversions outreach must cause
    res["deciles"] = dec.round(4).to_dict("records")
    scen = []
    for a in [1.0, 0.75, 0.5, 0.25]:
        per = y * a * V - COST_PER_CONTACT                                  # realised net value of each contact
        keep = s.p_scorecard.values * a * V > COST_PER_CONTACT              # contact only where it is expected to pay
        scen.append({"incrementality": a, "net_contact_all": per.sum() * annual, "net_with_cutoff": per[keep].sum() * annual,
                     "share_contacted": float(keep.mean()), "gain_from_cutoff": (per[keep].sum() - per.sum()) * annual,
                     "deciles_losing_money": int((dec.conversion_rate * a * V < COST_PER_CONTACT).sum())})
    res["incrementality_scenarios"] = scen

    # ---- 4. lead sources
    src = s.groupby("lead_source").agg(prospects=("converted_flag", "size"), conversion_rate=("converted_flag", "mean")).reset_index()
    src["prospects_per_year"] = src.prospects * annual
    src["cost_per_lead"] = src.lead_source.map(COST_PER_LEAD)
    src["cost_per_customer"] = (src.cost_per_lead + COST_PER_CONTACT) / src.conversion_rate
    src["first_year_return_per_dollar"] = V / src.cost_per_customer
    res["sources"] = src.round(4).to_dict("records")
    d["band"] = pd.qcut(d.p_scorecard.rank(method="first"), 3, labels=["Bottom third", "Middle third", "Top third"])
    mix = d.groupby(["lead_source", "band"], observed=True).converted_flag.agg(["size", "mean"]).round(4).reset_index()
    res["source_by_score"] = mix.to_dict("records")

    # does a higher score also mean a more valuable customer? (converters with a full first year)
    abt = pd.read_parquet(WORK / "prospect_abt.parquet").merge(val[["prospect_id", "margin_first_year"]], on="prospect_id")
    eff = {e["term"]: e["estimate"] for e in metrics["effects"]}
    score = (abt.lead_source.map(lambda v: eff.get(f"lead_source={v}", 0)) + abt.age_band.map(lambda v: eff.get(f"age_band={v}", 0))
             + abt.household_income_band.map(lambda v: eff.get(f"household_income_band={v}", 0)) + eff["web_visits_capped"] * abt.web_visits_capped
             + eff["distance_to_store_km"] * abt.distance_to_store_km / 10 + eff["has_children"] * abt.has_children
             + eff["email_engaged_flag"] * abt.email_engaged_flag)
    abt["third"] = pd.qcut(score.rank(method="first"), 3, labels=["Bottom third", "Middle third", "Top third"])
    res["value_by_score"] = abt.groupby("third", observed=True).margin_first_year.agg(["size", "mean", "sem"]).round(2).reset_index().to_dict("records")
    res["corr_score_value"] = float(np.corrcoef(score, abt.margin_first_year)[0, 1])

    # ---- 5. holdout test design: smallest incremental effect detectable (80% power, 5% two-sided)
    p, zsum, per_year = float(y.mean()), 1.96 + 0.8416, n * annual
    res["test_design"] = [
        {"holdout_share": h, "weeks": w, "holdout_n": per_year * w / 52 * h, "treated_n": per_year * w / 52 * (1 - h),
         "mde_points": zsum * np.sqrt(p * (1 - p) * (1 / (per_year * w / 52 * h) + 1 / (per_year * w / 52 * (1 - h)))),
         "smallest_incrementality_detectable": zsum * np.sqrt(p * (1 - p) * (1 / (per_year * w / 52 * h) + 1 / (per_year * w / 52 * (1 - h)))) / p}
        for h in [0.05, 0.10, 0.20] for w in [13, 26, 52]]

    (OUT / "economics.json").write_text(json.dumps(res, indent=2, default=float))
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    print("value", {k: v for k, v in res["value"].items() if k != "by_source"}, "| per year", round(res["prospects_per_year"]), round(res["converters_per_year"]))
    print(pd.DataFrame(res["budget_scenarios"]).round(1).to_string())
    print(pd.DataFrame(res["deciles"]).to_string())
    print(pd.DataFrame(scen).round(3).to_string())
    print(pd.DataFrame(res["sources"]).round(3).to_string())
    print(mix.pivot(index="lead_source", columns="band", values="mean").round(3).to_string())
    print(pd.DataFrame(res["value_by_score"]).to_string(), res["corr_score_value"])
    print(pd.DataFrame(res["test_design"]).round(4).to_string())


if __name__ == "__main__":
    main()
