# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "marimo",
#     "pandas",
# ]
# ///
#
# QGIS bindings (qgis.core) are NOT listed above because they ship with the
# QGIS application and are not available on PyPI.  They are added to sys.path
# at runtime inside the QGIS init cell below.
#
# Run with:  uv run marimo edit example/gpkg_summary.py
#            uv run marimo run  example/gpkg_summary.py
#
# No wrapper script is needed.  The QGIS init cell handles both
# sys.path (equivalent to PYTHONPATH) and QT_QPA_PLATFORM before
# QgsApplication is created — the only point at which Qt reads them.

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
    ## About This Notebook

    This notebook demonstrates a complementary coupling between two tools:

    **QGIS** is a full geographic information system with a Python API (PyQGIS). It
    handles everything spatial: opening vector layers, iterating features, measuring
    geometry (lengths, areas, distances) with geodesic accuracy, managing coordinate
    reference systems and on-the-fly reprojection, and exposing the same processing
    algorithms available in the QGIS desktop application — all running headlessly,
    without a display.

    **marimo** is a reactive Python notebook that treats each cell as a pure function.
    Dependencies between cells are tracked automatically: when data changes, only the
    affected cells re-execute. marimo handles documentation (markdown), interactive UI
    elements (tables, sliders, dropdowns), statistical summaries, and presentation —
    turning QGIS outputs into a reproducible, self-documenting report.

    The separation of responsibilities is deliberate:

    | Responsibility | Tool |
    |---|---|
    | Open and enumerate spatial layers | QGIS (`QgsProviderRegistry`, `QgsVectorLayer`) |
    | Iterate features and read attributes | QGIS (`getFeatures()`) |
    | Measure geometry (length, area, distance) | QGIS (`QgsDistanceArea`) |
    | Coordinate reference system handling | QGIS (`QgsCrs`, `QgsCoordinateTransform`) |
    | Tabular summaries and statistics | pandas (fed by QGIS feature data) |
    | Display, documentation, interactivity | marimo (`mo.md`, `mo.ui.table`, `mo.vstack`) |

    Because marimo notebooks are plain Python files, this workflow is fully reproducible
    from the command line (`marimo export html`) and version-controllable in git — with
    no hidden kernel state.
    """)
    return


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
    return QgsDistanceArea, QgsProject, QgsVectorLayer, QgsWkbTypes


@app.cell
def _(mo):
    mo.md("""
    # GeoPackage Summary: Youngstown, NY

    This notebook explores `example.gpkg`, a GeoPackage containing spatial data for
    the Youngstown, New York area — a small village in Niagara County on Lake Ontario.

    The file holds **20 layers** with mixed geometry types (points, lines, polygons) and
    three coordinate reference systems: **EPSG:26918** (UTM zone 18N, metres) for local
    NY layers, **EPSG:4269** (NAD83 geographic) for federal NHD/NHDPlus data, and
    **EPSG:4326** (WGS 84) for buildings and named features. Layers include administrative
    boundaries (`town`, `ny_youngstown`), infrastructure (`ny_ytown_streets`,
    `ny_culverts_clipped`), hydrology (`nhd_flowlines`, `ytown_nhdflowline`,
    `ny_hydrolines_clip`, `ny_streams`), land cover (`landcover_woodland`), NHDPlus
    catchments, state-owned parcels, and named features from GNIS. We use QGIS APIs
    throughout: layer enumeration, feature iteration, geometry measurement — the same
    APIs used in the QGIS desktop application, running headlessly here.
    """)
    return


@app.cell
def _(QgsVectorLayer, QgsWkbTypes):
    import os as _os
    import pandas as pd
    from qgis.core import QgsProviderRegistry

    _gpkg = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "example.gpkg")

    _rows = []
    for _sub in QgsProviderRegistry.instance().querySublayers(_gpkg):
        _name = _sub.name()
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
                f"{_ext.xMinimum():.4f}, {_ext.yMinimum():.4f}"
                f" → {_ext.xMaximum():.4f}, {_ext.yMaximum():.4f}"
            ),
        })

    gpkg_path = _gpkg
    inv_df = pd.DataFrame(_rows)
    return gpkg_path, inv_df, pd


@app.cell
def _(inv_df, mo):
    _crs_list = inv_df["crs"].unique().tolist() if not inv_df.empty else []
    _crs_note = (
        f"Layers use {len(_crs_list)} CRS: {', '.join(sorted(_crs_list))}. "
        "Extents are in each layer's native units."
        if len(_crs_list) != 1
        else f"All layers share {_crs_list[0]}. Extents are in that CRS's native units."
    )
    mo.vstack([
        mo.md(f"""
    ## Layer Inventory

    The table below lists every layer in the GeoPackage. {_crs_note}
        """),
        mo.ui.table(inv_df),
    ])
    return


@app.cell
def _(QgsVectorLayer, gpkg_path, pd):
    def _load_pop(layer_name):
        _lyr = QgsVectorLayer(f"{gpkg_path}|layername={layer_name}", layer_name, "ogr")
        assert _lyr.isValid(), f"Could not open {layer_name} layer"
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
        return pd.DataFrame(_records)

    town_df = _load_pop("town")
    village_df = _load_pop("ny_youngstown")

    # Decade-over-decade change for both town and village
    _decades = [("1990", "2000"), ("2000", "2010"), ("2010", "2020")]
    _change_rows = []
    for _entity, _df in [("Town", town_df), ("Village", village_df)]:
        for _from, _to in _decades:
            _p0 = _df[f"pop{_from}"].iloc[0]
            _p1 = _df[f"pop{_to}"].iloc[0]
            _delta = _p1 - _p0
            _pct   = round((_delta / _p0) * 100, 1) if _p0 else 0.0
            _change_rows.append({
                "entity":    _entity,
                "decade":    f"{_from}→{_to}",
                "pop_start": _p0,
                "pop_end":   _p1,
                "Δ pop":     _delta,
                "% change":  _pct,
            })

    pop_df = pd.DataFrame(_change_rows)
    return pop_df, town_df, village_df


@app.cell
def _(mo, pd, pop_df, town_df, village_df):
    mo.vstack([
        mo.md("""
    ## Population Trends

    The GeoPackage has two administrative boundaries for Youngstown: `town` (Town of
    Youngstown, a civil township) and `ny_youngstown` (Village of Youngstown, the
    incorporated village within it). The tables below show raw decennial census
    population and decade-over-decade change for both.
        """),
        mo.md("**Raw population by census decade**"),
        mo.ui.table(
            pd.concat([
                town_df[["name", "county", "pop1990", "pop2000", "pop2010", "pop2020", "area_sq_mi"]],
                village_df[["name", "county", "pop1990", "pop2000", "pop2010", "pop2020", "area_sq_mi"]],
            ], ignore_index=True)
        ),
        mo.md("**Decade-over-decade change (Town vs Village)**"),
        mo.ui.table(pop_df),
    ])
    return


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

    mo.md(f"**Total road network length (ny_ytown_streets):** {road_km} km ({_lyr.featureCount()} street segments)")
    return


@app.cell
def _(mo):
    mo.md("""
    ## What's Next

    This notebook establishes the pattern for headless QGIS spatial analysis in marimo.
    Obvious extensions using the same GeoPackage:

    - **Building footprint areas** — iterate `ny_ytown_buildings` polygons, sum
      `QgsDistanceArea.measureArea(geom)`, compare to town polygon area for coverage %
    - **Culvert proximity to water** — spatial join between `ny_culverts_clipped` (points) and
      `ny_hydrolines_clip` (lines) using `QgsDistanceArea.measureLine` or a QGIS Processing
      nearest-neighbour algorithm; cross-reference `CONDITION_RATING` from the culvert layer
    - **Population density** — `pop2020 / calc_sq_mi` from both `town` and `ny_youngstown`,
      with `gnis` or `us_geonames` for nearby named features as map context
    - **Watershed analysis** — overlay `nhdplus_catchment` polygons with `nhd_flowlines`
      to trace drainage; compare `ytown_nhdflowline` (local) vs `nhd_flowlines` (regional)
    - **Woodland coverage** — sum `landcover_woodland` polygon areas within the AOI
      (`AreaOfInterest`) and express as % of total area
    - **State-owned land inventory** — `ny_state_owned` has assessed values, year built,
      and owner agency; compare parcel areas against `gu_reserve` (federal reserve land)

    *Run this notebook with: `./marimo-qgis edit example/gpkg_summary.py`*
    """)
    return


if __name__ == "__main__":
    app.run()
