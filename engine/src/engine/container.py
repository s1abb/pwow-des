import heapq

import itertools
import logging

logger = logging.getLogger(__name__)


class ContainerRequestTimeout(Exception):
    """Raised when a Container request times out."""
    pass


class _TimeoutCallback:
    def __init__(self, container, proc, req, env):
        self.container = container
        self.proc = proc
        self.req = req
        self.env = env

    def _resume(self, value=None):
        self.container._expire_waiter(self.proc, self.req, self.env)


class ContainerRequest:
    def __init__(self, container, amount, is_put=False):
        self.container = container
        self.amount = amount
        self.is_put = is_put
        self.priority = 0
        self._active = False
        self.timeout = None

    def on_yield(self, env, proc):
        c = self.container
        if self.is_put:
            # can we put amount (not exceeding capacity)?
            if c.level + self.amount <= c.capacity:
                c.level += self.amount
                env._schedule(0.0, proc, None)
                # wake getters if possible
                c._drain_getters(env)
                return
        else:
            # get request
            if c.level >= self.amount:
                c.level -= self.amount
                env._schedule(0.0, proc, None)
                # wake putters if there's space now
                c._drain_putters(env)
                return

        # otherwise queue
        self._active = True
        seq = next(c._seq)
        heapq.heappush(c.waiters, (self.priority, seq, proc, env, self))
        if self.timeout is not None:
            cb = _TimeoutCallback(c, proc, self, env)
            env._schedule(float(self.timeout), cb)


class Container:
    def __init__(self, capacity):
        self.capacity = float(capacity)
        self.level = 0.0
        self.waiters = []
        self._seq = itertools.count()
        # user-defined metadata/annotations attached to this Container
        # callers may store small flags or objects here (e.g., "truck_pending").
        # Prefer using the helper methods below to access this dict.
        self.meta = {}

    def set_meta(self, key, value):
        """Set a metadata key on this Container.

        This is a convenience wrapper around the `meta` dict and is
        provided for clearer caller intent (storing small flags or objects
        alongside the Container). Example:

            container.set_meta('truck_pending', True)

        Parameters
        - key: hashable key
        - value: any Python object to store
        """
        self.meta[key] = value

    def get_meta(self, key, default=None):
        """Return the metadata value for ``key`` or ``default`` if missing.

        This wraps ``self.meta.get(key, default)`` and provides a clearer
        call site for consumers of the Container API.
        """
        return self.meta.get(key, default)

    def put_with(self, amount, timeout=None, priority=0):
        r = ContainerRequest(self, float(amount), is_put=True)
        r.timeout = timeout
        r.priority = int(priority)
        return r

    def get_with(self, amount, timeout=None, priority=0):
        r = ContainerRequest(self, float(amount), is_put=False)
        r.timeout = timeout
        r.priority = int(priority)
        return r

    def _expire_waiter(self, proc, req, env):
        if not getattr(req, "_active", False):
            return
        req._active = False
        env._schedule(0.0, proc, ContainerRequestTimeout())

    def put(self, amount):
        return ContainerRequest(self, float(amount), is_put=True)

    def get(self, amount):
        return ContainerRequest(self, float(amount), is_put=False)

    def _drain_getters(self, env):
        # attempt to satisfy waiting `get` requests
        import heapq
        changed = True
        while self.waiters and changed:
            changed = False
            prio, seq, proc, penv, req = self.waiters[0]
            if not req._active:
                heapq.heappop(self.waiters)
                logger.debug("skipping container waiter (inactive) seq=%s", seq)
                continue
            if getattr(proc, "_cancelled", False):
                heapq.heappop(self.waiters)
                req._active = False
                logger.debug("skipping container waiter (cancelled) proc=%s seq=%s", proc, seq)
                continue
            if not req.is_put and self.level >= req.amount:
                heapq.heappop(self.waiters)
                req._active = False
                self.level -= req.amount
                penv._schedule(0.0, proc, None)
                changed = True

    def _drain_putters(self, env):
        # attempt to satisfy waiting `put` requests
        import heapq
        changed = True
        while self.waiters and changed:
            changed = False
            prio, seq, proc, penv, req = self.waiters[0]
            if not req._active:
                heapq.heappop(self.waiters)
                logger.debug("skipping container waiter (inactive) seq=%s", seq)
                continue
            if getattr(proc, "_cancelled", False):
                heapq.heappop(self.waiters)
                req._active = False
                logger.debug("skipping container waiter (cancelled) proc=%s seq=%s", proc, seq)
                continue
            if req.is_put and self.level + req.amount <= self.capacity:
                heapq.heappop(self.waiters)
                req._active = False
                self.level += req.amount
                penv._schedule(0.0, proc, None)
                changed = True
