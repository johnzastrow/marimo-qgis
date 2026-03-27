# Stations Distance Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `stations_analysis.py` — a marimo notebook that loads `stations.gpkg` via PyQGIS, computes a full geodesic distance matrix with `QgsDistanceArea`, and analyses it with Pandas, with rich Markdown explanations in every cell.

**Architecture:** One marimo notebook file with 12 cells in strict dependency order: `setup → qgis_init → load_layer → to_dataframe → dist_matrix → analysis`, each preceded by a prose `mo.md()` cell. PyQGIS owns all spatial computation; Pandas owns all tabular analysis. The cell boundary between `dist_matrix` and `analysis` is intentionally clean to allow a future QGIS Processing Toolbox step to replace `dist_matrix` without touching anything else.

**Tech Stack:** Python 3.13, marimo 0.21.1, QGIS 4.0.0-Norrköping (`/usr/share/qgis/python`), pandas, numpy, uv

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `stations_analysis.py` | The complete notebook |
| Modify | `pyproject.toml` | Add `pandas` and `numpy` to dependencies |

The `marimo-qgis` wrapper script already sets `PYTHONPATH=/usr/share/qgis/python` and is how the notebook is launched.

---

## Verification command (used after every task)

```bash
PYTHONPATH=/usr/share/qgis/python uv run marimo export html stations_analysis.py -o /tmp/sa_test.html 2>&1
echo "Exit: $?"
```

Expected on success: `Exit: 0` with no `MarimoExceptionRaisedError` lines.

---

## Task 1: Add dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add pandas and numpy to pyproject.toml**

Open `pyproject.toml` and change the dependencies list:

```toml
[project]
name = "marimo-qgis"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "pandas",
    "numpy",
]
```

- [ ] **Step 2: Install dependencies**

```bash
cd /home/jcz/Github/marimo_qgis
uv sync
```

Expected: uv resolves and installs pandas and numpy into `.venv`.

- [ ] **Step 3: Verify import works**

```bash
uv run python -c "import pandas; import numpy; print('pandas', pandas.__version__, 'numpy', numpy.__version__)"
```

Expected: both version strings printed, no errors.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "feat: add pandas and numpy dependencies"
```

---

## Task 2: Create notebook scaffold (setup + qgis_init cells)

**Files:**
- Create: `stations_analysis.py`

- [ ] **Step 1: Create the file with PEP 723 header, setup cell, and qgis_init cell**

Write `stations_analysis.py` with the following content exactly:

```python
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


if __name__ == "__main__":
    app.run()
```

- [ ] **Step 2: Run lint check**

```bash
uv run marimo check stations_analysis.py
```

Expected: 0 errors (warnings about markdown indentation are acceptable).

- [ ] **Step 3: Verify scaffold executes**

```bash
PYTHONPATH=/usr/share/qgis/python uv run marimo export html stations_analysis.py -o /tmp/sa_test.html 2>&1
echo "Exit: $?"
```

Expected: `Exit: 0`, no `MarimoExceptionRaisedError`.

- [ ] **Step 4: Confirm QGIS version appears in output**

```bash
python3 -c "
import re, json
with open('/tmp/sa_test.html') as f: c = f.read()
matches = re.findall(r'text/markdown.*?(?=text/)', c, re.DOTALL)
print(len(matches), 'markdown outputs found')
print('Norrk' in c or '4.0.0' in c, '← QGIS version in output')
"
```

Expected: `True ← QGIS version in output`

- [ ] **Step 5: Commit**

```bash
git add stations_analysis.py
git commit -m "feat: add stations_analysis scaffold with QGIS init"
```

---

## Task 3: Load stations layer

**Files:**
- Modify: `stations_analysis.py` — add prose cell + `load_layer` cell before `if __name__`

- [ ] **Step 1: Add the prose cell**

Append before `if __name__ == "__main__":`:

```python
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
```

- [ ] **Step 2: Run lint check**

```bash
uv run marimo check stations_analysis.py
```

- [ ] **Step 3: Verify layer loads**

```bash
PYTHONPATH=/usr/share/qgis/python uv run marimo export html stations_analysis.py -o /tmp/sa_test.html 2>&1
echo "Exit: $?"
```

Expected: `Exit: 0`

- [ ] **Step 4: Commit**

```bash
git add stations_analysis.py
git commit -m "feat: add load_layer cell — opens stations.gpkg via QgsVectorLayer"
```

---

## Task 4: Convert layer to Pandas DataFrame

**Files:**
- Modify: `stations_analysis.py` — add prose cell + `to_dataframe` cell

- [ ] **Step 1: Add the prose cell**

```python
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
```

- [ ] **Step 2: Add the to_dataframe cell**

```python
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
```

- [ ] **Step 3: Run lint check**

```bash
uv run marimo check stations_analysis.py
```

- [ ] **Step 4: Verify table appears in export**

```bash
PYTHONPATH=/usr/share/qgis/python uv run marimo export html stations_analysis.py -o /tmp/sa_test.html 2>&1
echo "Exit: $?"
python3 -c "
with open('/tmp/sa_test.html') as f: c = f.read()
# Check station IDs appear
for sid in ['E1248', 'E4279', 'E4229']:
    print(sid, '→', sid in c)
"
```

Expected: all three site IDs found as `True`.

- [ ] **Step 5: Commit**

```bash
git add stations_analysis.py
git commit -m "feat: add to_dataframe cell — QgsFeature iterator → pandas DataFrame"
```

---

## Task 5: Compute geodesic distance matrix

**Files:**
- Modify: `stations_analysis.py` — add prose cell + `dist_matrix` cell

This is the core PyQGIS integration cell. Read it carefully before implementing.

- [ ] **Step 1: Add the prose cell**

```python
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
```python
da = QgsDistanceArea()
da.setEllipsoid("WGS84")           # Use the WGS84 ellipsoid model
da.setSourceCrs(crs, context)      # Tells QGIS the input CRS so it can transform
                                    # correctly; without this it may fall back to
                                    # planar (Euclidean) distance silently
```

`measureLine(p1, p2)` returns the geodesic distance in **metres**. We divide by 1000
for kilometres.

The result is a symmetric N×N DataFrame with station `site` codes as both index and
columns. The diagonal is 0 (distance from a station to itself).
    """)
    return
```

- [ ] **Step 2: Add the dist_matrix cell**

```python
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
```

- [ ] **Step 3: Run lint check**

```bash
uv run marimo check stations_analysis.py
```

- [ ] **Step 4: Verify matrix appears and values are plausible**

```bash
PYTHONPATH=/usr/share/qgis/python uv run marimo export html stations_analysis.py -o /tmp/sa_test.html 2>&1
echo "Exit: $?"
```

Expected: `Exit: 0`. Then spot-check a known distance:

```bash
PYTHONPATH=/usr/share/qgis/python uv run python -c "
import sys, os
sys.path.insert(0, '/usr/share/qgis/python')
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from qgis.core import QgsApplication, QgsDistanceArea, QgsPointXY, QgsVectorLayer, QgsProject
qgs = QgsApplication([], False); qgs.initQgis()
layer = QgsVectorLayer('stations.gpkg', 's', 'ogr')
da = QgsDistanceArea()
da.setEllipsoid('WGS84')
da.setSourceCrs(layer.crs(), QgsProject.instance().transformContext())
# E1248 (43.8075, -70.2462) to E4279 (43.9397, -70.3468)
d = da.measureLine(QgsPointXY(-70.2462, 43.8075), QgsPointXY(-70.3468, 43.9397)) / 1000
print(f'E1248→E4279: {d:.2f} km  (expect ~17-19 km for stations ~1.3° apart in Maine)')
" 2>/dev/null
```

Expected: a distance in the 15–25 km range (these are nearby Maine stations).

- [ ] **Step 5: Commit**

```bash
git add stations_analysis.py
git commit -m "feat: add dist_matrix cell — QgsDistanceArea geodesic N×N km matrix"
```

---

## Task 6: Pandas analysis and summary display

**Files:**
- Modify: `stations_analysis.py` — add prose cell + `analysis` cell

- [ ] **Step 1: Add the prose cell**

```python
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
```

- [ ] **Step 2: Add the analysis cell**

```python
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
```

- [ ] **Step 3: Run lint check**

```bash
uv run marimo check stations_analysis.py
```

- [ ] **Step 4: Verify full notebook executes and results are correct**

```bash
PYTHONPATH=/usr/share/qgis/python uv run marimo export html stations_analysis.py -o /tmp/sa_test.html 2>&1
echo "Exit: $?"
```

Expected: `Exit: 0`, no `MarimoExceptionRaisedError`.

Then confirm the result card is present:

```bash
python3 -c "
import re
with open('/tmp/sa_test.html') as f: c = f.read()
print('Closest pair found:', 'Closest pair' in c)
print('Farthest pair found:', 'Farthest pair' in c)
print('Nearest neighbour table found:', 'nearest' in c.lower())
# Check distance values look sensible (Maine stations: 10-100 km range)
nums = re.findall(r'(\d+\.\d+) km', c)
if nums:
    vals = [float(n) for n in nums]
    print(f'Distance values in output: {sorted(set(vals))[:8]}')
    print(f'All in 5-150 km range: {all(5 < v < 150 for v in vals)}')
"
```

- [ ] **Step 5: Commit**

```bash
git add stations_analysis.py
git commit -m "feat: add analysis cell — closest/farthest pairs, nearest neighbour table, summary stats"
```

---

## Task 7: Final polish and CLAUDE.md update

**Files:**
- Modify: `stations_analysis.py` — add closing markdown cell
- Modify: `CLAUDE.md` — document new notebook

- [ ] **Step 1: Add a closing context cell**

Before `if __name__ == "__main__":`, add:

```python
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
```

- [ ] **Step 2: Update CLAUDE.md**

In the `Key Files` section, add:
```
- `stations_analysis.py` — Distance analysis notebook: loads stations.gpkg, QgsDistanceArea geodesic matrix, Pandas nearest-neighbour analysis
```

- [ ] **Step 3: Final verification**

```bash
uv run marimo check stations_analysis.py
PYTHONPATH=/usr/share/qgis/python uv run marimo export html stations_analysis.py -o /tmp/sa_final.html 2>&1
echo "Exit: $?"
```

Expected: `Exit: 0`.

- [ ] **Step 4: Final commit**

```bash
git add stations_analysis.py CLAUDE.md
git commit -m "feat: complete stations distance analysis notebook

- 12 cells: setup, qgis_init, env display, load_layer, to_dataframe,
  dist_matrix, analysis, closing context (each preceded by prose md cell)
- QgsDistanceArea with setSourceCrs for true geodesic km distances
- Pandas closest/farthest pair via .stack().idxmax(), nearest neighbour table
- Rich markdown explanations throughout

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```
