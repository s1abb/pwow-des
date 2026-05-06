from engine.environment import Environment
from engine.resource import PreemptiveResource, Preempted

# This demo uses `req.name` to attach friendly names to Tokens.


def worker(name, hold, preemptible=True):
    print(f"[{env.now}] {name} starting and requesting {hold} unit(s)")
    req = res.request_with(priority=5, preemptible=preemptible)
    # attach a friendly name to the request so the Token carries it
    req.name = name
    dump_state("before request")
    with (yield req) as tok:
        print(f"[{env.now}] {name} acquired -> {tok}")
        dump_state("after acquire")
        try:
            yield env.timeout(hold)
        except Preempted:
            print(f"[{env.now}] {name} was preempted")
        else:
            print(f"[{env.now}] {name} done")
        dump_state("after done")


def high_priority_job():
    yield env.timeout(0.5)
    print(f"[{env.now}] high priority job requesting")
    req = res.request_with(priority=0)
    req.name = 'high'
    dump_state("high before request")
    with (yield req) as tok:
        print(f"[{env.now}] high priority job acquired -> {tok}")
        dump_state("high after acquire")
        yield env.timeout(1)
        print(f"[{env.now}] high priority job done")
        dump_state("high after done")


def dump_state(context=""):
    # concise summary: counts and compact allocations/waiters
    # delegate printing to the Resource helper; requests carry their own names
    res.pretty_print_to_stdout(current_time=env.now, proc_name_map=None, context=context)


if __name__ == "__main__":
    env = Environment()
    res = PreemptiveResource(capacity=1)
    p1 = env.process(lambda: worker('low1', 3))
    p2 = env.process(lambda: worker('low2', 3))
    p3 = env.process(high_priority_job)
    env.run()
    env.run()
