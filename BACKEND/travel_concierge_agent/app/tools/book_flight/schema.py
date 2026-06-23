SCHEMA = {
    "name": "book_flight",
    "description": "Rebook a passenger onto an alternative flight: adds a new segment to "
                   "the booking, reserves a seat, and marks the disrupted segments as rebooked. "
                   "Commits a real change — only call after the option is chosen.",
    "parameters": {
        "type": "object",
        "properties": {
            "booking_ref": {"type": "string"},
            "flight_no": {"type": "string", "description": "The alternative flight to book"},
            "seat": {"type": "string", "description": "Optional seat assignment"},
        },
        "required": ["booking_ref", "flight_no"],
    },
}
