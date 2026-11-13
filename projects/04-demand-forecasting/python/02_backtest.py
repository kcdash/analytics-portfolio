"""
02_backtest.py
Rolling-origin backtest at four planning levels.

Ten forecast origins, four weeks apart, each judged up to thirteen weeks ahead.
Five methods, including the two benchmarks a forecasting project should always
have to beat, and a test of whether the media plan is worth including at all.

Nothing in any feature is unknown at the time the forecast is made.
"""
import json

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge

from common import FIRST_ORIGIN, LEVELS, MAX_HORIZON, N_ORIGINS, ORIGIN_STEP, OUT, SEED, WORK
from features import build


def wide(series, level):
    """Series as a matrix: one row per series, one column per week."""
    d = series[series.level == level].pivot(index="series_id", columns="t", values="revenue")
    return d.index.to_numpy(), d.to_numpy(float)


def ridge_forecast(Y, X, origin, horizons, alpha=3.0, anchor=0):
    """
    One ridge per series on log demand, so seasonality and promotions act multiplicatively.

    With anchor=k the forecast is nudged by how far the fit sat above or below the
    last k weeks of actual demand. A long fit gets the shape right and the recent
    weeks get the level right.
    """
    tr = slice(0, origin)
    Xtr, Xte = X[tr], X[horizons]
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
    A, B = (Xtr - mu) / sd, (Xte - mu) / sd
    out = np.empty((len(Y), len(horizons)))
    for i in range(len(Y)):
        y = np.log(np.maximum(Y[i, tr], 1.0))
        m = Ridge(alpha=alpha).fit(A, y)
        shift = float((y[-anchor:] - m.predict(A[-anchor:])).mean()) if anchor else 0.0
        out[i] = np.exp(m.predict(B) + shift)
    return out


def series_traits(Y, woy, flyer, origin):
    """
    Two numbers that say how a particular series behaves, learned from its own history:
    how it moves in a given week of the year, and how much a flyer week lifts it.
    These replace a series identifier, so the model also works for a series it has
    never seen and does not blow up when there are hundreds of them.
    """
    L = np.log(np.maximum(Y[:, :origin], 1.0))
    dev = L - L.mean(1, keepdims=True)
    w = woy[:origin]
    n_w = int(woy.max()) + 1
    tot = np.zeros((Y.shape[0], n_w))
    cnt = np.zeros(n_w)
    np.add.at(tot.T, w, dev.T)
    np.add.at(cnt, w, 1.0)
    seasonal = tot / np.maximum(cnt, 1.0)                       # week-of-year index per series
    f = flyer[:origin] == 1
    tilt = dev[:, f].mean(1) - dev[:, ~f].mean(1) if f.any() and (~f).any() else np.zeros(len(Y))
    return seasonal, tilt


def gbm_forecast(Y, X, woy, flyer, origin, horizons, seed=SEED, anchor=0):
    """One model for every series at a level: calendar, media, and how this series usually behaves."""
    n = Y.shape[0]
    weeks = np.arange(origin)
    seasonal, tilt = series_traits(Y, woy, flyer, origin)
    level = np.log(np.maximum(Y[:, max(0, origin - 8):origin].mean(1), 1.0))   # how big this series is now

    def frame(idx):
        own = seasonal[:, woy[idx]].ravel()
        flt = np.repeat(tilt, len(idx)) * np.tile(flyer[idx], n)
        return np.column_stack([np.tile(X[idx], (n, 1)), own, flt])

    ytr = np.log(np.maximum(Y[:, weeks].ravel(), 1.0)) - np.repeat(level, origin)
    m = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.06, max_leaf_nodes=31, min_samples_leaf=40,
                                      l2_regularization=1.0, early_stopping=False,
                                      random_state=seed).fit(frame(weeks), ytr)
    shift = 0.0
    if anchor:
        recent = np.arange(origin - anchor, origin)
        resid = (np.log(np.maximum(Y[:, recent], 1.0)) - np.repeat(level, anchor).reshape(n, anchor)
                 - m.predict(frame(recent)).reshape(n, anchor))
        shift = resid.mean(1)[:, None]
    return np.exp(m.predict(frame(horizons)).reshape(n, len(horizons)) + level[:, None] + shift)


def metrics(actual, pred, scale):
    e = pred - actual
    return {"mae": float(np.abs(e).mean()), "wape": float(np.abs(e).sum() / actual.sum()),
            "bias": float(e.sum() / actual.sum()), "mase": float(np.abs(e).mean() / scale)}


def main():
    series = pd.read_parquet(WORK / "series.parquet")
    cal = pd.read_parquet(WORK / "calendar.parquet").sort_values("t").reset_index(drop=True)
    X, names = build(cal)
    woy = cal.week_of_year.to_numpy(int)
    flyer = cal.flyer_week.to_numpy(float)
    X_cal, _ = build(cal, blocks=("seasonality", "calendar"))
    X_seas, _ = build(cal, blocks=("seasonality",))
    origins = [FIRST_ORIGIN + i * ORIGIN_STEP for i in range(N_ORIGINS)]
    res = {"origins": origins, "max_horizon": MAX_HORIZON, "features": names,
           "backtest_weeks": [int(origins[0]), int(origins[-1] + MAX_HORIZON)],
           "backtest_dates": [str(cal.week_start.iloc[origins[0]]), str(cal.week_start.iloc[origins[-1] + MAX_HORIZON - 1])]}
    rows, store = [], {}

    for level in LEVELS:
        ids, Y = wide(series, level)
        scale = np.abs(Y[:, 52:] - Y[:, :-52]).mean()            # average seasonal-naive error, for MASE
        for origin in origins:
            h = np.arange(origin, min(origin + MAX_HORIZON, Y.shape[1]))
            if len(h) == 0:
                continue
            actual = Y[:, h]
            preds = {
                "Last week repeated": np.repeat(Y[:, origin - 1][:, None], len(h), 1),
                "Same week last year": Y[:, h - 52],
                "Same week last year, level adjusted": Y[:, h - 52] *
                    (Y[:, origin - 8:origin].mean(1) / np.maximum(Y[:, origin - 60:origin - 52].mean(1), 1.0))[:, None],
                "Seasonality only (ridge)": ridge_forecast(Y, X_seas, origin, h),
                "Seasonality and trading calendar (ridge)": ridge_forecast(Y, X_cal, origin, h),
                "Calendar and media plan (ridge)": ridge_forecast(Y, X, origin, h),
                "Calendar and media, level anchored (ridge)": ridge_forecast(Y, X, origin, h, anchor=8),
                "Calendar and media, level anchored (boosted)": gbm_forecast(Y, X, woy, flyer, origin, h, anchor=8),
            }
            # Combining two honest forecasts is usually better than choosing between them
            preds["Last year and calendar combined"] = 0.5 * (preds["Same week last year, level adjusted"]
                                                              + preds["Seasonality and trading calendar (ridge)"])
            for name, p in preds.items():
                for k, hh in enumerate(h - origin + 1):
                    rows.append({"level": level, "method": name, "origin": int(origin), "horizon": int(hh),
                                 **metrics(actual[:, k], p[:, k], scale)})
            if origin == origins[-1]:                            # keep the final forecast for the deck
                store[level] = {"ids": ids.tolist(), "weeks": [str(cal.week_start.iloc[i]) for i in h],
                                "actual": actual.tolist(),
                                "preds": {n: p.tolist() for n, p in preds.items()}}
        print("done", level)

    bt = pd.DataFrame(rows)
    bt.to_parquet(WORK / "backtest.parquet")
    piv = bt.groupby(["level", "method"]).agg(wape=("wape", "mean"), mae=("mae", "mean"),
                                              bias=("bias", "mean"), mase=("mase", "mean")).reset_index()
    base = piv[piv.method == "Same week last year"].set_index("level").wape
    piv["skill_vs_seasonal_naive"] = 1 - piv.wape / piv.level.map(base)
    res["summary"] = piv.round(5).to_dict("records")
    res["by_horizon"] = bt.groupby(["level", "method", "horizon"]).wape.mean().round(5).reset_index().to_dict("records")
    res["by_origin"] = bt[bt.level == "Category"].groupby(["method", "origin"]).wape.mean().round(5).reset_index().to_dict("records")

    def w(level, method):
        return float(piv[(piv.level == level) & (piv.method == method)].wape.iloc[0])

    # what each block of knowledge is worth, and which method wins at each level
    res["knowledge_ladder"] = {level: {
        "seasonality only": w(level, "Seasonality only (ridge)"),
        "plus trading calendar": w(level, "Seasonality and trading calendar (ridge)"),
        "plus media plan": w(level, "Calendar and media plan (ridge)"),
        "plus recent level": w(level, "Calendar and media, level anchored (ridge)")} for level in LEVELS}
    res["winner_by_level"] = {level: piv[piv.level == level].sort_values("wape").iloc[0].method for level in LEVELS}
    res["winner_wape"] = {level: float(piv[piv.level == level].sort_values("wape").iloc[0].wape) for level in LEVELS}
    res["seasonal_naive_wape"] = {level: w(level, "Same week last year") for level in LEVELS}
    champ = res["winner_by_level"]
    res["champion"] = champ
    res["final_forecast"] = store
    best = bt[[r.method == champ[r.level] for r in bt.itertuples()]]
    print(best.groupby(["level", "horizon"]).wape.mean().unstack().round(4).to_string())
    res["champion_by_horizon"] = best.groupby(["level", "horizon"]).wape.mean().round(5).reset_index().to_dict("records")
    res["champion_metrics"] = {level: piv[(piv.level == level) & (piv.method == champ[level])].iloc[0].to_dict() for level in LEVELS}
    (OUT / "backtest.json").write_text(json.dumps(res, indent=2, default=float))

    pd.set_option("display.width", 220)
    print(piv.pivot(index="method", columns="level", values="wape").round(4).to_string())
    print(piv.pivot(index="method", columns="level", values="skill_vs_seasonal_naive").round(3).to_string())
    print(json.dumps(res["knowledge_ladder"], indent=1))
    print(res["winner_by_level"])


if __name__ == "__main__":
    main()
