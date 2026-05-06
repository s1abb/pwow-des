Examples for the `engine` subproject

Run examples from the repository root with the `engine/src` folder on PYTHONPATH:

```powershell
. .venv\Scripts\Activate.ps1
$env:PYTHONPATH = "${PWD}\engine\src"
python engine\examples\simple_timeout_demo.py
```

This directory contains small, self-contained demos showing common engine
patterns: timeouts, resource requests and priorities, store/container
behaviour, interrupts and preemption.  Each script is runnable as a
standalone program; their names reflect the scenario they demonstrate.

See `INDEX.md` for a short description of each example and suggested
consolidations.

Pre-commit hook
---------------

This repository includes a small pre-commit hook configuration that runs
a local checker to ensure `engine/examples/*.py` files have module
docstrings and guard their logging configuration.

To enable pre-commit locally:

```powershell
pip install pre-commit
pre-commit install
```

You can run the checker manually without installing pre-commit:

```powershell
python tools\hooks\check_examples.py
```
