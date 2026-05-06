"""Simple demo showing how to use the event-driven Actor API.

Run this script from the repository root with PYTHONPATH set so the
`engine` package is importable. Example (PowerShell):

$env:PYTHONPATH = "${PWD}\engine\src"; C:/path/to/python.exe engine/examples/physics_move_to_demo.py

This demo schedules a move and prints the arrival payload.
"""
from engine.environment import Environment
from engine.actor import Actor


def mover(env, actor: Actor):
    print(f"t={env.now:.3f} - starting move")
    ev = actor.move_to(0.0, 0.0, 2.0, speed=2.0)
    try:
        payload = yield from ev.wait()
    except Exception as exc:
        print(f"t={env.now:.3f} - movement failed: {exc}")
        return
    print(f"t={env.now:.3f} - arrived: {payload}")


def main():
    env = Environment()
    a = Actor(env, position=(0.0, 0.0, 0.0), default_speed=1.0)
    env.process(lambda: mover(env, a))
    env.run()


if __name__ == "__main__":
    main()
