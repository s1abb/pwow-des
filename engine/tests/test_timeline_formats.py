import os
import json
import tempfile

from engine.engine import Engine, export_timeline


def make_dummy_engine():
    # Minimal stub engine exposing snapshot() used by collect_timeline_data
    class Dummy:
        def snapshot(self):
            return {
                "metadata": {"sample_dt": 0.1, "start_time": 0.0},
                "frames": [
                    {"t": 0.0, "actor_states": [{"id": "a", "pos": [0, 0, 0]}]},
                    {"t": 0.1, "actor_states": [{"id": "a", "pos": [1, 0, 0]}]},
                ],
            }

    return Dummy()


def test_json_roundtrip(tmp_path):
    eng = make_dummy_engine()
    out = tmp_path / "out.json"
    export_timeline(eng, str(out), format="json")
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "frames" in data and len(data["frames"]) == 2


def test_autodetect_by_extension(tmp_path):
    eng = make_dummy_engine()
    out = tmp_path / "auto.json"
    # format auto detection should pick JSON
    export_timeline(eng, str(out), format="auto")
    assert out.exists()