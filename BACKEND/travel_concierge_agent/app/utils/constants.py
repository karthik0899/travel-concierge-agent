"""Shared constants — single source of truth for thresholds & defaults.

Compensation amounts live in the DB (dgca_compensation_rules,
baggage_liability_rules) — NOT here. These are app-level knobs only.
"""

from __future__ import annotations

DEFAULT_CURRENCY = "INR"
DEFAULT_JURISDICTION = "domestic"

# DGCA cancellation notice window: cash compensation applies when the airline
# informs the passenger less than this many hours before departure.
CANCELLATION_NOTICE_HOURS = 24

# Duty-of-care delay thresholds (hours) — mirror dgca_care_rules.
MEALS_DELAY_HOURS = 2.0
REFUND_DELAY_HOURS = 6.0

# Engine guardrails: max tool-calling steps per agent (loose loop cap).
DEFAULT_MAX_STEPS = 4
MAX_STEPS_BY_SKILL = {
    "identity": 2,
    "disruption": 3,
    "rebooking": 6,
    "accommodation": 4,
    "compensation": 3,
    "claim": 2,
    "summary": 2,
}

# The deterministic pipeline order (orchestrator runs skills in this sequence).
PIPELINE = ["identity", "disruption", "rebooking", "accommodation", "compensation", "claim", "summary"]
