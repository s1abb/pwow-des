# Function export_timeline

## Module
`engine.timeline_export`

## Declaration
```py
def export_timeline(engine_or_data, path: str, format: str = "auto", **kwargs)
```

## Description
Export a timeline to the given `path` using the requested `format`.

- `engine_or_data` may be an `Engine` instance (the function will call
  `snapshot()` internally) or a pre-built timeline dict following the
  repository timeline shape (`{"metadata": {...}, "frames": [...]}`).
- `format` may be `'auto'` (default) which selects the handler based on
  the file extension, or an explicit format name such as `'json'` or
  `'hdf5'`.
- `kwargs` are passed to the selected format handler (for example
  `compression='gzip'` for the HDF5 handler).

### Returns
The function returns the `path` on success (handlers may vary).

### Errors
- Raises `ValueError` for unsupported format names.
- Format handlers may raise IOErrors or serialization errors.

### Example
```py
from engine.timeline_export import export_timeline

# engine is an Engine instance with a snapshot callback
export_timeline(engine, "out/sim.h5")  # auto-detects hdf5 from extension

# Or pass a pre-built timeline dict
export_timeline(timeline_dict, "out/sim.json", format='json')
```

