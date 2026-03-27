# Design: GeoPackage Summary Notebook

**Date:** 2026-03-27
**Status:** Approved

---

## Goal

A single self-contained marimo notebook (`example/gpkg_summary.py`) that gives a
reader a complete picture of `example/example.gpkg` using QGIS APIs throughout.
Three logical sections: layer inventory, population trend analysis, spatial analysis
placeholder. Concise markdown narrates each section.

---

## File Structure

```
example/
├── example.gpkg          # moved from repo root
├── gpkg_summary.py       # new notebook
└── INSTRUCTIONS.md       # concise requirements + quick start
```

The existing `marimo-qgis` wrapper at the repo root runs any notebook:
```bash
./marimo-qgis edit example/gpkg_summary.py
```

No new wrapper needed.

---

## Data

`example/example.gpkg` — EPSG:26918 (UTM zone 18N, metres), 9 layers:

| Layer | Geometry | Features |
|-------|----------|----------|
| town | MultiPolygon | 1 |
| ny_culverts | Point | 39 |
| ny_hydrolines | MultiLineString | 256 |
| ny_ytown_buildings | MultiPolygon | 646 |
| ny_ytown_streets | MultiLineString | 214 |
| ny_ytown_stateparks | MultiPolygon | 2 |
| ny_state_owned | MultiPolygon | 5 |
| ny_villages | MultiPolygon | 1 |
| ny_youngstown | MultiPolygon | 1 |

The `town` layer has population fields: `pop1990`, `pop2000`, `pop2010`, `pop2020`
plus name, county, area fields.

---

## Notebook Cell Plan

### Cell 1 — QGIS init

Same pattern as `stations_analysis.py`. Sets `sys.path`, `QT_QPA_PLATFORM=offscreen`,
initialises `QgsApplication([], False)`, calls `qgs.initQgis()`.

Returns: `Qgis, QgsApplication, QgsVectorLayer, QgsProject, qgs`

### Cell 2 — Intro markdown

One paragraph: what the notebook does, what the data is (Youngstown NY area,
9 layers, mixed geometry).

### Cell 3 — Enumerate layers → inventory DataFrame

Opens the GeoPackage with a probe layer, calls `dataProvider().subLayers()` to list
all layers. For each sublayer, opens it individually (`|layername=<name>`) and
extracts:

- `name` — layer name
- `geometry` — human-readable type from `QgsWkbTypes.displayString(layer.wkbType())`
- `features` — `layer.featureCount()`
- `crs` — `layer.crs().authid()`
- `extent` — formatted `layer.extent()` as "xmin, ymin → xmax, ymax" string

Builds a pandas DataFrame. Returns `gpkg_path`, `inv_df`.

### Cell 4 — Inventory display

Brief markdown header ("## Layer Inventory"), one sentence explaining what's shown,
then `mo.ui.table(inv_df)`.

### Cell 5 — Load town layer → population DataFrame

Opens `example.gpkg|layername=town`. Iterates features (just 1), extracts:
`name`, `county`, `pop1990`, `pop2000`, `pop2010`, `pop2020`, `calc_sq_mi`.

Builds a pandas DataFrame with those columns. Computes decade-over-decade change
columns:
- `Δ 90→00`, `Δ 00→10`, `Δ 10→20` (absolute)
- `% 90→00`, `% 00→10`, `% 10→20` (percentage, 1 decimal)

Returns `town_df`, `pop_df` (the change summary, one row per decade transition).

Uses only `QgsVectorLayer` — no Pandas-external computation needed for the
population extraction itself.

### Cell 6 — Population trends display

Markdown header + one sentence contextualising the data (Youngstown is a small
village in Niagara County NY). Then `mo.vstack` of:
- `mo.ui.table(town_df[display_cols])` — raw population by decade
- `mo.ui.table(pop_df)` — decade changes

### Cell 7 — Spatial analysis intro markdown

Short placeholder: "## Spatial Analysis" + one sentence noting this section will
grow. Keeps the notebook forward-looking.

### Cell 8 — Spatial analysis cell (placeholder)

A single working example to establish the pattern. Chosen because it uses
QGIS natively and produces a concrete number:

**Total road length**: iterate `ny_ytown_streets` features, sum
`QgsDistanceArea.measureLength(geom)` for each geometry (in metres, then convert
to km). Display as a `mo.stat` or inline markdown result.

This is intentionally minimal — one QGIS spatial measurement, clearly labelled, easy
to extend.

Returns: `road_km`

### Cell 9 — What's next markdown

2–3 bullets pointing toward obvious next analyses (building footprint areas, culvert
proximity to water, population density using town polygon area).

---

## QGIS APIs Used

| API | Purpose |
|-----|---------|
| `QgsApplication` | Initialise QGIS runtime |
| `QgsVectorLayer(path, name, "ogr")` | Open any OGR-supported format |
| `layer.dataProvider().subLayers()` | Enumerate layers in a GeoPackage |
| `QgsWkbTypes.displayString(wkbType)` | Human-readable geometry type name |
| `layer.extent()` → `QgsRectangle` | Bounding box of a layer |
| `layer.crs().authid()` | CRS identifier string |
| `layer.featureCount()` | Number of features |
| `layer.getFeatures()` | Iterate features |
| `QgsDistanceArea.measureLength(geom)` | Geodesic/planar length of a geometry |
| `QgsProject.instance().transformContext()` | CRS transform context for distance calc |

---

## INSTRUCTIONS.md Content

Concise — requirements table + 3-command quick start:

```
Requirements: QGIS 4, Python 3.13, uv
Quick start:
  uv venv --python 3.13 --system-site-packages
  uv pip install marimo pandas numpy
  ./marimo-qgis edit example/gpkg_summary.py   (from repo root)
```

---

## Out of Scope

- No map rendering (no QgsMapCanvas — headless only)
- No file writes or exports from within the notebook
- No `/// script` inline metadata (conflicts with system PyQt6)
- Spatial analysis section intentionally minimal; designed to be extended in a
  follow-up session
