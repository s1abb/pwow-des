"""Phase 1 acceptance tests — single truck, one bay, one mechanic.

Run with:  pytest simulation/tests/test_phase1.py -v
"""
import math

import pytest

from simulation.config import (
    SIM_DURATION,
    TRUCK_PREMATURE_FAILURE,
)
from simulation.sim import _PHASE1_BAYS, _PHASE1_MECHANICS, run_phase1


# ---------------------------------------------------------------------------
# Shared fixture — run the simulation once and reuse results across tests.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def phase1():
    stats, bay, mechanic = run_phase1()
    return stats, bay, mechanic


# ---------------------------------------------------------------------------
# 1. Physical availability lands in the expected single-truck range.
#
#    With 1 truck, 1 bay, 1 mechanic (no resource contention) and the given
#    PM schedule, PA% is consistently 96–98%.  The 92–94% concept-doc target
#    is a fleet figure under resource contention (Phases 2–4).
# ---------------------------------------------------------------------------

def test_pa_pct_in_benchmark_range(phase1):
    stats, _, _ = phase1
    pa = stats.summary()["pa_pct"]
    assert 95.0 <= pa <= 99.0, (
        f"PA% = {pa:.2f}% is outside the expected Phase 1 range [95, 99]"
    )


# ---------------------------------------------------------------------------
# 2. Scheduled PMs fire at exact multiples of 250 operating hours.
#
#    All PM intervals are multiples of 250, so PM-A always coincides with
#    every scheduled threshold.  cum_op_hrs at each scheduled/opportunistic
#    event must be an integer multiple of 250 (no floating-point drift).
# ---------------------------------------------------------------------------

def test_pm_fires_at_250_hr_multiples(phase1):
    stats, _, _ = phase1
    for event in stats.events:
        if event["type"] in ("scheduled", "opportunistic"):
            cum = event["cum_op_hrs"]
            remainder = cum % 250.0
            assert remainder < 1e-6 or abs(remainder - 250.0) < 1e-6, (
                f"Scheduled event '{event['name']}' fired at cum_op_hrs={cum:.4f}, "
                f"which is not a multiple of 250"
            )


# ---------------------------------------------------------------------------
# 3. Weibull TTF produces realistic premature-failure counts.
#
#    With the given scale values (>>250 hrs) and a 1-year run, premature
#    failures should be rare: 0–10 per year for one truck.
#    Any component that does fail more than once should have MTBF > 0.5×scale.
# ---------------------------------------------------------------------------

def test_weibull_ttf_produces_realistic_mtbf(phase1):
    stats, _, _ = phase1
    summary = stats.summary()

    # Rare failures: expect at most 10 unscheduled events in one year.
    assert summary["unscheduled_events"] <= 10, (
        f"Too many premature failures: {summary['unscheduled_events']}"
    )

    # For components with multiple failures, MTBF must exceed 50% of scale.
    for comp, mtbf in summary["mtbf_by_component"].items():
        scale = TRUCK_PREMATURE_FAILURE[comp]["scale"]
        assert mtbf >= 0.5 * scale, (
            f"Component '{comp}': MTBF {mtbf:.0f} hrs < 0.5 × scale {scale} hrs"
        )


# ---------------------------------------------------------------------------
# 4. No two events for the same truck overlap in time.
# ---------------------------------------------------------------------------

def test_no_event_overlap(phase1):
    stats, _, _ = phase1
    events = sorted(stats.events, key=lambda e: e["repair_start"])
    for i in range(1, len(events)):
        prev_end = events[i - 1]["repair_end"]
        curr_start = events[i]["repair_start"]
        # Allow tiny float tolerance.
        assert curr_start >= prev_end - 1e-9, (
            f"Event {i} starts at {curr_start:.4f} before event {i-1} ends "
            f"at {prev_end:.4f}"
        )


# ---------------------------------------------------------------------------
# 5. Resources are fully released when the simulation ends.
# ---------------------------------------------------------------------------

def test_resources_released(phase1):
    _, bay, mechanic = phase1
    assert bay.available == _PHASE1_BAYS, (
        f"Bay resource not fully released: available={bay.available}, capacity={_PHASE1_BAYS}"
    )
    assert mechanic.available == _PHASE1_MECHANICS, (
        f"Mechanic resource not fully released: available={mechanic.available}, "
        f"capacity={_PHASE1_MECHANICS}"
    )


# ---------------------------------------------------------------------------
# 6. Time conservation: operating + scheduled_down + unscheduled_down + queue
#    must exactly equal SIM_DURATION (within floating-point tolerance).
# ---------------------------------------------------------------------------

def test_operating_plus_downtime_equals_sim_duration(phase1):
    stats, _, _ = phase1
    total = (
        stats.operating_hours
        + stats.downtime_scheduled
        + stats.downtime_unscheduled
        + stats.queue_time
    )
    assert math.isclose(total, SIM_DURATION, rel_tol=1e-9), (
        f"Time does not balance: {total:.6f} != {SIM_DURATION} "
        f"(delta={abs(total - SIM_DURATION):.2e})"
    )
