"""Calendar and media features. Every one of them is known before the week starts."""
import numpy as np
import pandas as pd

MEDIA = ["spend_tv", "spend_flyer", "spend_search", "spend_social", "spend_display", "spend_email"]


def build(cal: pd.DataFrame, blocks=("seasonality", "calendar", "media"), harmonics=5):
    """
    One row per week, built up in blocks so each kind of knowledge can be priced:

      seasonality  trend and an annual shape with `harmonics` Fourier terms
      calendar     the trading events a planner knows months ahead: flyer weeks,
                   the holiday peak, back to school
      media        how much is planned for each channel that week
    """
    f = {"trend": cal.t.to_numpy() / 52.0}
    woy = cal.week_of_year.to_numpy()
    for k in range(1, harmonics + 1):
        f[f"sin{k}"] = np.sin(2 * np.pi * k * woy / 52.18)
        f[f"cos{k}"] = np.cos(2 * np.pi * k * woy / 52.18)
    if "calendar" in blocks:
        f["peak_holiday"] = cal.peak_holiday.to_numpy(float)
        f["back_to_school"] = cal.back_to_school.to_numpy(float)
        f["flyer_week"] = cal.flyer_week.to_numpy(float)
    if "media" in blocks:
        for c in MEDIA:
            v = cal[c].to_numpy(float)
            f[c] = np.log1p(v) - np.log1p(v).mean()
    names = list(f)
    return np.column_stack([f[n] for n in names]), names
