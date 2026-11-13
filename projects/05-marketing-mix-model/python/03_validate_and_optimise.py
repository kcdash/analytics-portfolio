"""
03_validate_and_optimise.py
What the model gets right, what it gets wrong, and what that costs.

  1. Every estimate is scored against the response curves the data was built from
  2. The number of in-market tests is varied, which prices experimentation
  3. Tests at two spend depths recover the shape of a curve, not just its height
  4. A constrained budget optimiser is run on each version of the model, and every
     recommendation is then judged on the true curves: the only honest way to ask
     whether a reallocation would actually have worked
"""
import json

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from common import CHANNELS, CHANNEL_NAMES, MARGIN_RATE, OUT, REPO, WORK
from experiment import run_curve_test, run_holdout
from mmm import adstock, base_design, fit_mmm, hill

PRIOR_LAMBDA = 0.3
BOUND = 0.5                 # a channel may move by at most half its current spend
COL = {v: k for k, v in CHANNEL_NAMES.items()}


def steady_lift(x, beta, decay, shape, half):
    return beta * hill(x / max(1 - decay, 1e-6), shape, half)


def annual_revenue(x, betas, params, halfs, base_week, truth=None):
    """Annual incremental revenue from a constant weekly spend vector."""
    tot = 0.0
    for i, c in enumerate(CHANNELS):
        if truth is None:
            tot += steady_lift(x[i], betas[i], params[c]["decay"], params[c]["shape"], halfs[c])
        else:
            tp = truth[CHANNEL_NAMES[c]]
            tot += steady_lift(x[i], tp["max_sales_lift"], tp["adstock_decay"],
                               tp["hill_shape"], tp["hill_half_saturation"])
    return 52.0 * base_week * tot


def optimise(betas, params, halfs, base_week, current, budget, truth=None, bound=BOUND):
    lo, hi = current * (1 - bound), current * (1 + bound)
    neg = lambda x: -annual_revenue(x, betas, params, halfs, base_week, truth) / 1e6
    cons = [{"type": "eq", "fun": lambda x: x.sum() - budget}]
    best, best_val = None, np.inf
    for start in [current, np.full(len(current), budget / len(current)), lo + (hi - lo) * 0.25]:
        s = np.clip(start * budget / start.sum(), lo, hi)
        r = minimize(neg, s, method="SLSQP", bounds=list(zip(lo, hi)), constraints=cons,
                     options={"maxiter": 400, "ftol": 1e-10})
        if r.success and r.fun < best_val:
            best, best_val = r.x, r.fun
    return best if best is not None else current.copy()


def recover_curve(x, test, decay, shape, base, weeks):
    """
    Read a channel's response curve off two holdouts of different depth.

    A single test gives one point and leaves the curve undetermined. Two depths
    pin both how much the channel is worth and how quickly it saturates.
    """
    ad = adstock(x, decay)
    best = None
    for hm in np.linspace(0.1, 4.0, 160):
        half = hm * ad.mean()
        s_full = hill(ad, shape, half)
        num = den = 0.0
        gaps = []
        for cell in test["cells"]:
            s_red = hill(adstock(x * (1 - cell["cut"]), decay), shape, half)
            g = float(((s_full - s_red)[weeks] * base[weeks]).sum())
            gaps.append((g, cell))
            num += g * cell["measured_revenue_lost"] / cell["standard_error"] ** 2
            den += g * g / cell["standard_error"] ** 2
        beta = max(num / max(den, 1e-12), 0.0)
        err = sum(((beta * g - cell["measured_revenue_lost"]) / cell["standard_error"]) ** 2 for g, cell in gaps)
        if best is None or err < best[0]:
            best = (err, hm, beta, half)
    return {"half_mult": best[1], "beta": best[2], "half": best[3]}


def main():
    d = pd.read_parquet(WORK / "mmm_base.parquet").sort_values("t").reset_index(drop=True)
    d.loc[d.display == 0, "display"] = np.nan
    d["display"] = d.display.interpolate().bfill().ffill()
    truth = json.loads((REPO / "data" / "full" / "truth" / "ground_truth.json").read_text())["mmm"]
    fit = json.loads((OUT / "mmm_fit.json").read_text())
    models = json.loads((WORK / "models.json").read_text())
    params = json.loads((WORK / "params.json").read_text())
    halfs = models["halfs"]
    S, B, y = np.load(WORK / "S.npy"), np.load(WORK / "B.npy"), np.load(WORK / "y.npy")
    spend = d[CHANNELS].sum().to_numpy(float)
    share = spend / spend.sum()
    current_week = d[CHANNELS].mean().to_numpy(float)
    theta_cal = np.array(models["calibrated_two"]["theta"])
    base_cal = np.exp(theta_cal[0] + B @ theta_cal[1:])
    base_week = float(base_cal.mean())
    test_weeks = np.array(models["test_weeks"])
    res = {"bound": BOUND, "test_weeks": [str(d.week_start.iloc[i]) for i in [test_weeks[0], test_weeks[-1]]]}

    # ---- 1. the truth -----------------------------------------------------
    true_contrib, true_roi = {}, {}
    for i, c in enumerate(CHANNELS):
        tp = truth[CHANNEL_NAMES[c]]
        lift = tp["max_sales_lift"] * hill(adstock(d[c].to_numpy(float), tp["adstock_decay"]),
                                           tp["hill_shape"], tp["hill_half_saturation"])
        true_contrib[CHANNEL_NAMES[c]] = float((lift * base_cal).sum())
        true_roi[CHANNEL_NAMES[c]] = float((lift * base_cal).sum() / spend[i])
    res["truth"] = {"contribution": true_contrib, "roi": true_roi,
                    "total_incremental": float(sum(true_contrib.values())),
                    "total_incremental_share": float(sum(true_contrib.values()) / y.sum()),
                    "saturation_weekly": {CHANNEL_NAMES[c]: float(truth[CHANNEL_NAMES[c]]["hill_half_saturation"] *
                                                                  (1 - truth[CHANNEL_NAMES[c]]["adstock_decay"]))
                                          for c in CHANNELS},
                    "decay": {CHANNEL_NAMES[c]: truth[CHANNEL_NAMES[c]]["adstock_decay"] for c in CHANNELS},
                    "note": "computed from the response curves the synthetic data was generated with"}

    res["accuracy_vs_truth"] = {}
    for key in ["uncalibrated", "calibrated_tv", "calibrated_two"]:
        est = {r["channel"]: r["roi"] for r in fit[key]["channels"]}
        res["accuracy_vs_truth"][key] = {
            "roi": est,
            "mean_absolute_roi_error": float(np.mean([abs(est[k] - true_roi[k]) / true_roi[k] for k in true_roi])),
            "total_incremental": fit[key]["incremental_revenue"],
            "total_error": float(fit[key]["incremental_revenue"] / res["truth"]["total_incremental"] - 1)}

    # ---- 2. how many tests does it take? ----------------------------------
    order = sorted(fit["collinearity"], key=lambda c: -fit["collinearity"][c]["r2_on_base_terms"])
    single = {ch: run_holdout(d[COL[ch]], ch, truth, test_weeks, base_revenue=base_cal) for ch in order}
    dose, betas_by_n = [], {}
    for n in range(len(order) + 1):
        cal = [(CHANNELS.index(COL[ch]), single[ch]["measured_incremental_revenue"],
                single[ch]["standard_error"], test_weeks) for ch in order[:n]]
        m = fit_mmm(y, B, S, beta_init=share * 0.3, prior_share=share, lam=PRIOR_LAMBDA, calibration=cal or None)
        roi = {CHANNEL_NAMES[c]: float(m["contrib"][:, i].sum() / spend[i]) for i, c in enumerate(CHANNELS)}
        betas_by_n[n] = m["beta"]
        dose.append({"tests": n, "channels_tested": order[:n], "roi": roi, "r2": m["r2"],
                     "mean_absolute_roi_error": float(np.mean([abs(roi[k] - true_roi[k]) / true_roi[k] for k in true_roi])),
                     "total_incremental": float(m["contrib"].sum()),
                     "total_error": float(m["contrib"].sum() / res["truth"]["total_incremental"] - 1)})
    res["experiment_dose_response"] = dose

    # ---- 3. two-depth tests recover the curve, not just its height --------
    curve_tests = {ch: run_curve_test(d[COL[ch]], ch, truth, test_weeks, base_revenue=base_cal) for ch in CHANNEL_NAMES.values()}
    rec, params_c, halfs_c = {}, {}, {}
    beta_c = np.zeros(len(CHANNELS))
    for i, c in enumerate(CHANNELS):
        ch = CHANNEL_NAMES[c]
        r = recover_curve(d[c].to_numpy(float), curve_tests[ch], params[c]["decay"], params[c]["shape"],
                          base_cal, test_weeks)
        params_c[c] = dict(params[c], half_mult=r["half_mult"])
        halfs_c[c] = r["half"]
        beta_c[i] = r["beta"]
        tp = truth[ch]
        rec[ch] = {"saturation_weekly_estimated": float(r["half"] * (1 - params[c]["decay"])),
                   "saturation_weekly_true": float(tp["hill_half_saturation"] * (1 - tp["adstock_decay"])),
                   "saturation_weekly_mmm_only": float(halfs[c] * (1 - params[c]["decay"])),
                   "current_weekly_spend": float(current_week[i]),
                   "beta_estimated": float(r["beta"]), "beta_true": float(tp["max_sales_lift"])}
    res["curve_recovery"] = rec
    res["curve_tests"] = curve_tests

    # ---- 4. response curves ------------------------------------------------
    beta_cal = np.array(models["calibrated_two"]["beta"])
    grid = np.linspace(0.05, 2.5, 50)
    res["response_curves"] = {}
    for i, c in enumerate(CHANNELS):
        xs = grid * current_week[i]
        tp = truth[CHANNEL_NAMES[c]]
        res["response_curves"][CHANNEL_NAMES[c]] = {
            "spend": [float(v) for v in xs],
            "model_only": [float(52 * base_week * steady_lift(x, beta_cal[i], params[c]["decay"], params[c]["shape"], halfs[c])) for x in xs],
            "with_curve_tests": [float(52 * base_week * steady_lift(x, beta_c[i], params_c[c]["decay"], params_c[c]["shape"], halfs_c[c])) for x in xs],
            "truth": [float(52 * base_week * steady_lift(x, tp["max_sales_lift"], tp["adstock_decay"], tp["hill_shape"], tp["hill_half_saturation"])) for x in xs],
            "current_weekly_spend": float(current_week[i])}

    # ---- 5. optimise, then judge every answer on the true curves ----------
    budget = float(current_week.sum())
    cur_true = annual_revenue(current_week, None, params, halfs, base_week, truth=truth)
    best_plan = optimise(None, params, halfs, base_week, current_week, budget, truth=truth)
    best_true = annual_revenue(best_plan, None, params, halfs, base_week, truth=truth)

    plan_specs = [
        ("Model alone, no in-market test", np.array(models["uncalibrated"]["beta"]), params, halfs),
        ("Model plus two single-depth tests", beta_cal, params, halfs),
        ("Model plus five single-depth tests", betas_by_n[5], params, halfs),
        ("Model plus two-depth tests on every channel", beta_c, params_c, halfs_c),
    ]
    plans = []
    for label, b, pp, hh in plan_specs:
        x = optimise(b, pp, hh, base_week, current_week, budget)
        real = annual_revenue(x, None, params, halfs, base_week, truth=truth)
        claimed = annual_revenue(x, b, pp, hh, base_week) - annual_revenue(current_week, b, pp, hh, base_week)
        plans.append({"plan": label, "claimed_gain": float(claimed), "true_gain": float(real - cur_true),
                      "share_of_achievable_gain": float((real - cur_true) / max(best_true - cur_true, 1e-9)),
                      "allocation": {CHANNEL_NAMES[c]: float(x[i]) for i, c in enumerate(CHANNELS)},
                      "change": {CHANNEL_NAMES[c]: float(x[i] / current_week[i] - 1) for i, c in enumerate(CHANNELS)}})
    plans.append({"plan": "Best possible, knowing the true curves", "claimed_gain": None,
                  "true_gain": float(best_true - cur_true), "share_of_achievable_gain": 1.0,
                  "allocation": {CHANNEL_NAMES[c]: float(best_plan[i]) for i, c in enumerate(CHANNELS)},
                  "change": {CHANNEL_NAMES[c]: float(best_plan[i] / current_week[i] - 1) for i, c in enumerate(CHANNELS)}})
    res["optimisation"] = {
        "weekly_budget": budget, "annual_budget": float(budget * 52),
        "current_annual_incremental_true": float(cur_true),
        "current_annual_margin_roi_true": float(cur_true * MARGIN_RATE / (budget * 52)),
        "best_possible_gain": float(best_true - cur_true), "plans": plans,
        "current_allocation": {CHANNEL_NAMES[c]: float(current_week[i]) for i, c in enumerate(CHANNELS)},
        "recommended": plans[3]["allocation"]}

    # ---- 6. what if the budget itself changes? -----------------------------
    scen = []
    for mult in [0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5]:
        x = optimise(beta_c, params_c, halfs_c, base_week, current_week, budget * mult, bound=0.6)
        model_rev = annual_revenue(x, beta_c, params_c, halfs_c, base_week)
        true_rev = annual_revenue(x, None, params, halfs, base_week, truth=truth)
        ann = budget * mult * 52
        scen.append({"budget_multiple": mult, "annual_budget": float(ann),
                     "model_incremental_revenue": float(model_rev), "true_incremental_revenue": float(true_rev),
                     "model_margin_roi": float(model_rev * MARGIN_RATE / ann),
                     "true_margin_roi": float(true_rev * MARGIN_RATE / ann),
                     "allocation": {CHANNEL_NAMES[c]: float(x[i]) for i, c in enumerate(CHANNELS)}})
    res["budget_scenarios"] = scen

    # ---- 7. the decomposition we would actually publish ---------------------
    S_c = np.column_stack([hill(adstock(d[c].to_numpy(float), params_c[c]["decay"]), params_c[c]["shape"], halfs_c[c])
                           for c in CHANNELS])
    m_final = fit_mmm(y, B, S_c, beta_init=beta_c, prior_share=share, lam=0.0,
                      calibration=[(i, (beta_c[i] * S_c[test_weeks, i] * base_cal[test_weeks]).sum(),
                                    max(0.02 * (beta_c[i] * S_c[test_weeks, i] * base_cal[test_weeks]).sum(), 1.0),
                                    test_weeks) for i in range(len(CHANNELS))])
    contrib = m_final["contrib"]
    res["final_model"] = {
        "r2": m_final["r2"], "incremental_revenue": float(contrib.sum()),
        "incremental_share": float(contrib.sum() / y.sum()),
        "total_error_vs_truth": float(contrib.sum() / res["truth"]["total_incremental"] - 1),
        "channels": [{"channel": CHANNEL_NAMES[c], "spend": float(spend[i]), "spend_share": float(share[i]),
                      "incremental_revenue": float(contrib[:, i].sum()),
                      "contribution_share": float(contrib[:, i].sum() / y.sum()),
                      "roi": float(contrib[:, i].sum() / spend[i]),
                      "true_roi": true_roi[CHANNEL_NAMES[c]],
                      "margin_roi": float(contrib[:, i].sum() * MARGIN_RATE / spend[i]),
                      "saturation_now": float(current_week[i] / (current_week[i] + halfs_c[c] * (1 - params_c[c]["decay"]))),
                      "recommended_weekly_spend": plans[3]["allocation"][CHANNEL_NAMES[c]],
                      "recommended_change": plans[3]["change"][CHANNEL_NAMES[c]]}
                     for i, c in enumerate(CHANNELS)],
        "decomposition": {"weeks": [str(w) for w in d.week_start], "revenue": [float(v) for v in y],
                          "base": [float(v) for v in m_final["base"]],
                          "channels": {CHANNEL_NAMES[c]: [float(v) for v in contrib[:, i]] for i, c in enumerate(CHANNELS)}},
        "mean_absolute_roi_error": float(np.mean([abs(contrib[:, i].sum() / spend[i] - true_roi[CHANNEL_NAMES[c]])
                                                  / true_roi[CHANNEL_NAMES[c]] for i, c in enumerate(CHANNELS)]))}

    (WORK / "final_model.json").write_text(json.dumps(
        {"beta": beta_c.tolist(), "halfs": halfs_c, "params": params_c}, default=float))
    (OUT / "validation_optimisation.json").write_text(json.dumps(res, indent=2, default=float))

    pd.set_option("display.width", 250)
    print("true roi", {k: round(v, 2) for k, v in true_roi.items()}, "| total $%.1fm" % (res["truth"]["total_incremental"] / 1e6))
    print(pd.DataFrame(dose)[["tests", "mean_absolute_roi_error", "total_incremental", "total_error", "r2"]].round(4).to_string())
    print("\ncurve recovery")
    print(pd.DataFrame(rec).T[["current_weekly_spend", "saturation_weekly_mmm_only", "saturation_weekly_estimated", "saturation_weekly_true"]].round(0).to_string())
    print("\noptimiser judged on the true curves")
    print(pd.DataFrame(plans)[["plan", "claimed_gain", "true_gain", "share_of_achievable_gain"]].round(3).to_string())
    print(pd.DataFrame([p["change"] for p in plans], index=[p["plan"][:28] for p in plans]).round(2).to_string())
    print("\nfinal model roi err", round(res["final_model"]["mean_absolute_roi_error"], 3),
          "total err", round(res["final_model"]["total_error_vs_truth"], 3))
    print(pd.DataFrame(res["final_model"]["channels"])[["channel", "roi", "true_roi", "saturation_now", "recommended_change"]].round(3).to_string())
    print(pd.DataFrame(scen)[["budget_multiple", "true_incremental_revenue", "true_margin_roi"]].round(3).to_string())


if __name__ == "__main__":
    main()
