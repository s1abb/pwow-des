import heapq
import itertools
from .event import ScheduledEvent
from .process import Process

class Environment:
    """Minimal discrete-event environment using a heap-based event queue.

    Scheduling model: processes yield `Timeout(delay)` or a numeric value to
    request resumption after `delay` units. Time advances to the scheduled
    event time just before the process is resumed.
    """
    def __init__(self):
        self.now = 0.0
        self._queue = []  # heap of ScheduledEvent
        self._seq = itertools.count()

    def _schedule(self, delay, proc, value=None):
        t = float(self.now) + float(delay)
        seq = next(self._seq)
        heapq.heappush(self._queue, ScheduledEvent(t, seq, proc, value))

    def process(self, generator_or_callable):
        """Wrap a generator function or generator into a `Process` and start it.

        Accepts either a generator object (e.g. `proc()`) or a callable that
        returns a generator (e.g. `lambda: proc()` or the function object).
        """
        if callable(generator_or_callable):
            gen = generator_or_callable()
        else:
            gen = generator_or_callable
        return Process(self, gen)

    def timeout(self, delay: float):
        """Convenience alias producing a `Timeout` yieldable (API parity).

        Usage: `yield env.timeout(3)`
        """
        # Return an Event that will be triggered after `delay`.
        from .event import TimerEvent as _TimerEvent

        return _TimerEvent(self, delay)

    def timeout_bool(self, delay: float):
        """Return an Event that succeeds with `True` when the delay elapses.

        Usage: `fired = yield from env.timeout_bool(5).wait()` — `fired` will be
        `True` when the timer fired.
        """
        from .event import TimerEventBool as _TimerEventBool

        return _TimerEventBool(self, delay)

    def run(self, until=None):
        """Run the simulation until the event queue is empty or time reaches `until`.

        Returns the time reached (self.now).
        """
        while self._queue:
            ev = heapq.heappop(self._queue)
            if until is not None and ev.time > until:
                # reinsert event and stop at 'until'
                heapq.heappush(self._queue, ev)
                self.now = float(until)
                return self.now
            # advance time
            self.now = ev.time
            # If this is a Process, run with its lifecycle checks
            if isinstance(ev.proc, Process):
                # skip dead processes
                if not getattr(ev.proc, "_alive", False):
                    continue
                # if process was cancelled after it started, skip future resumes
                if getattr(ev.proc, "_cancelled", False) and getattr(ev.proc, "_started", False):
                    continue
                ev.proc._resume(ev.value)
                continue

            # If the scheduled object is not a Process but provides a _resume
            # method (e.g., callback objects), call it directly.
            resume = getattr(ev.proc, "_resume", None)
            if callable(resume):
                resume(ev.value)
        return self.now

    def interrupt(self, proc, exc=None, delay: float = 0.0):
        """Interrupt a process by scheduling an exception to be thrown into it.

        Parameters
        - proc: Process to interrupt
        - exc: Exception instance to throw (default: `Interrupt()`)
        - delay: optional delay (float) until the interrupt is delivered

        Backwards-compatible behaviors:
        - interrupt(proc, Interrupt()) -> immediate interrupt
        - interrupt(proc, 1.0) -> delayed interrupt (positional numeric)
        - interrupt(proc, exc=Interrupt(), delay=1.0) -> delayed interrupt (keyword)
        """
        # allow calling as interrupt(proc, delay) where exc is numeric
        if isinstance(exc, (int, float)) and delay == 0.0:
            delay = float(exc)
            exc = None

        if exc is None:
            from .interrupt import Interrupt as _Interrupt

            exc = _Interrupt()

        self._schedule(float(delay), proc, exc)

    def next_event_time(self):
        return self._queue[0].time if self._queue else None
