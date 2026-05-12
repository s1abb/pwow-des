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
    AG_REQUIRES_BAY,
    OPP_WINDOW_HRS,
    PREMATURE_FAILURE,
    SIM_DURATION,
    TRUCK_PM_SCHEDULE,
)
from .utilisation import op_hours_to_sim_delta, sim_delta_to_op_hours

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
    failure_cfg: dict | None = None,
    pm_schedule: dict | None = None,
):
    """Generator process for a single haul truck.

    Yields timeouts and resource requests to the simulation environment.
    Writes KPI data directly into *stats*.

    pm_offsets: optional dict mapping PM name → initial due threshold in
    cumulative operating hours.  Defaults to one full interval for each PM
    (Phase 1 behaviour).  Pass randomised offsets via run_fleet() to stagger
    trucks so they don't all arrive at the workshop simultaneously.

    failure_cfg: activity-group keyed premature failure parameters for this
    unit's model.  Defaults to Cat_793F if not supplied (Phase 1 / direct calls).
    """
    if failure_cfg is None:
        failure_cfg = PREMATURE_FAILURE["Cat_793F"]
    if pm_schedule is None:
        pm_schedule = TRUCK_PM_SCHEDULE
    cum_op_hrs: float = 0.0

    # Next due threshold in cumulative operating hours for each PM.
    if pm_offsets is not None:
        pm_due: dict[str, float] = {pname: float(pm_offsets[pname]) for pname in pm_schedule}
    else:
        pm_due: dict[str, float] = {
            pname: float(cfg["interval"])
            for pname, cfg in pm_schedule.items()
        }

    while True:
        # ── Find the next PM threshold ────────────────────────────────────
        if pm_due:
            next_threshold = min(pm_due.values())
            time_to_next_pm = next_threshold - cum_op_hrs
            # All PMs whose due threshold coincides with next_threshold.
            due_pms = [n for n, due in pm_due.items() if due == next_threshold]
            # Primary PM: the one with the longest interval (subsumes shorter ones).
            primary_pm = max(due_pms, key=lambda n: pm_schedule[n]["interval"])
            # Duration PM: the one with the longest mean duration among concurrent
            # PMs — the combined workshop visit takes as long as the biggest job.
            duration_pm = max(due_pms, key=lambda n: pm_schedule[n]["duration_mean"])
        else:
            # No PM schedule — all events come from Weibull TTF draws.
            time_to_next_pm = float("inf")
            due_pms = []
            primary_pm = None
            duration_pm = None

        # ── Draw Weibull TTF for every activity group ────────────────────
        # Each draw models the remaining life in this operating leg.
        # If TTF < time_to_next_pm the unit fails early.
        ag_ttf: dict[str, float] = {
            ag: float(cfg["scale"]) * float(rng.weibull(cfg["shape"]))
            for ag, cfg in failure_cfg.items()
        }
        failed_ag = min(ag_ttf, key=ag_ttf.__getitem__)
        min_ttf = ag_ttf[failed_ag]

        # ── Decide which event fires first ────────────────────────────────
        if min_ttf < time_to_next_pm:
            if pm_due and min_ttf >= time_to_next_pm - OPP_WINDOW_HRS:
                # Premature failure within the opportunistic window:
                # pull the PM forward; combine both into one shop visit.
                op_interval = time_to_next_pm
                event_type = "opportunistic"
                event_name = primary_pm      # PM name used for duration lookup
                failed_ag = failed_ag
                dur_from_ttf = False
            else:
                op_interval = min_ttf
                # p_* prefix → preventive TTF (counts as scheduled downtime)
                event_type = "scheduled" if failed_ag.startswith("p_") else "premature"
                event_name = failed_ag
                dur_from_ttf = True
        else:
            op_interval = time_to_next_pm
            event_type = "scheduled"
            event_name = primary_pm
            failed_ag = None
            dur_from_ttf = False

        # Bay required?  Default-mode PMs always use a bay.  Fitted TTF events
        # consult AG_REQUIRES_BAY; opportunistic combines failure + PM → bay.
        if dur_from_ttf:
            needs_bay = AG_REQUIRES_BAY.get(event_name, True)
        else:
            needs_bay = True

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

                    if dur_from_ttf:
                        cfg = failure_cfg[event_name]
                        dur = max(0.5, float(rng.normal(cfg["repair_mean"], cfg["repair_sd"])))
                    else:
                        cfg = pm_schedule[duration_pm]
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
                        "activity_group": failed_ag,
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
            # Field / on-machine work — mechanic only, no bay required.
            req_mech = mechanic_resource.request()
            with (yield req_mech):
                queue_time = env.now - queue_start
                stats.queue_time += queue_time

                cfg = failure_cfg[event_name]
                dur = max(0.5, float(rng.normal(cfg["repair_mean"], cfg["repair_sd"])))

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
                    "activity_group": failed_ag,
                    "all_pms": [],
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
        # Fitted events (dur_from_ttf=True) have due_pms=[] so this loop is a no-op.
        if event_type in ("scheduled", "opportunistic"):
            for pname in due_pms:
                pm_due[pname] = next_threshold + pm_schedule[pname]["interval"]
        # For a pure premature failure the PM clocks are unchanged — the
        # truck will reach the next PM threshold on its next operating leg.
