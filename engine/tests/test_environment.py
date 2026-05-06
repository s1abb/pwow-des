from engine.environment import Environment
from engine.timeout import Timeout


def test_simple_timeout_run():
    env = Environment()
    log = []

    def p1():
        log.append(("p1-start", env.now))
        yield Timeout(2)
        log.append(("p1-after-2", env.now))

    env.process(p1)
    env.run()

    assert log == [("p1-start", 0.0), ("p1-after-2", 2.0)]
