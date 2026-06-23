"""LLM provider dispatcher.

One entry point, selected by the LLM_PROVIDER env var:
    LLM_PROVIDER=cortex  -> Gemini via the Cortex OpenAI-compatible gateway (native tools)
    LLM_PROVIDER=claude  -> Claude via the Claude Agent SDK (prompted tool protocol)

Both implement the same Provider Protocol (complete(...) -> {text, tool_calls}),
so swapping is a pure config change — the engine is identical for both.
"""

from __future__ import annotations

import os


def get_provider(name: str | None = None):
    name = (name or os.environ.get("LLM_PROVIDER", "cortex")).lower()
    if name == "cortex":
        from .cortex_provider import CortexProvider
        return CortexProvider()
    if name == "claude":
        from .claude_provider import ClaudeProvider
        return ClaudeProvider()
    raise ValueError(f"Unknown LLM_PROVIDER: {name!r} (use 'cortex' or 'claude')")


def provider_name() -> str:
    return os.environ.get("LLM_PROVIDER", "cortex").lower()
