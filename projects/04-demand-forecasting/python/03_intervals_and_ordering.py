"""
03_intervals_and_ordering.py
Three questions a point forecast cannot answer.

  1. How wrong is the forecast likely to be, and are the stated ranges honest?
  2. Should each level be forecast directly, or added up from below, or split from above?
  3. How much does it cost to order to the forecast instead of to the right quantile?

The intervals are built on the first five forecast origins and tested on the last
five, so nothing is judged on data that shaped it.
"""
import json

import numpy as np
import pandas as pd

from common import (FIRST_ORIGIN, LEVELS, MARGIN_RATE, MARKDOWN_RATE, MAX_HORIZON,
                    N_ORIGINS, ORIGIN_STEP, OUT, WORK)
from features import build
from importlib import import_module

bt = import_module("02_backtest")


def wide(series, level):
    d = series[series.level == level].pivot(index="series_id", columns="t", values="revenue")
    return d.index.to_numpy(), d.to_numpy(float)


def champion_forecast(name, Y, X, X_cal, X_seas, woy, flyer, origin, h):
    """Re-create whichever method won at this level in the backtest."""
    if name == "Same week last year, level adjusted":
        return Y[:, h - 52] * (Y[:, origin - 8:origin].mean(1) / np.maximum(Y[:, origin - 60:origin - 52].mean(1), 1.0))[:, None]
    if name == "Seasonality and trading calendar (ridge)":
        return bt.ridge_forecast(Y, X_cal, origin, h)
    if name == "Seasonality only (ridge)":
        return bt.ridge_forecast(Y, X_seas, origin, h)
    if name == "Last year and calendar combined":
        naive = Y[:, h - 52] * (Y[:, origin - 8:origin].mean(1) / np.maximum(Y[:, origin - 60:origin - 52].mean(1), 1.0))[:, None]
        return 0.5 * (naive + bt.ridge_forecast(Y, X_cal, origin, h))
    raise ValueError(name)


def main():
    series = pd.read_parquet(WORK / "series.parquet")
    cal = pd.read_parquet(WORK / "calendar.parquet").sort_values("t").reset_index(drop=True)
    back = json.loads((OUT / "backtest.json").read_text())
    champ = back["champion"]
    X, _ = build(cal)
    X_cal, _ = build(cal, blocks=("seasonality", "calendar"))
    X_seas, _ = build(cal, blocks=("seasonality",))
    woy, flyer = cal.week_of_year.to_numpy(int), cal.flyer_week.to_numpy(float)
    origins = [FIRST_ORIGIN + i * ORIGIN_STEP for i in range(N_ORIGINS)]
    fit_origins, test_origins = origins[:5], origins[5:]
    res = {"champion": champ, "fit_origins": fit_origins, "test_origins": test_origins,
           "assumptions": {"margin_rate": MARGIN_RATE, "markdown_rate": MARKDOWN_RATE}}

    # ---- collect champion forecasts for every level and origin -------------
    collected = {}
    for level in LEVELS:
        ids, Y = wide(series, level)
        recs = []
        for origin in origins:
            h = np.arange(origin, min(origin + MAX_HORIZON, Y.shape[1]))
            p = champion_forecast(champ[level], Y, X, X_cal, X_seas, woy, flyer, origin, h)
            recs.append({"origin": origin, "weeks": h, "actual": Y[:, h], "pred": np.maximum(p, 1.0)})
        collected[level] = {"ids": ids, "recs": recs}

    # ---- 1. intervals -------------------------------------------------------
    QS = [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95]
    res["intervals"] = {}
    for level in LEVELS:
        fit = np.concatenate([(r["actual"] / r["pred"]).ravel() for r in collected[level]["recs"] if r["origin"] in fit_origins])
        q = {str(p): float(np.quantile(fit, p)) for p in QS}
        test = [r for r in collected[level]["recs"] if r["origin"] in test_origins]
        ratios = np.concatenate([(r["actual"] / r["pred"]).ravel() for r in test])
        cover = {"80%": float(((ratios >= q["0.1"]) & (ratios <= q["0.9"])).mean()),
                 "90%": float(((ratios >= q["0.05"]) & (ratios <= q["0.95"])).mean()),
                 "50%": float(((ratios >= q["0.25"]) & (ratios <= q["0.75"])).mean())}
        # does the spread widen the further ahead we look?
        byh = []
        for hh in range(1, MAX_HORIZON + 1):
            v = np.concatenate([(r["actual"][:, k] / r["pred"][:, k]).ravel()
                                for r in test for k, w in enumerate(r["weeks"]) if w - r["origin"] + 1 == hh])
            byh.append({"horizon": hh, "p10": float(np.quantile(v, 0.1)), "p90": float(np.quantile(v, 0.9))})
        res["intervals"][level] = {"quantiles": q, "coverage_out_of_sample": cover, "spread_by_horizon": byh,
                                   "band_80_pct_of_forecast": [q["0.1"], q["0.9"]]}

    # ---- 2. direct, bottom-up or top-down? ---------------------------------
    cat_ids, Ycat = wide(series, "Category")
    sxc_ids, Ysxc = wide(series, "Store x Category")
    tot_ids, Ytot = wide(series, "Total")
    sxc_cat = np.array([s.split(" | ")[1] for s in sxc_ids])
    rows = []
    for origin in test_origins:
        h = np.arange(origin, min(origin + MAX_HORIZON, Ycat.shape[1]))
        actual = Ycat[:, h]
        direct = champion_forecast(champ["Category"], Ycat, X, X_cal, X_seas, woy, flyer, origin, h)
        sxc = champion_forecast(champ["Store x Category"], Ysxc, X, X_cal, X_seas, woy, flyer, origin, h)
        # store x category covers in-store sales only, so scale it to the whole channel mix
        bottom = np.vstack([sxc[sxc_cat == c].sum(0) for c in cat_ids])
        scale = (Ycat[:, origin - 52:origin].sum(1) /
                 np.vstack([Ysxc[sxc_cat == c].sum(0) for c in cat_ids])[:, origin - 52:origin].sum(1))
        bottom = bottom * scale[:, None]
        top = champion_forecast(champ["Total"], Ytot, X, X_cal, X_seas, woy, flyer, origin, h)
        share = Ycat[:, origin - 52:origin].sum(1) / Ytot[0, origin - 52:origin].sum()
        topdown = top[0][None, :] * share[:, None]
        for name, p in [("Forecast each category directly", direct), ("Add up store x category", bottom),
                        ("Split the company forecast", topdown)]:
            rows.append({"approach": name, "origin": origin,
                         "wape": float(np.abs(p - actual).sum() / actual.sum())})
    rec = pd.DataFrame(rows).groupby("approach").wape.mean()
    res["reconciliation"] = {"level": "Category", "wape": rec.round(5).to_dict(),
                             "best": rec.idxmin(), "note": "measured on the five forecast origins held back from fitting the intervals"}

    # ---- 3. the ordering decision ------------------------------------------
    # Demand is expressed in revenue at full price, so the costs below are in CAD.
    level = "Store x Category"
    q_fit = res["intervals"][level]["quantiles"]
    test = [r for r in collected[level]["recs"] if r["origin"] in test_origins]
    actual = np.concatenate([r["actual"].ravel() for r in test])
    pred = np.concatenate([r["pred"].ravel() for r in test])
    fit = np.concatenate([(r["actual"] / r["pred"]).ravel() for r in collected[level]["recs"] if r["origin"] in fit_origins])
    weeks_covered = len(test) * MAX_HORIZON
    optimal_sl = MARGIN_RATE / (MARGIN_RATE + MARKDOWN_RATE)

    def cost_for(p_test, r_fit, alpha, shrink=1.0):
        """Order to a quantile of the forecast's own error distribution, then count the damage."""
        ratios = 1.0 + (r_fit - 1.0) * shrink
        order = p_test * np.quantile(ratios, alpha)
        short = np.maximum(actual - order, 0).sum() * MARGIN_RATE
        over = np.maximum(order - actual, 0).sum() * MARKDOWN_RATE
        return {"service_level": alpha, "lost_margin": float(short), "markdown": float(over),
                "total": float(short + over), "fill_rate": float(np.minimum(order, actual).sum() / actual.sum())}

    def cost(alpha):
        return cost_for(pred, fit, alpha)

    curve = [cost(a) for a in np.round(np.arange(0.40, 0.96, 0.05), 2)]
    at_mean = cost(0.5)
    best = min(curve, key=lambda c: c["total"])
    theory = cost(round(optimal_sl, 2))

    # the same ordering rule run on the benchmark forecast, to price the modelling work
    ids_s, Ys = wide(series, level)
    naive_test = np.concatenate([Ys[:, np.arange(o, min(o + MAX_HORIZON, Ys.shape[1])) - 52].ravel() for o in test_origins])
    naive_fit = np.concatenate([(Ys[:, np.arange(o, min(o + MAX_HORIZON, Ys.shape[1]))] /
                                 np.maximum(Ys[:, np.arange(o, min(o + MAX_HORIZON, Ys.shape[1])) - 52], 1.0)).ravel()
                                for o in fit_origins])
    naive_cost = min((cost_for(np.maximum(naive_test, 1.0), naive_fit, a)
                      for a in np.round(np.arange(0.40, 0.96, 0.05), 2)), key=lambda c: c["total"])
    # what would a forecast half as wrong be worth? Build one by halving each log error,
    # then order with the error distribution that forecast would have had.
    pred_half = actual * (pred / actual) ** 0.5
    half_error = cost_for(np.maximum(pred_half, 1.0), fit ** 0.5, round(optimal_sl, 2))
    per_store_week = len(sxc_ids) * weeks_covered
    res["ordering"] = {
        "optimal_service_level_theory": optimal_sl, "curve": curve, "order_to_forecast": at_mean,
        "order_to_best_quantile": best, "order_to_theoretical_quantile": theory,
        "saving_vs_forecast": at_mean["total"] - theory["total"],
        "saving_vs_forecast_annualised": (at_mean["total"] - theory["total"]) / per_store_week * len(sxc_ids) * 52,
        "weeks_evaluated": weeks_covered, "series": len(sxc_ids),
        "note": "demand measured as revenue at full price; a unit short costs the margin, a unit over costs the markdown"}

    per_week = lambda v: v / weeks_covered * 52                      # one planning week, scaled to a year
    res["ordering"].update({
        "order_on_seasonal_naive": naive_cost,
        "saving_vs_seasonal_naive": naive_cost["total"] - theory["total"],
        "saving_vs_seasonal_naive_annualised": per_week(naive_cost["total"] - theory["total"]),
        "cost_if_error_halved": half_error, "value_of_halving_error_annualised": per_week(theory["total"] - half_error["total"]),
        "cost_as_share_of_revenue": theory["total"] / actual.sum(),
        "annual_cost_of_uncertainty": per_week(theory["total"])})
    res["ordering"]["saving_vs_forecast_annualised"] = per_week(at_mean["total"] - theory["total"])

    (OUT / "intervals_ordering.json").write_text(json.dumps(res, indent=2, default=float))
    pd.set_option("display.width", 220)
    for level in LEVELS:
        iv = res["intervals"][level]
        print(level, "80% band", [round(v, 3) for v in iv["band_80_pct_of_forecast"]], "coverage", {k: round(v, 3) for k, v in iv["coverage_out_of_sample"].items()})
    print("\nreconciliation", {k: round(v, 4) for k, v in res["reconciliation"]["wape"].items()}, "best:", res["reconciliation"]["best"])
    print("\noptimal service level", round(optimal_sl, 3))
    print(pd.DataFrame(curve).round(2).to_string())
    print("order to forecast", {k: round(v, 3) if isinstance(v, float) else v for k, v in at_mean.items()})
    print("order to theory  ", {k: round(v, 3) if isinstance(v, float) else v for k, v in theory.items()})
    print("order on naive    ", {k: round(v, 3) if isinstance(v, float) else v for k, v in naive_cost.items()})
    print("quantile saving a year", round(res["ordering"]["saving_vs_forecast_annualised"]),
          "| model vs naive a year", round(res["ordering"]["saving_vs_seasonal_naive_annualised"]),
          "| halving error a year", round(res["ordering"]["value_of_halving_error_annualised"]))
    print("annual cost of uncertainty", round(res["ordering"]["annual_cost_of_uncertainty"]),
          "| as share of revenue", round(res["ordering"]["cost_as_share_of_revenue"], 4))


if __name__ == "__main__":
    main()
