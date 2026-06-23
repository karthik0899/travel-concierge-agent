"""Tool registry — one flat namespace; `allowed_tools` (per skill) does the scoping.

Each tool package exposes SCHEMA (function-calling spec) + run(**args). The
registry maps tool name -> module. A skill is granted a subset via get_tools().
"""

from __future__ import annotations

from . import (
    book_flight,
    book_hotel,
    calculate_compensation,
    get_flight_details,
    request_user_input,
    search_alternative_flights,
    search_hotels,
    submit_claim,
    verify_booking,
)

# request_user_input is a CONTROL tool — the engine intercepts it to pause the
# pipeline; it is never executed via run_tool.
PAUSE_TOOL = "request_user_input"

_MODULES = [
    book_flight, book_hotel, calculate_compensation, get_flight_details,
    request_user_input, search_alternative_flights, search_hotels, submit_claim,
    verify_booking,
]

REGISTRY = {m.SCHEMA["name"]: m for m in _MODULES}


def get_tools(allowed: list[str]) -> dict:
    """Scope the registry to a skill's allowed_tools. Fails loudly on typos."""
    missing = [n for n in allowed if n not in REGISTRY]
    if missing:
        raise KeyError(f"Unknown tools in allowed_tools: {missing} "
                       f"(known: {sorted(REGISTRY)})")
    return {n: REGISTRY[n] for n in allowed}


def openai_schemas(allowed: list[str]) -> list[dict]:
    """OpenAI/Cortex function-calling format for the allowed tools."""
    return [{"type": "function", "function": REGISTRY[n].SCHEMA} for n in allowed]


def run_tool(name: str, **args):
    return REGISTRY[name].run(**args)
