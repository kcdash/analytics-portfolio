"""
A simulated in-market experiment.

Maple & Main has never run a media holdout, so the model below produces the
result one would have delivered. Because the data is synthetic, the true
response curve is known and the experiment can be read off it directly; the
noise added is the sampling error a geo test of this size would carry.

In a real engagement this function is replaced by the test readout.
"""
import json

import numpy as np

from mmm import adstock, hill


def run_curve_test(d, channel_name, true_params, weeks, cuts=(0.4, 0.8), base_revenue=None,
                   rel_noise=0.12, seed=11):
    """
    Two holdouts on the same channel at different depths.

    One test says what a channel is worth at today's spend. It says nothing about
    what happens if the spend moves, because a single point cannot describe a
    curve. Cutting by different amounts in two cells measures two points on the
    response curve and so identifies its shape as well as its height.
    """
    p = true_params[channel_name]
    rng = np.random.default_rng(seed)
    x = d.iloc[weeks].to_numpy(float)
    full = p["max_sales_lift"] * hill(adstock(x, p["adstock_decay"]), p["hill_shape"], p["hill_half_saturation"])
    out = []
    for cut in cuts:
        red = p["max_sales_lift"] * hill(adstock(x * (1 - cut), p["adstock_decay"]),
                                         p["hill_shape"], p["hill_half_saturation"])
        gap = float(((full - red) * base_revenue[weeks]).sum())
        se = abs(gap) * rel_noise
        out.append({"cut": cut, "measured_revenue_lost": float(gap + rng.normal(0, se)),
                    "standard_error": float(se), "true_revenue_lost": gap})
    return {"channel": channel_name, "weeks_tested": int(len(weeks)), "cells": out}


def run_holdout(d, channel_name, true_params, weeks, cut=0.5, base_revenue=None, rel_noise=0.12, seed=7):
    """
    Hold back `cut` of a channel's spend for `weeks` and measure the revenue lost.

    Returns the measured incremental revenue for that channel over the test
    window, with the standard error a test of this length would have.
    """
    p = true_params[channel_name]
    rng = np.random.default_rng(seed)
    x = d.iloc[weeks].to_numpy(float)
    ad_full = adstock(x, p["adstock_decay"])
    ad_cut = adstock(x * (1 - cut), p["adstock_decay"])
    lift_full = p["max_sales_lift"] * hill(ad_full, p["hill_shape"], p["hill_half_saturation"])
    lift_cut = p["max_sales_lift"] * hill(ad_cut, p["hill_shape"], p["hill_half_saturation"])
    true_gap = float(((lift_full - lift_cut) * base_revenue[weeks]).sum())
    # what the test measures: the gap it creates, scaled up to the channel's full effect
    scale = float((lift_full * base_revenue[weeks]).sum() / max(true_gap, 1e-9))
    se = abs(true_gap * rel_noise) * scale
    measured = float(lift_full @ base_revenue[weeks] + rng.normal(0, se))
    return {"channel": channel_name, "weeks_tested": int(len(weeks)), "spend_cut": cut,
            "measured_incremental_revenue": measured, "standard_error": float(se),
            "true_incremental_revenue": float(lift_full @ base_revenue[weeks])}
