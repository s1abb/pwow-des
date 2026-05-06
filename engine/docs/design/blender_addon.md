<!--
Revised design & roadmap for the Blender add-on (handler-based playback).

This document replaces the previous design note and brings it up to date with
the current repository state as of the last edits. It records what is already
implemented, what was recently fixed, and gives a tuned phase plan with
concrete next actions and tests.
-->

# Blender Addon — Handler-based Playback (revised plan)

Summary
-------
We drive Blender playback from an in-memory (or HDF5-backed) runtime cache and a
frame-change handler instead of baking keyframes. The handler updates object
transforms per-frame from NumPy arrays (positions, optionally rotations), which
enables instant scrubbing, adjustable speed, and much lower disk churn.

This file documents the current implementation status, recent fixes, and a
refined phased plan. It emphasizes small, testable steps and clear quality gates.

Current status (what's implemented now)
--------------------------------------
- Core runtime cache: `addon/utils/runtime_cache.py` loads timelines into
  NumPy arrays (actors, rotations, times, sample_dt) and exposes `load_timeline_to_cache`,
  `clear_cache`, and `is_loaded`.
- Frame handler: `addon/handlers/timeline_playback.py` provides `timeline_frame_update`,
  `enable()`, `disable()`, and `reload()` helpers. The handler computes sim_time
  from `scene.frame_current`, `scene.render.fps` and `scene.timeline_speed_factor`.
  The module already contains interpolation logic (alpha-based) and attempts to
  use `mathutils.Quaternion.slerp` when available.
- Import operator: `addon/operators/timeline_import.py` loads JSON/HDF5 timelines,
  creates actor objects (via `addon/utils/objects.py`), stores a few scene metadata
  fields (`timeline_file_size_mb`, `timeline_sample_dt`) and loads data into the
  runtime cache, then enables the handler.
- Loader & HDF5 fallback: `addon/utils/timeline.py` supports `.json` and `.h5`.
  It will use `h5py` inside Blender when available, otherwise call a venv/system
  python to run the engine HDF5 handler as a subprocess. If an HDF5 load fails,
  it falls back to an same-named `.json` file if present.
- Logging & properties: `addon/utils/logging.py` and `addon/utils/properties.py`
  provide a resilient logging configuration and register the `Scene` properties
  (`timeline_speed_factor`, `timeline_interpolate`, `timeline_actor_default_radius`, etc.).
- Addon packaging & UI: We added `addon/__init__.py` (safe `bl_info`, `register`/`unregister`)
  and `addon/ui/panels.py` (minimal N-panel). The UI was adjusted to guard access
  to scene properties so the panel doesn't trigger RNA warnings when Blender draws
  the UI before properties have been registered.
- Tests: Unit and integration tests exist under `addon/tests/` and engine `tests/`.
  On the development environment the full test suite passes (85 passed at the
  time of the last run).

Recent fixes
------------
- Moved to a safe import pattern: the UI package no longer imports panels at
  top-level to avoid running UI drawing code before `register()` executes.
- Guarded panel properties in `addon/ui/panels.py` to prevent Blender console
  warnings like: "rna_uiItemR: property not found: Scene.timeline_interpolate".
- Added `addon/__init__.py` to provide a robust Blender registration entrypoint
  that is import-safe outside Blender (useful for tests and CI).

Why we tuned the plan
---------------------
The earlier plan assumed some UI and interpolation work would be implemented
later; in practice core interpolation exists in the handler and the minimal UI
and registration were added earlier to enable iterative testing. The revised
plan reduces duplication, sharpens test coverage goals, and moves performance
and HDF5 mmap work into a later phase with explicit quality gates.

Phased plan (revised)
---------------------
Phase A — Core (done)
- Runtime cache and handler are implemented and unit-tested. Keep these files
  small and well-covered by unit tests.

Phase B — Operator wiring + basic UI (done)
- Import operator loads timelines into the cache and creates actor objects.
- Minimal N-panel added (Play/Import/Play/Pause placeholders). The panel is
  defensive against missing properties.

Phase C — Interpolation validation & tests (now)
Goal: verify interpolation and rotation handling are correct across edge cases
and make small improvements where necessary.
Tasks:
- Add unit tests that exercise interpolation behavior in `addon/handlers`:
  - linear position interpolation accuracy at alpha near 0, 0.5, and 1.0
  - quaternion slerp is used when `mathutils` is available; verify fallback
    linear-component interpolation behaves plausibly when `mathutils` missing
  - missing rotations: handler should skip or use Euler fallback without error
- Sanity-check handler reading of `timeline_interpolate` (toggle on/off)
- Ensure `is_enabled()`/`enable()` remain idempotent across repeated calls

Phase D — UI & developer ergonomics
Goal: make the panel fully usable and add convenience operators.
Tasks:
- Expand `addon/ui/panels.py` with:
  - a file selector or operator that opens Blender file selector for timeline import
  - a Play/Pause toggle that reflects handler state
  - Loop toggle (`timeline_loop`) and live speed slider
  - status area (frames count, sample_dt, file size)
- Add operators: `blenderdes.reload_timeline`, `blenderdes.clear_timeline_cache`,
  `blenderdes.disable_timeline` and wire them to the panel
- Add small UI tests (pure-Python tests that import panel and call draw with a
  fake `context` to assert no exceptions and no RNA warnings)

Phase E — Large-file / performance
Goal: support large timelines and optimize per-frame cost.
Tasks:
- Add an HDF5 mmap/read-on-demand mode: `load_timeline_to_cache(..., mmap=True)`
  that keeps `h5py` datasets open and reads slices on demand. Document that it
  requires `h5py` inside Blender (or rely on venv subprocess for import-time
  parsing + JSON fallback).
- Profile handler costs on realistic timelines; if necessary:
  - reduce Python overhead, batch compute lookups where possible
  - add a small LRU per-actor sample cache to avoid repeated h5py seeks
  - throttle heavy UI operations (e.g., avoid building expensive lists every frame)

Phase F — CI and Blender smoke tests
Goal: make sure the repo stays green and Blender integration is validated.
Tasks:
- Add a GitHub Actions workflow that runs `pytest` in the repo venv (fast,
  verifies pure-Python unit tests).
- Maintain a separate Blender smoke-test runner (optional) that:
  - runs Blender in headless/dev mode, installs/links the add-on, imports a
    small example HDF5/JSON timeline, enables handler, scrubs frames and
    verifies objects are transformed (this probably runs on a dedicated
    machine or is an optional job due to Blender binary size).

Data contract (unchanged)
------------------------
- Timeline (engine format): top-level dict with `metadata`, `frames` and
  optional `actors` metadata. `metadata.sample_dt` must be present for correct
  playback timing.
- Runtime cache shape: same as before (SIM_CACHE dict with `actors`, `rotations`,
  `times`, `sample_dt`, `loaded`, `meta`).

Quality gates
-------------
- All unit tests pass (`pytest`).
- No RNA warnings from UI when the add-on is enabled and the N-panel is
  displayed (we guarded property access already).
- Handler idempotence: enabling twice does not register duplicate handlers.
- HDF5 fallback: if `h5py` not present in Blender, fallback to venv subprocess
  / same-name JSON behavior occurs with a clear log message.

Concrete next action (recommended)
---------------------------------
Implement Phase C (interpolation validation & tests). It's small, testable,
and directly raises the playback quality. Steps I will take if you approve:
1. Add unit tests targeting `addon/handlers/timeline_playback.py` to cover:
   - position interpolation at alpha 0/0.5/1
   - quaternion interpolation path and fallback behavior
   - behavior when `timeline_interpolate` is False
2. Run the full test suite and fix any uncovered edge cases discovered by the
   tests.
3. Optionally, add a small integration-style test that runs `operators.timeline_import`
   in a fake-BPY context and asserts the cache was populated and handler enabled.

If you prefer UI work first, I can switch to Phase D and add the improved
panel and convenience operators instead.

Timing estimates (refined)
-------------------------
- Phase C: 1–3 hours (tests + small fixes).
- Phase D: 2–4 hours (UI polish + operators + tests).
- Phase E: 1–3 days depending on dataset size and `h5py` integration complexity.

Notes & open questions
----------------------
- Do you want the HDF5 mmap mode implemented now, or deferred until we
  can run larger timelines in Blender for profiling?
- Should we add an explicit feature flag to let users pick between bake vs
  handler playback while we complete rollout?

If you approve, I'll implement the Phase C test additions and any small
handler fixes they reveal. Otherwise, tell me which phase you'd like to
prioritize and I'll start there.

