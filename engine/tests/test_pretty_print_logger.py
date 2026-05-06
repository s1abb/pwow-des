import logging
import io
from engine.environment import Environment
from engine.resource import Resource


def test_pretty_print_to_logger_captures(caplog):
    env = Environment()
    res = Resource(capacity=1)

    def p():
        req = res.request_with()
        req.name = 'carol'
        with (yield req) as tok:
            # log while holding the token
            logger = logging.getLogger('engine.test')
            res.pretty_print_to_logger(logger, level=logging.INFO, current_time=env.now, context='test_logger')
            yield env.timeout(0)
        return

    logger = logging.getLogger('engine.test')
    logger.setLevel(logging.INFO)

    # ask caplog to capture logs at INFO for this logger before running the env
    caplog.set_level(logging.INFO, logger='engine.test')

    # run; the process will call pretty_print_to_logger while holding the token
    env.process(p)
    env.run()

    # Ensure the captured log contains the context and the token name
    records = [r.getMessage() for r in caplog.records]
    joined = "\n".join(records)
    assert 'test_logger' in joined
    assert 'carol' in joined
