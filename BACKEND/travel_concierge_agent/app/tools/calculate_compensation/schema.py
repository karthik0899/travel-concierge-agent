SCHEMA = {
    "name": "calculate_compensation",
    "description": "Assess compensation eligibility and amount under Indian law for a "
                   "disruption. Dispatches by event_type: 'cancellation' and 'denied_boarding' "
                   "use DGCA block-time/fare rules; '*_baggage' use Carriage-by-Air-Act/Montreal "
                   "weight rules. Returns the rule id needed by submit_claim. Pure rule lookup — "
                   "no money is paid here.",
    "parameters": {
        "type": "object",
        "properties": {
            "booking_ref": {"type": "string"},
            "event_type": {
                "type": "string",
                "enum": ["cancellation", "denied_boarding",
                         "lost_baggage", "delayed_baggage", "damaged_baggage"],
            },
            "alt_delay_hours": {"type": "number",
                                "description": "Denied boarding only: hours until the alternate flight"},
            "bag_tag": {"type": "string", "description": "Baggage events only: the bag tag"},
            "jurisdiction": {"type": "string", "enum": ["domestic", "international"],
                             "description": "Baggage events only (default domestic)"},
        },
        "required": ["booking_ref", "event_type"],
    },
}
