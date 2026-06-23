"""Compensation assessment — Indian law, three regimes, all data-driven.

  cancellation     -> DGCA block-time band; min(cap, 1.0 * (basic+fuel));
                      gated by cause=airline_fault (extraordinary waives cash).
  denied_boarding  -> DGCA alt-delay band; min(cap, multiplier * (basic+fuel)).
  *_baggage        -> Carriage by Air Act / Montreal; domestic min(cap, per_kg*weight),
                      international fixed cap.
"""

from __future__ import annotations

from app.db import connection as db
from app.utils.constants import CANCELLATION_NOTICE_HOURS, DEFAULT_CURRENCY
from app.utils.serialize import jsonable

_BAGGAGE_EVENTS = {"lost_baggage", "delayed_baggage", "damaged_baggage"}


def _fare_basis(booking_ref: str):
    row = db.query_one(
        "SELECT basic_fare, fuel_charge FROM bookings WHERE booking_ref = %s",
        (booking_ref,),
    )
    if not row:
        return None
    return float(row["basic_fare"]) + float(row["fuel_charge"])


def _cancellation(booking_ref: str) -> dict:
    fare = _fare_basis(booking_ref)
    if fare is None:
        return {"eligible": False, "reason": f"No booking {booking_ref}"}

    flight = db.query_one(
        """
        SELECT f.flight_no, f.block_minutes, f.cancel_cause,
               EXTRACT(EPOCH FROM (f.sched_departure - f.cancelled_at)) / 3600.0 AS notice_hours
        FROM booking_segments s
        JOIN flights f ON f.flight_id = s.flight_id
        WHERE s.booking_ref = %s AND f.status = 'cancelled'
        ORDER BY s.segment_order
        LIMIT 1
        """,
        (booking_ref,),
    )
    if not flight:
        return {"eligible": False, "reason": "No cancelled flight on this booking"}

    if flight["cancel_cause"] != "airline_fault":
        return {"event_type": "cancellation", "eligible": False, "amount": 0.0,
                "currency": DEFAULT_CURRENCY,
                "reason": "Extraordinary circumstance — no cash compensation due "
                          "(duty of care still applies)"}

    rule = db.query_one(
        """
        SELECT rule_id, cap_amount, fare_multiplier, car_ref
        FROM dgca_compensation_rules
        WHERE event_type = 'cancellation'
          AND %s > block_min_minutes
          AND %s <= COALESCE(block_max_minutes, 2147483647)
        """,
        (flight["block_minutes"], flight["block_minutes"]),
    )
    if not rule:
        return {"eligible": False, "reason": "No matching DGCA cancellation band"}

    amount = min(float(rule["cap_amount"]), float(rule["fare_multiplier"]) * fare)
    notice = flight["notice_hours"]
    return jsonable({
        "event_type": "cancellation",
        "eligible": True,
        "amount": round(amount, 2),
        "currency": DEFAULT_CURRENCY,
        "rule_id": rule["rule_id"],
        "rule_ref": rule["car_ref"],
        "reason": f"Block time {flight['block_minutes']} min, airline fault, "
                  f"{notice:.1f}h notice -> min(cap {rule['cap_amount']}, fare {fare:.0f})",
    })


def _denied_boarding(booking_ref: str, alt_delay_hours: float | None) -> dict:
    fare = _fare_basis(booking_ref)
    if fare is None:
        return {"eligible": False, "reason": f"No booking {booking_ref}"}
    if alt_delay_hours is None:
        return {"eligible": False, "reason": "alt_delay_hours required for denied boarding"}

    rule = db.query_one(
        """
        SELECT rule_id, cap_amount, fare_multiplier, car_ref
        FROM dgca_compensation_rules
        WHERE event_type = 'denied_boarding'
          AND %s > alt_min_hours
          AND %s <= COALESCE(alt_max_hours, 1e9)
        """,
        (alt_delay_hours, alt_delay_hours),
    )
    if not rule:
        return {"eligible": False, "reason": "No matching DGCA denied-boarding band"}

    amount = min(float(rule["cap_amount"]), float(rule["fare_multiplier"]) * fare)
    return jsonable({
        "event_type": "denied_boarding",
        "eligible": amount > 0,
        "amount": round(amount, 2),
        "currency": DEFAULT_CURRENCY,
        "rule_id": rule["rule_id"],
        "rule_ref": rule["car_ref"],
        "reason": f"Alternate {alt_delay_hours}h later -> "
                  f"min(cap {rule['cap_amount']}, {rule['fare_multiplier']}x fare {fare:.0f})",
    })


def _baggage(booking_ref: str, event_type: str, bag_tag: str | None,
             jurisdiction: str) -> dict:
    bag = db.query_one(
        "SELECT bag_tag, weight_kg FROM baggage "
        "WHERE booking_ref = %s AND (%s::text IS NULL OR bag_tag = %s) "
        "ORDER BY (status IN ('lost','delayed','damaged')) DESC LIMIT 1",
        (booking_ref, bag_tag, bag_tag),
    )
    if not bag:
        return {"eligible": False, "reason": "No baggage found on this booking"}

    rule = db.query_one(
        """
        SELECT rule_id, per_kg_amount, cap_amount, currency, claim_deadline_days, legal_ref
        FROM baggage_liability_rules
        WHERE jurisdiction = %s AND event_type = %s
        """,
        (jurisdiction, event_type),
    )
    if not rule:
        return {"eligible": False, "reason": f"No {jurisdiction} rule for {event_type}"}

    weight = float(bag["weight_kg"])
    cap = float(rule["cap_amount"])
    if rule["per_kg_amount"] is not None:        # domestic: weight-based
        amount = min(cap, float(rule["per_kg_amount"]) * weight)
        basis = f"min(cap {cap:.0f}, {rule['per_kg_amount']}/kg x {weight}kg)"
    else:                                        # international: fixed cap
        amount = cap
        basis = f"fixed cap {cap:.0f}"

    return jsonable({
        "event_type": event_type,
        "eligible": True,
        "amount": round(amount, 2),
        "currency": rule["currency"],
        "baggage_rule_id": rule["rule_id"],
        "rule_ref": rule["legal_ref"],
        "bag_tag": bag["bag_tag"],
        "claim_deadline_days": rule["claim_deadline_days"],
        "reason": f"{jurisdiction} baggage liability -> {basis}",
    })


def run(booking_ref: str, event_type: str, alt_delay_hours: float | None = None,
        bag_tag: str | None = None, jurisdiction: str = "domestic") -> dict:
    if event_type == "cancellation":
        return _cancellation(booking_ref)
    if event_type == "denied_boarding":
        return _denied_boarding(booking_ref, alt_delay_hours)
    if event_type in _BAGGAGE_EVENTS:
        return _baggage(booking_ref, event_type, bag_tag, jurisdiction)
    return {"eligible": False, "reason": f"Unsupported event_type: {event_type}"}
