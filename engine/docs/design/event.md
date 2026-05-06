# Event class hierarchy — design notes

Goal
- Provide a small Event abstraction and a few combinators (AllOf, AnyOf) so
  processes can wait on composed events instead of ad-hoc patterns.

Why
- Event composition is a powerful building block: it simplifies coordination
  (wait for any of several timeouts, or for both a resource and a timeout)
  and is an important piece for SimPy compatibility.

API sketch
- class `Event`: base event exposing `env`, `callbacks` and a `.succeed(value)`
  or `.fail(exc)` method. Processes can `yield event` to wait until it is
  triggered.
- class `AllOf(events)` — yields a single Event that succeeds when all
  member events succeed; value is dict mapping member->value.
- class `AnyOf(events)` — yields a single Event that succeeds when the first
  member succeeds; value is dict with the winning event.

Process integration
- `Process._resume` should treat `Event` instances as yieldables with an
  `on_yield(env, proc)` hook that registers the process as a callback on the
  event.
- When an Event is triggered, it schedules the waiting processes via
  `env._schedule(0.0, proc, event_value)`.

Tests (TDD)
- `test_event_simple`: creating and succeeding an Event resumes waiting
  process with the correct value.
- `test_allof`: wait on `AllOf([e1, e2])`, succeed both events and assert
  the joined value.
- `test_anyof`: wait on `AnyOf([e1, e2])`, succeed one event and assert the
  AnyOf result contains only the winning event.
- Edge cases: member event failure, event cancellation, simultaneous succeed
  ordering deterministic by seq.

Implementation notes
- Keep Event lightweight: store waiting procs as list of (proc, env) pairs or
  callbacks; triggering an Event should iterate callbacks and schedule them.
- AllOf/AnyOf are convenience Events that attach callbacks to member events
  and themselves succeed/fail accordingly.
- Consider whether to implement `timeout = env.timeout(5)` alias to `Timeout`
  for API compatibility.

Compatibility
- If SimPy compatibility is a goal, aim for API surface parity (names and
  behaviors). Otherwise pick minimal, expressive primitives and document the
  differences.
