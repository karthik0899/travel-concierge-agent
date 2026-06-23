#!/usr/bin/env python3
"""Command-line driver for the Travel Concierge Agent.

Runs the recovery pipeline for one disruption described in plain language. The
booking reference and disruption type are extracted from the message by intake.
Requires DATABASE_URL (and provider keys for live runs) — see .env.example.

Examples:
    python cli.py "My flight 6E2341 on PNR001 from Delhi to Mumbai was cancelled tonight"
    python cli.py "Baggage lost on UK945, booking PNR005" --provider claude
    python cli.py --demo                # run all six seeded demo scenarios
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.application.intake import parse_report
from app.application.orchestrator import Orchestrator
from app.db import connection as db
from app.domain.case_file import CaseFile
from app.llm import get_provider

# The six seeded demo scenarios as free-text messages (the PNR is in the text).
DEMOS = [
    "My flight 6E2341 on booking PNR001 from Delhi to Mumbai tonight was cancelled.",
    "Flight 6E5577 (PNR002) DEL-GOI was cancelled due to bad weather.",
    "On booking PNR003 my DEL-BOM flight was delayed and I missed my BOM-COK connection.",
    "I was denied boarding on 6E709 from Bangalore (PNR004), the flight was overbooked.",
    "My baggage didn't arrive on flight UK945 to Chennai, booking PNR005.",
    "Flight 6E812 DEL-HYD on PNR006 is delayed by 4 hours.",
]

C = {"h": "\033[1m", "g": "\033[32m", "y": "\033[33m", "d": "\033[2m", "x": "\033[0m"}


def _line(s=""):
    print(s)


def render(case: CaseFile) -> None:
    _line(f"\n{C['h']}{'='*70}{C['x']}")
    _line(f"{C['h']}Case {case.case_id}  [{case.status.value.upper()}]  "
          f"booking {case.report.booking_ref}{C['x']}")
    _line(f"{C['d']}\"{case.report.raw_text}\"{C['x']}")
    _line(f"{C['h']}{'='*70}{C['x']}")

    if case.identity:
        ok = case.identity.verified
        mark = f"{C['g']}verified{C['x']}" if ok else f"{C['y']}NOT verified{C['x']}"
        who = case.identity.name or "?"
        tier = case.identity.loyalty_tier.value if case.identity.loyalty_tier else "n/a"
        _line(f"Identity     : {mark} — {who} ({tier})")
        if not ok:
            _line(f"               reason: {case.identity.reason}")
    if case.assessment:
        a = case.assessment
        _line(f"Assessment   : {a.confirmed_type.value} / {a.severity}"
              f" — cause={a.cause.value if a.cause else 'n/a'}")
    if case.rebooking:
        r = case.rebooking
        if r.booked and r.selected:
            _line(f"Rebooking    : {C['g']}booked{C['x']} {r.selected.flight_no} "
                  f"dep {r.selected.departure}")
        else:
            _line(f"Rebooking    : {C['y']}not booked{C['x']} — {r.reason}")
    if case.accommodation:
        ac = case.accommodation
        if ac.booked and ac.selected:
            _line(f"Hotel        : {C['g']}booked{C['x']} {ac.selected.name} ({ac.confirmation})")
        else:
            _line(f"Hotel        : {ac.reason or 'not booked'}")
    if case.compensation:
        cp = case.compensation
        if cp.eligible and cp.amount:
            _line(f"Compensation : {C['g']}{cp.amount.amount:.0f} {cp.amount.currency}{C['x']} "
                  f"({cp.rule_ref})")
        else:
            _line(f"Compensation : {C['y']}none{C['x']} — {cp.reason}")
    if case.claim and case.claim.claim_submitted:
        _line(f"Claim        : {C['g']}filed{C['x']} {case.claim.claim_ref} ({case.claim.status})")

    if case.summary:
        _line(f"\n{C['h']}Summary{C['x']}")
        _line(f"  {case.summary.narrative}")
        for a in case.summary.actions_taken:
            _line(f"   • {a}")
        if case.summary.confirmations:
            _line(f"  {C['d']}refs: {', '.join(case.summary.confirmations)}{C['x']}")
        for n in case.summary.next_steps:
            _line(f"   → {n}")
    _line(f"{C['d']}({len(case.audit_log)} tool calls recorded in audit log){C['x']}")


def run_one(orch, provider, message, auto_yes=False) -> None:
    report = parse_report(message, provider)      # intake extracts booking_ref + type
    print(f"{C['d']}intake: {report.booking_ref} / {report.disruption_type.value}{C['x']}")
    case = orch.run(report, provider)
    # multi-turn: answer approval gates until the case reaches a terminal state
    while case.status.value == "awaiting_input":
        q = case.pending or {}
        print(f"\n{C['y']}❓ {q.get('question', 'Please confirm.')}{C['x']}")
        if q.get("options"):
            print(f"{C['d']}   options: {', '.join(q['options'])}{C['x']}")
        if auto_yes:
            reply = "Yes, please go ahead with your recommendation."
            print(f"{C['d']}   (auto) > {reply}{C['x']}")
        else:
            reply = input("   your reply > ").strip() or "yes"
        case = orch.resume(case.case_id, reply)
    render(case)


def main() -> None:
    p = argparse.ArgumentParser(description="Travel Concierge Agent CLI")
    p.add_argument("message", nargs="?", default="",
                   help='what the customer said, e.g. "My flight 6E2341 on PNR001 was cancelled"')
    p.add_argument("--provider", choices=["cortex", "claude"], help="override LLM_PROVIDER")
    p.add_argument("--demo", action="store_true", help="run all six seeded demo scenarios")
    p.add_argument("--yes", action="store_true", help="auto-approve all confirmation prompts")
    args = p.parse_args()

    provider = get_provider(args.provider)
    orch = Orchestrator()
    print(f"{C['d']}provider: {provider.name}{C['x']}")

    try:
        if args.demo:
            for message in DEMOS:
                run_one(orch, provider, message, auto_yes=True)
        elif args.message:
            run_one(orch, provider, args.message, auto_yes=args.yes)
        else:
            p.error('provide a message, e.g. "My flight 6E2341 on PNR001 was cancelled", or use --demo')
    finally:
        db.close_pool()


if __name__ == "__main__":
    main()
