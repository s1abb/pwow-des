"""Gas station refuelling example.

Shows a gas station with pumps (Resource) and a shared fuel Container,
plus a tank truck process that refills the station when low.

Run: python engine/examples/gas_station.py
"""

import itertools
import random

from engine.environment import Environment
from engine.resource import Resource
from engine.container import Container

# fmt: off
RANDOM_SEED = 42
STATION_TANK_SIZE = 200    # Size of the gas station tank (liters)
THRESHOLD = 25             # Station tank minimum level (% of full)
CAR_TANK_SIZE = 50         # Size of car fuel tanks (liters)
CAR_TANK_LEVEL = [5, 25]   # Min/max levels of car fuel tanks (liters)
REFUELING_SPEED = 2        # Rate of refuelling car fuel tank (liters / second)
TANK_TRUCK_TIME = 300      # Time it takes tank truck to arrive (seconds)
T_INTER = [30, 300]        # Interval between car arrivals [min, max] (seconds)
SIM_TIME = 1000            # Simulation time (seconds)
# fmt: on


def car(name, env, gas_station, station_tank):
    """A car arrives at the gas station for refueling.

    It requests one of the gas station's fuel pumps and tries to get the
    desired amount of fuel from it. If the station's fuel tank is
    depleted, the car has to wait for the tank truck to arrive.

    """
    car_tank_level = random.randint(*CAR_TANK_LEVEL)
    print(f'{env.now:6.1f} s: {name} arrived at gas station')
    with (yield gas_station.request()) as req_token:
        # Got a pump
        # Get the required amount of fuel
        fuel_required = CAR_TANK_SIZE - car_tank_level
        # Wait until the station tank has enough
        yield station_tank.get(fuel_required)

        # The "actual" refueling process takes some time
        yield env.timeout(fuel_required / REFUELING_SPEED)

        print(f'{env.now:6.1f} s: {name} refueled with {fuel_required:.1f}L')


def gas_station_control(env, station_tank):
    """Periodically check the level of the gas station tank and call the tank
    truck if the level falls below a threshold."""
    while True:
        if station_tank.level / station_tank.capacity * 100 < THRESHOLD:
            # Avoid calling another truck if one is already en route
            if station_tank.get_meta('truck_pending'):
                # already waiting for a truck; skip
                pass
            else:
                # mark truck as pending and call
                station_tank.set_meta('truck_pending', True)
                print(f'{env.now:6.1f} s: Calling tank truck')
                # Wait for the tank truck to arrive and refuel the station tank
                yield env.process(tank_truck(env, station_tank))

        yield env.timeout(10)  # Check every 10 seconds


def tank_truck(env, station_tank):
    """Arrives at the gas station after a certain delay and refuels it."""
    yield env.timeout(TANK_TRUCK_TIME)
    amount = station_tank.capacity - station_tank.level
    # use the Container.put request so the container updates its level
    yield station_tank.put(amount)
    # clear pending flag so control may call again later
    station_tank.set_meta('truck_pending', False)
    print(
        f'{env.now:6.1f} s: Tank truck arrived and refuelled station with {amount:.1f}L'
    )


def car_generator(env, gas_station, station_tank):
    """Generate new cars that arrive at the gas station."""
    for i in itertools.count():
        yield env.timeout(random.randint(*T_INTER))
        env.process(car(f'Car {i}', env, gas_station, station_tank))


def main():
    print('Gas Station refuelling')
    random.seed(RANDOM_SEED)

    env = Environment()
    # Resource in this engine takes only capacity
    gas_station = Resource(capacity=2)
    # Container takes capacity; set initial level manually
    station_tank = Container(STATION_TANK_SIZE)
    station_tank.level = float(STATION_TANK_SIZE)

    env.process(gas_station_control(env, station_tank))
    env.process(car_generator(env, gas_station, station_tank))

    env.run(until=SIM_TIME)


if __name__ == '__main__':
    main()
