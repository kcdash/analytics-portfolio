#!/usr/bin/env python3
"""
Maple & Main synthetic data generator
=====================================
Builds a fictional Canadian omnichannel retailer with a loyalty program:
~200k customers, 3 years of history (2023-11-06 to 2026-11-01), CAD.

Everything here is synthetic. No real customer, client or employer data.

Usage
-----
    python data/generate_maple_main.py                      # full size -> data/full/
    python data/generate_maple_main.py --scale 0.01 --out data/sample
    python data/generate_maple_main.py --no-issues          # skip planted data-quality issues
    python data/generate_maple_main.py --only customers,transactions   # write selected tables only

Ground truth (latent churn dates, uplift, media response curves, planted
issues) is written to <out>/truth/ so every model can be scored against
the mechanism that generated the data.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

# ----------------------------------------------------------------------------
# Reference data
# ----------------------------------------------------------------------------
PROV = {  # share of customers, cities, postal-code first letters
    "ON": (0.390, ["Toronto", "Mississauga", "Ottawa", "Hamilton", "London"], "KLMNP"),
    "QC": (0.220, ["Montréal", "Québec City", "Laval"], "GHJ"),
    "BC": (0.140, ["Vancouver", "Surrey", "Victoria"], "V"),
    "AB": (0.120, ["Calgary", "Edmonton"], "T"),
    "MB": (0.035, ["Winnipeg"], "R"),
    "SK": (0.030, ["Saskatoon", "Regina"], "S"),
    "NS": (0.027, ["Halifax"], "B"),
    "NB": (0.021, ["Moncton"], "E"),
    "NL": (0.013, ["St. John's"], "A"),
    "PE": (0.004, ["Charlottetown"], "C"),
}
PROV_NAMES = {"ON": "Ontario", "QC": "Quebec", "BC": "British Columbia", "AB": "Alberta"}
CATS = {  # category: (subcategories, price low, price high, base share, seasonal peak months, amplitude)
    "Apparel": (["Outerwear", "Tops", "Bottoms", "Footwear", "Accessories"], 15, 220, 0.20, [9, 11, 12], 0.35),
    "Home": (["Bedding", "Kitchen", "Decor", "Storage", "Small Appliances"], 10, 300, 0.17, [3, 11], 0.15),
    "Outdoor & Garden": (["Patio", "Garden Tools", "BBQ", "Camping"], 12, 450, 0.09, [4, 5, 6, 7], 1.10),
    "Electronics": (["Audio", "Smart Home", "Phone Accessories", "Computing"], 20, 900, 0.10, [11, 12], 0.80),
    "Beauty & Wellness": (["Skincare", "Haircare", "Vitamins", "Fragrance"], 6, 120, 0.12, [5, 12], 0.30),
    "Grocery & Pantry": (["Snacks", "Beverages", "Pantry Staples", "Coffee & Tea"], 3, 40, 0.18, [], 0.0),
    "Toys & Seasonal": (["Toys", "Games", "Holiday Decor", "Party"], 8, 150, 0.07, [10, 11, 12], 1.40),
    "Sports & Fitness": (["Fitness Gear", "Team Sports", "Cycling", "Winter Sports"], 12, 600, 0.07, [1, 5, 6], 0.50),
}
MEDIA = {  # channel: (base weekly spend CAD, adstock decay, hill shape, max sales lift, CPM)
    "TV": (60000, 0.60, 1.6, 0.070, 18.0),
    "Paid Search": (35000, 0.15, 1.2, 0.060, 45.0),
    "Paid Social": (28000, 0.30, 1.4, 0.040, 9.0),
    "Display": (15000, 0.35, 1.3, 0.015, 4.0),
    "Flyer": (22000, 0.20, 1.5, 0.050, 12.0),
    "Email": (4000, 0.10, 1.1, 0.030, 2.0),
}
TIERS = np.array(["Bronze", "Silver", "Gold"])
ACQ = np.array(["Store", "Organic Web", "Paid Search", "Paid Social", "Referral", "Partner"])
AGE = np.array(["18-24", "25-34", "35-44", "45-54", "55-64", "65+"])
CHANNELS = np.array(["Store", "Web", "App"])
W0 = np.datetime64("2023-11-06")  # Monday, first week of the window
NW = 156                          # weeks of history
DAY = np.timedelta64(1, "D")


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def fsa(rng, prov_codes):
    """First three characters of a postal code, consistent with province."""
    letters = np.array(list("ABCEGHJKLMNPRSTVWXYZ"))
    first = np.empty(len(prov_codes), dtype="<U1")
    for p, (_, _, initials) in PROV.items():
        m = prov_codes == p
        first[m] = rng.choice(list(initials), m.sum())
    digit = rng.integers(1, 10, len(prov_codes)).astype(str)
    return np.char.add(np.char.add(first, digit), rng.choice(letters, len(prov_codes)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/full")
    ap.add_argument("--scale", type=float, default=1.0, help="1.0 = 200k customers")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-issues", action="store_true", help="skip planted data-quality issues")
    ap.add_argument("--only", default="", help="comma-separated table names to write (same seed gives identical data)")
    a = ap.parse_args()

    rng = np.random.default_rng(a.seed)
    out = Path(a.out)
    (out / "truth").mkdir(parents=True, exist_ok=True)
    N = int(200_000 * a.scale)
    week_start = W0 + np.arange(NW) * 7 * DAY
    wend = W0 + NW * 7 * DAY
    truth = {"seed": a.seed, "scale": a.scale, "window": [str(W0), str(wend - DAY)]}

    # ------------------------------------------------------------------ stores
    n_st = 60
    st_prov = rng.choice(list(PROV), n_st, p=[v[0] for v in PROV.values()])
    st_prov[: len(PROV)] = list(PROV)  # every province has at least one store
    stores = pd.DataFrame({
        "store_id": np.arange(1, n_st + 1),
        "province": st_prov,
        "city": [rng.choice(PROV[p][1]) for p in st_prov],
        "store_format": rng.choice(["Flagship", "Standard", "Express"], n_st, p=[0.15, 0.6, 0.25]),
        "open_date": (np.datetime64("2008-01-01") + rng.integers(0, 5400, n_st) * DAY).astype("datetime64[D]"),
    })

    # ---------------------------------------------------------------- products
    cat_names = np.array(list(CATS))
    rows = []
    brands = np.array(["Main Street (private label)"] + [f"Brand {chr(65 + i)}" for i in range(25)])
    for c, (subs, lo, hi, share, _, _) in CATS.items():
        n = int(round(1200 * share))
        price = np.sort(np.round(np.exp(rng.uniform(np.log(lo), np.log(hi), n)), 0)) - 0.01   # cheapest first: best sellers skew low-priced
        rows.append(pd.DataFrame({
            "category": c, "subcategory": rng.choice(subs, n),
            "brand": rng.choice(brands, n, p=np.r_[0.22, np.full(25, 0.78 / 25)]),
            "list_price": price, "unit_cost": np.round(price * rng.uniform(0.42, 0.70, n), 2),
        }))
    products = pd.concat(rows, ignore_index=True)
    products.insert(0, "sku", ["SKU%05d" % i for i in range(1, len(products) + 1)])
    cat_start = products.groupby("category", sort=False).cumcount().eq(0).to_numpy().nonzero()[0]
    cat_count = products["category"].value_counts(sort=False).reindex(cat_names).to_numpy()
    cat_month_p = np.zeros((12, len(cat_names)))  # category mix by calendar month
    for j, (c, v) in enumerate(CATS.items()):
        cat_month_p[:, j] = v[3]
        for m in v[4]:
            cat_month_p[m - 1, j] *= 1 + v[5]
    cat_month_p /= cat_month_p.sum(1, keepdims=True)

    # ------------------------------------------------------------------- media
    t = np.arange(NW)
    woy = np.array([pd.Timestamp(d).isocalendar()[1] for d in week_start])
    holiday = np.exp(-0.5 * ((woy - 50) / 2.5) ** 2) + 0.35 * np.exp(-0.5 * ((woy - 35) / 2.0) ** 2)
    media_rows, media_mult, truth["mmm"] = [], np.ones(NW), {}
    for ch, (base, decay, shape, beta, cpm) in MEDIA.items():
        flight = np.where((t // 6) % 2 == 0, 1.0, 0.25) if ch == "TV" else 1.0
        spend = base * (1 + 0.9 * holiday) * flight * rng.lognormal(0, 0.25, NW)
        if ch == "Flyer":
            spend = np.where(t % 2 == 0, spend * 1.6, spend * 0.3)
        spend = np.round(spend, 0)
        ad = np.zeros(NW)
        for i in range(NW):
            ad[i] = spend[i] + (decay * ad[i - 1] if i else 0)
        k = np.median(ad)
        resp = ad ** shape / (ad ** shape + k ** shape)
        media_mult += beta * resp
        truth["mmm"][ch] = {"adstock_decay": decay, "hill_shape": shape, "hill_half_saturation": float(k),
                            "max_sales_lift": beta, "avg_sales_lift": float((beta * resp).mean())}
        media_rows.append(pd.DataFrame({"week_start": week_start, "channel": ch, "spend_cad": spend,
                                        "impressions": np.round(spend / cpm * 1000 * rng.lognormal(0, 0.08, NW))}))
    media = pd.concat(media_rows, ignore_index=True)
    flyer_on = (t % 2 == 0).astype(float)

    # weekly demand index: trend x seasonality x media response
    demand = (1 + 0.0010 * t) * (1 + 0.45 * holiday + 0.05 * np.sin(2 * np.pi * woy / 52)) * media_mult
    demand = demand / demand.mean()
    cum = np.r_[0.0, np.cumsum(demand)]
    truth["demand_index_note"] = "weekly orders are proportional to trend x seasonality x (1 + sum of media lifts)"

    # --------------------------------------------------------------- customers
    eng = rng.normal(0, 1, N)                       # latent engagement
    complaint_prone = rng.random(N) < 0.12          # latent service friction
    pre = rng.random(N) < 0.55                      # joined before the window
    jw = rng.choice(NW, N, p=(1 + 0.004 * t) * (1 + 0.5 * holiday) / ((1 + 0.004 * t) * (1 + 0.5 * holiday)).sum())
    join = np.where(pre, W0 - rng.integers(1, 2100, N) * DAY, W0 + (jw * 7 + rng.integers(0, 7, N)) * DAY)
    start = np.where(pre, 0, jw)                    # first active week in window
    prov = rng.choice(list(PROV), N, p=[v[0] for v in PROV.values()])
    tier_i = np.digitize(eng + rng.normal(0, 0.8, N), [0.35, 1.45])       # 0 Bronze, 1 Silver, 2 Gold
    acq_i = rng.choice(len(ACQ), N, p=[0.34, 0.20, 0.14, 0.16, 0.10, 0.06])
    age_i = rng.choice(len(AGE), N, p=[0.09, 0.22, 0.24, 0.19, 0.15, 0.11])
    email_opt = rng.random(N) < sigmoid(0.9 + 0.5 * eng)
    sms_opt = rng.random(N) < sigmoid(-0.7 + 0.3 * eng - 0.15 * (age_i - 2))
    home_store = np.zeros(N, dtype=int)
    for p in PROV:
        m = prov == p
        home_store[m] = rng.choice(stores.loc[stores.province == p, "store_id"].to_numpy(), m.sum())
    pref = np.stack([np.full(N, 0.55) + 0.06 * (age_i - 2), np.full(N, 0.28), 0.17 - 0.06 * (age_i - 2)], 1)
    pref = np.clip(pref, 0.03, None)
    pref /= pref.sum(1, keepdims=True)
    pref_ch = (rng.random(N)[:, None] > pref.cumsum(1)).sum(1).clip(0, 2)

    # churn: monthly hazard, exponential time to churn from first active week
    hz = 0.016 * np.exp(-0.55 * eng + 0.45 * (acq_i == 3) + 0.20 * (acq_i == 2) - 0.15 * (tier_i == 1)
                        - 0.35 * (tier_i == 2) - 0.20 * email_opt + 0.45 * complaint_prone + 0.25 * (~pre))
    churn_wk = start + rng.exponential(1 / hz) * 4.345
    churned = churn_wk < NW - 1
    end = np.where(churned, np.ceil(churn_wk), NW).astype(int).clip(1, NW)  # exclusive last active week
    end = np.maximum(end, start + 1)
    truth["churn"] = {"definition": "latent churn date; customer places no orders afterwards",
                      "share_churned_in_window": float(churned.mean()),
                      "hazard_log_coefficients": {"engagement": -0.55, "acq_paid_social": 0.45, "acq_paid_search": 0.20,
                                                  "tier_silver": -0.15, "tier_gold": -0.35, "email_opt_in": -0.20,
                                                  "complaint_prone": 0.45, "joined_in_window": 0.25}}

    customers = pd.DataFrame({
        "customer_id": np.arange(100001, 100001 + N), "join_date": join.astype("datetime64[D]"), "province": prov,
        "postal_fsa": fsa(rng, prov), "age_band": AGE[age_i], "loyalty_tier": TIERS[tier_i],
        "acquisition_channel": ACQ[acq_i], "email_opt_in": email_opt.astype(int), "sms_opt_in": sms_opt.astype(int),
        "home_store_id": home_store,
    })
    cid = customers["customer_id"].to_numpy()

    # ------------------------------------------------------- organic order flow
    tier_mult = np.array([1.0, 1.3, 1.7])[tier_i]
    lam = 4.2 * np.exp(0.5 * eng) * tier_mult                 # orders per year when active
    mass = cum[end] - cum[start]
    n_ord = rng.poisson(lam / 52 * mass)
    oc = np.repeat(np.arange(N), n_ord)                       # customer index per order
    target = cum[start][oc] + rng.random(len(oc)) * mass[oc]
    owk = (np.searchsorted(cum, target, side="right") - 1).clip(0, NW - 1)
    oday = owk * 7 + rng.choice(7, len(oc), p=[0.11, 0.11, 0.12, 0.13, 0.17, 0.20, 0.16])

    # ---------------------------------------------------------------- campaigns
    camp_rows, contact_rows, inj_c, inj_d = [], [], [], []
    offers = [("10% off", 1.0), ("5x bonus points", 0.8), ("$15 off $75", 1.2), ("Free shipping", 0.7), ("Win-back 20% off", 1.3)]
    ch_cfg = {"Email": (0.02, 1.0), "SMS": (0.06, 1.2), "Direct Mail": (0.95, 1.6)}
    for k, wk in enumerate(range(2, NW - 2, 4)):
        ch = ["Email", "SMS", "Email", "Direct Mail"][k % 4]
        offer, of = offers[k % len(offers)]
        cost, cf = ch_cfg[ch]
        elig = (start <= wk) & (end > wk)
        elig &= email_opt if ch == "Email" else sms_opt if ch == "SMS" else True
        idx = rng.choice(np.flatnonzero(elig), min(int(25000 * a.scale), int(elig.sum())), replace=False)
        treat = rng.random(len(idx)) >= 0.10
        e = eng[idx]
        p0 = sigmoid(-3.6 + 0.6 * e)                                          # buys anyway
        up = 0.045 * np.exp(-((e - 0.2) ** 2) / 0.8) * cf * of                # persuadables in the middle
        if ch == "SMS":
            up = np.where(e < -1.2, -0.010, up)                               # sleeping dogs
        resp = rng.random(len(idx)) < np.clip(p0 + treat * up, 0, 1)
        opened = treat & (ch != "Direct Mail") & (rng.random(len(idx)) < 0.22 + 0.15 * sigmoid(e))
        clicked = opened & (rng.random(len(idx)) < 0.18)
        cid_k = "C%03d" % (k + 1)
        camp_rows.append((cid_k, f"{offer} - {ch} - {str(week_start[wk])[:7]}", ch, offer, week_start[wk],
                          week_start[wk] + 13 * DAY, cost, len(idx), int(treat.sum())))
        contact_rows.append(pd.DataFrame({"campaign_id": cid_k, "customer_id": cid[idx],
                                          "treatment_group": np.where(treat, "Treatment", "Holdout"),
                                          "sent_flag": treat.astype(int), "opened_flag": opened.astype(int),
                                          "clicked_flag": clicked.astype(int), "responded_flag": resp.astype(int)}))
        r = idx[resp]
        inj_c.append(r)
        inj_d.append(np.minimum(wk * 7 + rng.integers(0, 14, len(r)), end[r] * 7 - 1))
    campaigns = pd.DataFrame(camp_rows, columns=["campaign_id", "campaign_name", "channel", "offer", "start_date",
                                                 "end_date", "cost_per_contact_cad", "audience_size", "treated_size"])
    contacts = pd.concat(contact_rows, ignore_index=True)
    truth["uplift"] = {"response_window_days": 14, "baseline": "sigmoid(-3.6 + 0.6*engagement)",
                       "uplift": "0.045*exp(-(engagement-0.2)^2/0.8) x channel x offer; SMS is -0.010 when engagement < -1.2",
                       "channel_factor": {k: v[1] for k, v in ch_cfg.items()}, "offer_factor": dict(offers)}

    # ------------------------------------------------- orders and order items
    oc = np.r_[oc, np.concatenate(inj_c)]
    oday = np.r_[oday, np.concatenate(inj_d)]
    order = np.argsort(oday, kind="stable")
    oc, oday = oc[order], oday[order]
    M = len(oc)
    odate = W0 + oday * DAY
    stick = rng.random(M) < 0.75
    och = np.where(stick, pref_ch[oc], rng.choice(3, M, p=[0.5, 0.3, 0.2]))
    ostore = np.where(rng.random(M) < 0.85, home_store[oc], rng.integers(1, n_st + 1, M))
    k_items = 1 + rng.poisson(1.3 * np.sqrt(tier_mult[oc]))
    oi = np.repeat(np.arange(M), k_items)                     # order index per line
    L = len(oi)
    month = (odate.astype("datetime64[M]").astype(int) % 12)[oi]
    cat = np.zeros(L, dtype=int)
    for m in range(12):
        mk = month == m
        cat[mk] = rng.choice(len(cat_names), mk.sum(), p=cat_month_p[m])
    sku_i = cat_start[cat] + (rng.random(L) ** 1.8 * cat_count[cat]).astype(int)   # long-tail popularity
    qty = rng.choice([1, 2, 3], L, p=[0.78, 0.17, 0.05])
    promo = rng.random(L) < 0.14 + 0.16 * flyer_on[(oday // 7).clip(0, NW - 1)][oi]
    disc = np.where(promo, rng.choice([0.10, 0.15, 0.20, 0.25, 0.30], L), 0.0)
    lp = products["list_price"].to_numpy()[sku_i]
    unit = np.round(lp * (1 - disc), 2)
    gross = np.bincount(oi, qty * lp, M)
    net = np.bincount(oi, qty * unit, M)
    redeemed = np.where(rng.random(M) < 0.06, rng.choice([500, 1000, 2000], M, p=[0.6, 0.3, 0.1]), 0)
    order_id = np.arange(5_000_001, 5_000_001 + M)
    transactions = pd.DataFrame({
        "order_id": order_id, "customer_id": cid[oc], "order_date": odate.astype("datetime64[D]"),
        "channel": CHANNELS[och], "store_id": pd.array(np.where(och == 0, ostore, -1), dtype="Int64"),
        "gross_amount": np.round(gross, 2), "discount_amount": np.round(gross - net, 2), "net_amount": np.round(net, 2),
        "points_earned": np.floor(net * np.array([1.0, 1.25, 1.5])[tier_i[oc]]).astype(int), "points_redeemed": redeemed,
    })
    transactions.loc[transactions.store_id == -1, "store_id"] = pd.NA
    order_items = pd.DataFrame({"order_id": order_id[oi], "line_no": pd.Series(oi).groupby(oi).cumcount().to_numpy() + 1,
                                "sku": products["sku"].to_numpy()[sku_i], "quantity": qty, "unit_price": unit,
                                "promo_flag": promo.astype(int)})

    # ---------------------------------------------------------- loyalty events
    tc = np.flatnonzero(rng.random(N) < 0.25)
    tc_day = (start[tc] * 7 + rng.random(len(tc)) * (end[tc] - start[tc]) * 7).astype(int)
    prior = np.where(tier_i[tc] == 0, 1, tier_i[tc] - 1)
    exp_c = np.flatnonzero(churned & ((end + 52) < NW))
    red = np.flatnonzero(redeemed > 0)
    ev = pd.concat([
        pd.DataFrame({"customer_id": cid, "event_date": join, "event_type": "ENROL", "tier_from": None,
                      "tier_to": "Bronze", "points": 0}),
        pd.DataFrame({"customer_id": cid[tc], "event_date": W0 + tc_day * DAY, "event_type": "TIER_CHANGE",
                      "tier_from": TIERS[prior], "tier_to": TIERS[tier_i[tc]], "points": 0}),
        pd.DataFrame({"customer_id": cid[oc[red]], "event_date": odate[red], "event_type": "REDEMPTION",
                      "tier_from": None, "tier_to": None, "points": -redeemed[red]}),
        pd.DataFrame({"customer_id": cid[exp_c], "event_date": W0 + (end[exp_c] + 52) * 7 * DAY,
                      "event_type": "POINTS_EXPIRY", "tier_from": None, "tier_to": None,
                      "points": -rng.integers(100, 6000, len(exp_c))}),
    ], ignore_index=True)
    ev["event_date"] = ev["event_date"].astype("datetime64[s]").dt.floor("D")
    ev = ev.sort_values("event_date", kind="stable").reset_index(drop=True)
    ev.insert(0, "event_id", np.arange(1, len(ev) + 1))

    # -------------------------------------------------------- service contacts
    yrs = (end - start) / 52
    n_sc = rng.poisson(0.25 * yrs * np.where(complaint_prone, 3.0, 1.0))
    sc_c = np.repeat(np.arange(N), n_sc)
    sc_day = (start[sc_c] * 7 + rng.random(len(sc_c)) * (end[sc_c] - start[sc_c]) * 7).astype(int)
    n_pre = np.where(churned, rng.poisson(np.where(complaint_prone, 0.9, 0.35)), 0)   # friction before churn
    pc = np.repeat(np.arange(N), n_pre)
    pc_day = np.maximum(end[pc] * 7 - rng.integers(1, 90, len(pc)), start[pc] * 7)
    is_pre = np.r_[np.zeros(len(sc_c), bool), np.ones(len(pc), bool)]
    sc_c, sc_day = np.r_[sc_c, pc], np.r_[sc_day, pc_day]
    reasons = np.array(["Delivery", "Return/Refund", "Product quality", "Loyalty points", "Billing", "General inquiry"])
    reason = np.where(is_pre, rng.choice(reasons, len(sc_c), p=[0.28, 0.27, 0.22, 0.10, 0.10, 0.03]),
                      rng.choice(reasons, len(sc_c), p=[0.18, 0.20, 0.10, 0.17, 0.08, 0.27]))
    csat = np.where(is_pre, rng.choice([1, 2, 3, 4, 5], len(sc_c), p=[0.30, 0.27, 0.22, 0.14, 0.07]),
                    rng.choice([1, 2, 3, 4, 5], len(sc_c), p=[0.06, 0.09, 0.20, 0.35, 0.30])).astype(float)
    csat[rng.random(len(sc_c)) < 0.40] = np.nan               # survey not answered
    service = pd.DataFrame({"customer_id": cid[sc_c], "contact_date": (W0 + sc_day * DAY).astype("datetime64[D]"),
                            "contact_channel": rng.choice(["Phone", "Chat", "Email", "In-store"], len(sc_c), p=[0.35, 0.3, 0.2, 0.15]),
                            "reason": reason, "resolved_flag": (rng.random(len(sc_c)) < np.where(is_pre, 0.62, 0.88)).astype(int),
                            "csat_score": pd.array(csat, dtype="Int64")})
    service = service.sort_values("contact_date", kind="stable").reset_index(drop=True)
    service.insert(0, "contact_id", np.arange(1, len(service) + 1))

    # ------------------------------------------------------ web activity (monthly)
    months = pd.period_range("2023-11", periods=36, freq="M")
    sm = (start * 7 / 30.44).astype(int).clip(0, 35)
    em = np.ceil(end * 7 / 30.44).astype(int).clip(1, 36)
    web_rows = []
    rate = 0.7 * np.exp(0.6 * eng) * np.array([0.6, 1.5, 1.8])[pref_ch]
    for m in range(36):
        act = (sm <= m) & (em > m)
        fading = churned & (m >= em - 2)                       # browsing drops before churn
        s = rng.poisson(np.where(act, rate * np.where(fading, 0.35, 1.0), 0.0))
        nz = np.flatnonzero(s)
        carts = rng.binomial(s[nz], 0.30)
        web_rows.append(pd.DataFrame({"customer_id": cid[nz], "activity_month": str(months[m]), "sessions": s[nz],
                                      "page_views": s[nz] + rng.poisson(s[nz] * 4.5), "cart_adds": carts,
                                      "abandoned_carts": rng.binomial(carts, 0.60)}))
    web = pd.concat(web_rows, ignore_index=True)

    # ---------------------------------------------------------------- prospects
    NP_ = int(150_000 * a.scale)
    src = rng.choice(5, NP_, p=[0.30, 0.20, 0.10, 0.12, 0.28])
    src_names = np.array(["Web lead", "Partner list", "Event", "Referral", "Purchased list"])
    visits = rng.poisson(1.2 + 1.5 * (src == 0))
    dist = np.round(rng.gamma(2.0, 6.0, NP_), 1)
    inc_i = rng.choice(5, NP_, p=[0.16, 0.24, 0.26, 0.20, 0.14])
    p_age = rng.choice(len(AGE), NP_, p=[0.10, 0.22, 0.23, 0.19, 0.15, 0.11])
    kids = rng.random(NP_) < 0.34
    p_email = rng.random(NP_) < 0.30
    logit = (-3.1 + 0.55 * (src == 3) + 0.35 * (src == 0) - 0.60 * (src == 4) + 0.16 * np.minimum(visits, 8)
             - 0.025 * dist + 0.12 * inc_i + 0.30 * np.isin(p_age, [1, 2]) + 0.25 * kids + 0.65 * p_email)
    conv = rng.random(NP_) < sigmoid(logit)
    new_c = np.flatnonzero(~pre)
    cv = np.flatnonzero(conv)[: len(new_c)]
    conv[:] = False
    conv[cv] = True
    link = rng.choice(new_c, len(cv), replace=False)
    p_prov = rng.choice(list(PROV), NP_, p=[v[0] for v in PROV.values()])
    p_prov[cv], p_age[cv] = prov[link], age_i[link]
    p_fsa = fsa(rng, p_prov)
    p_fsa[cv] = customers["postal_fsa"].to_numpy()[link]
    p_date = W0 + rng.integers(0, NW * 7 - 30, NP_) * DAY
    p_date[cv] = join[link] - rng.integers(1, 45, len(cv)) * DAY
    conv_id = np.full(NP_, -1)
    conv_id[cv] = cid[link]
    prospects = pd.DataFrame({
        "prospect_id": np.arange(900001, 900001 + NP_), "first_contact_date": p_date.astype("datetime64[D]"),
        "lead_source": src_names[src], "province": p_prov, "postal_fsa": p_fsa, "age_band": AGE[p_age],
        "household_income_band": np.array(["<50k", "50-75k", "75-100k", "100-150k", "150k+"])[inc_i],
        "has_children": kids.astype(int), "distance_to_store_km": dist, "web_visits_30d": visits,
        "email_engaged_flag": p_email.astype(int), "converted_flag": conv.astype(int),
        "converted_customer_id": pd.array(np.where(conv, conv_id, -1), dtype="Int64"),
    })
    prospects.loc[prospects.converted_customer_id == -1, "converted_customer_id"] = pd.NA
    truth["acquisition"] = {"conversion_rate": float(conv.mean()),
                            "logit": "-3.1 +0.55 referral +0.35 web lead -0.60 purchased list +0.16 web visits (cap 8) "
                                     "-0.025 km +0.12 income band +0.30 age 25-44 +0.25 children +0.65 email engaged"}

    # --------------------------------------------------------------- truth file
    cust_truth = pd.DataFrame({"customer_id": cid, "engagement": np.round(eng, 4), "complaint_prone": complaint_prone.astype(int),
                               "churned_in_window": churned.astype(int),
                               "churn_date": np.where(churned, (W0 + end * 7 * DAY).astype("datetime64[D]").astype(str), ""),
                               "annual_order_rate": np.round(lam, 3)})

    # ------------------------------------------------- planted data-quality issues
    transactions["order_date"] = transactions["order_date"].dt.strftime("%Y-%m-%d")
    issues = {}
    if not a.no_issues:
        d = customers.sample(frac=0.004, random_state=a.seed)
        customers = pd.concat([customers, d], ignore_index=True)
        issues["customers_duplicate_rows"] = len(d)
        m = rng.random(len(customers)) < 0.03
        customers.loc[m, "postal_fsa"] = None
        issues["customers_missing_postal_fsa"] = int(m.sum())
        m = (rng.random(len(customers)) < 0.012) & customers.province.isin(list(PROV_NAMES)).to_numpy()
        customers.loc[m, "province"] = customers.loc[m, "province"].map(PROV_NAMES)
        issues["customers_province_full_name_instead_of_code"] = int(m.sum())
        m = rng.random(M) < 0.02
        transactions.loc[m, "order_date"] = pd.to_datetime(transactions.loc[m, "order_date"]).dt.strftime("%d/%m/%Y")
        issues["transactions_order_date_in_dd_mm_yyyy"] = int(m.sum())
        m = rng.random(M) < 0.0003
        for c in ["gross_amount", "net_amount"]:
            transactions.loc[m, c] = (transactions.loc[m, c] * 100).round(2)
        issues["transactions_outlier_baskets_x100"] = int(m.sum())
        m = rng.random(M) < 0.0006
        transactions.loc[m, "net_amount"] = -transactions.loc[m, "net_amount"]
        issues["transactions_negative_net_amount"] = int(m.sum())
        d = transactions.sample(frac=0.001, random_state=a.seed)
        transactions = pd.concat([transactions, d], ignore_index=True)
        issues["transactions_duplicate_rows"] = len(d)
        old = ev["event_date"] < "2025-03-01"
        for c in ["tier_from", "tier_to"]:
            ev.loc[old, c] = ev.loc[old, c].str[0]
        issues["loyalty_events_tier_codes_B_S_G_before_2025_03_01"] = int(old.sum())
        drop = media[(media.channel == "Display")].sample(2, random_state=a.seed).index
        media = media.drop(drop).reset_index(drop=True)
        issues["media_spend_weekly_missing_display_weeks"] = 2
    truth["planted_issues"] = issues

    # -------------------------------------------------------------------- write
    tables = {"customers": customers, "transactions": transactions, "order_items": order_items, "products": products,
              "stores": stores, "campaigns": campaigns, "campaign_contacts": contacts, "media_spend_weekly": media,
              "web_activity_monthly": web, "service_contacts": service, "loyalty_events": ev, "prospects": prospects}
    truth["row_counts"] = {}
    only = {x.strip() for x in a.only.split(",") if x.strip()}
    for name, df in tables.items():
        truth["row_counts"][name] = len(df)
        if only and name not in only:
            continue
        df.to_csv(out / f"{name}.csv", index=False, date_format="%Y-%m-%d")
        print(f"{name:<24}{len(df):>12,}")
    cust_truth.to_csv(out / "truth" / "customer_truth.csv", index=False)
    (out / "truth" / "ground_truth.json").write_text(json.dumps(truth, indent=2))
    print("written to", out)


if __name__ == "__main__":
    main()
