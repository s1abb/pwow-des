from engine.environment import Environment
from engine.resource import Resource




def task(env, name, req_delay, hold, priority=5):
    # request after a small delay
    yield env.timeout(req_delay)
    print(f"[{env.now}] {name} requesting resource (priority={priority})")
    req = res.request_with(priority=priority)
    # attach friendly name so Tokens carry it
    req.name = name
    with (yield req) as tok:
        print(f"[{env.now}] {name} acquired")
        yield env.timeout(hold)
        print(f"[{env.now}] {name} releasing")


def main():
    global res
    env = Environment()
    res = Resource(capacity=1)
    # start low slightly later so high should win if priority is higher
    p_low = env.process(lambda: task(env, 'low', 0.1, 2, priority=5))
    p_high = env.process(lambda: task(env, 'high', 0.0, 1, priority=0))
    # requests carry friendly names via req.name
    env.run()


if __name__ == "__main__":
    main()
