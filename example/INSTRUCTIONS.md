# GeoPackage Summary Example

## Requirements

| Requirement | Version |
|-------------|---------|
| QGIS | 4.x |
| Python | 3.13 |
| uv | latest |

## Quick Start

From repo root:

    uv venv --python 3.13 --system-site-packages
    uv pip install marimo pandas numpy
    uv run marimo edit example/gpkg_summary.py

No wrapper script is needed. Each notebook's QGIS init cell adds the PyQGIS
bindings to `sys.path` and sets `QT_QPA_PLATFORM=offscreen` before
`QgsApplication` is created — the only point at which Qt reads those settings.

## What it shows

- **Layer inventory** — all 20 layers in `example.gpkg` with geometry type, feature count, CRS, and extent
- **Population trends** — Youngstown NY decade-over-decade population change 1990–2020
- **Spatial analysis** — total road length computed with `QgsDistanceArea`

## Notebooks in this directory

| Notebook | Description |
|----------|-------------|
| `gpkg_summary.py` | Full GeoPackage inventory, population trends, road length |
| `simple_marimo_qgis.py` | Minimal example — building footprint area, extensively commented |
