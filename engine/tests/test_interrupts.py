from engine.environment import Environment
from engine.timeout import Timeout
from engine.interrupt import Interrupt


def test_interrupt_timeout():
    env = Environment()
    log = []

    def target():
        try:
            yield Timeout(10)
            log.append("after-10")
        except Interrupt:
            log.append("interrupted")

    p = env.process(target)

    # schedule an interrupt at t=1 using the public API
    env.interrupt(p, Interrupt())

    env.run()

    assert log == ["interrupted"]


def test_cancel_skips_resume():
    env = Environment()
    log = []

    def p():
        log.append("start")
        yield Timeout(5)
        log.append("should-not-run")

    proc = env.process(p)
    # cancel before the scheduled resume
    proc.cancel()

    env.run()

    assert log == ["start"]
