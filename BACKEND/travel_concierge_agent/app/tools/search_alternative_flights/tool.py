from __future__ import annotations

from app.db import connection as db
from app.utils.serialize import jsonable


def run(origin: str, destination: str, not_before: str | None = None,
        max_results: int = 5) -> dict:
    rows = db.query(
        """
        SELECT f.flight_no, a.name AS airline, f.origin, f.destination,
               f.sched_departure, f.sched_arrival, f.block_minutes,
               f.seats_available, f.base_price, f.currency
        FROM flights f
        JOIN airlines a ON a.code = f.airline_code
        WHERE f.origin = %s AND f.destination = %s
          AND f.status <> 'cancelled' AND f.seats_available > 0
          AND (%s::timestamptz IS NULL OR f.sched_departure >= %s::timestamptz)
        ORDER BY f.sched_departure
        LIMIT %s
        """,
        (origin, destination, not_before, not_before, max_results),
    )
    return jsonable({"count": len(rows), "flights": rows})
