import heapq
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional


@dataclass(order=True)
class ScheduledEvent:
    """Small container used by Environment's event heap.

    Fields match the ordering used by the scheduler: time, seq, proc, value.
    """
    time: float
    seq: int
    proc: Any
    value: Any = None


class Event:
    """A lightweight event that processes can yield to wait for.

    Usage:
      e = Event()
      yield e            # wait until e.succeed(value) or e.fail(exc)
      e.succeed(42)
    """

    def __init__(self, env=None):
        self.env = env
        self._callbacks: List[Callable[[Any], None]] = []
        self._triggered = False
        self._value = None
        self._exc: Optional[BaseException] = None

    # on_yield hook used by Process._resume: register proc to be resumed
    def on_yield(self, env, proc):
        # compatibility helper for Process._resume — subscribe a callback that
        # schedules the proc when the event triggers.
        def _schedule_proc():
            env._schedule(0.0, proc, self._result())

        # store env reference for convenience
        self.env = env
        if self._triggered:
            # event already fired: schedule immediate resume
            env._schedule(0.0, proc, self._result())
            return
        self.subscribe(_schedule_proc)

    def subscribe(self, callback: Callable[[], None]):
        """Register a callback to be invoked when the event triggers.

        The callback is invoked without arguments at trigger time. Returns a
        callable that can be used to unsubscribe.
        """
        if self._triggered:
            # if already triggered, invoke immediately (synchronous)
            try:
                callback()
            except Exception:
                pass
            # return a noop unsubscribe
            return lambda: None

        self._callbacks.append(callback)

        def _unsubscribe():
            try:
                self._callbacks.remove(callback)
            except ValueError:
                pass

        return _unsubscribe

    def unsubscribe(self, callback: Callable[[], None]):
        try:
            self._callbacks.remove(callback)
        except ValueError:
            pass

    def _result(self):
        if self._exc is not None:
            return self._exc
        return self._value

    def wait(self):
        """Coroutine helper: yield from event.wait() returns the event value or
        raises the exception delivered to the event.
        """
        val = yield self
        if isinstance(val, BaseException):
            raise val
        return val

    def fail(self, exc: BaseException):
        """Fail this event with the provided exception.

        This marks the event as triggered with an exception which will be
        returned by `_result()` and cause the waiting process to receive an
        exception object (which Process._resume will throw into the generator).
        """
        if self._triggered:
            return
        self._triggered = True
        self._exc = exc
        for cb in list(self._callbacks):
            try:
                cb()
            except Exception:
                pass
        self._callbacks.clear()

    def succeed(self, value=None):
        if self._triggered:
            return
        self._triggered = True
        self._value = value
        # schedule all waiting callbacks at current env time
        for cb in list(self._callbacks):
            try:
                cb()
            except Exception:
                # swallow scheduling errors — env will handle them
                pass
        # clear callbacks to avoid memory leaks
        self._callbacks.clear()

    # convenience alias
    def trigger(self, value=None):
        """Alias for `succeed` offering a shorter name used in tests/examples."""
        self.succeed(value)


class TimerEvent(Event):
    """An Event that auto-succeeds after a scheduled delay.

    This wraps the existing scheduler so users can `yield env.timeout(1)` and
    receive an `Event` instance that will succeed with value `None` when the
    delay elapses. It is useful for composing with `AllOf`/`AnyOf`.
    """

    def __init__(self, env, delay: float = 0.0):
        super().__init__(env)
        # schedule self to succeed after `delay` time units
        def _resume(_v):
            # when the scheduler invokes this, mark the event succeeded with
            # the current environment time (useful for compositions)
            # note: capture `env` from the outer scope
            self.succeed(env.now)

        env._schedule(delay, type("_TE", (), {"_resume": staticmethod(lambda v: _resume(v) )})())


class TimerEventBool(Event):
    """A TimerEvent variant that succeeds with `True` when the timeout fires.

    Useful when the caller only needs a boolean indicating the timeout fired
    rather than the timestamp.
    """

    def __init__(self, env, delay: float = 0.0):
        super().__init__(env)

        def _resume(_v):
            self.succeed(True)

        env._schedule(delay, type("_TEB", (), {"_resume": staticmethod(lambda v: _resume(v) )})())

    def fail(self, exc: BaseException):
        if self._triggered:
            return
        self._triggered = True
        self._exc = exc
        for cb in list(self._callbacks):
            try:
                cb()
            except Exception:
                pass
        self._callbacks.clear()


class AllOf(Event):
    """An Event that succeeds when all member events succeed.

    The value of the AllOf is a dict mapping member event -> value.
    If any member fails, AllOf fails with the same exception.
    """

    def __init__(self, events: Iterable[Event]):
        self.events = list(events)
        super().__init__()
        self._remaining = set(self.events)
        self._values: Dict[Event, Any] = {}

        for ev in self.events:
            # attach callback per member
            def make_cb(member):
                def _cb():
                    # if member already triggered, skip
                    if member in self._values:
                        return
                    # record value or exception
                    if getattr(member, "_exc", None) is not None:
                        # propagate failure
                        self.fail(member._exc)
                        return
                    self._values[member] = member._value
                    self._remaining.discard(member)
                    if not self._remaining:
                        self.succeed(dict(self._values))

                return _cb

            # If member already triggered, invoke cb immediately; otherwise
            # register a callback by using the member's on_yield hook with a
            # dummy process that executes cb when scheduled. We'll emulate
            # that by appending cb to member._callbacks when available.
            if getattr(ev, "_triggered", False):
                # member already triggered; call the logic directly
                if getattr(ev, "_exc", None) is not None:
                    self.fail(ev._exc)
                    return
                self._values[ev] = ev._value
                self._remaining.discard(ev)
            else:
                # subscribe a callback to handle when the member triggers
                unsub = ev.subscribe(make_cb(ev))
                # keep unsubscribe reference in case we need to cancel later
                # (not used currently but stored for clarity)
                # store on the member so garbage collection doesn't drop it
                setattr(ev, f"_unsub_allof_{id(self)}", unsub)

        # if all members were already triggered at creation time
        if not self._remaining and not self._triggered:
            self.succeed(dict(self._values))


class AnyOf(Event):
    """An Event that succeeds when the first member event succeeds.

    The value is a dict containing only the winning event -> value mapping.
    If all members fail, AnyOf fails with the last exception.
    """

    def __init__(self, events: Iterable[Event]):
        self.events = list(events)
        super().__init__()
        self._pending = set(self.events)

        for ev in self.events:
            if getattr(ev, "_triggered", False):
                if getattr(ev, "_exc", None) is not None:
                    # treat as a failure; record and continue
                    self._pending.discard(ev)
                    # if no pending left, fail with this exc
                    if not self._pending:
                        self.fail(ev._exc)
                        return
                    continue
                # member already succeeded; succeed AnyOf immediately
                self.succeed({ev: ev._value})
                return

            def make_cb(member):
                def _cb():
                    if self._triggered:
                        return
                    if getattr(member, "_exc", None) is not None:
                        # member failed: remove from pending and maybe fail
                        self._pending.discard(member)
                        if not self._pending:
                            self.fail(member._exc)
                        return
                    # member succeeded: succeed AnyOf with single mapping
                    self.succeed({member: member._value})

                return _cb

            # subscribe and keep unsubscribe reference similarly
            unsub = ev.subscribe(make_cb(ev))
            setattr(ev, f"_unsub_anyof_{id(self)}", unsub)
# ScheduledEvent is defined at module top to match Environment expectations
