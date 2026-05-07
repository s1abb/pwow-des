"""Fleet spawner for Phase 2 — multiple trucks sharing resources."""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from .config import N_TRUCKS, TRUCK_PM_SCHEDULE
from .stats import TruckStats
from .truck import truck_process

if TYPE_CHECKING:
    from engine.environment import Environment
    from engine.resource import Resource


def run_fleet(
    env: "Environment",
    bay: "Resource",
    mechanic: "Resource",
    rng: np.random.Generator,
    n_trucks: int = N_TRUCKS,
) -> list[TruckStats]:
    """Spawn *n_trucks* truck processes sharing *bay* and *mechanic*.

    Each truck receives an independent child RNG derived from the master so
    results are independent but fully reproducible from a single seed.

    PM clocks are randomised within the first interval for each PM so trucks
    don't all arrive at the workshop simultaneously on day one.  The offset is
    drawn uniformly from [0, interval), meaning the first PM fires somewhere
    in the first full interval.
    """
    fleet_stats: list[TruckStats] = []

    for i in range(n_trucks):
        # Independent child RNG per truck.
        truck_rng = np.random.default_rng(rng.integers(0, 2**32))

        # Staggered initial PM thresholds: uniform draw in (0, interval].
        # Using (0, interval] (exclusive 0) avoids a PM firing at t=0.
        pm_offsets = {
            pname: float(truck_rng.uniform(cfg["interval"] * 0.05, cfg["interval"]))
            for pname, cfg in TRUCK_PM_SCHEDULE.items()
        }

        stats = TruckStats(name=f"Truck-{i}")
        fleet_stats.append(stats)
        env.process(
            truck_process(
                env,
                f"Truck-{i}",
                bay,
                mechanic,
                stats,
                truck_rng,
                pm_offsets=pm_offsets,
            )
        )

    return fleet_stats
