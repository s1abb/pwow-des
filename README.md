# blender-des-lib

Compact discrete-event simulation primitives, runnable examples, and a small
Blender addon for importing/exporting timelines.

Repository layout

- `engine/` — core simulation package, examples, and tests
- `engine/docs/` — detailed engine documentation
- `engine/examples/` — runnable demos, exporters, timeline schema and validator
- `engine/tests/` — unit tests (pytest)
- `addon/` — Blender addon (development-stage) that depends on Blender's `bpy`

Quickstart (Windows PowerShell)

Create and activate a virtual environment, upgrade pip, and install dev
requirements:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

Run the test suite:

```powershell
pytest -q
```

Documentation

- API Documentation: [engine/docs/api](engine/docs/api.md)
- Architecture Documentation: [engine/docs/architecture.md](engine/docs/architecture.md)


Blender addon

Blender integrates with the discrete event simulation engine through a custom addon. The addon enables bidirectional workflow: importing simulation timelines for visualization and exporting Blender scenes as simulation setups.





