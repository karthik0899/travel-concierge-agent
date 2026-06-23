SCHEMA = {
    "name": "submit_claim",
    "description": "File a compensation claim for an assessed amount. Pass the rule id from "
                   "calculate_compensation (rule_id for flight events, baggage_rule_id for baggage "
                   "events). Commits a real claim — only call after assessment confirms eligibility.",
    "parameters": {
        "type": "object",
        "properties": {
            "booking_ref": {"type": "string"},
            "event_type": {
                "type": "string",
                "enum": ["cancellation", "denied_boarding",
                         "lost_baggage", "delayed_baggage", "damaged_baggage"],
            },
            "amount": {"type": "number"},
            "rule_id": {"type": "string", "description": "DGCA rule id (flight events)"},
            "baggage_rule_id": {"type": "string", "description": "Baggage liability rule id (baggage events)"},
            "bag_tag": {"type": "string", "description": "Bag tag for baggage claims"},
            "currency": {"type": "string", "description": "Default INR"},
        },
        "required": ["booking_ref", "event_type", "amount"],
    },
}
