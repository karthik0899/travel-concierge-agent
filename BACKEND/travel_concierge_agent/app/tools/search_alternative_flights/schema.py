SCHEMA = {
    "name": "search_alternative_flights",
    "description": "Search bookable alternative flights on a route (only flights that "
                   "are not cancelled and have seats), optionally departing after a given time.",
    "parameters": {
        "type": "object",
        "properties": {
            "origin": {"type": "string", "description": "Origin IATA code, e.g. DEL"},
            "destination": {"type": "string", "description": "Destination IATA code, e.g. BOM"},
            "not_before": {"type": "string", "description": "ISO datetime; only flights departing at/after this"},
            "max_results": {"type": "integer", "description": "Max rows to return (default 5)"},
        },
        "required": ["origin", "destination"],
    },
}
