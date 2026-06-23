SCHEMA = {
    "name": "get_flight_details",
    "description": "Get the current status of a flight by its number: schedule, block "
                   "time, delay, cancellation status and cause, and seats available.",
    "parameters": {
        "type": "object",
        "properties": {
            "flight_no": {"type": "string", "description": "Flight number, e.g. 6E2341"},
        },
        "required": ["flight_no"],
    },
}
