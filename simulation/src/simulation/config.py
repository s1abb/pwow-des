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
# Keyed by activity group (RPR/RPL/INS/TYR) matching the fitting pipeline output.
# bay key removed — all premature failures unconditionally require a bay + mechanic.
PREMATURE_FAILURE: dict[str, dict[str, dict]] = {
    "Cat_793F": {
        "RPR": {"shape": 1.010, "scale":   382, "repair_mean": 4.87, "repair_sd":  9.10},
        "RPL": {"shape": 0.900, "scale":   374, "repair_mean": 5.50, "repair_sd": 13.99},
        "INS": {"shape": 0.968, "scale": 1_068, "repair_mean": 4.28, "repair_sd":  5.41},
        "TYR": {"shape": 1.087, "scale": 2_430, "repair_mean": 6.69, "repair_sd":  5.03},
    },
    "EH4000": {
        "RPR": {"shape": 1.038, "scale":   286, "repair_mean": 5.21, "repair_sd": 11.64},
        "RPL": {"shape": 0.934, "scale":   449, "repair_mean": 5.13, "repair_sd": 11.18},
        "INS": {"shape": 0.918, "scale": 1_468, "repair_mean": 2.98, "repair_sd":  5.83},
        "TYR": {"shape": 1.083, "scale": 2_245, "repair_mean": 8.63, "repair_sd":  6.40},
    },
    "EH5000": {
        "RPR": {"shape": 0.983, "scale":   247, "repair_mean": 5.93, "repair_sd": 10.68},
        "RPL": {"shape": 0.999, "scale":   313, "repair_mean": 6.76, "repair_sd": 13.47},
        "INS": {"shape": 0.894, "scale":   750, "repair_mean": 4.64, "repair_sd":  8.37},
        "TYR": {"shape": 1.088, "scale": 1_798, "repair_mean": 8.04, "repair_sd":  6.00},
    },
    "EX3600": {
        "RPR": {"shape": 0.892, "scale":  207, "repair_mean": 6.54, "repair_sd": 13.64},
        "RPL": {"shape": 0.737, "scale":  159, "repair_mean": 6.05, "repair_sd": 17.56},
        "INS": {"shape": 0.886, "scale":  604, "repair_mean": 3.62, "repair_sd":  9.05},
    },
    "EX5600": {
        "RPR": {"shape": 0.906, "scale":   99, "repair_mean": 5.88, "repair_sd": 15.49},
        "RPL": {"shape": 0.835, "scale":   86, "repair_mean": 5.66, "repair_sd": 19.47},
        "INS": {"shape": 0.921, "scale":  240, "repair_mean": 2.46, "repair_sd":  4.53},
    },
    "EX8000": {
        "RPR": {"shape": 0.696, "scale":  181, "repair_mean": 7.25, "repair_sd": 33.48},
        "RPL": {"shape": 0.634, "scale":  164, "repair_mean": 7.38, "repair_sd": 31.42},
        "INS": {"shape": 0.897, "scale":  951, "repair_mean": 3.90, "repair_sd":  5.15},
    },
    "L9800": {
        "RPR": {"shape": 0.812, "scale":  132, "repair_mean": 4.89, "repair_sd":  7.47},
        "RPL": {"shape": 0.678, "scale":   99, "repair_mean": 6.79, "repair_sd": 13.56},
        "INS": {"shape": 0.889, "scale":  349, "repair_mean": 3.02, "repair_sd":  3.45},
    },
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
# Shovel models use the same PREMATURE_FAILURE dict above (EX3600/EX5600/EX8000/L9800).

# ── Activity-group bay requirements (fitted mode) ────────────────────────────
# Used when USE_FITTED_PARAMS=True.  Maps prefixed AG key → requires workshop bay.
# True  = bay + mechanic.  False = mechanic only (field / on-machine work).
AG_REQUIRES_BAY: dict[str, bool] = {
    # Corrective
    "c_RPR":      True,   # unplanned workshop repair
    "c_RPL":      True,   # unplanned component replacement
    "c_INS":      False,  # on-machine inspection / fault-find
    "c_TYR":      True,   # tyre change
    "c_OTHER_CM": True,   # other corrective (conservative default)
    # Preventive
    "p_SVC":      False,  # on-site fluid/filter service
    "p_RPL":      True,   # planned component swap
    "p_NDT":      False,  # on-machine non-destructive testing
    "p_INS":      False,  # planned on-machine inspection
    "p_TYR":      True,   # planned tyre replacement
    "p_CAS":      True,   # component assembly / overhaul
    "p_OTHER_PM": False,  # other light PM (conservative default)
}

# ── Shared Resources ──────────────────────────────────────────────────────────
N_BAYS      = 12  # workshop bays (all truck events; shovel major events only)
N_MECHANICS = 24  # mechanics — day-shift baseline

# ── Fleet Size ────────────────────────────────────────────────────────────────
N_FLEET: dict[str, int] = {
    "Cat_793F": 56,
    "EH4000":   19,
    "EH5000":   24,
    "EX3600":    8,
    "EX5600":    5,
    "EX8000":    3,
    "L9800":     2,
}

_TRUCK_MODELS  = ("Cat_793F", "EH4000", "EH5000")
_SHOVEL_MODELS = ("EX3600", "EX5600", "EX8000", "L9800")

N_TRUCKS  = sum(N_FLEET[m] for m in _TRUCK_MODELS)   # 99
N_SHOVELS = sum(N_FLEET[m] for m in _SHOVEL_MODELS)  # 18

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
    {"name": "day_handover",    "start":  6.0, "duration": 0.5, "n_mechanics":  0, "productive": False},
    {"name": "day_working_1",   "start":  6.5, "duration": 3.5, "n_mechanics": 24, "productive": True},
    {"name": "day_crib_1",      "start": 10.0, "duration": 0.5, "n_mechanics": 12, "productive": False},
    {"name": "day_working_2",   "start": 10.5, "duration": 4.5, "n_mechanics": 24, "productive": True},
    {"name": "day_crib_2",      "start": 15.0, "duration": 0.5, "n_mechanics": 12, "productive": False},
    {"name": "day_working_3",   "start": 15.5, "duration": 2.0, "n_mechanics": 24, "productive": True},
    # ── Night shift 18:00–06:00 ────────────────────────────────────────────
    {"name": "night_handover",  "start": 17.5, "duration": 0.5, "n_mechanics":  0, "productive": False},
    {"name": "night_working_1", "start": 18.0, "duration": 3.5, "n_mechanics": 16, "productive": True},
    {"name": "night_crib_1",    "start": 21.5, "duration": 0.5, "n_mechanics":  8, "productive": False},
    {"name": "night_working_2", "start": 22.0, "duration": 4.5, "n_mechanics": 16, "productive": True},
    {"name": "night_crib_2",    "start":  2.5, "duration": 0.5, "n_mechanics":  8, "productive": False},
    {"name": "night_working_3", "start":  3.0, "duration": 3.0, "n_mechanics": 16, "productive": True},
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
SIM_DURATION = 13_140  # hours (1.5 years)
N_RUNS       = 1       # Phase 1: single deterministic run
RANDOM_SEED  = 42

from datetime import datetime, timezone
SIM_START = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)  # hour 0 = simulation epoch

# ── Fitted-parameter toggle ───────────────────────────────────────────────────
# Set True to override premature-failure dicts with actuals-fitted values from
# fitting/output/fitted_config.py (run `python -m fitting` to regenerate).
USE_FITTED_PARAMS = False

if USE_FITTED_PARAMS:
    try:
        from fitting.output.fitted_config import PREMATURE_FAILURE_FITTED  # type: ignore[import]
        # PREMATURE_FAILURE_FITTED is a 3-level dict:
        #   model → order_type_group → activity_group → {shape, scale, ...}
        # Flatten to the 2-level structure the simulation expects:
        #   model → activity_group → {shape, scale, ...}
        # Activity group keys are prefixed with order type ('c_' / 'p_') to avoid
        # collisions where the same code appears in both corrective and preventive.
        _PREFIX = {"corrective": "c_", "preventive": "p_"}
        PREMATURE_FAILURE = {
            model: {
                _PREFIX.get(otg, otg + "_") + ag: params
                for otg, ags in otg_dict.items()
                for ag, params in ags.items()
            }
            for model, otg_dict in PREMATURE_FAILURE_FITTED.items()
        }
    except (ImportError, KeyError):
        import warnings
        warnings.warn(
            "USE_FITTED_PARAMS=True but fitting/output/fitted_config.py not found "
            "or expected model key missing. Using hand-coded defaults."
        )
