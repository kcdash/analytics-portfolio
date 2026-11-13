"""Shared settings for the churn and uplift scripts."""
from pathlib import Path

import pandas as pd

PROJECT = Path(__file__).resolve().parents[1]
REPO = PROJECT.parents[1]
WORK = PROJECT / "work"
OUT = PROJECT / "outputs"

CATEGORICAL = ["province", "age_band", "loyalty_tier", "acquisition_channel"]
NUMERIC = [
    "tenure_days", "email_opt_in", "sms_opt_in", "recency_days", "orders_90d", "orders_prev_90d", "orders_365d",
    "spend_365d", "spend_90d", "avg_basket_365d", "discount_share_365d", "promo_line_share_365d",
    "avg_categories_per_order", "digital_order_share_365d", "redemptions_365d", "avg_gap_days", "overdue_ratio",
    "web_sessions_1m", "web_sessions_3m", "web_sessions_prev_3m", "abandoned_carts_3m", "service_contacts_90d",
    "service_contacts_365d", "complaints_180d", "unresolved_180d", "min_csat_180d", "crm_contacts_365d",
    "crm_opens_365d", "crm_clicks_365d",
]
FEATURES = NUMERIC + CATEGORICAL

LABELS = {  # plain-English names used in charts, the deck and the demo
    "recency_days": "Days since last order", "overdue_ratio": "Overdue vs own buying rhythm",
    "orders_90d": "Orders, last 90 days", "orders_prev_90d": "Orders, prior 90 days", "orders_365d": "Orders, last 12 months",
    "spend_365d": "Spend, last 12 months", "spend_90d": "Spend, last 90 days", "avg_basket_365d": "Average basket",
    "avg_gap_days": "Average days between orders", "web_sessions_1m": "Web sessions, last month",
    "web_sessions_3m": "Web sessions, last 3 months", "web_sessions_prev_3m": "Web sessions, prior 3 months",
    "abandoned_carts_3m": "Abandoned carts, last 3 months", "service_contacts_90d": "Service contacts, last 90 days",
    "service_contacts_365d": "Service contacts, last 12 months", "complaints_180d": "Complaints, last 6 months",
    "unresolved_180d": "Unresolved service issues", "min_csat_180d": "Lowest satisfaction score",
    "tenure_days": "Tenure", "loyalty_tier": "Loyalty tier", "acquisition_channel": "Acquisition channel",
    "email_opt_in": "Email opt-in", "sms_opt_in": "SMS opt-in", "province": "Province", "age_band": "Age band",
    "discount_share_365d": "Share of spend on discount", "promo_line_share_365d": "Share of items on promotion",
    "avg_categories_per_order": "Categories per order", "digital_order_share_365d": "Share of orders online",
    "redemptions_365d": "Points redemptions", "crm_contacts_365d": "CRM contacts, last 12 months",
    "crm_opens_365d": "CRM opens", "crm_clicks_365d": "CRM clicks",
}


def prep(df: pd.DataFrame) -> pd.DataFrame:
    """Feature frame with categoricals typed for gradient boosting."""
    x = df[FEATURES].copy()
    for c in CATEGORICAL:
        x[c] = x[c].astype("category")
    return x
