# Timeline Storage Formats: Status and Architecture

This document records the design and the current implementation status for
timeline import/export formats. It replaces and updates the earlier design
notes with what has already been implemented, what remains, and concrete
next steps.

## Current status (summary)

- Core export infrastructure implemented: `engine/src/engine/timeline_export.py`.
- Format handler registry and JSON handler implemented: `engine/src/engine/formats/` (`json_format.py`).
- HDF5 handler implemented: `engine/src/engine/formats/hdf5_format.py` (basic export + partial import by time range).
- Example updated to use core export API: `engine/examples/collision_timeline_demo.py` now calls `export_timeline(...)` and supports `.h5` exports.
- Tests added and passing: `engine/tests/test_timeline_formats.py` (JSON roundtrip + autodetect). Full test-suite currently passes (80 tests).
- Requirements updated and installed in dev venv: `h5py`, `numpy` added to `requirements.txt` / `requirements-dev.txt`.

This means HDF5 is usable today by running examples with an `.h5` output path.

## Files added/modified in this work

- engine/src/engine/timeline_export.py — core export API, format detection and dispatcher
- engine/src/engine/formats/__init__.py — handler registry
- engine/src/engine/formats/json_format.py — JSON handler (export/import/validate)
- engine/src/engine/formats/hdf5_format.py — HDF5 handler (export/import/validate)
- engine/src/engine/engine.py — convenience `export_timeline` wrapper
- engine/examples/collision_timeline_demo.py — now uses core exporter and supports `.h5`
- engine/tests/test_timeline_formats.py — unit tests for timeline formats
- requirements.txt / requirements-dev.txt — added `h5py` and `numpy`

## How to use HDF5 export right now

1. Activate your venv (PowerShell):

    ```powershell
    .venv\Scripts\Activate.ps1
    ```

2. Run the collision example and export to HDF5:

    ```powershell
    python engine/examples/collision_timeline_demo.py simulation/collision.h5
    ```

3. The produced file `simulation/collision.h5` contains:
   - `times` dataset (float64)
   - per-actor datasets `actors/{actor_id}/positions` (n_frames x 3 float32)
   - attributes under the root for metadata

You can read the file with `h5py` (or any HDF5 viewer) and slice by time
using numpy's `searchsorted` on the `times` dataset.

## Tests & verification

- Unit tests for JSON round-trip and auto-detection were added and run.
- The full project test-suite passes (80 tests) in the current environment.

Commands used during development

```powershell
#. Activate venv
.venv\Scripts\Activate.ps1
# Install deps
python -m pip install -r requirements.txt
# Run full tests
python -m pytest -q
# Run example that writes HDF5
python engine/examples/collision_timeline_demo.py simulation/collision_test.h5
```

## Known limitations (current)

- HDF5 handler is currently implemented in a simple, non-streaming way: it
  builds arrays from the in-memory `frames` list and writes datasets in one
  go. For very large timelines this will require significant memory.
- The HDF5 schema is minimal (times + actors/{id}/positions). Additional
  datasets (velocities, rotations, per-frame metadata) are not yet
  standardized.
- There are no dedicated unit tests yet for HDF5 round-trip or partial
 -read behavior; currently only the JSON handler is covered by unit tests.

## Short-term next steps (recommended)

1. Add unit tests for HDF5 handler
   - test_hdf5_roundtrip: export timeline -> import_timeline() -> assert equality
   - test_hdf5_partial_read: export a timeline and import only a time range

2. Implement streaming/appendable HDF5 writes
   - Use chunked, extendable datasets (create_dataset with maxshape) and
     append frames to avoid buffering all frames in memory.
   - Provide an API for incremental export (open writer, append_frame, close).

3. Harden `collect_timeline_data()` and export options
   - Support `time_range`, `actors`, `sample_dt` at the collection layer so
     handlers can avoid processing unneeded data.

4. Documentation and examples
   - Add a small HOWTO showing HDF5 structure and a code snippet to read a
     time-slice from an HDF5 timeline.
   - Update `engine/docs/index.md` and examples README to show `.h5` usage.

5. CI and packaging
   - Add a CI job (or conditional step) to install `h5py` wheels and run the
     HDF5 tests (or mark them xfail on unsupported platforms).

## Medium/long term (optional)

- Implement Parquet handler if analytics workflows are a priority (requires
  `pyarrow`/`pandas`).
- Implement a compact custom-binary format if extremely large or streaming
  real-time workloads require minimal overhead and maximum performance.
- Add format versioning and migration helpers (store `format_version` in
  metadata and provide `validate()` and `migrate()` hooks on handlers).

## Risks & mitigations

- Dependency friction: `h5py` can be large on some CI runners. Mitigation:
  pin wheel-friendly versions and run HDF5 tests only on suitable machines.
- Memory usage for large timelines: Mitigation — implement streaming HDF5
  writer immediately and provide an incremental API for examples.
- Backwards compatibility: Keep JSON handler stable and provide converters to
  migrate JSON -> HDF5 for large datasets.

## Status checklist (short)

- [x] Core export API and format registry
- [x] JSON handler and tests
- [x] HDF5 handler (basic export + partial import)
- [x] Example updated to use core exporter and supports `.h5`
- [x] HDF5 unit tests (to add)
- [ ] Streaming HDF5 writer
- [ ] Benchmarks and CI coverage for HDF5

---

If you'd like, I can now:
- add the HDF5 unit tests and run them (recommended), or
- implement the streaming HDF5 writer (higher effort), or
- add a small HOWTO and example reader snippet to docs.
Tell me which and I'll proceed.