"""Clock demo.

Shows two periodic processes (fast and slow clocks) using the engine
Environment and timeout primitives.

Run: python engine/examples/clock_demo.py
"""

from engine.environment import Environment


def clock(env, name, tick):
    while True:
        print(f"{name} {env.now}")
        yield env.timeout(tick)


def main():
    env = Environment()
    env.process(lambda: clock(env, 'fast', 0.5))
    env.process(lambda: clock(env, 'slow', 1))
    env.run(until=2)


if __name__ == '__main__':
    main()
