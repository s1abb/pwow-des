# Blender Add-on UI: Phase D Plan

This document describes a small, iterative plan to improve the Blender add-on UI
(the N-panel) in safe, testable steps. Make one change at a time and test it in
Blender (VS Code dev add-in). I will implement each step and you can verify the
change in Blender and give feedback.

Each step below lists the goal, files to change, how to test in Blender, local
pytest ideas, acceptance criteria and an estimated time.

---

## Step D.0 — Log file location & level selector (new first step)

- Goal: allow users to choose where the add-on writes its runtime `timeline.log` file,
  select a minimal log level for console output, and recreate the log file in the
  chosen location when they press Apply. The default path should be an accessible
  temporary location (system temp directory).
- Why first: logging is useful for debugging during UI iteration and import work;
  having an easily accessible place to configure log output avoids hunting for
  logs and makes testing clearer.

Files to change
- `addon/ui/panels.py` — add a file selector (file-path field or operator invoke)
  for the log file path, a log level drop-down (DEBUG/INFO/WARNING/ERROR), and an
  "Apply" button that triggers reconfiguration of the logger.
- `addon/utils/properties.py` — add `blenderdes_log_path` (StringProperty with
  default to a temp file) and `blenderdes_log_level` (EnumProperty) if not already
  present (they exist but ensure defaults and descriptors are set correctly).
- `addon/utils/logging.py` — expose a small helper (already present) to
  `teardown()` and `setup_log(file_path, file_level, stream_level)`; ensure the
  code will recreate/truncate the log file on Apply and is safe to call at runtime.
- `addon/operators/timeline_import.py` — optional: if desired, update import
  operator to use the selected scene logging settings (already implemented partially).

Local tests
- Unit test that calls `addon.utils.logging.setup_log()` with a temporary
  path (use `tempfile.gettempdir()` or `tmp_path` fixture) and verifies the file
  is created and contains expected header lines or that handlers exist on the
  logger. Also test `teardown()` followed by `setup_log()` to ensure recreate works.

Blender test (Dev Add-in)
1. Start Blender via the VS Code dev add-in and enable the add-on.
2. Open the Timeline panel in the 3D View sidebar.
3. In the logging section enter a file path (or use the file selector) — the
   default should be a temp path like `%TEMP%/blenderdes.log` on Windows.
4. Choose a log level from the dropdown (DEBUG, INFO, WARNING, ERROR).
5. Click Apply. The add-on should:
   - Recreate/truncate the selected log file (zero-length or with a small header)
   - Reconfigure the logger so subsequent actions write to that file at the
     chosen levels.
6. Trigger an importer action or a small log event and confirm the log file
   receives output at the expected level.

Acceptance criteria
- The file selector and dropdown appear and accept user input.
- Clicking Apply recreates the file path (creates parent dirs if needed) and
  reconfigures logging without causing errors.
- No sensitive data is written by default; the log file location is user-chosen.

Estimated time: 20–40 minutes

Notes / UX details
- Default path: use Python's `tempfile.gettempdir()` and name the file
  `blenderdes.log` (e.g., `C:\Users\<user>\AppData\Local\Temp\blenderdes.log`).
- The Apply button should call `addon.utils.logging.teardown()` then
  `addon.utils.logging.setup_log(...)`. If file recreation fails (permissions),
  show a small error report in Blender or fallback to console logging.
- Creating/truncating the file should be done carefully (create parent dirs if
  necessary, open with `w` then close) and be resilient to race conditions.

---

## Step D.1 — Play / Pause toggle (reflect handler state)

- Goal: show a single button labelled "Play" or "Pause" depending on whether the
  playback handler is enabled. Clicking toggles the handler state.
- Why first: low risk, quick UX improvement that gives immediate feedback.

Files to change
- `addon/ui/panels.py` — replace the static Play/Pause layout with a dynamic
  toggle that checks `addon.handlers.timeline_playback.is_enabled()` and shows
  the appropriate operator (`blenderdes.play_timeline` or
  `blenderdes.pause_timeline`).

Local tests
- Add a pure‑Python test that fakes `bpy` and `addon.handlers.timeline_playback.is_enabled()`
  and calls the panel's `draw()` to ensure no exceptions are raised.

Blender test (Dev Add-in)
1. Launch Blender via the VS Code dev add‑in and enable the add‑on.
2. Open *View3D → Sidebar → Timeline* panel.
3. Confirm the button shows "Play" when the handler is disabled.
4. Click "Play" → handler should enable and the button should change to "Pause".
5. Click "Pause" → handler should disable and the button should change back to "Play".

Acceptance criteria
- No RNA warnings in the console.
- Button label updates correctly.
- Handler actually toggles on Play/Pause (verify via runtime behavior or logs).

Estimated time: 15–30 minutes

---

## Step D.2 — Status row (handler + timeline info)

- Goal: add a compact status row showing handler state (On/Off), `sample_dt` and
  frame count (when a timeline is loaded).

Files to change
- `addon/ui/panels.py` — add a small status area that reads
  `addon.handlers.timeline_playback.is_enabled()` and `addon.utils.runtime_cache.SIM_CACHE`
  (`sample_dt`, `times` length).

Local tests
- Unit test that manipulates `runtime_cache.SIM_CACHE` and confirms the panel
  text formatting code runs without raising.

Blender test
- Import a small timeline. The panel should show `sample_dt` and frame count.
- Toggling the handler should update the handler status display.

Estimated time: 20–40 minutes

---

## Step D.3 — Interpolate & Loop toggles (Scene props)

- Goal: expose `timeline_interpolate` (already present) and add a new
  `timeline_loop` property, both as toggles in the panel.

Files to change
- `addon/utils/properties.py` — ensure `timeline_interpolate` exists and add
  `timeline_loop` (Boolean property).
- `addon/ui/panels.py` — add UI toggles bound to the Scene properties.

Local tests
- Unit tests that set the Scene properties and call `timeline_frame_update` to
  assert interpolation and loop behavior (for loop you may need a small handler
  change; we can add that if desired).

Blender test
- Toggle Interpolate on/off and verify the handler interpolates positions when
  enabled.
- Toggle Loop: when the playback reaches the end it should wrap to the start
  (this may require a tiny handler change; we'll add it if desired).

Estimated time: 30–60 minutes (longer if loop logic must be added)

---

## Step D.4 — Inline file selector + Import operator

- Goal: let users trigger the import operator directly from the panel using
  Blender's file selector.

Files to change
- `addon/ui/panels.py` — add a button that invokes `blenderdes.import_timeline`
  and triggers Blender's file selector (operator `invoke` behaviour).

Blender test
- Click Import → Blender file dialog appears → choose `.json` or `.h5` → the
  importer runs, panel updates and handler loads the cache.

Estimated time: 20–40 minutes

---

## Step D.5 — Convenience operators: Reload & Clear Cache

- Goal: add `blenderdes.reload_timeline` and `blenderdes.clear_timeline_cache`.

Implementation notes
- Store the raw (parsed) timeline in `runtime_cache.SIM_CACHE['meta']['raw_timeline']`
  when the import operator runs. A `reload` operator can re-call
  `runtime_cache.load_timeline_to_cache(raw_timeline)` and `handlers.enable()`.

Files to change
- `addon/operators/timeline_import.py` — store the imported timeline into the
  runtime cache `meta` area.
- `addon/operators/timeline_import.py` (or a new module) — add classes for
  `BLENDERDES_OT_reload_timeline` and `BLENDERDES_OT_clear_timeline_cache`.
- `addon/ui/panels.py` — add buttons for Reload and Clear.

Blender test
- Import a timeline, click Clear Cache → panel shows no sample info. Click
  Reload → cache and status are restored.

Local tests
- Unit tests for runtime_cache storage and clear behavior.

Estimated time: 30–60 minutes

---

## Step D.6 — UX polish & optional shortcuts

- Goal: small layout improvements and optional Play/Pause keyboard shortcuts.

Files to change
- `addon/ui/panels.py`, `addon/__init__.py` (for keymap registration).

Blender test
- Verify layout looks good and shortcuts trigger the operators.

Estimated time: 30–60 minutes (optional)

---

## Step D.7 — UI unit tests & CI (wrap-up)

- Goal: add pure‑Python tests for the panel draw code and add a CI job to run
  `pytest` automatically in the repo venv.

Files to change
- `addon/tests/` — add tests that fake `bpy`/context and call the panel draw
  method to ensure no exceptions and no RNA warnings.
- Add a GitHub Actions workflow file (optional) that runs the tests in the
  repository virtualenv.

Estimated time: 1–2 hours

---

## Order & iteration

Do the steps in numeric order. Each step is intentionally small so you can test
quickly in Blender and report back. If you want a different priority (for
example file import first), we can reorder.


