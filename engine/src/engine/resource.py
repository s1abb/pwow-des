import heapq
import itertools
import logging

from .event import Event

logger = logging.getLogger(__name__)


class Token:
    """Token representing an acquired unit from a Resource.

    It is a context-manager: exiting the context releases the token back to
    the resource (calls `Resource.release(token=self)`).

    Tokens now carry an optional `name` and the `allocated_at` timestamp so
    callers (and examples) can pretty-print who holds what and for how long.
    """
    _id_iter = itertools.count()

    def __init__(self, resource, proc, name=None, allocated_at=None):
        self.resource = resource
        self.proc = proc
        self.name = name
        # timestamp when this token was allocated (env.now at allocation)
        self.allocated_at = allocated_at
        # small numeric id to make tokens easy to distinguish in prints
        self.id = next(Token._id_iter)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        # release this token back to the resource
        try:
            self.resource.release(token=self)
        except Exception:
            # swallow release errors to not mask original exceptions
            pass

    def __repr__(self):
        name = f" name={self.name!r}" if self.name is not None else ""
        at = f" allocated_at={self.allocated_at}" if self.allocated_at is not None else ""
        return f"<Token id={self.id}{name}{at} proc={self.proc}>"


class Request(Event):
    def __init__(self, resource):
        # don't set env here; Event.on_yield will do that when the process
        # yields this Request
        super().__init__(env=None)
        self.resource = resource
        # optional behavior parameters; populated via factory call
        self.timeout = None
        self.priority = 0
        # optional friendly name to attach to any Token created for this request
        self.name = None
        self._active = False

    def on_yield(self, env, proc):
        """Called by Process._resume when this object is yielded.

        This hooks the process up to this Request (via Event.on_yield) so that
        when the Request is granted we call `self.succeed(token)` and the
        subscribed callback will schedule the process with the token value.
        """
        res = self.resource
        _logger = logging.getLogger(__name__)

        # register the process callback (and set self.env)
        super().on_yield(env, proc)

        # If resource has immediate availability, allocate and succeed the
        # request now. We must succeed after subscribing so the callback will
        # be invoked and the process scheduled with the token.
        if res.available > 0:
            token = Token(res, proc, name=getattr(self, "name", None), allocated_at=env.now)
            _logger.debug("Granting token %r to proc=%r at time=%s", token, proc, env.now)
            # store allocation metadata: (proc, token, priority, preemptible)
            res.allocated.append((proc, token, getattr(self, "priority", 0), getattr(self, "preemptible", False)))
            res.available -= 1
            # succeed the Request so registered callbacks resume the process
            self.succeed(token)
            return

        # otherwise queue with priority and seq to ensure stable ordering
        self._active = True
        seq = next(res._seq)
        heapq.heappush(res.waiters, (self.priority, seq, proc, env, self))
        # if a timeout was requested, schedule a timeout callback
        if self.timeout is not None:
            cb = _TimeoutCallback(res, proc, self, env)
            env._schedule(float(self.timeout), cb)
        # if the resource supports preemption, attempt it now
        if hasattr(res, "_try_preempt"):
            victim_proc = res._try_preempt(self)
            if victim_proc is not None:
                # schedule Preempted into the victim immediately
                env._schedule(0.0, victim_proc, Preempted())
                # and, if capacity freed, grant this request immediately
                if res.available > 0:
                    token = Token(res, proc, name=getattr(self, "name", None), allocated_at=env.now)
                    res.allocated.append((proc, token, getattr(self, "priority", 0), getattr(self, "preemptible", False)))
                    res.available -= 1
                    self.succeed(token)

    def __repr__(self):
        return f"<Request resource={self.resource}>"


class Resource:
    def __init__(self, capacity=1):
        self.capacity = int(capacity)
        self.available = int(capacity)
        # allocated holds tuples of (proc, token)
        self.allocated = []
        # waiters holds tuples of (proc, env)
        # use a heap: (priority, seq, proc, env, request)
        self.waiters = []
        self._seq = itertools.count()

    def request(self):
        return Request(self)

    def request_with(self, timeout=None, priority=0):
        r = Request(self)
        r.timeout = timeout
        r.priority = int(priority)
        return r

    def release(self, proc=None, token=None):
        """Release one unit from the resource.

        You may specify either `proc` (process) or `token` (the token returned
        by the yield) to release a specific allocation. If neither is
        provided, the oldest allocation is removed (FIFO).

        After freeing a unit, if waiters exist and capacity allows, the next
        waiter is allocated and resumed (using the env saved when it requested
        the resource).
        """
        removed = False

        # remove by token if given
        if token is not None:
            for i, entry in enumerate(self.allocated):
                aproc, atoken = entry[0], entry[1]
                if atoken is token:
                    self.allocated.pop(i)
                    removed = True
                    break

        # remove by proc if given
        if not removed and proc is not None:
            for i, entry in enumerate(self.allocated):
                aproc = entry[0]
                if aproc is proc:
                    self.allocated.pop(i)
                    removed = True
                    break

        # remove oldest if still nothing removed AND caller didn't specify
        # a token or proc. If the caller provided a token or proc and we
        # didn't find it, that means the allocation was already removed
        # (for example by preemption) and we must NOT remove another
        # allocation here — that would incorrectly free an extra unit and
        # lead to duplicated grants. Only when neither `token` nor `proc`
        # were given should we pop the oldest allocation (FIFO).
        if not removed and proc is None and token is None and self.allocated:
            self.allocated.pop(0)
            removed = True

        if removed:
            self.available += 1

        # allocate to waiters by priority, skipping inactive entries
        while self.waiters and self.available > 0:
            # peek at top
            prio, seq, next_proc, next_env, req = self.waiters[0]
            if not getattr(req, "_active", False):
                heapq.heappop(self.waiters)
                logger.debug("skipping resource waiter (inactive) seq=%s", seq)
                continue
            heapq.heappop(self.waiters)
            # allocate to this waiter
            req._active = False
            token2 = Token(self, next_proc, name=getattr(req, "name", None), allocated_at=next_env.now)
            self.allocated.append((next_proc, token2, getattr(req, "priority", 0), getattr(req, "preemptible", False)))
            self.available -= 1
            # succeed the Request event so its subscribed callback schedules
            # the waiting process with the token value.
            try:
                req.succeed(token2)
            except Exception:
                # If succeed raises for some reason, schedule the resume
                # directly as a fallback.
                next_env._schedule(0.0, next_proc, token2)

    def _expire_waiter(self, proc, req, env):
        """Called by timeout callback: mark request inactive and if still
        queued, schedule a RequestTimeout exception into the waiting process.
        """
        if not getattr(req, "_active", False):
            logger.debug("expire called for inactive request proc=%s", proc)
            return
        # mark inactive so release will skip it
        req._active = False
        # notify the Request that it failed due to timeout; this will trigger
        # the Request's callbacks to schedule the waiting process with the
        # exception value that `Event._result()` returns (a BaseException),
        # which Process._resume will throw into the generator.
        try:
            req._active = False
            req.fail(RequestTimeout())
        except Exception:
            # fallback: schedule exception directly
            env._schedule(0.0, proc, RequestTimeout())

    def snapshot(self, current_time=None):
        """Return a structured snapshot of current allocations.

        Each allocation is returned as a dict with keys:
        - proc: the process object
        - token_id: numeric token id (or None)
        - token_name: token.name if present
        - allocated_at: token.allocated_at if present
        - held_for: computed as current_time - allocated_at if current_time provided
        - priority: recorded priority for the allocation
        - preemptible: boolean

        This helper is intended for programs and monitoring tools so they don't
        need to duplicate allocation unpacking logic.
        """
        snaps = []
        for entry in self.allocated:
            # entry expected: (proc, token, priority, preemptible)
            proc = entry[0]
            token = entry[1] if len(entry) > 1 else None
            prio = entry[2] if len(entry) > 2 else None
            preempt = entry[3] if len(entry) > 3 else None
            token_id = getattr(token, 'id', None)
            token_name = getattr(token, 'name', None)
            allocated_at = getattr(token, 'allocated_at', None)
            held_for = None
            if current_time is not None and allocated_at is not None:
                held_for = float(current_time) - float(allocated_at)
            snaps.append({
                'proc': proc,
                'token_id': token_id,
                'token_name': token_name,
                'allocated_at': allocated_at,
                'held_for': held_for,
                'priority': prio,
                'preemptible': preempt,
            })
        return snaps

    def pretty_allocations(self, current_time=None):
        """Return a compact, human-readable list of allocation tuples.

        Each item is a tuple: (proc, token_id, token_name, allocated_at, held_for, priority, preemptible)
        """
        snaps = self.snapshot(current_time=current_time)
        out = []
        for s in snaps:
            out.append((s['proc'], s['token_id'], s['token_name'], s['allocated_at'], s['held_for'], s['priority'], s['preemptible']))
        return out

    def pretty_print(self, current_time=None, proc_name_map=None):
        """Return pretty_allocations with the `proc` element replaced by a
        friendly name when available.

        - `current_time` is forwarded to `pretty_allocations` so `held_for` is
          computed.
        - `proc_name_map` is an optional dict mapping process objects to
          friendly strings (e.g., proc -> 'worker-1'). If a proc is not in the
          map, the proc's `__repr__()` is used.

        The returned list contains tuples:
        (proc_name, token_id, token_name, allocated_at, held_for, priority, preemptible)
        """
        allocs = self.pretty_allocations(current_time=current_time)

        def _proc_name(proc):
            if proc_name_map is not None and proc in proc_name_map:
                return proc_name_map[proc]
            # prefer the proc's __repr__ bound method when available
            repr_fn = getattr(proc, '__repr__', None)
            try:
                if callable(repr_fn):
                    return repr_fn()
            except Exception:
                pass
            return str(proc)

        pretty = [(_proc_name(a[0]), a[1], a[2], a[3], a[4], a[5], a[6]) for a in allocs]
        return pretty

    def pretty_print_to_stdout(self, current_time=None, proc_name_map=None, context=""):
        """Print a human-friendly summary of this Resource to stdout.

        - `current_time` should be provided (e.g., `env.now`) to calculate
          `held_for` values; if omitted, held_for will be None.
        - `proc_name_map` is an optional mapping from proc objects to friendly
          names.
        - `context` is an optional string included in the header.
        """
        pretty = self.pretty_print(current_time=current_time, proc_name_map=proc_name_map)
        # header line
        if current_time is None:
            time_str = "?"
        else:
            time_str = f"{float(current_time)}"
        print(f"[{time_str}] STATE {context}: available={self.available} allocated_count={len(self.allocated)} waiters_count={len(self.waiters)}")
        if pretty:
            print(f"[{time_str}] STATE allocations (proc, token_id, token_name, allocated_at, held_for, priority, preemptible)={pretty}")
        if self.waiters:
            waiters = [(w[0], w[1]) for w in self.waiters]
            print(f"[{time_str}] STATE waiters (priority, seq)={waiters}")

    def pretty_print_to_logger(self, logger, level=None, current_time=None, proc_name_map=None, context=""):
        """Log a pretty-printed resource snapshot through the provided logger.

        - `logger` is a standard Python logger.
        - `level` is an optional logging level (default: logging.INFO).
        Other parameters are forwarded to `pretty_print_to_stdout` but the
        formatted lines are sent to the logger instead of stdout.
        """
        import logging

        if level is None:
            level = logging.INFO

        pretty = self.pretty_print(current_time=current_time, proc_name_map=proc_name_map)
        if current_time is None:
            time_str = "?"
        else:
            time_str = f"{float(current_time)}"
        header = f"[{time_str}] STATE {context}: available={self.available} allocated_count={len(self.allocated)} waiters_count={len(self.waiters)}"
        logger.log(level, header)
        if pretty:
            logger.log(level, f"[{time_str}] STATE allocations (proc, token_id, token_name, allocated_at, held_for, priority, preemptible)={pretty}")
        if self.waiters:
            waiters = [(w[0], w[1]) for w in self.waiters]
            logger.log(level, f"[{time_str}] STATE waiters (priority, seq)={waiters}")

    def __str__(self):
        # compact textual representation using pretty_allocations; avoid importing env here
        allocs = self.pretty_allocations()
        return f"<Resource cap={self.capacity} avail={self.available} allocations={allocs}>"


class RequestTimeout(Exception):
    """Raised into a process when a resource request times out."""
    pass


class _TimeoutCallback:
    def __init__(self, resource, proc, req, env):
        self.resource = resource
        self.proc = proc
        self.req = req
        self.env = env

    def _resume(self, value=None):
        # delegate to resource to expire waiter and raise timeout into proc
        self.resource._expire_waiter(self.proc, self.req, self.env)

    def __repr__(self):
        # safe repr that doesn't assume attributes on Resource here
        return f"<_TimeoutCallback for resource>"


class Preempted(Exception):
    """Raised into a process when it is preempted by a higher-priority requester."""


class PreemptiveResource(Resource):
    """Resource that supports preemption of holders by higher-priority waiters.

    Note: priority numeric interpretation: lower number == higher priority.
    """
    def __init__(self, capacity=1):
        super().__init__(capacity=capacity)

    def request_with(self, timeout=None, priority=0, preemptible=False):
        r = Request(self)
        r.timeout = timeout
        r.priority = int(priority)
        r.preemptible = bool(preemptible)
        return r

    def _try_preempt(self, req):
        """Try to preempt current holders if the incoming request has higher
        priority than some holders and those holders are preemptible.
        Returns True if preemption occurred and the request can be granted.
        """
        # find any allocated holder with lower priority (higher numeric value)
        # that is preemptible. For simplicity, stored allocations don't carry
        # priority yet; this minimal implementation will preempt the first
        # allocated holder unconditionally if it is preemptible.
        # request priority (lower value is higher priority)
        rprio = getattr(req, "priority", 0)
        # find candidate victims with lower priority (higher numeric value)
        for i, entry in enumerate(self.allocated):
            aproc, atoken, aprio, apreempt = entry
            if apreempt and aprio > rprio:
                # remove this allocation and return victim
                self.allocated.pop(i)
                self.available += 1
                return aproc
        return None
