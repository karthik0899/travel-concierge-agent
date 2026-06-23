"""Skill descriptor + loader.

A skill package is a folder with:
    SKILL.md     frontmatter (name, description, allowed_tools, max_steps, model) + persona body
    schema.json  JSON Schema of the agent's output slice
    __init__.py  exposes SKILL = load_skill(<this dir>)

The engine runs ANY skill through one general loop; a skill is pure data
(persona + allowed_tools + output_schema + caps). allowed_tools is the scoping.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from app.utils.constants import DEFAULT_MAX_STEPS


@dataclass
class Skill:
    name: str
    description: str
    persona: str
    allowed_tools: list[str] = field(default_factory=list)
    output_schema: dict = field(default_factory=dict)
    max_steps: int = DEFAULT_MAX_STEPS
    model: str | None = None


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split a `--- yaml --- body` markdown file into (frontmatter, body)."""
    if not text.startswith("---"):
        return {}, text
    _, fm, body = text.split("---", 2)
    return yaml.safe_load(fm) or {}, body.strip()


def load_skill(skill_dir: Path) -> Skill:
    fm, body = _parse_frontmatter((skill_dir / "SKILL.md").read_text())
    schema = json.loads((skill_dir / "schema.json").read_text())
    return Skill(
        name=fm["name"],
        description=fm.get("description", ""),
        persona=body,
        allowed_tools=fm.get("allowed_tools", []),
        output_schema=schema,
        max_steps=fm.get("max_steps", DEFAULT_MAX_STEPS),
        model=fm.get("model"),
    )


def load_all() -> dict[str, Skill]:
    """Discover every skill folder under app/agent/ (by name)."""
    base = Path(__file__).parent
    skills: dict[str, Skill] = {}
    for d in sorted(base.iterdir()):
        if d.is_dir() and (d / "SKILL.md").exists():
            s = load_skill(d)
            skills[s.name] = s
    return skills
