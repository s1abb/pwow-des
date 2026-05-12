"""Fleet spawner for Phase 2 / Phase 3 — trucks and shovels sharing resources."""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from .config import (
    N_FLEET,
    PREMATURE_FAILURE,
    SHOVEL_PM_SCHEDULE,
    TRUCK_PM_SCHEDULE,
    USE_FITTED_PARAMS,
    _SHOVEL_MODELS,
    _TRUCK_MODELS,
)
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
) -> tuple[list[TruckStats], list[ShovelStats]]:
    """Spawn truck and shovel processes sharing *bay* and *mechanic*.

    Each piece of equipment receives an independent child RNG derived from
    the master so results are independent but fully reproducible from a
    single seed.  PM clocks are staggered so all equipment doesn't arrive
    at the workshop simultaneously on day one.

    Processes are spawned model-by-model so each unit draws TTFs from its
    own fitted Weibull parameters.

    Returns a (truck_stats, shovel_stats) tuple.
    """
    truck_stats: list[TruckStats] = []
    # When using fitted params the Weibull preventive TTFs replace the
    # hardcoded PM schedule entirely; pass an empty dict to suppress it.
    truck_pm = {} if USE_FITTED_PARAMS else TRUCK_PM_SCHEDULE
    shovel_pm = {} if USE_FITTED_PARAMS else SHOVEL_PM_SCHEDULE
    unit = 0
    for model in _TRUCK_MODELS:
        for _ in range(N_FLEET[model]):
            truck_rng = np.random.default_rng(rng.integers(0, 2**32))
            pm_offsets = _stagger(truck_pm, truck_rng)
            name = f"Truck-{unit}({model})"
            stats = TruckStats(name=name)
            truck_stats.append(stats)
            env.process(
                truck_process(
                    env, name, bay, mechanic, stats, truck_rng,
                    pm_offsets=pm_offsets,
                    failure_cfg=PREMATURE_FAILURE[model],
                    pm_schedule=truck_pm,
                )
            )
            unit += 1

    shovel_stats: list[ShovelStats] = []
    unit = 0
    for model in _SHOVEL_MODELS:
        for _ in range(N_FLEET[model]):
            shovel_rng = np.random.default_rng(rng.integers(0, 2**32))
            pm_offsets = _stagger(shovel_pm, shovel_rng)
            name = f"Shovel-{unit}({model})"
            stats = ShovelStats(name=name)
            shovel_stats.append(stats)
            env.process(
                shovel_process(
                    env, name, bay, mechanic, stats, shovel_rng,
                    pm_offsets=pm_offsets,
                    failure_cfg=PREMATURE_FAILURE[model],
                    pm_schedule=shovel_pm,
                )
            )
            unit += 1

    return truck_stats, shovel_stats
