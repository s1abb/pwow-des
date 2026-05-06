import heapq
import time
from typing import Optional, Callable

from .environment import Environment
from .event import ScheduledEvent
from .process import Process


class Engine:
    """Simple simulation Engine facade.

    The Engine wraps an `Environment` and provides lifecycle control
    (start/run/step/pause/stop/finish) plus a small set of introspection
    helpers. Error handling is configurable:

    - `raise_on_error` (default True): if True, exceptions raised by
      processes will be re-raised from `run()`/`step()` after the engine
      records the error state. If False, the exception is captured into
      `last_exception` and `run()`/`step()` return False.
    - `on_error`: optional callback `on_error(exc, engine)` invoked when
      an exception occurs; exceptions from the callback are ignored.

    Use `getLastException()` to retrieve the captured exception.
    """

    IDLE = 'IDLE'
    PAUSED = 'PAUSED'
    RUNNING = 'RUNNING'
    FINISHED = 'FINISHED'
    ERROR = 'ERROR'
    PLEASE_WAIT = 'PLEASE_WAIT'

    def __init__(self, time_func: Optional[Callable[[], float]] = None):
        # allow injecting a monotonic time source for deterministic tests
        self._time_func = time_func or time.monotonic
        self.env = Environment()
        self._state = Engine.IDLE
        self._root = None
        self._step_count = 0
        self._run_count = 0
        self._start_wall = None
        self._last_run_ms = 0
        # error handling configuration and last exception storage
        self.raise_on_error = True
        self.on_error = None
        self.last_exception = None

        # control flags
        self._pause_requested = False
        self._stop_requested = False
        self._finish_requested = False

    # Lifecycle API
    def start(self, root) -> bool:
        if self._state != Engine.IDLE:
            return False
        # set root and schedule it if callable/generator
        self._root = root
        if root is not None:
            try:
                self.env.process(root)
            except Exception:
                # if env.process raises, still record root
                pass
        self._state = Engine.PAUSED
        return True

    def run(self, until: Optional[float] = None) -> bool:
        if self._state == Engine.RUNNING:
            return False
        self._pause_requested = False
        self._stop_requested = False
        self._finish_requested = False
        self._state = Engine.RUNNING
        self._run_count += 1
        self._start_wall = self._time_func()

        # run loop (single-threaded) using environment queue so we can
        # honor pause/finish/stop requests between events.
        while self.env._queue:
            ev = heapq.heappop(self.env._queue)
            if until is not None and ev.time > until:
                heapq.heappush(self.env._queue, ev)
                self.env.now = float(until)
                break

            # advance time and execute
            self.env.now = ev.time

            # if stop requested, clear queue and go to IDLE
            if self._stop_requested:
                self.env._queue.clear()
                self._state = Engine.IDLE
                self._last_run_ms = int((time.monotonic() - self._start_wall) * 1000)
                return True

            # dispatch - wrap in try/except so Engine can enforce a clear
            # exception handling contract: any exception raised while
            # dispatching an event will set the Engine state to ERROR,
            # record run-time, and either re-raise or capture the exception
            try:
                if isinstance(ev.proc, Process):
                    # skip dead/cancelled similar to Environment.run
                    if not getattr(ev.proc, "_alive", False):
                        continue
                    if getattr(ev.proc, "_cancelled", False) and getattr(ev.proc, "_started", False):
                        continue
                    ev.proc._resume(ev.value)
                    self._step_count += 1
                else:
                    resume = getattr(ev.proc, "_resume", None)
                    if callable(resume):
                        resume(ev.value)
            except Exception as exc:
                # set ERROR state and record elapsed time
                self._state = Engine.ERROR
                self._last_run_ms = int((self._time_func() - self._start_wall) * 1000)
                # clear pending events to avoid continuing in a broken state
                self.env._queue.clear()
                # store exception for inspection
                self.last_exception = exc
                # call optional on_error callback
                if callable(self.on_error):
                    try:
                        self.on_error(exc, self)
                    except Exception:
                        # ignore errors from the callback
                        pass
                # either re-raise or return False depending on configuration
                if self.raise_on_error:
                    raise
                return False

            # if finish requested, stop after current event
            if self._finish_requested:
                self._state = Engine.FINISHED
                self._last_run_ms = int((self._time_func() - self._start_wall) * 1000)
                return True

            # if pause requested, stop after current event and become PAUSED
            if self._pause_requested:
                self._state = Engine.PAUSED
                self._last_run_ms = int((self._time_func() - self._start_wall) * 1000)
                return True

        # queue empty
        self._state = Engine.FINISHED
        self._last_run_ms = int((self._time_func() - self._start_wall) * 1000)
        return True

    def pause(self) -> bool:
        if self._state != Engine.RUNNING:
            return False
        self._pause_requested = True
        return True

    def step(self) -> bool:
        # Execute at most one scheduled event (like a single discrete step)
        if not self.env._queue:
            # no events
            self._state = Engine.FINISHED
            return False
        ev = heapq.heappop(self.env._queue)
        self.env.now = ev.time
        try:
            if isinstance(ev.proc, Process):
                if not getattr(ev.proc, "_alive", False):
                    return False
                if getattr(ev.proc, "_cancelled", False) and getattr(ev.proc, "_started", False):
                    return False
                ev.proc._resume(ev.value)
                self._step_count += 1
            else:
                resume = getattr(ev.proc, "_resume", None)
                if callable(resume):
                    resume(ev.value)
        except Exception as exc:
            self._state = Engine.ERROR
            self._last_run_ms = int((self._time_func() - self._start_wall) * 1000) if self._start_wall else 0
            self.env._queue.clear()
            self.last_exception = exc
            if callable(self.on_error):
                try:
                    self.on_error(exc, self)
                except Exception:
                    pass
            if self.raise_on_error:
                raise
            return False
        # after a single step keep engine paused
        self._state = Engine.PAUSED
        return True

    def step_to_time(self, target_time: float) -> bool:
        """Run the underlying Environment until env.now >= target_time.

        Returns True if the engine reached the requested time (or if
        target_time <= current time). Exceptions during processing follow
        the engine's exception handling contract (captured or re-raised
        depending on `raise_on_error`).
        """
        try:
            # no-op if target_time is not in the future
            if target_time <= float(self.env.now):
                return True
            # delegate to Environment.run for scheduling semantics
            self.env.run(until=float(target_time))
            return True
        except Exception as exc:
            # mirror Engine.run exception handling semantics
            self._state = Engine.ERROR
            self.last_exception = exc
            if callable(self.on_error):
                try:
                    self.on_error(exc, self)
                except Exception:
                    pass
            if self.raise_on_error:
                raise
            return False

    def step_by(self, delta: float) -> bool:
        """Convenience: advance the simulation by `delta` simulation seconds."""
        return self.step_to_time(float(self.env.now) + float(delta))

    # Snapshot API
    def set_snapshot_callback(self, cb):
        """Register a snapshot callback.

        The callback will be called with no arguments and should return a
        JSON-serializable structure representing actor states. This keeps
        engine decoupled from actor implementations and exporters.
        """
        self._snapshot_cb = cb

    def snapshot(self):
        """Return a snapshot produced by the registered callback or an empty list.

        The snapshot is intended to be a list/dict describing actor states
        and is suitable for writing to JSON by exporters.
        """
        cb = getattr(self, "_snapshot_cb", None)
        if cb is None:
            return []
        try:
            return cb()
        except Exception:
            # snapshot should not raise; return empty on error
            return []

    def stop(self) -> bool:
        # Clear pending events and reset state to IDLE
        self.env._queue.clear()
        self._state = Engine.IDLE
        self._root = None
        return True

    def finish(self) -> bool:
        # Request termination after current event
        if self._state != Engine.RUNNING:
            return False
        self._finish_requested = True
        return True

    # Introspection
    def time(self) -> float:
        return float(self.env.now)

    def getState(self) -> str:
        return self._state

    def getRoot(self):
        return self._root

    def getStep(self) -> int:
        return int(self._step_count)

    def getEventCount(self) -> int:
        return len(self.env._queue)

    def getNextEventTime(self) -> Optional[float]:
        return self.env._queue[0].time if self.env._queue else None

    def getRunCount(self) -> int:
        return int(self._run_count)

    def getRunTimeMillis(self) -> int:
        return int(self._last_run_ms)

    def getStartTimeMillis(self) -> Optional[int]:
        return None if self._start_wall is None else int(self._start_wall * 1000)

    def getLastException(self):
        """Return the last captured exception or None if none was captured."""
        return self.last_exception


__all__ = ["Engine"]

def export_timeline(engine, path: str, format: str = "auto", **kwargs):
    """Convenience top-level function to export a timeline from an Engine.

    Kept separate from the Engine class to simplify imports from the addon
    without importing the entire Engine object.
    """
    from .timeline_export import export_timeline as _export

    return _export(engine, path, format=format, **kwargs)
