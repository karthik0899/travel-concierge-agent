"""CaseFile — the shared case file for one disruption journey.

Opened on report, passed through each agent (each writes its own slice), closed
as the audit-ready record. The orchestrator owns it; agents write only their slice.
Persisted as JSONB in db.case_files.

Slices mirror the 7 agents: identity, disruption(assessment), rebooking,
accommodation, compensation, claim, summary.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .enums import CancelCause, CaseStatus, CompEvent, DisruptionType, LoyaltyTier


# --- shared value objects -----------------------------------------------------
class Money(BaseModel):
    amount: float
    currency: str = "INR"


class FlightOption(BaseModel):
    flight_no: str
    origin: str
    destination: str
    departure: datetime
    arrival: datetime
    seats_available: int
    price: Money


class HotelOption(BaseModel):
    hotel_id: str
    name: str
    near_airport: str
    star_rating: int
    price_per_night: Money


class ActionRecord(BaseModel):
    step: str                       # which agent
    tool: str
    args: dict
    result: dict | str              # errors are recorded as results, not raised
    at: datetime


# --- slice 0: the input -------------------------------------------------------
class DisruptionReport(BaseModel):
    raw_text: str
    booking_ref: str
    disruption_type: DisruptionType
    reported_at: datetime


# --- slice 1: Identity --------------------------------------------------------
class IdentityResult(BaseModel):
    verified: bool                  # BRANCH: false -> failure path
    customer_id: Optional[str] = None
    name: Optional[str] = None
    loyalty_tier: Optional[LoyaltyTier] = None
    booking_ref: Optional[str] = None
    itinerary: list[dict] = Field(default_factory=list)   # legs (flight_no/origin/dest/...) for downstream agents
    reason: Optional[str] = None


# --- slice 2: Disruption Assessment (the hinge) -------------------------------
class AssessmentResult(BaseModel):
    confirmed_type: DisruptionType
    severity: str                   # minor | major | severe
    affected_flights: list[str] = Field(default_factory=list)
    cause: Optional[CancelCause] = None      # THE HINGE -> compensation
    needs_rebooking: bool                     # BRANCH
    needs_accommodation: bool                 # BRANCH
    details: str


# --- slice 3: Rebooking -------------------------------------------------------
class RebookingResult(BaseModel):
    options_considered: list[FlightOption] = Field(default_factory=list)
    selected: Optional[FlightOption] = None
    booked: bool = False                       # approval gate
    new_segment_id: Optional[str] = None
    overnight_required: bool = False
    reason: Optional[str] = None


# --- slice 4: Accommodation ---------------------------------------------------
class AccommodationResult(BaseModel):
    options_considered: list[HotelOption] = Field(default_factory=list)
    selected: Optional[HotelOption] = None
    booked: bool = False
    confirmation: Optional[str] = None
    reason: Optional[str] = None


# --- slice 5: Compensation (assess only — claim is separate) ------------------
class CompensationResult(BaseModel):
    event_type: Optional[CompEvent] = None
    eligible: bool = False                      # derived from cause + rule lookup
    rule_ref: Optional[str] = None             # legal citation (human-readable)
    rule_id: Optional[str] = None              # DGCA rule id (flight events) -> Claim Agent
    baggage_rule_id: Optional[str] = None      # baggage liability rule id -> Claim Agent
    bag_tag: Optional[str] = None              # for baggage claims
    amount: Optional[Money] = None
    reason: str = ""


# --- slice 6: Claim (submits the assessed compensation) -----------------------
class ClaimResult(BaseModel):
    claim_submitted: bool = False              # approval gate
    claim_ref: Optional[str] = None
    status: Optional[str] = None
    reason: Optional[str] = None


# --- slice 7: Summary (read-only over the rest) -------------------------------
class SummaryResult(BaseModel):
    narrative: str
    actions_taken: list[str] = Field(default_factory=list)
    confirmations: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


# --- the case file ------------------------------------------------------------
class CaseFile(BaseModel):
    case_id: Optional[str] = None
    status: CaseStatus = CaseStatus.open
    current_step: Optional[str] = None
    report: DisruptionReport
    identity: Optional[IdentityResult] = None
    assessment: Optional[AssessmentResult] = None
    rebooking: Optional[RebookingResult] = None
    accommodation: Optional[AccommodationResult] = None
    compensation: Optional[CompensationResult] = None
    claim: Optional[ClaimResult] = None
    summary: Optional[SummaryResult] = None
    pending: Optional[dict] = None       # transient: the approval question when awaiting_input
    audit_log: list[ActionRecord] = Field(default_factory=list)
