"""FastAPI app for the Travel Concierge Agent frontend.

Job pattern (the pipeline takes a while with a live LLM):
    POST /cases    -> kicks off the run in the background, returns {case_id} immediately
    GET  /cases/{id} -> poll; status + current_step advance as the pipeline persists each step

Reference endpoints feed the UI (booking picker, demo prompts, history, providers).
Endpoints are sync (def) so the Claude provider's asyncio.run stays off the loop;
the heavy pipeline runs via BackgroundTasks in the threadpool.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.application.intake import parse_report
from app.application.orchestrator import Orchestrator
from app.db import connection as db
from app.llm import get_provider, provider_name
from app.tools import run_tool

_orchestrator: Orchestrator | None = None

# demo prompts for the UI (the PNR is embedded in the message text)
DEMO_MESSAGES = [
    "My flight 6E2341 on booking PNR001 from Delhi to Mumbai tonight was cancelled.",
    "Flight 6E5577 (PNR002) DEL-GOI was cancelled due to bad weather.",
    "On booking PNR003 my DEL-BOM flight was delayed and I missed my BOM-COK connection.",
    "I was denied boarding on 6E709 from Bangalore (PNR004), the flight was overbooked.",
    "My baggage didn't arrive on flight UK945 to Chennai, booking PNR005.",
    "Flight 6E812 DEL-HYD on PNR006 is delayed by 4 hours.",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _orchestrator
    _orchestrator = Orchestrator()
    yield
    db.close_pool()


app = FastAPI(title="Travel Concierge Agent", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # dev: allow any frontend origin
    allow_methods=["*"],
    allow_headers=["*"],
)


class ReportIn(BaseModel):
    message: str
    provider: str | None = None   # 'cortex' | 'claude' (defaults to LLM_PROVIDER)


class ReplyIn(BaseModel):
    message: str                  # the customer's answer to a pending question


# ----------------------------------------------------------------------------
# Meta / reference
# ----------------------------------------------------------------------------
@app.get("/health")
def health() -> dict:
    return {"status": "ok", "default_provider": provider_name()}


@app.get("/providers")
def providers() -> dict:
    return {"default": provider_name(), "available": ["cortex", "claude"]}


@app.get("/demos")
def demos() -> dict:
    return {"messages": DEMO_MESSAGES}


@app.get("/bookings")
def list_bookings() -> dict:
    rows = db.query(
        """
        SELECT b.booking_ref, c.name, b.status, b.fare_class,
               (SELECT string_agg(f.origin || '-' || f.destination, ', ' ORDER BY s.segment_order)
                FROM booking_segments s JOIN flights f ON f.flight_id = s.flight_id
                WHERE s.booking_ref = b.booking_ref) AS route
        FROM bookings b JOIN customers c ON c.customer_id = b.customer_id
        ORDER BY b.booking_ref
        """
    )
    return {"bookings": rows}


@app.get("/bookings/{booking_ref}")
def get_booking(booking_ref: str) -> dict:
    result = run_tool("verify_booking", booking_ref=booking_ref)
    if not result.get("verified"):
        raise HTTPException(status_code=404, detail=result.get("reason", "Not found"))
    return result


# ----------------------------------------------------------------------------
# World data (read-only) — customers, flights, hotels, airports, rules, claims
# ----------------------------------------------------------------------------
@app.get("/customers")
def list_customers() -> dict:
    rows = db.query(
        "SELECT customer_id, name, email, phone, loyalty_tier, created_at "
        "FROM customers ORDER BY name"
    )
    return {"customers": rows}


@app.get("/customers/{customer_id}")
def get_customer(customer_id: str) -> dict:
    cust = db.query_one(
        "SELECT customer_id, name, email, phone, loyalty_tier, created_at "
        "FROM customers WHERE customer_id = %s",
        (customer_id,),
    )
    if cust is None:
        raise HTTPException(status_code=404, detail=f"No customer {customer_id}")
    cust["bookings"] = db.query(
        "SELECT booking_ref, fare_class, status, total_price, currency "
        "FROM bookings WHERE customer_id = %s ORDER BY booked_at DESC",
        (customer_id,),
    )
    return cust


@app.get("/flights")
def list_flights(origin: str | None = None, destination: str | None = None,
                 status: str | None = None, bookable: bool = False,
                 limit: int = 100) -> dict:
    conds, params = [], []
    if origin:
        conds.append("f.origin = %s"); params.append(origin)
    if destination:
        conds.append("f.destination = %s"); params.append(destination)
    if status:
        conds.append("f.status = %s"); params.append(status)
    if bookable:
        conds.append("f.status <> 'cancelled' AND f.seats_available > 0")
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    params.append(limit)
    rows = db.query(
        f"""
        SELECT f.flight_no, a.name AS airline, f.origin, f.destination,
               f.sched_departure, f.sched_arrival, f.block_minutes, f.status,
               f.delay_minutes, f.cancel_cause, f.seats_available, f.base_price, f.currency
        FROM flights f JOIN airlines a ON a.code = f.airline_code
        {where}
        ORDER BY f.sched_departure
        LIMIT %s
        """,
        tuple(params),
    )
    return {"flights": rows}


@app.get("/flights/{flight_no}")
def get_flight(flight_no: str) -> dict:
    result = run_tool("get_flight_details", flight_no=flight_no)
    if not result.get("found"):
        raise HTTPException(status_code=404, detail=result.get("reason", "Not found"))
    return result


@app.get("/airports")
def list_airports() -> dict:
    return {"airports": db.query("SELECT iata_code, name, city, country FROM airports ORDER BY iata_code")}


@app.get("/hotels")
def list_hotels(near_airport: str | None = None) -> dict:
    if near_airport:
        rows = db.query(
            "SELECT hotel_id, name, city, near_airport, star_rating, price_per_night, "
            "currency, rooms_available FROM hotels WHERE near_airport = %s ORDER BY price_per_night",
            (near_airport,),
        )
    else:
        rows = db.query(
            "SELECT hotel_id, name, city, near_airport, star_rating, price_per_night, "
            "currency, rooms_available FROM hotels ORDER BY near_airport, price_per_night"
        )
    return {"hotels": rows}


@app.get("/rules")
def list_rules() -> dict:
    """The Indian aviation rules the agent applies (for display / transparency)."""
    return {
        "compensation": db.query(
            "SELECT event_type, block_min_minutes, block_max_minutes, alt_min_hours, "
            "alt_max_hours, fare_multiplier, cap_amount, currency, car_ref, notes "
            "FROM dgca_compensation_rules ORDER BY event_type, block_min_minutes NULLS FIRST, alt_min_hours NULLS FIRST"
        ),
        "baggage": db.query(
            "SELECT jurisdiction, event_type, per_kg_amount, cap_amount, currency, "
            "claim_deadline_days, legal_ref, notes FROM baggage_liability_rules "
            "ORDER BY jurisdiction, event_type"
        ),
        "care": db.query(
            "SELECT care_type, min_delay_hours, overnight, car_ref, notes "
            "FROM dgca_care_rules ORDER BY care_type"
        ),
    }


@app.get("/claims")
def list_claims(limit: int = 50) -> dict:
    rows = db.query(
        "SELECT claim_ref, booking_ref, event_type, amount, currency, status, submitted_at "
        "FROM claims ORDER BY submitted_at DESC LIMIT %s",
        (limit,),
    )
    return {"claims": rows}


# ----------------------------------------------------------------------------
# Cases
# ----------------------------------------------------------------------------
@app.post("/cases", status_code=202)
def create_case(report_in: ReportIn, background_tasks: BackgroundTasks) -> dict:
    provider = get_provider(report_in.provider)
    report = parse_report(report_in.message, provider)        # intake (fast)
    case = _orchestrator.begin(report, provider)              # persist, get id
    background_tasks.add_task(_orchestrator.execute, case, provider)  # run pipeline async
    return {
        "case_id": case.case_id,
        "status": case.status.value,
        "booking_ref": report.booking_ref,
        "disruption_type": report.disruption_type.value,
    }


@app.post("/cases/{case_id}/messages", status_code=202)
def reply_to_case(case_id: str, reply: ReplyIn, background_tasks: BackgroundTasks) -> dict:
    """Answer a pending question on a paused case; resumes the pipeline in the background."""
    row = db.query_one("SELECT status FROM case_files WHERE case_id = %s", (case_id,))
    if row is None:
        raise HTTPException(status_code=404, detail=f"No case {case_id}")
    if row["status"] != "awaiting_input":
        raise HTTPException(status_code=409, detail=f"Case is not awaiting input (status={row['status']})")
    background_tasks.add_task(_orchestrator.resume, case_id, reply.message)
    return {"case_id": case_id, "status": "open"}


@app.get("/cases")
def list_cases(limit: int = 50) -> dict:
    rows = db.query(
        """
        SELECT case_id, booking_ref, status, current_step, provider, pending,
               report->>'disruption_type' AS disruption_type,
               report->>'raw_text' AS message,
               created_at, updated_at
        FROM case_files
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (limit,),
    )
    return {"cases": rows}


@app.get("/cases/{case_id}")
def get_case(case_id: str) -> dict:
    row = db.query_one(
        "SELECT case_id, booking_ref, status, current_step, provider, "
        "report, slices, audit_log, pending, created_at, updated_at "
        "FROM case_files WHERE case_id = %s",
        (case_id,),
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"No case {case_id}")
    return row
