from __future__ import annotations

import uuid

from app.db import connection as db
from app.utils.constants import DEFAULT_CURRENCY
from app.utils.serialize import jsonable


def run(booking_ref: str, event_type: str, amount: float,
        rule_id: str | None = None, baggage_rule_id: str | None = None,
        bag_tag: str | None = None, currency: str = DEFAULT_CURRENCY) -> dict:
    booking = db.query_one(
        "SELECT customer_id FROM bookings WHERE booking_ref = %s", (booking_ref,)
    )
    if not booking:
        return {"claim_submitted": False, "reason": f"No booking {booking_ref}"}

    claim_ref = "CLM-" + uuid.uuid4().hex[:8].upper()
    db.execute(
        """
        INSERT INTO claims
            (claim_ref, booking_ref, customer_id, event_type,
             rule_id, baggage_rule_id, bag_tag, amount, currency)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (claim_ref, booking_ref, booking["customer_id"], event_type,
         rule_id, baggage_rule_id, bag_tag, amount, currency),
    )
    return jsonable({
        "claim_submitted": True,
        "claim_ref": claim_ref,
        "status": "submitted",
        "amount": amount,
        "currency": currency,
    })
