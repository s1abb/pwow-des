from engine.environment import Environment
from engine.resource import PreemptiveResource


def victim(name):
    print(f"[{env.now}] {name} starting and acquiring")
    req = res.request_with(priority=5, preemptible=True)
    req.name = name
    try:
        with (yield req) as tok:
            print(f"[{env.now}] {name} acquired")
            # simulate long work; may be preempted
            yield env.timeout(3)
            print(f"[{env.now}] {name} completed work")
    except Exception as e:
        print(f"[{env.now}] {name} was preempted: {type(e).__name__}")
        # re-request after preemption with higher priority backoff
        yield env.timeout(1)
        print(f"[{env.now}] {name} re-requesting")
        req2 = res.request_with(priority=5, preemptible=True)
        with (yield req2) as tok2:
            print(f"[{env.now}] {name} reacquired")
            yield env.timeout(1)
            print(f"[{env.now}] {name} done after reacquire")


def aggressor():
    yield env.timeout(0.5)
    print(f"[{env.now}] aggressor requesting high priority")
    req = res.request_with(priority=0)
    with (yield req) as tok:
        print(f"[{env.now}] aggressor acquired")
        yield env.timeout(1)
        print(f"[{env.now}] aggressor done")


if __name__ == "__main__":
    env = Environment()
    res = PreemptiveResource(capacity=1)
    p = env.process(lambda: victim('victim1'))
    pa = env.process(lambda: aggressor())
    env.run()
