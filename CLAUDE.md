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

```bash
# Interactive editing
export PYTHONPATH=/usr/share/qgis/python
uv run marimo edit qgis_test.py

# Or use the wrapper script
./marimo-qgis edit qgis_test.py
```

## Known Issues / Status

- **WORKING**: Full QGIS4 + marimo integration. `marimo export html qgis_test.py` exits 0 with QGIS version table and sample data rendered.
- **RESOLVED**: Previous "cells not executing" was a stale `__marimo__/session/` cache — not a real kernel failure. `marimo export html` always re-executes and confirms cells work.

## Key Files

- `stations_analysis.py` — Distance analysis notebook: loads stations.gpkg, QgsDistanceArea geodesic matrix, Pandas nearest-neighbour analysis
- `qgis_test.py` — QGIS notebook (tests `Qgis.version()`)
- `test_simple.py` — Minimal notebook with no QGIS deps (also broken)
- `marimo-qgis` — Wrapper script that sets `PYTHONPATH` and runs marimo
- `TROUBLESHOOTING.md` — Detailed investigation notes
- `MARIMO_QGIS.md` — Setup instructions

## Notebook Format

Marimo notebooks use decorated functions, not Jupyter cells:

```python
import marimo as mo
app = mo.App()

@app.cell
def _():
    import marimo as _mo
    return _mo.md("# Title")
```

Use underscore-prefixed imports inside cells (`import qgis as _qgis`) to avoid cross-cell namespace conflicts.

## Next Debugging Steps

1. Try `marimo run` (non-interactive) to see if it produces output without browser
2. Check if kernel process is actually spawned: `ps aux | grep marimo`
3. Try `--sandbox` mode
4. Test with a fresh user account to rule out env pollution
