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
# Run with:  uv run marimo edit example/processing_demo.py
#            uv run marimo run  example/processing_demo.py
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
# QGIS Processing Algorithms in marimo

The QGIS **Processing framework** exposes 300+ spatial algorithms — buffer,
dissolve, clip, reproject, spatial join, and more — through a single
`processing.run()` call. QGIS **Processing models** (`.model3` files built in
the Model Designer) are registered and called identically.

This notebook demonstrates:

1. Initialising the Processing framework headlessly alongside `QgsApplication`
2. Running `native:buffer` on the culvert layer with a **reactive distance
   slider** — marimo re-executes the algorithm automatically when it changes
3. Running `native:dissolve` to merge overlapping buffers into a single
   coverage polygon
4. Comparing culvert buffer coverage to the total town area
5. Listing all available algorithms
    """)
    return


@app.cell
def _():
    import os as _os
    import sys as _sys

    _sys.path.insert(0, "/usr/share/qgis/python/plugins")  # processing.run(), etc.
    _sys.path.insert(0, "/usr/share/qgis/python")
    _os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from qgis.core import (
        QgsApplication,
        QgsVectorLayer,
        QgsDistanceArea,
        QgsProject,
        QgsProcessingFeedback,
    )
    from qgis.analysis import QgsNativeAlgorithms

    _qgs = QgsApplication([], False)
    _qgs.initQgis()

    # Register the native algorithm provider.  This step is required when
    # running headlessly — inside the QGIS desktop application the providers
    # are already registered by the application startup sequence.  Without it,
    # processing.run("native:buffer", ...) raises "No algorithm found".
    QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())

    # The processing module lives at /usr/share/qgis/python/processing/.
    # It must be imported AFTER initQgis() and provider registration.
    import processing

    # QgsProcessingFeedback emits signals but does not store log text.
    # This thin subclass accumulates lines so they can be displayed in marimo.
    class LogFeedback(QgsProcessingFeedback):
        def __init__(self):
            super().__init__()
            self._lines = []
        def pushInfo(self, info):        self._lines.append(info)
        def pushWarning(self, w):        self._lines.append(f"⚠ {w}")
        def pushCommandInfo(self, info): self._lines.append(f"$ {info}")
        def log(self):                   return "\n".join(self._lines) or "(no messages)"

    return LogFeedback, QgsDistanceArea, QgsProject, QgsVectorLayer, processing


@app.cell
def _(QgsVectorLayer):
    import os as _os

    # __file__ is always the notebook's own path — use it to locate example.gpkg
    # reliably regardless of how the notebook was launched.
    _gpkg = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "example.gpkg")

    culverts_layer = QgsVectorLayer(f"{_gpkg}|layername=ny_culverts_clipped", "culverts", "ogr")
    assert culverts_layer.isValid(), "Could not open ny_culverts_clipped"

    town_layer = QgsVectorLayer(f"{_gpkg}|layername=town", "town", "ogr")
    assert town_layer.isValid(), "Could not open town"

    return culverts_layer, town_layer


@app.cell
def _(mo):
    mo.md("""
## Reactive processing — buffer distance

The slider below controls the buffer radius applied around each culvert.
Changing it triggers `native:buffer` → `native:dissolve` → area comparison —
the full Processing chain re-executes automatically.

Both layers are **EPSG:26918** (UTM zone 18N, metres), so the distance is
in metres with no unit conversion needed.
    """)
    return


@app.cell
def _(mo):
    buffer_distance = mo.ui.slider(
        start=50, stop=500, step=50, value=200,
        label="Buffer distance (metres)",
    )
    buffer_distance
    return (buffer_distance,)


@app.cell
def _(LogFeedback, buffer_distance, culverts_layer, processing):
    # native:buffer applies a fixed-distance buffer around every feature.
    # SEGMENTS=8 controls polygon smoothness (more segments = rounder circles).
    # TEMPORARY_OUTPUT returns an in-memory QgsVectorLayer; no file is written.
    _feedback = LogFeedback()
    _result = processing.run(
        "native:buffer",
        {
            'INPUT':         culverts_layer,
            'DISTANCE':      buffer_distance.value,
            'SEGMENTS':      8,
            'END_CAP_STYLE': 0,   # 0 = Round
            'JOIN_STYLE':    0,   # 0 = Round
            'MITER_LIMIT':   2,
            'DISSOLVE':      False,
            'OUTPUT':        'TEMPORARY_OUTPUT',
        },
        feedback=_feedback,
    )
    buffer_layer = _result['OUTPUT']
    buffer_log   = _feedback.log()
    return buffer_layer, buffer_log


@app.cell
def _(LogFeedback, buffer_layer, processing):
    # native:dissolve merges all features into a single polygon.
    # FIELD=[] means dissolve unconditionally (no grouping field).
    # The result is one polygon representing the union of all buffer circles —
    # the total area reachable within buffer_distance metres of any culvert.
    _feedback = LogFeedback()
    _result = processing.run(
        "native:dissolve",
        {
            'INPUT':  buffer_layer,
            'FIELD':  [],
            'OUTPUT': 'TEMPORARY_OUTPUT',
        },
        feedback=_feedback,
    )
    dissolved_layer = _result['OUTPUT']
    dissolve_log    = _feedback.log()
    return dissolved_layer, dissolve_log


@app.cell
def _(QgsDistanceArea, QgsProject, buffer_distance, buffer_layer, buffer_log, dissolved_layer, dissolve_log, mo, town_layer):
    def _measure(lyr):
        _da = QgsDistanceArea()
        _da.setSourceCrs(lyr.crs(), QgsProject.instance().transformContext())
        _da.setEllipsoid(lyr.crs().ellipsoidAcronym() or "WGS84")
        return sum(_da.measureArea(f.geometry()) for f in lyr.getFeatures())

    _coverage_m2 = _measure(dissolved_layer)
    _town_m2     = _measure(town_layer)
    _pct         = (_coverage_m2 / _town_m2) * 100

    mo.vstack([
        mo.md(f"## Results — {buffer_distance.value} m buffer around culverts"),
        mo.hstack([
            mo.stat(
                value=f"{buffer_layer.featureCount()}",
                label="Culverts buffered",
                caption=f"{buffer_distance.value} m radius each",
            ),
            mo.stat(
                value=f"{_coverage_m2 / 10_000:,.2f} ha",
                label="Coverage area",
                caption="dissolved buffer union",
            ),
            mo.stat(
                value=f"{_town_m2 / 10_000:,.1f} ha",
                label="Town of Youngstown",
                caption="total area",
            ),
            mo.stat(
                value=f"{_pct:.1f}%",
                label="Town covered",
                caption=f"within {buffer_distance.value} m of a culvert",
            ),
        ]),
        mo.accordion({
            "Buffer log":  mo.md(f"```\n{buffer_log}\n```"),
            "Dissolve log": mo.md(f"```\n{dissolve_log}\n```"),
        }),
    ])
    return


@app.cell
def _(mo):
    mo.md("""
## Running Processing models

A QGIS Processing model (`.model3` file built in the Model Designer) is just
another algorithm. Load the file, register it, then call it identically to any
native algorithm:

```python
from qgis.core import QgsProcessingModelAlgorithm

model = QgsProcessingModelAlgorithm()
model.fromFile("/path/to/my_model.model3")
QgsApplication.processingRegistry().addAlgorithm(model)

result = processing.run(model.name(), {
    'INPUT_LAYER': my_layer,
    'THRESHOLD':   500,
    'OUTPUT':      'TEMPORARY_OUTPUT',
})
```

`model.name()` returns the algorithm ID set in the Model Designer.  All
outputs are returned in the `result` dict, keyed by the output names defined
in the model.  The same `LogFeedback` class captures the model's run log.
    """)
    return


@app.cell
def _(mo):
    import pandas as _pd
    from qgis.core import QgsApplication as _QgsApp

    _rows = [
        {"id": alg.id(), "name": alg.displayName(), "group": alg.group()}
        for alg in _QgsApp.processingRegistry().algorithms()
    ]
    _alg_df = _pd.DataFrame(_rows).sort_values("id").reset_index(drop=True)

    mo.vstack([
        mo.md(f"## Available algorithms — {len(_rows)} registered"),
        mo.ui.table(_alg_df),
    ])
    return


@app.cell
def _(mo):
    mo.md("""
## What's next

With the Processing framework initialised, the same GeoPackage supports more
complex spatial workflows:

- **Culvert proximity to streams** — `native:joinbynearest` between
  `ny_culverts_clipped` (points) and `ny_hydrolines_clip` (lines), then
  cross-reference `CONDITION_RATING` from the culvert attributes
- **Building density grid** — `native:countpointsinpolygon` with a generated
  grid over the town extent and `ny_ytown_buildings` centroids
- **Catchment analysis** — `native:clip` to isolate `nhdplus_catchment`
  polygons touching the area of interest, then chain with `nhd_flowlines`
- **Multi-step model** — build any of the above as a `.model3` in QGIS Model
  Designer, save it alongside this notebook, and load it with
  `QgsProcessingModelAlgorithm.fromFile()`
    """)
    return


if __name__ == "__main__":
    app.run()
