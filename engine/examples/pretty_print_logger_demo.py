"""Pretty-print logger demo.

Demonstrates pretty-printing resource state to a standard logger and
capturing the output through a StringIO-backed handler.
"""

from engine.environment import Environment
from engine.resource import Resource
import logging


def demo():
    env = Environment()
    res = Resource(capacity=1)

    def worker(name, delay):
        yield env.timeout(delay)
        req = res.request()
        req.name = name
        with (yield req) as tok:
            # do some work
            yield env.timeout(0.5)

    env.process(lambda: worker('alice', 0))
    env.process(lambda: worker('bob', 0.1))

    # run until a little after both started
    env.run()

    # log a snapshot
    logger = logging.getLogger('engine.demo')
    logger.setLevel(logging.INFO)
    # attach a stream handler and a StringIO handler to demonstrate capture
    import io
    stream_handler = logging.StreamHandler()
    sio = io.StringIO()
    str_handler = logging.StreamHandler(sio)
    # Ensure basic config is set for the demo but avoid reconfiguring in
    # environments that already configured logging. Use a no-op if handlers
    # are present.
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO)
    logger.addHandler(stream_handler)
    logger.addHandler(str_handler)

    res.pretty_print_to_logger(logger, level=logging.INFO, current_time=env.now, context='pretty_logger_demo')

    # print captured logs from the StringIO buffer
    print('\n-- captured logger output --')
    print(sio.getvalue())


if __name__ == '__main__':
    demo()
