# Class Process

## Module
`engine.process`

## Inheritance
```
object
  engine.process.Process
```

## Class Declaration
```py
class Process:
    def __init__(self, env, generator)
```

## Description
`Process` wraps a generator-based coroutine and integrates it with the
`Environment` scheduler. Processes yield `Timeout` objects, numeric
delays, or other yieldables that implement an `on_yield(env, proc)`
hook.

The `Process` handles injecting exceptions delivered by `Event.fail`
or by `Environment.interrupt` and manages lifecycle flags such as
`_alive`, `_cancelled`, and `_started`.

## Method Summary
| Method | Description |
|--------|-------------|
| `interrupt(exc=None)` | Schedule an exception to be thrown into this process. |
| `cancel()` | Mark the process cancelled so future resumes are ignored. |

## Details
`Process._resume(value)` is the internal resume logic. It interprets the
value thrown into the generator (exception vs value), calls the
generator's `send` or `throw`, and inspects the yielded object to decide
how to schedule the next activation (timeouts, numeric delays, or
on_yield hooks).

`Process` also has a defensive `_waiting_for_type` marker to avoid
cross-delivering numeric timer values into processes actually waiting
on other yieldables (e.g., `Request`).
