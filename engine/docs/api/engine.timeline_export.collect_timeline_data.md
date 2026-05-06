# Function collect_timeline_data

## Module
`engine.timeline_export`

## Declaration
```py
def collect_timeline_data(engine) -> dict
```

## Description
Collect a timeline data structure from an `Engine` instance. The engine is
expected to expose a `snapshot()` method or a registered snapshot callback
that returns a JSON-serializable representation of actor states.

The returned dict should follow the repository convention:

```py
{
  "metadata": { ... },
  "frames": [ {"t": <float>, "actor_states": [ {"id": ..., "pos": [...]}, ... ] }, ... ]
}
```

Format handlers rely on this shape for export. Handlers may expect extra
metadata keys (for example `sample_dt`) when available.

