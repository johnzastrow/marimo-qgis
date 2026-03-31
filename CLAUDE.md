# marimo_qgis — Claude Project Context

## What This Is

A project for running [marimo](https://marimo.io) notebooks with QGIS4 (PyQGIS) on this Linux machine.

## Environment

- QGIS4 at `/usr/bin/qgis`, Python bindings at `/usr/share/qgis/python`
- QGIS version: 4.0.0-Norrköping
- Python 3.13.7 (system), marimo 0.21.1
- uv for package management
- `.venv` created with `--system-site-packages` (required for system PyQt6)

## Running Notebooks

No wrapper script or exported environment variables are needed:

```bash
# Interactive editing
uv run marimo edit qgis_test.py

# View-only
uv run marimo run qgis_test.py

# Export to static HTML
uv run marimo export html qgis_test.py -o output.html
```

Each QGIS notebook self-configures by including this pattern in its init cell:

```python
sys.path.insert(0, "/usr/share/qgis/python")          # finds PyQGIS bindings
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # headless Qt
```

These two lines run before `QgsApplication([], False)` is created — the only
point at which Qt reads `QT_QPA_PLATFORM`. `setdefault` leaves it unchanged
when launched from inside a live QGIS session.

## Known Issues / Status

- **WORKING**: Full QGIS4 + marimo integration. `uv run marimo export html qgis_test.py` exits 0 with QGIS version table and sample data rendered.
- **RESOLVED**: Previous "cells not executing" was a stale `__marimo__/session/` cache.
- **RESOLVED**: `AssertionError: Could not open <layer>` when launched from QGIS Processing tool — caused by relying on `os.getcwd()`. Fixed by using `os.path.dirname(os.path.abspath(__file__))`.

## Key Files

- `stations_analysis.py` — Distance analysis: loads stations.gpkg, QgsDistanceArea geodesic matrix, Pandas nearest-neighbour analysis
- `qgis_test.py` — Minimal notebook: confirms QGIS version
- `marimo_tutorial.py` — Comprehensive marimo feature tour (no QGIS dependency)
- `example/gpkg_summary.py` — Layer inventory, population trends, road length for Youngstown NY (20-layer GeoPackage)
- `example/simple_marimo_qgis.py` — Ultra-simple QGIS+marimo demo, extensively commented
- `processing/launch_marimo.py` — QGIS Processing Toolbox script to launch a marimo notebook from within QGIS
- `TROUBLESHOOTING.md` — Detailed investigation notes
- `MARIMO_QGIS.md` — Setup instructions

## Notebook Format

Marimo notebooks are plain Python files with decorated cell functions:

```python
import marimo
app = marimo.App()

@app.cell
def _():
    import marimo as mo
    return (mo,)

@app.cell
def _(mo):
    mo.md("# Title")   # last expression = cell output
    return
```

- Variables in `return (...)` are shared downstream; `_`-prefixed vars are cell-private
- **Cell output**: use `expr` as the last statement, then bare `return` — NOT `return expr`
- `__file__` works inside cells — use it for reliable relative paths to data files
- Run `uvx marimo check notebook.py` before handing back to the user

## PEP 723 Inline Script Metadata

All notebooks include a PEP 723 header listing their PyPI dependencies:

```python
# /// script
# requires-python = ">=3.13"
# dependencies = ["marimo", "pandas"]
# ///
```

QGIS bindings are NOT listed (not on PyPI). The header is used by
`uv run notebook.py` for direct script execution; marimo itself ignores it.
