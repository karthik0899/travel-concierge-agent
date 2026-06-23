"""Enums mirroring the DB enum types (keep in sync with db/schema.sql)."""

from __future__ import annotations

from enum import Enum


class LoyaltyTier(str, Enum):
    none = "none"
    silver = "silver"
    gold = "gold"
    platinum = "platinum"


class DisruptionType(str, Enum):
    cancelled_flight = "cancelled_flight"
    flight_delay = "flight_delay"
    missed_connection = "missed_connection"
    denied_boarding = "denied_boarding"
    lost_baggage = "lost_baggage"
    delayed_baggage = "delayed_baggage"
    damaged_baggage = "damaged_baggage"


class CancelCause(str, Enum):
    airline_fault = "airline_fault"
    extraordinary_circumstance = "extraordinary_circumstance"


class CompEvent(str, Enum):
    """Cash-compensable events (dispatch key for calculate_compensation)."""
    cancellation = "cancellation"
    denied_boarding = "denied_boarding"
    lost_baggage = "lost_baggage"
    delayed_baggage = "delayed_baggage"
    damaged_baggage = "damaged_baggage"


class CaseStatus(str, Enum):
    open = "open"
    awaiting_input = "awaiting_input"   # paused at an approval gate, waiting for the customer
    rebooked = "rebooked"
    compensated = "compensated"
    closed = "closed"
    failed = "failed"
