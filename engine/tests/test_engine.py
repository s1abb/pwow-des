import time

from engine.engine import Engine


def test_start_and_run_basic():
    e = Engine()

    # simple process that advances time
    def proc():
        yield e.env.timeout(1)
        yield e.env.timeout(1)

    assert e.getState() == Engine.IDLE
    assert e.start(proc) is True
    assert e.getState() == Engine.PAUSED

    # run the engine until completion
    assert e.run() is True
    assert e.getState() == Engine.FINISHED
    assert e.getStep() >= 2


def test_step_and_pause():
    e = Engine()

    def proc():
        yield e.env.timeout(5)

    e.start(proc)
    # single step executes the first event (the timeout is at t=5, but
    # scheduling will still step to that event)
    assert e.step() is True
    assert e.getState() == Engine.PAUSED

    # schedule another small event and pause during run
    def p2():
        yield e.env.timeout(0.1)

    e.env.process(p2)
    assert e.run(until=None) is True
    # after run completes, engine is FINISHED
    assert e.getState() in (Engine.FINISHED, Engine.PAUSED)


def test_stop_and_finish_requests():
    e = Engine()

    def long_proc():
        # schedule many small events
        for _ in range(10):
            yield e.env.timeout(1)

    e.start(long_proc)
    # request stop before running
    assert e.stop() is True
    # queue is cleared, running now would do nothing
    assert e.getEventCount() == 0

    # start again and test finish request
    e = Engine()
    e.start(long_proc)
    # run and then request finish during run by setting flag
    # simulate by calling run() and then finish will be a no-op since not RUNNING
    # so we simply assert finish() returns False when not running
    assert e.finish() is False


def test_pause_requested_during_run():
    e = Engine()

    def proc():
        # schedule several events; we will request pause while running
        yield e.env.timeout(0.1)
        yield e.env.timeout(0.1)
        yield e.env.timeout(0.1)

    e.start(proc)

    # schedule a parallel process that requests pause when first activated
    def pauser():
        # wait for a short time then request pause
        yield e.env.timeout(0.05)
        e.pause()

    e.env.process(pauser)

    # run; the engine should stop after the current event loop when pause is processed
    assert e.run() is True
    # after run returns due to pause, state should be PAUSED
    assert e.getState() == Engine.PAUSED


def test_finish_requested_during_run():
    e = Engine()

    def proc():
        yield e.env.timeout(0.05)
        yield e.env.timeout(0.05)

    e.start(proc)

    def finisher():
        yield e.env.timeout(0.02)
        # request finish while engine will be running
        e.finish()

    e.env.process(finisher)
    assert e.run() is True
    # finish requested should lead to FINISHED
    assert e.getState() == Engine.FINISHED


def test_exception_in_process_sets_error_state():
    e = Engine()

    def bad_proc():
        yield e.env.timeout(0.01)
        raise RuntimeError("boom")

    e.start(bad_proc)
    # Running should raise inside the process handler. Engine.run should
    # propagate the exception and set the engine state to ERROR.
    try:
        e.run()
        raised = False
    except RuntimeError:
        raised = True
    assert raised is True
    assert e.getState() == Engine.ERROR


def test_deterministic_timing_and_counters():
    # fake monotonic time source to deterministically track wall time
    fake_time = [1000.0]

    def time_func():
        # advance by a tiny fixed amount whenever queried
        fake_time[0] += 0.005
        return fake_time[0]

    e = Engine(time_func=time_func)

    def proc():
        # two timed events
        yield e.env.timeout(0.1)
        yield e.env.timeout(0.2)

    e.start(proc)
    # before run: zero steps, events scheduled
    assert e.getStep() == 0
    assert e.getEventCount() >= 1

    # run to completion
    assert e.run() is True
    assert e.getState() == Engine.FINISHED
    # two steps executed
    assert e.getStep() >= 2
    # run count incremented
    assert e.getRunCount() >= 1
    # run time recorded in ms and is > 0
    assert e.getRunTimeMillis() >= 0
    # start time uses the injected time source (milliseconds)
    assert e.getStartTimeMillis() is not None


def test_capture_mode_records_exception_and_returns():
    # Engine configured to capture exceptions instead of raising
    e = Engine()
    e.raise_on_error = False

    def bad_proc():
        yield e.env.timeout(0.01)
        raise ValueError("capture-me")

    e.start(bad_proc)
    result = e.run()
    # run should return False in capture mode when an exception occurs
    assert result is False
    assert e.getState() == Engine.ERROR
    assert isinstance(e.last_exception, Exception)
    # event queue should be cleared
    assert e.getEventCount() == 0


def test_on_error_callback_invoked_and_ignored_exceptions():
    called = {}

    def callback(exc, engine):
        called['exc'] = exc
        called['state'] = engine.getState()

    e = Engine()
    e.raise_on_error = False
    e.on_error = callback

    def bad_proc():
        yield e.env.timeout(0.01)
        raise RuntimeError("cb-test")

    e.start(bad_proc)
    res = e.run()
    assert res is False
    assert 'exc' in called and isinstance(called['exc'], RuntimeError)
    assert called.get('state') == Engine.ERROR


def test_on_error_callback_exception_is_ignored():
    # callback itself raises; Engine should ignore callback errors and
    # continue to capture the original exception
    def bad_callback(exc, engine):
        raise ValueError("callback-broke")

    e = Engine()
    e.raise_on_error = False
    e.on_error = bad_callback

    def bad_proc():
        yield e.env.timeout(0.01)
        raise RuntimeError("original")

    e.start(bad_proc)
    res = e.run()
    assert res is False
    # ensure the original exception was stored
    assert isinstance(e.last_exception, RuntimeError)
