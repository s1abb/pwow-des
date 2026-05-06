# Class Store

## Module
`engine.store`

This module implements `Store`, a FIFO buffer primitive with optional
capacity and queued put/get requests supporting timeouts and priorities.

## Exceptions
| Exception | Description |
|-----------|-------------|
| `StoreRequestTimeout` | Raised into waiting processes when timed requests expire. |

## PutRequest / GetRequest
`PutRequest(store, item)` and `GetRequest(store)` are yieldable objects
returned by `Store.put(item)` and `Store.get()` respectively. They
implement `on_yield(env, proc)` to integrate with the scheduler and
queue semantics.

## Store
```py
class Store:
    def __init__(self, capacity=None)
```

Constructor takes an optional integer `capacity` (None == unbounded).
Key methods:

| Method | Description |
|--------|-------------|
| `put(item)` | Return a `PutRequest` to insert an item when space is available. |
| `put_with(item, timeout=None, priority=0)` | Return a put request with timeout/priority. |
| `get()` | Return a `GetRequest` that yields the next item when available. |
| `get_with(timeout=None, priority=0)` | Return a get request with timeout/priority. |

Behavior notes:
- `put` returns immediately and enqueues the item if space exists; if
  not, the putter is queued. When a getter becomes available, the oldest
  active putter is allowed to insert its item.
- `get` returns the oldest available item or queues the getter until an
  item is available.
