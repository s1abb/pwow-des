# Design note: 3D physics / movement support for the engine (REVISED)

This document is the authoritative, updated plan for adding deterministic,
discrete 3D movement and basic physics primitives to the engine. It
focuses on the discrete-event integration, an Actor primitive that can
move in space, and a minimal PhysicsWorld and PathNetwork to support
deterministic, testable simulations.

Goals
-----
- Provide deterministic, yieldable movement primitives (Actor.move_to,
  jump_to, stop, attach_to_path) that integrate naturally with the
  engine's `Environment` and process model.
-- Keep the core lightweight and optional. The core Actor is implemented
  in `engine.actor` (see Status below); an optional `engine.physics`
  package can provide a PhysicsWorld/advanced backends later.
- Support both event-driven motion (schedule arrival) and a
  time-stepped PhysicsWorld for interaction-heavy scenarios.
- Reuse `Resource`/`Token` semantics for node/queue interactions so
  movement integrates with existing queuing and service components.

Audience
--------
Engine maintainers, feature implementers, and architects who will
implement and review the Actor/PhysicsWorld/PathNetwork features.

Status
------
- Phase 1 implemented (Event-driven Actor): a minimal event-driven
  Actor primitive has been added to the codebase as `engine.actor`.
  See `engine/src/engine/actor.py` and `engine/tests/test_physics_actor.py`.
  This implements `move_to`/`jump_to`/`stop` semantics and arrival
  events described below.

- PhysicsWorld prototype implemented (time-stepped): a first-pass
  `PhysicsWorld` and `Body` implementation now exists at
  `engine/src/engine/physics_world.py`. It supports fixed-dt stepping,
  sphere-sphere collision detection with rollback semantics, and a
  convenience `schedule_loop(env, dt)` helper. Tests are in
  `engine/tests/test_physics_world.py` and the full test-suite is
  passing locally (76 tests).

Notes:
- The PhysicsWorld currently uses sphere-based collisions for simplicity
  and determinism. Distance checks use squared-distance math to avoid
  unnecessary sqrt calls.
- The PhysicsWorld is optional: `Actor` still works in event-driven mode
  (it delegates to the world only when registered). If the world hasn't
  been scheduled, `move_to` will fall back to the actor's event-driven
  arrival behavior for compatibility.

High-level approach
-------------------
We recommend a hybrid strategy:

1. Default Actor movement is event-driven: `Actor.move_to(...)` schedules
   an arrival event in the `Environment` and returns an `Event` that
   succeeds on arrival. This is efficient for sparse interactions.
2. Provide a `PhysicsWorld` time-stepped integrator for dense
   interactions (collisions, proximity-based behaviors). Actors may be
   registered with the world to enable per-dt updates.
3. Provide a `PathNetwork` with `Node` / `Edge` / `PathBody` primitives
   for constrained, efficient 1D movement (roads, conveyors). Nodes
   reuse `Resource` semantics for queuing.

Rationale: This keeps typical DES patterns efficient while giving a
clear path for interaction-rich scenarios.

Core actor API (Python sketch)
------------------------------
Below are concrete, implementable method signatures for the Actor
primitive designed to be used from `env.process` and other engine
processes.

Types used below:
- Vec3: small tuple-like (x, y, z) or minimal class
- Event: engine Event class

Actor API (essential)
- property position -> Vec3
- def set_position(self, x: float, y: float, z: float) -> None
- def get_position(self) -> Vec3
- def set_rotation(self, angle: float) -> None
- def get_rotation(self) -> float

- def set_dimensions(self, length: float, width: float, height: float) -> None
- def bounds(self) -> dict  # radius/AABB info for collision tests

- def set_velocity(self, v: Vec3) -> None
- def get_velocity(self) -> Vec3
- def set_speed(self, s: float) -> None
- def get_speed(self) -> float

# Movement primitives (yieldable where noted)
- def move_to(self, x: float, y: float, z: float, *, speed: Optional[float]=None) -> Event
  - Schedules arrival; returns Event that succeeds with metadata on arrival.
- def move_to_component(self, component, *, speed: Optional[float]=None) -> Event
- def jump_to(self, x: float, y: float, z: float) -> None
- def stop(self) -> None
- def is_moving(self) -> bool
- def time_to_arrival(self) -> Optional[float]
- def distance_to(self, x: float, y: float, z: float) -> float

# Path/network primitives
- def attach_to_path(self, edge, s: float=0.0, *, speed: Optional[float]=None) -> None
- def detach_from_path(self) -> None
- def move_along_edge(self, edge, target_s: float, *, speed: float) -> Event

# Events and queries
- def wait_for_arrival(self, target) -> Event
- def wait_for_proximity(self, other, radius: float) -> Event
- def on_arrival(self, callback)  # called by engine at arrival

# Integration with engine
- def request_parking_or_queue(self, node, *, timeout: Optional[float] = None) -> Event
  - Node.request() should reuse Resource semantics and return Token on success.

# PhysicsWorld registration
- def register_with_world(self, world) -> None
- def unregister_from_world(self) -> None
- def set_physics_mode(self, mode: str) -> None  # 'EVENT_DRIVEN' | 'TIMESTEP'

Event contract for movement methods
----------------------------------
- move_to returns an `Event` that:
  - Succeeds when the actor arrives; Event.value is a small dict with keys
    like `target`, `arrival_time`, and `distance_travelled`.
  - Is failed (Event.fail) if the movement is interrupted by `stop()` or a
    re-route; the raised exception should be a well-defined `MovementInterrupted`.
  - If the actor is registered with a PhysicsWorld and a collision occurs
    that stops the actor, the world should call the Event.fail with a
    `CollisionException` (or similar) so processes can handle it.

State transitions (aligned with CHECKPOINT_ACTOR.md)
--------------------------------------------------
- IDLE — initial state
- IN_TRANSIT — after move_to starts
- IN_QUEUE — when placed in a node parking queue
- IN_PROCESS — when being processed by a component

Transitions:
- move_to -> IN_TRANSIT
- arrival -> IDLE or IN_QUEUE or IN_PROCESS (depending on destination)
- stop -> IDLE (and arrival Event.fail)
- node.request success -> IN_PROCESS
- node.request enqueue -> IN_QUEUE

PhysicsWorld (time-stepped) API
-------------------------------
The PhysicsWorld is an optional component that manages time-stepped
integration for bodies registered with it. Implementation notes:
- Discrete, fixed dt with deterministic ordering (registration order or
  stable sorted id)
- Pure-Python first; optional numpy or external-backend adapters later

Suggested API:
- class PhysicsWorld:
  - def register_body(self, body) -> BodyHandle
  - def unregister_body(self, body) -> None
  - def step(self, dt: float, now: float) -> None
  - def query_region(self, bounds) -> List[Body]
  - def schedule_loop(self, env, dt: float) -> process  # convenience

Body (representation returned by registration):
- properties: position, velocity, mass, radius, owner (Actor)
- methods: apply_impulse(vec), set_velocity(vec), set_position(vec)
- events: on_collision(other, contact_info)

Collision semantics
-------------------
- Minimal built-in detectors: sphere-sphere and optional AABB checks
- Resolution policy (prototype): rollback + stop + arrival Event.fail
  (CollisionException). The prototype keeps resolution conservative and
  simple; future work can add impulses/contact models as needed.
- For path-followers, collision prevention is preferably handled by
  headway rules on edges rather than 3D collision resolution.

PathNetwork, Edge, Node (constrained movement)
---------------------------------------------
PathNetwork primitives enable efficient 1D movement along edges. Key
APIs:
- PathNetwork:
  - nodes: Dict[node_id -> Node]
  - edges: Dict[edge_id -> Edge]
  - find_path(a,b) -> List[Edge]
  - query_nearby(pos, r)

- Edge:
  - length: float
  - pos_at(s: float) -> Vec3
  - tangent_at(s: float) -> Vec3

- Node:
  - position: Vec3
  - request() -> Event/Token  # implementable by wrapping a Resource

- PathBody (actor attached to path):
  - attributes: edge, s, speed
  - methods: advance(dt), wait_for_node(node) -> Event

Design choices for path-following
- Use 1D headway for same-edge bodies (enforce minimum spacing along s)
- Allow event-driven arrival scheduling for isolated path-followers,
  converting to time-step updates when interactions occur (hybrid approach)

Determinism and ordering rules
------------------------------
- PhysicsWorld.step must iterate bodies in a deterministic order.
- Physics ticks should be scheduled with the environment using fixed
  times derived from dt and the Environment's time/seq semantics.
- When scheduling arrival events for move_to, use env's deterministic
  ordering (time + seq) to break ties reproducibly.

Recent changes
--------------
- Added `engine/src/engine/physics_world.py`: Body/PhysicsWorld, fixed-dt
  stepping, sphere-sphere collision with rollback semantics, loop
  lifecycle management, and squared-distance optimizations.
- Added `engine/tests/test_physics_world.py`: movement and collision
  behavior tests.
- Updated `engine/src/engine/actor.py`: actor-world registration helpers
  (register_with_world / unregister_from_world) and stable delegation.
- Added `engine/examples/physics_move_to_demo.py` and included it in
  the smoke examples list.

Immediate priorities (next small tickets)
---------------------------------------
These are small, high-value tasks to improve the prototype and make it
production-ready incrementally. Each item includes an estimate and the
acceptance criteria.

1) Squared-distance & micro-optimizations (DONE)
   - Estimate: 0.5 day
   - Status: implemented (uses squared comparisons; one sqrt for
     normalization and arrival payload). Tests: `test_physics_world.py`
     passes.

2) Multi-sphere Body support (better fit for elongated actors)
   - Estimate: 1–2 days
   - Acceptance: allow `Body` to carry multiple (offset, radius) spheres
     and perform pairwise checks; unit test showing better collision
     approximation vs single-sphere.

3) Swept-sphere (segment-sphere) per-step check to prevent tunneling
   - Estimate: 1 day
   - Acceptance: fast-moving body that would otherwise tunnel is
     detected by the swept test and collision events fire deterministically.

4) Simple broad-phase culling (loose AABB grid or sweep-and-prune)
   - Estimate: 1–2 days
   - Acceptance: unit benchmark demonstrates fewer narrow-phase pair
     checks on ~100 bodies.

5) PathNetwork prototype (1D headway + Node/Resource integration)
   - Estimate: 4–7 days
   - Acceptance: two bodies on same edge obey headway rules and node
     `request()` reuses Resource semantics (Token) with tests.

6) Docs & examples / CI smoke tests
   - Estimate: 1–2 days
   - Acceptance: add smoke examples under `engine/examples/physics_*` and
     a small CI job that runs the smoke set and relevant unit tests.

Design decisions & rationale (short)
-----------------------------------
- Use spheres as the default collision primitive: spheres are
  rotationally-invariant, cheap, and deterministic. They minimize
  numerical and implementation complexity for the first prototype.
- Squared-distance comparisons: avoid frequent sqrt calls; compute a
  single sqrt only when normalizing velocity or producing a distance
  payload.
- Loop lifecycle: physics loop auto-stops when no bodies are moving; a
  best-effort restart is triggered by `move_actor`. This prevents the
  simulation from hanging when the world is idle (good for smoke
  examples and test termination).

Testing & CI checklist
----------------------
- Unit tests:
  - `test_physics_actor.py` (actor arrival/stop semantics)
  - `test_physics_world.py` (movement & collision)
  - `test_actor_world_hook.py` (actor-world registration/delegation)
- Smoke examples:
  - `engine/examples/physics_move_to_demo.py` included in smoke tests
- Deterministic checks:
  - Repeat key scenarios and assert identical event ordering/times
- Performance checks (optional):
  - Micro-benchmarks for broad-phase vs naive O(n^2)

How to validate locally
-----------------------
Run the focused physics tests:

```powershell
pytest -q engine/tests/test_physics_world.py
pytest -q engine/tests/test_actor_world_hook.py
```

Run full suite (quick):

```powershell
pytest -q
```

API doc updates (appendix)
--------------------------
The Appendix below is updated to reflect the implemented API and the
current stable contract.

Appendix: small API reference (copyable)
----------------------------------------
Vec3 = Tuple[float, float, float]

class Actor:
    position: Vec3
    def move_to(self, x: float, y: float, z: float, *, speed: Optional[float]=None) -> Event: ...
    def jump_to(self, x: float, y: float, z: float) -> None: ...
    def stop(self) -> None: ...
    def register_with_world(self, world) -> None: ...
    def unregister_from_world(self) -> None: ...
    def wait_for_proximity(self, other, radius: float) -> Event: ...

class PhysicsWorld:
    def register_body(self, actor, *, radius: float = 0.5, mass: float = 1.0) -> Body: ...
    def unregister_body(self, body) -> None: ...
    def move_actor(self, actor, target: Vec3, speed: float) -> Event: ...
    def step(self, dt: float, now: float) -> None: ...
    def schedule_loop(self, env, dt: float) -> process: ...

Next steps / actions I can take now
----------------------------------
1. Create the small tickets and implement #2 (multi-sphere Body) next.
2. Implement the swept-sphere check to eliminate tunneling.
3. Add a simple broad-phase (loose AABB grid) and micro-benchmark.

Tell me which of those you'd like next and I'll implement it with tests
and a short example.

Testing strategy and required tests
----------------------------------
Unit tests (Phase 1):
- move_to arrival accuracy: schedule move_to; assert arrival time == now + distance/speed
- stop semantics: move_to followed by stop -> arrival Event fails with MovementInterrupted
- deterministic repeatability: repeat the same scenario multiple times; assert same event sequencing

Integration tests (Phase 2/3):
- path-following: 2 bodies on same edge obey headway rules
- collision: PhysicsWorld resolves a simple 2-body collision predictably
- node queuing: Actor arriving at Node yields on `node.request()` and receives Token with expected behavior

Regression and reproducibility
-----------------------------
- Use fixed seeds for any RNG in examples
- Add smoke examples under `engine/examples/physics_*` and include a pytest smoke test (fast subset + optional slow set)

Incremental implementation plan (detailed)
----------------------------------------
Phase 0 — API and doc (this document)
- Finalize Actor API and Event contract
- Produce a one-page API reference (optional)

Phase 1 — Event-driven Actor movement (2–4 days)
- Implement Actor.move_to / jump_to / stop / is_moving
- Implement arrival Event semantics and state transitions
- Add unit tests for arrival, stop, re-route
- Provide minimal example `examples/physics_move_to_demo.py`

Phase 2 — PathNetwork & Node integration (4–7 days)

Phase 2 focuses on constrained 1D movement (roads, conveyors) using a
PathNetwork abstraction. This phase implements efficient path-following
and queuing semantics that integrate with `Resource`/`Token` mechanics.

- Implement PathNetwork, Edge, Node primitives
- Implement attach_to_path / move_along_edge and path-body updates
- Node.request uses Resource semantics and returns Token
- Add path-following tests and examples

Phase 3 — PhysicsWorld time-stepped mode (6–10 days)
- Implement PhysicsWorld.step with deterministic iteration
- Implement Body registration, simple collision detection/resolution
- Implement wait_for_proximity and collision events
- Add tests for collision determinism and integration examples

Phase 4 — Performance & backends (2–6 days)
- Optional numpy vectorized path
- Broadphase (grid or sweep-and-prune)
- Optional adapter to PyBullet (document non-determinism caveats)

Phase 5 — Docs, examples, CI (2–3 days)
- Add `engine/examples/physics_*` and smoke tests, update docs and diagrams
- Add reproducibility tests for round-trip scenarios

Security, packaging, and dependencies
------------------------------------
- Keep the pure-Python PhysicsWorld dependency-free by default.
- Backends that add C dependencies should be optional and documented.

Open questions / trade-offs to finalize (for maintainers)
-----------------------------------------------------
- Default movement mode for new Actors: event-driven or registered with
  a PhysicsWorld? Recommendation: start event-driven, allow opt-in
  registration for PhysicsWorld when needed.
- Event semantics on interruption: prefer Event.fail with explicit
  exception types for clarity (MovementInterrupted, CollisionException).
- How aggressive should the built-in collision resolution be vs. relying
  on path-headway rules? Recommendation: keep collision resolution
  minimal; encourage path-headway for constrained networks.

Examples to provide early
-------------------------
- physics_move_to_demo.py — demonstrates move_to and arrival Event
- physics_stop_and_reroute.py — move_to, stop, move_to(new_target)
- physics_path_conveyor.py — PathNetwork with items transported and serviced
- physics_collision_demo.py — simple 2-body collision in PhysicsWorld

Appendix: small API reference (copyable)
----------------------------------------
Vec3 = Tuple[float, float, float]

class Actor:
    position: Vec3
    def move_to(self, x: float, y: float, z: float, *, speed: Optional[float]=None) -> Event: ...
    def jump_to(self, x: float, y: float, z: float) -> None: ...
    def stop(self) -> None: ...
    def attach_to_path(self, edge, s: float = 0.0, *, speed: Optional[float]=None) -> None: ...
    def wait_for_proximity(self, other, radius: float) -> Event: ...

class PhysicsWorld:
    def register_body(self, actor) -> Body: ...
    def unregister_body(self, body) -> None: ...
    def step(self, dt: float, now: float) -> None: ...

Next steps / actions I can take now
----------------------------------
1. Produce a focused one-page API reference (markdown) suitable for
   sharing with stakeholders (if you want immediate review-ready
   documentation).
2. Implement a Phase 1 prototype: minimal `Actor` class with move_to
   implemented using `Environment` scheduling and a unit test that
   validates arrival and interruption semantics.

Tell me which of those you want me to do next (API doc or Phase 1
prototype), or if you'd like I can open a small PR draft implementing
Phase 1 in the repo directly.

Usage example
-------------
Minimal usage from a process (see `engine/examples/physics_move_to_demo.py`):

```py
def mover(env, actor):
  ev = actor.move_to(0, 0, 2, speed=2.0)
  payload = yield from ev.wait()
  print("arrived", payload)

env = Environment()
actor = Actor(env, position=(0,0,0))
env.process(lambda: mover(env, actor))
env.run()
```

Document owner: engineering / design

Last updated: 2025-10-09
