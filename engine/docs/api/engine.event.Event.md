# Class Event

## Module
`engine.event`

This module provides the `Event` abstraction and common event types used
by the engine: `Event`, `TimerEvent`, `TimerEventBool`, `AllOf`, and
`AnyOf`.

## Event
```py
class Event:
    def __init__(self, env=None)
```
Lightweight synchronization primitive processes can `yield` to wait for.
An `Event` may be `succeed(value)`ed or `fail(exception)` to resume
waiting processes. Use `e.wait()` as a coroutine helper to raise
delivered exceptions into the waiting code.

Key methods:
- `on_yield(env, proc)` — hook called when a process yields the event.
- `subscribe(callback)` / `unsubscribe(callback)` — low-level callbacks.
- `succeed(value)` — trigger the event with a value.
- `fail(exc)` — trigger the event with an exception.

## TimerEvent / TimerEventBool
`TimerEvent(env, delay)` schedules a success after `delay`; the value
provided by `TimerEvent` is the `env.now` timestamp, while
`TimerEventBool` succeeds with `True`. These are the primitives behind
`env.timeout()` and `env.timeout_bool()`.

## AllOf / AnyOf
Combinator events that compose multiple events:
- `AllOf(events)` succeeds when all members succeed; its value is a
  dict mapping each member to its value.
- `AnyOf(events)` succeeds when the first member succeeds; its value is
  a single-entry dict with the winning member.

Usage examples and details mirror the `Event` API; see source for
behavior when members already triggered at combinator creation time.
