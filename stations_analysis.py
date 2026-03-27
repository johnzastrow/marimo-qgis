# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "marimo",
#     "pandas",
#     "numpy",
# ]
# ///

import marimo

__generated_with = "0.21.1"

app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    mo.md("""
# QGIS + Marimo: Stations Distance Analysis

This notebook demonstrates the **PyQGIS + Pandas + marimo** integration pipeline using
a set of CWOP (Citizen Weather Observer Program) weather stations in Maine, USA.

## What we're doing

1. **Load** station locations from a GeoPackage file using PyQGIS
2. **Compute** geodesic distances between every pair of stations using QGIS's
   `QgsDistanceArea` engine (true ellipsoidal distances on the WGS84 globe, not flat-map approximations)
3. **Analyse** the distance matrix with Pandas to find closest/farthest pairs and
   per-station nearest neighbours
4. **Display** results as interactive tables and a summary card

## Why this architecture matters

Each cell has exactly one responsibility. The boundary between the QGIS distance
computation (`dist_matrix`) and the Pandas analysis (`analysis`) is intentionally clean:
in the next milestone, a QGIS Processing Toolbox algorithm will replace the distance
cell, and everything downstream will work unchanged.
    """)
    return


@app.cell
def _():
    import sys
    import os

    sys.path.insert(0, "/usr/share/qgis/python")

    # Prevent Qt from trying to connect to a display server.
    # Without this, QGIS raises a Qt platform error in headless environments.
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from qgis.core import (
        QgsApplication,
        Qgis,
        QgsVectorLayer,
        QgsDistanceArea,
        QgsPointXY,
        QgsProject,
    )

    # QgsApplication must be initialised before any other QGIS API call.
    # gui=False tells Qt not to create a window or event loop.
    qgs = QgsApplication([], False)
    qgs.initQgis()

    return Qgis, QgsApplication, QgsDistanceArea, QgsPointXY, QgsProject, QgsVectorLayer, qgs


@app.cell
def _(Qgis, mo):
    mo.md(f"""
## Environment

| Component | Value |
|-----------|-------|
| QGIS version | `{Qgis.version()}` |
| Release name | `{Qgis.releaseName()}` |

*QGIS is running headlessly — no GUI, no display connection required.*
    """)
    return


@app.cell
def _(mo):
    mo.md("""
## Step 1 — Load the station layer with PyQGIS

We use `QgsVectorLayer` to open `stations.gpkg`. This is the standard PyQGIS entry
point for vector data: it handles GeoPackage, Shapefile, PostGIS, and any other
OGR-supported format through a unified interface.

The `'ogr'` provider string tells QGIS to use the OGR/GDAL library for reading —
the same library that powers GDAL command-line tools. Under the hood, QGIS is calling
into the same C++ spatial library used by the desktop application.

`layer.isValid()` is the canonical QGIS check that the file opened successfully and
the geometry/attribute schema was parsed without errors. A layer can open without
raising a Python exception but still be invalid (e.g., corrupted geometry index),
so this check is essential.
    """)
    return


@app.cell
def _(QgsVectorLayer):
    # Use a hardcoded absolute path — pathlib.Path(__file__) raises NameError
    # inside a marimo cell function because __file__ is not in the cell's local scope.
    _gpkg = "/home/jcz/Github/marimo_qgis/stations.gpkg"
    layer = QgsVectorLayer(_gpkg, "stations", "ogr")

    assert layer.isValid(), f"Layer failed to load from {_gpkg}"

    return (layer,)


@app.cell
def _(mo):
    mo.md("""
## Step 2 — From QGIS features to a Pandas DataFrame

PyQGIS represents each row in the layer as a `QgsFeature` object. We iterate the
layer with `layer.getFeatures()` and pull the attributes we care about into a plain
Python dict, then hand the list of dicts to `pd.DataFrame`.

**Why Pandas here, not pure PyQGIS?**
QGIS is excellent at spatial operations — reprojection, distance, overlay, topology.
Pandas is excellent at tabular analysis — groupby, pivot, describe, merge. We use
each tool for what it is best at and convert at the boundary between the two worlds.

The fields we extract are:
- `site` — station identifier (used as the index in the distance matrix)
- `city`, `county` — human-readable location context
- `lat`, `long` — geographic coordinates (also stored in the point geometry, but
  easier to access from attributes for display purposes)
- `elev_m` — station elevation in metres above sea level
- `status` — whether the station is currently active
    """)
    return


@app.cell
def _(layer, mo):
    import pandas as pd

    _records = []
    for _feat in layer.getFeatures():
        _records.append({
            "site":    _feat["site"],
            "city":    _feat["city"],
            "county":  _feat["county"],
            "lat":     _feat["lat"],
            "long":    _feat["long"],
            "elev_m":  _feat["elev_m"],
            "status":  _feat["status"],
        })

    df = pd.DataFrame(_records)

    mo.ui.table(df[["site", "city", "county", "elev_m", "status"]])
    return df, pd


if __name__ == "__main__":
    app.run()
