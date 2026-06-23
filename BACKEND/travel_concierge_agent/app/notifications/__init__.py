"""SMS notifications via Twilio — best-effort, never breaks the pipeline.

The orchestrator calls notify(case, event) on case transitions (opened, rebooked,
hotel, claim, closed, failed). If Twilio isn't configured the message is logged
instead of sent, so the app runs without creds.

Env (.env):
    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER
    NOTIFY_OVERRIDE_PHONE   # optional: route ALL messages here (demo / Twilio trial)
"""

from __future__ import annotations

import os

from app.db import connection as db

_service: "_Twilio | None" = None
_init = False


class _Twilio:
    def __init__(self):
        self.sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.token = os.getenv("TWILIO_AUTH_TOKEN")
        self.from_number = os.getenv("TWILIO_PHONE_NUMBER")
        self.client = None
        self.configured = bool(self.sid and self.token and self.from_number)
        if self.configured:
            try:
                from twilio.rest import Client          # lazy: app runs without twilio installed
                self.client = Client(self.sid, self.token)
            except Exception:                            # noqa: BLE001
                self.configured = False

    def send(self, to: str, body: str) -> str | None:
        if not (self.configured and self.client):
            return None
        return self.client.messages.create(body=body, from_=self.from_number, to=to).sid


def _svc() -> _Twilio:
    global _service, _init
    if not _init:
        _service, _init = _Twilio(), True
    return _service


def _phone_for(case) -> str | None:
    override = os.getenv("NOTIFY_OVERRIDE_PHONE")
    if override:
        return override
    ref = (case.identity.booking_ref if (case.identity and case.identity.verified)
           else case.report.booking_ref)
    row = db.query_one(
        "SELECT c.phone FROM bookings b JOIN customers c ON c.customer_id = b.customer_id "
        "WHERE b.booking_ref = %s",
        (ref,),
    )
    return row["phone"] if row else None


def _message(case, event: str) -> str | None:
    ref, cid = case.report.booking_ref, (case.case_id or "")[:8]
    if event == "opened":
        return f"Travel Concierge: We've received your report for booking {ref}. Case {cid} is open — we're on it."
    if event == "rebooked" and case.rebooking and case.rebooking.selected:
        s = case.rebooking.selected
        return (f"Travel Concierge: You're rebooked on {s.flight_no} "
                f"({s.origin}->{s.destination}), departs {s.departure}. (Case {cid})")
    if event == "hotel" and case.accommodation and case.accommodation.selected:
        a = case.accommodation
        return (f"Travel Concierge: Overnight hotel booked — {a.selected.name}. "
                f"Confirmation {a.confirmation}. (Case {cid})")
    if event == "claim" and case.claim and case.claim.claim_submitted:
        amt = case.compensation.amount if case.compensation else None
        amt_s = f"{amt.amount:.0f} {amt.currency}" if amt else "your entitlement"
        return (f"Travel Concierge: Compensation claim filed for {amt_s}. "
                f"Ref {case.claim.claim_ref}. (Case {cid})")
    if event == "closed":
        return f"Travel Concierge: Your case {cid} (booking {ref}) is resolved. Check your email for details."
    if event == "failed":
        return f"Travel Concierge: We couldn't verify booking {ref}. Please contact support. (Case {cid})"
    return None


def notify(case, event: str) -> None:
    """Best-effort SMS for a case event. Never raises."""
    try:
        body = _message(case, event)
        if not body:
            return
        to = _phone_for(case)
        if not to:
            return
        svc = _svc()
        if svc.configured:
            sid = svc.send(to, body)
            print(f"[SMS sent {sid}] -> {to}: {body}")
        else:
            print(f"[SMS skipped — Twilio not configured] -> {to}: {body}")
    except Exception as e:                               # noqa: BLE001 — notifications never break the pipeline
        print(f"[SMS error] {e}")
