from engine.environment import Environment
from engine.actor import Actor, MovementInterrupted


def test_move_to_arrival_timing():
    env = Environment()
    a = Actor(env, position=(0.0, 0.0, 0.0), default_speed=2.0)

    def proc():
        ev = a.move_to(0.0, 0.0, 2.0)
        # wait for arrival and capture payload
        payload = yield from ev.wait()
        assert payload["target"] == (0.0, 0.0, 2.0)
        # distance is 2.0, speed 2.0 => travel time 1.0
        assert abs(payload["arrival_time"] - 1.0) < 1e-9

    env.process(proc)
    env.run()


def test_stop_interrupts_movement():
    env = Environment()
    a = Actor(env, position=(0.0, 0.0, 0.0), default_speed=1.0)

    def proc():
        ev = a.move_to(0.0, 0.0, 10.0)
        # stop the actor after 1 time unit
        yield env.timeout(1)
        a.stop()
        try:
            yield from ev.wait()
            assert False, "expected MovementInterrupted"
        except MovementInterrupted:
            # expected
            pass

    env.process(proc)
    env.run()


def test_jump_to_immediate():
    env = Environment()
    a = Actor(env, position=(1.0, 1.0, 1.0))

    def proc():
        a.jump_to(5.0, 5.0, 5.0)
        assert a.get_position() == (5.0, 5.0, 5.0)
        # jump should not schedule movement
        assert not a.is_moving()
        # make this function a generator for Process by yielding once
        yield env.timeout(0)

    env.process(proc)
    env.run()


def test_reroute_fails_previous_event():
    env = Environment()
    a = Actor(env, position=(0.0, 0.0, 0.0), default_speed=1.0)

    def proc():
        ev1 = a.move_to(0.0, 0.0, 10.0)
        # after 1 unit, request a new move
        yield env.timeout(1)
        ev2 = a.move_to(0.0, 0.0, 2.0)
        # ev1 should have failed
        try:
            yield from ev1.wait()
            assert False, "ev1 should have been failed"
        except MovementInterrupted:
            pass
        # ev2 should succeed
        payload = yield from ev2.wait()
        assert payload["target"] == (0.0, 0.0, 2.0)

    env.process(proc)
    env.run()
