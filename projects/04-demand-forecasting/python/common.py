"""Shared settings for the demand forecasting project."""
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
REPO = PROJECT.parents[1]
WORK = PROJECT / "work"
OUT = PROJECT / "outputs"
SEED = 42

LEVELS = ["Total", "Category", "Store", "Store x Category"]

# Backtest design: forecasts are made every four weeks from week 104 onwards and
# judged up to thirteen weeks ahead, the lead time a buying team works to.
FIRST_ORIGIN = 104
ORIGIN_STEP = 4
N_ORIGINS = 10
MAX_HORIZON = 13

# Ordering economics (stated assumptions, adjustable in the explorer).
# A unit short costs the margin that was not earned; a unit over costs the
# markdown needed to clear it.
MARGIN_RATE = 0.42          # gross margin on a unit sold at full price
MARKDOWN_RATE = 0.25        # share of retail given away to clear an overstock
