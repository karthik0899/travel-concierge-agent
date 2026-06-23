"""Pull a single JSON object out of an LLM reply (fences/prose-safe).

Shared by the engine (parsing final results) and the Claude provider (parsing
prompted tool calls), since neither the SDK text path nor a chatty model is
guaranteed to return bare JSON.
"""

from __future__ import annotations


def extract_json(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        t = t.rsplit("```", 1)[0].strip()
    start = t.find("{")
    if start == -1:
        return t
    depth, in_str, esc = 0, False, False
    for i in range(start, len(t)):
        ch = t[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return t[start:i + 1]
    return t[start:]
