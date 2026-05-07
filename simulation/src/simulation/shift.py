"""Shift scheduler for the mechanic resource pool.

Drives a Resource's capacity through the phases defined in SHIFT_SCHEDULE,
including non-productive handover and break windows.

Capacity changes:
  Decrease — clamps resource.available to min(available, new_capacity).
             Mechanics already holding tokens (in-progress repairs) are
             unaffected; they finish their current job normally.
  Increase  — raises resource.capacity and resource.available by the delta,
             then grants any queued requests up to the new available count.
             Reuses the same waiter-grant logic as Resource.release().
"""
from __future__ import annotations

import bisect
import heapq
from typing import TYPE_CHECKING

from engine.resource import Token

if TYPE_CHECKING:
    from engine.environment import Environment
    from engine.resource import Resource


class ShiftScheduler:
    """Adjusts mechanic resource capacity according to a shift schedule.

    Parameters
    ----------
    env:
        The simulation environment.
    resource:
        The Resource whose capacity will be managed.
    schedule:
        List of phase dicts (SHIFT_SCHEDULE from config).  Each dict must
        have keys: name, start (hour of day, float), duration (hours),
        n_mechanics (int), productive (bool).
        Phases must tile the 24-hour clock without gaps, listed in
        chronological order starting from the first shift of the day.

    Implementation notes
    --------------------
    When capacity is *reduced* while mechanics are in-progress (holding
    tokens), the ``Resource.release()`` method would normally increment
    ``available`` for every completed repair, eventually pushing ``available``
    above ``capacity``.  To prevent this, the scheduler tracks a
    ``_capacity_debt`` counter — the number of in-progress mechanics that
    exceed the new capacity.  The resource's ``release()`` is patched so that
    each "debt" release pre-decrements ``available`` before calling the
    original, resulting in a net-zero change to ``available`` for those
    excess mechanics.
    """

    _DAY = 24.0

    def __init__(
        self,
        env: "Environment",
        resource: "Resource",
        schedule: list[dict],
    ) -> None:
        self.env = env
        self.resource = resource
        self.schedule = schedule
        self._capacity_debt: int = 0

        # Cycle start = start hour of the first phase (e.g. 6.0 for day shift).
        self._cycle_start: float = float(schedule[0]["start"])

        # Build cumulative phase-start times within the 24-hr cycle.
        # Phase i starts at _phase_starts[i] hours after _cycle_start.
        cumul = 0.0
        self._phase_starts: list[float] = []
        for phase in schedule:
            self._phase_starts.append(cumul)
            cumul += phase["duration"]

        # Total cycle duration should equal 24.0.
        self._cycle_duration: float = cumul

        # Patch resource.release to absorb excess releases when in debt.
        self._patch_release()

        env.process(self._shift_change_process())

    # ── Release patch ─────────────────────────────────────────────────────────

    def _patch_release(self) -> None:
        """Replace resource.release with a debt-aware wrapper."""
        original = self.resource.release
        scheduler = self

        def _managed_release(proc=None, token=None):
            if scheduler._capacity_debt > 0:
                # Pre-decrement available so that the +1 inside original
                # release nets to zero for this "excess" mechanic.
                scheduler.resource.available -= 1
                scheduler._capacity_debt -= 1
            original(proc=proc, token=token)

        self.resource.release = _managed_release

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _current_phase_index(self) -> tuple[int, float]:
        """Return (phase_index, elapsed_hours_into_phase) for env.now."""
        hour_of_day = self.env.now % self._DAY
        # Convert to hours since cycle start (wraps within [0, cycle_duration)).
        cycle_hour = (hour_of_day - self._cycle_start) % self._cycle_duration
        # Binary search: find the last phase whose cumulative start ≤ cycle_hour.
        idx = bisect.bisect_right(self._phase_starts, cycle_hour) - 1
        idx = max(0, idx)
        elapsed = cycle_hour - self._phase_starts[idx]
        return idx, elapsed

    def _set_capacity(self, new_capacity: int) -> None:
        """Adjust resource capacity to new_capacity, handling waiters and debt."""
        res = self.resource
        # Compute in-use mechanics from the allocated list (ground truth).
        in_use = len(res.allocated)
        # Debt = mechanics currently in-progress beyond the new capacity.
        # Their releases will be absorbed (net-zero available change).
        self._capacity_debt = max(0, in_use - new_capacity)
        res.capacity = new_capacity
        res.available = max(0, new_capacity - in_use)
        if res.available > 0:
            self._grant_waiters()

    def _grant_waiters(self) -> None:
        """Grant waiting Resource requests up to the current available count.

        This replicates the waiter-grant loop in Resource.release() so that
        capacity increases are immediately reflected in queued requests.
        """
        res = self.resource
        while res.waiters and res.available > 0:
            prio, seq, next_proc, next_env, req = res.waiters[0]
            if not getattr(req, "_active", False):
                heapq.heappop(res.waiters)
                continue
            heapq.heappop(res.waiters)
            req._active = False
            token = Token(
                res,
                next_proc,
                name=getattr(req, "name", None),
                allocated_at=next_env.now,
            )
            res.allocated.append(
                (next_proc, token, getattr(req, "priority", 0), getattr(req, "preemptible", False))
            )
            res.available -= 1
            req.succeed(token)

    # ── Generator process ─────────────────────────────────────────────────────

    def _shift_change_process(self):
        """Generator that applies capacity changes at each phase boundary."""
        idx, elapsed = self._current_phase_index()

        # Apply the current phase's capacity immediately at simulation start.
        phase = self.schedule[idx]
        self._set_capacity(phase["n_mechanics"])

        # Yield the remainder of the current phase, then loop through phases.
        remaining = phase["duration"] - elapsed
        yield self.env.timeout(remaining)

        while True:
            idx = (idx + 1) % len(self.schedule)
            phase = self.schedule[idx]
            self._set_capacity(phase["n_mechanics"])
            yield self.env.timeout(phase["duration"])
