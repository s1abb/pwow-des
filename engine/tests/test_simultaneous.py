from engine.environment import Environment
from engine.timeout import Timeout


def test_same_time_fifo():
    env = Environment()
    log = []

    def a():
        log.append(("a-start", env.now))
        yield Timeout(1)
        log.append(("a-resume", env.now))

    def b():
        log.append(("b-start", env.now))
        yield Timeout(1)
        log.append(("b-resume", env.now))

    env.process(a)
    env.process(b)
    env.run()

    assert log == [("a-start", 0.0), ("b-start", 0.0), ("a-resume", 1.0), ("b-resume", 1.0)]
