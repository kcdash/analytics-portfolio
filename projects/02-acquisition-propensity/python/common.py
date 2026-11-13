"""Shared settings for the acquisition project."""
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
REPO = PROJECT.parents[1]
WORK = PROJECT / "work"
OUT = PROJECT / "outputs"
SEED = 42

# ---- Assumptions (not in the data; all adjustable in the simulator) ---------
COST_PER_CONTACT = 6.00      # welcome mailer plus follow-up emails, CAD per prospect
COST_PER_LEAD = {"Web lead": 8.00, "Partner list": 5.00, "Event": 15.00, "Referral": 20.00, "Purchased list": 2.00}

CATEGORICAL = ["lead_source", "age_band", "household_income_band"]
NUMERIC = ["web_visits_capped", "distance_to_store_km", "has_children", "email_engaged_flag"]
REFERENCE = {"lead_source": "Partner list", "age_band": "45-54", "household_income_band": "<50k"}
LEVELS = {
    "lead_source": ["Partner list", "Event", "Purchased list", "Referral", "Web lead"],
    "age_band": ["45-54", "18-24", "25-34", "35-44", "55-64", "65+"],
    "household_income_band": ["<50k", "50-75k", "75-100k", "100-150k", "150k+"],
}
LABELS = {"web_visits_capped": "Each web visit (up to 8)", "distance_to_store_km": "Each 10 km from a store",
          "has_children": "Children at home", "email_engaged_flag": "Opened a marketing email"}
