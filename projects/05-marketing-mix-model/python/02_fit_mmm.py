"""
02_fit_mmm.py
Fits the marketing mix model, and then shows what it cannot know.

  1. Carry-over and saturation are searched per channel on out-of-time error
  2. The model is written the way the business works: a base that media
     multiplies, so contributions add up to sales exactly
  3. The same data is fitted from several honest starting points, which is how
     the identification problem becomes visible instead of staying hidden
  4. One simulated in-market test is used to pin a channel, and the whole model
     is refitted around it
"""
import json

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from common import CHANNELS, CHANNEL_NAMES, DECAYS, HALF_SAT, MARGIN_RATE, OUT, REPO, SHAPES, WORK
from experiment import run_holdout
from mmm import base_design, fit_mmm, transform

FOLDS = [(0, 104), (0, 117), (0, 130), (0, 143)]
TEST_LEN = 13
PRIOR_LAMBDA = 0.3          # how hard the split is pulled toward the split of spend


def wape(a, f):
    return float(np.abs(a - f).sum() / a.sum())


def loglinear(y, B, S):
    X = np.column_stack([np.ones(len(y)), B, S])
    return np.linalg.lstsq(X, np.log(y), rcond=None)[0]


def build_S(d, params, cache=None):
    cols, halfs = [], {}
    for c in CHANNELS:
        p = params[c]
        s, half = cache[(c, p["decay"], p["shape"], p["half_mult"])] if cache else \
            transform(d[c].to_numpy(float), p["decay"], p["shape"], p["half_mult"])
        cols.append(s)
        halfs[c] = half
    return np.column_stack(cols), halfs


def cv_error(d, y, B, params, cache):
    """Out-of-time error, scored with a fast log-linear stand-in during the search."""
    S, _ = build_S(d, params, cache)
    errs = []
    for a, b in FOLDS:
        tr, te = slice(a, b), slice(b, min(b + TEST_LEN, len(y)))
        co = loglinear(y[tr], B[tr], S[tr])
        pred = np.exp(np.column_stack([np.ones(te.stop - te.start), B[te], S[te]]) @ co)
        errs.append(wape(y[te], pred))
    return float(np.mean(errs))


def summarise(d, S, halfs, params, m, label):
    """Spend, contribution, return, and the return on the next dollar."""
    rows = []
    total_spend = d[CHANNELS].sum().sum()
    for i, c in enumerate(CHANNELS):
        x = d[c].to_numpy(float)
        p = params[c]
        inc = m["contrib"][:, i].sum()
        bump = 0.01 * x.mean()
        s_now, _ = transform(x, p["decay"], p["shape"], p["half_mult"])
        s_up, _ = transform(x + bump, p["decay"], p["shape"], p["half_mult"])
        d_rev = float((m["base"] * m["beta"][i] * (s_up - s_now)).sum())
        rows.append({
            "channel": CHANNEL_NAMES[c], "spend": float(x.sum()), "spend_share": float(x.sum() / total_spend),
            "incremental_revenue": float(inc), "contribution_share": float(inc / d.revenue.sum()),
            "roi": float(inc / x.sum()), "margin_roi": float(inc * MARGIN_RATE / x.sum()),
            "marginal_roi": float(d_rev / (bump * len(x))),
            "marginal_margin_roi": float(d_rev * MARGIN_RATE / (bump * len(x))),
            "beta": float(m["beta"][i]), "saturation_now": float(s_now.mean()),
            "half_saturation_weekly_spend": float(halfs[c] * (1 - p["decay"])),
            "avg_weekly_spend": float(x.mean()), "model": label, **p})
    return rows


def main():
    d = pd.read_parquet(WORK / "mmm_base.parquet").sort_values("t").reset_index(drop=True)
    truth = json.loads((REPO / "data" / "full" / "truth" / "ground_truth.json").read_text())["mmm"]
    res = {"weeks": len(d), "period": [str(d.week_start.iloc[0]), str(d.week_start.iloc[-1])],
           "prior_lambda": PRIOR_LAMBDA}

    gaps = int((d.display == 0).sum())
    d.loc[d.display == 0, "display"] = np.nan
    d["display"] = d.display.interpolate().bfill().ffill()
    res["display_weeks_interpolated"] = gaps

    y = d.revenue.to_numpy(float)
    B, base_names = base_design(d)
    res["base_terms"] = base_names
    spend = d[CHANNELS].sum().to_numpy(float)
    share = spend / spend.sum()

    # ---- 1. search the transforms -----------------------------------------
    cache = {(c, dec, sh, hm): transform(d[c].to_numpy(float), dec, sh, hm)
             for c in CHANNELS for dec in DECAYS for sh in SHAPES for hm in HALF_SAT}
    params = {c: {"decay": 0.3, "shape": 1.4, "half_mult": 1.0} for c in CHANNELS}
    best = cv_error(d, y, B, params, cache)
    history = []
    for sweep in range(4):
        improved = False
        for c in CHANNELS:
            keep = dict(params[c])
            for dec in DECAYS:
                for sh in SHAPES:
                    for hm in HALF_SAT:
                        params[c] = {"decay": dec, "shape": sh, "half_mult": hm}
                        e = cv_error(d, y, B, params, cache)
                        if e < best - 1e-7:
                            best, keep, improved = e, dict(params[c]), True
            params[c] = keep
        history.append({"sweep": sweep + 1, "cv_wape": best})
        if not improved:
            break
    S, halfs = build_S(d, params, cache)
    res["transform_search"] = {"sweeps": history, "cv_wape": best,
                               "chosen": {CHANNEL_NAMES[c]: params[c] for c in CHANNELS}}

    # ---- 2. the identification problem ------------------------------------
    # Several starting points, all honest, all fitting the data equally well.
    starts = {"no media to begin with": np.zeros(len(CHANNELS)),
              "a modest effect, split like spend": share * 0.3,
              "a large effect, split like spend": share * 1.5,
              "every channel equal": np.full(len(CHANNELS), 0.08)}
    multi = []
    for label, b0 in starts.items():
        mm = fit_mmm(y, B, S, beta_init=b0)
        multi.append({"start": label, "r2": mm["r2"], "wape": wape(y, mm["fitted"]),
                      "incremental_revenue": float(mm["contrib"].sum()),
                      "incremental_share": float(mm["contrib"].sum() / y.sum()),
                      "blended_roi": float(mm["contrib"].sum() / spend.sum()),
                      "roi": {CHANNEL_NAMES[c]: float(mm["contrib"][:, i].sum() / spend[i])
                              for i, c in enumerate(CHANNELS)}})
    lo, hi = min(m["incremental_revenue"] for m in multi), max(m["incremental_revenue"] for m in multi)
    res["identification"] = {
        "starts": multi, "range_incremental_revenue": [lo, hi], "ratio": float(hi / max(lo, 1)),
        "r2_spread": float(max(m["r2"] for m in multi) - min(m["r2"] for m in multi)),
        "note": "same data, same transforms, same fit quality, very different answers"}

    # how far is each channel from being separable from the base and from each other?
    res["collinearity"] = {
        CHANNEL_NAMES[c]: {"r2_on_base_terms": float(LinearRegression().fit(B, S[:, i]).score(B, S[:, i])),
                           "r2_on_other_channels": float(LinearRegression().fit(np.delete(S, i, 1), S[:, i])
                                                         .score(np.delete(S, i, 1), S[:, i]))}
        for i, c in enumerate(CHANNELS)}

    # ---- 3. the model a client would be given without a test ---------------
    uncal = fit_mmm(y, B, S, beta_init=share * 0.3, prior_share=share, lam=PRIOR_LAMBDA)
    res["uncalibrated"] = {"r2": uncal["r2"], "wape": wape(y, uncal["fitted"]),
                           "incremental_revenue": float(uncal["contrib"].sum()),
                           "channels": summarise(d, S, halfs, params, uncal, "uncalibrated")}

    # ---- 4. one in-market test, and the model refitted around it -----------
    # The model itself says which channels need a test: the ones whose spend
    # pattern is nearly a copy of the trading calendar.
    needs_test = sorted(res["collinearity"], key=lambda c: -res["collinearity"][c]["r2_on_base_terms"])[:2]
    res["channels_needing_a_test"] = needs_test
    test_weeks = np.arange(len(d) - 26, len(d) - 13)
    tests = {}
    for ch in needs_test:
        tests[ch] = run_holdout(d[TRUE_TO_COL[ch]], ch, truth, test_weeks, base_revenue=uncal["base"])
    res["experiment"] = tests

    def calibrated(channels):
        cal = [(CHANNELS.index(TRUE_TO_COL[ch]), tests[ch]["measured_incremental_revenue"],
                tests[ch]["standard_error"], test_weeks) for ch in channels]
        return fit_mmm(y, B, S, beta_init=share * 0.3, prior_share=share, lam=PRIOR_LAMBDA, calibration=cal)

    cal_tv = calibrated(needs_test[:1])
    cal_two = calibrated(needs_test)
    res["calibrated_tv"] = {"r2": cal_tv["r2"], "wape": wape(y, cal_tv["fitted"]),
                            "incremental_revenue": float(cal_tv["contrib"].sum()),
                            "channels": summarise(d, S, halfs, params, cal_tv, "calibrated on one test")}
    res["calibrated_two"] = {"r2": cal_two["r2"], "wape": wape(y, cal_two["fitted"]),
                             "incremental_revenue": float(cal_two["contrib"].sum()),
                             "channels": summarise(d, S, halfs, params, cal_two, "calibrated on two tests")}

    # ---- 5. decomposition and diagnostics for the calibrated model ---------
    m = cal_two
    res["headline_model"] = "calibrated on two tests"
    res["decomposition"] = {
        "weeks": [str(w) for w in d.week_start], "revenue": [float(v) for v in y],
        "base": [float(v) for v in m["base"]],
        "channels": {CHANNEL_NAMES[c]: [float(v) for v in m["contrib"][:, i]] for i, c in enumerate(CHANNELS)},
        "reconciliation_error": float(np.abs(m["base"] + m["contrib"].sum(1) - m["fitted"]).max())}
    res["totals"] = {"revenue": float(y.sum()), "base_revenue": float(m["base"].sum()),
                     "incremental_revenue": float(m["contrib"].sum()), "media_spend": float(spend.sum()),
                     "incremental_share": float(m["contrib"].sum() / y.sum()),
                     "blended_roi": float(m["contrib"].sum() / spend.sum()),
                     "blended_margin_roi": float(m["contrib"].sum() * MARGIN_RATE / spend.sum())}
    resid = y - m["fitted"]
    res["fit"] = {"r2": m["r2"], "wape": wape(y, m["fitted"]),
                  "mape": float(np.abs(y / m["fitted"] - 1).mean()),
                  "durbin_watson": float(np.sum(np.diff(resid) ** 2) / np.sum(resid ** 2))}
    res["base_coefficients"] = {n: float(v) for n, v in zip(["intercept"] + base_names, m["theta"])}

    folds = []
    cal_all = [(CHANNELS.index(TRUE_TO_COL[ch]), tests[ch]["measured_incremental_revenue"],
                tests[ch]["standard_error"], test_weeks) for ch in needs_test]
    for a, b in FOLDS:
        tr, te = slice(a, b), slice(b, min(b + TEST_LEN, len(y)))
        cal_in = [(i, mv, se, mask[mask < b]) for i, mv, se, mask in cal_all if (mask < b).any()]
        fm = fit_mmm(y[tr], B[tr], S[tr], beta_init=share * 0.3, prior_share=share, lam=PRIOR_LAMBDA,
                     calibration=cal_in or None)
        pred = np.exp(fm["theta"][0] + B[te] @ fm["theta"][1:]) * (1.0 + S[te] @ fm["beta"])
        folds.append({"train_weeks": b - a, "test_from": str(d.week_start.iloc[b]), "wape": wape(y[te], pred),
                      "bias": float((pred - y[te]).sum() / y[te].sum()),
                      "beta": {CHANNEL_NAMES[c]: float(fm["beta"][i]) for i, c in enumerate(CHANNELS)}})
    res["validation"] = {"folds": folds, "mean_wape": float(np.mean([f["wape"] for f in folds]))}
    res["coefficient_stability"] = {
        CHANNEL_NAMES[c]: {"full_sample": float(m["beta"][i]),
                           "fold_min": float(min(f["beta"][CHANNEL_NAMES[c]] for f in folds)),
                           "fold_max": float(max(f["beta"][CHANNEL_NAMES[c]] for f in folds))}
        for i, c in enumerate(CHANNELS)}

    alts = {"as specified": {r["channel"]: r["roi"] for r in res["calibrated_two"]["channels"]}}
    for label, drop in [("without the price control", ["price_index"]),
                        ("without the holiday flags", ["peak_holiday", "back_to_school"]),
                        ("without any seasonality", [n for n in base_names if n.startswith(("sin", "cos"))])]:
        keep = [i for i, n in enumerate(base_names) if n not in drop]
        am = fit_mmm(y, B[:, keep], S, beta_init=share * 0.3, prior_share=share, lam=PRIOR_LAMBDA, calibration=cal_all)
        alts[label] = {CHANNEL_NAMES[c]: float(am["contrib"][:, i].sum() / spend[i]) for i, c in enumerate(CHANNELS)}
    res["specification_sensitivity"] = alts

    np.save(WORK / "S.npy", S)
    np.save(WORK / "B.npy", B)
    np.save(WORK / "y.npy", y)
    (WORK / "params.json").write_text(json.dumps({c: params[c] for c in CHANNELS}))
    (WORK / "models.json").write_text(json.dumps({
        "uncalibrated": {"beta": uncal["beta"].tolist(), "theta": uncal["theta"].tolist()},
        "calibrated_tv": {"beta": cal_tv["beta"].tolist(), "theta": cal_tv["theta"].tolist()},
        "calibrated_two": {"beta": cal_two["beta"].tolist(), "theta": cal_two["theta"].tolist()},
        "halfs": halfs, "test_weeks": test_weeks.tolist()}))
    (OUT / "mmm_fit.json").write_text(json.dumps(res, indent=2, default=float))

    pd.set_option("display.width", 250)
    print("transforms", {CHANNEL_NAMES[c]: params[c] for c in CHANNELS})
    print("\nidentification: incremental revenue by starting point")
    print(pd.DataFrame(multi)[["start", "r2", "incremental_revenue", "incremental_share", "blended_roi"]].round(4).to_string())
    print("\ncollinearity", {k: {kk: round(vv, 2) for kk, vv in v.items()} for k, v in res["collinearity"].items()})
    for key in ["uncalibrated", "calibrated_tv", "calibrated_two"]:
        print(f"\n{key}: inc ${res[key]['incremental_revenue']/1e6:.1f}m r2 {res[key]['r2']:.4f}")
        print(pd.DataFrame(res[key]["channels"])[["channel", "spend_share", "contribution_share", "roi", "marginal_roi", "saturation_now"]].round(3).to_string())
    print("\ntests", {k: {kk: round(vv, 1) if isinstance(vv, float) else vv for kk, vv in v.items()} for k, v in tests.items()})
    print("validation", round(res["validation"]["mean_wape"], 4), "| DW", round(res["fit"]["durbin_watson"], 2))


TRUE_TO_COL = {"TV": "tv", "Paid Search": "paid_search", "Paid Social": "paid_social",
               "Display": "display", "Flyer": "flyer", "Email": "email"}

if __name__ == "__main__":
    main()
