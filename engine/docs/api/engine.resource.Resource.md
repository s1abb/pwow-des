# Class Resource, Request, Token

## Module
`engine.resource`

This module implements a `Resource` primitive with `Request` events and
`Token` objects representing allocations. It provides FIFO and
priority-based queuing, optional preemption, and timeout semantics.

## Token
```py
class Token:
    def __init__(self, resource, proc, name=None, allocated_at=None)
```
`Token` represents a granted allocation. It is a context-manager and
automatically releases the resource when exiting a `with` block.

Attributes: `resource`, `proc`, `name`, `allocated_at`, `id`.

## Request
```py
class Request(Event):
    def __init__(self, resource)
```
`Request` is an `Event`-subclass returned by `Resource.request()` and
`Resource.request_with(...)`. Yielding a `Request` binds the waiting
process to that request; when the resource grants the request the
request is `succeed(token)`ed and the process receives the `Token`.

`Request` supports `timeout`, `priority`, optional `name` and
`preemptible` attributes.

## Resource
```py
class Resource:
    def __init__(self, capacity=1)
```
Resource tracks `capacity`, `available`, `allocated` list and a
priority `waiters` heap. Key methods:

| Method | Description |
|--------|-------------|
| `request()` | Return a `Request` yieldable for acquiring one unit. |
| `request_with(timeout=None, priority=0)` | Return a `Request` with options. |
| `release(proc=None, token=None)` | Release an allocation by proc or token (or FIFO if none provided). |
| `snapshot(current_time=None)` | Return a structured snapshot of current allocations. |
| `pretty_allocations(current_time=None)` | Compact allocation tuples. |
| `pretty_print(current_time=None, proc_name_map=None)` | Friendly representation. |

Exceptions and special types:
- `RequestTimeout` — raised into waiting process when a request times out.
- `Preempted` — raised into a process when it is preempted by a higher-priority requester.

Notes:
- `Token` objects include `id`, optional `name` and `allocated_at` for
  monitoring and pretty-printing.
- `Resource.release()` supports releasing by `token` or `proc` to avoid
  ambiguous FIFO removals when preemption occurred.
