# Module engine.formats (registry)

## Module
`engine.formats`

## Overview
The `engine.formats` module provides a small registry for timeline format
handlers. Handlers implement a minimal interface (export/import/validate)
and are registered under a short name (for example `"json"` or `"hdf5"`).

### Public functions
- `register_handler(name: str, handler)` — register a handler object
- `get_handler(name: str)` — retrieve a previously registered handler (raises `ValueError` if unknown)
- `available_handlers()` — return a list of registered handler names

### Handler interface (informal)
Handlers should implement the following static methods:
- `export(timeline_data, path, **kwargs)`
- `import_timeline(path, **kwargs)`
- `validate(path) -> bool`

