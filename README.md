# marimo-qgis

Run [marimo](https://marimo.io) reactive notebooks on
[QGIS 4 / PyQGIS](https://qgis.org), launched straight from QGIS.

The plugin runs notebooks on **QGIS's own Python interpreter** (`<qgis_python> -m
marimo …`), discovered live from the running QGIS. Because it is the exact
interpreter QGIS itself uses, it is always ABI-compatible with the PyQGIS
bindings and tracks QGIS Python upgrades automatically — no version to pin, no
separate virtualenv required. Tested on Windows (QGIS 4 / OSGeo4W) and Linux.
See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for debugging tips; contributions to
improve cross-platform coverage are very welcome.

## Version compatibility

| Component | Version |
|-----------|---------|
| QGIS | 4.0.3-Norrköping (tested); minimum 4.0 required |
| marimo | 0.23.9 (tested); any recent release should work |
| Python | Whatever interpreter QGIS runs on (3.12.13 / OSGeo4W on the Windows test machine). The plugin derives it live — nothing to pin. |
| Platform | Windows (QGIS 4 / OSGeo4W) and Linux — tested and working |

The QGIS plugin (`plugin/`) declares `qgisMinimumVersion=4.0` in `metadata.txt`. It has not been tested against QGIS 3.x; the 4.x PyQGIS API is assumed throughout.

**Videos about Marimo**
* [Marimo Overview](https://youtu.be/3N6lInzq5MI?si=l6BnT-hA2vuTkPgV)
* [All Marimo Videos](https://www.youtube.com/@marimo-team/videos)
* [Marimo + Quarto for publications](https://youtu.be/scuGmtv81S0?si=qVcCK49GMDqqOH8k)

This repository contains working notebooks and a setup guide for the combination of:

- **QGIS 4** spatial operations (vector layers, geodesic distance, coordinate reference systems)
- **Pandas** tabular analysis
- **marimo** reactive, browser-based Python notebooks

## What's in this repo

### Notebooks (`.py` files)

marimo notebooks are plain Python files — not JSON, not `.ipynb`. Each cell is
a decorated function; marimo reads the function signatures to build a dependency
graph and re-runs only the cells whose inputs changed. Because they're plain
Python, they diff cleanly in git and run equally well as scripts or in the
browser.

| File | What it does |
|------|-------------|
| `example/simple_marimo_qgis.py` | Minimal QGIS + marimo demo — best starting point, extensively commented |
| `example/gpkg_summary.py` | Full GeoPackage inventory, population trends, road network length |
| `example/processing_demo.py` | QGIS Processing algorithms — reactive buffer/dissolve, parameter inspector, capabilities reference |
| `example/live_layers.py` | **Live bridge (experimental):** lists the layers in your *running* QGIS project and pulls one into a GeoDataFrame — falls back to headless when run standalone |
| `notebooks/stations_analysis.py` | Geodesic distance matrix between weather stations, Pandas nearest-neighbour analysis |
| `notebooks/qgis_test.py` | Smoke test — confirms QGIS version and Python bindings |
| `notebooks/marimo_tutorial.py` | marimo feature tour with no QGIS dependency (UI elements, exports, reactivity) |

### Sample data (`.gpkg` files)

[GeoPackage](https://www.geopackage.org/) is an open, SQLite-based format that
stores vector layers, attributes, and metadata in a single file — no shapefile
sidecar files, no proprietary format. QGIS reads and writes it natively.

| File | Contents |
|------|----------|
| `example/example.gpkg` | 20 layers covering Youngstown, NY: buildings, streets, culverts, hydrology, land cover, parcels, population boundaries — three CRS (EPSG:26918, 4269, 4326) |
| `notebooks/stations.gpkg` | CWOP weather station locations in Maine, USA (points, EPSG:4326) |

---

## Example notebooks

`example/simple_marimo_qgis.py` is the recommended starting point — a minimal,
extensively-commented notebook that opens `example.gpkg`, filters building polygons,
and sums their geodesic area with `QgsDistanceArea`.

`example/gpkg_summary.py` explores a 20-layer GeoPackage (Youngstown NY area, three
CRS: EPSG:26918, EPSG:4269, EPSG:4326), builds a layer inventory using
`QgsProviderRegistry.querySublayers()`, extracts decennial population data, and
computes total road network length — all displayed as interactive marimo tables.

`notebooks/stations_analysis.py` loads CWOP weather stations from a GeoPackage, computes a
geodesic distance matrix using `QgsDistanceArea`, and analyses closest/farthest pairs
and per-station nearest neighbours with Pandas.

---

## Quick start

The intended workflow is: **install the plugin, install marimo into QGIS's
Python (the plugin offers to do this for you), then launch notebooks from the
dock.** No separate virtualenv, no `uv`, and no version pinning are required —
notebooks run on QGIS's own interpreter.

### 1. Install QGIS 4

Follow the [official QGIS installation guide](https://qgis.org/download/) for
your platform (OSGeo4W on Windows; the QGIS apt repository on Ubuntu).

### 2. Install the plugin

Download `marimo_launcher.zip` from the [latest release](https://github.com/johnzastrow/marimo-qgis/releases/latest)
(or build it yourself with `make package`), then in QGIS:

**Plugins ▸ Manage and Install Plugins ▸ Install from ZIP**

The QGIS plugin folder is named `marimo_launcher`. (QGIS 4 uses its own profile
tree — e.g. on Windows `…\AppData\Roaming\QGIS\QGIS4\profiles\default\python\plugins\`.)

### 3. Install marimo into QGIS's Python

Notebooks run on the interpreter QGIS itself uses, so **marimo must be installed
into that interpreter** (not into a separate venv). The easiest way: open the
dock and try to launch a notebook — if marimo is missing, the plugin pops a
dialog offering to run `python -m pip install marimo` into the correct
interpreter for you. Click **Yes** and re-launch once it finishes.

This also makes QGIS Python upgrades graceful: a new QGIS Python has a fresh
site-packages with no marimo, and the plugin simply offers to reinstall.

To install it manually instead, see
[Installing marimo into QGIS's Python](#installing-marimo-into-qgiss-python) below.

### 4. Launch a notebook

Click the **marimo toolbar button** to open the dock, then:

- **Setup tab** — review the environment report (QGIS / Python / GDAL / PROJ /
  GEOS / Qt versions, installed packages, CLI tools) and **Download examples…**
  to fetch this repo's `example/` and `notebooks/` folders into a folder you
  choose.
- **Browse tab** — point at a folder, pick a `.py` notebook, and launch it. Your
  browser opens automatically and the notebook gets a live bridge to the running
  QGIS project.
- **Running tab** — the notebooks launched this session, with **Stop**.

Every launch writes the notebook's stdout/stderr to a log file under
`%TEMP%\marimo_qgis_logs\<notebook>.log` (Windows) or the OS temp dir equivalent.
The flashing console window is suppressed. If a launched notebook dies within a
few seconds of starting, the dock shows a dialog with the last lines of that log
so the error isn't lost.

### Running notebooks manually (optional)

You normally launch from the dock, but you can run the same command yourself
using QGIS's interpreter:

```bash
# <qgis_python> is the interpreter QGIS runs on — see the Setup tab's report.
# Windows (OSGeo4W), via the QGIS Python launcher:
& cmd /c "C:\OSGeo4W\bin\python-qgis.bat -m marimo edit example\simple_marimo_qgis.py"

# Linux:
<qgis_python> -m marimo edit example/simple_marimo_qgis.py
<qgis_python> -m marimo run example/gpkg_summary.py
<qgis_python> -m marimo export html example/gpkg_summary.py -o summary.html
```

> **Note on `uv` (optional, dev-only):** `uv` is **not** required to run
> notebooks from the plugin. The `pyproject.toml`/`uv` workflow is still a fine
> way to *develop* notebooks outside QGIS, but the plugin launch path no longer
> uses it.

---

## Installing marimo into QGIS's Python

marimo and any library a notebook imports must live in **QGIS's own
interpreter** (the same one the Setup tab reports). The plugin can do this for
you (Step 3 above); to install manually:

### Windows (OSGeo4W)

```powershell
& cmd /c "C:\OSGeo4W\bin\python-qgis.bat -m pip install marimo"
```

`pip install` into the OSGeo4W Python works directly.

### Linux / macOS

The system or bundle Python QGIS uses is often **externally managed** (PEP 668)
or read-only, so a plain `pip install` may be refused. In that case install into
the per-user site with `--user`:

```bash
<qgis_python> -m pip install --user marimo
```

(Some distributions prefer you install marimo from a system package instead.)

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
notebooks launched from inside a live QGIS session (the plugin's launcher, which
does not force `offscreen`) correctly inherit the real display platform.

### Do not use PEP 723 inline script metadata in QGIS notebooks

When a notebook is launched through `uv run` (the optional dev workflow), marimo
detects any `# /// script` block and **auto-sandboxes** the kernel — creating a
fresh isolated environment with no access to QGIS's site-packages. That
environment has no PyQt6, so every `from qgis.core import ...` fails with
`ModuleNotFoundError: No module named 'PyQt6'`.

The plugin avoids this entirely by launching on QGIS's own interpreter rather
than via `uv run`. Still, **do not add** `# /// script` blocks to QGIS notebooks
so they stay safe under either launch method — rely on whatever is installed in
QGIS's Python instead.

PEP 723 headers are safe in notebooks with **no QGIS dependency** (e.g.
`notebooks/marimo_tutorial.py`), where the isolated environment has everything it needs.

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

## QGIS plugin

`plugin/` is a QGIS 4 plugin that adds a **marimo toolbar button**. Clicking it
opens the **marimo manager panel** (a dock) with three tabs — **Setup**,
**Browse**, and **Running** — where you check the environment, launch any
notebook in your browser, and stop running ones. Notebooks run on QGIS's own
Python interpreter (`<qgis_python> -m marimo …`, discovered live), so they are
ABI-compatible with PyQGIS and can `import qgis` natively. Launched notebooks
also get a live HTTP **bridge** to the running QGIS project — read layers, the
current selection and canvas extent, and push results back as new layers —
through the bundled `qgis_bridge` client. Without the plugin the same notebooks
fall back to a headless `QgsApplication`.

The **Setup tab** is the first tab. It shows an environment report (QGIS,
Python interpreter/version/prefix, GDAL/PROJ/GEOS/SpatiaLite/Qt versions, marimo
and uv status, a table of relevant Python packages, and detected CLI utilities
such as `gdalinfo`, `ogr2ogr`, `spatialite`). Buttons let you **Refresh report**,
**Save report as…** (Markdown), and **Download examples…** (fetches the repo's
`example/` and `notebooks/` folders from GitHub into a folder you choose).

### Install from ZIP (recommended)

Download `marimo_launcher.zip` from the [latest release](https://github.com/johnzastrow/marimo-qgis/releases/latest)
(or build it with `make package`), then in QGIS:

**Plugins ▸ Manage and Install Plugins ▸ Install from ZIP**

The plugin installs under the folder name `marimo_launcher`. QGIS 4 keeps its
plugins in a QGIS4-specific profile tree:

| Platform | Plugin folder |
|----------|---------------|
| Windows | `…\AppData\Roaming\QGIS\QGIS4\profiles\default\python\plugins\marimo_launcher` |
| Linux | `~/.local/share/QGIS/QGIS4/profiles/default/python/plugins/marimo_launcher` |
| macOS | `~/Library/Application Support/QGIS/QGIS4/profiles/default/python/plugins/marimo_launcher` |

### Install from source (development)

Symlink `plugin/` into the QGIS plugins directory above. The link name
(`marimo_launcher`) becomes the Python package name:

```bash
# Linux example
ln -s /path/to/marimo-qgis/plugin \
      ~/.local/share/QGIS/QGIS4/profiles/default/python/plugins/marimo_launcher
```

```powershell
# Windows example (run an elevated PowerShell, or enable Developer Mode)
New-Item -ItemType SymbolicLink `
  -Path "$env:APPDATA\QGIS\QGIS4\profiles\default\python\plugins\marimo_launcher" `
  -Target "C:\path\to\marimo-qgis\plugin"
```

Then: **Plugins ▸ Manage and Install Plugins ▸ Installed** — enable **marimo
Launcher**. Restart QGIS after pulling changes that add new sub-modules (a
running plugin keeps the old code in memory). The marimo button then appears on
the toolbar and under **Plugins ▸ marimo**.

### Build the ZIP yourself

```bash
make package   # → marimo_launcher.zip  (bundles the whole plugin/ tree + LICENSE)
```

### How it works

| Path | Role |
|------|------|
| `plugin/__init__.py` | `classFactory()` entry point — QGIS loads this first |
| `plugin/plugin.py` | `MarimoLauncherPlugin` — starts the bridge, adds the toolbar button + dock |
| `plugin/bridge/` | localhost HTTP bridge to the live project (`auth`, `api`, `server`, `convert`) |
| `plugin/ui/dock.py` | `MarimoManagerDock` — Setup/Browse/Running tabs; preflights marimo and surfaces launch logs |
| `plugin/ui/process.py` | `MarimoProcessManager` — launches `<qgis_python> -m marimo` with the bridge env injected, logs to `%TEMP%\marimo_qgis_logs\` |
| `plugin/environment.py` | `report_markdown()` env report + `download_examples()` for the Setup tab |
| `plugin/runtime.py` | bridge handle + `qgis_python()` / `pyqgis_dir()` interpreter resolution |
| `qgis_bridge/` | notebook-side client (QGIS-free): `QgisBridge` + `HeadlessQGIS` |

The standalone `processing/launch_marimo.py` script remains available for manual
addition to the Processing Toolbox if you prefer launching without the plugin
(note: it does not connect the bridge).

---

## Project structure

```
marimo-qgis/
├── qgis-env.sh                   # (optional, dev) detect QGIS's Python + build a venv for editing notebooks outside QGIS
├── notebooks/
│   ├── stations_analysis.py      # QGIS distance matrix + Pandas analysis
│   ├── stations.gpkg             # sample data: CWOP weather stations, Maine
│   ├── qgis_test.py              # minimal: confirms QGIS version
│   └── marimo_tutorial.py        # marimo feature tour (no QGIS dependency)
├── example/
│   ├── example.gpkg              # Youngstown NY area: 20-layer GeoPackage
│   ├── gpkg_summary.py           # layer inventory, population trends, road length
│   ├── simple_marimo_qgis.py     # minimal QGIS+marimo demo, extensively commented
│   ├── processing_demo.py        # Processing algorithms, parameter inspector
│   └── INSTRUCTIONS.md           # quick start for this example
├── plugin/                       # QGIS 4 plugin (toolbar button + live bridge)
│   ├── __init__.py               # classFactory() entry point
│   ├── metadata.txt              # plugin name, version, QGIS minimum version
│   ├── plugin.py                 # plugin class — starts bridge, adds toolbar/dock
│   ├── runtime.py                # bridge handle + qgis_python()/pyqgis_dir() interpreter resolution
│   ├── environment.py            # Setup-tab env report + example downloader
│   ├── icons/marimoqgis.svg      # toolbar icon
│   ├── bridge/                   # localhost HTTP bridge (auth, api, server, convert)
│   └── ui/                       # dock widget (Setup/Browse/Running) + process manager
├── qgis_bridge/                  # notebook-side bridge client (no QGIS dependency)
├── processing/
│   └── launch_marimo.py          # standalone Processing script (no plugin needed)
├── pyproject.toml                # project metadata and dependencies
├── TROUBLESHOOTING.md            # debugging guide
└── MARIMO_QGIS.md                # additional setup notes
```

---

## Platform support

| Platform | Status |
|----------|--------|
| Windows (QGIS 4 / OSGeo4W) | Tested and working |
| Linux (Ubuntu, QGIS apt repo) | Tested and working |
| macOS | Should work (same QGIS-own-interpreter model); not yet verified |

The plugin runs notebooks on QGIS's own interpreter on every platform, so there
is no separate Python/Qt6 to locate or pin — the historical Windows/macOS
"finding the bindings" problem does not arise for the plugin launch path. The
manual standalone instructions below remain useful if you run notebooks outside
the plugin.

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
well-known path (`/usr/share/qgis/python`). `./qgis-env.sh setup` automates the Linux
case end to end (and `./qgis-env.sh doctor` diagnoses a broken environment).

On Windows and macOS, **QGIS bundles its own Python, Qt6, and PyQt6 inside the
application**. There is no system PyQt6 to inherit, and `--system-site-packages` does
not help. The same principle still applies, though: build the environment around
**QGIS's own bundled interpreter** rather than pinning a separate Python version —
that is exactly what the platform-specific instructions below do. (`qgis-env.sh` is
currently Linux-only; the Windows/macOS steps remain manual.)

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

- The console window flashes and closes / `AssertionError: SRE module mismatch` —
  the old `uv run` failure mode, now fixed by running on QGIS's own interpreter
- A launched notebook exits immediately — check `%TEMP%\marimo_qgis_logs\`
- `ImportError: libQt6Network.so.6: undefined symbol` — a PyQt6 version conflict
  in a manually-built venv (only affects the optional standalone/`uv` workflow)
- Cells showing no output in `marimo edit` — stale session cache

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE).

Copyright (C) 2026 John Zastrow. GPLv3 is used for consistency with the QGIS
ecosystem: this plugin imports PyQGIS (a GPL library), and the sibling
`qgis-light` project is GPLv3 as well.
