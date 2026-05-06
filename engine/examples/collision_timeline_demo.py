"""Collision-driven mover demo + timeline export

Moves a slow actor between static actors. Each collision with a static
actor triggers the mover to proceed to the next target. The script
samples actor positions at a fixed rate and writes a timeline JSON file
suitable for import into Blender or other visualizers.

Usage:
    python engine/examples/collision_timeline_demo.py [out.json]

Note: this example uses the pure-Python `PhysicsWorld` prototype and the
engine snapshot API. It tries to validate the produced timeline using
`engine/examples/timeline_validator.py` if available (requires
`jsonschema`), otherwise it will still write the timeline file.
"""
import json
import sys
from pathlib import Path

# Add the engine src to path for imports when run as script
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from engine.engine import Engine
from engine.actor import Actor, CollisionException
from engine.physics_world import PhysicsWorld


def run_demo(output_path: Path, sample_dt: float = 1.0 / 20.0, sim_until: float = 10.0):
    engine = Engine()
    env = engine.env

    # create world and schedule fixed-dt loop
    world = PhysicsWorld()
    world.schedule_loop(env, 0.05)

    # static targets
    # Increase spacing so actors are clearly separated in Blender visualizations.
    # The radii are made explicit here so the exported timeline contains
    # per-actor radius metadata usable by visualizers.
    static_positions = [ (4.0, 0.0, 0.0), (4.0, 4.0, 0.0), (0.0, 4.0, 0.0) ]

    statics = [Actor(env, position=pos, actor_id=f"static-{i}") for i, pos in enumerate(static_positions)]
    mover = Actor(env, position=(0.0, 0.0, 0.0), actor_id="mover")

    # register all with world so collisions are detected and use explicit radii
    # to make collision extents clearer in visualizations.
    bodies = {}
    for i, s in enumerate(statics):
        # choose a larger visual radius for static targets
        b = world.register_body(s, radius=1.0)
        bodies[str(s.id)] = b
    # mover slightly smaller
    bodies[str(mover.id)] = world.register_body(mover, radius=0.8)

    # snapshot callback for engine
    actors = [mover] + statics

    def snapshot_cb():
        return [ {"id": a.id, "pos": list(a.position)} for a in actors ]

    engine.set_snapshot_callback(snapshot_cb)

    # process that moves the mover sequentially, using collisions to
    # trigger advancing to the next target.
    def mover_proc():
        for target in static_positions:
            ev = world.move_actor(mover, target, speed=0.5)
            try:
                payload = yield from ev.wait()
                # arrived cleanly (no collision)
            except Exception as e:
                # treat any exception (CollisionException) as the trigger
                # to proceed to the next target
                pass
            # small delay before moving to next target
            yield env.timeout(0.05)

    env.process(mover_proc)

    # run and record timeline frames at fixed sampling rate
    # Recommended sampling: ~20 Hz (sample_dt = 0.05s) is a good compromise
    # for Blender playback: it captures motion detail without producing
    # an excessive number of frames in the exported timeline. Higher rates
    # (e.g. 60Hz) increase fidelity but linearly increase file size.
    timeline = {
        "metadata": {
            "engine_version": "local",
            "sample_dt": sample_dt,
            "start_time": 0.0,
            "sim_until": sim_until,
        },
        "frames": [],
        # actors metadata map: key -> metadata dict (e.g. radius)
        "actors": {},
    }

    t = 0.0
    while t <= sim_until:
        engine.step_to_time(t)
        snap = engine.snapshot()
        timeline["frames"].append({"t": float(t), "actor_states": snap})
        t += sample_dt

    # optional validation using the provided validator script
    try:
        from engine.examples.timeline_validator import validate_timeline
    except Exception:
        validate_timeline = None

    if validate_timeline is not None:
        validate_timeline(timeline)

    # Prefer the engine's core export API which auto-detects format by
    # extension (supports json, hdf5, msgpack handlers). Fall back to
    # writing JSON text if the core exporter is not available or fails.
    try:
        from engine.engine import export_timeline

        # export_timeline accepts either an Engine instance or a pre-built
        # timeline data dict. We pass the dict we constructed above so the
        # core handlers can write it in the requested format (e.g. HDF5).

        try:
            # physics world bodies have been registered; collect radii from Body objects
            for aid, body in bodies.items():
                timeline["actors"][str(aid)] = {"radius": float(getattr(body, 'radius', 0.5))}
        except Exception:
            # best-effort only; leave actors map empty on error
            pass

        export_timeline(timeline, str(output_path), format="auto")
    except Exception:
        output_path.write_text(json.dumps(timeline, indent=2), encoding="utf8")


if __name__ == "__main__":
    # Default to simulation folder in project root
    default_path = Path(__file__).parent.parent.parent / "simulation" / "timeline.json"
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else default_path
    run_demo(out)
    print(f"Exported timeline to {out}")
