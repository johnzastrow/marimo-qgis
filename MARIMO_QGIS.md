# Marimo + QGIS4 Setup

This project provides marimo notebooks that leverage QGIS4 (PyQGIS) libraries.

## Prerequisites

- QGIS4 installed (on this system: `/usr/bin/qgis`)
- `uv` package manager installed

## Setup

```bash
cd /home/jcz/Github/marimo_qgis
uv venv --python 3.13.7 --system-site-packages
uv pip install marimo pandas numpy matplotlib
```

`--system-site-packages` is required so the venv finds the **system** PyQt6
that ships with QGIS. Without it, uv installs a bundled PyQt6 wheel whose Qt6
version conflicts with the system QGIS Qt6 and causes an `ImportError` at runtime.

## Running Notebooks

No wrapper script or exported environment variables are needed. Just use `uv run`:

```bash
# Interactive editing
uv run marimo edit qgis_test.py

# View-only (no code editing)
uv run marimo run qgis_test.py

# Export to static HTML (headless, no browser needed)
uv run marimo export html qgis_test.py -o output.html
```

Each notebook's QGIS init cell handles the two environment requirements
internally, before `QgsApplication` is created (the only point Qt reads them):

```python
sys.path.insert(0, "/usr/share/qgis/python")   # ≡ PYTHONPATH
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # headless Qt
```

`setdefault` leaves `QT_QPA_PLATFORM` unchanged if it was already set — so
notebooks launched from within a live QGIS session (via the Processing Toolbox
script) correctly inherit the real display platform.

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

- QGIS Python bindings are located at `/usr/share/qgis/python`
- System Python 3.13 is required (at `/usr/bin/python3`)
- The venv must use `--system-site-packages` to access system PyQt6
- LSP will show errors for `qgis` imports — these can be ignored as long as
  runtime works
- Run `uvx marimo check notebook.py` to catch empty cells, cycles, and
  undefined variables before publishing
