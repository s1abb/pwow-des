from engine.environment import Environment
from engine.resource import Resource, RequestTimeout, Token


def test_request_immediate_grant_returns_token():
    env = Environment()
    r = Resource(capacity=1)

    result = {}

    def proc():
        req = r.request()
        val = yield req
        result['val'] = val

    env.process(proc)
    env.run()

    assert 'val' in result
    assert isinstance(result['val'], Token)


def test_request_queued_then_granted_returns_token():
    env = Environment()
    r = Resource(capacity=1)

    # allocate the only unit first
    holder = r.request()
    # process to take holder
    def holder_proc():
        tok = (yield holder)
        # hold for one time unit then release
        try:
            yield env.timeout(1)
        finally:
            try:
                tok.resource.release(token=tok)
            except Exception:
                pass

    env.process(holder_proc())

    out = {}

    def waiter_proc():
        req = r.request()
        val = yield req
        out['val'] = val

    # start waiter
    env.process(waiter_proc())
    env.run()

    assert 'val' in out
    assert isinstance(out['val'], Token)


def test_request_timeout_raises():
    env = Environment()
    r = Resource(capacity=0)

    out = {}

    def p():
        req = r.request_with(timeout=0)
        try:
            yield req
        except Exception as e:
            out['exc'] = e

    env.process(p())
    env.run()

    assert 'exc' in out
    assert isinstance(out['exc'], RequestTimeout)
