from engine.environment import Environment
from engine.timeout import Timeout


def test_zero_delay_chaining():
    env = Environment()
    log = []

    def p():
        log.append(("start", env.now))
        yield Timeout(0)
        log.append(("after-0-1", env.now))
        yield Timeout(0)
        log.append(("after-0-2", env.now))

    env.process(p)
    env.run()

    # env.now should remain 0.0 during zero-delay chain
    assert log == [("start", 0.0), ("after-0-1", 0.0), ("after-0-2", 0.0)]
