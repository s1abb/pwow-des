from engine.environment import Environment
from engine.resource import Resource
from engine.timeout import Timeout


def test_resource_request_release_fifo():
    env = Environment()
    res = Resource(capacity=1)
    log = []

    def p1():
        log.append(("p1-start", env.now))
        token = yield res.request()
        log.append(("p1-acquired", env.now))
        yield Timeout(1)
        # release using token
        res.release(token=token)
        log.append(("p1-released", env.now))

    def p2():
        log.append(("p2-start", env.now))
        token = yield res.request()
        log.append(("p2-acquired", env.now))

    env.process(p1)
    env.process(p2)
    env.run()

    # Expect p1 to acquire first, release at t=1, then p2 acquires immediately at t=1
    assert log == [
        ("p1-start", 0.0),
        ("p2-start", 0.0),
        ("p1-acquired", 0.0),
        ("p1-released", 1.0),
        ("p2-acquired", 1.0),
    ]


def test_resource_request_context_manager():
    env = Environment()
    res = Resource(capacity=1)
    log = []

    def p():
        log.append(("start", env.now))
        with (yield res.request()) as tok:
            log.append(("inside", env.now))
            yield Timeout(1)
        # after context exit the token should be released
        log.append(("after", env.now))

    env.process(p)
    env.run()

    assert log == [("start", 0.0), ("inside", 0.0), ("after", 1.0)]


def test_resource_capacity_multiple():
    env = Environment()
    res = Resource(capacity=2)
    log = []

    def p(name, hold):
        log.append((f"{name}-start", env.now))
        token = yield res.request()
        log.append((f"{name}-acquired", env.now))
        yield Timeout(hold)
        res.release(token=token)
        log.append((f"{name}-released", env.now))

    env.process(lambda: p("p1", 1))
    env.process(lambda: p("p2", 2))
    env.process(lambda: p("p3", 0))
    env.run()

    # p1 and p2 should acquire at t=0 (capacity 2), p3 should get it when p1 releases at t=1
    assert ("p1-acquired", 0.0) in log
    assert ("p2-acquired", 0.0) in log
    assert ("p3-acquired", 1.0) in log


def test_request_timeout():
    env = Environment()
    res = Resource(capacity=1)
    log = []

    def holder():
        # hold the resource for a long time
        token = yield res.request()
        yield Timeout(10)

    def waiter():
        try:
            yield res.request_with(timeout=1)
            log.append("acquired")
        except Exception:
            log.append("timed-out")

    env.process(holder)
    env.process(waiter)
    env.run()

    assert log == ["timed-out"]


def test_request_priority():
    env = Environment()
    res = Resource(capacity=1)
    order = []

    def holder():
        token = yield res.request()
        yield Timeout(1)
        res.release(token=token)

    def waiter(name, prio):
        token = yield res.request_with(priority=prio)
        order.append(name)
        # release immediately so next waiter can acquire
        res.release(token=token)

    env.process(holder)
    env.process(lambda: waiter("low", 5))
    env.process(lambda: waiter("high", 0))
    env.run()

    # high priority (0) should acquire before low priority (5)
    assert order == ["high", "low"]
