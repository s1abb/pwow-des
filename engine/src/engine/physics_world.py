"""Minimal PhysicsWorld scaffold.

This stub provides registration APIs and a `move_actor` method that
currently falls back to the Actor's event-driven arrival behavior. It is
intended as a safe extension point for future deterministic time-stepped
physics implementations.
"""
from typing import Any, Tuple, List, Optional
from math import sqrt

from .event import Event


class Body:
    def __init__(self, actor, radius: float = 0.5, mass: float = 1.0):
        self.actor = actor
        self.radius = float(radius)
        self.mass = float(mass)
        # internal position mirrors actor.position (tuple)
        self.position = tuple(actor.position)
        # velocity vector (vx,vy,vz)
        self.velocity = (0.0, 0.0, 0.0)
        self.target: Optional[Tuple[float, float, float]] = None
        self.speed: Optional[float] = None
        self.moving = False
        self.arrival_event: Optional[Event] = None
    pass

class PhysicsWorld:
    def __init__(self):
        self._bodies: List[Body] = []
        self._env = None
        self._loop_proc = None
        self._dt = None
        # proximity subscriptions: list of (actor_a, actor_b, radius, Event)
        self._proximity_subs = []

    def register_body(self, actor, *, radius: float = 0.5, mass: float = 1.0) -> Any:
        b = Body(actor, radius=radius, mass=mass)
        self._bodies.append(b)
        return b

    def unregister_body(self, actor) -> None:
        # allow passing either actor or Body
        to_remove = None
        for b in list(self._bodies):
            if b.actor is actor or b is actor:
                to_remove = b
                break
        if to_remove is not None:
            try:
                self._bodies.remove(to_remove)
            except ValueError:
                pass

    def move_actor(self, actor, target: Tuple[float, float, float], speed: float):
        # Find body for actor
        b = None
        for body in self._bodies:
            if body.actor is actor:
                b = body
                break
        if b is None:
            # actor not registered: fall back to actor's move_to
            prev = getattr(actor, "_world", None)
            actor._world = None
            try:
                return actor.move_to(target[0], target[1], target[2], speed=speed)
            finally:
                actor._world = prev

        # If the world hasn't been scheduled into an env, fall back to the
        # actor's event-driven move_to implementation for backwards
        # compatibility with code that registers actors but doesn't run a
        # physics loop.
        if self._env is None:
            prev = getattr(actor, "_world", None)
            actor._world = None
            try:
                return actor.move_to(target[0], target[1], target[2], speed=speed)
            finally:
                actor._world = prev

        # prepare arrival Event
        ev = Event(self._env)
        # set body motion params
        b.target = (float(target[0]), float(target[1]), float(target[2]))
        b.speed = float(speed)
        # compute direction using squared-distance to avoid an extra sqrt
        dx = b.target[0] - b.position[0]
        dy = b.target[1] - b.position[1]
        dz = b.target[2] - b.position[2]
        dist2 = dx*dx + dy*dy + dz*dz
        if dist2 <= 1e-24:
            # effectively zero distance
            ev.succeed({"target": b.target, "arrival_time": float(self._env.now), "distance_travelled": 0.0})
            return ev
        # set velocity vector (one sqrt for normalization)
        dist = sqrt(dist2)
        vx = dx / dist * b.speed
        vy = dy / dist * b.speed
        vz = dz / dist * b.speed
        b.velocity = (vx, vy, vz)
        b.moving = True
        b.arrival_event = ev
        # ensure physics loop is running to process this motion
        try:
            # prefer stored dt when available
            if getattr(self, "_loop_proc", None) is None and getattr(self, "_env", None) is not None and getattr(self, "_dt", None) is not None:
                # start the loop process
                self._loop_proc = self._env.process(lambda: self._make_loop(self._env, self._dt)())
        except Exception:
            # swallow; scheduling is best-effort and will be set when schedule_loop is called
            pass
        return ev

    def step(self, dt: float, now: float) -> None:
        # deterministic iteration in registration order
        # snapshot previous positions for rollback on collision
        prev_positions = {b: tuple(b.position) for b in self._bodies}

        # advance moving bodies
        for b in self._bodies:
            if not b.moving:
                continue
            # tentative move
            px, py, pz = b.position
            vx, vy, vz = b.velocity
            nx = px + vx * dt
            ny = py + vy * dt
            nz = pz + vz * dt
            # check if we reached or passed the target
            if b.target is not None:
                tx, ty, tz = b.target
                # distance remaining before move
                rem_dx = tx - px
                rem_dy = ty - py
                rem_dz = tz - pz
                rem2 = rem_dx*rem_dx + rem_dy*rem_dy + rem_dz*rem_dz
                travel2 = (nx-px)**2 + (ny-py)**2 + (nz-pz)**2
                # compare squared distances with a tolerance
                if travel2 >= rem2 - 1e-12:
                    # arrive at target
                    b.position = (tx, ty, tz)
                    b.actor.position = b.position
                    b.moving = False
                    b.velocity = (0.0, 0.0, 0.0)
                    if b.arrival_event is not None:
                        # distance travelled equals sqrt(rem2)
                        payload = {"target": b.target, "arrival_time": float(now), "distance_travelled": sqrt(rem2)}
                        b.arrival_event.succeed(payload)
                        b.arrival_event = None
                    b.target = None
                    b.speed = None
                    continue
            # Otherwise update position
            b.position = (nx, ny, nz)
            b.actor.position = b.position

        # collision detection (simple sphere-sphere)
        n = len(self._bodies)
        for i in range(n):
            for j in range(i+1, n):
                bi = self._bodies[i]
                bj = self._bodies[j]
                dx = bi.position[0] - bj.position[0]
                dy = bi.position[1] - bj.position[1]
                dz = bi.position[2] - bj.position[2]
                d2 = dx*dx + dy*dy + dz*dz
                rsum = (bi.radius + bj.radius)
                if d2 < (rsum*rsum) - 1e-12:
                    # collision: rollback to prev positions and stop bodies
                    bi.position = prev_positions[bi]
                    bj.position = prev_positions[bj]
                    bi.actor.position = bi.position
                    bj.actor.position = bj.position
                    bi.moving = False
                    bj.moving = False
                    bi.velocity = (0.0, 0.0, 0.0)
                    bj.velocity = (0.0, 0.0, 0.0)
                    # fail arrival events if present
                    from .actor import CollisionException
                    if bi.arrival_event is not None:
                        try:
                            bi.arrival_event.fail(CollisionException("collision"))
                        except Exception:
                            pass
                        bi.arrival_event = None
                    if bj.arrival_event is not None:
                        try:
                            bj.arrival_event.fail(CollisionException("collision"))
                        except Exception:
                            pass
                        bj.arrival_event = None
        return None

        # proximity subscriptions: check and fire any matching events
        # (use a snapshot since handlers may modify the list)
        # NOTE: keep deterministic iteration order (registration order)
        for sub in list(self._proximity_subs):
            actor_a, actor_b, radius, ev = sub
            # read positions from actors (world updates actor.position when moving)
            pa = getattr(actor_a, "position", None)
            pb = getattr(actor_b, "position", None)
            if pa is None or pb is None:
                continue
            dx = pa[0] - pb[0]
            dy = pa[1] - pb[1]
            dz = pa[2] - pb[2]
            d2 = dx*dx + dy*dy + dz*dz
            if d2 <= (radius*radius) + 1e-12:
                try:
                    ev.succeed({"a": actor_a, "b": actor_b, "time": float(now), "distance": sqrt(d2)})
                except Exception:
                    pass
                try:
                    self._proximity_subs.remove(sub)
                except ValueError:
                    pass
        return None

    def subscribe_proximity(self, actor_a, actor_b, radius: float):
        """Register a proximity Event that succeeds when actors are within radius.

        Returns an Event scheduled on the world's env. The Event will
        succeed with a payload {'a': actor_a, 'b': actor_b, 'time': now,
        'distance': d} when the proximity condition is met.
        """
        if self._env is None:
            raise RuntimeError("PhysicsWorld must be scheduled (schedule_loop) before subscribing to proximity")

        ev = Event(self._env)
        # use a mutable subscription entry so unsubscribe can remove it by identity
        sub_entry = [actor_a, actor_b, float(radius), ev]
        self._proximity_subs.append(sub_entry)

        class ProximitySubscription:
            def __init__(self, world, entry, event):
                self._world = world
                self._entry = entry
                self.event = event

            def unsubscribe(self):
                try:
                    self._world._proximity_subs.remove(self._entry)
                except Exception:
                    pass

            def wait(self):
                return self.event.wait()

        return ProximitySubscription(self, sub_entry, ev)

    def schedule_loop(self, env, dt: float):
        """Convenience: schedule a deterministic fixed-dt loop in `env`.

        Returns the Process object created by `env.process`. The returned
        process will call `self.step(dt, env.now)` every `dt` seconds.
        """

        # store env and dt for later restarts
        self._env = env
        self._dt = float(dt)

        # inner loop factory so we can create a callable easily when
        # restarting from move_actor
        def _loop():
            # run while there are active moving bodies; exit when idle
            while True:
                # if no bodies are moving, end the loop so the env can
                # naturally terminate when other processes complete
                if not any(b.moving for b in self._bodies):
                    # clear stored proc to indicate loop is not running
                    self._loop_proc = None
                    return
                # call step with the current simulation time
                try:
                    self.step(dt, env.now)
                except Exception:
                    # swallow to avoid terminating the loop in the stub
                    pass
                # yield a timeout for the next tick
                yield env.timeout(dt)

        # start the loop process and remember it so we can restart later
        self._loop_proc = env.process(_loop)
        return self._loop_proc

    def _make_loop(self, env, dt: float):
        # helper factory returning the loop generator function for restart
        def _loop():
            if self._env is None:
                self._env = env
            while True:
                if not any(b.moving for b in self._bodies):
                    self._loop_proc = None
                    return
                try:
                    self.step(dt, env.now)
                except Exception:
                    pass
                yield env.timeout(dt)

        return _loop
