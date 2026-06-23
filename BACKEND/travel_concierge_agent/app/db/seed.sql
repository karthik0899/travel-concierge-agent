-- =============================================================================
-- Travel Concierge Agent — demo seed data (PostgreSQL 18)
-- =============================================================================
-- Run AFTER schema.sql (which already seeds the DGCA rules — the law itself).
-- This file seeds the *world* for the demo: airports, airlines, customers,
-- flights, bookings, hotels.
--
-- "Today" for this demo is 2026-06-23 (IST). Times are Asia/Kolkata (+05:30).
--
-- Six booking PNRs, each a DELIBERATE disruption scenario that exercises a
-- different branch of the agent flow:
--
--   PNR001  Cancelled flight, AIRLINE FAULT, short notice, last flight of day
--           -> rebook (next morning) + OVERNIGHT HOTEL + CASH COMPENSATION (₹10k band)
--   PNR002  Cancelled flight, EXTRAORDINARY (weather)
--           -> rebook + hotel, but NO cash compensation (duty of care only)
--   PNR003  Missed connection (multi-leg DEL->BOM->COK, leg 1 delayed)
--           -> rebook leg 2 only; tests segment_order connection logic
--   PNR004  Denied boarding (overbooking), alternate within 24h
--           -> rebook + DENIED-BOARDING COMPENSATION (200%, ₹10k cap)
--   PNR005  Lost baggage (flight arrived fine)
--           -> NO rebooking / NO hotel; claim-only path (scope branch)
--   PNR006  Long delay (4h), airline fault
--           -> duty of care (meals/refund), no rebooking needed
--
-- Each route also has ALTERNATIVE flights with seats so the Rebooking agent has
-- something real to find and compare.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Airports (Indian metros + a couple of spokes)
-- -----------------------------------------------------------------------------
INSERT INTO airports (iata_code, name, city, country, lat, lon) VALUES
    ('DEL', 'Indira Gandhi International',      'Delhi',     'India', 28.5562, 77.1000),
    ('BOM', 'Chhatrapati Shivaji Maharaj Intl', 'Mumbai',    'India', 19.0896, 72.8656),
    ('BLR', 'Kempegowda International',          'Bengaluru', 'India', 13.1986, 77.7066),
    ('MAA', 'Chennai International',             'Chennai',   'India', 12.9941, 80.1709),
    ('COK', 'Cochin International',              'Kochi',     'India', 10.1520, 76.3919),
    ('GOI', 'Manohar International (Goa)',       'Goa',       'India', 15.3808, 73.8314),
    ('HYD', 'Rajiv Gandhi International',        'Hyderabad', 'India', 17.2403, 78.4294),
    ('CCU', 'Netaji Subhas Chandra Bose Intl',  'Kolkata',   'India', 22.6547, 88.4467);

-- -----------------------------------------------------------------------------
-- Airlines
-- -----------------------------------------------------------------------------
INSERT INTO airlines (code, name) VALUES
    ('6E', 'IndiGo'),
    ('AI', 'Air India'),
    ('UK', 'Vistara'),
    ('SG', 'SpiceJet');

-- -----------------------------------------------------------------------------
-- Customers (loyalty tier varies so the demo can show tier-aware behaviour)
-- -----------------------------------------------------------------------------
INSERT INTO customers (name, email, phone, loyalty_tier) VALUES
    ('Rohan Sharma',  'rohan.sharma@example.in',  '+91-98100-11111', 'gold'),
    ('Priya Nair',    'priya.nair@example.in',    '+91-98200-22222', 'silver'),
    ('Arjun Mehta',   'arjun.mehta@example.in',   '+91-98300-33333', 'platinum'),
    ('Sneha Reddy',   'sneha.reddy@example.in',   '+91-98400-44444', 'none'),
    ('Vikram Singh',  'vikram.singh@example.in',  '+91-98500-55555', 'gold'),
    ('Kavya Iyer',    'kavya.iyer@example.in',    '+91-98600-66666', 'silver');

-- =============================================================================
-- FLIGHTS
--   Disrupted flights (the originals) + alternatives for rebooking search.
--   block_minutes is auto-derived from (sched_arrival - sched_departure).
-- =============================================================================

-- ---- Scenario 1: DEL -> BOM, evening flight CANCELLED (airline fault) --------
-- Original: block 130 min (>2h -> ₹10,000 cap). Cancelled 3h before dep (<24h).
INSERT INTO flights
    (flight_no, airline_code, origin, destination, sched_departure, sched_arrival,
     status, delay_minutes, cancel_cause, cancelled_at, aircraft, seats_available, base_price) VALUES
    ('6E2341', '6E', 'DEL', 'BOM', '2026-06-23 20:00+05:30', '2026-06-23 22:10+05:30',
     'cancelled', 0, 'airline_fault', '2026-06-23 17:00+05:30', 'A320', 0, 7800),
-- Alternatives DEL->BOM (next morning -> forces overnight hotel)
    ('6E2401', '6E', 'DEL', 'BOM', '2026-06-24 06:00+05:30', '2026-06-24 08:10+05:30',
     'scheduled', 0, NULL, NULL, 'A320', 25, 7200),
    ('AI805',  'AI', 'DEL', 'BOM', '2026-06-24 07:30+05:30', '2026-06-24 09:45+05:30',
     'scheduled', 0, NULL, NULL, 'A321', 12, 8100),
    ('UK931',  'UK', 'DEL', 'BOM', '2026-06-24 09:15+05:30', '2026-06-24 11:25+05:30',
     'scheduled', 0, NULL, NULL, 'A320neo', 30, 7600);

-- ---- Scenario 2: DEL -> GOI, CANCELLED (extraordinary / weather) -------------
-- block 155 min. Cause extraordinary -> NO cash comp, but duty of care applies.
INSERT INTO flights
    (flight_no, airline_code, origin, destination, sched_departure, sched_arrival,
     status, delay_minutes, cancel_cause, cancelled_at, aircraft, seats_available, base_price) VALUES
    ('6E5577', '6E', 'DEL', 'GOI', '2026-06-23 19:00+05:30', '2026-06-23 21:35+05:30',
     'cancelled', 0, 'extraordinary_circumstance', '2026-06-23 14:00+05:30', 'A320', 0, 6400),
-- Alternative DEL->GOI (next morning -> overnight)
    ('6E5601', '6E', 'DEL', 'GOI', '2026-06-24 08:00+05:30', '2026-06-24 10:35+05:30',
     'scheduled', 0, NULL, NULL, 'A320', 18, 6500),
    ('SG211',  'SG', 'DEL', 'GOI', '2026-06-24 10:30+05:30', '2026-06-24 13:00+05:30',
     'scheduled', 0, NULL, NULL, 'B737', 9, 6100);

-- ---- Scenario 3: DEL -> BOM -> COK, leg 1 DELAYED -> missed connection -------
-- Leg 1 delayed 180 min; passenger arrives BOM ~19:10, misses leg 2 (dep 18:00).
INSERT INTO flights
    (flight_no, airline_code, origin, destination, sched_departure, sched_arrival,
     status, delay_minutes, cancel_cause, cancelled_at, aircraft, seats_available, base_price) VALUES
    ('AI2934', 'AI', 'DEL', 'BOM', '2026-06-23 14:00+05:30', '2026-06-23 16:10+05:30',
     'delayed', 180, NULL, NULL, 'A321', 0, 7900),
    ('AI676',  'AI', 'BOM', 'COK', '2026-06-23 18:00+05:30', '2026-06-23 20:00+05:30',
     'scheduled', 0, NULL, NULL, 'A320', 0, 5600),
-- Alternatives BOM->COK (later same night / next morning)
    ('6E455',  '6E', 'BOM', 'COK', '2026-06-23 22:30+05:30', '2026-06-24 00:30+05:30',
     'scheduled', 0, NULL, NULL, 'A320', 8, 5400),
    ('AI680',  'AI', 'BOM', 'COK', '2026-06-24 06:00+05:30', '2026-06-24 08:00+05:30',
     'scheduled', 0, NULL, NULL, 'A320', 15, 5900);

-- ---- Scenario 4: BLR -> DEL, DENIED BOARDING (overbooked) --------------------
-- Flight operates fine; passenger bumped. Alternate within 24h -> 200%, ₹10k cap.
INSERT INTO flights
    (flight_no, airline_code, origin, destination, sched_departure, sched_arrival,
     status, delay_minutes, cancel_cause, cancelled_at, aircraft, seats_available, base_price) VALUES
    ('6E709',  '6E', 'BLR', 'DEL', '2026-06-23 16:00+05:30', '2026-06-23 18:50+05:30',
     'scheduled', 0, NULL, NULL, 'A320', 0, 6700),
-- Alternative BLR->DEL same evening (within 24h)
    ('6E715',  '6E', 'BLR', 'DEL', '2026-06-23 20:00+05:30', '2026-06-23 22:50+05:30',
     'scheduled', 0, NULL, NULL, 'A320neo', 6, 6800),
    ('UK864',  'UK', 'BLR', 'DEL', '2026-06-23 21:30+05:30', '2026-06-24 00:20+05:30',
     'scheduled', 0, NULL, NULL, 'A320', 14, 7100);

-- ---- Scenario 5: DEL -> MAA, LOST BAGGAGE (flight arrived fine) --------------
INSERT INTO flights
    (flight_no, airline_code, origin, destination, sched_departure, sched_arrival,
     status, delay_minutes, cancel_cause, cancelled_at, aircraft, seats_available, base_price) VALUES
    ('UK945',  'UK', 'DEL', 'MAA', '2026-06-22 10:00+05:30', '2026-06-22 12:45+05:30',
     'arrived', 0, NULL, NULL, 'A321', 0, 8500);

-- ---- Scenario 6: DEL -> HYD, long DELAY (4h, airline fault) ------------------
-- Duty of care (meals / refund option). Delay -> no DGCA cash comp.
INSERT INTO flights
    (flight_no, airline_code, origin, destination, sched_departure, sched_arrival,
     status, delay_minutes, cancel_cause, cancelled_at, aircraft, seats_available, base_price) VALUES
    ('6E812',  '6E', 'DEL', 'HYD', '2026-06-23 21:00+05:30', '2026-06-23 23:05+05:30',
     'delayed', 240, NULL, NULL, 'A320', 0, 5600);

-- =============================================================================
-- BOOKINGS  (fare decomposed: basic_fare + fuel_charge drive DGCA compensation)
-- =============================================================================
INSERT INTO bookings (booking_ref, customer_id, fare_class, basic_fare, fuel_charge, taxes_fees, status)
SELECT 'PNR001', customer_id, 'economy',  8000, 1500,  800, 'disrupted' FROM customers WHERE email='rohan.sharma@example.in';
INSERT INTO bookings (booking_ref, customer_id, fare_class, basic_fare, fuel_charge, taxes_fees, status)
SELECT 'PNR002', customer_id, 'economy',  6000, 1200,  600, 'disrupted' FROM customers WHERE email='priya.nair@example.in';
INSERT INTO bookings (booking_ref, customer_id, fare_class, basic_fare, fuel_charge, taxes_fees, status)
SELECT 'PNR003', customer_id, 'business',11000, 2000, 1500, 'disrupted' FROM customers WHERE email='arjun.mehta@example.in';
INSERT INTO bookings (booking_ref, customer_id, fare_class, basic_fare, fuel_charge, taxes_fees, status)
SELECT 'PNR004', customer_id, 'economy',  5500, 1000,  700, 'disrupted' FROM customers WHERE email='sneha.reddy@example.in';
INSERT INTO bookings (booking_ref, customer_id, fare_class, basic_fare, fuel_charge, taxes_fees, status)
SELECT 'PNR005', customer_id, 'premium',  9000, 1600,  900, 'active'    FROM customers WHERE email='vikram.singh@example.in';
INSERT INTO bookings (booking_ref, customer_id, fare_class, basic_fare, fuel_charge, taxes_fees, status)
SELECT 'PNR006', customer_id, 'economy',  4800,  900,  500, 'disrupted' FROM customers WHERE email='kavya.iyer@example.in';

-- =============================================================================
-- BOOKING SEGMENTS  (the booking <-> flight connection; segment_order = leg)
-- =============================================================================
-- PNR001: single leg DEL->BOM (the cancelled flight)
INSERT INTO booking_segments (booking_ref, flight_id, segment_order, seat, status)
SELECT 'PNR001', flight_id, 1, '12C', 'disrupted' FROM flights WHERE flight_no='6E2341';

-- PNR002: single leg DEL->GOI (cancelled, weather)
INSERT INTO booking_segments (booking_ref, flight_id, segment_order, seat, status)
SELECT 'PNR002', flight_id, 1, '8A', 'disrupted' FROM flights WHERE flight_no='6E5577';

-- PNR003: TWO legs DEL->BOM (delayed) then BOM->COK (missed)
INSERT INTO booking_segments (booking_ref, flight_id, segment_order, seat, status)
SELECT 'PNR003', flight_id, 1, '3A', 'disrupted' FROM flights WHERE flight_no='AI2934';
INSERT INTO booking_segments (booking_ref, flight_id, segment_order, seat, status)
SELECT 'PNR003', flight_id, 2, '3B', 'disrupted' FROM flights WHERE flight_no='AI676';

-- PNR004: single leg BLR->DEL (denied boarding)
INSERT INTO booking_segments (booking_ref, flight_id, segment_order, seat, status)
SELECT 'PNR004', flight_id, 1, '19F', 'disrupted' FROM flights WHERE flight_no='6E709';

-- PNR005: single leg DEL->MAA (arrived; baggage lost)
INSERT INTO booking_segments (booking_ref, flight_id, segment_order, seat, status)
SELECT 'PNR005', flight_id, 1, '2D', 'confirmed' FROM flights WHERE flight_no='UK945';

-- PNR006: single leg DEL->HYD (delayed 4h)
INSERT INTO booking_segments (booking_ref, flight_id, segment_order, seat, status)
SELECT 'PNR006', flight_id, 1, '22A', 'disrupted' FROM flights WHERE flight_no='6E812';

-- =============================================================================
-- BAGGAGE  (Scenario 5 = PNR005 has a LOST bag; others delivered for realism)
--   Domestic liability = min(₹20,000, ₹450/kg). 18.5kg lost -> ₹8,325.
-- =============================================================================
INSERT INTO baggage (bag_tag, booking_ref, segment_id, weight_kg, description, status)
SELECT 'BG10050001', 'PNR005', s.segment_id, 18.5, 'Large grey suitcase', 'lost'
FROM booking_segments s WHERE s.booking_ref='PNR005' AND s.segment_order=1;

INSERT INTO baggage (bag_tag, booking_ref, segment_id, weight_kg, description, status)
SELECT 'BG10010001', 'PNR001', s.segment_id, 15.0, 'Black trolley bag', 'checked'
FROM booking_segments s WHERE s.booking_ref='PNR001' AND s.segment_order=1;

INSERT INTO baggage (bag_tag, booking_ref, segment_id, weight_kg, description, status)
SELECT 'BG10030001', 'PNR003', s.segment_id, 22.0, 'Red hardcase', 'in_transit'
FROM booking_segments s WHERE s.booking_ref='PNR003' AND s.segment_order=1;

-- =============================================================================
-- HOTELS  (near airports where overnight stays may be needed)
-- =============================================================================
INSERT INTO hotels (name, city, near_airport, star_rating, price_per_night, rooms_available) VALUES
    ('Aerocity Grand',        'Delhi',     'DEL', 5, 8500, 20),
    ('IGI Transit Inn',       'Delhi',     'DEL', 3, 3200, 40),
    ('Holiday Stay Aerocity', 'Delhi',     'DEL', 4, 5400, 15),
    ('Mumbai Airport Suites', 'Mumbai',    'BOM', 5, 9200, 12),
    ('Sahar Comfort Hotel',   'Mumbai',    'BOM', 3, 3600, 25),
    ('Goa Airport Resort',    'Goa',       'GOI', 4, 6100, 10),
    ('Kochi Airport Lodge',   'Kochi',     'COK', 3, 2900, 18),
    ('Bengaluru Air Plaza',   'Bengaluru', 'BLR', 4, 5800, 22),
    ('Hyderabad Sky Hotel',   'Hyderabad', 'HYD', 4, 5200, 16);

-- =============================================================================
-- Demo cheat-sheet — what to type as the customer "disruption report":
--   PNR001  "My flight 6E2341 from Delhi to Mumbai tonight was cancelled."
--   PNR002  "Flight 6E5577 DEL-GOI cancelled due to weather."
--   PNR003  "My DEL-BOM flight was delayed and I missed my BOM-COK connection."
--   PNR004  "I was denied boarding on 6E709 from Bangalore, the flight was overbooked."
--   PNR005  "My baggage didn't arrive on UK945 to Chennai."
--   PNR006  "Flight 6E812 DEL-HYD is delayed by 4 hours."
-- =============================================================================
