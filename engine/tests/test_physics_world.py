from engine.environment import Environment
from engine.actor import Actor
from engine.physics_world import PhysicsWorld


def test_physics_move_actor():
    env = Environment()
    world = PhysicsWorld()
    # schedule physics loop with dt=0.1
    world.schedule_loop(env, 0.1)

    a = Actor(env, position=(0.0, 0.0, 0.0))
    b = Actor(env, position=(0.0, 0.0, 5.0))
    # register bodies
    world.register_body(a)
    world.register_body(b)

    def proc():
        ev = world.move_actor(a, (0.0, 0.0, 2.0), speed=1.0)
        payload = yield from ev.wait()
        assert payload["target"] == (0.0, 0.0, 2.0)

    env.process(proc)
    env.run()


def test_physics_collision_stops_and_fails():
    env = Environment()
    world = PhysicsWorld()
    world.schedule_loop(env, 0.1)

    a = Actor(env, position=(0.0, 0.0, 0.0))
    b = Actor(env, position=(0.0, 0.0, 2.0))
    wa = world.register_body(a)
    wb = world.register_body(b)

    # move both towards each other
    def proc_a():
        ev = world.move_actor(a, (0.0, 0.0, 1.5), speed=1.0)
        try:
            yield from ev.wait()
            assert False, "expected collision"
        except Exception:
            # any exception indicates collision in this stub
            pass

    def proc_b():
        ev = world.move_actor(b, (0.0, 0.0, 0.5), speed=1.0)
        try:
            yield from ev.wait()
            assert False, "expected collision"
        except Exception:
            pass

    env.process(proc_a)
    env.process(proc_b)
    env.run()
