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
    ./marimo-qgis edit example/gpkg_summary.py

## What it shows

- **Layer inventory** — all 9 layers in `example.gpkg` with geometry type, feature count, CRS, and extent
- **Population trends** — Youngstown NY decade-over-decade population change 1990–2020
- **Spatial analysis** — total road length computed with `QgsDistanceArea`
