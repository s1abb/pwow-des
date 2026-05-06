"""Minimal event-driven Actor primitive for Phase 1.

This module implements a lightweight Actor that can `move_to` a target
position by scheduling an arrival event with the Environment. It is
intended to be purely event-driven and dependency-free; a future
PhysicsWorld can integrate via the registration hooks.
"""
from __future__ import annotations

from typing import Optional, Tuple, Any

Vec3 = Tuple[float, float, float]

class MovementInterrupted(Exception):
    pass

class CollisionException(Exception):
    pass


def _distance(a: Vec3, b: Vec3) -> float:
    return ((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2) ** 0.5


class Actor:
    """Simple Actor supporting event-driven move_to/jump_to/stop.

    Usage: create an Actor with an `env` attribute set to an
    `engine.environment.Environment` instance. Methods like `move_to`
    are intended to be called from within processes (env.process).
    """

    def __init__(self, env, actor_id: Optional[str] = None, position: Vec3 = (0.0,0.0,0.0), default_speed: float = 1.0):
        self.env = env
        self.id = actor_id or f"actor-{id(self)}"
        self.position: Vec3 = position
        self._moving = False
        self._arrival_event = None
        self._arrival_time: Optional[float] = None
        self.default_speed = float(default_speed)
        # Optional PhysicsWorld integration hook (set by register_with_world)
        self._world = None

    def register_with_world(self, world) -> None:
        """Register this actor with a PhysicsWorld (or similar).

        The world should implement `register_body(actor)` and provide a
        `move_actor(actor, target, speed)` method. This method is a
        convenience wrapper that sets the `_world` attribute.
        """
        try:
            world.register_body(self)
        except Exception:
            # ignore registration errors for now; the world may be a stub
            pass
        self._world = world

    def unregister_from_world(self) -> None:
        """Unregister from a previously-registered world.

        Clears the internal `_world` reference and calls `unregister_body` if
        available.
        """
        w = getattr(self, "_world", None)
        if w is not None:
            try:
                w.unregister_body(self)
            except Exception:
                pass
        self._world = None

    def set_position(self, x: float, y: float, z: float) -> None:
        self.position = (float(x), float(y), float(z))

    def get_position(self) -> Vec3:
        return self.position

    def distance_to(self, x: float, y: float, z: float) -> float:
        return _distance(self.position, (x,y,z))

    def wait_for_proximity(self, other: "Actor", radius: float):
        """Yieldable: wait until this actor is within `radius` of `other`.

        If the actor is registered with a `PhysicsWorld` that supports
        proximity subscriptions, delegate to it. Otherwise poll using
        `env.timeout` with a small tick (default dt) until condition met.
        Returns the Event whose `wait()` yields a payload dict with keys
        `a`, `b`, `time`, `distance`.
        """
        # if registered with a physics world that has subscribe_proximity,
        # delegate for efficiency
        w = getattr(self, "_world", None)
        if w is not None and hasattr(w, "subscribe_proximity"):
            return w.subscribe_proximity(self, other, radius)

        # fallback polling: sample at small intervals (use 0.05s)
        from .event import Event as _Event

        ev = _Event(self.env)

        def _poll_loop():
            while True:
                d = _distance(self.position, other.position)
                if d <= float(radius):
                    ev.succeed({"a": self, "b": other, "time": float(self.env.now), "distance": d})
                    return
                # wait a small tick
                yield self.env.timeout(0.05)

        # start polling process and keep a handle so we can cancel it
        proc = self.env.process(_poll_loop)

        class PollingSubscription:
            def __init__(self, event, process):
                self._event = event
                self._proc = process

            def unsubscribe(self):
                try:
                    # cancel the polling process so it won't resume again
                    self._proc.cancel()
                except Exception:
                    pass

            def wait(self):
                return self._event.wait()

        return PollingSubscription(ev, proc)

    def is_moving(self) -> bool:
        return bool(self._moving)

    def time_to_arrival(self) -> Optional[float]:
        if not self._moving or self._arrival_time is None:
            return None
        return max(0.0, float(self._arrival_time) - float(self.env.now))

    def jump_to(self, x: float, y: float, z: float) -> None:
        # cancel any in-flight movement
        if self._arrival_event is not None:
            try:
                self._arrival_event.fail(MovementInterrupted("jump"))
            except Exception:
                pass
            self._arrival_event = None
            self._moving = False
            self._arrival_time = None
        self.set_position(x,y,z)

    def stop(self) -> None:
        if self._arrival_event is not None:
            try:
                self._arrival_event.fail(MovementInterrupted("stop"))
            except Exception:
                pass
        self._arrival_event = None
        self._moving = False
        self._arrival_time = None

    def move_to(self, x: float, y: float, z: float, *, speed: Optional[float] = None):
        """Schedule arrival to the target position and return an Event.

        The returned Event succeeds with a dict {"target":(x,y,z),
        "arrival_time": t, "distance_travelled": d} when the actor
        arrives. If movement is interrupted, the Event.fail is called with
        MovementInterrupted.
        """
        if speed is None:
            speed = self.default_speed
        speed = float(speed)
        if speed < 0.0:
            raise ValueError("speed must be non-negative")

        # If registered with a PhysicsWorld, delegate movement to it.
        if getattr(self, "_world", None) is not None:
            # world.move_actor should accept (actor, target_tuple, speed)
            return self._world.move_actor(self, (x, y, z), speed)

        # compute travel time
        dist = self.distance_to(x,y,z)
        if dist == 0.0:
            # immediate succeed
            from .event import Event as _Event
            ev = _Event(self.env)
            ev.succeed({"target": (x,y,z), "arrival_time": float(self.env.now), "distance_travelled": 0.0})
            return ev

        dt = 0.0 if speed == 0.0 else dist / speed

        from .event import Event as _Event

        # If a previous movement is in-flight, fail it (re-route)
        if self._arrival_event is not None:
            try:
                self._arrival_event.fail(MovementInterrupted("reroute"))
            except Exception:
                pass

        ev = _Event(self.env)
        self._arrival_event = ev
        self._moving = True
        arrival_time = float(self.env.now) + float(dt)
        self._arrival_time = arrival_time

        # schedule an internal callback at dt that will finalize the move
        def _on_arrival(_v):
            # If event was already failed, do nothing
            if getattr(ev, "_triggered", False) and getattr(ev, "_exc", None) is not None:
                # already failed
                self._arrival_event = None
                self._moving = False
                self._arrival_time = None
                return
            # update position and succeed event
            self.position = (float(x), float(y), float(z))
            payload = {"target": (x,y,z), "arrival_time": float(self.env.now), "distance_travelled": dist}
            ev.succeed(payload)
            self._arrival_event = None
            self._moving = False
            self._arrival_time = None

        # schedule the resume object used by Environment
        self.env._schedule(dt, type("_ARR", (), {"_resume": staticmethod(lambda v: _on_arrival(v))})())
        return ev
