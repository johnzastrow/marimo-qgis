# Design: Stations Distance Analysis Notebook

**Date:** 2026-03-27
**Project:** marimo_qgis
**File to create/replace:** `stations_analysis.py`

---

## Goal

Demonstrate the full marimo + PyQGIS integration pipeline by loading `stations.gpkg`
(9 CWOP weather stations in Maine), computing a geodesic distance matrix using
`QgsDistanceArea`, and analysing the results with Pandas — all inside a single marimo
notebook with rich Markdown explanations throughout.

This notebook is a **proof-of-concept pipeline** whose cell boundaries are designed to
mirror how QGIS Processing Toolbox results will slot in at the `dist_matrix` step in
future work.

---

## Data

- **File:** `stations.gpkg` (in project root)
- **Layer:** single point layer, EPSG:4326
- **Features:** 9 stations, fields confirmed in file: `site`, `lat`, `long`, `elev_m`, `ned_m`, `city`, `county`, `state`, `status`, `station_type`, `equipment`, `software`, `operator`, `forecast_office`, `timezone`, `url`, `notes`, `ts`

---

## Architecture

### Cell responsibilities (in dependency order)

| Cell | Inputs | Exports | Responsibility |
|------|--------|---------|----------------|
| `setup` | — | `mo` | `import marimo as mo; return (mo,)` |
| `qgis_init` | — | `qgs`, `Qgis`, `QgsApplication`, `QgsVectorLayer`, `QgsDistanceArea`, `QgsPointXY`, `QgsProject` | Initialise headless `QgsApplication([], False)` + `initQgis()`, set `QT_QPA_PLATFORM=offscreen`, import all needed QGIS classes from `qgis.core` |
| `load_layer` | `QgsVectorLayer` | `layer` | Load `stations.gpkg` via `QgsVectorLayer(..., 'ogr')`, assert `layer.isValid()` |
| `to_dataframe` | `layer`, `mo` | `df`, `pd` | `import pandas as pd` and export `pd`; iterate `QgsFeature` objects → DataFrame with columns `site`, `city`, `county`, `lat`, `long`, `elev_m`, `status`; display preview with `mo.ui.table` |
| `dist_matrix` | `layer`, `QgsDistanceArea`, `QgsPointXY`, `QgsProject`, `mo` | `dist_df` | Compute N×N geodesic distance matrix (km); display as `mo.ui.table(dist_df.round(2))` |
| `analysis` | `dist_df`, `pd`, `mo` | — | Closest pair, farthest pair, per-station nearest neighbour table (`station`, `nearest`, `distance_km`), summary stats; `import numpy as np` locally; `mo.md` summary card |

### Separation of concerns

- **PyQGIS cells** (`qgis_init`, `load_layer`, `dist_matrix`): own all spatial logic
- **Pandas cells** (`to_dataframe`, `analysis`): own all tabular/statistical logic
- **Marimo display**: `mo.ui.table()` for interactive tables, `mo.md()` for narrative

This boundary is intentional: when a Processing Toolbox step replaces `dist_matrix` in
future, only that one cell changes.

---

## PyQGIS Distance Computation

```python
da = QgsDistanceArea()
da.setEllipsoid("WGS84")
da.setSourceCrs(layer.crs(), QgsProject.instance().transformContext())
# measureLine returns metres; divide by 1000 for km
distance_km = da.measureLine(QgsPointXY(lon1, lat1), QgsPointXY(lon2, lat2)) / 1000
```

- **Must call `setSourceCrs`** — without it, `QgsDistanceArea` may silently fall back to planar (Cartesian) distance on some QGIS builds even with `setEllipsoid` set
- Geodesic (ellipsoidal) distances, not Euclidean
- Output: symmetric N×N DataFrame with station `site` codes as index and columns
- 9 stations → 36 unique pairs

---

## Pandas Analysis

From `dist_df` (N×N, diagonal = 0):

```python
import numpy as np

# Closest pair — mask diagonal, find min
_masked = dist_df.replace(0, float("inf"))
closest_pair = _masked.stack().idxmin()   # (row_label, col_label) tuple
closest_km   = _masked.stack().min()

# Farthest pair — stack upper triangle, find max
farthest_pair = dist_df.stack().idxmax()  # (row_label, col_label) tuple
farthest_km   = dist_df.stack().max()

# Per-station nearest neighbour table
nn = _masked.idxmin(axis=1).rename("nearest")
nn_dist = _masked.min(axis=1).rename("distance_km")
nn_df = pd.concat([nn, nn_dist], axis=1).reset_index(names="station")

# Summary stats over all unique pairs (upper triangle only)
_upper = dist_df.where(np.triu(np.ones(dist_df.shape, dtype=bool), k=1))
stats = _upper.stack().describe()
```

- Using `.stack().idxmax()` / `.stack().idxmin()` returns a `(row, col)` tuple — the full pair, not just one station name
- `numpy` needed for `np.triu` (upper-triangle mask to avoid double-counting pairs)

---

## Markdown cells

Every cell is preceded by a `mo.md()` cell explaining:
- What the cell does and why
- Which QGIS API is being used and what it returns
- What the Pandas operation means analytically
- How this step fits the larger pipeline

---

## Display

- Station metadata: `mo.ui.table(df[['site','city','county','elev_m','status']])`
- Distance matrix: `mo.ui.table(dist_df.round(2))` with site codes as headers
- Summary: `mo.md()` card with closest pair, farthest pair, mean distance
- Per-station nearest neighbour: `mo.ui.table()`

---

## Constraints

- Add to `pyproject.toml` dependencies and to the PEP 723 `# /// script` header in `stations_analysis.py`: `pandas` and `numpy` (no version pins needed)
- Install via `uv add pandas numpy` before running
- `QT_QPA_PLATFORM=offscreen` set inside `qgis_init` cell
- `PYTHONPATH=/usr/share/qgis/python` required at launch (via `marimo-qgis` wrapper)
- Run with: `./marimo-qgis edit stations_analysis.py`
- Verify with: `PYTHONPATH=/usr/share/qgis/python uv run marimo export html stations_analysis.py -o /tmp/out.html`

---

## Out of scope

- Map rendering / cartographic display (next milestone)
- Processing Toolbox integration (next milestone)
- More than 9 stations (current dataset)
