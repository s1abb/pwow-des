# Architecture overview

This page is a short conceptual summary. For implementation-level details,
see the source under `engine/src/engine/` and design deep-dives under
`engine/docs/design/`.


# Architecture overview

This page gives a compact, high-level summary of the engine components and
their core responsibilities. For implementation details, see the Python
sources under `/engine/src/engine/` and the design notes in
`/engine/docs/design/`.

Core concepts

- Deterministic scheduling: a single event queue orders actions by (time,
  sequence) so simulations are reproducible and deterministic.
- Generator-based processes: lightweight cooperative tasks implemented as
  Python generators that yield waitables (timeouts, requests, events).
- Small, composable primitives: Events, Resources, Stores, and Containers
  expose tiny, well-defined hooks so new synchronization primitives can be
  added without touching the scheduler.

Component overview

- Environment (`/engine/src/engine/environment.py`)
  - Heap-based event queue and the canonical `now` time. Schedules callbacks
    and processes, advances simulation time, and provides convenience
    timer helpers.

- Process (`/engine/src/engine/process.py`)
  - Generator wrapper that manages lifecycle (start, resume, cancel,
    interrupt) and translates yielded objects into scheduler actions.

- Event primitives (`/engine/src/engine/event.py`, `/engine/src/engine/timeout.py`)
  - `Event`: subscribe/notify primitives with `on_yield` hooks for
    integration with `Process`.
  - Timer/Event combinators: `TimerEvent`, `TimerEventBool`, `AllOf`,
    `AnyOf` to compose and wait on multiple events.

- Engine facade (`/engine/src/engine/engine.py`)
  - Higher-level runtime that wraps `Environment` and exposes lifecycle
    controls (start, run, pause, step, stop, finish), error handling,
    and a snapshot API useful for exporters and deterministic stepping.
# Architecture overview

This page gives a compact, high-level summary of the engine components and
their core responsibilities. For implementation details, see the Python
sources under [engine/src/engine/](../../src/engine/) and the design notes in
[engine/docs/design/](../design/).

Core concepts

- Deterministic scheduling: a single event queue orders actions by (time,
  sequence) so simulations are reproducible and deterministic.
- Generator-based processes: lightweight cooperative tasks implemented as
  Python generators that yield waitables (timeouts, requests, events).
- Small, composable primitives: Events, Resources, Stores, and Containers
  expose tiny, well-defined hooks so new synchronization primitives can be
  added without touching the scheduler.

Component overview

- Environment ([engine/src/engine/environment.py](../../src/engine/environment.py))
  - Heap-based event queue and the canonical `now` time. Schedules callbacks
    and processes, advances simulation time, and provides convenience
    timer helpers.

- Process ([engine/src/engine/process.py](../../src/engine/process.py))
  - Generator wrapper that manages lifecycle (start, resume, cancel,
    interrupt) and translates yielded objects into scheduler actions.

- Event primitives ([engine/src/engine/event.py](../../src/engine/event.py), [engine/src/engine/timeout.py](../../src/engine/timeout.py))
  - `Event`: subscribe/notify primitives with `on_yield` hooks for
    integration with `Process`.
  - Timer/Event combinators: `TimerEvent`, `TimerEventBool`, `AllOf`,
    `AnyOf` to compose and wait on multiple events.

- Engine facade ([engine/src/engine/engine.py](../../src/engine/engine.py))
  - Higher-level runtime that wraps `Environment` and exposes lifecycle
    controls (start, run, pause, step, stop, finish), error handling,
    and a snapshot API useful for exporters and deterministic stepping.

- Synchronization primitives
  - Resource ([engine/src/engine/resource.py](../../src/engine/resource.py)): capacity-based allocator
    returning `Token` objects for granted requests; supports timeouts and
    priority semantics.
  - Store ([engine/src/engine/store.py](../../src/engine/store.py)): FIFO buffer with `put`/`get`
    semantics, timed/priority variants and validators in tests.
  - Container ([engine/src/engine/container.py](../../src/engine/container.py)): numeric-level primitive
    supporting increment/decrement operations and timed requests.

- Actor & Physics ([engine/src/engine/actor.py](../../src/engine/actor.py), [engine/src/engine/physics_world.py](../../src/engine/physics_world.py))
  - `Actor`: movement primitives (move_to/jump_to/stop), world registration
    and higher-level helpers (e.g., proximity waiting).
  - `PhysicsWorld`: optional time-stepped integrator for spatial dynamics,
    collision detection, proximity subscriptions and deterministic stepping.

- Interrupts ([engine/src/engine/interrupt.py](../../src/engine/interrupt.py))
  - Lightweight exception objects and helpers used to interrupt running
    processes in a controlled way.

- Monitoring ([engine/src/engine/monitoring.py](../../src/engine/monitoring.py))
  - Utilities to pretty-print snapshots, instrument actor/resource state
    and provide observability hooks for exporters and debugging.

- Public API surface ([engine/src/engine/api.py](../../src/engine/api.py), `__init__.py`)
  - Convenience exports and small facade utilities that make importing the
    core classes easier for examples and tests.

Core features and usage patterns

- Reproducible simulations: deterministic event ordering and a simple
  sequence counter enable repeatable runs and testable behavior.
- Composability: `Event` combinators and the `on_yield` hook let you build
  rich synchronization semantics (timeouts, all/any-of patterns) from
  small primitives.
- Export-friendly: `Engine` provides snapshot callbacks and stepping
  helpers (`step_to_time`, `step_by`) used by exporters to produce frame-
  aligned timelines.
- Hybrid dynamics: default event-driven Actors can opt into an
  explicitly-scheduled `PhysicsWorld` for fixed-step spatial integration
  and collision handling when needed.


