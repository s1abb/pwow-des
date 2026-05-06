from engine.environment import Environment


def producer(env):
    print(f"[{env.now}] producer start")
    t = yield from env.timeout(1).wait()
    print(f"[{env.now}] producer resumed at {t}")


def consumer(env):
    print(f"[{env.now}] consumer start")
    t = yield from env.timeout(2).wait()
    print(f"[{env.now}] consumer resumed at {t}")


def main():
    env = Environment()
    env.process(lambda: producer(env))
    env.process(lambda: consumer(env))
    env.run()


if __name__ == "__main__":
    main()
