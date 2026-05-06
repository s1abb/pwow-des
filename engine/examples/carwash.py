"""Carwash example using the engine APIs.

Classic carwash simulation demonstrating resource requests and queueing.

Run: python engine/examples/carwash.py
"""
import itertools
import random

from engine.environment import Environment
from engine.resource import Resource

# fmt: off
RANDOM_SEED = 42
NUM_MACHINES = 2  # Number of machines in the carwash
WASHTIME = 5      # Minutes it takes to clean a car
T_INTER = 7       # Create a car every ~7 minutes
SIM_TIME = 20     # Simulation time in minutes
# fmt: on


class Carwash:
    def __init__(self, env, num_machines, washtime):
        self.env = env
        self.machine = Resource(capacity=num_machines)
        self.washtime = washtime

    def wash(self, car):
        # take some time to wash
        yield self.env.timeout(self.washtime)
        pct_dirt = random.randint(50, 99)
        print(f"Carwash removed {pct_dirt}% of {car}'s dirt.")


def car(env, name, cw):
    print(f'{name} arrives at the carwash at {env.now:.2f}.')
    # request a machine (yield the Request event and get a Token)
    req = cw.machine.request()
    with (yield req) as tok:
        print(f'{name} enters the carwash at {env.now:.2f}.')
        # perform the washing process and wait for it to finish
        yield env.process(cw.wash(name))
        print(f'{name} leaves the carwash at {env.now:.2f}.')


def setup(env, num_machines, washtime, t_inter):
    carwash = Carwash(env, num_machines, washtime)
    car_count = itertools.count()

    # Create 4 initial cars
    for _ in range(4):
        env.process(car(env, f'Car {next(car_count)}', carwash))

    # Create more cars while the simulation is running
    while True:
        yield env.timeout(random.randint(t_inter - 2, t_inter + 2))
        env.process(car(env, f'Car {next(car_count)}', carwash))


def main():
    print('Carwash')
    print('Check out http://youtu.be/fXXmeP9TvBg while simulating ... ;-)')
    random.seed(RANDOM_SEED)

    env = Environment()
    env.process(lambda: setup(env, NUM_MACHINES, WASHTIME, T_INTER))
    env.run(until=SIM_TIME)


if __name__ == '__main__':
    main()
