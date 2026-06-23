from __future__ import annotations

from app.db import connection as db
from app.utils.serialize import jsonable


def run(near_airport: str, max_price: float | None = None,
        min_star: int | None = None, max_results: int = 5) -> dict:
    rows = db.query(
        """
        SELECT hotel_id, name, city, near_airport, star_rating,
               price_per_night, currency, rooms_available
        FROM hotels
        WHERE near_airport = %s AND rooms_available > 0
          AND (%s::numeric IS NULL OR price_per_night <= %s::numeric)
          AND (%s::int IS NULL OR star_rating >= %s::int)
        ORDER BY price_per_night
        LIMIT %s
        """,
        (near_airport, max_price, max_price, min_star, min_star, max_results),
    )
    return jsonable({"count": len(rows), "hotels": rows})
