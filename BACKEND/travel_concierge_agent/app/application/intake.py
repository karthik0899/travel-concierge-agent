"""Intake — turn a free-text customer message into a structured DisruptionReport.

The customer just describes what happened ("my flight 6E2341 on PNR001 was
cancelled"); intake uses the LLM (one shot, no tools) to extract the booking
reference and a first-guess disruption type. The Disruption Assessment agent
later confirms/corrects the type from flight data, so intake only needs to be
roughly right.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from app.domain.case_file import DisruptionReport
from app.domain.enums import DisruptionType
from app.utils.jsonx import extract_json

_TYPES = [t.value for t in DisruptionType]

_SCHEMA = {
    "type": "object",
    "properties": {
        "booking_ref": {"type": "string", "description": "PNR / booking reference, e.g. PNR001 or ABC123"},
        "disruption_type": {"type": "string", "enum": _TYPES},
    },
    "required": ["booking_ref", "disruption_type"],
}

_SYSTEM = (
    "You are an intake assistant for an airline disruption desk. From the customer's "
    "message, extract their booking reference (a PNR like PNR001 or ABC123) and classify "
    f"the disruption into exactly one of: {_TYPES}.\n"
    "Reply with ONLY a JSON object conforming to this schema (no prose, no fences):\n"
    f"{json.dumps(_SCHEMA)}"
)

# fallback: PNR-like tokens (3 letters + 3 digits, or a 6-char alphanumeric)
_REF_RE = re.compile(r"\b([A-Z]{3}\d{3}|[A-Z]{2}\d{4}|[A-Z0-9]{6})\b")


def _fallback_ref(text: str) -> str | None:
    m = _REF_RE.search(text.upper())
    return m.group(1) if m else None


def parse_report(raw_text: str, provider) -> DisruptionReport:
    turn = provider.complete(system=_SYSTEM,
                             messages=[{"role": "user", "content": raw_text}],
                             tools=None, force_text=True)
    data = {}
    try:
        data = json.loads(extract_json(turn.get("text") or ""))
    except (json.JSONDecodeError, ValueError):
        pass

    ref = data.get("booking_ref") or _fallback_ref(raw_text)
    if not ref:
        raise ValueError("Could not find a booking reference in the message.")

    dtype = data.get("disruption_type")
    if dtype not in _TYPES:
        dtype = DisruptionType.cancelled_flight.value   # safe default; assessment corrects it

    return DisruptionReport(
        raw_text=raw_text,
        booking_ref=ref,
        disruption_type=DisruptionType(dtype),
        reported_at=datetime.now(timezone.utc),
    )
