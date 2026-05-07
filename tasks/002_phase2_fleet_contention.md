# Task 002 — Phase 2: Truck Fleet with Resource Contention

## Goal

Scale the simulation from a single truck to a full fleet of `N_TRUCKS` haul
trucks sharing a limited pool of workshop bays and mechanics. Introduce
shift-based mechanic availability so crew rosters reduce capacity at night.
Observe queue formation, measure its impact on fleet PA%, and confirm the
model produces the 92–94% benchmark range seen at world-class surface mines.

Simulation run: **5 years (43,800 simulated hours)**, one deterministic run.
(Monte Carlo wrapping is deferred to Phase 4.)

---

## Deliverables

1. `simulation/src/simulation/config.py` — updated fleet/resource constants
   (restore `N_TRUCKS = 15`, `N_BAYS = 4`, `N_MECHANICS = 6`; add shift
   schedule).
2. `simulation/src/simulation/fleet.py` — `run_fleet()` helper that spawns
   `N_TRUCKS` truck processes with staggered starting clocks.
3. `simulation/src/simulation/shift.py` — `ShiftMechanicResource` that
   adjusts mechanic capacity according to a day/afternoon/night roster.
4. `simulation/src/simulation/sim.py` — updated entry point calling
   `run_fleet()`.
5. `simulation/src/simulation/stats.py` — add `FleetStats` aggregating per-
   truck summaries into fleet-level KPIs.
6. `simulation/tests/test_phase2.py` — pytest tests covering acceptance
   criteria.

---

## Folder layout (additions)

```
simulation/
    src/
        simulation/
            fleet.py       ← NEW
            shift.py       ← NEW
            config.py      ← UPDATED
            sim.py         ← UPDATED
            stats.py       ← UPDATED
    tests/
        test_phase2.py     ← NEW
```

---

## Step-by-step plan

### Step 1 — `config.py`: restore fleet-scale constants

Update the overridden Phase 1 values back to the concept-doc defaults and add
a shift schedule:

```python
N_TRUCKS    = 15
N_BAYS      = 4
N_MECHANICS = 6   # day-shift active baseline

# Two 12-hour shifts per day (06:00–18:00 day, 18:00–06:00 night).
# Each shift entry describes one phase within that shift.
# Phases are ordered and tile the 24-hour clock without gaps.
#
# Fields:
#   name          — human-readable label
#   start         — hour-of-day this phase begins (0–23)
#   duration      — phase length in hours
#   n_mechanics   — active (available for work) mechanics during this phase
#   productive    — False marks handover/break windows where mechanics are
#                   present but unavailable for new work requests
#
# Non-productive phases:
#   Shift handover: 30 min at each shift change (both crews present but
#                   occupied with handover; model uses 0 available mechanics).
#   Crib/meal break: two 30-min breaks per 12-hr shift where the crew rotates
#                   through in two groups — half the mechanics remain available.

SHIFT_SCHEDULE = [
    # ── Day shift 06:00–18:00 ────────────────────────────────────────────
    {"name": "day_handover",    "start":  6.0, "duration": 0.5, "n_mechanics": 0, "productive": False},
    {"name": "day_working_1",   "start":  6.5, "duration": 3.5, "n_mechanics": 6, "productive": True},
    {"name": "day_crib_1",      "start": 10.0, "duration": 0.5, "n_mechanics": 3, "productive": False},
    {"name": "day_working_2",   "start": 10.5, "duration": 4.5, "n_mechanics": 6, "productive": True},
    {"name": "day_crib_2",      "start": 15.0, "duration": 0.5, "n_mechanics": 3, "productive": False},
    {"name": "day_working_3",   "start": 15.5, "duration": 2.0, "n_mechanics": 6, "productive": True},
    # ── Night shift 18:00–06:00 ──────────────────────────────────────────
    {"name": "night_handover",  "start": 17.5, "duration": 0.5, "n_mechanics": 0, "productive": False},
    {"name": "night_working_1", "start": 18.0, "duration": 3.5, "n_mechanics": 4, "productive": True},
    {"name": "night_crib_1",    "start": 21.5, "duration": 0.5, "n_mechanics": 2, "productive": False},
    {"name": "night_working_2", "start": 22.0, "duration": 4.5, "n_mechanics": 4, "productive": True},
    {"name": "night_crib_2",    "start":  2.5, "duration": 0.5, "n_mechanics": 2, "productive": False},
    {"name": "night_working_3", "start":  3.0, "duration": 3.0, "n_mechanics": 4, "productive": True},
]
```

> The `productive: False` phases drive the `ShiftScheduler` to temporarily
> set `resource.capacity` to the reduced count, preventing new requests from
> being granted. In-progress repairs are unaffected — mechanics already
> holding a token continue until they release it.

---

### Step 2 — `shift.py`: shift-aware mechanic resource

`ShiftScheduler` drives a `Resource`'s capacity through each phase in
`SHIFT_SCHEDULE`, including the non-productive handover and break windows.

Implementation approach:
- At `__init__`, compute the time (in simulated hours) until the start of
  the first upcoming phase boundary, then schedule `_shift_change_process`.
- `_shift_change_process` is a generator that loops forever: on each
  iteration it applies the current phase's `n_mechanics` to
  `resource.capacity`, yields a timeout for the phase's `duration`, then
  advances to the next phase.
- Capacity *reductions* clamp `available` to
  `min(resource.available, new_capacity)` so in-progress repairs are
  unaffected — mechanics holding a token continue until they release it.
- Capacity *increases* simply raise `resource.capacity` and `resource.available`
  by the delta; any queued requests are then granted normally by the engine.
- The `productive` flag is informational; the scheduler enforces it by
  setting `n_mechanics = 0` (or the reduced break count) for that phase —
  no separate code path is required.

```python
class ShiftScheduler:
    def __init__(
        self,
        env: Environment,
        resource: Resource,
        schedule: list[dict],   # SHIFT_SCHEDULE from config
    ) -> None: ...

    def _current_phase_index(self) -> int:
        """Return the index of the phase active at env.now."""
        ...

    def _shift_change_process(self): ...   # generator — loops forever
```

---

### Step 3 — `fleet.py`: spawn truck fleet

```python
def run_fleet(
    env: Environment,
    bay: Resource,
    mechanic: Resource,
    rng: np.random.Generator,
    n_trucks: int = N_TRUCKS,
) -> list[TruckStats]:
    """Spawn n_trucks truck processes with independent RNG streams.

    Each truck gets a separate child RNG derived from the master so results
    are independent but still fully reproducible from a single seed.
    """
    fleet_stats = []
    for i in range(n_trucks):
        truck_rng = np.random.default_rng(rng.integers(0, 2**32))
        stats = TruckStats(name=f"Truck-{i}")
        fleet_stats.append(stats)
        env.process(truck_process(env, f"Truck-{i}", bay, mechanic, stats, truck_rng))
    return fleet_stats
```

Each truck starts with a randomised initial PM clock offset (uniform draw in
`[0, interval)` for each PM) so trucks don't all arrive at the workshop
simultaneously on day one.

---

### Step 4 — `stats.py`: `FleetStats` aggregate

Add a `FleetStats` class:

```python
@dataclass
class FleetStats:
    trucks: list[TruckStats]

    def summary(self, sim_duration: float = SIM_DURATION) -> dict:
        per_truck = [t.summary(sim_duration) for t in self.trucks]
        pa_values = [s["pa_pct"] for s in per_truck]
        return {
            "fleet_pa_pct_mean": mean(pa_values),
            "fleet_pa_pct_min":  min(pa_values),
            "fleet_pa_pct_max":  max(pa_values),
            "per_truck": per_truck,
            "total_scheduled_events":   sum(s["scheduled_events"]   for s in per_truck),
            "total_unscheduled_events": sum(s["unscheduled_events"]  for s in per_truck),
            "total_opportunistic_events": sum(s["opportunistic_events"] for s in per_truck),
            "mean_queue_time_hrs":        mean(s["mean_queue_time_hrs"] for s in per_truck),
            "peak_queue_time_hrs":        max(e["queue_time"]
                                              for t in self.trucks for e in t.events),
        }
```

---

### Step 5 — `sim.py`: updated entry point

```python
def run_phase2(seed: int = RANDOM_SEED) -> tuple[FleetStats, Resource, Resource]:
    rng  = np.random.default_rng(seed)
    env  = Environment()
    bay      = Resource(capacity=N_BAYS)
    mechanic = Resource(capacity=N_MECHANICS)

    # Start shift scheduler (adjusts mechanic capacity at shift boundaries).
    ShiftScheduler(env, mechanic, SHIFT_SCHEDULE)

    fleet_stats = FleetStats(trucks=run_fleet(env, bay, mechanic, rng))
    env.run(until=SIM_DURATION)
    return fleet_stats, bay, mechanic
```

`__main__` block prints `fleet_stats.summary()` as JSON.

---

### Step 6 — `tests/test_phase2.py`: acceptance tests

| Test | Assertion |
|---|---|
| `test_fleet_pa_pct_in_benchmark_range` | `92.0 <= fleet_pa_pct_mean <= 94.0` |
| `test_all_trucks_have_events` | Every truck has ≥ 1 scheduled event |
| `test_queue_forms_under_contention` | At least one event has `queue_time > 0` |
| `test_no_event_overlap_per_truck` | No two events for the same truck overlap |
| `test_resources_released` | `bay.available == N_BAYS` and `mechanic.available == N_MECHANICS` at sim end |
| `test_time_conservation_per_truck` | `operating + downtime + queue ≈ SIM_DURATION` for every truck |
| `test_shift_reduces_night_capacity` | During a known night working phase, `mechanic.capacity == 4` |
| `test_handover_sets_capacity_zero` | During a known handover window, `mechanic.capacity == 0` |
| `test_break_halves_capacity` | During a known crib break, `mechanic.capacity == 3` (day) or `2` (night) |

---

## Acceptance criteria (Phase 2 complete when all pass)

- [ ] `pytest simulation/tests/test_phase2.py -v` passes with zero failures.
- [ ] `python -m simulation.sim` (or a `run_phase2` call) prints a JSON
      summary with `fleet_pa_pct_mean` in `[92.0, 94.0]`.
- [ ] Phase 1 tests still pass: `pytest simulation/tests/test_phase1.py -v`.
- [ ] No import of SimPy — only the local `engine` package is used.

---

## Out of scope for Phase 2

- Shovels (Phase 3).
- Monte Carlo / P10-P50-P90 distributions (Phase 4).
- Scenario parameter sweeps.
- Any output beyond stdout JSON and pytest assertions.
