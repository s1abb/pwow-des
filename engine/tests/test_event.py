from engine.environment import Environment
from engine.event import Event, AllOf, AnyOf


def test_event_simple():
    env = Environment()

    def proc():
        e = Event(env)
        # schedule success at the next simulation step using env.timeout
        def trigger_later():
            yield env.timeout(0)
            e.trigger(123)

        yield from trigger_later()
        val = yield from e.wait()
        assert val == 123

    env.process(proc)
    env.run()


def test_allof():
    env = Environment()

    def proc():
        e1 = Event(env)
        e2 = Event(env)
        # combine e1 and a timeout to exercise composition with env.timeout
        all_ev = AllOf([e1, e2])

        # trigger e1 and schedule e2 after a small env.timeout
        e1.trigger("a")
        def trigger_e2():
            yield env.timeout(0)
            e2.trigger("b")

        yield from trigger_e2()

        result = yield from all_ev.wait()
        # expect dict mapping events to values
        assert isinstance(result, dict)
        assert result[e1] == "a"
        assert result[e2] == "b"

    env.process(proc)
    env.run()


def test_anyof():
    env = Environment()

    def proc():
        e1 = Event(env)
        e2 = Event(env)
        any_ev = AnyOf([e1, e2])

        # schedule e2 to win after a short timeout
        def trigger_e2():
            yield env.timeout(0)
            e2.trigger("win")

        yield from trigger_e2()

        result = yield from any_ev.wait()
        assert isinstance(result, dict)
        # should contain only the winning event value
        assert list(result.values()) == ["win"]

    env.process(proc)
    env.run()


def test_allof_failure_propagates():
    env = Environment()

    def proc():
        e1 = Event(env)
        e2 = Event(env)
        all_ev = AllOf([e1, e2])

        # e1 fails immediately
        e1.fail(RuntimeError("boom"))

        # e2 would succeed later
        def t2():
            yield env.timeout(0)
            e2.trigger("b")

        yield from t2()

        # waiting on all_ev should raise the propagated exception when awaited
        try:
            _ = yield from all_ev.wait()
            assert False, "AllOf should have failed"
        except RuntimeError:
            pass

    env.process(proc)
    env.run()


def test_anyof_all_fail():
    env = Environment()

    def proc():
        e1 = Event(env)
        e2 = Event(env)
        any_ev = AnyOf([e1, e2])

        # both fail (one now, one slightly later)
        e1.fail(ValueError("fail1"))

        def t2():
            yield env.timeout(0)
            e2.fail(ValueError("fail2"))

        yield from t2()

        try:
            _ = yield from any_ev.wait()
            assert False, "AnyOf should have failed when all members fail"
        except ValueError:
            pass

    env.process(proc)
    env.run()
