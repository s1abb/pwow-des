import json
from pathlib import Path
import tempfile

from engine.engine import Engine


def test_step_to_time_and_step_by():
    eng = Engine()
    env = eng.env

    # schedule a timeout at t=1
    def proc():
        yield env.timeout(1.0)

    env.process(proc)

    assert eng.step_to_time(0.5)
    assert env.now == 0.5
    assert eng.step_by(0.5)
    assert env.now == 1.0


def test_snapshot_and_export_smoke(tmp_path: Path):
    out = tmp_path / "demo_timeline.json"
    # import the example exporter by path since examples/ is not a package
    import runpy
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "engine" / "examples" / "export_simulation.py"
    ns = runpy.run_path(str(script))
    run_fn = ns.get("run_and_export")
    assert run_fn is not None
    run_fn(out, sample_dt=0.5, sim_until=1.0)

    assert out.exists()
    data = json.loads(out.read_text(encoding="utf8"))
    assert "frames" in data and isinstance(data["frames"], list)
    # ensure frames contain t and actor_states
    assert all("t" in f and "actor_states" in f for f in data["frames"])


def test_timeline_validator_accepts_valid(tmp_path: Path):
    # generate a valid timeline via exporter
    out = tmp_path / "timeline.json"
    import runpy
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "engine" / "examples" / "export_simulation.py"
    ns = runpy.run_path(str(script))
    ns["run_and_export"](out, sample_dt=0.5, sim_until=1.0)

    # import validator: prefer package import, otherwise load by path
    try:
        from engine.examples.timeline_validator import validate_timeline
    except Exception:
        import runpy
        repo_root = Path(__file__).resolve().parents[2]
        nv = runpy.run_path(str(repo_root / "engine" / "examples" / "timeline_validator.py"))
        validate_timeline = nv.get("validate_timeline")

    data = json.loads(out.read_text(encoding="utf8"))
    assert validate_timeline(data) is True


def test_timeline_validator_rejects_invalid():
    try:
        from engine.examples.timeline_validator import validate_timeline
    except Exception:
        import runpy
        repo_root = Path(__file__).resolve().parents[2]
        nv = runpy.run_path(str(repo_root / "engine" / "examples" / "timeline_validator.py"))
        validate_timeline = nv.get("validate_timeline")

    bad = {"metadata": {}, "frames": [{"x": 1}]}
    try:
        validate_timeline(bad)
    except Exception:
        return
    raise AssertionError("validator did not reject malformed timeline")
