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
- **Features:** 9 stations, fields include `site`, `lat`, `long`, `elev_m`, `county`, `status`

---

## Architecture

### Cell responsibilities (in dependency order)

| Cell | Inputs | Exports | Responsibility |
|------|--------|---------|----------------|
| `setup` | — | `mo` | `import marimo as mo` |
| `qgis_init` | — | `qgs`, `Qgis`, `QgsApplication`, `QgsVectorLayer`, `QgsDistanceArea`, `QgsPointXY` | Initialise headless QgsApplication, import QGIS classes |
| `load_layer` | `qgs`, `QgsVectorLayer` | `layer` | Load stations.gpkg, assert `layer.isValid()` |
| `to_dataframe` | `layer`, `mo` | `df` | Iterate QgsFeature objects → pandas DataFrame; display preview table |
| `dist_matrix` | `layer`, `QgsDistanceArea`, `QgsPointXY`, `mo` | `dist_df` | Compute N×N geodesic distance matrix (km); display as mo.ui.table |
| `analysis` | `dist_df`, `mo` | — | Closest pair, farthest pair, mean/min/max distances; mo.md summary card |

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
# da.measureLine(QgsPointXY(lon1, lat1), QgsPointXY(lon2, lat2)) → metres
distance_km = da.measureLine(...) / 1000
```

- Geodesic (ellipsoidal) distances, not Euclidean
- Output: symmetric N×N DataFrame with station `site` codes as index and columns
- 9 stations → 36 unique pairs

---

## Pandas Analysis

From `dist_df`:
- **Closest pair**: `dist_df.replace(0, float('inf')).min().min()` + `idxmin()`
- **Farthest pair**: `dist_df.max().max()` + `idxmax()`
- **Per-station nearest neighbour**: for each station, the closest other station
- **Summary stats**: `dist_df.values[dist_df.values > 0]` flattened → `describe()`

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

- `pandas` must be added to `pyproject.toml` dependencies
- `QT_QPA_PLATFORM=offscreen` set in `qgis_init` cell
- `PYTHONPATH=/usr/share/qgis/python` required at launch (via `marimo-qgis` wrapper)
- Run with: `./marimo-qgis edit stations_analysis.py`
- Verify with: `PYTHONPATH=/usr/share/qgis/python uv run marimo export html stations_analysis.py`

---

## Out of scope

- Map rendering / cartographic display (next milestone)
- Processing Toolbox integration (next milestone)
- More than 9 stations (current dataset)
