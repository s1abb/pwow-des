import json
from pathlib import Path
from typing import Any, Dict


def detect_format_from_path(path: str) -> str:
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix in (".json",):
        return "json"
    if suffix in (".msgpack", ".mpack"):
        return "msgpack"
    if suffix in (".h5", ".hdf5"):
        return "hdf5"
    # default to json
    return "json"


def get_format_handler(format_name: str):
    # Import here to avoid package import cycles when engine is imported
    from .formats import get_handler

    return get_handler(format_name)


def collect_timeline_data(engine) -> Dict[str, Any]:
    """Collect timeline data from an Engine instance.

    The engine may expose a `snapshot()` method (preferred) or a
    registered snapshot callback via `set_snapshot_callback`.
    """
    if hasattr(engine, "snapshot") and callable(engine.snapshot):
        return engine.snapshot()
    # If engine is already a data dict, return it unchanged
    if isinstance(engine, dict):
        return engine
    # Fallback: minimal metadata
    return {"metadata": {"collected_at": None}, "frames": []}


def export_timeline(engine_or_data, path: str, format: str = "auto", **kwargs):
    """Export a timeline to `path` using the requested format.

    `engine_or_data` may be an Engine instance (with `snapshot()`) or a
    pre-built timeline data dict. If `format` is 'auto', detect by path.
    """
    if format == "auto":
        format = detect_format_from_path(path)

    handler = get_format_handler(format)

    # If engine_or_data is Engine-like, collect data
    if not isinstance(engine_or_data, dict):
        timeline_data = collect_timeline_data(engine_or_data)
    else:
        timeline_data = engine_or_data

    return handler.export(timeline_data, path, **kwargs)
