# ── TRUCK: Scheduled PM & Overhaul ───────────────────────────────────────────
# All truck events require a bay and a mechanic (bay: True throughout).
TRUCK_PM_SCHEDULE = {
    "PM_A":            {"interval": 250,    "duration_mean": 4,   "duration_sd": 1.0,  "bay": True},
    "PM_B":            {"interval": 500,    "duration_mean": 8,   "duration_sd": 1.5,  "bay": True},
    "PM_C":            {"interval": 1_000,  "duration_mean": 16,  "duration_sd": 2.0,  "bay": True},
    "PM_D":            {"interval": 3_000,  "duration_mean": 32,  "duration_sd": 4.0,  "bay": True},
    "suspension_OH":   {"interval": 3_000,  "duration_mean": 6,   "duration_sd": 1.5,  "bay": True},
    "hydraulic_OH":    {"interval": 4_000,  "duration_mean": 12,  "duration_sd": 3.0,  "bay": True},
    "tyre_replace":    {"interval": 5_000,  "duration_mean": 3,   "duration_sd": 0.5,  "bay": True},
    "injector_OH":     {"interval": 6_000,  "duration_mean": 8,   "duration_sd": 2.0,  "bay": True},
    "transmission_OH": {"interval": 13_000, "duration_mean": 48,  "duration_sd": 8.0,  "bay": True},
    "engine_rebuild":  {"interval": 20_000, "duration_mean": 240, "duration_sd": 24,   "bay": True},
}

# ── TRUCK: Premature Failures — Weibull(shape, scale) ────────────────────────
TRUCK_PREMATURE_FAILURE = {
    "engine":       {"shape": 2.0, "scale": 12_000, "repair_mean": 240, "repair_sd": 24,  "bay": True},
    "transmission": {"shape": 1.8, "scale":  8_000, "repair_mean": 48,  "repair_sd": 8,   "bay": True},
    "injectors":    {"shape": 2.0, "scale":  4_000, "repair_mean": 8,   "repair_sd": 2,   "bay": True},
    "hydraulics":   {"shape": 1.5, "scale":  2_500, "repair_mean": 12,  "repair_sd": 3,   "bay": True},
    "suspension":   {"shape": 2.0, "scale":  2_000, "repair_mean": 6,   "repair_sd": 1.5, "bay": True},
    "tyres":        {"shape": 2.5, "scale":  3_000, "repair_mean": 3,   "repair_sd": 0.5, "bay": True},
}

# ── SHOVEL: Scheduled PM & Overhaul ──────────────────────────────────────────
# bay: False → mechanic only (on-site); bay: True → bay + mechanic (workshop)
SHOVEL_PM_SCHEDULE = {
    "PM_A":             {"interval": 250,    "duration_mean": 3,   "duration_sd": 0.8,  "bay": False},
    "PM_B":             {"interval": 1_000,  "duration_mean": 6,   "duration_sd": 1.5,  "bay": False},
    "GET_replace":      {"interval": 1_000,  "duration_mean": 4,   "duration_sd": 1.0,  "bay": False},
    "pin_service":      {"interval": 3_000,  "duration_mean": 8,   "duration_sd": 2.0,  "bay": False},
    "hydraulic_OH":     {"interval": 4_000,  "duration_mean": 16,  "duration_sd": 4.0,  "bay": True},
    "swing_ring_OH":    {"interval": 6_000,  "duration_mean": 24,  "duration_sd": 6.0,  "bay": True},
    "undercarriage_OH": {"interval": 8_000,  "duration_mean": 48,  "duration_sd": 10.0, "bay": True},
    "swing_gear_OH":    {"interval": 12_000, "duration_mean": 32,  "duration_sd": 8.0,  "bay": True},
    "engine_rebuild":   {"interval": 20_000, "duration_mean": 240, "duration_sd": 24,   "bay": True},
}

# ── SHOVEL: Premature Failures — Weibull(shape, scale) ───────────────────────
# Engine scale 12,000 matches the concept-doc narrative table (same as truck).
# The 4,000 figure in the concept doc's Python block was a transcription error.
SHOVEL_PREMATURE_FAILURE = {
    "engine":        {"shape": 2.0, "scale": 12_000, "repair_mean": 48,  "repair_sd": 24,  "bay": True},
    "hydraulics":    {"shape": 1.5, "scale":  2_500, "repair_mean": 16,  "repair_sd": 4,   "bay": True},
    "swing_ring":    {"shape": 2.0, "scale":  4_000, "repair_mean": 48,  "repair_sd": 12,  "bay": True},
    "boom_pins":     {"shape": 2.2, "scale":  2_000, "repair_mean": 12,  "repair_sd": 3,   "bay": True},
    "GET":           {"shape": 1.8, "scale":    600,  "repair_mean": 4,   "repair_sd": 1,   "bay": True},
    "undercarriage": {"shape": 2.5, "scale":  5_000, "repair_mean": 24,  "repair_sd": 6,   "bay": True},
}

# ── Shared Resources ──────────────────────────────────────────────────────────
N_BAYS      = 4   # workshop bays (all truck events; shovel major events only)
N_MECHANICS = 6   # mechanics — day-shift baseline

# ── Fleet Size ────────────────────────────────────────────────────────────────
N_TRUCKS  = 15
N_SHOVELS = 3

# ── Opportunistic Maintenance Window ─────────────────────────────────────────
OPP_WINDOW_HRS = 50   # combine premature failure + scheduled PM when this close

# ── Shift Schedule ────────────────────────────────────────────────────────────
# Two 12-hour shifts per day (06:00–18:00 day, 18:00–06:00 night).
# Each entry is one phase within a shift.  Phases tile the 24-hour clock
# without gaps and repeat daily.
#
# Fields:
#   name        — human-readable label
#   start       — hour-of-day this phase begins (0–23, decimals allowed)
#   duration    — phase length in hours
#   n_mechanics — mechanics available for work during this phase
#   productive  — False marks handover/break windows (new requests blocked)
#
# Non-productive phases:
#   Handover : 30 min at each shift change — both crews present but occupied
#              with handover; 0 mechanics available for new work.
#   Crib break: two 30-min breaks per shift where the crew rotates in two
#              groups — half the mechanics remain available.
SHIFT_SCHEDULE = [
    # ── Day shift 06:00–18:00 ──────────────────────────────────────────────
    {"name": "day_handover",    "start":  6.0, "duration": 0.5, "n_mechanics": 0, "productive": False},
    {"name": "day_working_1",   "start":  6.5, "duration": 3.5, "n_mechanics": 6, "productive": True},
    {"name": "day_crib_1",      "start": 10.0, "duration": 0.5, "n_mechanics": 3, "productive": False},
    {"name": "day_working_2",   "start": 10.5, "duration": 4.5, "n_mechanics": 6, "productive": True},
    {"name": "day_crib_2",      "start": 15.0, "duration": 0.5, "n_mechanics": 3, "productive": False},
    {"name": "day_working_3",   "start": 15.5, "duration": 2.0, "n_mechanics": 6, "productive": True},
    # ── Night shift 18:00–06:00 ────────────────────────────────────────────
    {"name": "night_handover",  "start": 17.5, "duration": 0.5, "n_mechanics": 0, "productive": False},
    {"name": "night_working_1", "start": 18.0, "duration": 3.5, "n_mechanics": 4, "productive": True},
    {"name": "night_crib_1",    "start": 21.5, "duration": 0.5, "n_mechanics": 2, "productive": False},
    {"name": "night_working_2", "start": 22.0, "duration": 4.5, "n_mechanics": 4, "productive": True},
    {"name": "night_crib_2",    "start":  2.5, "duration": 0.5, "n_mechanics": 2, "productive": False},
    {"name": "night_working_3", "start":  3.0, "duration": 3.0, "n_mechanics": 4, "productive": True},
]

# ── Equipment Utilisation Schedule ───────────────────────────────────────────
# Per-equipment fraction of each calendar year that the machine is deployed.
# 1.0 = fully utilised; 0.6 = 60% utilisation (PM clocks accumulate 40% slower).
# Equipment not listed here defaults to 1.0 for all years.
# Trucks/shovels with a ramp-down to 0 will idle out their remaining sim time.
UTILISATION: dict[str, dict[int, float]] = {
    "Shovel-0": {2026: 1.0, 2027: 1.0, 2028: 1.0, 2029: 1.0, 2030: 1.0},
    "Shovel-1": {2026: 1.0, 2027: 1.0, 2028: 1.0, 2029: 1.0, 2030: 0.6},
    "Shovel-2": {2026: 1.0, 2027: 1.0, 2028: 0.8, 2029: 0.6, 2030: 0.4},
    "Truck-0":  {2026: 1.0, 2027: 1.0, 2028: 1.0, 2029: 1.0, 2030: 1.0},
    "Truck-1":  {2026: 1.0, 2027: 1.0, 2028: 1.0, 2029: 1.0, 2030: 1.0},
    "Truck-2":  {2026: 1.0, 2027: 1.0, 2028: 1.0, 2029: 1.0, 2030: 1.0},
    "Truck-3":  {2026: 1.0, 2027: 1.0, 2028: 1.0, 2029: 1.0, 2030: 1.0},
    "Truck-4":  {2026: 1.0, 2027: 1.0, 2028: 1.0, 2029: 1.0, 2030: 1.0},
    "Truck-5":  {2026: 1.0, 2027: 1.0, 2028: 1.0, 2029: 1.0, 2030: 1.0},
    "Truck-6":  {2026: 1.0, 2027: 1.0, 2028: 0.8, 2029: 0.6, 2030: 0.4},
    "Truck-7":  {2026: 1.0, 2027: 1.0, 2028: 0.8, 2029: 0.6, 2030: 0.4},
    "Truck-8":  {2026: 1.0, 2027: 1.0, 2028: 0.8, 2029: 0.6, 2030: 0.4},
    "Truck-9":  {2026: 1.0, 2027: 1.0, 2028: 0.8, 2029: 0.6, 2030: 0.4},
    "Truck-10": {2026: 1.0, 2027: 0.8, 2028: 0.6, 2029: 0.4, 2030: 0.0},
    "Truck-11": {2026: 1.0, 2027: 0.8, 2028: 0.6, 2029: 0.4, 2030: 0.0},
    "Truck-12": {2026: 1.0, 2027: 0.8, 2028: 0.6, 2029: 0.4, 2030: 0.0},
    "Truck-13": {2026: 1.0, 2027: 0.8, 2028: 0.6, 2029: 0.4, 2030: 0.0},
    "Truck-14": {2026: 1.0, 2027: 0.8, 2028: 0.6, 2029: 0.4, 2030: 0.0},
}

# ── Simulation Settings ───────────────────────────────────────────────────────
SIM_DURATION = 43_800  # hours (5 years)
N_RUNS       = 1       # Phase 1: single deterministic run
RANDOM_SEED  = 42

from datetime import datetime, timezone
SIM_START = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)  # hour 0 = simulation epoch
