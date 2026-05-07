"""Shovel process generator for the mining fleet availability simulation.

Mirrors truck_process with one key difference: the ``bay`` flag in each
PM/failure config determines whether a workshop bay is required. Minor shovel
PMs (daily_inspect, PM_A, PM_B, GET_replace, pin_service) are performed
on-site and consume only a mechanic. Major overhauls and all unscheduled
repairs require both a bay and a mechanic.

PM superseding behaviour is identical to trucks: concurrent PMs are collapsed
into a single workshop visit whose duration equals the longest individual job.
The bay flag for a combined visit is True if *any* concurrent PM requires a bay.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from .config import (
    OPP_WINDOW_HRS,
    SHOVEL_PM_SCHEDULE,
    SHOVEL_PREMATURE_FAILURE,
    SIM_DURATION,
)
from .utilisation import op_hours_to_sim_delta, sim_delta_to_op_hours

if TYPE_CHECKING:
    from engine.environment import Environment
    from engine.resource import Resource

    from .stats import ShovelStats


def shovel_process(
    env: "Environment",
    name: str,
    bay_resource: "Resource",
    mechanic_resource: "Resource",
    stats: "ShovelStats",
    rng: np.random.Generator,
    *,
    pm_offsets: dict[str, float] | None = None,
):
    """Generator process for a single hydraulic mining shovel.

    Yields timeouts and resource requests to the simulation environment.
    Writes KPI data directly into *stats*.

    pm_offsets: optional dict mapping PM name → initial due threshold in
    cumulative operating hours.  Pass randomised offsets via run_fleet() to
    stagger shovels so they don't all arrive at the workshop simultaneously.
    """
    cum_op_hrs: float = 0.0

    if pm_offsets is not None:
        pm_due: dict[str, float] = {pname: float(pm_offsets[pname]) for pname in SHOVEL_PM_SCHEDULE}
    else:
        pm_due: dict[str, float] = {
            pname: float(cfg["interval"])
            for pname, cfg in SHOVEL_PM_SCHEDULE.items()
        }

    while True:
        # ── Find the next PM threshold ────────────────────────────────────
        next_threshold = min(pm_due.values())
        time_to_next_pm = next_threshold - cum_op_hrs

        due_pms = [n for n, due in pm_due.items() if due == next_threshold]

        primary_pm = max(due_pms, key=lambda n: SHOVEL_PM_SCHEDULE[n]["interval"])
        duration_pm = max(due_pms, key=lambda n: SHOVEL_PM_SCHEDULE[n]["duration_mean"])

        # ── Draw Weibull TTF for every component ──────────────────────────
        comp_ttf: dict[str, float] = {
            comp: float(cfg["scale"]) * float(rng.weibull(cfg["shape"]))
            for comp, cfg in SHOVEL_PREMATURE_FAILURE.items()
        }
        min_comp = min(comp_ttf, key=comp_ttf.__getitem__)
        min_ttf = comp_ttf[min_comp]

        # ── Decide which event fires first ────────────────────────────────
        if min_ttf < time_to_next_pm:
            if min_ttf >= time_to_next_pm - OPP_WINDOW_HRS:
                op_interval = time_to_next_pm
                event_type = "opportunistic"
                event_name = primary_pm
                failed_comp = min_comp
                needs_bay = True  # premature failure always requires a bay
            else:
                op_interval = min_ttf
                event_type = "premature"
                event_name = min_comp
                failed_comp = min_comp
                needs_bay = True  # all premature failures require a bay
        else:
            op_interval = time_to_next_pm
            event_type = "scheduled"
            event_name = primary_pm
            failed_comp = None
            # Bay required if any concurrent PM requires one.
            needs_bay = any(SHOVEL_PM_SCHEDULE[p]["bay"] for p in due_pms)

        # ── Cap operating leg at simulation end ───────────────────────────
        # Convert operating-hours to sim-time (accounts for utilisation < 1).
        sim_delta = op_hours_to_sim_delta(name, env.now, op_interval)
        remaining_sim = SIM_DURATION - env.now
        if sim_delta >= remaining_sim:
            stats.operating_hours += sim_delta_to_op_hours(name, env.now, remaining_sim)
            yield env.timeout(remaining_sim)
            break

        # ── Operate ───────────────────────────────────────────────────────
        op_start = env.now
        yield env.timeout(sim_delta)
        stats.operating_hours += op_interval
        cum_op_hrs += op_interval

        # ── Request resources ──────────────────────────────────────────────
        queue_start = env.now

        if needs_bay:
            req_bay = bay_resource.request()
            with (yield req_bay):
                req_mech = mechanic_resource.request()
                with (yield req_mech):
                    queue_time = env.now - queue_start
                    stats.queue_time += queue_time

                    if event_type == "premature":
                        cfg = SHOVEL_PREMATURE_FAILURE[event_name]
                        dur = max(0.5, float(rng.normal(cfg["repair_mean"], cfg["repair_sd"])))
                    else:
                        cfg = SHOVEL_PM_SCHEDULE[duration_pm]
                        dur = max(0.5, float(rng.normal(cfg["duration_mean"], cfg["duration_sd"])))

                    repair_start = env.now
                    dur = min(dur, max(0.0, SIM_DURATION - env.now))

                    if event_type == "premature":
                        stats.downtime_unscheduled += dur
                    else:
                        stats.downtime_scheduled += dur

                    yield env.timeout(dur)
                    repair_end = env.now

                    stats.events.append({
                        "type": event_type,
                        "name": event_name,
                        "failed_comp": failed_comp,
                        "all_pms": due_pms if event_type in ("scheduled", "opportunistic") else [],
                        "bay_used": True,
                        "cum_op_hrs": cum_op_hrs,
                        "op_start": op_start,
                        "queue_start": queue_start,
                        "repair_start": repair_start,
                        "repair_end": repair_end,
                        "duration": dur,
                        "queue_time": queue_time,
                    })
        else:
            # Minor PM — mechanic only, no bay required.
            req_mech = mechanic_resource.request()
            with (yield req_mech):
                queue_time = env.now - queue_start
                stats.queue_time += queue_time

                cfg = SHOVEL_PM_SCHEDULE[duration_pm]
                dur = max(0.5, float(rng.normal(cfg["duration_mean"], cfg["duration_sd"])))

                repair_start = env.now
                dur = min(dur, max(0.0, SIM_DURATION - env.now))

                stats.downtime_scheduled += dur

                yield env.timeout(dur)
                repair_end = env.now

                stats.events.append({
                    "type": event_type,
                    "name": event_name,
                    "failed_comp": failed_comp,
                    "all_pms": due_pms,
                    "bay_used": False,
                    "cum_op_hrs": cum_op_hrs,
                    "op_start": op_start,
                    "queue_start": queue_start,
                    "repair_start": repair_start,
                    "repair_end": repair_end,
                    "duration": dur,
                    "queue_time": queue_time,
                })

        # ── Advance PM clocks ─────────────────────────────────────────────
        if event_type in ("scheduled", "opportunistic"):
            for pname in due_pms:
                pm_due[pname] = next_threshold + SHOVEL_PM_SCHEDULE[pname]["interval"]
