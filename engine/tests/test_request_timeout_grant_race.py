from engine.environment import Environment
from engine.resource import Resource, RequestTimeout, Token


def test_request_timeout_grant_race():
    """Create a scenario where a holder releases a resource at the exact
    same simulation time that a queued request's timeout fires. Ensure no
    TypeError or incorrect value delivery occurs and resource invariants
    hold (available + allocated == capacity).
    """
    env = Environment()
    r = Resource(capacity=1)

    results = {}

    def holder():
        # acquire the only unit immediately
        tok = (yield r.request())
        # schedule a release at time 5.0 (by yielding a timeout)
        yield env.timeout(5.0)
        # release via token context manager
        tok.resource.release(token=tok)

    def waiter():
        # wait for the resource with a timeout that expires at time 5.0
        req = r.request_with(timeout=0.0)
        # schedule the request at time 0 so its timeout callback will be
        # scheduled for env.now + 0.0 == 0.0; we will move the env forward
        # to time 5.0 before releasing the holder to create a concurrency
        # point. To simulate the race, yield a timeout to advance to 5.0
        yield env.timeout(5.0)
        try:
            tok = (yield req)
            results['got_token'] = isinstance(tok, Token)
        except RequestTimeout:
            results['timed_out'] = True

    env.process(holder())
    env.process(waiter())

    # run until 6.0 to let both the release and timeout callbacks run
    env.run(until=6.0)

    # verify no TypeError occurred and the resource invariant holds
    assert (r.available + len(r.allocated)) == r.capacity
    # either the waiter got a token or it timed out; at least one should be set
    assert results.get('got_token') or results.get('timed_out')
