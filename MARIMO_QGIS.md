# Marimo + QGIS4 Setup

This project provides marimo notebooks that leverage QGIS4 (PyQGIS) libraries.

## Prerequisites

- QGIS4 installed (on this system: `/usr/bin/qgis`)
- `uv` package manager installed

## Setup

```bash
cd /home/jcz/Github/marimo_qgis
./qgis-env.sh setup     # detects QGIS's Python and builds the venv to match
```

`qgis-env.sh setup` detects the interpreter QGIS's bindings actually load under
and creates the venv against it with `--system-site-packages` — no Python version
to pin, so it survives QGIS/OS upgrades. If something is off, `./qgis-env.sh
doctor` reports exactly what and how to fix it.

The manual equivalent (only if you'd rather not use the script):

```bash
uv venv --python "$(./qgis-env.sh path)" --system-site-packages
uv pip install marimo pandas numpy matplotlib
```

`--system-site-packages` is required so the venv finds the **system** PyQt6
that ships with QGIS. Without it, uv installs a bundled PyQt6 wheel whose Qt6
version conflicts with the system QGIS Qt6 and causes an `ImportError` at runtime.

Two things matter here, both learned the hard way:

- **Pass the explicit system interpreter path** (`/usr/bin/python3.14`), not a
  bare version like `3.14`. A bare version lets uv use one of its own downloaded
  standalone CPython builds, whose "system site-packages" is the standalone
  build's own — *not* `/usr/lib/python3/dist-packages` where the OS PyQt6 lives.
  Pointing at `/usr/bin/python3.14` forces the OS interpreter, so
  `--system-site-packages` actually reaches the system PyQt6.
- **The venv Python must match the version QGIS's bindings are compiled for.**
  QGIS ships a compiled `qgis/_core.so` built against one Python ABI; a venv on
  any other minor version cannot import it. On this machine QGIS 4.0.3 is built
  against Python 3.14, and the system PyQt6 is installed only for 3.14 — so the
  venv must be 3.14. (The previous 3.13.7 instructions broke after the OS
  upgraded to Python 3.14, with `ModuleNotFoundError: No module named 'PyQt6'`.)

## Running Notebooks

No wrapper script or exported environment variables are needed. Just use `uv run`:

```bash
# Interactive editing
uv run marimo edit notebooks/qgis_test.py

# View-only (no code editing)
uv run marimo run notebooks/qgis_test.py

# Export to static HTML (headless, no browser needed)
uv run marimo export html notebooks/qgis_test.py -o output.html
```

Each notebook's QGIS init cell handles the two environment requirements
internally, before `QgsApplication` is created (the only point Qt reads them):

```python
sys.path.insert(0, "/usr/share/qgis/python")   # ≡ PYTHONPATH
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # headless Qt
```

`setdefault` leaves `QT_QPA_PLATFORM` unchanged if it was already set — so
notebooks launched from within a live QGIS session (via the plugin's launcher)
correctly inherit the real display platform.

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
- System Python 3.14 is required (at `/usr/bin/python3.14`) — it must match the
  Python version QGIS's compiled bindings were built against
- The venv must use `--system-site-packages` to access system PyQt6
- LSP will show errors for `qgis` imports — these can be ignored as long as
  runtime works
- Run `uvx marimo check notebook.py` to catch empty cells, cycles, and
  undefined variables before publishing
