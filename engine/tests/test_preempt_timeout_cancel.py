from engine.environment import Environment
from engine.timeout import Timeout
from engine.resource import PreemptiveResource, Preempted, RequestTimeout


def test_preempt_timeout_cancel_interaction():
    env = Environment()
    res = PreemptiveResource(capacity=2)
    log = []

    def holder1():
        try:
            token = yield res.request_with(priority=5, preemptible=True)
            log.append(('h1_acquired', env.now))
            yield Timeout(5)
            log.append(('h1_after', env.now))
        except Preempted:
            log.append(('h1_preempted', env.now))

    def holder2():
        try:
            token = yield res.request_with(priority=5, preemptible=True)
            log.append(('h2_acquired', env.now))
            yield Timeout(5)
            log.append(('h2_after', env.now))
        except Preempted:
            log.append(('h2_preempted', env.now))

    def waiter_timeout():
        try:
            yield res.request_with(priority=10, timeout=0.5)
            log.append(('waiter_acquired', env.now))
        except RequestTimeout:
            log.append(('waiter_timedout', env.now))

    def waiter_preempt():
        # this high priority request should preempt one holder
        yield Timeout(0.1)
        yield res.request_with(priority=0)
        log.append(('waiter_preempt_acquired', env.now))

    env.process(holder1)
    env.process(holder2)
    env.process(waiter_timeout)
    env.process(waiter_preempt)
    env.run()

    # Expect one of the holders to be preempted at t==0.1 and waiter_timeout to time out
    assert ('waiter_timedout', 0.5) in log
    assert any(e[0] == 'h1_preempted' or e[0] == 'h2_preempted' for e in log)
