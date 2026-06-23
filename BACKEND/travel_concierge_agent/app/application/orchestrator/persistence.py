"""Persist the CaseFile to db.case_files (JSONB slices + audit + status).

The orchestrator owns the case; this module is the only place it touches the
case_files table. Slices are stored keyed by their attribute name (identity,
assessment, rebooking, accommodation, compensation, claim, summary).
"""

from __future__ import annotations

import json

from app.db import connection as db
from app.domain.case_file import (
    AccommodationResult, ActionRecord, AssessmentResult, CaseFile, CaseStatus,
    ClaimResult, CompensationResult, DisruptionReport, IdentityResult,
    RebookingResult, SummaryResult,
)

# slice attribute name -> model (the JSONB keys under `slices`)
_SLICE_MODELS = {
    "identity": IdentityResult, "assessment": AssessmentResult,
    "rebooking": RebookingResult, "accommodation": AccommodationResult,
    "compensation": CompensationResult, "claim": ClaimResult, "summary": SummaryResult,
}
_SLICE_ATTRS = list(_SLICE_MODELS)


def _verified_ref(case: CaseFile) -> str | None:
    """The booking_ref FK is set only once Identity verifies it exists (else NULL).

    The customer's *reported* ref always lives in report JSONB; this column links
    to the bookings table only for verified cases, so failed verifications still
    persist a case row.
    """
    if case.identity is not None and case.identity.verified:
        return case.identity.booking_ref
    return None


def _slices_json(case: CaseFile) -> str:
    out = {}
    for attr in _SLICE_ATTRS:
        val = getattr(case, attr)
        if val is not None:
            out[attr] = val.model_dump(mode="json")
    return json.dumps(out)


def _audit_json(case: CaseFile) -> str:
    return json.dumps([a.model_dump(mode="json") for a in case.audit_log])


def create_case(case: CaseFile, provider: str) -> str:
    row = db.execute(
        """
        INSERT INTO case_files (booking_ref, status, current_step, report, slices, audit_log, provider)
        VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s)
        RETURNING case_id
        """,
        (_verified_ref(case), case.status.value, case.current_step,
         json.dumps(case.report.model_dump(mode="json")),
         _slices_json(case), _audit_json(case), provider),
    )
    case_id = str(row[0]["case_id"])
    case.case_id = case_id
    return case_id


def save_case(case: CaseFile) -> None:
    db.execute(
        """
        UPDATE case_files
        SET booking_ref = %s, status = %s, current_step = %s, slices = %s::jsonb,
            audit_log = %s::jsonb, updated_at = now()
        WHERE case_id = %s
        """,
        (_verified_ref(case), case.status.value, case.current_step,
         _slices_json(case), _audit_json(case), case.case_id),
    )


def save_runstate(case_id: str, *, step_index: int, messages: list[dict],
                  pending_call_id: str, question: dict) -> None:
    """Persist the paused engine state + the question shown to the customer."""
    db.execute(
        "UPDATE case_files SET pending = %s::jsonb, runstate = %s::jsonb, updated_at = now() "
        "WHERE case_id = %s",
        (json.dumps(question),
         json.dumps({"step_index": step_index, "pending_call_id": pending_call_id,
                     "messages": messages}),
         case_id),
    )


def clear_runstate(case_id: str) -> None:
    db.execute("UPDATE case_files SET pending = NULL, runstate = NULL, updated_at = now() "
               "WHERE case_id = %s", (case_id,))


def load_case(case_id: str) -> tuple[CaseFile, dict, str | None] | None:
    """Reconstruct a CaseFile + its runstate + provider name from the DB (for resume)."""
    row = db.query_one(
        "SELECT case_id, status, current_step, report, slices, audit_log, runstate, provider "
        "FROM case_files WHERE case_id = %s",
        (case_id,),
    )
    if row is None:
        return None
    case = CaseFile(report=DisruptionReport(**row["report"]))
    case.case_id = str(row["case_id"])
    case.status = CaseStatus(row["status"])
    case.current_step = row["current_step"]
    for attr, model in _SLICE_MODELS.items():
        if attr in (row["slices"] or {}):
            setattr(case, attr, model(**row["slices"][attr]))
    case.audit_log = [ActionRecord(**a) for a in (row["audit_log"] or [])]
    return case, (row["runstate"] or {}), row["provider"]
