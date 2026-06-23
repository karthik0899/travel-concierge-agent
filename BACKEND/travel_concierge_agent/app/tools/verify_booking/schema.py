SCHEMA = {
    "name": "verify_booking",
    "description": "Look up a booking by its reference and return the customer, "
                   "fare and full itinerary. Optionally check the passenger's last name.",
    "parameters": {
        "type": "object",
        "properties": {
            "booking_ref": {"type": "string", "description": "PNR / booking reference, e.g. ABC123"},
            "last_name": {"type": "string", "description": "Optional surname to verify against the booking"},
        },
        "required": ["booking_ref"],
    },
}
