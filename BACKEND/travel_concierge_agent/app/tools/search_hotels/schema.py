SCHEMA = {
    "name": "search_hotels",
    "description": "Find hotels with rooms available near an airport, optionally filtered "
                   "by max price per night and minimum star rating.",
    "parameters": {
        "type": "object",
        "properties": {
            "near_airport": {"type": "string", "description": "Airport IATA code, e.g. DEL"},
            "max_price": {"type": "number", "description": "Max price per night"},
            "min_star": {"type": "integer", "description": "Minimum star rating (1-5)"},
            "max_results": {"type": "integer", "description": "Max rows to return (default 5)"},
        },
        "required": ["near_airport"],
    },
}
