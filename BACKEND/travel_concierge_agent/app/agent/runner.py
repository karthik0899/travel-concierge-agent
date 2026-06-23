"""The general agent engine — one loose tool-calling loop that runs ANY skill.

The engine owns the loop; a Provider does single turns. Flow per skill:

    system = persona + output schema + "finish with JSON"
    loop up to skill.max_steps:
        turn = provider.complete(system, messages, tools=scoped)
        if turn has tool_calls:  run them, feed results back (errors as results)
        else:                    parse the text as the result JSON, validate it
                                 -> valid: done;  invalid: feed errors back, retry
    (last step forces a text answer so the loop always terminates)

The engine is provider-agnostic and domain-agnostic: it takes a Skill + a context
dict (assembled by the orchestrator) and returns a result dict + an audit trail.

Normalized message format (providers translate to their own API):
    {"role": "user", "content": str}
    {"role": "assistant", "content": str|None, "tool_calls": [ToolCall]}
    {"role": "tool", "tool_call_id": str, "name": str, "content": str}
ToolCall = {"id": str, "name": str, "arguments": dict}
Provider.complete(system, messages, tools, model, temperature, force_text) -> Turn
Turn = {"text": str|None, "tool_calls": list[ToolCall]}
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from jsonschema import Draft202012Validator

from app.agent._skill import Skill
from app.tools import PAUSE_TOOL, openai_schemas, run_tool
from app.utils.jsonx import extract_json


class Provider(Protocol):
    def complete(self, *, system: str, messages: list[dict], tools: list[dict] | None,
                 model: str | None = None, temperature: float = 0.1,
                 force_text: bool = False) -> dict: ...


@dataclass
class AgentResult:
    skill: str
    result: dict | None          # the validated output slice (None if it never produced valid output)
    finished: bool               # produced schema-valid output within max_steps
    steps_used: int
    audit: list[dict] = field(default_factory=list)
    # multi-turn: set when the agent paused on request_user_input
    paused: bool = False
    question: dict | None = None        # {question, options}
    messages: list[dict] = field(default_factory=list)   # conversation, for persist/resume
    pending_call_id: str | None = None  # the request_user_input call awaiting an answer


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate(data: Any, schema: dict) -> list[str]:
    """Return a list of human-readable validation errors (empty = valid)."""
    validator = Draft202012Validator(schema)
    return [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
            for e in validator.iter_errors(data)]


def _build_system(skill: Skill) -> str:
    schema = json.dumps(skill.output_schema)
    tool_note = (
        "You have tools available — call them as needed to do your job.\n"
        if skill.allowed_tools else
        "You have no tools; work only from the context provided.\n"
    )
    return (
        f"{skill.persona}\n\n"
        f"{tool_note}"
        "When you have finished, reply with ONLY a single JSON object that conforms "
        f"exactly to this JSON Schema (no prose, no markdown fences):\n{schema}"
    )


def _build_context(skill: Skill, context: dict) -> str:
    return (
        "Here is the current case context (slices written by earlier agents):\n"
        f"{json.dumps(context, default=str, indent=2)}\n\n"
        f"Your task: produce the `{skill.name}` result as specified."
    )


def run_skill(skill: Skill, context: dict, provider: Provider, *,
              temperature: float = 0.1,
              resume_messages: list[dict] | None = None) -> AgentResult:
    system = _build_system(skill)
    tools_spec = openai_schemas(skill.allowed_tools) if skill.allowed_tools else None
    # resume: continue the prior conversation (the user's answer is already appended);
    # fresh: start from the case context.
    messages: list[dict] = (resume_messages
                            if resume_messages is not None
                            else [{"role": "user", "content": _build_context(skill, context)}])
    audit: list[dict] = []
    data: dict | None = None

    for step in range(skill.max_steps):
        last = step == skill.max_steps - 1
        turn = provider.complete(
            system=system, messages=messages, tools=None if last else tools_spec,
            model=skill.model, temperature=temperature, force_text=last,
        )
        tool_calls = turn.get("tool_calls") or []

        if tool_calls and not last:
            messages.append({"role": "assistant", "content": turn.get("text"),
                             "tool_calls": tool_calls})
            # pause gate: if the agent asks the customer, stop and hand back control
            pause = next((c for c in tool_calls if c["name"] == PAUSE_TOOL), None)
            for call in tool_calls:
                if call is pause:
                    continue                         # answered later, on resume
                result = _run_one_tool(skill.name, call, audit)
                messages.append({"role": "tool", "tool_call_id": call["id"],
                                 "name": call["name"],
                                 "content": json.dumps(result, default=str)})
            if pause is not None:
                return AgentResult(skill.name, None, False, step + 1, audit,
                                   paused=True, question=pause.get("arguments") or {},
                                   messages=messages, pending_call_id=pause["id"])
            continue

        # no tool calls -> treat the text as the final result JSON
        data = None
        try:
            data = json.loads(extract_json(turn.get("text") or ""))
        except json.JSONDecodeError as e:
            errors = [f"reply was not valid JSON: {e}"]
        else:
            errors = _validate(data, skill.output_schema)

        if not errors:
            return AgentResult(skill.name, data, True, step + 1, audit)

        # invalid -> feed the errors back and let the model retry
        messages.append({"role": "assistant", "content": turn.get("text")})
        messages.append({"role": "user",
                         "content": "Your reply did not match the required schema:\n- "
                                    + "\n- ".join(errors)
                                    + "\nReply again with ONLY the corrected JSON object."})

    # exhausted max_steps without valid output (data holds the last invalid attempt, if any)
    return AgentResult(skill.name, data, False, skill.max_steps, audit)


def _run_one_tool(skill_name: str, call: dict, audit: list[dict]) -> dict:
    """Execute a tool call; record it; return errors AS results (never raise)."""
    name, args = call["name"], call.get("arguments") or {}
    try:
        result = run_tool(name, **args)
    except Exception as e:                       # noqa: BLE001 — errors feed back to the model
        result = {"error": f"{type(e).__name__}: {e}"}
    audit.append({"step": skill_name, "tool": name, "args": args,
                  "result": result, "at": _now()})
    return result
