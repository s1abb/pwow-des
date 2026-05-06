# HDF5Handler

## Module
`engine.formats.hdf5_format`

## Class / Interface
`HDF5Handler` (static-method based)

## Description
Handler that exports/imports timeline data using HDF5 via `h5py` and
`numpy`. The current implementation writes:

- `times` (float64 dataset)
- `actors/{actor_id}/positions` (n_frames x 3 float32 datasets)
- root attributes for `metadata`

The handler supports partial read by specifying a `time_range` (start, end)
and an `actors` filter when importing.

### Methods
- `export(timeline_data, path, compression='gzip', **kwargs)` — write HDF5.
- `import_timeline(path, time_range=None, actors=None, **kwargs)` — read timeline data; `time_range` is a `(start, end)` tuple.
- `validate(path) -> bool` — return True if file can be opened as HDF5.

### Caveats
- Current implementation writes datasets in one pass and is not streaming —
  for very large timelines implement a streaming writer using extendable
  datasets to avoid high memory usage.

