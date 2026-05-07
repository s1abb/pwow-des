# Task 001 — Phase 1: Single Truck Scaffold

## Goal

Build and validate a single-truck discrete-event simulation using the local
`engine` package. One truck, one workshop bay, one mechanic. No shovels, no
fleet, no Monte Carlo. The simulation should pass the Phase 1 acceptance
criteria from the concept document:

- Weibull time-to-failure (TTF) draws produce realistic MTBF values.
- Scheduled PMs fire at the correct hour thresholds.
- Physical availability (PA%) lands in the 92–94% benchmark range over a
  1-year run (8,760 simulated hours).

---

## Deliverables

1. `simulation/src/simulation/sim.py` — runnable simulation entry point.
2. `simulation/src/simulation/config.py` — all parameter constants from the concept doc
   (Phase 1 subset: single truck, 1 bay, 1 mechanic).
3. `simulation/src/simulation/truck.py` — `truck_process` generator and helpers.
4. `simulation/src/simulation/stats.py` — KPI collection and summary reporting.
5. `simulation/tests/test_phase1.py` — pytest tests covering acceptance
   criteria.

---

## Folder layout (target)

```
simulation/
    concept/
        mining_fleet_des_concept.md   ← existing
    src/
        simulation/
            __init__.py
            config.py
            stats.py
            truck.py
            sim.py
    tests/
        __init__.py
        test_phase1.py
```

---

## Step-by-step plan

### Step 1 — `config.py`: parameter constants

Copy the four parameter dictionaries from the concept doc verbatim.
For Phase 1, only `TRUCK_PM_SCHEDULE`, `TRUCK_PREMATURE_FAILURE`, and the
shared-resource / fleet / simulation constants are needed. Include the full
shovel dicts as commented stubs so Phase 3 is trivial to add.

Constants to define:

```python
TRUCK_PM_SCHEDULE        # dict — 10 entries, interval/duration_mean/duration_sd/bay
TRUCK_PREMATURE_FAILURE  # dict — 6 entries, shape/scale/repair_mean/repair_sd/bay
N_BAYS      = 1          # Phase 1 override (concept default: 4)
N_MECHANICS = 1          # Phase 1 override (concept default: 6)
N_TRUCKS    = 1          # Phase 1 override
OPP_WINDOW_HRS = 50
SIM_DURATION   = 8_760
N_RUNS         = 1       # single run for Phase 1
RANDOM_SEED    = 42
```

---

### Step 2 — `truck.py`: the truck process generator

The truck process is a single generator that loops for the full simulation
duration. Each iteration:

1. **Race operating vs. premature failure.**
   For each component in `TRUCK_PREMATURE_FAILURE`, draw a Weibull TTF from
   the current simulated hour. Use `numpy.random.weibull` scaled by `scale`:
   `ttf = scale * rng.weibull(shape)`.
   The component with the shortest TTF "wins" if its TTF < the next PM
   threshold (see below).

2. **Find the next PM threshold.**
   Maintain a `pm_clock` dict keyed by PM name, tracking the next scheduled
   hour for each event. The nearest upcoming PM is `next_pm_hrs`.

3. **Decide which event fires next.**
   - If `min_ttf < next_pm_hrs`: a premature failure fires at `now + min_ttf`.
   - Else: the next PM fires at `now + next_pm_hrs - pm_clock_elapsed`.
   - **Opportunistic window**: if `min_ttf` falls within `OPP_WINDOW_HRS` of
     `next_pm_hrs`, combine both events (use the PM duration, no separate
     failure repair).

4. **Yield a timeout** for the operating interval (time until next event).
   Accumulate `operating_hours` during this yield.

5. **Request resources.**
   All truck events require a bay and a mechanic. Use
   `engine.resource.Resource.request()`. Yield the request; time spent
   waiting is **queue time** (downtime, not operating time).

6. **Yield a timeout** for the event duration.
   Draw duration from a normal distribution:
   `max(0.5, rng.normal(duration_mean, duration_sd))`.
   Accumulate `downtime_hours`.

7. **Release resources** (context manager on the token).

8. **Advance the PM clock** by the operating interval elapsed.
   If the fired event was a scheduled PM, advance that PM's threshold by
   its interval. If it was a premature failure followed by opportunistic PM,
   advance both.

9. Loop back to step 1.

**Signature:**

```python
def truck_process(
    env: Environment,
    name: str,
    bay_resource: Resource,
    mechanic_resource: Resource,
    stats: "TruckStats",
    rng: numpy.random.Generator,
) -> Generator:
    ...
```

`TruckStats` is a small dataclass (see Step 3) passed in by reference so the
process can write KPIs directly.

---

### Step 3 — `stats.py`: KPI collection

Define a `TruckStats` dataclass:

```python
@dataclass
class TruckStats:
    name: str
    operating_hours: float = 0.0
    downtime_scheduled: float = 0.0
    downtime_unscheduled: float = 0.0
    queue_time: float = 0.0
    events: list = field(default_factory=list)
    # events list items: dict with keys:
    #   type ("scheduled" | "premature" | "opportunistic")
    #   name (PM key or component key)
    #   start_operating, queue_start, repair_start, repair_end
```

Add a `summary()` method that returns:

```python
{
    "pa_pct": operating_hours / SIM_DURATION * 100,
    "scheduled_events": count,
    "unscheduled_events": count,
    "opportunistic_events": count,
    "mean_queue_time_hrs": mean queue time per event,
    "mtbf_by_component": {component: mean operating hrs between failures},
    "mttr_by_event_type": {event_name: mean repair duration},
}
```

---

### Step 4 — `sim.py`: simulation entry point

```python
def run_phase1(seed=RANDOM_SEED) -> dict:
    rng = numpy.random.default_rng(seed)
    env = Environment()
    bay      = Resource(capacity=N_BAYS)
    mechanic = Resource(capacity=N_MECHANICS)
    stats    = TruckStats(name="Truck-0")
    env.process(lambda: truck_process(env, "Truck-0", bay, mechanic, stats, rng))
    env.run(until=SIM_DURATION)
    return stats.summary()

if __name__ == "__main__":
    result = run_phase1()
    print(json.dumps(result, indent=2))
```

Running `python -m simulation.sim` should print a JSON summary to stdout.

---

### Step 5 — `tests/test_phase1.py`: acceptance tests

| Test | Assertion |
|---|---|
| `test_pa_pct_in_benchmark_range` | `92.0 <= pa_pct <= 94.0` |
| `test_pm_a_fires_at_250_hr_intervals` | All PM-A events occur at multiples of 250 hrs (±queue wait) |
| `test_weibull_ttf_produces_realistic_mtbf` | Per-component MTBF > 0.6 × scale (most machines reach overhaul) |
| `test_no_event_overlap` | No two events for the same truck overlap in time |
| `test_resources_released` | `bay.capacity == bay.available` and same for mechanic at sim end |
| `test_operating_plus_downtime_equals_sim_duration` | `operating + downtime + queue ≈ SIM_DURATION` (within float tolerance) |

---

## Acceptance criteria (Phase 1 complete when all pass)

- [ ] `pytest simulation/tests/test_phase1.py -v` passes with zero failures.
- [ ] `python -m simulation.sim` prints a JSON summary with `pa_pct` in
      `[92.0, 94.0]`.
- [ ] No import of SimPy — only the local `engine` package is used.

---

## Out of scope for Phase 1

- Multiple trucks or shovels.
- Shift-based mechanic availability.
- Monte Carlo replications.
- Scenario sweeps.
- Any output beyond stdout JSON and pytest assertions.

These are covered in tasks 002–004 (Phases 2–4).
