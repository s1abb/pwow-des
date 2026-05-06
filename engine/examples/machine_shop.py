"""Machine shop example adapted from the SimPy tutorial.

Demonstrates PreemptiveResource, interrupts and repair workflows.

Run: python engine/examples/machine_shop.py
"""
import random

from engine.environment import Environment
from engine.resource import PreemptiveResource, Preempted, Token
from engine.interrupt import Interrupt

# fmt: off
RANDOM_SEED = 42
PT_MEAN = 10.0         # Avg. processing time in minutes
PT_SIGMA = 2.0         # Sigma of processing time
MTTF = 300.0           # Mean time to failure in minutes
BREAK_MEAN = 1 / MTTF  # Param. for expovariate distribution
REPAIR_TIME = 30.0     # Time it takes to repair a machine in minutes
JOB_DURATION = 30.0    # Duration of other jobs in minutes
NUM_MACHINES = 10      # Number of machines in the machine shop
WEEKS = 4              # Simulation time in weeks
SIM_TIME = WEEKS * 7 * 24 * 60  # Simulation time in minutes
# fmt: on


def time_per_part():
    t = random.normalvariate(PT_MEAN, PT_SIGMA)
    while t <= 0:
        t = random.normalvariate(PT_MEAN, PT_SIGMA)
    return t


def time_to_failure():
    return random.expovariate(BREAK_MEAN)


class Machine:
    def __init__(self, env, name, repairman):
        self.env = env
        self.name = name
        self.parts_made = 0
        self.broken = False
        self.process = env.process(lambda: self.working(repairman))
        env.process(lambda: self.break_machine())

    def working(self, repairman):
        while True:
            done_in = time_per_part()
            while done_in:
                start = self.env.now
                try:
                    yield self.env.timeout(done_in)
                    done_in = 0
                except Interrupt:
                    # machine got interrupted (broken)
                    self.broken = True
                    done_in -= self.env.now - start
                    print(f"[{self.env.now}] {self.name} broken; remaining work {done_in}")

                    # request repairman (higher priority)
                    req = repairman.request_with(priority=1)
                    req.name = f"repair-{self.name}"
                    print(f"[{self.env.now}] {self.name} requesting repair")
                    # SimPy-style: the Request is an Event; using the context
                    # manager with `with (yield req) as tok:` will receive the
                    # Token allocated to this process. When Request is failed
                    # with an exception, that exception is thrown into the
                    # generator.
                    try:
                        with (yield req) as tok:
                            print(f"[{self.env.now}] {self.name} repair started")
                            yield self.env.timeout(REPAIR_TIME)
                            print(f"[{self.env.now}] {self.name} repair finished")
                    finally:
                        # if tok exists, release it
                        try:
                            tok.resource.release(token=tok)
                        except Exception:
                            pass

                    self.broken = False

            self.parts_made += 1

    def break_machine(self):
        while True:
            yield self.env.timeout(time_to_failure())
            if not self.broken:
                # interrupt the working process to simulate failure
                print(f"[{self.env.now}] {self.name} failing; interrupting process")
                self.process.interrupt()


def other_jobs(env, repairman):
    while True:
        done_in = JOB_DURATION
        while done_in:
            req = repairman.request_with(priority=2)
            req.name = "other-job"
            try:
                # use SimPy-style request handling
                with (yield req) as tok:
                    try:
                        start = env.now
                        try:
                            yield env.timeout(done_in)
                            done_in = 0
                        except Preempted:
                            done_in -= env.now - start
                    finally:
                        try:
                            tok.resource.release(token=tok)
                        except Exception:
                            pass
            except Exception:
                # If request times out or something else, continue
                break


def run():
    print('Machine shop (engine)')
    random.seed(RANDOM_SEED)

    env = Environment()
    repairman = PreemptiveResource(capacity=1)
    machines = [Machine(env, f'Machine {i}', repairman) for i in range(NUM_MACHINES)]
    env.process(lambda: other_jobs(env, repairman))

    env.run(until=SIM_TIME)

    print(f'Machine shop results after {WEEKS} weeks')
    for m in machines:
        print(f'{m.name} made {m.parts_made} parts.')


if __name__ == '__main__':
    run()
