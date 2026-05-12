# Task 005 — Refactor simulation to activity-group failure structure

**Status: COMPLETE** — all 45 tests pass (20 fitting + 25 simulation).

## Goal

Replace the component-keyed premature failure dicts (`"engine"`, `"tyres"`,
`"hydraulics"`, etc.) with activity-group-keyed dicts (`"RPR"`, `"RPL"`,
`"INS"`, `"TYR"`, `"OTHER_CM"`) that match the output of the fitting pipeline,
**and** spawn model-typed simulation processes so that each physical model
(Cat_793F, EH4000, EX3600, etc.) uses its own fitted Weibull parameters rather
than a single type-level dict.  No backwards compatibility required.

Also extends the fitting pipeline to handle **both corrective and preventive**
work orders, producing a 3-level `PREMATURE_FAILURE_FITTED[model][order_type_group][activity_group]`
dict that the simulation flattens at load time.

---

## Implemented state

### `simulation/src/simulation/config.py`

```python
PREMATURE_FAILURE: dict[str, dict[str, dict]] = {
    "Cat_793F": {
        "RPR": {"shape": 1.010, "scale":   382, "repair_mean": 4.87, "repair_sd":  9.10},
        "RPL": {"shape": 0.900, "scale":   374, "repair_mean": 5.50, "repair_sd": 13.99},
        "INS": {"shape": 0.968, "scale": 1_068, "repair_mean": 4.28, "repair_sd":  5.41},
        "TYR": {"shape": 1.087, "scale": 2_430, "repair_mean": 6.69, "repair_sd":  5.03},
    },
    "EH4000": { ... },
    "EH5000": { ... },
    "EX3600": { ... },
    "EX5600": { ... },
    "EX8000": { ... },
    "L9800":  { ... },
}

N_FLEET = {
    "Cat_793F": 56, "EH4000": 19, "EH5000": 24,
    "EX3600": 8, "EX5600": 5, "EX8000": 3, "L9800": 2,
}
_TRUCK_MODELS  = ("Cat_793F", "EH4000", "EH5000")
_SHOVEL_MODELS = ("EX3600", "EX5600", "EX8000", "L9800")
N_TRUCKS  = sum(N_FLEET[m] for m in _TRUCK_MODELS)   # 99
N_SHOVELS = sum(N_FLEET[m] for m in _SHOVEL_MODELS)  # 18

N_BAYS      = 12
N_MECHANICS = 24   # day shift (4× night shift = 16)

SIM_DURATION = 13_140  # 1.5 years

USE_FITTED_PARAMS = False

if USE_FITTED_PARAMS:
    try:
        from fitting.output.fitted_config import PREMATURE_FAILURE_FITTED
        # PREMATURE_FAILURE_FITTED is 3-level: model → order_type_group → ag → entry
        # Flatten to 2-level expected by truck/shovel: model → (otg_prefix+ag) → entry
        _PREFIX = {"corrective": "c_", "preventive": "p_"}
        PREMATURE_FAILURE = {
            model: {
                _PREFIX.get(otg, otg + "_") + ag: params
                for otg, ags in otg_dict.items()
                for ag, params in ags.items()
            }
            for model, otg_dict in PREMATURE_FAILURE_FITTED.items()
        }
    except (ImportError, KeyError):
        import warnings
        warnings.warn("USE_FITTED_PARAMS=True but fitted_config.py not found. Using defaults.")
```

### `simulation/src/simulation/fleet.py`

Spawns model-typed processes:

```python
unit = 0
for model in _TRUCK_MODELS:
    for _ in range(N_FLEET[model]):
        truck_rng = np.random.default_rng(rng.integers(0, 2**32))
        pm_offsets = _stagger(TRUCK_PM_SCHEDULE, truck_rng)
        stats = TruckStats(name=f"Truck-{unit}({model})")
        truck_stats.append(stats)
        env.process(
            truck_process(env, stats.name, bay, mechanic, stats, truck_rng,
                          pm_offsets=pm_offsets, failure_cfg=PREMATURE_FAILURE[model])
        )
        unit += 1
```

### `simulation/src/simulation/truck.py` and `shovel.py`

Accept `failure_cfg: dict` parameter; draw Weibull TTF from all activity groups:

```python
ag_ttf: dict[str, float] = {
    ag: float(cfg["scale"]) * float(rng.weibull(cfg["shape"]))
    for ag, cfg in failure_cfg.items()
}
failed_ag = min(ag_ttf, key=ag_ttf.__getitem__)
min_ttf   = ag_ttf[failed_ag]
```

Event records use `"activity_group": failed_ag`.

### `simulation/src/simulation/stats.py`

MTBF summary keyed by activity group:

```python
# → summary["mtbf_by_activity_group"]
```

### `fitting/src/fitting/ift.py`

Processes both corrective and preventive orders; returns columns:
`[model, equip_type, order_type_group, activity_group, ift_hrs]`

AG maps:
- corrective → `{RPR, RPL, INS, TYR, OTHER_CM}`
- preventive → `{RPL, SVC, NDT, INS, TYR, CAS, OTHER_PM}`

### `fitting/src/fitting/weibull_fit.py`

Groups by `(model, order_type_group, activity_group)`; output includes `order_type_group` column.

### `fitting/src/fitting/duration_fit.py`

Uses separate AG maps per order type (`_CM_AG_MAP` / `_PM_AG_MAP`); `OTHER_CM`/`OTHER_PM` suffixes.

### `fitting/src/fitting/export_config.py`

Writes `PREMATURE_FAILURE_FITTED[model][order_type_group][activity_group]` — a 3-level nested dict.

### `fitting/src/fitting/__main__.py`

Removed `pm_intervals` import and summary block; summary table now shows `order_type_group` column.

### `fitting/src/fitting/pm_intervals.py`

**Deleted** — superseded by preventive Weibull fits.

### `fitting/output/fitted_config.py`

Regenerated. Sample structure:

```python
PREMATURE_FAILURE_FITTED = {
    "Cat_793F": {
        "corrective": {
            "INS":      {"shape": 0.9681, "scale": 1068.2, "repair_mean": 4.28, "repair_sd": 5.41, "n": 807, "dur_n": 789},
            "OTHER_CM": {...},
            "RPL":      {...},
            "RPR":      {...},
            "TYR":      {...},
        },
        "preventive": {
            "INS":  {...},
            "NDT":  {...},
            "RPL":  {...},
            "SVC":  {...},
            "TYR":  {...},
        },
    },
    "EH4000": { ... },
    ...
}
```

---

## Capacity settings (determined by sweep)

- `N_BAYS = 12`, `N_MECHANICS = 24` (day) / 16 (night)
- `SIM_DURATION = 13_140` hrs (1.5 years)
- Resulting PA: Truck ~79%, Shovel ~72%

---

## Acceptance criteria — all met

- [x] `python -m pytest simulation/tests/ -q` — 25 tests pass
- [x] `python -m pytest fitting/tests/ -q` — 20 tests pass (was 21; pm_intervals tests removed)
- [x] `python -m fitting` — runs without error; `fitted_config.py` has 3-level structure
- [x] `USE_FITTED_PARAMS = True` flattens 3-level fitted dict to 2-level before passing to processes
- [x] No reference to old component names (`"engine"`, `"tyres"`, `"hydraulics"`,
  `"transmission"`, `"injectors"`, `"suspension"`, `"swing_ring"`,
  `"boom_pins"`, `"GET"`, `"undercarriage"`) in `config.py`, `truck.py`, or `shovel.py`
- [x] `N_FLEET` in `config.py` matches `N_UNITS` in `fitting/weibull_fit.py`
- [x] No reference to `TRUCK_PREMATURE_FAILURE`, `SHOVEL_PREMATURE_FAILURE`, or `"failed_comp"` in any source file
- [x] `pm_intervals.py` deleted; no PM-interval summary in `__main__.py`


---

## Current state (confirmed by reading source)

### `simulation/src/simulation/config.py`

```python
N_TRUCKS  = 15
N_SHOVELS = 3

TRUCK_PREMATURE_FAILURE = {
    "engine":       {"shape": 2.0, "scale": 12_000, "repair_mean": 240, "repair_sd": 24,  "bay": True},
    "transmission": {"shape": 1.8, "scale":  8_000, "repair_mean": 48,  "repair_sd": 8,   "bay": True},
    "injectors":    {"shape": 2.0, "scale":  4_000, "repair_mean": 8,   "repair_sd": 2,   "bay": True},
    "hydraulics":   {"shape": 1.5, "scale":  2_500, "repair_mean": 12,  "repair_sd": 3,   "bay": True},
    "suspension":   {"shape": 2.0, "scale":  2_000, "repair_mean": 6,   "repair_sd": 1.5, "bay": True},
    "tyres":        {"shape": 2.5, "scale":  3_000, "repair_mean": 3,   "repair_sd": 0.5, "bay": True},
}
SHOVEL_PREMATURE_FAILURE = {
    "engine":        {"shape": 2.0, "scale": 12_000, "repair_mean": 48, "repair_sd": 24,  "bay": True},
    "hydraulics":    {"shape": 1.5, "scale":  2_500, "repair_mean": 16, "repair_sd": 4,   "bay": True},
    "swing_ring":    {"shape": 2.0, "scale":  4_000, "repair_mean": 48, "repair_sd": 12,  "bay": True},
    "boom_pins":     {"shape": 2.2, "scale":  2_000, "repair_mean": 12, "repair_sd": 3,   "bay": True},
    "GET":           {"shape": 1.8, "scale":    600,  "repair_mean": 4,  "repair_sd": 1,   "bay": True},
    "undercarriage": {"shape": 2.5, "scale":  5_000, "repair_mean": 24, "repair_sd": 6,   "bay": True},
}

# Bottom of file:
USE_FITTED_PARAMS = False
if USE_FITTED_PARAMS:
    from fitting.output.fitted_config import (
        TRUCK_PREMATURE_FAILURE_FITTED,
        SHOVEL_PREMATURE_FAILURE_FITTED,
    )
    TRUCK_PREMATURE_FAILURE.update(TRUCK_PREMATURE_FAILURE_FITTED)
    SHOVEL_PREMATURE_FAILURE.update(SHOVEL_PREMATURE_FAILURE_FITTED)
```

### `simulation/src/simulation/fleet.py`

```python
from .config import N_SHOVELS, N_TRUCKS, SHOVEL_PM_SCHEDULE, TRUCK_PM_SCHEDULE

def run_fleet(env, bay, mechanic, rng,
              n_trucks: int = N_TRUCKS,
              n_shovels: int = N_SHOVELS) -> ...:
```

### `simulation/src/simulation/truck.py` (failure TTF loop)

```python
comp_ttf: dict[str, float] = {
    comp: float(cfg["scale"]) * float(rng.weibull(cfg["shape"]))
    for comp, cfg in TRUCK_PREMATURE_FAILURE.items()
}
min_comp    = min(comp_ttf, key=comp_ttf.__getitem__)
min_ttf     = comp_ttf[min_comp]
...
failed_comp = min_comp
...
stats.events.append({..., "failed_comp": failed_comp, ...})
```

### `simulation/src/simulation/shovel.py` (failure TTF loop)

Same pattern as truck, plus an explicit `needs_bay = True` branch for premature
failures, and `bay`-flag-driven `needs_bay` for PM events.

### `simulation/src/simulation/stats.py`

```python
comp_op_hrs: dict[str, list[float]] = defaultdict(list)
for e in self.events:
    if e["type"] == "premature":
        comp = e["name"]   # currently the component string e.g. "tyres"
        ...
# → summary["mtbf_by_component"]
```

### `fitting/output/fitted_config.py` (generated — current format after task 004)

```python
PREMATURE_FAILURE_FITTED = {
    "Cat_793F": {
        "RPR": {"shape": ..., "scale": ..., "repair_mean": ..., "repair_sd": ..., "n": ..., "dur_n": ...},
        "RPL": {...},
        "INS": {...},
        "TYR": {...},
        "OTHER_CM": {...},
    },
    "EH4000":  {...},
    "EH5000":  {...},
    "EX3600":  {"RPR": {...}, "RPL": {...}, "INS": {...}},   # no TYR/OTHER_CM (sparse)
    "EX5600":  {...},
    "EX8000":  {...},
    "L9800":   {...},
}
```

---

## Target state

### `config.py` — single model-keyed failure dict (hand-coded defaults)

Replace the two type-level dicts with a single `PREMATURE_FAILURE` dict keyed
by model.  Values come directly from the fitting output (per-unit `scale_individual_cal`,
corrective `dur_mean`/`dur_sd`).  `bay` key dropped throughout.

```python
PREMATURE_FAILURE: dict[str, dict[str, dict]] = {
    "Cat_793F": {
        "RPR": {"shape": 1.010, "scale":   382, "repair_mean": 4.87, "repair_sd":  9.10},
        "RPL": {"shape": 0.900, "scale":   374, "repair_mean": 5.50, "repair_sd": 13.99},
        "INS": {"shape": 0.968, "scale": 1_068, "repair_mean": 4.28, "repair_sd":  5.41},
        "TYR": {"shape": 1.087, "scale": 2_430, "repair_mean": 6.69, "repair_sd":  5.03},
    },
    "EH4000": {
        "RPR": {"shape": 1.038, "scale":   286, "repair_mean": 5.21, "repair_sd": 11.64},
        "RPL": {"shape": 0.934, "scale":   449, "repair_mean": 5.13, "repair_sd": 11.18},
        "INS": {"shape": 0.918, "scale": 1_468, "repair_mean": 2.98, "repair_sd":  5.83},
        "TYR": {"shape": 1.083, "scale": 2_245, "repair_mean": 8.63, "repair_sd":  6.40},
    },
    "EH5000": {
        "RPR": {"shape": 0.983, "scale":   247, "repair_mean": 5.93, "repair_sd": 10.68},
        "RPL": {"shape": 0.999, "scale":   313, "repair_mean": 6.76, "repair_sd": 13.47},
        "INS": {"shape": 0.894, "scale":   750, "repair_mean": 4.64, "repair_sd":  8.37},
        "TYR": {"shape": 1.088, "scale": 1_798, "repair_mean": 8.04, "repair_sd":  6.00},
    },
    "EX3600": {
        "RPR": {"shape": 0.892, "scale":  207, "repair_mean": 6.54, "repair_sd": 13.64},
        "RPL": {"shape": 0.737, "scale":  159, "repair_mean": 6.05, "repair_sd": 17.56},
        "INS": {"shape": 0.886, "scale":  604, "repair_mean": 3.62, "repair_sd":  9.05},
    },
    "EX5600": {
        "RPR": {"shape": 0.906, "scale":   99, "repair_mean": 5.88, "repair_sd": 15.49},
        "RPL": {"shape": 0.835, "scale":   86, "repair_mean": 5.66, "repair_sd": 19.47},
        "INS": {"shape": 0.921, "scale":  240, "repair_mean": 2.46, "repair_sd":  4.53},
    },
    "EX8000": {
        "RPR": {"shape": 0.696, "scale":  181, "repair_mean": 7.25, "repair_sd": 33.48},
        "RPL": {"shape": 0.634, "scale":  164, "repair_mean": 7.38, "repair_sd": 31.42},
        "INS": {"shape": 0.897, "scale":  951, "repair_mean": 3.90, "repair_sd":  5.15},
    },
    "L9800": {
        "RPR": {"shape": 0.812, "scale":  132, "repair_mean": 4.89, "repair_sd":  7.47},
        "RPL": {"shape": 0.678, "scale":   99, "repair_mean": 6.79, "repair_sd": 13.56},
        "INS": {"shape": 0.889, "scale":  349, "repair_mean": 3.02, "repair_sd":  3.45},
    },
}
```

### `config.py` — fleet size dict

```python
# Before
N_TRUCKS  = 15
N_SHOVELS = 3

# After
N_FLEET = {
    "Cat_793F": 56,
    "EH4000":   19,
    "EH5000":   24,
    "EX3600":    8,
    "EX5600":    5,
    "EX8000":    3,
    "L9800":     2,
}

_TRUCK_MODELS  = ("Cat_793F", "EH4000", "EH5000")
_SHOVEL_MODELS = ("EX3600", "EX5600", "EX8000", "L9800")

N_TRUCKS  = sum(N_FLEET[m] for m in _TRUCK_MODELS)   # 99
N_SHOVELS = sum(N_FLEET[m] for m in _SHOVEL_MODELS)  # 18
```

`N_TRUCKS` and `N_SHOVELS` are kept as derived module-level names so existing
test imports do not break.

> `N_UNITS` in `fitting/weibull_fit.py` uses the same counts and is the source
> of truth for IFT scaling.  `N_FLEET` must stay in sync with it.

### `config.py` — `USE_FITTED_PARAMS` block

```python
USE_FITTED_PARAMS = False

if USE_FITTED_PARAMS:
    try:
        from fitting.output.fitted_config import PREMATURE_FAILURE_FITTED
        PREMATURE_FAILURE = PREMATURE_FAILURE_FITTED
    except (ImportError, KeyError):
        warnings.warn(
            "USE_FITTED_PARAMS=True but fitted_config.py not found or "
            "model key missing. Using hand-coded defaults."
        )
```

The entire nested dict is swapped in wholesale — no per-model selection needed
because `fleet.py` now iterates over model keys directly.
The `n` and `dur_n` keys present in fitted entries are ignored by the simulation.

---

## Changes required

### 1. `simulation/src/simulation/config.py`

- Replace `N_TRUCKS` / `N_SHOVELS` literal constants with `N_FLEET` per-model
  dict; derive `N_TRUCKS` / `N_SHOVELS` from it (keep names exported).
- Remove `TRUCK_PREMATURE_FAILURE` and `SHOVEL_PREMATURE_FAILURE`; add single
  `PREMATURE_FAILURE` nested dict as shown above (drop `bay` key everywhere).
- Export `_TRUCK_MODELS` and `_SHOVEL_MODELS` tuples (fleet.py needs them).
- Rewrite the `USE_FITTED_PARAMS` block to assign `PREMATURE_FAILURE` wholesale.

### 2. `simulation/src/simulation/fleet.py`

Change the spawn loop from a flat count to a model-typed iteration:

```python
# Before
from .config import N_SHOVELS, N_TRUCKS, SHOVEL_PM_SCHEDULE, TRUCK_PM_SCHEDULE

for i in range(n_trucks):
    ...truck_process(env, f"Truck-{i}", bay, mechanic, stats, rng, pm_offsets=pm_offsets)

for i in range(n_shovels):
    ...shovel_process(env, f"Shovel-{i}", bay, mechanic, stats, rng, pm_offsets=pm_offsets)

# After
from .config import (
    N_FLEET, _TRUCK_MODELS, _SHOVEL_MODELS,
    PREMATURE_FAILURE,
    SHOVEL_PM_SCHEDULE, TRUCK_PM_SCHEDULE,
)

unit = 0
for model in _TRUCK_MODELS:
    for _ in range(N_FLEET[model]):
        truck_rng = np.random.default_rng(rng.integers(0, 2**32))
        pm_offsets = _stagger(TRUCK_PM_SCHEDULE, truck_rng)
        stats = TruckStats(name=f"Truck-{unit}({model})")
        truck_stats.append(stats)
        env.process(
            truck_process(
                env, stats.name, bay, mechanic, stats, truck_rng,
                pm_offsets=pm_offsets,
                failure_cfg=PREMATURE_FAILURE[model],
            )
        )
        unit += 1

unit = 0
for model in _SHOVEL_MODELS:
    for _ in range(N_FLEET[model]):
        shovel_rng = np.random.default_rng(rng.integers(0, 2**32))
        pm_offsets = _stagger(SHOVEL_PM_SCHEDULE, shovel_rng)
        stats = ShovelStats(name=f"Shovel-{unit}({model})")
        shovel_stats.append(stats)
        env.process(
            shovel_process(
                env, stats.name, bay, mechanic, stats, shovel_rng,
                pm_offsets=pm_offsets,
                failure_cfg=PREMATURE_FAILURE[model],
            )
        )
        unit += 1
```

The `n_trucks` / `n_shovels` default parameters on `run_fleet` can be
removed; the counts are now fully determined by `N_FLEET`.
The `run_phase1` helper that spawns a single truck should pass
`failure_cfg=PREMATURE_FAILURE["Cat_793F"]` explicitly.

### 3. `simulation/src/simulation/truck.py`

Add a `failure_cfg` keyword parameter and use it instead of the module-level
import.  Remove the `TRUCK_PREMATURE_FAILURE` import.

```python
# Signature change
def truck_process(
    env, name, bay_resource, mechanic_resource, stats, rng,
    *, pm_offsets=None,
    failure_cfg: dict | None = None,   # ← new
):
    if failure_cfg is None:
        from .config import PREMATURE_FAILURE   # fallback for phase-1 direct calls
        failure_cfg = PREMATURE_FAILURE["Cat_793F"]
```

Replace `TRUCK_PREMATURE_FAILURE` references in the body:

```python
# Before
comp_ttf: dict[str, float] = {
    comp: float(cfg["scale"]) * float(rng.weibull(cfg["shape"]))
    for comp, cfg in TRUCK_PREMATURE_FAILURE.items()
}
min_comp    = min(comp_ttf, key=comp_ttf.__getitem__)
min_ttf     = comp_ttf[min_comp]
...
failed_comp = min_comp
...
{"failed_comp": failed_comp}

# After
ag_ttf: dict[str, float] = {
    ag: float(cfg["scale"]) * float(rng.weibull(cfg["shape"]))
    for ag, cfg in failure_cfg.items()
}
failed_ag = min(ag_ttf, key=ag_ttf.__getitem__)
min_ttf   = ag_ttf[failed_ag]
...
# (no separate failed_ag assignment — already set above)
...
{"activity_group": failed_ag}
```

Also replace the duration lookup that currently reads `TRUCK_PREMATURE_FAILURE[event_name]`
with `failure_cfg[event_name]`.

### 4. `simulation/src/simulation/shovel.py`

Same changes as truck.py:
- Add `failure_cfg` parameter with fallback to `PREMATURE_FAILURE["EX3600"]`.
- Remove `SHOVEL_PREMATURE_FAILURE` import.
- Rename `comp_ttf`/`min_comp`/`failed_comp` → `ag_ttf`/`failed_ag`.
- Replace `SHOVEL_PREMATURE_FAILURE[event_name]` → `failure_cfg[event_name]`.
- `"failed_comp"` key → `"activity_group"` in `stats.events`.

The `needs_bay = True` lines for premature failures stay as-is — PM schedule
entries still carry the `bay` flag; only premature failure entries drop it.

### 5. `simulation/src/simulation/stats.py`

Rename the internal variable and the summary dict key:

```python
# Before
comp_op_hrs: dict[str, list[float]] = defaultdict(list)
for e in self.events:
    if e["type"] == "premature":
        comp = e["name"]
        ...
# → summary["mtbf_by_component"]

# After
ag_op_hrs: dict[str, list[float]] = defaultdict(list)
for e in self.events:
    if e["type"] == "premature":
        ag = e["name"]   # e["name"] is now the activity group code
        ...
# → summary["mtbf_by_activity_group"]
```

### 6. Tests

**`simulation/tests/test_phase1.py`**

- `summary["mtbf_by_component"]` → `summary["mtbf_by_activity_group"]`.
- Loop variable `comp` → `ag`; lookup changes to
  `PREMATURE_FAILURE["Cat_793F"][ag]["scale"]`.
- Update import: `TRUCK_PREMATURE_FAILURE` → `PREMATURE_FAILURE`.

**`simulation/tests/test_phase3.py`**

No import change needed — `N_TRUCKS` and `N_SHOVELS` are still exported from
`config.py` (now derived from `N_FLEET`).  Assertions remain as-is:

```python
assert len(fleet.trucks)  == N_TRUCKS
assert len(fleet.shovels) == N_SHOVELS
```

---

## Acceptance criteria

- `python -m pytest simulation/tests/ -q` — all 25 tests pass.
- `python -m pytest fitting/tests/ -q` — all 21 tests pass.
- `python -m fitting` — runs without error; `fitted_config.py` contains
  `PREMATURE_FAILURE_FITTED` (nested by model).
- Setting `USE_FITTED_PARAMS = True` in `config.py` and running
  `python -m pytest simulation/tests/ -q` passes all 25 tests.
- Each model's processes draw Weibull TTFs from that model's fitted parameters
  (confirmed by inspecting `failure_cfg` passed to truck/shovel processes).
- No reference to old component names (`"engine"`, `"tyres"`, `"hydraulics"`,
  `"transmission"`, `"injectors"`, `"suspension"`, `"swing_ring"`,
  `"boom_pins"`, `"GET"`, `"undercarriage"`) remains in `config.py`,
  `truck.py`, or `shovel.py`.
- `N_FLEET` in `config.py` is a per-model dict matching `N_UNITS` in
  `fitting/weibull_fit.py`; `N_TRUCKS`/`N_SHOVELS` are derived from it.
- No reference to `TRUCK_PREMATURE_FAILURE` or `SHOVEL_PREMATURE_FAILURE`
  remains in any source file.
- No reference to `"failed_comp"` remains in any source file.
