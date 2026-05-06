from .environment import Environment
from .timeout import Timeout


def run_example():
    env = Environment()

    def p():
        print(f"[{env.now}] start")
        yield Timeout(3)
        print(f"[{env.now}] resumed after 3")

    env.process(p)
    env.run()

if __name__ == "__main__":
    run_example()
