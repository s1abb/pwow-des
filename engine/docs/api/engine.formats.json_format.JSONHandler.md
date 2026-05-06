# JSONHandler

## Module
`engine.formats.json_format`

## Class / Interface
`JSONHandler` (static-method based)

## Description
Handler that exports/imports timeline data as JSON. It writes a single JSON
object containing `metadata` and `frames` by default. The handler accepts a
`pretty` kwarg to enable pretty-printed output.

### Methods
- `export(timeline_data, path, pretty=False, **kwargs)` — write JSON to `path`.
- `import_timeline(path, **kwargs)` — read JSON and return the timeline dict.
- `validate(path) -> bool` — return True if the file can be parsed as JSON.

### Notes
- This handler preserves the human-readable nature of timelines and is
  suitable for examples and small simulations. For large datasets prefer
  binary formats (HDF5).

