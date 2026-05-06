"""Monitoring helpers for the discrete-event engine.

This module provides small utilities to collect snapshots from Resources and
Stores and to serialize them for external monitoring tools.
"""
from typing import Any, Dict


def resource_snapshot(resource, current_time=None):
    """Return the same structured snapshot as Resource.snapshot()."""
    return resource.snapshot(current_time=current_time)


def store_snapshot(store):
    """Return a small snapshot for Store: items count, waiting getters/putters counts."""
    return {
        'capacity': store.capacity,
        'items_count': len(store.items),
        'get_waiters': len(store.get_waiters),
        'put_waiters': len(store.put_waiters),
    }


def serialize_snapshot(snapshot: Any) -> Dict:
    """Convert a snapshot into JSON-serializable dicts (shallow)."""
    # This helper is intentionally shallow and safe — it converts known fields
    # into primitive types where possible.
    if isinstance(snapshot, list):
        return [serialize_snapshot(s) for s in snapshot]
    if isinstance(snapshot, dict):
        out = {}
        for k, v in snapshot.items():
            if hasattr(v, '__name__'):
                out[k] = getattr(v, '__name__')
            elif hasattr(v, '__repr__') and not isinstance(v, (str, int, float, bool, type(None))):
                out[k] = repr(v)
            else:
                out[k] = v
        return out
    # fallback
    try:
        return repr(snapshot)
    except Exception:
        return str(snapshot)
