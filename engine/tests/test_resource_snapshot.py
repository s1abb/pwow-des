from engine.environment import Environment
from engine.resource import Resource


def test_req_name_and_allocated_at_flows_to_token():
    env = Environment()
    res = Resource(capacity=1)

    def proc():
        req = res.request_with(priority=1)
        req.name = 'alice'
        with (yield req) as tok:
            # inside critical section immediately after acquiring
            assert getattr(tok, 'name', None) == 'alice'
            # allocated_at should be set and equal to env.now approximately
            assert getattr(tok, 'allocated_at', None) is not None
            # the allocated_at should be equal to the environment now when allocation happened
            assert abs(tok.allocated_at - env.now) < 1e-9
            # snapshot should include the token info
            snaps = res.snapshot(current_time=env.now)
            assert snaps[0]['token_name'] == 'alice'
            assert snaps[0]['allocated_at'] == tok.allocated_at
        return

    env.process(proc)
    env.run()
