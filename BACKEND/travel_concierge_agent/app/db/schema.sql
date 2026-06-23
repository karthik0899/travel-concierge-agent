-- =============================================================================
-- Travel Concierge Agent — world schema (PostgreSQL 18)
-- =============================================================================
-- "The world": all bookings, flights, hotels, customers, DGCA compensation
-- rules, and transactional outputs (claims, hotel bookings). Tools read/write THIS.
--
-- The CaseFile (one disruption journey) is persisted separately as JSONB in
-- `case_files` — agents read/write the case; tools read/write the world.
--
-- Compensation law: India's DGCA, CAR Section 3, Series M, Part IV (refund &
-- compensation). NOTE: this is BLOCK-TIME based (flight duration), not distance
-- based like EC261. Compensation = min(cap, multiplier * (basic_fare + fuel_charge)),
-- gated by cause (extraordinary circumstances waive cash) and notice period.
--
-- Conventions:
--   * human-facing refs (booking_ref, flight_no, claim_ref) are TEXT — customers quote them
--   * internal surrogate keys are uuid (uuidv7 = time-ordered, good index locality)
--   * all timestamps are timestamptz (store UTC)
--   * money is numeric(10,2) + char(3) ISO-4217 currency (INR) — never float
--
-- Idempotent: safe to re-run for a fresh demo DB.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Clean slate (demo convenience — drop in reverse dependency order)
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS case_files               CASCADE;
DROP TABLE IF EXISTS claims                   CASCADE;
DROP TABLE IF EXISTS hotel_bookings           CASCADE;
DROP TABLE IF EXISTS baggage_liability_rules  CASCADE;
DROP TABLE IF EXISTS baggage                  CASCADE;
DROP TABLE IF EXISTS booking_segments         CASCADE;
DROP TABLE IF EXISTS bookings                 CASCADE;
DROP TABLE IF EXISTS flights                  CASCADE;
DROP TABLE IF EXISTS hotels                   CASCADE;
DROP TABLE IF EXISTS dgca_care_rules          CASCADE;
DROP TABLE IF EXISTS dgca_compensation_rules  CASCADE;
DROP TABLE IF EXISTS customers                CASCADE;
DROP TABLE IF EXISTS airlines                 CASCADE;
DROP TABLE IF EXISTS airports                 CASCADE;

DROP TYPE IF EXISTS loyalty_tier    CASCADE;
DROP TYPE IF EXISTS flight_status   CASCADE;
DROP TYPE IF EXISTS cancel_cause    CASCADE;
DROP TYPE IF EXISTS fare_class      CASCADE;
DROP TYPE IF EXISTS booking_status  CASCADE;
DROP TYPE IF EXISTS segment_status  CASCADE;
DROP TYPE IF EXISTS claim_status    CASCADE;
DROP TYPE IF EXISTS disruption_type CASCADE;
DROP TYPE IF EXISTS case_status     CASCADE;
DROP TYPE IF EXISTS comp_event      CASCADE;
DROP TYPE IF EXISTS care_type       CASCADE;
DROP TYPE IF EXISTS baggage_status  CASCADE;
DROP TYPE IF EXISTS jurisdiction    CASCADE;

-- =============================================================================
-- ENUM types — make the branching signals type-safe at the DB level
-- =============================================================================
CREATE TYPE loyalty_tier    AS ENUM ('none','silver','gold','platinum');
CREATE TYPE flight_status   AS ENUM ('scheduled','delayed','cancelled','departed','arrived');
CREATE TYPE cancel_cause    AS ENUM ('airline_fault','extraordinary_circumstance');
CREATE TYPE fare_class      AS ENUM ('economy','premium','business','first');
CREATE TYPE booking_status  AS ENUM ('active','disrupted','rebooked','cancelled');
CREATE TYPE segment_status  AS ENUM ('confirmed','disrupted','rebooked');
CREATE TYPE claim_status    AS ENUM ('submitted','approved','rejected');
CREATE TYPE disruption_type AS ENUM ('cancelled_flight','flight_delay','missed_connection','denied_boarding','lost_baggage','delayed_baggage','damaged_baggage');
CREATE TYPE case_status     AS ENUM ('open','awaiting_input','rebooked','compensated','closed','failed');
-- cash-compensable events: flight-disruption events (DGCA block-time/denied-boarding)
-- + baggage events (Carriage by Air Act / Montreal — weight/cap based)
CREATE TYPE comp_event      AS ENUM ('cancellation','denied_boarding','lost_baggage','delayed_baggage','damaged_baggage');
CREATE TYPE care_type       AS ENUM ('meals','hotel','refund','transfers');
CREATE TYPE baggage_status  AS ENUM ('checked','in_transit','delivered','delayed','lost','damaged');
CREATE TYPE jurisdiction    AS ENUM ('domestic','international');

-- =============================================================================
-- GROUP A — Reference data
-- =============================================================================

CREATE TABLE airports (
    iata_code   char(3)     PRIMARY KEY,           -- "DEL"
    name        text        NOT NULL,
    city        text        NOT NULL,
    country     text        NOT NULL DEFAULT 'India',
    lat         double precision,
    lon         double precision
);

CREATE TABLE airlines (
    code        text        PRIMARY KEY,           -- "6E"
    name        text        NOT NULL               -- "IndiGo"
);

-- =============================================================================
-- GROUP B — The customer's existing world (Identity / Assessment read these)
-- =============================================================================

CREATE TABLE customers (
    customer_id  uuid          PRIMARY KEY DEFAULT uuidv7(),
    name         text          NOT NULL,
    email        text          NOT NULL UNIQUE,
    phone        text,
    loyalty_tier loyalty_tier  NOT NULL DEFAULT 'none',
    created_at   timestamptz   NOT NULL DEFAULT now()
);

-- A flight is a scheduled service that exists independent of any booking.
-- It is BOTH the customer's original itinerary source AND the rebooking supply.
CREATE TABLE flights (
    flight_id       uuid          PRIMARY KEY DEFAULT uuidv7(),
    flight_no       text          NOT NULL,              -- "6E2341"
    airline_code    text          NOT NULL REFERENCES airlines(code),
    origin          char(3)       NOT NULL REFERENCES airports(iata_code),
    destination     char(3)       NOT NULL REFERENCES airports(iata_code),
    sched_departure timestamptz   NOT NULL,
    sched_arrival   timestamptz   NOT NULL,
    -- block time in minutes, derived (PG18 virtual generated column).
    -- This is the band key for DGCA cancellation compensation.
    block_minutes   integer       GENERATED ALWAYS AS
                        (CEIL(EXTRACT(EPOCH FROM (sched_arrival - sched_departure)) / 60.0)) VIRTUAL,
    status          flight_status NOT NULL DEFAULT 'scheduled',
    delay_minutes   integer       NOT NULL DEFAULT 0,
    delay_hours     double precision GENERATED ALWAYS AS (delay_minutes / 60.0) VIRTUAL,
    cancel_cause    cancel_cause,                        -- NULL unless cancelled — THE HINGE
    cancelled_at    timestamptz,                         -- when cancellation was announced (notice period)
    aircraft        text,
    seats_available integer       NOT NULL DEFAULT 0,
    base_price      numeric(10,2) NOT NULL,              -- headline price for rebooking comparison
    currency        char(3)       NOT NULL DEFAULT 'INR',

    -- a cancelled flight must have a cause AND an announcement time; else neither
    CONSTRAINT cancel_fields_iff_cancelled
        CHECK ((status = 'cancelled') = (cancel_cause IS NOT NULL)
           AND (status = 'cancelled') = (cancelled_at IS NOT NULL)),
    CONSTRAINT seats_non_negative      CHECK (seats_available >= 0),
    CONSTRAINT delay_non_negative      CHECK (delay_minutes >= 0),
    CONSTRAINT origin_dest_differ      CHECK (origin <> destination),
    CONSTRAINT arrival_after_departure CHECK (sched_arrival > sched_departure)
);

-- the customer's trip / PNR. Fare is decomposed because DGCA compensation is
-- "min(cap, multiplier * (basic_fare + fuel_charge))" — we need the components.
CREATE TABLE bookings (
    booking_ref  text           PRIMARY KEY,            -- "ABC123" (customer-quoted)
    customer_id  uuid           NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    fare_class   fare_class     NOT NULL DEFAULT 'economy',
    basic_fare   numeric(10,2)  NOT NULL,               -- one-way basic fare component
    fuel_charge  numeric(10,2)  NOT NULL DEFAULT 0,     -- airline fuel charge component
    taxes_fees   numeric(10,2)  NOT NULL DEFAULT 0,
    total_price  numeric(10,2)  GENERATED ALWAYS AS (basic_fare + fuel_charge + taxes_fees) STORED,
    currency     char(3)        NOT NULL DEFAULT 'INR',
    status       booking_status NOT NULL DEFAULT 'active',
    booked_at    timestamptz    NOT NULL DEFAULT now(),

    CONSTRAINT fare_components_non_negative
        CHECK (basic_fare >= 0 AND fuel_charge >= 0 AND taxes_fees >= 0)
);

-- THE connection between a booking and its flights.
-- One booking -> many legs; each leg -> one flight. segment_order defines
-- connections (segment 1 feeds segment 2 -> missed-connection detectable).
CREATE TABLE booking_segments (
    segment_id    uuid           PRIMARY KEY DEFAULT uuidv7(),
    booking_ref   text           NOT NULL REFERENCES bookings(booking_ref) ON DELETE CASCADE,
    flight_id     uuid           NOT NULL REFERENCES flights(flight_id),
    segment_order integer        NOT NULL,              -- 1, 2, 3 ...
    seat          text,                                 -- "14A"
    status        segment_status NOT NULL DEFAULT 'confirmed',

    CONSTRAINT segment_order_positive CHECK (segment_order > 0),
    CONSTRAINT one_order_per_booking  UNIQUE (booking_ref, segment_order)
);

-- Checked bags. Lost/damaged/delayed baggage is a DIFFERENT compensation regime
-- (Carriage by Air Act / Montreal — weight & cap based), so the actual bag and
-- its weight must be tracked to compute liability.
CREATE TABLE baggage (
    bag_tag       text           PRIMARY KEY,            -- "BG12345678"
    booking_ref   text           NOT NULL REFERENCES bookings(booking_ref) ON DELETE CASCADE,
    segment_id    uuid           REFERENCES booking_segments(segment_id) ON DELETE SET NULL,
    weight_kg     numeric(5,1)   NOT NULL,               -- checked weight drives per-kg liability
    description   text,
    status        baggage_status NOT NULL DEFAULT 'checked',
    checked_at    timestamptz    NOT NULL DEFAULT now(),

    CONSTRAINT weight_positive CHECK (weight_kg > 0)
);

-- =============================================================================
-- GROUP C — Supply / inventory
--   Flights (above) are the rebooking supply. Hotels are the accommodation supply.
-- =============================================================================

CREATE TABLE hotels (
    hotel_id        uuid          PRIMARY KEY DEFAULT uuidv7(),
    name            text          NOT NULL,
    city            text          NOT NULL,
    near_airport    char(3)       NOT NULL REFERENCES airports(iata_code),
    star_rating     integer       NOT NULL,
    price_per_night numeric(10,2) NOT NULL,
    currency        char(3)       NOT NULL DEFAULT 'INR',
    rooms_available integer       NOT NULL DEFAULT 0,

    CONSTRAINT star_rating_range  CHECK (star_rating BETWEEN 1 AND 5),
    CONSTRAINT rooms_non_negative CHECK (rooms_available >= 0)
);

-- =============================================================================
-- GROUP D — DGCA regulations + transactional outputs
-- =============================================================================

-- DGCA cash-compensation rules (CAR Section 3, Series M, Part IV).
--   cancellation : banded by flight block time; multiplier 1.0 (one-way basic+fuel)
--   denied_boarding : banded by alternate-flight delay hours; multiplier 2.0 / 4.0
-- Payable amount = min(cap_amount, fare_multiplier * (basic_fare + fuel_charge)),
-- and only when NOT an extraordinary circumstance and within the notice window.
-- A JOIN + arithmetic, not an LLM guess.
CREATE TABLE dgca_compensation_rules (
    rule_id           uuid          PRIMARY KEY DEFAULT uuidv7(),
    event_type        comp_event    NOT NULL,

    -- cancellation bands (block time minutes); NULL for denied_boarding
    block_min_minutes integer,
    block_max_minutes integer,                          -- NULL = unbounded upper

    -- denied-boarding bands (alternate flight delay, hours); NULL for cancellation
    alt_min_hours     double precision,
    alt_max_hours     double precision,                 -- NULL = unbounded upper

    fare_multiplier   numeric(4,2)  NOT NULL,           -- 1.0 cancel; 2.0 / 4.0 denied boarding
    cap_amount        numeric(10,2) NOT NULL,           -- 5000/7500/10000 ; 10000/20000
    currency          char(3)       NOT NULL DEFAULT 'INR',
    car_ref           text          NOT NULL,           -- "CAR S3 Series M Part IV, Para 3.1.3"
    notes             text,

    CONSTRAINT band_shape_matches_event CHECK (
        (event_type = 'cancellation'
            AND block_min_minutes IS NOT NULL AND alt_min_hours IS NULL)
     OR (event_type = 'denied_boarding'
            AND alt_min_hours IS NOT NULL AND block_min_minutes IS NULL)
    ),
    CONSTRAINT multiplier_non_negative CHECK (fare_multiplier >= 0),
    CONSTRAINT cap_non_negative        CHECK (cap_amount >= 0)
);

-- DGCA duty-of-care thresholds (delay). Care is owed even under extraordinary
-- circumstances (weather waives cash, not care).
CREATE TABLE dgca_care_rules (
    rule_id          uuid             PRIMARY KEY DEFAULT uuidv7(),
    care_type        care_type        NOT NULL,
    min_delay_hours  double precision,                  -- threshold to trigger (NULL = overnight)
    overnight        boolean          NOT NULL DEFAULT false,
    car_ref          text             NOT NULL,
    notes            text
);

-- Baggage liability rules (Carriage by Air Act 1972 / Montreal Convention).
--   domestic      : per_kg_amount with a cap -> min(cap, per_kg * weight_kg)
--   international : fixed cap per passenger (Montreal SDR-based)
-- Each (jurisdiction, event_type) carries its own statutory claim deadline.
CREATE TABLE baggage_liability_rules (
    rule_id         uuid          PRIMARY KEY DEFAULT uuidv7(),
    jurisdiction    jurisdiction  NOT NULL,
    event_type      comp_event    NOT NULL,              -- lost/delayed/damaged_baggage
    per_kg_amount   numeric(10,2),                       -- NULL for international fixed cap
    cap_amount      numeric(10,2) NOT NULL,              -- 20000 domestic; ~172000 intl
    currency        char(3)       NOT NULL DEFAULT 'INR',
    claim_deadline_days integer   NOT NULL,              -- 7 damaged / 21 delayed / 730 lost
    legal_ref       text          NOT NULL,
    notes           text,

    CONSTRAINT baggage_event_only
        CHECK (event_type IN ('lost_baggage','delayed_baggage','damaged_baggage')),
    CONSTRAINT cap_positive CHECK (cap_amount > 0),
    CONSTRAINT one_rule_per_jurisdiction_event UNIQUE (jurisdiction, event_type)
);

-- output of the Compensation agent (submit_claim).
-- Polymorphic by event_type: flight-disruption claims cite a dgca_compensation_rule,
-- baggage claims cite a baggage_liability_rule. Exactly one FK applies.
CREATE TABLE claims (
    claim_ref      text          PRIMARY KEY,            -- customer-facing
    booking_ref    text          NOT NULL REFERENCES bookings(booking_ref) ON DELETE CASCADE,
    customer_id    uuid          NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    event_type     comp_event    NOT NULL,
    rule_id        uuid          REFERENCES dgca_compensation_rules(rule_id),   -- flight events
    baggage_rule_id uuid         REFERENCES baggage_liability_rules(rule_id),   -- baggage events
    bag_tag        text          REFERENCES baggage(bag_tag),                   -- for baggage claims
    amount         numeric(10,2) NOT NULL DEFAULT 0,
    currency       char(3)       NOT NULL DEFAULT 'INR',
    status         claim_status  NOT NULL DEFAULT 'submitted',
    submitted_at   timestamptz   NOT NULL DEFAULT now(),

    -- the right rule table for the event type (NULL allowed when ineligible)
    CONSTRAINT claim_rule_matches_event CHECK (
        (event_type IN ('cancellation','denied_boarding') AND baggage_rule_id IS NULL)
     OR (event_type IN ('lost_baggage','delayed_baggage','damaged_baggage') AND rule_id IS NULL)
    )
);

-- output of the Accommodation agent (book_hotel)
CREATE TABLE hotel_bookings (
    confirmation  text          PRIMARY KEY,            -- customer-facing
    hotel_id      uuid          NOT NULL REFERENCES hotels(hotel_id),
    customer_id   uuid          NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    booking_ref   text          REFERENCES bookings(booking_ref) ON DELETE SET NULL,
    check_in      timestamptz   NOT NULL,
    check_out     timestamptz   NOT NULL,
    price         numeric(10,2) NOT NULL,
    currency      char(3)       NOT NULL DEFAULT 'INR',
    booked_at     timestamptz   NOT NULL DEFAULT now(),

    CONSTRAINT checkout_after_checkin CHECK (check_out > check_in)
);
-- Rebooking has NO dedicated table: book_flight inserts a new booking_segments
-- row, decrements flights.seats_available, and flips the old segment to 'rebooked'.

-- =============================================================================
-- GROUP E — CaseFile persistence (one disruption journey, as JSONB)
-- =============================================================================
CREATE TABLE case_files (
    case_id      uuid         PRIMARY KEY DEFAULT uuidv7(),
    booking_ref  text         REFERENCES bookings(booking_ref) ON DELETE SET NULL,
    status       case_status  NOT NULL DEFAULT 'open',
    current_step text,
    report       jsonb        NOT NULL,                 -- DisruptionReport (slice 0)
    slices       jsonb        NOT NULL DEFAULT '{}',    -- identity/assessment/.../summary
    audit_log    jsonb        NOT NULL DEFAULT '[]',    -- append-only ActionRecord[]
    pending      jsonb,                                 -- approval question shown to the customer (when awaiting_input)
    runstate     jsonb,                                 -- engine resume state: {step_index, pending_call_id, messages}
    provider     text,                                  -- 'claude' | 'cortex' (A/B compare)
    created_at   timestamptz  NOT NULL DEFAULT now(),
    updated_at   timestamptz  NOT NULL DEFAULT now()
);

-- =============================================================================
-- Indexes — search tools (Rebooking / Accommodation) hit these hard
-- =============================================================================
CREATE INDEX idx_flights_route_dep ON flights (origin, destination, sched_departure)
    WHERE status <> 'cancelled' AND seats_available > 0;
CREATE INDEX idx_flights_flight_no ON flights (flight_no);
CREATE INDEX idx_segments_booking  ON booking_segments (booking_ref, segment_order);
CREATE INDEX idx_baggage_booking   ON baggage (booking_ref);
CREATE INDEX idx_baggage_status    ON baggage (status) WHERE status IN ('lost','delayed','damaged');
CREATE INDEX idx_hotels_airport    ON hotels (near_airport) WHERE rooms_available > 0;
CREATE INDEX idx_bookings_customer ON bookings (customer_id);
CREATE INDEX idx_dgca_cancel_band  ON dgca_compensation_rules (event_type, block_min_minutes, block_max_minutes);
CREATE INDEX idx_dgca_denied_band  ON dgca_compensation_rules (event_type, alt_min_hours, alt_max_hours);
CREATE INDEX idx_cases_booking     ON case_files (booking_ref);
CREATE INDEX idx_cases_status      ON case_files (status);
CREATE INDEX idx_cases_provider    ON case_files (provider);
CREATE INDEX idx_cases_slices_gin  ON case_files USING gin (slices);

-- =============================================================================
-- Seed: DGCA compensation + care rules (the regulation itself, not test fixtures)
--   CAR Section 3, Series M, Part IV. Amounts current as of 2024-25 revision.
-- =============================================================================
INSERT INTO dgca_compensation_rules
    (event_type, block_min_minutes, block_max_minutes, fare_multiplier, cap_amount, car_ref, notes)
VALUES
    ('cancellation',   0,   60, 1.0,  5000, 'CAR S3 M IV §3.1', 'Block time up to 1 hour'),
    ('cancellation',  60,  120, 1.0,  7500, 'CAR S3 M IV §3.1', 'Block time 1 to 2 hours'),
    ('cancellation', 120, NULL, 1.0, 10000, 'CAR S3 M IV §3.1', 'Block time over 2 hours');

INSERT INTO dgca_compensation_rules
    (event_type, alt_min_hours, alt_max_hours, fare_multiplier, cap_amount, car_ref, notes)
VALUES
    ('denied_boarding',  0,    1, 0.0,     0, 'CAR S3 M IV §3.2', 'Alternate within 1 hour — no compensation'),
    ('denied_boarding',  1,   24, 2.0, 10000, 'CAR S3 M IV §3.2', '200% of basic+fuel, capped'),
    ('denied_boarding', 24, NULL, 4.0, 20000, 'CAR S3 M IV §3.2', '400% of basic+fuel, capped');

INSERT INTO dgca_care_rules (care_type, min_delay_hours, overnight, car_ref, notes)
VALUES
    ('meals',     2.0, false, 'CAR S3 M IV §3.3', 'Meals & refreshments for delay of 2h+'),
    ('hotel',    NULL, true,  'CAR S3 M IV §3.3', 'Hotel accommodation for overnight delay'),
    ('transfers',NULL, true,  'CAR S3 M IV §3.3', 'Airport-hotel transfers with overnight stay'),
    ('refund',    6.0, false, 'CAR S3 M IV §3.3', 'Full refund option for delay beyond 6h / reschedule');

-- Baggage liability (Carriage by Air Act 1972 / DGCA CAR S3 M VI; Montreal Convention).
-- Domestic: ₹450/kg capped at ₹20,000. International: Montreal ~1288 SDR (~₹1,72,000).
INSERT INTO baggage_liability_rules
    (jurisdiction, event_type, per_kg_amount, cap_amount, currency, claim_deadline_days, legal_ref, notes)
VALUES
    ('domestic',      'lost_baggage',     450, 20000,  'INR',  730, 'Carriage by Air Act 1972 / CAR S3 M VI', '₹450/kg, ₹20k cap; 2-year limit for total loss'),
    ('domestic',      'damaged_baggage',  450, 20000,  'INR',    7, 'Carriage by Air Act 1972 / CAR S3 M VI', '₹450/kg, ₹20k cap; PIR within 7 days'),
    ('domestic',      'delayed_baggage',  450, 20000,  'INR',   21, 'Carriage by Air Act 1972 / CAR S3 M VI', '₹450/kg, ₹20k cap; claim within 21 days'),
    ('international',  'lost_baggage',    NULL, 172000, 'INR',  730, 'Montreal Convention 1999 (1288 SDR)',     'Fixed cap per passenger'),
    ('international',  'damaged_baggage', NULL, 172000, 'INR',    7, 'Montreal Convention 1999 (1288 SDR)',     'Fixed cap; written complaint within 7 days'),
    ('international',  'delayed_baggage', NULL, 172000, 'INR',   21, 'Montreal Convention 1999 (1288 SDR)',     'Fixed cap; complaint within 21 days');
