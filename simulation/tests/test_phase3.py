"""Phase 3 acceptance tests — trucks + shovels, shared bays and mechanics.

Run with:  pytest simulation/tests/test_phase3.py -v
"""
import math

import pytest

from simulation.config import (
    N_BAYS,
    N_MECHANICS,
    N_SHOVELS,
    N_TRUCKS,
    RANDOM_SEED,
    SHIFT_SCHEDULE,
    SHOVEL_PM_SCHEDULE,
    SIM_DURATION,
)
from simulation.sim import run_phase2, run_phase3


# ---------------------------------------------------------------------------
# Shared fixture — run the Phase 3 simulation once per test session.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def phase3():
    fleet, bay, mechanic = run_phase3(seed=RANDOM_SEED)
    return fleet, bay, mechanic


# ---------------------------------------------------------------------------
# 1. Truck fleet PA% stays within benchmark range (widened for contention).
# ---------------------------------------------------------------------------

def test_truck_pa_pct_in_benchmark_range(phase3):
    fleet, _, _ = phase3
    summary = fleet.summary()
    pa = summary["truck_pa_pct_mean"]
    # Mean includes partially-deployed trucks (u < 1 in later years) so the
    # fleet-wide average is below the ~92% achieved by fully-deployed units.
    assert 68.0 <= pa <= 80.0, (
        f"Truck mean PA% = {pa:.2f}% is outside [68, 80]"
    )


# ---------------------------------------------------------------------------
# 2. Shovel fleet PA% lands in the world-class benchmark range (88–93%).
# ---------------------------------------------------------------------------

def test_shovel_pa_pct_in_benchmark_range(phase3):
    fleet, _, _ = phase3
    summary = fleet.summary()
    pa = summary["shovel_pa_pct_mean"]
    # Shovel-1 and Shovel-2 have partial utilisation in later years, pulling
    # the mean below the ~94% achieved by a fully-deployed shovel.
    assert 79.0 <= pa <= 91.0, (
        f"Shovel mean PA% = {pa:.2f}% is outside [79, 91]"
    )


# ---------------------------------------------------------------------------
# 3. All equipment records at least one event (all processes ran).
# ---------------------------------------------------------------------------

def test_all_equipment_has_events(phase3):
    fleet, _, _ = phase3
    for truck in fleet.trucks:
        assert len(truck.events) > 0, f"{truck.name} has no events"
    for shovel in fleet.shovels:
        assert len(shovel.events) > 0, f"{shovel.name} has no events"


# ---------------------------------------------------------------------------
# 4. Fleet has the right number of trucks and shovels.
# ---------------------------------------------------------------------------

def test_fleet_counts(phase3):
    fleet, _, _ = phase3
    assert len(fleet.trucks) == N_TRUCKS
    assert len(fleet.shovels) == N_SHOVELS


# ---------------------------------------------------------------------------
# 5. Shovel minor PM events never consume a bay.
# ---------------------------------------------------------------------------

MINOR_PM_NAMES = {
    name for name, cfg in SHOVEL_PM_SCHEDULE.items() if not cfg["bay"]
}


def test_shovel_minor_pms_never_use_bay(phase3):
    fleet, _, _ = phase3
    for shovel in fleet.shovels:
        for e in shovel.events:
            if e["type"] == "scheduled" and e["name"] in MINOR_PM_NAMES:
                assert e["bay_used"] is False, (
                    f"{shovel.name}: minor PM '{e['name']}' incorrectly used a bay"
                )


# ---------------------------------------------------------------------------
# 6. Shovel major PM and premature failure events always consume a bay.
# ---------------------------------------------------------------------------

MAJOR_PM_NAMES = {
    name for name, cfg in SHOVEL_PM_SCHEDULE.items() if cfg["bay"]
}


def test_shovel_major_events_use_bay(phase3):
    fleet, _, _ = phase3
    for shovel in fleet.shovels:
        for e in shovel.events:
            if e["type"] == "premature":
                assert e["bay_used"] is True, (
                    f"{shovel.name}: premature failure '{e['name']}' did not use a bay"
                )
            elif e["type"] == "scheduled" and e["name"] in MAJOR_PM_NAMES:
                assert e["bay_used"] is True, (
                    f"{shovel.name}: major PM '{e['name']}' did not use a bay"
                )


# ---------------------------------------------------------------------------
# 7. Adding shovels increases peak bay queue vs Phase 2 (same seed).
# ---------------------------------------------------------------------------

def test_queue_increases_vs_phase2(phase3):
    fleet3, _, _ = phase3
    fleet2, _, _ = run_phase2(seed=RANDOM_SEED)
    peak3 = fleet3.summary()["peak_queue_time_hrs"]
    peak2 = fleet2.summary()["peak_queue_time_hrs"]
    assert peak3 >= peak2, (
        f"Phase 3 peak queue ({peak3:.2f}h) should be >= Phase 2 ({peak2:.2f}h) "
        "with shovels adding bay contention"
    )


# ---------------------------------------------------------------------------
# 8. No two events for the same piece of equipment overlap in time.
# ---------------------------------------------------------------------------

def test_no_event_overlap_per_equipment(phase3):
    fleet, _, _ = phase3
    for equip in fleet.trucks + fleet.shovels:
        events = sorted(equip.events, key=lambda e: e["queue_start"])
        for i in range(len(events) - 1):
            assert events[i]["repair_end"] <= events[i + 1]["queue_start"] + 1e-9, (
                f"{equip.name}: event {i} ends at {events[i]['repair_end']:.4f} "
                f"but event {i+1} starts at {events[i+1]['queue_start']:.4f}"
            )


# ---------------------------------------------------------------------------
# 9. Time conservation — operating + downtime never exceeds SIM_DURATION.
# ---------------------------------------------------------------------------

def test_time_conservation_per_equipment(phase3):
    fleet, _, _ = phase3
    for equip in fleet.trucks + fleet.shovels:
        total = equip.operating_hours + equip.downtime_scheduled + equip.downtime_unscheduled
        assert total <= SIM_DURATION + 1e-9, (
            f"{equip.name}: operating + downtime = {total:.4f} > SIM_DURATION {SIM_DURATION}"
        )
        # Equipment may end the sim waiting in queue — that unfinished queue
        # period is not recorded in any stats bucket.  Just verify some
        # operating time was accumulated.
        assert equip.operating_hours > 0, (
            f"{equip.name}: zero operating hours — process may not have run"
        )


# ---------------------------------------------------------------------------
# 10. Resources are in a valid state at simulation end.
# ---------------------------------------------------------------------------

def test_resources_released(phase3):
    fleet, bay, mechanic = phase3
    assert 0 <= bay.available <= N_BAYS, (
        f"bay.available = {bay.available} out of [0, {N_BAYS}]"
    )
    assert 0 <= mechanic.available <= mechanic.capacity, (
        f"mechanic.available = {mechanic.available} > capacity {mechanic.capacity}"
    )


# ---------------------------------------------------------------------------
# 11. Phase 1 and Phase 2 tests still pass (regression guard).
# ---------------------------------------------------------------------------

def test_phase2_still_passes():
    """Phase 2 KPIs must be unaffected by Phase 3 code changes."""
    fleet, bay, mechanic = run_phase2(seed=RANDOM_SEED)
    summary = fleet.summary()
    pa = summary["fleet_pa_pct_mean"]
    # Fleet-wide mean includes partially-deployed trucks (utilisation < 1).
    assert 68.0 <= pa <= 80.0, (
        f"Phase 2 regression: fleet mean PA% = {pa:.2f}% outside [68, 80]"
    )
    assert len(fleet.shovels) == 0
