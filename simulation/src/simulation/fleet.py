"""Fleet spawner for Phase 2 / Phase 3 — trucks and shovels sharing resources."""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from .config import N_SHOVELS, N_TRUCKS, SHOVEL_PM_SCHEDULE, TRUCK_PM_SCHEDULE
from .shovel import shovel_process
from .stats import ShovelStats, TruckStats
from .truck import truck_process

if TYPE_CHECKING:
    from engine.environment import Environment
    from engine.resource import Resource


def _stagger(pm_schedule: dict, rng: np.random.Generator) -> dict[str, float]:
    """Draw randomised initial PM thresholds, staggered within (0, interval].

    Using (interval * 0.05, interval] (exclusive near-zero) avoids a PM
    firing at simulation t=0.
    """
    return {
        pname: float(rng.uniform(cfg["interval"] * 0.05, cfg["interval"]))
        for pname, cfg in pm_schedule.items()
    }


def run_fleet(
    env: "Environment",
    bay: "Resource",
    mechanic: "Resource",
    rng: np.random.Generator,
    n_trucks: int = N_TRUCKS,
    n_shovels: int = N_SHOVELS,
) -> tuple[list[TruckStats], list[ShovelStats]]:
    """Spawn truck and shovel processes sharing *bay* and *mechanic*.

    Each piece of equipment receives an independent child RNG derived from
    the master so results are independent but fully reproducible from a
    single seed.  PM clocks are staggered so all equipment doesn't arrive
    at the workshop simultaneously on day one.

    Returns a (truck_stats, shovel_stats) tuple. Either list may be empty
    when the corresponding count is zero.
    """
    truck_stats: list[TruckStats] = []
    for i in range(n_trucks):
        truck_rng = np.random.default_rng(rng.integers(0, 2**32))
        pm_offsets = _stagger(TRUCK_PM_SCHEDULE, truck_rng)
        stats = TruckStats(name=f"Truck-{i}")
        truck_stats.append(stats)
        env.process(
            truck_process(
                env, f"Truck-{i}", bay, mechanic, stats, truck_rng,
                pm_offsets=pm_offsets,
            )
        )

    shovel_stats: list[ShovelStats] = []
    for i in range(n_shovels):
        shovel_rng = np.random.default_rng(rng.integers(0, 2**32))
        pm_offsets = _stagger(SHOVEL_PM_SCHEDULE, shovel_rng)
        stats = ShovelStats(name=f"Shovel-{i}")
        shovel_stats.append(stats)
        env.process(
            shovel_process(
                env, f"Shovel-{i}", bay, mechanic, stats, shovel_rng,
                pm_offsets=pm_offsets,
            )
        )

    return truck_stats, shovel_stats
