from engine.environment import Environment
from engine.actor import Actor
from engine.physics_world import PhysicsWorld


def test_wait_for_proximity_polling():
    env = Environment()
    a = Actor(env, position=(0.0, 0.0, 0.0))
    b = Actor(env, position=(1.0, 0.0, 0.0))

    def proc():
        sub = a.wait_for_proximity(b, 0.5)
        try:
            payload = yield from sub.wait()
            # initial distance is 1.0 > 0.5, so this should not immediately succeed
            assert payload["distance"] <= 0.5
        except Exception:
            assert False, "proximity wait failed"

    def mover():
        # move b closer using event-driven move_to
        ev = b.move_to(0.25, 0.0, 0.0, speed=1.0)
        yield from ev.wait()

    env.process(proc)
    env.process(mover)
    env.run()


def test_wait_for_proximity_world():
    env = Environment()
    world = PhysicsWorld()
    world.schedule_loop(env, 0.05)

    a = Actor(env, position=(0.0, 0.0, 0.0))
    b = Actor(env, position=(2.0, 0.0, 0.0))
    a.register_with_world(world)
    b.register_with_world(world)

    def proc():
        sub = a.wait_for_proximity(b, 0.5)
        payload = yield from sub.wait()
        assert payload["distance"] <= 0.5

    def mover():
        ev = world.move_actor(b, (0.25, 0.0, 0.0), speed=2.0)
        try:
            yield from ev.wait()
        except Exception:
            # collisions in the world could fail; that's acceptable
            pass

    env.process(proc)
    env.process(mover)
    env.run()
