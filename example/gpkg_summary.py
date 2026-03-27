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


@app.cell
def _(QgsVectorLayer, QgsWkbTypes):
    import os as _os
    import pandas as pd

    _gpkg = _os.path.join(_os.getcwd(), "example", "example.gpkg")

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
            "Δ pop":     _delta,
            "% change":  _pct,
        })

    pop_df = pd.DataFrame(_change_rows)

    return pop_df, town_df


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
    return (road_km,)


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


if __name__ == "__main__":
    app.run()
