from typing import Dict

_handlers: Dict[str, object] = {}


def register_handler(name: str, handler):
    _handlers[name] = handler


def get_handler(name: str):
    h = _handlers.get(name)
    if h is None:
        raise ValueError(f"Unknown timeline format handler: {name}")
    return h


# lazy import to avoid heavy deps at package import time
def available_handlers():
    return list(_handlers.keys())


# Register built-in handlers lazily to avoid import-time heavy deps
try:
    from .json_format import JSONHandler

    register_handler("json", JSONHandler)
except Exception:
    # ignore errors during packaging/import
    pass

# Register HDF5 handler if available
try:
    from .hdf5_format import HDF5Handler

    register_handler("hdf5", HDF5Handler)
except Exception:
    pass
