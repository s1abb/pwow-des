"""AnyOf / Timeout demo.

Shows waiting on multiple events with a timeout using AnyOf.

Run: python engine/examples/anyof_timeout_demo.py
"""

from engine.environment import Environment
from engine.event import AnyOf, Event


def task_timeout(env):
    print(f"[{env.now}] task_timeout starting; waiting for event or timeout")
    e = Event(env)
    winner = yield from AnyOf([e, env.timeout(1)]).wait()
    if e in winner:
        print(f"[{env.now}] task_timeout: event fired: {winner[e]}")
    else:
        print(f"[{env.now}] task_timeout: timed out at {list(winner.values())[0]}")


def task_event(env):
    print(f"[{env.now}] task_event starting; will fire event before timeout")
    e = Event(env)

    def fire():
        yield env.timeout(0.5)
        e.trigger('payload')

    env.process(fire)
    winner = yield from AnyOf([e, env.timeout(1)]).wait()
    if e in winner:
        print(f"[{env.now}] task_event: event fired: {winner[e]}")
    else:
        print(f"[{env.now}] task_event: timed out at {list(winner.values())[0]}")


def main():
    env = Environment()
    env.process(lambda: task_timeout(env))
    env.run()

    env = Environment()
    env.process(lambda: task_event(env))
    env.run()


if __name__ == "__main__":
    main()
