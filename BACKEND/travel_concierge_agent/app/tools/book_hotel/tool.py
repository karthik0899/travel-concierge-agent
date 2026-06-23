from __future__ import annotations

import uuid

from app.db import connection as db
from app.utils.serialize import jsonable


def run(booking_ref: str, hotel_id: str, check_in: str, check_out: str) -> dict:
    with db.cursor() as cur:
        cur.execute("SELECT customer_id FROM bookings WHERE booking_ref = %s", (booking_ref,))
        booking = cur.fetchone()
        if booking is None:
            return {"booked": False, "reason": f"No booking {booking_ref}"}

        cur.execute(
            "SELECT name, price_per_night, currency, rooms_available "
            "FROM hotels WHERE hotel_id = %s FOR UPDATE",
            (hotel_id,),
        )
        hotel = cur.fetchone()
        if hotel is None:
            return {"booked": False, "reason": f"No hotel {hotel_id}"}
        if hotel["rooms_available"] <= 0:
            return {"booked": False, "reason": f"{hotel['name']} has no rooms available"}

        confirmation = "HTL-" + uuid.uuid4().hex[:8].upper()
        cur.execute(
            """
            INSERT INTO hotel_bookings
                (confirmation, hotel_id, customer_id, booking_ref, check_in, check_out, price, currency)
            VALUES (%s, %s, %s, %s, %s::timestamptz, %s::timestamptz, %s, %s)
            """,
            (confirmation, hotel_id, booking["customer_id"], booking_ref,
             check_in, check_out, hotel["price_per_night"], hotel["currency"]),
        )
        cur.execute(
            "UPDATE hotels SET rooms_available = rooms_available - 1 WHERE hotel_id = %s",
            (hotel_id,),
        )

    return jsonable({
        "booked": True,
        "confirmation": confirmation,
        "hotel": hotel["name"],
        "price_per_night": hotel["price_per_night"],
        "currency": hotel["currency"],
        "check_in": check_in,
        "check_out": check_out,
    })
