from engine.environment import Environment
from engine.actor import Actor
from engine.physics_world import PhysicsWorld


def test_register_and_delegate():
    env = Environment()
    a = Actor(env, position=(0.0, 0.0, 0.0), default_speed=1.0)
    world = PhysicsWorld()

    # register actor with world
    a.register_with_world(world)

    def proc():
        ev = a.move_to(0.0, 0.0, 2.0, speed=2.0)
        payload = yield from ev.wait()
        assert payload["target"] == (0.0, 0.0, 2.0)

    env.process(proc)
    env.run()


def test_unregister_and_fallback():
    env = Environment()
    a = Actor(env, position=(0.0,0.0,0.0), default_speed=1.0)
    world = PhysicsWorld()
    world.register_body(a)
    a._world = world

    # unregister and ensure fallback behavior works
    a.unregister_from_world()

    def proc():
        ev = a.move_to(0.0, 0.0, 1.0, speed=1.0)
        payload = yield from ev.wait()
        assert payload["target"] == (0.0, 0.0, 1.0)

    env.process(proc)
    env.run()
