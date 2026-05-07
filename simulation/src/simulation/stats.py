from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from statistics import mean
from typing import Any

from .config import SIM_DURATION


@dataclass
class TruckStats:
    name: str
    operating_hours: float = 0.0
    downtime_scheduled: float = 0.0
    downtime_unscheduled: float = 0.0
    queue_time: float = 0.0
    events: list[dict[str, Any]] = field(default_factory=list)
    # Each event dict contains:
    #   type          : "scheduled" | "premature" | "opportunistic"
    #   name          : PM key (scheduled/opportunistic) or component key (premature)
    #   all_pms       : list of PM keys that fired together (empty for premature)
    #   cum_op_hrs    : cumulative operating hours at the moment this event fired
    #   op_start      : env.now at start of the preceding operating leg
    #   queue_start   : env.now when resource request was issued
    #   repair_start  : env.now when both resources were acquired (work begins)
    #   repair_end    : env.now when repair/PM finished
    #   duration      : actual repair/PM duration in hours
    #   queue_time    : hours spent waiting for resources

    def summary(self, sim_duration: float = SIM_DURATION) -> dict[str, Any]:
        scheduled = [e for e in self.events if e["type"] == "scheduled"]
        unscheduled = [e for e in self.events if e["type"] == "premature"]
        opportunistic = [e for e in self.events if e["type"] == "opportunistic"]
        total_events = len(self.events)

        mean_queue = self.queue_time / total_events if total_events > 0 else 0.0

        # MTBF per component — computed from successive premature failure times
        comp_op_hrs: dict[str, list[float]] = defaultdict(list)
        last_failure_op: dict[str, float] = {}
        for e in self.events:
            if e["type"] == "premature":
                comp = e["name"]
                if comp in last_failure_op:
                    comp_op_hrs[comp].append(e["cum_op_hrs"] - last_failure_op[comp])
                last_failure_op[comp] = e["cum_op_hrs"]
        mtbf = {
            comp: sum(intervals) / len(intervals)
            for comp, intervals in comp_op_hrs.items()
            if intervals
        }

        # MTTR per event type
        mttr: dict[str, float] = {}
        for etype, evs in [
            ("scheduled", scheduled),
            ("premature", unscheduled),
            ("opportunistic", opportunistic),
        ]:
            if evs:
                mttr[etype] = sum(e["duration"] for e in evs) / len(evs)

        return {
            "pa_pct": self.operating_hours / sim_duration * 100,
            "operating_hours": self.operating_hours,
            "downtime_scheduled": self.downtime_scheduled,
            "downtime_unscheduled": self.downtime_unscheduled,
            "queue_time": self.queue_time,
            "total_events": total_events,
            "scheduled_events": len(scheduled),
            "unscheduled_events": len(unscheduled),
            "opportunistic_events": len(opportunistic),
            "mean_queue_time_hrs": mean_queue,
            "mtbf_by_component": mtbf,
            "mttr_by_event_type": mttr,
        }


@dataclass
class FleetStats:
    """Aggregates per-truck KPIs into fleet-level summary statistics."""

    trucks: list[TruckStats]

    def summary(self, sim_duration: float = SIM_DURATION) -> dict[str, Any]:
        per_truck = [t.summary(sim_duration) for t in self.trucks]
        pa_values = [s["pa_pct"] for s in per_truck]
        all_events = [e for t in self.trucks for e in t.events]

        return {
            "fleet_pa_pct_mean": mean(pa_values),
            "fleet_pa_pct_min": min(pa_values),
            "fleet_pa_pct_max": max(pa_values),
            "total_scheduled_events": sum(s["scheduled_events"] for s in per_truck),
            "total_unscheduled_events": sum(s["unscheduled_events"] for s in per_truck),
            "total_opportunistic_events": sum(s["opportunistic_events"] for s in per_truck),
            "mean_queue_time_hrs": mean(s["mean_queue_time_hrs"] for s in per_truck),
            "peak_queue_time_hrs": max((e["queue_time"] for e in all_events), default=0.0),
            "per_truck": per_truck,
        }
