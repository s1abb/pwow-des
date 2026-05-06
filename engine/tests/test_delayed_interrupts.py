from engine.environment import Environment
from engine.timeout import Timeout
from engine.interrupt import Interrupt


def test_delayed_interrupt_positional():
    env = Environment()
    log = []

    def target():
        try:
            yield Timeout(10)
            log.append("after-10")
        except Interrupt:
            log.append(("interrupted", env.now))

    p = env.process(target)
    # positional numeric as second arg -> delay
    env.interrupt(p, 2.0)
    env.run()
    assert log == [("interrupted", 2.0)]


def test_delayed_interrupt_keyword():
    env = Environment()
    log = []

    def target():
        try:
            yield Timeout(10)
            log.append("after-10")
        except Interrupt:
            log.append(("interrupted", env.now))

    p = env.process(target)
    env.interrupt(p, Interrupt(), delay=3.0)
    env.run()
    assert log == [("interrupted", 3.0)]
