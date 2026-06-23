from __future__ import annotations

from app.db import connection as db
from app.utils.serialize import jsonable


def run(flight_no: str) -> dict:
    flight = db.query_one(
        """
        SELECT f.flight_no, a.name AS airline, f.origin, f.destination,
               f.sched_departure, f.sched_arrival, f.block_minutes,
               f.status, f.delay_minutes, f.delay_hours,
               f.cancel_cause, f.cancelled_at, f.seats_available,
               f.base_price, f.currency,
               CASE WHEN f.cancelled_at IS NOT NULL
                    THEN EXTRACT(EPOCH FROM (f.sched_departure - f.cancelled_at)) / 3600.0
                    END AS notice_hours
        FROM flights f
        JOIN airlines a ON a.code = f.airline_code
        WHERE f.flight_no = %s
        """,
        (flight_no,),
    )
    if not flight:
        return {"found": False, "reason": f"No flight found with number {flight_no}"}
    return jsonable({"found": True, **flight})
