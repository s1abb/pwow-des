"""Pretty-print logger hold demo.

Demonstrates printing logger output while a token/resource is held,
capturing the output in a StringIO buffer.
"""

from engine.environment import Environment
from engine.resource import Resource
import logging
import io


def demo():
    env = Environment()
    res = Resource(capacity=1)

    def worker(name, delay):
        yield env.timeout(delay)
        req = res.request()
        req.name = name
        with (yield req) as tok:
            # set up a logger that writes into a StringIO so we can print it after
            logger = logging.getLogger('engine.hold_demo')
            logger.setLevel(logging.INFO)
            sio = io.StringIO()
            handler = logging.StreamHandler(sio)
            logger.addHandler(handler)

            # log snapshot while holding the token
            res.pretty_print_to_logger(logger, level=logging.INFO, current_time=env.now, context='hold_demo')

            # flush handler and print what's been captured
            handler.flush()
            print('\n-- captured logger output while holding token --')
            print(sio.getvalue())

            # keep holding for a short time
            yield env.timeout(0.2)

    # Ensure logging is configured only if not already set up by the host.
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO)

    env.process(lambda: worker('holder', 0))
    env.process(lambda: worker('waiter', 0.05))

    env.run()


if __name__ == '__main__':
    demo()
