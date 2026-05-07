"""Utilisation schedule helpers.

Converts between operating-hours and simulation-time (wall-clock hours) using
a piecewise-constant per-equipment utilisation factor that varies by calendar
year.

A utilisation factor ``u`` for a given year means::

    op_hours = sim_hours * u

So 1 sim-hour yields ``u`` operating hours.  Equipment with ``u < 1``
accumulates PM-clock hours more slowly, reflecting reduced deployment.  With
``u = 0`` the equipment is fully stood-down for the year and no PM hours
accumulate.

If a piece of equipment has no entry in :data:`~simulation.config.UTILISATION`
its utilisation is treated as 1.0 for all years (no change to existing
behaviour).
"""
from __future__ import annotations

from datetime import datetime, timezone

from .config import SIM_DURATION, SIM_START, UTILISATION


# ---------------------------------------------------------------------------
# Year-boundary cache (sim-time hours at 1 Jan of each calendar year)
# ---------------------------------------------------------------------------

def _build_year_starts() -> dict[int, float]:
    starts: dict[int, float] = {}
    for year in range(SIM_START.year, SIM_START.year + 30):
        dt = datetime(year, 1, 1, tzinfo=timezone.utc)
        starts[year] = (dt - SIM_START).total_seconds() / 3600.0
    return starts


_YEAR_STARTS: dict[int, float] = _build_year_starts()
_SORTED_YEARS: list[int] = sorted(_YEAR_STARTS)


def _sim_time_to_year(sim_now: float) -> int:
    """Return the calendar year that contains sim-time *sim_now*."""
    year = _SORTED_YEARS[0]
    for y in _SORTED_YEARS:
        if _YEAR_STARTS[y] <= sim_now:
            year = y
        else:
            break
    return year


def _year_end(year: int) -> float:
    """Return the sim-time (hours) at the start of *year + 1*."""
    return _YEAR_STARTS[year + 1]


# ---------------------------------------------------------------------------
# Public conversion helpers
# ---------------------------------------------------------------------------

def op_hours_to_sim_delta(name: str, sim_now: float, op_hours: float) -> float:
    """Convert *op_hours* of operating time to elapsed sim-time.

    Starts the integration at *sim_now* and integrates the piecewise-constant
    utilisation schedule across year boundaries.  If the equipment has no
    entry in :data:`UTILISATION` the result equals *op_hours* (1:1).

    When utilisation is 0 for a year the equipment idles through it; the
    returned delta will overshoot ``SIM_DURATION`` so the caller's cap logic
    naturally terminates the process.
    """
    u_schedule = UTILISATION.get(name)
    if not u_schedule:
        return op_hours

    remaining = op_hours
    t = sim_now

    while remaining > 1e-9:
        year = _sim_time_to_year(t)
        u = u_schedule.get(year, 1.0)
        year_end = _year_end(year)

        if u <= 0.0:
            # Idle year — skip forward.  If already past SIM_DURATION, signal
            # with a large value so the caller's cap terminates the process.
            if year_end >= SIM_DURATION:
                return SIM_DURATION - sim_now + 1e9
            t = year_end
            continue

        sim_avail = year_end - t
        op_avail = sim_avail * u

        if remaining <= op_avail + 1e-9:
            t += remaining / u
            remaining = 0.0
        else:
            remaining -= op_avail
            t = year_end

    return t - sim_now


def sim_delta_to_op_hours(name: str, sim_now: float, sim_delta: float) -> float:
    """Convert elapsed sim-time *sim_delta* to operating hours.

    Inverse of :func:`op_hours_to_sim_delta`.  Integrates utilisation across
    year boundaries so the correct number of operating hours is credited even
    when the period spans a year with a different utilisation factor.
    """
    u_schedule = UTILISATION.get(name)
    if not u_schedule:
        return sim_delta

    op_hours = 0.0
    t = sim_now
    remaining_sim = sim_delta

    while remaining_sim > 1e-9:
        year = _sim_time_to_year(t)
        u = u_schedule.get(year, 1.0)
        year_end = _year_end(year)

        sim_in_year = min(remaining_sim, year_end - t)
        op_hours += sim_in_year * u
        remaining_sim -= sim_in_year
        t += sim_in_year

    return op_hours
