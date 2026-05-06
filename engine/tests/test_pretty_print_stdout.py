import io
import sys
from engine.environment import Environment
from engine.resource import Resource


def test_pretty_print_to_stdout_captures(monkeypatch):
    env = Environment()
    res = Resource(capacity=1)

    def p():
        req = res.request_with()
        req.name = 'bob'
        with (yield req) as tok:
            # capture stdout
            buf = io.StringIO()
            old = sys.stdout
            try:
                sys.stdout = buf
                res.pretty_print_to_stdout(current_time=env.now, proc_name_map=None, context='test')
            finally:
                sys.stdout = old
            out = buf.getvalue()
            assert 'STATE test' in out
            assert 'bob' in out
        return

    env.process(p)
    env.run()
