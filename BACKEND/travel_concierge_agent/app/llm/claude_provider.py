"""Claude provider — via the Claude Agent SDK (Claude Code auth, no API key).

The Agent SDK does TEXT generation, so this provider implements tool-calling with
a prompted JSON protocol instead of native function calling:

  * To call a tool, the model replies with ONLY:  {"tool_call": {"name": ..., "arguments": {...}}}
  * To finish, the model replies with ONLY its final result JSON.

The provider parses that text into the engine's normalized Turn shape, so the
engine loop is identical whether Cortex (native tools) or Claude (prompted) runs.

Install: uv add claude-agent-sdk   (requires the logged-in Claude Code CLI)
Env: CLAUDE_MODEL=claude-sonnet-4-6   (optional override)
"""

from __future__ import annotations

import asyncio
import json
import os

from app.utils.jsonx import extract_json

DEFAULT_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")


def _resolve_model(model: str | None) -> str:
    if not model:
        return DEFAULT_MODEL
    if model.startswith("claude"):
        return model
    # a Gemini-style name slipped through -> map to a Claude tier
    return "claude-sonnet-4-6" if "pro" in model else "claude-haiku-4-5"


def _tool_protocol(tools: list[dict]) -> str:
    lines = [
        "You can use tools to gather information or take actions.",
        'To CALL a tool, reply with ONLY this JSON and nothing else:',
        '  {"tool_call": {"name": "<tool_name>", "arguments": { ... }}}',
        "Call one tool at a time; you will receive its result, then may call another.",
        "To FINISH, reply with ONLY your final result JSON (no tool_call wrapper).",
        "",
        "Available tools:",
    ]
    for t in tools:
        f = t["function"]
        lines.append(f'- {f["name"]}: {f.get("description", "")}  '
                     f'parameters={json.dumps(f["parameters"])}')
    return "\n".join(lines)


def _render_conversation(messages: list[dict]) -> str:
    parts: list[str] = []
    for m in messages:
        role = m["role"]
        if role == "user":
            parts.append(f"USER:\n{m['content']}")
        elif role == "assistant":
            for tc in m.get("tool_calls") or []:
                parts.append(f"ASSISTANT (called {tc['name']} with "
                             f"{json.dumps(tc.get('arguments') or {})})")
            if m.get("content"):
                parts.append(f"ASSISTANT:\n{m['content']}")
        elif role == "tool":
            parts.append(f"TOOL RESULT ({m['name']}):\n{m['content']}")
    return "\n\n".join(parts)


def _parse_tool_call(text: str, known: set[str]) -> dict | None:
    try:
        obj = json.loads(extract_json(text))
    except (json.JSONDecodeError, ValueError):
        return None
    if isinstance(obj, dict) and isinstance(obj.get("tool_call"), dict):
        tc = obj["tool_call"]
        if tc.get("name") in known:
            return {"name": tc["name"], "arguments": tc.get("arguments") or {}}
    return None


async def _ask(system: str, prompt: str, model: str) -> str:
    from claude_agent_sdk import (  # lazy: module imports without the dep
        AssistantMessage, ClaudeAgentOptions, TextBlock, query,
    )
    options = ClaudeAgentOptions(
        system_prompt=system,
        model=_resolve_model(model),
        allowed_tools=[],            # we drive tools ourselves via the prompted protocol
        permission_mode="dontAsk",
    )
    text = ""
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    text += block.text
    return text


class ClaudeProvider:
    name = "claude"

    def __init__(self, model: str | None = None):
        self.default_model = model or DEFAULT_MODEL

    def complete(self, *, system: str, messages: list[dict], tools: list[dict] | None,
                 model: str | None = None, temperature: float = 0.1,
                 force_text: bool = False) -> dict:
        full_system = system
        known: set[str] = set()
        if tools and not force_text:
            full_system = f"{system}\n\n{_tool_protocol(tools)}"
            known = {t["function"]["name"] for t in tools}

        prompt = _render_conversation(messages)
        text = asyncio.run(_ask(full_system, prompt, model or self.default_model))

        if known:
            call = _parse_tool_call(text, known)
            if call:
                return {"text": None,
                        "tool_calls": [{"id": f"call_{call['name']}",
                                        "name": call["name"],
                                        "arguments": call["arguments"]}]}
        return {"text": text, "tool_calls": []}
