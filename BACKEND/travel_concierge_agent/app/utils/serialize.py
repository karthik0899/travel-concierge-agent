"""Make DB rows JSON-safe for tool results handed to the LLM."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID


def jsonable(o):
    if isinstance(o, dict):
        return {k: jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, Decimal):
        return float(o)
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if isinstance(o, UUID):
        return str(o)
    return o
