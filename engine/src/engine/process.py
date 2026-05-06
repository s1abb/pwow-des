from .timeout import Timeout
import logging

logger = logging.getLogger(__name__)

class Process:
    """Simple generator-based process wrapper.

    The wrapped generator should be a Python generator that yields either:
    - a `Timeout` instance, or
    - a numeric delay (seconds), or
    - anything else (treated as immediate resume).
    """
    def __init__(self, env, generator):
        self.env = env
        self._gen = generator
        self._alive = True
        self._cancelled = False
        self._started = False
        # track what the process last yielded (type name) to detect races
        # where an unrelated Event (e.g. TimerEvent) may schedule a numeric
        # resume into a process that is actually waiting on a Resource
        # Request. In that case we should ignore the numeric resume and wait
        # for the Resource grant (Token) to arrive.
        self._waiting_for_type = None
        # schedule first activation immediately (delay 0)
        self.env._schedule(0.0, self)

    def _resume(self, value=None):
        if not self._alive:
            return
        # mark that this process has begun executing at least once
        self._started = True
        # If the process is currently known to be waiting on a Request and a
        # numeric value (typically a TimerEvent timestamp) is delivered, it
        # is likely a racing timer firing that was scheduled at the same time
        # as a resource grant. Ignore such numeric resumes so the process
        # receives the actual Token when the Resource grants it.
        if self._waiting_for_type == 'Request' and not isinstance(value, BaseException):
            # numeric timer values are floats/ints; if we get such a value
            # while waiting on a Request, silently ignore it.
            if isinstance(value, (int, float)):
                return
        try:
            if isinstance(value, BaseException):
                # throw exception into generator so it can catch it
                yielded = self._gen.throw(value)
            else:
                yielded = self._gen.send(value)
        except StopIteration:
            # Process finished normally
            self._alive = False
            logger.debug("Process finished: %r", self)
            return
        except Exception:
            # log unexpected exceptions and mark process dead
            self._alive = False
            logger.exception("Process %r raised an unexpected exception and will be terminated", self)
            # Re-raise so the Engine.run() can transition to ERROR and
            # enforce the exception handling contract.
            raise
        # yielded can be a Timeout object or a numeric delay
        from .timeout import Timeout as _Timeout

        if isinstance(yielded, _Timeout):
            # clear waiting marker (we're now waiting on a Timeout)
            self._waiting_for_type = 'Timeout'
            self.env._schedule(yielded.delay, self)
        elif isinstance(yielded, (int, float)):
            # waiting on a raw numeric delay
            self._waiting_for_type = 'numeric'
            self.env._schedule(float(yielded), self)
        else:
            # If the yielded object has an `on_yield(env, proc)` hook, call it
            hook = getattr(yielded, "on_yield", None)
            if callable(hook):
                # remember the yielded type name so we can detect races when
                # unrelated events later schedule numeric resumes into this
                # process.
                try:
                    self._waiting_for_type = type(yielded).__name__
                except Exception:
                    self._waiting_for_type = None
                # call the object's on_yield hook; the yielded Event will be
                # responsible for scheduling/resuming this process when ready.
                hook(self.env, self)
            else:
                # unsupported yield; treat as immediate
                self._waiting_for_type = None
                self.env._schedule(0.0, self)

    def interrupt(self, exc=None):
        """Interrupt this process by scheduling an exception to be thrown
        into the process at the next immediate activation.

        `exc` should be an Exception instance (default: `Interrupt()`).
        """
        if self._cancelled or not self._alive:
            return
        # delegate to environment's public interrupt API
        self.env.interrupt(self, exc)

    def cancel(self):
        """Cancel this process. Future scheduled resumes will be skipped."""
        self._cancelled = True

    def __repr__(self):
        return f"<Process alive={self._alive}>"
