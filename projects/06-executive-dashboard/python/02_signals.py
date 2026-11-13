"""
02_signals.py
The question a dashboard should answer before any other: is this movement real?

For every metric the script fits a seasonal baseline, measures how much a normal
week varies around it, and then applies the control rules used on a factory floor
for a century. A number that moves inside its own normal variation is not news,
however large it looks on a chart.

It also answers the first question an executive asks when revenue moves: was it
customers, how often they came, or how much they spent?
"""
import json

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from common import AS_OF_WEEK, METRICS, OUT, RUN_LENGTH, SIGMA_ALERT, SIGMA_WARN, WORK

HARMONICS = 3
MIN_HISTORY = 52        # a baseline needs at least a year behind it


def design(d, harmonics=HARMONICS):
    """Trend, annual shape and the trading events a planner knows in advance."""
    woy = d.week_of_year.to_numpy()
    cols = {"trend": d.t.to_numpy() / 52.0}
    for k in range(1, harmonics + 1):
        cols[f"sin{k}"] = np.sin(2 * np.pi * k * woy / 52.18)
        cols[f"cos{k}"] = np.cos(2 * np.pi * k * woy / 52.18)
    cols["peak_holiday"] = d.peak_holiday.to_numpy(float)
    cols["back_to_school"] = d.back_to_school.to_numpy(float)
    cols["flyer_week"] = d.flyer_week.to_numpy(float)
    return np.column_stack(list(cols.values())), list(cols)


def baseline(values, X, as_of):
    """
    Expected level and normal variation for every week, each estimated only from
    the weeks before it. Nothing is judged against a baseline that has seen it.
    """
    n = len(values)
    exp = np.full(n, np.nan)
    sd = np.full(n, np.nan)
    for i in range(MIN_HISTORY, n):
        tr = slice(0, i)
        m = LinearRegression().fit(X[tr], values[tr])
        resid = values[tr] - m.predict(X[tr])
        exp[i] = m.predict(X[i:i + 1])[0]
        sd[i] = resid.std(ddof=len(X[0]) + 1) if i > len(X[0]) + 2 else resid.std()
    return exp, sd


def run_rules(z):
    """
    Western Electric rules, trimmed to the three that matter on weekly data:
      a point beyond three standard deviations
      two of three consecutive points beyond two
      eight consecutive points on the same side of the baseline
    """
    flags = []
    for i, v in enumerate(z):
        if np.isnan(v):
            flags.append(None)
            continue
        if abs(v) >= SIGMA_ALERT:
            flags.append("beyond three standard deviations")
        elif i >= 2 and np.sum(np.abs(z[i - 2:i + 1]) >= SIGMA_WARN) >= 2 and abs(v) >= SIGMA_WARN:
            flags.append("two of three weeks beyond two standard deviations")
        elif i >= RUN_LENGTH - 1 and not np.isnan(z[i - RUN_LENGTH + 1:i + 1]).any() and \
                (np.all(z[i - RUN_LENGTH + 1:i + 1] > 0) or np.all(z[i - RUN_LENGTH + 1:i + 1] < 0)):
            flags.append(f"{RUN_LENGTH} weeks in a row on one side of the baseline")
        else:
            flags.append(None)
    return flags


def period_change(values, as_of, length):
    """
    Compare the last `length` weeks with the `length` before them, and say whether
    the difference is larger than the week-to-week variation would produce anyway.
    """
    cur = values[as_of - length + 1:as_of + 1]
    prev = values[as_of - 2 * length + 1:as_of - length + 1]
    diff = cur.mean() - prev.mean()
    se = np.sqrt(cur.var(ddof=1) / len(cur) + prev.var(ddof=1) / len(prev))
    return {"current": float(cur.mean()), "previous": float(prev.mean()),
            "change": float(diff), "change_pct": float(diff / prev.mean()) if prev.mean() else None,
            "standard_error": float(se), "t": float(diff / se) if se > 0 else 0.0,
            "is_real": bool(abs(diff) > 1.96 * se)}


def main():
    d = pd.read_parquet(WORK / "kpi_week.parquet").sort_values("t").reset_index(drop=True)
    X, terms = design(d)
    as_of = min(AS_OF_WEEK, len(d) - 1)
    res = {"as_of_week": int(as_of), "as_of_date": str(d.week_start.iloc[as_of]),
           "weeks": len(d), "baseline_terms": terms, "min_history_weeks": MIN_HISTORY,
           "rules": {"sigma_alert": SIGMA_ALERT, "sigma_warn": SIGMA_WARN, "run_length": RUN_LENGTH}}

    metrics = {}
    for m in METRICS:
        v = d[m["key"]].to_numpy(float)
        exp, sd = baseline(v, X, as_of)
        z = (v - exp) / np.where(sd > 0, sd, np.nan)
        flags = run_rules(z)
        latest = {"value": float(v[as_of]), "expected": float(exp[as_of]), "sd": float(sd[as_of]),
                  "z": float(z[as_of]), "flag": flags[as_of],
                  "in_normal_range": bool(abs(z[as_of]) < SIGMA_WARN)}
        metrics[m["key"]] = {
            **m, "latest": latest,
            "periods": {str(L): period_change(v, as_of, L) for L in (4, 13, 26, 52)},
            "vs_last_year": {"value": float(v[as_of]), "last_year": float(v[as_of - 52]),
                             "change_pct": float(v[as_of] / v[as_of - 52] - 1)},
            "series": {"weeks": [str(w) for w in d.week_start], "value": [float(x) for x in v],
                       "expected": [None if np.isnan(x) else float(x) for x in exp],
                       "upper": [None if np.isnan(exp[i]) else float(exp[i] + SIGMA_ALERT * sd[i]) for i in range(len(v))],
                       "lower": [None if np.isnan(exp[i]) else float(exp[i] - SIGMA_ALERT * sd[i]) for i in range(len(v))],
                       "flag": flags},
            "signals_in_last_13_weeks": int(sum(1 for f in flags[as_of - 12:as_of + 1] if f)),
            "weeks_with_a_signal": int(sum(1 for f in flags if f)),
            "weeks_judged": int(sum(1 for f in flags if f is not None) + sum(1 for f in flags if f)),
        }
    res["metrics"] = metrics

    # ---- how much of a dashboard's movement is noise? ----------------------
    judged = len(d) - MIN_HISTORY
    total_signals = sum(m["weeks_with_a_signal"] for m in metrics.values())
    res["noise_audit"] = {
        "metrics": len(METRICS), "weeks_judged_per_metric": judged,
        "metric_weeks": len(METRICS) * judged, "weeks_with_a_signal": total_signals,
        "share_of_weeks_with_a_signal": float(total_signals / (len(METRICS) * judged)),
        "weeks_that_moved_more_than_2pct": int(sum(
            1 for m in METRICS for i in range(MIN_HISTORY + 1, len(d))
            if abs(d[m["key"]].iloc[i] / d[m["key"]].iloc[i - 1] - 1) > 0.02)),
        "note": "a dashboard that highlights every move larger than two per cent would raise "
                "far more flags than the data supports"}

    # ---- when revenue moves, what moved it? -------------------------------
    # revenue = active customers x orders per customer x average basket
    def decompose(a, b):
        """Log decomposition: each factor's share of the change, adding to the total."""
        parts = {}
        for f in ["active_customers", "orders_per_customer", "avg_basket"]:
            parts[f] = float(np.log(b[f] / a[f]))
        tot = float(np.log(b["revenue"] / a["revenue"]))
        scale = tot / sum(parts.values()) if sum(parts.values()) != 0 else 0.0
        return {"total_change_pct": float(b["revenue"] / a["revenue"] - 1),
                "contributions": {k: float(v * scale * (b["revenue"] / a["revenue"] - 1) / tot) if tot else 0.0
                                  for k, v in parts.items()},
                "residual": float(tot - sum(parts.values()))}

    decomps = {}
    for L in (4, 13, 52):
        cur = d.iloc[as_of - L + 1:as_of + 1].mean(numeric_only=True)
        prev = d.iloc[as_of - 2 * L + 1:as_of - L + 1].mean(numeric_only=True)
        decomps[str(L)] = decompose(prev, cur)
    res["revenue_decomposition"] = decomps

    # ---- the same signal test on every slice -------------------------------
    sl = pd.read_parquet(WORK / "kpi_slice.parquet")
    slice_rows = []
    for (dim, name), g in sl.groupby(["dimension", "slice"]):
        g = g.sort_values("t").reset_index(drop=True)
        g = g.merge(d[["t", "week_of_year", "peak_holiday", "back_to_school", "flyer_week"]], on="t")
        if len(g) < MIN_HISTORY + 4:
            continue
        Xs, _ = design(g)
        v = g.revenue.to_numpy(float)
        exp, sd = baseline(v, Xs, as_of)
        z = (v - exp) / np.where(sd > 0, sd, np.nan)
        pc = period_change(v, as_of, 13)
        slice_rows.append({"dimension": dim, "slice": name, "revenue_13w": float(v[as_of - 12:as_of + 1].sum()),
                           "share": None, "z": float(z[as_of]), "flag": run_rules(z)[as_of],
                           "change_13w_pct": pc["change_pct"], "is_real": pc["is_real"],
                           "series": [float(x) for x in v[-26:]]})
    for dim in {r["dimension"] for r in slice_rows}:
        tot = sum(r["revenue_13w"] for r in slice_rows if r["dimension"] == dim)
        for r in slice_rows:
            if r["dimension"] == dim:
                r["share"] = r["revenue_13w"] / tot
    res["slices"] = slice_rows

    (OUT / "signals.json").write_text(json.dumps(res, indent=2, default=float))
    pd.set_option("display.width", 240)
    print("as of", res["as_of_date"])
    print(pd.DataFrame([{"metric": m["label"], "value": m["latest"]["value"], "expected": m["latest"]["expected"],
                         "z": m["latest"]["z"], "flag": m["latest"]["flag"],
                         "13w change": m["periods"]["13"]["change_pct"], "real": m["periods"]["13"]["is_real"],
                         "signals": m["weeks_with_a_signal"]} for m in metrics.values()]).round(3).to_string())
    print("\nnoise audit", {k: v for k, v in res["noise_audit"].items() if k != "note"})
    print("\nrevenue decomposition"); print(pd.DataFrame({k: v["contributions"] for k, v in decomps.items()}).round(4).to_string())
    print({k: round(v["total_change_pct"], 4) for k, v in decomps.items()})
    print("\nslices with a signal:", [(r["dimension"], r["slice"], r["flag"]) for r in slice_rows if r["flag"]])
    print(pd.DataFrame(slice_rows)[["dimension", "slice", "share", "change_13w_pct", "is_real", "z"]].round(3).to_string())


if __name__ == "__main__":
    main()
