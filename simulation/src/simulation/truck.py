"""Truck process generator for the mining fleet availability simulation.

The generator runs for the full simulation duration, looping through:
  operating → request resources → repair/PM → release resources → repeat.

PM superseding: when multiple PMs are simultaneously due (e.g. PM-A, PM-B,
and PM-C all fall on the 1,000-hr threshold), the highest-interval PM is
used as the primary event and all due PMs' clocks are advanced. This prevents
double-counting of downtime for services that subsume lower-level tasks.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from .config import (
    OPP_WINDOW_HRS,
    SIM_DURATION,
    TRUCK_PM_SCHEDULE,
    TRUCK_PREMATURE_FAILURE,
)

if TYPE_CHECKING:
    from engine.environment import Environment
    from engine.resource import Resource

    from .stats import TruckStats


def truck_process(
    env: "Environment",
    name: str,
    bay_resource: "Resource",
    mechanic_resource: "Resource",
    stats: "TruckStats",
    rng: np.random.Generator,
    *,
    pm_offsets: dict[str, float] | None = None,
):
    """Generator process for a single haul truck.

    Yields timeouts and resource requests to the simulation environment.
    Writes KPI data directly into *stats*.

    pm_offsets: optional dict mapping PM name → initial due threshold in
    cumulative operating hours.  Defaults to one full interval for each PM
    (Phase 1 behaviour).  Pass randomised offsets via run_fleet() to stagger
    trucks so they don't all arrive at the workshop simultaneously.
    """
    cum_op_hrs: float = 0.0

    # Next due threshold in cumulative operating hours for each PM.
    if pm_offsets is not None:
        pm_due: dict[str, float] = {pname: float(pm_offsets[pname]) for pname in TRUCK_PM_SCHEDULE}
    else:
        pm_due: dict[str, float] = {
            pname: float(cfg["interval"])
            for pname, cfg in TRUCK_PM_SCHEDULE.items()
        }

    while True:
        # ── Find the next PM threshold ────────────────────────────────────
        next_threshold = min(pm_due.values())
        time_to_next_pm = next_threshold - cum_op_hrs

        # All PMs whose due threshold coincides with next_threshold.
        due_pms = [n for n, due in pm_due.items() if due == next_threshold]

        # Primary PM: the one with the longest interval (subsumes shorter ones).
        primary_pm = max(due_pms, key=lambda n: TRUCK_PM_SCHEDULE[n]["interval"])
        # Duration PM: the one with the longest mean duration among concurrent
        # PMs — the combined workshop visit takes as long as the biggest job.
        duration_pm = max(due_pms, key=lambda n: TRUCK_PM_SCHEDULE[n]["duration_mean"])

        # ── Draw Weibull TTF for every component ──────────────────────────
        # Each draw models the remaining life of the component in this
        # operating leg. If TTF < time_to_next_pm the component fails early.
        comp_ttf: dict[str, float] = {
            comp: float(cfg["scale"]) * float(rng.weibull(cfg["shape"]))
            for comp, cfg in TRUCK_PREMATURE_FAILURE.items()
        }
        min_comp = min(comp_ttf, key=comp_ttf.__getitem__)
        min_ttf = comp_ttf[min_comp]

        # ── Decide which event fires first ────────────────────────────────
        if min_ttf < time_to_next_pm:
            if min_ttf >= time_to_next_pm - OPP_WINDOW_HRS:
                # Premature failure within the opportunistic window:
                # pull the PM forward; combine both into one shop visit.
                op_interval = time_to_next_pm
                event_type = "opportunistic"
                event_name = primary_pm      # PM name used for duration lookup
                failed_comp = min_comp
            else:
                op_interval = min_ttf
                event_type = "premature"
                event_name = min_comp
                failed_comp = min_comp
        else:
            op_interval = time_to_next_pm
            event_type = "scheduled"
            event_name = primary_pm
            failed_comp = None

        # ── Cap operating leg at simulation end ───────────────────────────
        remaining_sim = SIM_DURATION - env.now
        if op_interval >= remaining_sim:
            stats.operating_hours += remaining_sim
            yield env.timeout(remaining_sim)
            break

        # ── Operate ───────────────────────────────────────────────────────
        op_start = env.now
        yield env.timeout(op_interval)
        stats.operating_hours += op_interval
        cum_op_hrs += op_interval

        # ── Request workshop bay and mechanic ─────────────────────────────
        queue_start = env.now
        req_bay = bay_resource.request()
        with (yield req_bay):
            req_mech = mechanic_resource.request()
            with (yield req_mech):
                queue_time = env.now - queue_start
                stats.queue_time += queue_time

                # ── Sample event duration ─────────────────────────────────
                if event_type == "premature":
                    cfg = TRUCK_PREMATURE_FAILURE[event_name]
                    dur = max(0.5, float(rng.normal(cfg["repair_mean"], cfg["repair_sd"])))
                else:
                    # scheduled or opportunistic — use the longest concurrent PM duration
                    cfg = TRUCK_PM_SCHEDULE[duration_pm]
                    dur = max(0.5, float(rng.normal(cfg["duration_mean"], cfg["duration_sd"])))

                repair_start = env.now

                # Clamp to remaining simulation time BEFORE booking stats so
                # downtime never overshoots SIM_DURATION.
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
            # All PMs that were simultaneously due get their clocks advanced.
            for pname in due_pms:
                pm_due[pname] = next_threshold + TRUCK_PM_SCHEDULE[pname]["interval"]
        # For a pure premature failure the PM clocks are unchanged — the
        # truck will reach the next PM threshold on its next operating leg.
