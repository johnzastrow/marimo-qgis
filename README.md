# marimo-qgis

Run [marimo](https://marimo.io) reactive notebooks with full [QGIS 4 / PyQGIS](https://qgis.org) support on Linux.

This repository contains working notebooks and a setup guide for the combination of:

- **QGIS 4** spatial operations (vector layers, geodesic distance, coordinate reference systems)
- **Pandas** tabular analysis
- **marimo** reactive, browser-based Python notebooks

## Example notebook

`stations_analysis.py` loads a set of weather stations from a GeoPackage, computes a
geodesic distance matrix using `QgsDistanceArea` (true ellipsoidal distances on WGS84),
and analyses closest/farthest pairs and per-station nearest neighbours with Pandas —
all displayed as interactive marimo tables.

`example/gpkg_summary.py` loads a 9-layer GeoPackage (Youngstown NY area, EPSG:26918),
builds a layer inventory using `dataProvider().subLayers()`, extracts decennial
population data from the `town` layer, and computes total road network length with
`QgsDistanceArea` — all displayed as interactive marimo tables.

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

uv pip install marimo pandas numpy
```

Verify the venv finds the **system** PyQt6, not a bundled wheel:

```bash
.venv/bin/python -c "import PyQt6; print(PyQt6.__file__)"
# Must print: /usr/lib/python3/dist-packages/PyQt6/__init__.py
```

### 4. Run a notebook

Use the `marimo-qgis` wrapper script. It sets the required environment variables
before Python starts (see [Why the wrapper?](#why-the-wrapper) below):

```bash
# Interactive editing
./marimo-qgis edit stations_analysis.py

# Export to static HTML (headless, no browser needed)
./marimo-qgis export html stations_analysis.py -o output.html
```

Your browser will open automatically. The notebook loads the included
`stations.gpkg` and displays QGIS version info, the distance matrix, and
nearest-neighbour analysis.

---

## Writing your own QGIS notebook

### Minimal cell pattern

```python
@app.cell
def _():
    import sys, os

    sys.path.insert(0, "/usr/share/qgis/python")   # adjust if QGIS is elsewhere
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # fallback if no wrapper

    from qgis.core import QgsApplication, Qgis

    qgs = QgsApplication([], False)   # False = no GUI
    qgs.initQgis()

    return Qgis, QgsApplication, qgs
```

### Do not use `/// script` inline metadata

marimo supports [PEP 723 inline script metadata](https://peps.python.org/pep-0723/):

```python
# /// script
# dependencies = ["pandas", "pyqt6"]
# ///
```

**Do not use this with QGIS notebooks.** When marimo sees this block it creates a
fresh uv-managed environment that does not have `--system-site-packages`. It will
install a bundled PyQt6 wheel with its own Qt6, which conflicts with the system QGIS
Qt6 and produces:

```
ImportError: libQt6Network.so.6: undefined symbol: _ZN14QObjectPrivateC2Ei,
             version Qt_6_PRIVATE_API
```

Manage dependencies via the venv (`uv pip install`) instead.

### Cell return values

marimo tracks data flow between cells through `return` statements. Everything a
downstream cell needs must be explicitly returned:

```python
@app.cell
def _(QgsVectorLayer):
    layer = QgsVectorLayer("/path/to/data.gpkg", "name", "ogr")
    assert layer.isValid()
    return (layer,)   # other cells can now use `layer`
```

### No `__file__` in cells

`pathlib.Path(__file__)` raises `NameError` inside a cell — marimo wraps each cell
in a function where `__file__` is not defined. Use absolute paths:

```python
# Bad
data = pathlib.Path(__file__).parent / "data.gpkg"

# Good
data = "/home/user/project/data.gpkg"
```

---

## Why the wrapper?

The `marimo-qgis` script sets three environment variables **before Python starts**:

```bash
export PYTHONPATH=/usr/share/qgis/python  # find PyQGIS
export QT_QPA_PLATFORM=offscreen          # run Qt headlessly, no display needed
export QT_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/qt6/plugins  # use system Qt6 plugins
```

In `marimo edit` mode, cells run in a **subprocess spawned with
`multiprocessing.spawn`** — a fresh Python interpreter that inherits environment
variables but not loaded libraries. Qt reads `QT_QPA_PLATFORM` at library-load time,
before any cell code executes. Setting it inside a cell with
`os.environ.setdefault(...)` is too late for the spawn process.

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for the full root-cause analysis and
a debugging checklist.

---

## Project structure

```
marimo-qgis/
├── marimo-qgis          # wrapper script (sets env vars, runs marimo)
├── stations_analysis.py # example notebook: QGIS distance matrix + Pandas analysis
├── qgis_test.py         # minimal notebook: confirms QGIS version
├── stations.gpkg        # sample data: CWOP weather stations in Maine, USA
├── example/
│   ├── example.gpkg     # Youngstown NY area: 9-layer GeoPackage, EPSG:26918
│   ├── gpkg_summary.py  # example notebook: layer inventory, population trends, road length
│   └── INSTRUCTIONS.md  # quick start for this example
├── pyproject.toml       # project metadata and dependencies
├── TROUBLESHOOTING.md   # debugging guide for marimo + QGIS integration issues
└── MARIMO_QGIS.md       # additional setup notes
```

---

## Platform support

| Platform | Status |
|----------|--------|
| Linux (Ubuntu, QGIS apt repo) | Tested and working |
| Windows | Not yet documented |
| macOS | Not yet documented |

On Windows and macOS the main challenges are:

- **PyQGIS path**: the QGIS Python bindings are in a different location (often inside
  the QGIS application bundle).
- **Qt6 conflict**: QGIS ships its own Qt6 on those platforms; ensuring Python finds
  QGIS's Qt6 rather than a PyPI-installed one requires setting `PATH` and
  `QT_PLUGIN_PATH` correctly in the launcher.

If you get it working on Windows or macOS, a pull request adding a platform-specific
wrapper script and notes to TROUBLESHOOTING.md would be very welcome.

---

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for documented issues including:

- `ImportError: libQt6Network.so.6: undefined symbol` — the most common error, caused
  by a PyQt6 version conflict
- Cells showing no output in `marimo edit` — stale session cache
- uv using the wrong Python version

## License

MIT
