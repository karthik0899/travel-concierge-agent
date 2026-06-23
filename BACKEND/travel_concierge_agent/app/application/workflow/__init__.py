"""The workflow definition — the fixed pipeline and its branch conditions.

The order is deterministic (identity -> ... -> summary). Whether a step RUNS is a
structured-signal decision, evaluated over the CaseFile written so far — not LLM
routing. This is the "fixed pipeline, structured-signal branching" design.

Each Step pairs a skill name with a predicate `should_run(case) -> bool`.
The orchestrator merges each skill's slice into the case before the next predicate
is evaluated, so later predicates see earlier results.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.domain.case_file import CaseFile


def _verified(c: CaseFile) -> bool:
    return c.identity is not None and c.identity.verified


def _needs_rebooking(c: CaseFile) -> bool:
    return _verified(c) and c.assessment is not None and c.assessment.needs_rebooking


def _needs_accommodation(c: CaseFile) -> bool:
    if not _verified(c):
        return False
    by_assessment = c.assessment is not None and c.assessment.needs_accommodation
    by_rebooking = c.rebooking is not None and c.rebooking.overnight_required
    return bool(by_assessment or by_rebooking)


def _has_assessment(c: CaseFile) -> bool:
    return _verified(c) and c.assessment is not None


def _claim_due(c: CaseFile) -> bool:
    return (
        c.compensation is not None
        and c.compensation.eligible
        and c.compensation.amount is not None
        and c.compensation.amount.amount > 0
    )


@dataclass(frozen=True)
class Step:
    skill: str
    should_run: Callable[[CaseFile], bool]


# The pipeline. Order is fixed; predicates gate execution.
STEPS: list[Step] = [
    Step("identity",      lambda c: True),
    Step("disruption",    _verified),            # needs a verified booking
    Step("rebooking",     _needs_rebooking),     # cancellation / missed connection / denied boarding
    Step("accommodation", _needs_accommodation), # overnight required
    Step("compensation",  _has_assessment),      # always assess (may be ineligible)
    Step("claim",         _claim_due),           # only if eligible & amount > 0
    Step("summary",       lambda c: True),       # always compile a recap
]
