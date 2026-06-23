SCHEMA = {
    "name": "book_hotel",
    "description": "Book a hotel room for an overnight stay: reserves a room and issues a "
                   "confirmation. Commits a real change — only call after the hotel is chosen.",
    "parameters": {
        "type": "object",
        "properties": {
            "booking_ref": {"type": "string"},
            "hotel_id": {"type": "string", "description": "Hotel id from search_hotels"},
            "check_in": {"type": "string", "description": "ISO datetime"},
            "check_out": {"type": "string", "description": "ISO datetime"},
        },
        "required": ["booking_ref", "hotel_id", "check_in", "check_out"],
    },
}
