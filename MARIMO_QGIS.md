# Marimo + QGIS4 Setup

This project provides marimo notebooks that leverage QGIS4 (PyQGIS) libraries.

## Prerequisites

- QGIS4 installed (on this system: `/usr/bin/qgis`)
- `uv` package manager installed

## Setup

```bash
cd /home/jcz/Github/marimo_qgis
rm -rf .venv
uv venv --python 3.13.7 --system-site-packages
uv pip install marimo
```

## Running Notebooks

Set the PYTHONPATH before running marimo:

```bash
export PYTHONPATH=/usr/share/qgis/python
uv run marimo edit qgis_test.py
```

To run as a script (non-interactive):
```bash
PYTHONPATH=/usr/share/qgis/python uv run marimo run qgis_test.py
```

## Notebook Format

Marimo notebooks must follow this pattern:

```python
import sys
sys.path.insert(0, "/usr/share/qgis/python")

import marimo as mo

app = mo.App()

@app.cell
def _():
    import marimo as _mo
    _mo.md("# Title")
    return

@app.cell
def _():
    import sys
    sys.path.insert(0, "/usr/share/qgis/python")
    import qgis as _qgis
    from qgis.core import Qgis as _Qgis
    
    # Use underscore prefix for variables used across cells
    result = {"version": _Qgis.version()}
    return (result,)
```

Key points:
- Import `marimo as mo` at module level
- Use `@app.cell` decorators for cells
- Set `sys.path` inside each cell that uses qgis
- Use underscore prefix (`_qgis`, `_Qgis`) for imports that would conflict across cells
- Import marimo in each cell as well (`import marimo as _mo`)

## Notes

- QGIS Python bindings are located at `/usr/share/qgis/python`
- System Python 3.13 is required (at `/usr/bin/python3`)
- The PYTHONPATH must include the QGIS Python path whenever importing `qgis` modules
- Use `--system-site-packages` to access system PyQt6 required by QGIS
- The LSP will show errors for qgis imports - these can be ignored as long as runtime works
