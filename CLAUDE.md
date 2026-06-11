# marimo_qgis — Claude Project Context

## What This Is

A project for running [marimo](https://marimo.io) notebooks with QGIS4 (PyQGIS).
The QGIS plugin launches notebooks on **QGIS's own Python interpreter**. Now
developed and run on both Windows (QGIS 4 / OSGeo4W) and Linux; the project was
historically Linux/`uv`-centric, but that model has been replaced.

## Architecture: the launch model

- The plugin runs notebooks as `<qgis_python> -m marimo <mode> <notebook>`.
- `<qgis_python>` comes from `plugin/runtime.py::qgis_python()`, derived **live**
  from the running QGIS: `sys.prefix` → `python.exe` on Windows;
  `sys.executable` / `sys.prefix/bin` on Linux/macOS. No hardcoded version, so
  it tracks QGIS Python upgrades and is always ABI-compatible with PyQGIS.
- **Why the change:** the old `uv run marimo edit` model failed on Windows with
  `AssertionError: SRE module mismatch` — uv built a Python 3.14 venv (from
  `requires-python>=3.13` in `pyproject.toml`) while QGIS on Windows runs Python
  3.12 (OSGeo4W), and the 3.14 interpreter loaded QGIS's 3.12 stdlib. Using
  QGIS's own interpreter eliminates this entire class of mismatch.
- marimo must be installed into QGIS's Python. The dock preflight-checks via
  `plugin/ui/process.py::marimo_available()` and offers to run
  `python -m pip install marimo` into that interpreter if missing (also handles
  QGIS Python upgrades, which present a fresh site-packages with no marimo).
- **`uv` is optional/dev-only.** `runtime.uv_executable()` still exists but is no
  longer on the launch path. The `pyproject.toml`/`uv` workflow is fine for
  developing notebooks outside QGIS; never document it as required to run them.

## Environment

- QGIS 4.0.3-Norrköping; marimo 0.23.9.
- Windows test machine: Python 3.12.13 at
  `C:\OSGeo4W\apps\Python312\python.exe`; GDAL 3.13.1; PROJ 9.8.1; GEOS 3.14.1;
  SpatiaLite 5.1.0 / SQLite 3.53.2; Qt 6.11.0 / PyQt 6.11.0.
- The Setup tab's environment report (`plugin/environment.py::report_markdown()`)
  is the source of truth for what a launched notebook will see.

## Running Notebooks

The normal path is the dock's **Browse** tab. Equivalent manual commands use
QGIS's interpreter:

```powershell
# Windows (OSGeo4W)
& cmd /c "C:\OSGeo4W\bin\python-qgis.bat -m marimo edit notebooks\qgis_test.py"
```

```bash
# Linux / macOS
<qgis_python> -m marimo edit notebooks/qgis_test.py
<qgis_python> -m marimo export html notebooks/qgis_test.py -o output.html
```

Each QGIS notebook sets `QT_QPA_PLATFORM` before `QgsApplication([], False)` is
created (the only point Qt reads it):

```python
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # headless Qt
```

`setdefault` leaves it unchanged when launched from inside a live QGIS session.
When launched from the dock, the plugin adds the PyQGIS bindings dir
(`runtime.pyqgis_dir()`) to the notebook's `PYTHONPATH`, so `import qgis` works
without editing `sys.path`.

## Logs / debugging

- Every dock launch logs subprocess stdout/stderr to
  `%TEMP%\marimo_qgis_logs\<notebook>.log` (Windows) / OS temp equivalent; the
  flashing console window is suppressed (CREATE_NO_WINDOW on Windows).
- If a launched notebook dies within ~3 seconds, the dock shows a dialog with
  the last 40 lines of that log.

## Known Issues / Status

- **WORKING**: Full QGIS4 + marimo integration on Windows and Linux. Headless
  smoke test `python -m marimo export html notebooks/qgis_test.py` exits 0.
- **RESOLVED**: Windows `AssertionError: SRE module mismatch` (console window
  flashed and closed) — was the `uv run` 3.14-vs-3.12 interpreter mismatch; fixed
  by launching on QGIS's own interpreter.
- **RESOLVED**: Previous "cells not executing" was a stale `__marimo__/session/` cache.
- **RESOLVED**: `AssertionError: Could not open <layer>` when launched from QGIS Processing tool — caused by relying on `os.getcwd()`. Fixed by using `os.path.dirname(os.path.abspath(__file__))`.

## Key Files

- `notebooks/stations_analysis.py` — Distance analysis: loads stations.gpkg, QgsDistanceArea geodesic matrix, Pandas nearest-neighbour analysis
- `notebooks/qgis_test.py` — Minimal notebook: confirms QGIS version
- `notebooks/marimo_tutorial.py` — Comprehensive marimo feature tour (no QGIS dependency)
- `example/gpkg_summary.py` — Layer inventory, population trends, road length for Youngstown NY (20-layer GeoPackage)
- `example/simple_marimo_qgis.py` — Ultra-simple QGIS+marimo demo, extensively commented
- `processing/launch_marimo.py` — QGIS Processing Toolbox script to launch a marimo notebook from within QGIS
- `plugin/runtime.py` — `qgis_python()` / `pyqgis_dir()` interpreter resolution; bridge handle; legacy `uv_executable()`
- `plugin/ui/process.py` — `MarimoProcessManager`: launches `-m marimo`, logs to `%TEMP%\marimo_qgis_logs\`, `marimo_available()` preflight
- `plugin/ui/dock.py` — Setup/Browse/Running tabs; marimo install prompt; early-exit log dialog
- `plugin/environment.py` — Setup-tab env report + example downloader
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
- Run `marimo check notebook.py` (QGIS's Python) or `uvx marimo check` (dev venv) before handing back to the user

## PEP 723 Inline Script Metadata — Do NOT use in QGIS notebooks

The plugin launches on QGIS's own interpreter, not `uv run`, so PEP 723
auto-sandboxing is not triggered there. But under the optional `uv run` dev
workflow, marimo detects any `# /// script` block and auto-sandboxes the kernel
in a fresh isolated environment with no access to QGIS's site-packages — no
PyQt6, causing `ModuleNotFoundError: No module named 'PyQt6'`.

Keep QGIS notebooks safe under either launch method: carry a comment at the top
explaining this instead of a `# /// script` header. PEP 723 headers are only safe
in notebooks with no QGIS dependency (e.g. `notebooks/marimo_tutorial.py`).
