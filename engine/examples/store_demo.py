from engine.environment import Environment
from engine.store import Store


def producer(env, s):
    # small delay to simulate producer work
    yield env.timeout(0)
    print(f"[{env.now}] producer putting item")
    # put without timeout so the item is available for getters
    yield s.put('item')
    print(f"[{env.now}] producer done")


def getter(env, s, name, delay, priority=5):
    yield env.timeout(delay)
    try:
        # use `yield` for the Store get request so the process waits correctly
        item = yield s.get_with(priority=priority, timeout=2)
        print(f"[{env.now}] {name} got {item}")
    except Exception:
        print(f"[{env.now}] {name} timed out getting")


def main():
    env = Environment()
    s = Store(capacity=1)
    env.process(lambda: producer(env, s))
    # start low slightly later so high with priority=0 wins
    env.process(lambda: getter(env, s, 'low', 0.1, priority=5))
    env.process(lambda: getter(env, s, 'high', 0.0, priority=0))
    env.run()


if __name__ == "__main__":
    main()
