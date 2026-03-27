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


@app.cell
def _(mo):
    mo.md("""
## Step 3 — Geodesic distance matrix via QgsDistanceArea

`QgsDistanceArea` is QGIS's geodesic measurement engine. It computes distances on
the surface of an ellipsoid (in our case WGS84) rather than treating coordinates as
flat 2D numbers — which would be badly wrong at the latitudes and scales involved.

**Why geodesic matters here:**
Maine spans roughly 3° of longitude and 3° of latitude. A naive Euclidean distance
on raw lat/long coordinates would give results in degrees, not metres, and would not
account for the fact that a degree of longitude at 44°N is shorter than at the equator
(by a factor of cos(44°) ≈ 0.72). Geodesic computation handles all of this correctly.

**The three setup calls:**

- `da.setEllipsoid("WGS84")` — use the WGS84 ellipsoid model
- `da.setSourceCrs(crs, context)` — tells QGIS the input CRS so it can transform
  correctly; without this it may fall back to planar (Euclidean) distance silently

`measureLine(p1, p2)` returns the geodesic distance in **metres**. We divide by 1000
for kilometres.

The result is a symmetric N×N DataFrame with station `site` codes as both index and
columns. The diagonal is 0 (distance from a station to itself).
    """)
    return


@app.cell
def _(QgsDistanceArea, QgsPointXY, QgsProject, df, layer, mo, pd):
    _da = QgsDistanceArea()
    _da.setEllipsoid("WGS84")
    _da.setSourceCrs(layer.crs(), QgsProject.instance().transformContext())

    _sites = df["site"].tolist()
    _coords = {
        row["site"]: QgsPointXY(row["long"], row["lat"])
        for _, row in df.iterrows()
    }

    _matrix = {}
    for _s1 in _sites:
        _matrix[_s1] = {}
        for _s2 in _sites:
            _dist_m = _da.measureLine(_coords[_s1], _coords[_s2])
            _matrix[_s1][_s2] = round(_dist_m / 1000, 4)

    dist_df = pd.DataFrame(_matrix)

    # Assign the table to a variable, then leave it as the final bare expression
    # so marimo renders it. The return statement after exports dist_df to
    # downstream cells without affecting what is displayed.
    _table = mo.ui.table(dist_df.round(2))
    _table
    return (dist_df,)


@app.cell
def _(mo):
    mo.md("""
## Step 4 — Analysis with Pandas

Now that PyQGIS has done the spatial heavy lifting, Pandas takes over for the
analytical work.

**Closest and farthest pairs:**
We use `.stack()` to convert the N×N matrix into a Series of `(station_A, station_B)`
index pairs, then `.idxmin()` / `.idxmax()` to find the pair labels directly. This
gives us a `(row_label, col_label)` tuple — both station names — rather than just
one side of the pair.

The diagonal (self-distance = 0) is masked out before finding the minimum by replacing
zeros with `inf`.

**Per-station nearest neighbour:**
For each station we find the closest other station using `.idxmin(axis=1)` on the
masked matrix. This is a clean vector operation — no loops required.

**Summary statistics:**
We extract the upper triangle of the matrix (to avoid counting each pair twice) and
run Pandas `.describe()` to get count, mean, min, max, and quartiles across all 36
unique station-pair distances.
    """)
    return


@app.cell
def _(dist_df, mo, pd):
    import numpy as np

    # --- closest pair ---
    _masked = dist_df.replace(0, float("inf"))
    closest_pair = _masked.stack().idxmin()   # (site_A, site_B)
    closest_km   = _masked.stack().min()

    # --- farthest pair ---
    farthest_pair = dist_df.stack().idxmax()  # (site_A, site_B)
    farthest_km   = dist_df.stack().max()

    # --- per-station nearest neighbour ---
    _nn      = _masked.idxmin(axis=1).rename("nearest")
    _nn_dist = _masked.min(axis=1).rename("distance_km")
    nn_df    = pd.concat([_nn, _nn_dist.round(2)], axis=1).reset_index(names="station")

    # --- summary stats (upper triangle only — avoids double-counting) ---
    _upper = dist_df.where(np.triu(np.ones(dist_df.shape, dtype=bool), k=1))
    _stats = _upper.stack().describe().round(2)

    # Use mo.vstack to display both the summary card and the nearest-neighbour table
    # in one cell. In marimo only the last expression is rendered, so wrapping both
    # in mo.vstack is the correct way to show multiple display elements from one cell.
    _summary = mo.md(f"""
## Results

| Metric | Stations | Distance |
|--------|----------|----------|
| **Closest pair** | `{closest_pair[0]}` ↔ `{closest_pair[1]}` | **{closest_km:.2f} km** |
| **Farthest pair** | `{farthest_pair[0]}` ↔ `{farthest_pair[1]}` | **{farthest_km:.2f} km** |
| Mean distance (all pairs) | — | {_stats['mean']:.2f} km |
| Std deviation | — | {_stats['std']:.2f} km |
| 25th percentile | — | {_stats['25%']:.2f} km |
| 75th percentile | — | {_stats['75%']:.2f} km |

### Nearest neighbour for each station
    """)
    _table = mo.ui.table(nn_df)
    mo.vstack([_summary, _table])
    return


@app.cell
def _(mo):
    mo.md("""
---

## What's next

This notebook establishes the core PyQGIS → Pandas → marimo pipeline. The next steps are:

- **QGIS Processing Toolbox** — replace the `dist_matrix` cell with a Processing
  algorithm (e.g., `qgis:distancematrix`) and pipe its output into the same Pandas
  analysis cells
- **Map display** — render station locations on a map using marimo's widget ecosystem
- **Statistical analysis** — bring in more weather observation data from the `weather`
  project and join it to this station geometry for spatial statistics

*Run this notebook interactively with: `./marimo-qgis edit stations_analysis.py`*
    """)
    return


if __name__ == "__main__":
    app.run()
