"""Shared settings for the marketing mix model."""
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
REPO = PROJECT.parents[1]
WORK = PROJECT / "work"
OUT = PROJECT / "outputs"
SEED = 42

CHANNELS = ["tv", "paid_search", "paid_social", "display", "flyer", "email"]
CHANNEL_NAMES = {"tv": "TV", "paid_search": "Paid Search", "paid_social": "Paid Social",
                 "display": "Display", "flyer": "Flyer", "email": "Email"}
TRUE_NAMES = {v: k for k, v in CHANNEL_NAMES.items()}

# Candidate transforms searched for every channel
DECAYS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
SHAPES = [0.8, 1.1, 1.4, 1.7, 2.0]
HALF_SAT = [0.4, 0.6, 0.8, 1.0, 1.3, 1.7, 2.3]      # as a multiple of average adstocked spend

MARGIN_RATE = 0.42     # gross margin earned on incremental revenue, for ROI in margin terms
