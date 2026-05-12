"""CSV export helpers for simulation output KPIs."""
from __future__ import annotations

import csv
import os
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .stats import FleetStats, TruckStats

from .config import SIM_DURATION, SIM_START


def _sim_hours_to_dt(hours: float) -> str:
    """Convert simulation hours offset to an ISO-8601 UTC datetime string."""
    return (SIM_START + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def write_fleet_summary(
    fleet_stats: FleetStats,
    path: str | os.PathLike = "output/fleet_summary.csv",
    sim_duration: float = SIM_DURATION,
) -> Path:
    """Write one row per piece of equipment (trucks and shovels) with KPI columns.

    Columns: equipment, equipment_type, pa_pct, operating_hours,
    downtime_scheduled, downtime_unscheduled, queue_time, total_events,
    scheduled_events, unscheduled_events, opportunistic_events,
    mean_queue_time_hrs
    """
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "equipment",
        "equipment_type",
        "pa_pct",
        "operating_hours",
        "downtime_scheduled",
        "downtime_unscheduled",
        "queue_time",
        "total_events",
        "scheduled_events",
        "unscheduled_events",
        "opportunistic_events",
        "mean_queue_time_hrs",
    ]

    all_equipment = [
        (equip, "truck") for equip in fleet_stats.trucks
    ] + [
        (equip, "shovel") for equip in fleet_stats.shovels
    ]

    with dest.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for equip, equip_type in all_equipment:
            s = equip.summary(sim_duration)
            writer.writerow(
                {
                    "equipment": equip.name,
                    "equipment_type": equip_type,
                    "pa_pct": round(s["pa_pct"], 4),
                    "operating_hours": round(s["operating_hours"], 4),
                    "downtime_scheduled": round(s["downtime_scheduled"], 4),
                    "downtime_unscheduled": round(s["downtime_unscheduled"], 4),
                    "queue_time": round(s["queue_time"], 4),
                    "total_events": s["total_events"],
                    "scheduled_events": s["scheduled_events"],
                    "unscheduled_events": s["unscheduled_events"],
                    "opportunistic_events": s["opportunistic_events"],
                    "mean_queue_time_hrs": round(s["mean_queue_time_hrs"], 4),
                }
            )

    return dest


# Backward-compatible alias used by any existing callers.
write_truck_summary = write_fleet_summary


def write_events(
    fleet_stats: FleetStats,
    path: str | os.PathLike = "output/events.csv",
) -> Path:
    """Write one row per maintenance event across all trucks and shovels.

    Columns: equipment, equipment_type, sim_time, event_type, name, all_pms,
    bay_used, cum_op_hrs, op_start, queue_start, repair_start, repair_end,
    duration, queue_time

    sim_time is the ISO-8601 UTC datetime when the event triggered.
    bay_used is True for all truck events and for shovel major events.
    """
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "equipment",
        "equipment_type",
        "sim_time",
        "event_type",
        "activity_group",
        "name",
        "all_pms",
        "bay_used",
        "cum_op_hrs",
        "op_start",
        "queue_start",
        "repair_start",
        "repair_end",
        "duration",
        "queue_time",
    ]

    all_equipment = [
        (equip, "truck") for equip in fleet_stats.trucks
    ] + [
        (equip, "shovel") for equip in fleet_stats.shovels
    ]

    with dest.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for equip, equip_type in all_equipment:
            for e in equip.events:
                writer.writerow(
                    {
                        "equipment": equip.name,
                        "equipment_type": equip_type,
                        "sim_time": _sim_hours_to_dt(e["queue_start"]),
                        "event_type": e["type"],
                        "activity_group": e.get("activity_group", ""),
                        "name": e["name"],
                        "all_pms": "|".join(e.get("all_pms", [])),
                        # Trucks always use a bay; shovels record bay_used explicitly.
                        "bay_used": e.get("bay_used", True),
                        "cum_op_hrs": round(e["cum_op_hrs"], 4),
                        "op_start": round(e["op_start"], 4),
                        "queue_start": round(e["queue_start"], 4),
                        "repair_start": round(e["repair_start"], 4),
                        "repair_end": round(e["repair_end"], 4),
                        "duration": round(e["duration"], 4),
                        "queue_time": round(e["queue_time"], 4),
                    }
                )

    return dest
