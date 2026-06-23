SCHEMA = {
    "name": "request_user_input",
    "description": "Pause and ask the customer a question — use this to confirm a booking "
                   "or let them choose between options BEFORE committing. The pipeline halts "
                   "until the customer replies, then you continue with their answer.",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "The question to ask the customer"},
            "options": {"type": "array", "items": {"type": "string"},
                        "description": "Optional list of choices to present"},
        },
        "required": ["question"],
    },
}
