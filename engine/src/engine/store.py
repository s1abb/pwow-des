from collections import deque
import heapq
import itertools
import logging

logger = logging.getLogger(__name__)


class StoreRequestTimeout(Exception):
    """Raised when a Store request times out."""
    pass


class _TimeoutCallback:
    def __init__(self, store, proc, req, env, is_put=False):
        self.store = store
        self.proc = proc
        self.req = req
        self.env = env
        self.is_put = is_put

    def _resume(self, value=None):
        if self.is_put:
            self.store._expire_putter(self.proc, self.req, self.env)
        else:
            self.store._expire_getter(self.proc, self.req, self.env)



class PutRequest:
    def __init__(self, store, item):
        self.store = store
        self.item = item
        self.priority = 0
        self._active = False
        self.timeout = None

    def on_yield(self, env, proc):
        s = self.store
        # if no capacity or space available, put immediately
        if s.capacity is None or len(s.items) < s.capacity:
            s.items.append(self.item)
            # if there are waiting getters, satisfy the oldest
            if s.get_waiters:
                # pop until we find an active, non-cancelled getter
                while s.get_waiters:
                    prio, seq, gproc, genv, greq = heapq.heappop(s.get_waiters)
                    if not getattr(greq, "_active", False):
                        logger.debug("skipping getter (inactive) seq=%s", seq)
                        continue
                    if getattr(gproc, "_cancelled", False):
                        # mark requester inactive and skip
                        greq._active = False
                        logger.debug("skipping getter (cancelled) proc=%s seq=%s", gproc, seq)
                        continue
                    # grant the item to the getter
                    genv._schedule(0.0, gproc, s.items.popleft())
                    break
            # immediate resume of the putter (no token needed)
            env._schedule(0.0, proc, None)
            return

        # otherwise enqueue putter
        self._active = True
        seq = next(s._seq)
        heapq.heappush(s.put_waiters, (self.priority, seq, proc, env, self))
        if self.timeout is not None:
            cb = _TimeoutCallback(s, proc, self, env, is_put=True)
            env._schedule(float(self.timeout), cb)


class GetRequest:
    def __init__(self, store):
        self.store = store
        self.priority = 0
        self._active = False
        self.timeout = None

    def on_yield(self, env, proc):
        s = self.store
        if s.items:
            item = s.items.popleft()
            # if there are putters waiting, allow the oldest putter to insert
            if s.put_waiters and (s.capacity is None or len(s.items) < s.capacity):
                # pop until we find an active, non-cancelled putter
                while s.put_waiters and (s.capacity is None or len(s.items) < s.capacity):
                    prio, seq, pproc, penv, preq = heapq.heappop(s.put_waiters)
                    if not getattr(preq, "_active", False):
                        logger.debug("skipping putter (inactive) seq=%s", seq)
                        continue
                    if getattr(pproc, "_cancelled", False):
                        preq._active = False
                        logger.debug("skipping putter (cancelled) proc=%s seq=%s", pproc, seq)
                        continue
                    # insert the putter's item
                    s.items.append(preq.item)
                    preq._active = False
                    penv._schedule(0.0, pproc, None)
                    break
            env._schedule(0.0, proc, item)
            return

        # otherwise enqueue getter
        self._active = True
        seq = next(s._seq)
        heapq.heappush(s.get_waiters, (self.priority, seq, proc, env, self))
        if self.timeout is not None:
            cb = _TimeoutCallback(s, proc, self, env, is_put=False)
            env._schedule(float(self.timeout), cb)


class Store:
    def __init__(self, capacity=None):
        self.capacity = None if capacity is None else int(capacity)
        self.items = deque()
        self.get_waiters = []
        self.put_waiters = []
        self._seq = __import__("itertools").count()

    def put(self, item):
        return PutRequest(self, item)

    def put_with(self, item, timeout=None, priority=0):
        r = PutRequest(self, item)
        r.timeout = timeout
        r.priority = int(priority)
        return r

    def get(self):
        return GetRequest(self)

    def get_with(self, timeout=None, priority=0):
        r = GetRequest(self)
        r.timeout = timeout
        r.priority = int(priority)
        return r

    def _expire_putter(self, proc, req, env):
        if not getattr(req, "_active", False):
            return
        req._active = False
        env._schedule(0.0, proc, StoreRequestTimeout())

    def _expire_getter(self, proc, req, env):
        if not getattr(req, "_active", False):
            return
        req._active = False
        env._schedule(0.0, proc, StoreRequestTimeout())

    # convenience factories with timeout/priority could be added later
