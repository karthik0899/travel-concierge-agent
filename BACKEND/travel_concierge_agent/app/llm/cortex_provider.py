"""Cortex provider — Gemini via the Cortex OpenAI-compatible gateway.

Implements the Provider Protocol with NATIVE function calling. Translates the
engine's normalized messages to OpenAI chat format and back.

Env (.env supported):
    CORTEX_API_KEY=...
    CORTEX_BASE_URL=...      # gateway URL ending in /v1
    CORTEX_MODEL=gemini-2.5-flash   (optional override)
"""

from __future__ import annotations

import json
import os

DEFAULT_MODEL = os.environ.get("CORTEX_MODEL", "gemini-2.5-flash")


def _to_openai(m: dict) -> dict:
    """Normalized engine message -> OpenAI chat message."""
    role = m["role"]
    if role == "assistant" and m.get("tool_calls"):
        return {
            "role": "assistant",
            "content": m.get("content"),
            "tool_calls": [
                {"id": tc["id"], "type": "function",
                 "function": {"name": tc["name"],
                              "arguments": json.dumps(tc.get("arguments") or {})}}
                for tc in m["tool_calls"]
            ],
        }
    if role == "tool":
        return {"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["content"]}
    return {"role": role, "content": m.get("content")}


class CortexProvider:
    name = "cortex"

    def __init__(self, model: str | None = None):
        self.default_model = model or DEFAULT_MODEL
        self._client = None

    def client(self):
        if self._client is None:
            from openai import OpenAI  # lazy: module imports without the dep
            base_url = os.environ.get("CORTEX_BASE_URL")
            if not base_url:
                raise RuntimeError("CORTEX_BASE_URL is not set (see .env.example).")
            self._client = OpenAI(base_url=base_url, api_key=os.environ["CORTEX_API_KEY"])
        return self._client

    def complete(self, *, system: str, messages: list[dict], tools: list[dict] | None,
                 model: str | None = None, temperature: float = 0.1,
                 force_text: bool = False) -> dict:
        oai_messages = [{"role": "system", "content": system}] + [_to_openai(m) for m in messages]
        kwargs: dict = {
            "model": model or self.default_model,
            "temperature": temperature,
            "messages": oai_messages,
        }
        if tools and not force_text:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        elif force_text:
            kwargs["response_format"] = {"type": "json_object"}   # nudge bare JSON on the final step

        resp = self.client().chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        tool_calls = [
            {"id": tc.id, "name": tc.function.name,
             "arguments": json.loads(tc.function.arguments or "{}")}
            for tc in (msg.tool_calls or [])
        ]
        return {"text": msg.content, "tool_calls": tool_calls}
