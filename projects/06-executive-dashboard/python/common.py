"""Shared settings for the executive dashboard."""
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
REPO = PROJECT.parents[1]
WORK = PROJECT / "work"
OUT = PROJECT / "outputs"
SEED = 42

# The dashboard reports as at the last complete week in the data.
AS_OF_WEEK = 155

# Every metric on the front page, with the direction that counts as good and the
# decision it exists to support. A metric with no decision does not belong here.
METRICS = [
    {"key": "revenue", "label": "Revenue", "unit": "cad", "good": "up",
     "owner": "Chief executive", "decision": "Is the business on plan this quarter?"},
    {"key": "margin", "label": "Gross margin", "unit": "cad", "good": "up",
     "owner": "Finance", "decision": "Is growth being bought with discount?"},
    {"key": "active_customers", "label": "Active customers", "unit": "count", "good": "up",
     "owner": "Marketing", "decision": "Is the base growing or just spending more?"},
    {"key": "new_customers", "label": "New customers", "unit": "count", "good": "up",
     "owner": "Acquisition", "decision": "Is acquisition keeping pace with lapsing?"},
    {"key": "avg_basket", "label": "Average basket", "unit": "cad", "good": "up",
     "owner": "Merchandising", "decision": "Are people buying more per trip?"},
    {"key": "margin_rate", "label": "Margin rate", "unit": "pct", "good": "up",
     "owner": "Merchandising", "decision": "Is the discount plan holding?"},
    {"key": "price_index", "label": "Realised price", "unit": "pct", "good": "up",
     "owner": "Merchandising", "decision": "How much of list price are we keeping?"},
    {"key": "digital_revenue_share", "label": "Digital share", "unit": "pct", "good": "up",
     "owner": "Digital", "decision": "Is the channel shift continuing?"},
    {"key": "media_spend", "label": "Media spend", "unit": "cad", "good": "flat",
     "owner": "Marketing", "decision": "Are we spending to plan?"},
    {"key": "service_contacts", "label": "Service contacts", "unit": "count", "good": "down",
     "owner": "Customer service", "decision": "Is service load rising faster than orders?"},
]

# Statistical process control. A point outside three standard deviations of its own
# seasonal baseline is a signal; so is a run of eight weeks on one side of it.
SIGMA_ALERT = 3.0
SIGMA_WARN = 2.0
RUN_LENGTH = 8
