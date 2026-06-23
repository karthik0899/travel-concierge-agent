from __future__ import annotations

import uuid

from app.db import connection as db
from app.utils.serialize import jsonable


def run(booking_ref: str, flight_no: str, seat: str | None = None) -> dict:
    # All statements share one transaction so seat reservation is atomic.
    with db.cursor() as cur:
        cur.execute("SELECT 1 FROM bookings WHERE booking_ref = %s", (booking_ref,))
        if cur.fetchone() is None:
            return {"booked": False, "reason": f"No booking {booking_ref}"}

        cur.execute(
            "SELECT flight_id, seats_available FROM flights WHERE flight_no = %s FOR UPDATE",
            (flight_no,),
        )
        flight = cur.fetchone()
        if flight is None:
            return {"booked": False, "reason": f"No flight {flight_no}"}
        if flight["seats_available"] <= 0:
            return {"booked": False, "reason": f"Flight {flight_no} has no seats available"}

        cur.execute(
            "SELECT COALESCE(MAX(segment_order), 0) AS m FROM booking_segments WHERE booking_ref = %s",
            (booking_ref,),
        )
        next_order = cur.fetchone()["m"] + 1

        cur.execute(
            """
            INSERT INTO booking_segments (booking_ref, flight_id, segment_order, seat, status)
            VALUES (%s, %s, %s, %s, 'confirmed')
            RETURNING segment_id
            """,
            (booking_ref, flight["flight_id"], next_order, seat),
        )
        new_segment_id = cur.fetchone()["segment_id"]

        cur.execute(
            "UPDATE flights SET seats_available = seats_available - 1 WHERE flight_id = %s",
            (flight["flight_id"],),
        )
        cur.execute(
            "UPDATE booking_segments SET status = 'rebooked' "
            "WHERE booking_ref = %s AND status = 'disrupted'",
            (booking_ref,),
        )
        cur.execute(
            "UPDATE bookings SET status = 'rebooked' WHERE booking_ref = %s",
            (booking_ref,),
        )

    return jsonable({
        "booked": True,
        "booking_ref": booking_ref,
        "flight_no": flight_no,
        "new_segment_id": new_segment_id,
        "seat": seat,
        "confirmation": "RBK-" + uuid.uuid4().hex[:8].upper(),
    })
