# Class Engine

## Module
`engine.engine`

## Inheritance
```
object
  engine.engine.Engine
```

## Class Declaration
```py
class Engine:
    def __init__(self, time_func: Optional[Callable[[], float]] = None)
```

## Description
`Engine` is a small facade around `engine.environment.Environment` providing
application-friendly lifecycle control (start/run/step/pause/stop/finish)
and a few inspection helpers.

The Engine's error handling is configurable:
- `raise_on_error` (default True): if True, exceptions raised by processes
  will be re-raised from `run()`/`step()` after the engine records the
  error state. If False, the exception is captured into `last_exception`
  and `run()`/`step()` return `False`.
- `on_error`: optional callback `on_error(exc, engine)` invoked when an
  exception occurs; exceptions from the callback are ignored.

Use `getLastException()` to retrieve the captured exception when
`raise_on_error` is False.

## Constructor Summary
| Constructor | Description |
|-------------|-------------|
| `Engine(time_func=None)` | Create a new Engine. `time_func` is an optional callable returning a monotonic time (used for deterministic tests). |

## Attributes
| Name | Type | Description |
|------|------|-------------|
| `raise_on_error` | bool | Controls whether exceptions are re-raised (True) or captured (False). |
| `on_error` | Optional[Callable[[Exception, Engine], None]] | Optional callback invoked on exception. |
| `last_exception` | Optional[Exception] | The last captured exception (set when an error occurs and capture mode is used). |

## Method Summary
| Method | Description |
|--------|-------------|
| `start(root)` | Schedule a root process (callable or generator) and set state to `PAUSED`. |
| `run(until=None)` | Run the engine. Returns True on clean completion, False if an error occurred in capture mode. If `raise_on_error` is True, exceptions propagate. |
| `pause()` | Request pause (cooperative). |
| `step()` | Execute a single event and return True on success; obeys `raise_on_error`. |
| `stop()` | Clear pending events and set state to `IDLE`. |
| `finish()` | Request termination after current event. |
| `time()` | Return the current simulation time. |
| `getState()` | Return the current Engine state string. |
| `getStep()` | Return the number of steps executed. |
| `getEventCount()` | Return the number of scheduled events. |
| `getNextEventTime()` | Return the time of the next scheduled event or `None`. |
| `getRunCount()` | Return how many times `run()` has been invoked. |
| `getRunTimeMillis()` | Return the last run's elapsed wall time in milliseconds. |
| `getStartTimeMillis()` | Return the start wall time (ms) of the last run, or `None`. |
| `getLastException()` | Return the last captured exception or `None`.
| `step_to_time(target_time: float)` | Advance the engine until `target_time` (inclusive). Returns True on clean completion, False if an exception was captured in non-raising mode. |
| `step_by(delta: float)` | Advance the engine by `delta` seconds (convenience wrapper around `step_to_time`). |
| `set_snapshot_callback(cb)` | Register a snapshot callback used by `snapshot()` to capture engine state for exporters. |
| `snapshot()` | Invoke the registered snapshot callback and return its result (typically a JSON-serializable snapshot). |

## Method Details

### run
```py
def run(self, until: Optional[float] = None) -> bool
```
Run the simulation loop. If an exception occurs in a process:
- If `raise_on_error` is True (default), the exception is re-raised after
  the engine sets its state to `ERROR` and records timing information.
- If `raise_on_error` is False, the exception is stored in
  `last_exception`, `on_error` is invoked (if provided), pending events
  are cleared, and `run()` returns `False`.

### step_to_time
```
def step_to_time(self, target_time: float) -> bool
```
Advance the simulation until `target_time`. This method delegates to the
underlying `Environment` to run scheduled events up to (and including)
the specified simulation time. Return value semantics mirror `run()`:
- If `raise_on_error` is True, exceptions raised by processes will be
  re-raised.
- If `raise_on_error` is False, exceptions are captured to
  `last_exception`, `on_error` is invoked (if provided), pending events are
  cleared, and the method returns `False`.

`step_to_time` is useful for deterministic frame-based exporters that need
to sample the simulation at discrete times.

### step_by
```
def step_by(self, delta: float) -> bool
```
Convenience wrapper that advances the engine by `delta` seconds. It calls
`step_to_time(self.time() + float(delta))` internally and returns the same
boolean success value.

### set_snapshot_callback
```
def set_snapshot_callback(self, cb: Optional[Callable[[], Any]]) -> None
```
Register a snapshot callback used by `snapshot()`. The callback should be a
callable that captures the application-visible state of the simulation
(for example, actor transforms) and returns a JSON-serializable object.
If `cb` is `None`, any previously registered callback is cleared.

The engine does not interpret the callback's return value; exporters may
call `snapshot()` repeatedly to build timelines.

### snapshot
```
def snapshot(self) -> Any
```
Invoke the currently registered snapshot callback and return its result.
If no snapshot callback is registered, `snapshot()` returns `None`.
This method is synchronous and intended for use by exporters which sample
the simulation state at deterministic times (for example, after calling
`step_to_time`).

### getLastException
```py
def getLastException(self)
```
Return the last captured exception or `None` if none was captured.

