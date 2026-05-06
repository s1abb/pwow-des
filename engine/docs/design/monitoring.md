# Monitoring and statistics — design notes

Goal
- Provide simple observability primitives: built-in monitors for resource
  usage, queue lengths, store sizes, and hooks for collecting time-series
  metrics during simulation runs.

Why
- Monitoring is essential to understand simulation dynamics and to debug
  preemption/timeout/cancellation interactions.

API sketches
- `Monitor(metric_name, sample_fn)`: register a sampling function that will be
  polled at each event time or at user-specified intervals; samples appended
  to an internal list for later analysis.
- `Resource.monitor()` / `Store.monitor()` convenience methods that register
  common samplers (e.g., `available`, `len(items)`).
- `Stats` helper to compute averages, percentiles and simple histograms from
  collected samples.

Usage example
- In `env` setup:
  ```python
  m = Monitor('store_len', lambda: len(store.items))
  env.process(lambda: monitor_runner(m, interval=1))
  ```
- Or provide an `env.register_sampler(fn, interval)` API.

Tests (TDD)
- `test_monitor_samples`: register a sampler and assert it collects values at
  expected times.
- `test_resource_monitor`: attach a resource monitor and assert it records
  available units over time as holders acquire/release.

Implementation notes
- Sampling at every event may be heavy; consider sampling only when relevant
  changes occur (on put/get/release) in addition to periodic sampling.
- Keep the sampling API optional and lightweight; don't change core event
  semantics.
- Provide utilities to export samples as CSV or to integrate with plotting
  scripts in `examples/`.
*** End Patch