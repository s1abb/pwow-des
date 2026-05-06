# Class Environment

## Module
`engine.environment`

## Inheritance
```
object
  engine.environment.Environment
```

## Class Declaration
```py
class Environment:
    def __init__(self)
```

## Description
`Environment` is the discrete-event scheduler driving processes and
events. It maintains a heap-based event queue, a logical `now` time, and
a deterministic sequence counter to order simultaneous events.

Use `env.process(generator_or_callable)` to create a `Process` and
`env.run(until=None)` to execute the event loop.

## Constructor Summary
| Constructor | Description |
|-------------|-------------|
| `Environment()` | Create a new simulation environment with `now == 0.0`. |

## Attributes
| Name | Type | Description |
|------|------|-------------|
| `now` | float | Current simulation time |

## Method Summary
| Method | Description |
|--------|-------------|
| `process(generator_or_callable)` | Wrap a generator or generator-factory into a `Process` and schedule it. |
| `timeout(delay)` | Return a TimerEvent that succeeds after `delay` (alias helper). |
| `timeout_bool(delay)` | Return a TimerEventBool that succeeds with True after `delay`. |
| `run(until=None)` | Run the simulation until the queue empties or time reaches `until`. |
| `interrupt(proc, exc=None, delay=0.0)` | Schedule an exception into `proc` optionally after `delay`. |
| `next_event_time()` | Return the time of the next scheduled event or `None`. |

## Method Details

### process
```py
def process(self, generator_or_callable)
```
Wrap a generator (or callable producing a generator) into a `Process` and
start it. Accepts either a generator object or a callable that returns a
generator.

### timeout
```py
def timeout(self, delay: float)
```
Convenience alias returning a `TimerEvent` that succeeds when the delay
elapses. Usage: `yield env.timeout(3)`.

### timeout_bool
```py
def timeout_bool(self, delay: float)
```
Return a `TimerEventBool` that succeeds with `True` when the timer fires.

### run
```py
def run(self, until=None)
```
Advance the simulation by popping scheduled events, updating `now`, and
resuming processes or calling callback `_resume` methods. Returns the
final `now` reached (or `until` if specified and reached early).

### interrupt
```py
def interrupt(self, proc, exc=None, delay: float = 0.0)
```
Schedule an exception to be thrown into the given `Process`. `exc` may
be omitted (defaults to `Interrupt()`), and the API accepts the
backwards-compatible form `interrupt(proc, delay)` where a numeric
second positional value is used as `delay`.

### next_event_time
```py
def next_event_time(self)
```
Return the time of the earliest scheduled event or `None` if the queue
is empty. Useful for monitoring or integrating external loops.
