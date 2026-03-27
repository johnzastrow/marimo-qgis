# GeoPackage Summary Notebook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `example/gpkg_summary.py`, a self-contained marimo notebook that summarises `example/example.gpkg` using QGIS APIs throughout, with layer inventory, population trends, and a spatial analysis example.

**Architecture:** Three logical sections — layer inventory (enumerate all 9 layers via `dataProvider().subLayers()`), population trends (load `town` layer, build decade-change DataFrame), spatial analysis (total road length via `QgsDistanceArea.measureLength`). Concise markdown narrates each section. No map rendering; headless QGIS only.

**Tech Stack:** Python 3.13, QGIS 4 (PyQGIS), marimo 0.21.1, pandas, uv + `--system-site-packages` venv

---

### Task 1: Create example/ directory structure and move example.gpkg

**Files:**
- Create: `example/` directory
- Move: `example.gpkg` → `example/example.gpkg`
- Create: `example/INSTRUCTIONS.md`

- [ ] **Step 1: Move the GeoPackage**

```bash
mkdir -p example
git mv example.gpkg example/example.gpkg
```

- [ ] **Step 2: Verify move**

```bash
ls -la example/
# Expected: example.gpkg listed
git status
# Expected: renamed: example.gpkg -> example/example.gpkg
```

- [ ] **Step 3: Create INSTRUCTIONS.md**

Create `example/INSTRUCTIONS.md` with this exact content:

```markdown
# GeoPackage Summary Example

## Requirements

| Requirement | Version |
|-------------|---------|
| QGIS | 4.x |
| Python | 3.13 |
| uv | latest |

## Quick Start

```bash
# From repo root:
uv venv --python 3.13 --system-site-packages
uv pip install marimo pandas numpy
./marimo-qgis edit example/gpkg_summary.py
```

## What it shows

- **Layer inventory** — all 9 layers in `example.gpkg` with geometry type, feature count, CRS, and extent
- **Population trends** — Youngstown NY decade-over-decade population change 1990–2020
- **Spatial analysis** — total road length computed with `QgsDistanceArea`
```

- [ ] **Step 4: Commit**

```bash
git add example/example.gpkg example/INSTRUCTIONS.md
git commit -m "feat: create example/ directory, move example.gpkg, add INSTRUCTIONS.md"
```

---

### Task 2: Create example/gpkg_summary.py — skeleton and QGIS init cell

**Files:**
- Create: `example/gpkg_summary.py`

- [ ] **Step 1: Write the notebook skeleton with Cell 1 (QGIS init)**

Create `example/gpkg_summary.py` with this content:

```python
import marimo

__generated_with = "0.21.1"

app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    import sys
    import os

    sys.path.insert(0, "/usr/share/qgis/python")

    # Belt-and-suspenders: the marimo-qgis wrapper sets QT_QPA_PLATFORM=offscreen
    # and QT_PLUGIN_PATH before Python starts so the spawn subprocess inherits
    # them. The setdefault here is a fallback for direct invocations.
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from qgis.core import (
        QgsApplication,
        Qgis,
        QgsVectorLayer,
        QgsProject,
        QgsWkbTypes,
        QgsDistanceArea,
    )

    qgs = QgsApplication([], False)
    qgs.initQgis()

    return Qgis, QgsApplication, QgsDistanceArea, QgsProject, QgsVectorLayer, QgsWkbTypes, qgs


if __name__ == "__main__":
    app.run()
```

- [ ] **Step 2: Verify it parses**

```bash
.venv/bin/python -c "import example.gpkg_summary" 2>&1 | head -5
# Or:
python -c "
import ast, sys
with open('example/gpkg_summary.py') as f:
    ast.parse(f.read())
print('OK')
"
```

Expected: `OK`

---

### Task 3: Add Cell 2 — Intro markdown

**Files:**
- Modify: `example/gpkg_summary.py`

- [ ] **Step 1: Insert Cell 2 before `if __name__`**

Add the following cell after the QGIS init cell and before `if __name__ == "__main__":`:

```python
@app.cell
def _(mo):
    mo.md("""
# GeoPackage Summary: Youngstown, NY

This notebook explores `example.gpkg`, a GeoPackage containing spatial data for
the Youngstown, New York area — a small village in Niagara County on Lake Ontario.

The file holds **9 layers** with mixed geometry types (points, lines, polygons) all
in EPSG:26918 (UTM zone 18N, metres). We use QGIS APIs throughout: layer enumeration,
feature iteration, geometry measurement — the same APIs used in the QGIS desktop
application, running headlessly here.
    """)
    return
```

---

### Task 4: Add Cells 3 & 4 — Layer inventory

**Files:**
- Modify: `example/gpkg_summary.py`

This is the most complex cell. `dataProvider().subLayers()` returns a list of
`"::"` delimited strings. For OGR/GeoPackage in QGIS 4 the format is:
`"layerId::layerName::featureCount::geometryType::tableName::geometryColumn"`

We parse index 1 for the name, then open each layer individually.

- [ ] **Step 1: Add Cell 3 — enumerate layers**

```python
@app.cell
def _(QgsVectorLayer, QgsWkbTypes):
    import os
    import pandas as pd

    _gpkg = os.path.join(os.getcwd(), "example", "example.gpkg")

    # Open a probe layer to call subLayers() — any layer name works here
    _probe = QgsVectorLayer(_gpkg, "probe", "ogr")
    assert _probe.isValid(), f"Could not open GeoPackage: {_gpkg}"

    _rows = []
    for _sub in _probe.dataProvider().subLayers():
        # Format: "layerId::layerName::featureCount::geometryType::tableName::geomCol"
        _parts = _sub.split("::")
        _name = _parts[1]

        _lyr = QgsVectorLayer(f"{_gpkg}|layername={_name}", _name, "ogr")
        if not _lyr.isValid():
            continue

        _ext = _lyr.extent()
        _rows.append({
            "name":     _name,
            "geometry": QgsWkbTypes.displayString(_lyr.wkbType()),
            "features": _lyr.featureCount(),
            "crs":      _lyr.crs().authid(),
            "extent":   (
                f"{_ext.xMinimum():.0f}, {_ext.yMinimum():.0f}"
                f" → {_ext.xMaximum():.0f}, {_ext.yMaximum():.0f}"
            ),
        })

    gpkg_path = _gpkg
    inv_df = pd.DataFrame(_rows)

    return gpkg_path, inv_df, pd
```

- [ ] **Step 2: Add Cell 4 — display inventory**

```python
@app.cell
def _(inv_df, mo):
    mo.vstack([
        mo.md("""
## Layer Inventory

The table below lists every layer in the GeoPackage. All layers share EPSG:26918
(UTM zone 18N, metres), so extents are in metres east/north.
        """),
        mo.ui.table(inv_df),
    ])
    return
```

---

### Task 5: Add Cells 5 & 6 — Population trends

**Files:**
- Modify: `example/gpkg_summary.py`

The `town` layer has one feature with fields: `name`, `county`, `pop1990`,
`pop2000`, `pop2010`, `pop2020`, `calc_sq_mi`. We build two DataFrames:
`town_df` (raw values) and `pop_df` (decade-over-decade changes).

- [ ] **Step 1: Add Cell 5 — load town layer and build DataFrames**

```python
@app.cell
def _(QgsVectorLayer, gpkg_path, pd):
    _lyr = QgsVectorLayer(f"{gpkg_path}|layername=town", "town", "ogr")
    assert _lyr.isValid(), "Could not open town layer"

    _records = []
    for _feat in _lyr.getFeatures():
        _records.append({
            "name":       _feat["name"],
            "county":     _feat["county"],
            "pop1990":    int(_feat["pop1990"]),
            "pop2000":    int(_feat["pop2000"]),
            "pop2010":    int(_feat["pop2010"]),
            "pop2020":    int(_feat["pop2020"]),
            "area_sq_mi": round(float(_feat["calc_sq_mi"]), 2),
        })

    town_df = pd.DataFrame(_records)

    # Decade-over-decade change summary
    _decades = [("1990", "2000"), ("2000", "2010"), ("2010", "2020")]
    _change_rows = []
    for _from, _to in _decades:
        _p0 = town_df[f"pop{_from}"].iloc[0]
        _p1 = town_df[f"pop{_to}"].iloc[0]
        _delta = _p1 - _p0
        _pct   = round((_delta / _p0) * 100, 1) if _p0 else 0.0
        _change_rows.append({
            "decade":    f"{_from}→{_to}",
            "pop_start": _p0,
            "pop_end":   _p1,
            f"Δ pop":    _delta,
            "% change":  _pct,
        })

    pop_df = pd.DataFrame(_change_rows)

    return pop_df, town_df
```

- [ ] **Step 2: Add Cell 6 — display population tables**

```python
@app.cell
def _(mo, pop_df, town_df):
    mo.vstack([
        mo.md("""
## Population Trends

Youngstown is a small incorporated village in Niagara County, NY, on the eastern
shore of the Niagara River at Lake Ontario. The tables below show raw decennial
census population and decade-over-decade change.
        """),
        mo.md("**Raw population by census decade**"),
        mo.ui.table(town_df[["name", "county", "pop1990", "pop2000", "pop2010", "pop2020", "area_sq_mi"]]),
        mo.md("**Decade-over-decade change**"),
        mo.ui.table(pop_df),
    ])
    return
```

---

### Task 6: Add Cells 7, 8, & 9 — Spatial analysis

**Files:**
- Modify: `example/gpkg_summary.py`

Cell 8 computes total road length using `QgsDistanceArea.measureLength()`. This
method takes a `QgsGeometry` object and returns the length in metres (or geodesic
metres depending on CRS setup). Since the layer is in EPSG:26918 (projected,
metres), planar measurement is accurate.

- [ ] **Step 1: Add Cell 7 — spatial analysis intro**

```python
@app.cell
def _(mo):
    mo.md("""
## Spatial Analysis

QGIS provides geometry measurement APIs that work directly on feature geometries —
no coordinate conversion needed for projected layers. The example below computes
total road network length using `QgsDistanceArea`, the same engine used for geodesic
distance in `stations_analysis.py`.
    """)
    return
```

- [ ] **Step 2: Add Cell 8 — road length computation**

```python
@app.cell
def _(QgsDistanceArea, QgsProject, QgsVectorLayer, gpkg_path, mo):
    _lyr = QgsVectorLayer(f"{gpkg_path}|layername=ny_ytown_streets", "streets", "ogr")
    assert _lyr.isValid(), "Could not open ny_ytown_streets layer"

    _da = QgsDistanceArea()
    _da.setSourceCrs(_lyr.crs(), QgsProject.instance().transformContext())
    _da.setEllipsoid(_lyr.crs().ellipsoidAcronym() or "WGS84")

    _total_m = 0.0
    for _feat in _lyr.getFeatures():
        _total_m += _da.measureLength(_feat.geometry())

    road_km = round(_total_m / 1000, 2)

    mo.stat(
        label="Total road network length (ny_ytown_streets)",
        value=f"{road_km} km",
        caption=f"{_lyr.featureCount()} street segments",
    )
    return (road_km,)
```

- [ ] **Step 3: Add Cell 9 — what's next**

```python
@app.cell
def _(mo):
    mo.md("""
## What's Next

This notebook establishes the pattern for headless QGIS spatial analysis in marimo.
Obvious extensions using the same GeoPackage:

- **Building footprint areas** — iterate `ny_ytown_buildings` polygons, sum
  `QgsDistanceArea.measureArea(geom)`, compare to town polygon area for coverage %
- **Culvert proximity to water** — spatial join between `ny_culverts` (points) and
  `ny_hydrolines` (lines) using `QgsDistanceArea.measureLine` or a QGIS Processing
  nearest-neighbour algorithm
- **Population density** — `pop2020 / calc_sq_mi` from the `town` layer, displayed
  alongside neighbouring villages from `ny_villages`

*Run this notebook with: `./marimo-qgis edit example/gpkg_summary.py`*
    """)
    return
```

---

### Task 7: Test the notebook with marimo export

**Files:**
- Read: `example/gpkg_summary.py` (verify final structure)

- [ ] **Step 1: Export to HTML (re-executes all cells headlessly)**

```bash
./marimo-qgis export html example/gpkg_summary.py -o /tmp/gpkg_summary.html
```

Expected output includes:
- Exit code 0
- No `ImportError` or `AssertionError` lines
- `"Exporting..."` or similar marimo export message

- [ ] **Step 2: Verify output file was created**

```bash
ls -lh /tmp/gpkg_summary.html
# Expected: file exists, size > 50KB
```

- [ ] **Step 3: Spot-check for rendered content**

```bash
grep -o "Layer Inventory\|Population Trends\|Spatial Analysis\|road_km\|Youngstown" /tmp/gpkg_summary.html | sort -u
# Expected: all keywords appear
```

If export fails, check:
1. `./marimo-qgis export html example/gpkg_summary.py 2>&1 | head -40` for traceback
2. Common issue: `example.gpkg` path — the wrapper `cd`s to repo root, so `os.getcwd()` returns `/home/jcz/Github/marimo_qgis`
3. Common issue: field names — use `_feat.fields().names()` to inspect if attribute access fails

---

### Task 8: Update README and commit

**Files:**
- Modify: `README.md`
- Modify: `example/gpkg_summary.py` (final state)

- [ ] **Step 1: Update README project structure section**

In `README.md`, find the project structure block and add the example lines:

```
marimo-qgis/
├── marimo-qgis          # wrapper script (sets env vars, runs marimo)
├── stations_analysis.py # example notebook: QGIS distance matrix + Pandas analysis
├── qgis_test.py         # minimal notebook: confirms QGIS version
├── stations.gpkg        # sample data: CWOP weather stations in Maine, USA
├── example/
│   ├── example.gpkg     # Youngstown NY area: 9-layer GeoPackage, EPSG:26918
│   ├── gpkg_summary.py  # example notebook: layer inventory, population trends, road length
│   └── INSTRUCTIONS.md  # quick start for this example
├── pyproject.toml       # project metadata and dependencies
├── TROUBLESHOOTING.md   # debugging guide for marimo + QGIS integration issues
└── MARIMO_QGIS.md       # additional setup notes
```

- [ ] **Step 2: Update README example notebook section**

Add a second example after the `stations_analysis.py` description:

```markdown
`example/gpkg_summary.py` loads a 9-layer GeoPackage (Youngstown NY area, EPSG:26918),
builds a layer inventory using `dataProvider().subLayers()`, extracts decennial
population data from the `town` layer, and computes total road network length with
`QgsDistanceArea` — all displayed as interactive marimo tables.
```

- [ ] **Step 3: Commit all work**

```bash
git add example/gpkg_summary.py README.md
git commit -m "feat: add example/gpkg_summary.py — QGIS layer inventory, population trends, road length"
```

- [ ] **Step 4: Push to GitHub**

```bash
git push
```

Expected: push succeeds, no errors.

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|-----------------|------|
| Cell 1: QGIS init (QgsApplication, QgsVectorLayer, QgsProject, QgsWkbTypes, QgsDistanceArea) | Task 2 |
| Cell 2: Intro markdown | Task 3 |
| Cell 3: subLayers() inventory with name/geometry/features/crs/extent | Task 4 |
| Cell 4: `mo.ui.table(inv_df)` | Task 4 |
| Cell 5: town layer pop fields, decade-change DataFrame | Task 5 |
| Cell 6: `mo.vstack` of both pop tables | Task 5 |
| Cell 7: Spatial analysis intro markdown | Task 6 |
| Cell 8: Road length via `QgsDistanceArea.measureLength` | Task 6 |
| Cell 9: "What's next" markdown | Task 6 |
| `example/` directory with `example.gpkg` moved | Task 1 |
| `example/INSTRUCTIONS.md` with concise quick start | Task 1 |
| No `/// script` metadata | All cells — omitted |
| No map rendering | All cells — no QgsMapCanvas used |
| No file writes from notebook | Verified — no open() calls |

**Placeholder scan:** No TBD, no TODO, all code blocks complete.

**Type consistency:**
- `inv_df` defined in Cell 3, consumed in Cell 4 ✓
- `gpkg_path` defined in Cell 3, consumed in Cells 5 and 8 ✓
- `pd` returned from Cell 3, imported again in Cell 5 (each cell is isolated) — Cell 5 receives `pd` from Cell 3 via return ✓
- `town_df`, `pop_df` defined in Cell 5, consumed in Cell 6 ✓
- `road_km` defined in Cell 8, not consumed downstream (used inline via `mo.stat`) ✓
- `QgsDistanceArea` returned from QGIS init cell, received in Cell 8 ✓
