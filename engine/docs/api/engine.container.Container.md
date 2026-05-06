# Class Container

## Module
`engine.container`

## Inheritance
```
object
  engine.container.Container
```

## Class Declaration
```py
class Container:
    def __init__(self, capacity: float)
```

## Description
`Container` is a synchronous numeric storage primitive. It maintains a
numeric `level` (float) bounded by `capacity`. Producers call `put(amount)`
to add to the level; consumers call `get(amount)` to remove from the level.

If a `put` or `get` cannot be satisfied immediately (e.g., not enough
space or not enough level), the request is queued. Requests may specify
timeouts and priorities via the `put_with` and `get_with` helpers.

`Container` requests are yieldable objects; yielding a `ContainerRequest`
will block the current process until the request succeeds (or a timeout
exception is raised).

This implementation provides a lightweight `meta` dict for caller-local
annotations and two convenience helpers `set_meta` / `get_meta`.

## Constructor Summary
| Constructor | Description |
|-------------|-------------|
| `Container(capacity)` | Create a container with the given numeric capacity. The initial `level` is 0.0. |

## Attributes
| Name | Type | Description |
|------|------|-------------|
| `capacity` | float | Maximum stored level |
| `level` | float | Current stored level (starts at 0.0 unless set by user) |
| `waiters` | list | Internal queue of pending `ContainerRequest` entries |
| `meta` | dict | Caller-defined metadata storage (use `set_meta`/`get_meta`) |

## Method Summary

| Method | Description |
|--------|-------------|
| `put(amount)` | Return a `ContainerRequest` that will add `amount` when satisfied (yield this). |
| `get(amount)` | Return a `ContainerRequest` that will remove `amount` when satisfied (yield this). |
| `put_with(amount, timeout=None, priority=0)` | Return a request with timeout/priority options. |
| `get_with(amount, timeout=None, priority=0)` | Return a request with timeout/priority options. |
| `set_meta(key, value)` | Store a small caller-local metadata value. |
| `get_meta(key, default=None)` | Retrieve a metadata value or default. |

## Exceptions
| Exception | Description |
|-----------|-------------|
| `ContainerRequestTimeout` | Raised into a waiting process when a timed request expires. |

## Method Details

### __init__
```py
def __init__(self, capacity)
```
Create a new `Container` with numeric capacity. The initial `level` is
0.0. The `capacity` is converted to float internally.

**Parameters:**
- `capacity` (float-like) — maximum stored level

### put
```py
def put(self, amount)
```
Return a `ContainerRequest` that will add `amount` to the container when
the container has space. Typical usage:

```py
yield container.put(3.0)
```

### get
```py
def get(self, amount)
```
Return a `ContainerRequest` that will remove `amount` from the
container when enough level is available. Typical usage:

```py
yield container.get(2.5)
```

### put_with
```py
def put_with(self, amount, timeout=None, priority=0)
```
Return a `ContainerRequest` that supports `timeout` (seconds) and a
numeric `priority` (lower value == higher priority). If the request is
not satisfied before `timeout` seconds elapse a `ContainerRequestTimeout`
is scheduled into the waiting process.

### get_with
```py
def get_with(self, amount, timeout=None, priority=0)
```
Similar to `put_with` but for get requests.

### set_meta
```py
def set_meta(self, key, value)
```
Convenience wrapper to store small caller-local annotations in the
container's `meta` dict. Example:

```py
container.set_meta('truck_pending', True)
```

### get_meta
```py
def get_meta(self, key, default=None)
```
Return the metadata value or `default` if the key is not present.
