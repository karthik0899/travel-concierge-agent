from __future__ import annotations

from app.db import connection as db
from app.utils.serialize import jsonable


def run(booking_ref: str, last_name: str | None = None) -> dict:
    booking = db.query_one(
        """
        SELECT b.booking_ref, b.fare_class, b.status,
               b.basic_fare, b.fuel_charge, b.taxes_fees, b.total_price, b.currency,
               c.customer_id, c.name, c.email, c.phone, c.loyalty_tier
        FROM bookings b
        JOIN customers c ON c.customer_id = b.customer_id
        WHERE b.booking_ref = %s
        """,
        (booking_ref,),
    )
    if not booking:
        return {"verified": False, "reason": f"No booking found for reference {booking_ref}"}

    if last_name and last_name.strip().lower() not in booking["name"].lower():
        return {"verified": False, "reason": "Passenger name does not match the booking"}

    segments = db.query(
        """
        SELECT s.segment_order, s.seat, s.status AS segment_status,
               f.flight_no, f.origin, f.destination,
               f.sched_departure, f.sched_arrival, f.status AS flight_status
        FROM booking_segments s
        JOIN flights f ON f.flight_id = s.flight_id
        WHERE s.booking_ref = %s
        ORDER BY s.segment_order
        """,
        (booking_ref,),
    )

    return jsonable({
        "verified": True,
        "customer": {
            "customer_id": booking["customer_id"],
            "name": booking["name"],
            "email": booking["email"],
            "phone": booking["phone"],
            "loyalty_tier": booking["loyalty_tier"],
        },
        "booking": {
            "booking_ref": booking["booking_ref"],
            "fare_class": booking["fare_class"],
            "status": booking["status"],
            "basic_fare": booking["basic_fare"],
            "fuel_charge": booking["fuel_charge"],
            "taxes_fees": booking["taxes_fees"],
            "total_price": booking["total_price"],
            "currency": booking["currency"],
        },
        "itinerary": segments,
    })
