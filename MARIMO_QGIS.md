# Marimo + QGIS4 Setup

This project provides marimo notebooks that leverage QGIS4 (PyQGIS) libraries.
The plugin runs them on **QGIS's own Python interpreter**, so there is no
separate virtualenv to build or version to pin.

## Prerequisites

- QGIS 4 installed (OSGeo4W on Windows; the QGIS apt repo on Linux)
- The **marimo Launcher** plugin installed (see `README.md`)
- marimo installed into QGIS's Python (the plugin offers to do this on first
  launch — see below)

## Setup

The plugin launches notebooks with `<qgis_python> -m marimo <mode> <notebook>`,
where `<qgis_python>` is derived live from the running QGIS (`runtime.qgis_python()`).
Because it is the exact interpreter QGIS uses, it is always ABI-compatible with
the PyQGIS bindings and tracks QGIS Python upgrades automatically — nothing to
pin.

### Installing marimo into QGIS's Python

marimo (and any library a notebook imports) must be installed into QGIS's own
interpreter. The dock preflight-checks this on launch (`marimo_available()` in
`plugin/ui/process.py`); if marimo is missing it offers to install it into that
interpreter. The dock runs a **cross-platform pip bootstrap**: it ensures pip
exists (via `ensurepip` if needed), then tries `pip install` and falls back to
`--user` / `--user --break-system-packages` so it works on a bundled writable
Python (Windows/macOS) or a read-only/externally-managed system Python (Linux).
This also handles QGIS Python upgrades gracefully — a new interpreter has a fresh
site-packages with no marimo, so the plugin simply offers to reinstall.

To install manually:

```powershell
# Windows (OSGeo4W) — pip into the QGIS Python works directly:
& cmd /c "C:\OSGeo4W\bin\python-qgis.bat -m pip install marimo"
```

```bash
# Linux — QGIS uses the system Python; if pip is missing, add it once:
sudo apt install python3-pip
# then install into the per-user site (externally-managed safe):
<qgis_python> -m pip install --user marimo
```

> **`uv` is optional and dev-only.** `runtime.uv_executable()` still exists, but
> the plugin launch path no longer uses `uv`. The `pyproject.toml`/`uv` workflow
> (and `./qgis-env.sh setup`) remains a convenient way to *develop* notebooks
> outside QGIS, but is **not** required to run them from the plugin.

### Installing other packages (geopandas, etc.)

Notebook dependencies go in the **same** interpreter — never a separate venv.
The dock's Setup tab has an **Install package(s)** field; the Browse tab's
**Detect packages** button scans a notebook for what it needs (PEP 723
`# /// script` deps + imports missing from QGIS's Python, mapped to PyPI names
via marimo's own table) and pre-fills the field. After installing, it verifies
the imports resolve. The Setup tab's **"Packages available to marimo & QGIS"**
report is the shareable inventory of what's installed (with `user`/`system`
location). Do **not** use marimo's in-browser "Install with uv" button for QGIS
notebooks — it targets a uv sandbox venv without PyQGIS that a dock-launched
notebook can't see.

## Running Notebooks

The normal path is to launch from the dock's **Browse** tab. To run the same
command manually, use QGIS's interpreter (the Setup tab reports its path):

```powershell
# Windows (OSGeo4W)
& cmd /c "C:\OSGeo4W\bin\python-qgis.bat -m marimo edit notebooks\qgis_test.py"
```

```bash
# Linux / macOS
<qgis_python> -m marimo edit notebooks/qgis_test.py     # interactive editing
<qgis_python> -m marimo run notebooks/qgis_test.py      # view-only
<qgis_python> -m marimo export html notebooks/qgis_test.py -o output.html  # headless
```

Each notebook's QGIS init cell sets `QT_QPA_PLATFORM` before `QgsApplication` is
created (the only point Qt reads it):

```python
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # headless Qt
```

`setdefault` leaves `QT_QPA_PLATFORM` unchanged if it was already set — so
notebooks launched from within a live QGIS session (via the plugin's launcher,
which does not force offscreen) correctly inherit the real display platform.
When launched from the dock, the plugin also adds the PyQGIS bindings directory
to the notebook's `PYTHONPATH`, so `import qgis` works without editing `sys.path`.

### Launch logs

Every dock launch captures the subprocess stdout/stderr to
`%TEMP%\marimo_qgis_logs\<notebook>.log` (Windows) or the OS temp dir equivalent,
and the flashing console window is suppressed. If a launched notebook dies within
~3 seconds, the dock shows a dialog with the last 40 lines of that log.

## Notebook Format

Marimo notebooks are plain Python files. Each cell is a decorated function:

```python
import marimo

app = marimo.App()

@app.cell
def _():
    import marimo as mo
    return (mo,)

@app.cell
def _(mo):
    mo.md("# Title")
    return
```

Key points:
- Variables returned from a cell are shared with all downstream cells that list
  them as function arguments.
- Prefix with `_` to keep a variable cell-private (not exported).
- The **last expression** of a cell is its visual output — do not use
  `return mo.md(...)`.  Use `mo.md(...)` then bare `return`.
- `__file__` works inside cells — use it to locate data files relative to the
  notebook rather than relying on `os.getcwd()`.

## Notes

- Notebooks run on QGIS's own interpreter — no separate venv, and no Python
  version to pin. The plugin derives it live, so it tracks QGIS upgrades.
- marimo must be installed **into that interpreter** (the dock offers to do it).
- The plugin adds QGIS's PyQGIS bindings directory to the notebook's
  `PYTHONPATH` automatically (derived from the running QGIS, correct on every
  platform).
- LSP will show errors for `qgis` imports — these can be ignored as long as
  runtime works.
- Run `marimo check notebook.py` (with QGIS's Python, or `uvx marimo check` in a
  dev venv) to catch empty cells, cycles, and undefined variables before
  publishing.
