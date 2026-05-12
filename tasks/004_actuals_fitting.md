# Task 004 — Actuals Fitting Module

## Goal

Replace the assumed Weibull / Normal parameters in `config.py` with values
fitted directly from the work order actuals in
`actuals/am_work_order_vw.xlsx`.  The fitting pipeline lives in a standalone
`fitting/` package so it can be re-run whenever the actuals extract is
refreshed, producing an updated `fitted_config.py` that the simulation imports
in place of (or alongside) the hand-coded defaults.

---

## Source data

| File | Rows | Key columns |
|------|------|-------------|
| `actuals/am_work_order_vw.xlsx` | 48,604 | `order_type_description`, `maintenance_activity_type_id`, `level_4_asset_description`, `actual_start_timestamp`, `sum_actual_hours` |

### Dimension mapping

| `order_type_description` | `maintenance_activity_type_id` | Model event type |
|--------------------------|-------------------------------|-----------------|
| Corrective | RPR, RPL, INS, TYR | `corrective` — Weibull IFT + repair duration |
| Preventive | RPL, SVC, NDT, INS, TYR, CAS | `preventive` — Weibull IFT + PM duration |

Both `corrective` and `preventive` orders are fitted with Weibull IFTs.  The
simulation draws TTF from each `(model, order_type_group, activity_group)`
entry independently and takes the earliest to determine the next maintenance
event.  The hardcoded `PM_A/PM_B/…` schedule is replaced entirely.

### Fleet-type mapping

Fitting runs at the **model** level (`level_4_asset_description`). A short
model key is derived in `load.py` for use as Python dict keys. `equip_type`
is retained as a secondary grouping column.

| `level_4_asset_description` | `model` (short key) | `equip_type` |
|-----------------------------|--------------------|--------------|
| Caterpillar 793F Dump Truck Fleet | `Cat_793F` | truck |
| Hitachi EH4000 Dump Truck Fleet | `EH4000` | truck |
| Hitachi EH5000 Dump Truck Fleet | `EH5000` | truck |
| Hitachi EX3600 Excavator Fleet | `EX3600` | shovel |
| Hitachi EX5600 Excavator Fleet | `EX5600` | shovel |
| Hitachi EX8000 Excavator Fleet | `EX8000` | shovel |
| Liebherr 9800 Excavator Fleet | `L9800` | shovel |

### Fleet-level IFT → per-unit scale

Without individual unit identifiers we compute IFTs at the **fleet level**:
time between consecutive corrective events across all units of a given
`equip_type` and `activity_group`.  The fleet-level event rate equals
`N_units × individual_rate`, so:

```
scale_individual_cal = scale_fleet_cal × N_units
```

Fleet sizes from actuals:

| `level_4_asset_description` | units | `equip_type` |
|-----------------------------|-------|--------------|
| Caterpillar 793F Dump Truck Fleet | 56 | truck |
| Hitachi EH4000 Dump Truck Fleet | 19 | truck |
| Hitachi EH5000 Dump Truck Fleet | 24 | truck |
| Hitachi EX3600 Excavator Fleet | 8 | shovel |
| Hitachi EX5600 Excavator Fleet | 5 | shovel |
| Hitachi EX8000 Excavator Fleet | 3 | shovel |
| Liebherr 9800 Excavator Fleet | 2 | shovel |

Aggregated `N_units` used in scaling:
- **truck**: 56 + 19 + 24 = **99**
- **shovel**: 8 + 5 + 3 + 2 = **18**

### Calendar → operating hours conversion

Scale is in calendar hours.  Convert to operating hours:
`scale_op = scale_individual_cal × mean_utilisation`
(util_factor = 1.0 initially, configurable).  Refine when SMU data arrives.

---

## Deliverables

1. **`fitting/src/fitting/load.py`** — load and clean the work orders Excel
   file; parse timestamps; map `level_4_asset_description` → `model` (short
   key, e.g. `"Cat_793F"`) and → `equip_type` (`"truck"` / `"shovel"`);
   derive `order_type_group` from `order_type_description` (`"Corrective
   Maintenance Order"` → `"corrective"`, `"Preventive Maintenance Order"` →
   `"preventive"`, others → `"other"`); filter to completed orders
   (`completed_flag == 1`); filter `actual_start_timestamp <= today` to
   exclude future-dated data quality anomalies (planned orders incorrectly
   marked complete); drop rows where `model` is null.

3. **`fitting/src/fitting/ift.py`** — compute model-level inter-failure times
   per `(model, order_type_group, activity_group)` from **both corrective and
   preventive** work orders:
   - Filter to `order_type_group in ('corrective', 'preventive')` (exclude `'other'`)
   - Add `activity_group` column per order type:
     - Corrective: `TYR` → `TYR`, `RPR` → `RPR`, `RPL` → `RPL`, `INS` → `INS`,
       all others (`SVC`, `CAS`, `NDT`) → `OTHER_CM`
     - Preventive: `RPL` → `RPL`, `SVC` → `SVC`, `NDT` → `NDT`, `INS` → `INS`,
       `TYR` → `TYR`, `CAS` → `CAS`, all others → `OTHER_PM`
   - Deduplicate on `work_order_id`
   - Sort by `(model, order_type_group, activity_group, actual_start_timestamp)`
   - `groupby(['model', 'order_type_group', 'activity_group']).diff()` on timestamps
   - Convert to hours, apply `> 0.5h` floor
   - Return tidy DataFrame with columns
     `[model, equip_type, order_type_group, activity_group, ift_hrs]`

4. **`fitting/src/fitting/weibull_fit.py`** — fit `Weibull(shape, scale_fleet_cal)`
   via MLE (`scipy.stats.weibull_min` with `floc=0`) per `(model,
   order_type_group, activity_group)`; look up `N_units` from the per-model
   dict; scale up: `scale_individual_cal = scale_fleet_cal × N_units`; apply
   utilisation: `scale_op = scale_individual_cal × util_factor`; require
   minimum 30 samples; groups below the threshold are silently omitted; return
   a DataFrame with columns `[model, equip_type, order_type_group,
   activity_group, shape, scale_fleet_cal, scale_individual_cal, scale_op,
   n_units, util_factor, n]`.

4. **`fitting/src/fitting/duration_fit.py`** — compute Normal `(mean, sd)` for
   `sum_actual_hours` per `(model, order_type_group, activity_group)`
   where `order_type_group` is the column derived in `load.py` (`"corrective"`
   or `"preventive"`); filter `sum_actual_hours > 0`; return a DataFrame with
   columns `[model, equip_type, order_type_group, activity_group, dur_mean, dur_sd, n]`.

5. **`fitting/src/fitting/pm_intervals.py`** — compute model-level inter-PM
   times per `(model, maintenance_activity_type_id)` from `Preventive`
   orders: (1) deduplicate on `work_order_id`; (2) sort by
   `actual_start_timestamp`; (3) diff consecutive events within each group;
   (4) apply `> 0.5h` floor; scale to per-unit using per-model `N_units`;
   return median per-unit interval per `(model, maintenance_activity_type_id)`.

6. **`fitting/src/fitting/export_config.py`** — write
   `fitting/output/fitted_config.py`, a drop-in Python module containing a
   single nested dict `PREMATURE_FAILURE_FITTED` keyed by model, then
   `order_type_group`, then `activity_group`:
   ```python
   PREMATURE_FAILURE_FITTED = {
       "Cat_793F": {
           "corrective": {
               "RPR": {"shape": ..., "scale": ..., "repair_mean": ..., "repair_sd": ...},
               "RPL": {...},
               ...
           },
           "preventive": {
               "RPL": {"shape": ..., "scale": ..., "repair_mean": ..., "repair_sd": ...},
               "SVC": {...},
               ...
           },
       },
       "EH4000": {...},
       ...
   }
   ```
   The `pm_intervals.py` module and `PM_INTERVALS_FITTED` output are **removed** —
   preventive intervals are fully captured by the Weibull fits above.  Include
   a header comment with fit date, sample counts per model, and the utilisation
   assumption used.  **Missing combinations** are silently omitted.

7. **`fitting/src/fitting/__main__.py`** — CLI entry point: `python -m fitting`
   runs the full pipeline and prints a fit summary table to stdout.

8. **`fitting/pyproject.toml`** — flit-based package config; dependencies:
   `pandas`, `openpyxl`, `scipy`, `numpy`.

9. **`simulation/src/simulation/config.py`** — add an import toggle:
   ```python
   USE_FITTED_PARAMS = False  # set True to use actuals-fitted values
   ```
   When `True`, load from `fitting/output/fitted_config.py` and override the
   premature-failure and PM-schedule dicts.

10. **`fitting/tests/test_fitting.py`** — pytest tests covering:
    - IFT computation produces positive values
    - Weibull shape > 0 and scale > 0 for each group with sufficient data
    - Duration mean > 0 for each group
    - Output config file is valid Python and importable

---

## Folder layout

```
fitting/
    pyproject.toml
    src/
        fitting/
            __init__.py
            __main__.py
            load.py
            ift.py
            weibull_fit.py
            duration_fit.py
            pm_intervals.py
            export_config.py
    output/
        fitted_config.py    ← generated, not committed
    tests/
        test_fitting.py
```

---

## Step-by-step plan

### Step 1 — Package scaffold
Create `fitting/pyproject.toml` and `fitting/src/fitting/__init__.py`.
Install in editable mode.

### Step 2 — `load.py`
- Read Excel, parse timestamps
- Map `level_4_asset_description` → `model` (short key) and → `equip_type`
- Derive `order_type_group`: `"Corrective Maintenance Order"` → `"corrective"`,
  `"Preventive Maintenance Order"` → `"preventive"`, all others → `"other"`
- Filter: `completed_flag == 1`
- Filter: `actual_start_timestamp <= pd.Timestamp.now(tz='UTC')` — excludes
  future-dated rows (planned orders incorrectly marked complete; these would
  inject false long IFTs into the fitting data)
- Drop rows where `model` is null (unknown fleet)

### Step 3 — `ift.py`
- Filter to `order_type_group in ('corrective', 'preventive')`
- Add `activity_group` column per order type:
  - Corrective: `TYR` → `TYR`; `RPR` → `RPR`; `RPL` → `RPL`; `INS` → `INS`;
    all others (`SVC`, `CAS`, `NDT`) → `OTHER_CM`
  - Preventive: `RPL` → `RPL`; `SVC` → `SVC`; `NDT` → `NDT`; `INS` → `INS`;
    `TYR` → `TYR`; `CAS` → `CAS`; all others → `OTHER_PM`
- **Deduplicate on `work_order_id`** — primary mechanism against re-logged entries
- Sort by `(model, order_type_group, activity_group, actual_start_timestamp)`
- `groupby(['model', 'order_type_group', 'activity_group']).diff()` on timestamps
- Convert to hours, apply `> 0.5h` floor only

> **Rationale**: grouping by `model` rather than `equip_type` gives separate
> Weibull fits per machine type at the cost of smaller sample counts per group.
> All model sub-fleets have enough volume to exceed the 30-sample minimum except
> possibly `L9800` (2 units) for low-frequency groups — those are skipped with
> a warning.

### Step 4 — `weibull_fit.py`
- Group by `(model, order_type_group, activity_group)`
- `weibull_min.fit(data, floc=0)` — MLE with location fixed at 0
- Look up `N_units` from per-model dict:
  `{"Cat_793F": 56, "EH4000": 19, "EH5000": 24, "EX3600": 8, "EX5600": 5, "EX8000": 3, "L9800": 2}`
- `scale_individual_cal = scale_fleet_cal × N_units`
- `scale_op = scale_individual_cal × util_factor` (1.0 initially)
- Skip groups with < 30 samples, warn with model/order_type_group/activity_group name

### Step 5 — `duration_fit.py`
- Filter `sum_actual_hours > 0`
- Group by `(model, order_type_group, activity_group)`
- Compute `mean`, `std`, `n`
- Clip `sd` to minimum 0.1 to avoid degenerate Normal

### Step 6 — `pm_intervals.py` — REMOVED
This module is no longer needed.  Preventive maintenance intervals are fully
captured by the Weibull IFT fits in `ift.py` + `weibull_fit.py`.  Delete the
file and remove its import from `__main__.py`.

### Step 7 — `export_config.py`
- Build nested dict: `PREMATURE_FAILURE_FITTED[model][order_type_group][activity_group]`
- Write `fitting/output/fitted_config.py` with `pprint`-formatted dict
- Include generation timestamp, per-model sample counts, and util_factor in header
- `PM_INTERVALS_FITTED` is no longer written

### Step 8 — `__main__.py` CLI
- Call all steps in sequence (load → ift → weibull_fit → duration_fit → export_config)
- Remove `compute_pm_intervals` call
- Print a summary table: model × order_type_group × activity_group → shape, scale_op, dur_mean

### Step 9 — `config.py` toggle + simulation PM schedule replacement
- Add `USE_FITTED_PARAMS = False`
- When `True`, load `PREMATURE_FAILURE_FITTED` from `fitting/output/fitted_config.py`
  and set `PREMATURE_FAILURE = PREMATURE_FAILURE_FITTED`
- **Remove** `TRUCK_PM_SCHEDULE`, `SHOVEL_PM_SCHEDULE`, and all hardcoded PM interval
  constants — the simulation no longer uses fixed-interval PMs when fitted params
  are active.  Both corrective and preventive events are driven by Weibull TTF draws.
- When `USE_FITTED_PARAMS = False`, the existing `PREMATURE_FAILURE` dict (corrective
  only) is used and the truck/shovel process loops retain their current structure.

### Step 10 — Tests
- `test_fitting.py`: smoke tests for each module

---

## Acceptance criteria

- `python -m fitting` runs without error and produces `fitting/output/fitted_config.py`
- Weibull fits present for corrective at least: `Cat_793F/corrective/RPR`,
  `Cat_793F/corrective/RPL`, `Cat_793F/corrective/TYR`, `EX3600/corrective/RPR`
- Weibull fits present for preventive at least: `Cat_793F/preventive/RPL`,
  `Cat_793F/preventive/SVC`, `Cat_793F/preventive/INS`
- Groups with < 30 samples are silently omitted — no `KeyError` or `NaN` in output
- Duration mean > 0 for every group
- `fitted_config.py` is importable; `PREMATURE_FAILURE_FITTED` is a three-level
  nested dict: `model → order_type_group → activity_group`
- `USE_FITTED_PARAMS = True` in `config.py` runs the full simulation without error
- All existing simulation tests still pass (25/25)
- `pm_intervals.py` is deleted; no reference to `PM_INTERVALS_FITTED` remains
