# marimo-qgis

Run [marimo](https://marimo.io) reactive notebooks with full [QGIS 4 / PyQGIS](https://qgis.org) support on Linux.

This repository contains working notebooks and a setup guide for the combination of:

- **QGIS 4** spatial operations (vector layers, geodesic distance, coordinate reference systems)
- **Pandas** tabular analysis
- **marimo** reactive, browser-based Python notebooks

## Example notebooks

`example/simple_marimo_qgis.py` is the recommended starting point — a minimal,
extensively-commented notebook that opens `example.gpkg`, filters building polygons,
and sums their geodesic area with `QgsDistanceArea`.

`example/gpkg_summary.py` explores a 20-layer GeoPackage (Youngstown NY area, three
CRS: EPSG:26918, EPSG:4269, EPSG:4326), builds a layer inventory using
`QgsProviderRegistry.querySublayers()`, extracts decennial population data, and
computes total road network length — all displayed as interactive marimo tables.

`stations_analysis.py` loads CWOP weather stations from a GeoPackage, computes a
geodesic distance matrix using `QgsDistanceArea`, and analyses closest/farthest pairs
and per-station nearest neighbours with Pandas.

---

## Quick start — Linux

> **Platform note**: This guide targets Linux (tested on Ubuntu with QGIS 4.0.0
> "Norrköping"). Windows and macOS support is possible but not yet documented — the
> main challenge on those platforms is locating the PyQGIS bindings and ensuring the
> correct Qt6 is on the path. Contributions welcome.

### 1. Install QGIS 4

Follow the [official QGIS installation guide](https://qgis.org/download/) for your
distribution. On Ubuntu you can use the QGIS apt repository:

```bash
sudo apt install qgis python3-qgis
```

Confirm the Python bindings are present:

```bash
ls /usr/share/qgis/python/qgis/core/__init__.py
```

### 2. Install uv

[uv](https://docs.astral.sh/uv/) is the recommended package manager for this project.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 3. Clone this repo and create the venv

```bash
git clone https://github.com/johnzastrow/marimo-qgis.git
cd marimo-qgis

# --system-site-packages is REQUIRED — it makes the system PyQt6
# (installed alongside QGIS) visible inside the venv.  Without it,
# uv will install a bundled PyQt6 wheel whose Qt6 version conflicts
# with the system QGIS Qt6 and causes an ImportError at runtime.
uv venv --python 3.13 --system-site-packages

uv pip install marimo pandas numpy matplotlib
```

Verify the venv finds the **system** PyQt6, not a bundled wheel:

```bash
.venv/bin/python -c "import PyQt6; print(PyQt6.__file__)"
# Must print: /usr/lib/python3/dist-packages/PyQt6/__init__.py
```

### 4. Run a notebook

No wrapper script or exported environment variables are needed:

```bash
# Interactive editing
uv run marimo edit example/simple_marimo_qgis.py

# View-only (no code editing)
uv run marimo run example/gpkg_summary.py

# Export to static HTML (headless, no browser needed)
uv run marimo export html example/gpkg_summary.py -o summary.html
```

Your browser will open automatically in edit/run mode.

---

## Writing your own QGIS notebook

### Minimal QGIS init cell

Every QGIS notebook needs one init cell that configures the environment and
creates the `QgsApplication` singleton:

```python
@app.cell
def _():
    import os, sys

    sys.path.insert(0, "/usr/share/qgis/python")   # find PyQGIS bindings
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # headless Qt

    from qgis.core import QgsApplication, Qgis

    qgs = QgsApplication([], False)   # False = no GUI
    qgs.initQgis()

    return Qgis, QgsApplication, qgs
```

`sys.path.insert` and `os.environ.setdefault` both execute **before**
`QgsApplication([], False)` — the only point at which Qt reads
`QT_QPA_PLATFORM`. No wrapper script or pre-exported environment variables
are required; the notebook is self-contained.

`setdefault` leaves `QT_QPA_PLATFORM` unchanged if it was already set — so
notebooks launched from inside a live QGIS session (via the Processing Toolbox
script in `processing/launch_marimo.py`) correctly inherit the real display
platform rather than forcing `offscreen`.

### Do not use PEP 723 inline script metadata in QGIS notebooks

When marimo is launched via `uv run`, it detects any `# /// script` block and
**auto-sandboxes** the notebook kernel — creating a fresh isolated environment
without `--system-site-packages`. That environment has no PyQt6, so every
`from qgis.core import ...` fails with `ModuleNotFoundError: No module named 'PyQt6'`.

**Do not add** `# /// script` blocks to QGIS notebooks. Manage dependencies
via the project venv instead:

```bash
uv venv --python 3.13 --system-site-packages
uv pip install marimo pandas numpy
```

PEP 723 headers are safe in notebooks with **no QGIS dependency** (e.g.
`marimo_tutorial.py`), where the isolated environment has everything it needs.

### Locating data files

Use `__file__` to locate data files relative to the notebook, not `os.getcwd()`.
`os.getcwd()` reflects the launch directory, which varies depending on whether
you started from the terminal, the QGIS Processing Toolbox, or a CI runner.
`__file__` is always the notebook's own path:

```python
import os as _os
_gpkg = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "data.gpkg")
```

### Cell output

marimo renders the **last expression** of a cell as its visual output. Use the
expression as the final statement and follow it with a bare `return`:

```python
@app.cell
def _(mo, total_m2):
    mo.stat(value=f"{total_m2:,.1f} m²", label="Total area")
    return
```

**Do not** use `return mo.stat(...)` — marimo's checker (`uvx marimo check`)
flags this as an empty cell, and nothing is displayed.

---

## Project structure

```
marimo-qgis/
├── stations_analysis.py          # QGIS distance matrix + Pandas analysis
├── qgis_test.py                  # minimal: confirms QGIS version
├── marimo_tutorial.py            # marimo feature tour (no QGIS dependency)
├── stations.gpkg                 # sample data: CWOP weather stations, Maine
├── example/
│   ├── example.gpkg              # Youngstown NY area: 20-layer GeoPackage
│   ├── gpkg_summary.py           # layer inventory, population trends, road length
│   ├── simple_marimo_qgis.py     # minimal QGIS+marimo demo, extensively commented
│   └── INSTRUCTIONS.md           # quick start for this example
├── processing/
│   └── launch_marimo.py          # QGIS Processing Toolbox script
├── pyproject.toml                # project metadata and dependencies
├── TROUBLESHOOTING.md            # debugging guide
└── MARIMO_QGIS.md                # additional setup notes
```

---

## Platform support

| Platform | Status |
|----------|--------|
| Linux (Ubuntu, QGIS apt repo) | Tested and working |
| Windows | Not yet documented |
| macOS | Not yet documented |

### What transfers to all platforms

The following aspects of this approach are fully platform-independent:

- `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` — Qt ships the offscreen
  platform on Windows and macOS too
- `__file__`-based data paths — portable Python
- PEP 723 headers, marimo cell patterns, `uvx marimo check`
- `processing/launch_marimo.py` — `subprocess.Popen` with `start_new_session=True`
  works on all platforms

### Why Linux is simpler

On Linux, QGIS is installed via the system package manager (apt). PyQt6 lands in the
system Python packages (`/usr/lib/python3/dist-packages/PyQt6/`), so a venv created
with `--system-site-packages` inherits it automatically. The bindings are at a stable,
well-known path (`/usr/share/qgis/python`).

On Windows and macOS, **QGIS bundles its own Python, Qt6, and PyQt6 inside the
application**. There is no system PyQt6 to inherit, and `--system-site-packages` does
not help.

### Windows

QGIS on Windows is typically installed via the OSGeo4W installer. The PyQGIS bindings
and Qt6 DLLs live inside that installation:

| Item | Typical path |
|------|-------------|
| Python bindings | `C:\Program Files\QGIS 4.x\apps\qgis\python` |
| Qt6 plugins | `C:\Program Files\QGIS 4.x\apps\qt6\plugins` |
| Python interpreter | `C:\Program Files\QGIS 4.x\apps\Python313\python.exe` |

Two viable approaches:

**Option A — Use QGIS's bundled Python directly.** Avoids all Qt6 conflicts because
you are using the exact Python and Qt6 that QGIS itself uses:
```bat
"C:\Program Files\QGIS 4.x\apps\Python313\python.exe" -m pip install marimo pandas
"C:\Program Files\QGIS 4.x\apps\Python313\python.exe" -m marimo edit notebook.py
```

**Option B — Use a separate Python, adapt the init cell.** Add both `sys.path` and
`QT_PLUGIN_PATH` before `QgsApplication` is created:
```python
sys.path.insert(0, r"C:\Program Files\QGIS 4.x\apps\qgis\python")
os.environ.setdefault("QT_PLUGIN_PATH", r"C:\Program Files\QGIS 4.x\apps\qt6\plugins")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
```
Getting a separate Python venv to find QGIS's Qt6 DLLs (not a PyPI-installed copy)
is the main difficulty on this path.

### macOS

QGIS on macOS ships as `QGIS.app`. The bundle contains its own Python and Qt6:

| Item | Path |
|------|------|
| Python bindings | `/Applications/QGIS.app/Contents/Resources/python/` |
| Qt6 plugins | `/Applications/QGIS.app/Contents/MacOS/plugins/` |
| Python interpreter | `/Applications/QGIS.app/Contents/MacOS/bin/python3` |

**Option A — Use QGIS's bundled Python directly:**
```bash
/Applications/QGIS.app/Contents/MacOS/bin/python3 -m pip install marimo pandas
/Applications/QGIS.app/Contents/MacOS/bin/python3 -m marimo edit notebook.py
```

**Option B — Use a separate Python, adapt the init cell:**
```python
sys.path.insert(0, "/Applications/QGIS.app/Contents/Resources/python")
os.environ.setdefault("QT_PLUGIN_PATH", "/Applications/QGIS.app/Contents/MacOS/plugins")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
```

### Cross-platform init cell pattern

If you want notebooks that work on all three platforms, detect the OS in the init cell:

```python
import sys, os

if sys.platform == "win32":
    sys.path.insert(0, r"C:\Program Files\QGIS 4.x\apps\qgis\python")
    os.environ.setdefault("QT_PLUGIN_PATH", r"C:\Program Files\QGIS 4.x\apps\qt6\plugins")
elif sys.platform == "darwin":
    sys.path.insert(0, "/Applications/QGIS.app/Contents/Resources/python")
    os.environ.setdefault("QT_PLUGIN_PATH", "/Applications/QGIS.app/Contents/MacOS/plugins")
else:  # Linux
    sys.path.insert(0, "/usr/share/qgis/python")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
```

`QT_PLUGIN_PATH` is not needed on Linux because Qt finds the system plugins
automatically. On Windows and macOS it is required so Qt locates the platform plugin
(`qoffscreen`) inside QGIS's bundle rather than looking in a non-existent system
location.

If you get it working on Windows or macOS, a pull request adding platform-specific
notes to TROUBLESHOOTING.md would be very welcome.

---

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for documented issues including:

- `ImportError: libQt6Network.so.6: undefined symbol` — the most common error, caused
  by a PyQt6 version conflict (venv missing `--system-site-packages`)
- Cells showing no output in `marimo edit` — stale session cache
- uv using the wrong Python version

## License

MIT
