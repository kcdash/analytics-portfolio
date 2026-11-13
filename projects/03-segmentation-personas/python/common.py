"""Shared settings for the segmentation project."""
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
REPO = PROJECT.parents[1]
WORK = PROJECT / "work"
OUT = PROJECT / "outputs"
SEED = 42

# The eight merchandise categories, and the unit-count column for each
CATEGORIES = ["Apparel", "Home", "Outdoor & Garden", "Electronics",
              "Beauty & Wellness", "Grocery & Pantry", "Toys & Seasonal", "Sports & Fitness"]
UNIT_COLS = ["u_apparel", "u_home", "u_outdoor", "u_electronics",
             "u_beauty", "u_grocery", "u_toys", "u_sports"]

# Shrinkage toward the average shopper, in units. A customer with this many units
# is pulled half way back, which stops a two-item buyer looking like a specialist.
SHRINKAGE_UNITS = 20
# A persona is only assigned when the best-fitting one explains the basket at least
# this many times better than the runner-up (log scale).
MIN_LOG_ODDS = 2.0

# Clustering inputs: the shape of a customer's shopping, never its size.
SHAPE = [
    "log_basket", "log_gap", "categories_per_order", "distinct_categories", "promo_line_share",
    "store_share", "web_share", "app_share", "weekend_share", "q4_share", "redemption_rate",
    "share_apparel", "share_home", "share_outdoor", "share_electronics", "share_beauty",
    "share_grocery", "share_toys", "share_sports", "share_private_label",
    "log_sessions_per_order", "abandoned_per_order",
]

LABELS = {
    "log_basket": "Average basket", "log_gap": "Days between orders", "categories_per_order": "Categories per order",
    "distinct_categories": "Categories bought in a year", "promo_line_share": "Share of items on promotion",
    "store_share": "Orders in store", "web_share": "Orders on web", "app_share": "Orders in app",
    "weekend_share": "Orders at the weekend", "q4_share": "Orders in November and December",
    "redemption_rate": "Orders using points", "share_apparel": "Apparel share of spend",
    "share_home": "Home share of spend", "share_outdoor": "Outdoor and garden share", "share_electronics": "Electronics share",
    "share_beauty": "Beauty and wellness share", "share_grocery": "Grocery and pantry share", "share_toys": "Toys and seasonal share",
    "share_sports": "Sports and fitness share", "share_private_label": "Private-label share",
    "log_sessions_per_order": "Web sessions per order", "abandoned_per_order": "Abandoned carts per order",
}
