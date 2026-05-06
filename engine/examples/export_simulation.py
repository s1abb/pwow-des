"""Export a small simulation timeline to JSON using Engine.snapshot().

This example shows how to run the engine headless and sample actor states
at a fixed rate, writing a timeline JSON file suitable for importing into
Blender or other tools.

Usage:
    python engine/examples/export_simulation.py output.json
"""
import json
import sys
from pathlib import Path

from engine.engine import Engine


def make_dummy_actors(env):
    """Create a couple of dummy actor-like objects attached to env for demo.

    In a real simulation these would be full Actor objects; here we
    register lightweight moving items for exporter demonstration.
    """
    actors = []

    class Dummy:
        def __init__(self, id, start_pos, vel):
            self.id = id
            self.pos = list(start_pos)
            self.vel = list(vel)

        def step(self, dt):
            # simple Euler update
            self.pos[0] += self.vel[0] * dt
            self.pos[1] += self.vel[1] * dt
            self.pos[2] += self.vel[2] * dt

    # two moving dummies
    actors.append(Dummy('a', (0.0, 0.0, 0.0), (1.0, 0.2, 0.0)))
    actors.append(Dummy('b', (5.0, -1.0, 0.0), (-0.5, 0.1, 0.0)))

    return actors


def run_and_export(output_path: Path, sample_dt: float = 1.0 / 10.0, sim_until: float = 5.0):
    engine = Engine()
    env = engine.env

    actors = make_dummy_actors(env)

    # register a snapshot callback that reads actor positions
    def snapshot_cb():
        return [
            {"id": a.id, "pos": list(a.pos)}
            for a in actors
        ]

    engine.set_snapshot_callback(snapshot_cb)

    # simple process to advance dummies in simulation time
    def updater():
        last = env.now
        while True:
            # advance by a small step to update positions
            yield env.timeout(0.01)
            now = env.now
            dt = now - last
            last = now
            for a in actors:
                a.step(dt)

    env.process(updater)

    timeline = {
        "metadata": {
            "engine_version": "local",
            "sample_dt": sample_dt,
            "start_time": 0.0,
            "sim_until": sim_until,
        },
        "frames": [],
    }

    t = 0.0
    while t <= sim_until:
        engine.step_to_time(t)
        snap = engine.snapshot()
        timeline["frames"].append({"t": float(t), "actor_states": snap})
        t += sample_dt

    # validate timeline before writing
    try:
        # prefer normal import when run as package
        from engine.examples.timeline_validator import validate_timeline
    except Exception:
        # fallback: load the validator by path when executed as a script
        import runpy
        here = Path(__file__).resolve().parent
        nv = runpy.run_path(str(here / "timeline_validator.py"))
        validate_timeline = nv.get("validate_timeline")

    # call validator (may raise on failure)
    if validate_timeline is None:
        raise RuntimeError("timeline validator not available")
    validate_timeline(timeline)

    output_path.write_text(json.dumps(timeline, indent=2), encoding="utf8")


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("timeline.json")
    run_and_export(out)
    print(f"Exported timeline to {out}")
