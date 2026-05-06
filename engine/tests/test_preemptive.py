from engine.environment import Environment
from engine.timeout import Timeout
from engine.resource import PreemptiveResource, Preempted


def test_preempt_simple():
    env = Environment()
    res = PreemptiveResource(capacity=1)
    log = []

    def low():
        try:
            token = yield res.request_with(priority=5, preemptible=True)
            log.append(("low-acquired", env.now))
            yield Timeout(10)
            log.append(("low-after", env.now))
        except Preempted:
            log.append(("low-preempted", env.now))

    def high():
        token = yield res.request_with(priority=0)
        log.append(("high-acquired", env.now))

    env.process(low)
    env.process(high)
    env.run()

    # low acquires first, then is preempted and high acquires
    assert log == [("low-acquired", 0.0), ("low-preempted", 0.0), ("high-acquired", 0.0)]


def test_preempt_respects_priority():
    env = Environment()
    res = PreemptiveResource(capacity=1)
    log = []

    def high_holder():
        token = yield res.request_with(priority=0, preemptible=True)
        log.append(("high-acquired", env.now))
        yield Timeout(2)
        res.release(token=token)
        log.append(("high-released", env.now))

    def low_waiter():
        token = yield res.request_with(priority=5)
        log.append(("low-acquired", env.now))

    env.process(high_holder)
    env.process(low_waiter)
    env.run()

    # low should only acquire after high releases at t=2
    assert ("high-acquired", 0.0) in log
    assert ("low-acquired", 2.0) in log
