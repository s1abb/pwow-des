# Task 003 — Phase 3: Add Hydraulic Mining Shovels

## Goal

Introduce hydraulic shovel processes alongside the existing truck fleet.
Shovels share the same workshop bay and mechanic pools as trucks, but with
asymmetric resource demand: minor PMs are performed on-site using only a
mechanic; major overhauls and all unscheduled repairs require both a bay and
a mechanic.

Observe whether shovel major overhauls create bay contention that degrades
truck PA%, and verify that shovel PA% lands in the 90–92% world-class
benchmark range.

Simulation run: **5 years (43,800 simulated hours)**, single deterministic
run (Monte Carlo is Phase 4).

---

## Deliverables

1. `simulation/src/simulation/config.py` — uncomment/add `SHOVEL_PM_SCHEDULE`,
   `SHOVEL_PREMATURE_FAILURE`, and `N_SHOVELS = 3`.
2. `simulation/src/simulation/shovel.py` — `shovel_process` generator,
   mirroring `truck_process` but honouring the `bay` flag per event.
3. `simulation/src/simulation/fleet.py` — extend `run_fleet()` to also spawn
   shovel processes; return `(list[TruckStats], list[ShovelStats])`.
4. `simulation/src/simulation/stats.py` — add `ShovelStats` (same fields as
   `TruckStats`); update `FleetStats` to carry both lists and report combined
   + per-type summaries.
5. `simulation/src/simulation/sim.py` — update `run_phase2()` (now effectively
   Phase 3 content) or add `run_phase3()` that calls the extended `run_fleet`.
6. `simulation/src/simulation/export.py` — extend `write_truck_summary` and
   `write_events` to also write shovel rows, or add dedicated shovel CSVs.
7. `simulation/tests/test_phase3.py` — pytest tests covering acceptance
   criteria.

---

## Folder layout (additions)

```
simulation/
    src/
        simulation/
            shovel.py      ← NEW
            config.py      ← UPDATED (uncomment shovel dicts, N_SHOVELS)
            fleet.py       ← UPDATED (spawn shovels)
            stats.py       ← UPDATED (ShovelStats, FleetStats extended)
            sim.py         ← UPDATED (run_phase3)
            export.py      ← UPDATED (shovel rows in CSVs)
    tests/
        test_phase3.py     ← NEW
```

---

## Step-by-step plan

### Step 1 — `config.py`: activate shovel parameters

The concept doc already defines both dicts. Uncomment / add them and set
`N_SHOVELS = 3`:

```python
# ── SHOVEL: Scheduled PM & Overhaul ──────────────────────────────────────────
# bay: False → mechanic only (on-site service)
# bay: True  → bay + mechanic (workshop)
SHOVEL_PM_SCHEDULE = {
    "daily_inspect":    {"interval": 10,     "duration_mean": 0.5, "duration_sd": 0.2,  "bay": False},
    "PM_A":             {"interval": 250,    "duration_mean": 3,   "duration_sd": 0.8,  "bay": False},
    "PM_B":             {"interval": 1_000,  "duration_mean": 6,   "duration_sd": 1.5,  "bay": False},
    "GET_replace":      {"interval": 1_000,  "duration_mean": 4,   "duration_sd": 1.0,  "bay": False},
    "pin_service":      {"interval": 3_000,  "duration_mean": 8,   "duration_sd": 2.0,  "bay": False},
    "hydraulic_OH":     {"interval": 4_000,  "duration_mean": 16,  "duration_sd": 4.0,  "bay": True},
    "swing_ring_OH":    {"interval": 6_000,  "duration_mean": 24,  "duration_sd": 6.0,  "bay": True},
    "undercarriage_OH": {"interval": 8_000,  "duration_mean": 48,  "duration_sd": 10.0, "bay": True},
    "swing_gear_OH":    {"interval": 12_000, "duration_mean": 32,  "duration_sd": 8.0,  "bay": True},
    "engine_rebuild":   {"interval": 20_000, "duration_mean": 240, "duration_sd": 24,   "bay": True},
}

# ── SHOVEL: Premature Failures — Weibull(shape, scale) ───────────────────────
SHOVEL_PREMATURE_FAILURE = {
    "engine":        {"shape": 2.0, "scale": 12_000, "repair_mean": 240, "repair_sd": 24, "bay": True},
    "hydraulics":    {"shape": 1.5, "scale":  2_500, "repair_mean": 16,  "repair_sd": 4,  "bay": True},
    "swing_ring":    {"shape": 2.0, "scale":  4_000, "repair_mean": 48,  "repair_sd": 12, "bay": True},
    "boom_pins":     {"shape": 2.2, "scale":  2_000, "repair_mean": 12,  "repair_sd": 3,  "bay": True},
    "GET":           {"shape": 1.8, "scale":    600,  "repair_mean": 4,   "repair_sd": 1,  "bay": True},
    "undercarriage": {"shape": 2.5, "scale":  5_000, "repair_mean": 24,  "repair_sd": 6,  "bay": True},
}

N_SHOVELS = 3
```

> Note: The concept doc lists shovel engine premature failure `scale = 4_000`
> (much lower than the truck's 12,000). This reflects higher thermal loading
> on shovel engines. Use the truck value (12,000) to match the benchmark PA%
> range, or keep 4,000 and accept lower shovel PA%.
> **Decision needed before implementation.**

---

### Step 2 — `shovel.py`: `shovel_process` generator

Mirror `truck_process` with one key difference: check `cfg["bay"]` on each
event to decide whether to request a bay. Minor PM events skip the bay
request entirely, holding only a mechanic token.

```python
def shovel_process(
    env: Environment,
    name: str,
    bay_resource: Resource,
    mechanic_resource: Resource,
    stats: ShovelStats,
    rng: np.random.Generator,
    *,
    pm_offsets: dict[str, float] | None = None,
):
    ...
    while True:
        # same threshold / TTF logic as truck_process
        ...

        # Resource acquisition: branch on bay flag
        needs_bay = cfg["bay"]   # True for major events, False for minor PMs

        queue_start = env.now
        if needs_bay:
            req_bay = bay_resource.request()
            with (yield req_bay):
                req_mech = mechanic_resource.request()
                with (yield req_mech):
                    # sample duration, yield timeout, record event
                    ...
        else:
            req_mech = mechanic_resource.request()
            with (yield req_mech):
                # sample duration, yield timeout, record event
                ...
```

The `bay` flag for the *active* event is determined as follows:
- For **scheduled** events: `SHOVEL_PM_SCHEDULE[primary_pm]["bay"]`
- For **premature** failures: `SHOVEL_PREMATURE_FAILURE[failed_comp]["bay"]`
  (all premature failures are `True` per the concept doc)
- For **opportunistic** events (premature within OPP window of a PM):
  use `True` if either the PM or the failure requires a bay

Add `failed_comp` to the event dict so it mirrors the truck event schema.

---

### Step 3 — `fleet.py`: spawn shovels alongside trucks

```python
def run_fleet(
    env: Environment,
    bay: Resource,
    mechanic: Resource,
    rng: np.random.Generator,
    n_trucks: int = N_TRUCKS,
    n_shovels: int = N_SHOVELS,
) -> tuple[list[TruckStats], list[ShovelStats]]:
    truck_stats = []
    for i in range(n_trucks):
        truck_rng = np.random.default_rng(rng.integers(0, 2**32))
        s = TruckStats(name=f"Truck-{i}")
        truck_stats.append(s)
        env.process(truck_process(env, f"Truck-{i}", bay, mechanic, s, truck_rng,
                                  pm_offsets=_stagger(TRUCK_PM_SCHEDULE, truck_rng)))

    shovel_stats = []
    for i in range(n_shovels):
        shovel_rng = np.random.default_rng(rng.integers(0, 2**32))
        s = ShovelStats(name=f"Shovel-{i}")
        shovel_stats.append(s)
        env.process(shovel_process(env, f"Shovel-{i}", bay, mechanic, s, shovel_rng,
                                   pm_offsets=_stagger(SHOVEL_PM_SCHEDULE, shovel_rng)))

    return truck_stats, shovel_stats
```

Extract the existing stagger logic from `run_fleet` into a private
`_stagger(pm_schedule, rng)` helper to avoid duplication.

---

### Step 4 — `stats.py`: `ShovelStats` and extended `FleetStats`

`ShovelStats` is identical in fields to `TruckStats`. Reuse via a shared
base class or simply duplicate (simpler for now — no generalisation until
Phase 4 requires it).

Update `FleetStats`:

```python
@dataclass
class FleetStats:
    trucks: list[TruckStats]
    shovels: list[ShovelStats]

    def summary(self, sim_duration: float = SIM_DURATION) -> dict:
        truck_summaries  = [t.summary(sim_duration) for t in self.trucks]
        shovel_summaries = [s.summary(sim_duration) for s in self.shovels]
        all_events = [e for t in self.trucks  for e in t.events] + \
                     [e for s in self.shovels for e in s.events]
        return {
            # truck fleet KPIs
            "truck_pa_pct_mean":  ...,
            "truck_pa_pct_min":   ...,
            "truck_pa_pct_max":   ...,
            # shovel fleet KPIs
            "shovel_pa_pct_mean": ...,
            "shovel_pa_pct_min":  ...,
            "shovel_pa_pct_max":  ...,
            # combined
            "combined_pa_pct_mean": ...,
            "total_scheduled_events":     ...,
            "total_unscheduled_events":   ...,
            "total_opportunistic_events": ...,
            "mean_queue_time_hrs":        ...,
            "peak_queue_time_hrs":        ...,
            "per_truck":   truck_summaries,
            "per_shovel":  shovel_summaries,
        }
```

---

### Step 5 — `sim.py`: `run_phase3`

```python
def run_phase3(seed: int = RANDOM_SEED) -> tuple[FleetStats, Resource, Resource]:
    rng = np.random.default_rng(seed)
    env = Environment()
    bay      = Resource(capacity=N_BAYS)
    mechanic = Resource(capacity=N_MECHANICS)

    ShiftScheduler(env, mechanic, SHIFT_SCHEDULE)

    truck_stats, shovel_stats = run_fleet(env, bay, mechanic, rng)
    fleet = FleetStats(trucks=truck_stats, shovels=shovel_stats)
    env.run(until=SIM_DURATION)
    return fleet, bay, mechanic
```

Keep `run_phase2` untouched and working for regression purposes — Phase 3
adds a new entry point.

---

### Step 6 — `export.py`: include shovels in CSVs

Add an `equipment_type` column (`"truck"` / `"shovel"`) to both
`truck_summary.csv` and `events.csv` so a single file covers the full fleet.
Rename `write_truck_summary` → `write_fleet_summary` (or keep the old name
and add a new one) to reflect that it now covers both equipment types.

---

### Step 7 — `tests/test_phase3.py`: acceptance tests

| Test | Assertion |
|---|---|
| `test_truck_pa_pct_in_benchmark_range` | `90.0 <= truck_pa_pct_mean <= 95.0` (widened to account for shovel contention) |
| `test_shovel_pa_pct_in_benchmark_range` | `88.0 <= shovel_pa_pct_mean <= 93.0` |
| `test_all_equipment_has_events` | Every truck and shovel has ≥ 1 event |
| `test_shovel_minor_pms_never_use_bay` | No event with `bay=False` in the shovel PM schedule appears in bay-acquired events |
| `test_shovel_major_events_use_bay` | Events for `hydraulic_OH`, `swing_ring_OH`, `undercarriage_OH`, `swing_gear_OH`, `engine_rebuild` all have `queue_time` consistent with bay contention |
| `test_queue_increases_vs_phase2` | `peak_queue_time_hrs` in Phase 3 ≥ Phase 2 (shovels add contention) |
| `test_no_event_overlap_per_equipment` | No two events for the same machine overlap in time |
| `test_resources_released` | `0 <= bay.available <= N_BAYS`, `0 <= mechanic.available <= mechanic.capacity` at sim end |
| `test_time_conservation_per_equipment` | `operating + downtime <= SIM_DURATION + 1e-9` for every machine |
| `test_phase2_still_passes` | Import and call `run_phase2()` — all Phase 2 KPIs still in range |

---

## Key design decisions to resolve before implementing

1. **Shovel engine `scale`**: concept doc says 4,000 hrs (aggressive failure
   rate); truck uses 12,000. Clarify which value to use for benchmarking.

2. **`FleetStats` backwards compatibility**: `run_phase2` returns a
   `FleetStats` with only `trucks`. Either add `shovels=[]` default to
   `FleetStats.__init__`, or keep the Phase 2 `FleetStats` separate from the
   Phase 3 one. Recommended: add `shovels: list[ShovelStats] = field(default_factory=list)` so Phase 2 callers are unaffected.

3. **`write_fleet_summary` naming**: adding an `equipment_type` column and
   renaming is cleaner than two separate CSVs, but it breaks any downstream
   tooling built against Phase 2 output. Decide whether to add a new function
   or migrate the existing one.

---

## Acceptance criteria (Phase 3 complete when all pass)

- [ ] `pytest simulation/tests/test_phase3.py -v` passes with zero failures.
- [ ] `python -m simulation.sim` (calling `run_phase3`) prints a JSON summary
      with `truck_pa_pct_mean` in `[90.0, 95.0]` and `shovel_pa_pct_mean`
      in `[88.0, 93.0]`.
- [ ] Phase 1 and Phase 2 tests still pass.
- [ ] No import of SimPy — only the local `engine` package is used.

---

## Out of scope for Phase 3

- Aging / imperfect repair model (tracked separately).
- Monte Carlo / P10-P50-P90 distributions (Phase 4).
- Scenario parameter sweeps (Phase 4).
- Notebook / HTML reporting (Phase 4).
