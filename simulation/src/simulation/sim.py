"""Simulation entry points for Phase 1, Phase 2, and Phase 3.

Run Phase 3 (trucks + shovels):
    python -m simulation.sim

Run Phase 2 (trucks only, for regression):
    python -c "from simulation.sim import run_phase2; import json; f,_,_ = run_phase2(); print(json.dumps({k:v for k,v in f.summary().items() if k!='per_truck'}, indent=2))"

Run Phase 1 (single truck, for reference/testing):
    python -c "from simulation.sim import run_phase1; import json; s,_,_ = run_phase1(); print(json.dumps(s.summary(), indent=2))"
"""
from __future__ import annotations

import json

import numpy as np

from engine.environment import Environment
from engine.resource import Resource

from .config import N_BAYS, N_MECHANICS, N_SHOVELS, RANDOM_SEED, SHIFT_SCHEDULE, SIM_DURATION
from .fleet import run_fleet
from .shift import ShiftScheduler
from .stats import FleetStats, ShovelStats, TruckStats
from .truck import truck_process

# ── Phase 1: single truck, one bay, one mechanic ──────────────────────────────

_PHASE1_BAYS = 1
_PHASE1_MECHANICS = 1


def run_phase1(
    seed: int = RANDOM_SEED,
) -> tuple[TruckStats, Resource, Resource]:
    """Run a single Phase 1 simulation (1 truck, 1 bay, 1 mechanic, no shifts).

    Returns the TruckStats object and both Resource objects so callers
    (e.g. tests) can inspect final resource state as well as event logs.
    """
    rng = np.random.default_rng(seed)
    env = Environment()
    bay = Resource(capacity=_PHASE1_BAYS)
    mechanic = Resource(capacity=_PHASE1_MECHANICS)
    stats = TruckStats(name="Truck-0")

    env.process(truck_process(env, "Truck-0", bay, mechanic, stats, rng))
    env.run(until=SIM_DURATION)

    return stats, bay, mechanic


# ── Phase 2: full fleet with resource contention and shift scheduling ─────────


def run_phase2(
    seed: int = RANDOM_SEED,
) -> tuple[FleetStats, Resource, Resource]:
    """Run a Phase 2 fleet simulation.

    15 trucks share 4 bays and a shift-scheduled mechanic pool.
    Returns FleetStats and both Resource objects.
    """
    rng = np.random.default_rng(seed)
    env = Environment()
    bay = Resource(capacity=N_BAYS)
    mechanic = Resource(capacity=N_MECHANICS)

    # Start shift scheduler — adjusts mechanic capacity at each phase boundary.
    ShiftScheduler(env, mechanic, SHIFT_SCHEDULE)

    truck_stats, _ = run_fleet(env, bay, mechanic, rng, n_shovels=0)
    fleet = FleetStats(trucks=truck_stats)
    env.run(until=SIM_DURATION)

    return fleet, bay, mechanic


# ── Phase 3: trucks + shovels sharing bays and mechanics ──────────────────────


def run_phase3(
    seed: int = RANDOM_SEED,
) -> tuple[FleetStats, Resource, Resource]:
    """Run a Phase 3 simulation: 15 trucks + 3 shovels, shift-scheduled mechanics.

    Shovels share workshop bays and mechanics with trucks.  Minor shovel PMs
    consume only a mechanic; major overhauls consume both a bay and a mechanic.
    Returns FleetStats (with both .trucks and .shovels populated) and resources.
    """
    rng = np.random.default_rng(seed)
    env = Environment()
    bay = Resource(capacity=N_BAYS)
    mechanic = Resource(capacity=N_MECHANICS)

    ShiftScheduler(env, mechanic, SHIFT_SCHEDULE)

    truck_stats, shovel_stats = run_fleet(env, bay, mechanic, rng, n_shovels=N_SHOVELS)
    fleet = FleetStats(trucks=truck_stats, shovels=shovel_stats)
    env.run(until=SIM_DURATION)

    return fleet, bay, mechanic


if __name__ == "__main__":
    from .export import write_events, write_fleet_summary

    fleet, _bay, _mechanic = run_phase3()
    summary = fleet.summary()
    # Strip nested per-truck/per-shovel lists so the JSON is clean on stdout.
    print(json.dumps(
        {k: v for k, v in summary.items() if k not in ("per_truck", "per_shovel")},
        indent=2,
    ))

    trucks_path = write_fleet_summary(fleet)
    events_path = write_events(fleet)
    print(f"\nCSVs written to:\n  {trucks_path}\n  {events_path}")
