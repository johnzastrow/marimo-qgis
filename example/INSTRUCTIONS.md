# GeoPackage Summary Example

## Requirements

| Requirement | Version |
|-------------|---------|
| QGIS | 4.x |
| Python | whatever QGIS runs on (the plugin uses it automatically) |
| marimo | installed into QGIS's Python (the dock offers to do this) |

## Quick Start

The easy way: open the **marimo** dock in QGIS, go to the **Browse** tab, point
it at this `example/` folder, and launch `gpkg_summary.py`. Notebooks run on
QGIS's own Python interpreter, so there is no venv to build. If marimo is not yet
installed in QGIS's Python, the dock prompts to install it — accept and re-launch.

To run it manually instead, use QGIS's interpreter:

    # Windows (OSGeo4W)
    & cmd /c "C:\OSGeo4W\bin\python-qgis.bat -m marimo edit example\gpkg_summary.py"

    # Linux / macOS  (<qgis_python> = the path shown on the dock's Setup tab)
    <qgis_python> -m marimo edit example/gpkg_summary.py

Each notebook's QGIS init cell sets `QT_QPA_PLATFORM=offscreen` before
`QgsApplication` is created — the only point at which Qt reads it. (When launched
from the dock, the plugin also puts the PyQGIS bindings on `PYTHONPATH`, so
`import qgis` works without editing `sys.path`.)

## What it shows

- **Layer inventory** — all 20 layers in `example.gpkg` with geometry type, feature count, CRS, and extent
- **Population trends** — Youngstown NY decade-over-decade population change 1990–2020
- **Spatial analysis** — total road length computed with `QgsDistanceArea`

## Notebooks in this directory

| Notebook | Description |
|----------|-------------|
| `gpkg_summary.py` | Full GeoPackage inventory, population trends, road length |
| `simple_marimo_qgis.py` | Minimal example — building footprint area, extensively commented |
