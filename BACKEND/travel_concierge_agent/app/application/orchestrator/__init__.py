"""The orchestrator — runs the fixed pipeline over one CaseFile.

For each step whose predicate passes:
  1. assemble the skill's context from the case so far,
  2. run the skill through the engine (with the selected provider),
  3. merge the validated slice into the case + append the audit trail,
  4. persist the case.

Order is deterministic; branching is by structured signal (see workflow.STEPS).
Agents write only their own slice; the orchestrator owns the merge + persistence.
"""

from __future__ import annotations

from app.agent import load_all
from app.agent.runner import run_skill
from app.application.orchestrator.persistence import (
    clear_runstate, create_case, load_case, save_case, save_runstate,
)
from app.application.workflow import STEPS
from app.domain.case_file import (
    AccommodationResult, ActionRecord, AssessmentResult, CaseFile, CaseStatus,
    ClaimResult, CompensationResult, DisruptionReport, IdentityResult,
    RebookingResult, SummaryResult,
)
from app.llm import get_provider
from app.notifications import notify

# skill name -> (CaseFile attribute, slice model)
_SLICE = {
    "identity":      ("identity", IdentityResult),
    "disruption":    ("assessment", AssessmentResult),
    "rebooking":     ("rebooking", RebookingResult),
    "accommodation": ("accommodation", AccommodationResult),
    "compensation":  ("compensation", CompensationResult),
    "claim":         ("claim", ClaimResult),
    "summary":       ("summary", SummaryResult),
}


class Orchestrator:
    def __init__(self):
        self.skills = load_all()

    def begin(self, report: DisruptionReport, provider) -> CaseFile:
        """Create the persisted case (status=open) and return it immediately."""
        case = CaseFile(report=report)
        create_case(case, getattr(provider, "name", "unknown"))
        notify(case, "opened")
        return case

    def run(self, report: DisruptionReport, provider) -> CaseFile:
        """Synchronous: create + run the whole pipeline (may end paused)."""
        return self.execute(self.begin(report, provider), provider)

    def execute(self, case: CaseFile, provider, *, start_index: int = 0,
                resume_messages: list[dict] | None = None) -> CaseFile:
        for i in range(start_index, len(STEPS)):
            step = STEPS[i]
            if not step.should_run(case):
                continue
            case.current_step = step.skill
            context = case.model_dump(mode="json", exclude={"audit_log", "pending"}, exclude_none=True)
            # only the resumed step gets the prior conversation; later steps start fresh
            rmsgs = resume_messages if (i == start_index and resume_messages is not None) else None

            result = run_skill(self.skills[step.skill], context, provider, resume_messages=rmsgs)
            case.audit_log.extend(ActionRecord(**a) for a in result.audit)

            if result.paused:
                case.status = CaseStatus.awaiting_input
                case.pending = result.question
                save_case(case)
                save_runstate(case.case_id, step_index=i, messages=result.messages,
                              pending_call_id=result.pending_call_id, question=result.question)
                return case

            if result.finished and result.result is not None:
                attr, model = _SLICE[step.skill]
                setattr(case, attr, model(**result.result))
            save_case(case)
            _notify_step(case, step.skill)

        case.current_step = None
        case.pending = None
        case.status = _final_status(case)
        save_case(case)
        clear_runstate(case.case_id)
        notify(case, "failed" if case.status == CaseStatus.failed else "closed")
        return case

    def resume(self, case_id: str, user_reply: str) -> CaseFile:
        """Continue a paused case with the customer's answer."""
        loaded = load_case(case_id)
        if loaded is None:
            raise KeyError(f"No case {case_id}")
        case, runstate, provider_name = loaded
        if case.status != CaseStatus.awaiting_input or not runstate:
            raise ValueError(f"Case {case_id} is not awaiting input")

        provider = get_provider(provider_name)
        messages = runstate["messages"]
        # answer the pending request_user_input call with the customer's reply
        messages.append({"role": "tool", "tool_call_id": runstate["pending_call_id"],
                         "name": "request_user_input", "content": user_reply})
        case.status = CaseStatus.open
        return self.execute(case, provider, start_index=runstate["step_index"],
                            resume_messages=messages)


def _notify_step(case: CaseFile, skill: str) -> None:
    """SMS the customer when a step commits a real change."""
    if skill == "rebooking" and case.rebooking and case.rebooking.booked:
        notify(case, "rebooked")
    elif skill == "accommodation" and case.accommodation and case.accommodation.booked:
        notify(case, "hotel")
    elif skill == "claim" and case.claim and case.claim.claim_submitted:
        notify(case, "claim")


def _final_status(case: CaseFile) -> CaseStatus:
    if case.identity is None or not case.identity.verified:
        return CaseStatus.failed
    return CaseStatus.closed
