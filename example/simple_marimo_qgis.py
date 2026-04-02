# DO NOT add a PEP 723 `# /// script` block to QGIS notebooks.
# When marimo is launched via `uv run`, it auto-sandboxes any notebook that
# has inline script metadata, creating a fresh isolated environment without
# --system-site-packages.  That environment has no PyQt6, so every
# `from qgis.core import ...` fails with ModuleNotFoundError.
# Manage dependencies via the project venv instead:
#   uv venv --python 3.13 --system-site-packages
#   uv pip install marimo pandas
#
# Run with:  uv run marimo edit example/simple_marimo_qgis.py
#            uv run marimo run  example/simple_marimo_qgis.py
#
# No wrapper script is needed.  The QGIS init cell handles both
# sys.path (equivalent to PYTHONPATH) and QT_QPA_PLATFORM before
# QgsApplication is created — the only point at which Qt reads them.

# marimo notebook files are plain Python modules.
# The marimo package is imported first so the App object can be created.
import marimo

# marimo writes this tag when it saves the file so it can warn you if a newer
# version of marimo made breaking changes to the format.
__generated_with = "0.21.1"

# The App object is the container for all cells.  Every cell is registered on
# this object via the @app.cell decorator below.  marimo reads the decorator
# arguments (the function's parameter names) to build a dependency graph —
# cells only re-execute when the variables they depend on change.
app = marimo.App()


# ── Cell 1: import marimo ────────────────────────────────────────────────────
#
# Every notebook needs `import marimo as mo` so subsequent cells can call
# mo.md(), mo.stat(), etc.  The variable `mo` is returned in a tuple so that
# marimo registers it as a shared output that other cells can declare as a
# dependency by listing `mo` in their function signature.
@app.cell
def _():
    import marimo as mo
    return (mo,)


# ── Cell 2: narrative explanation ────────────────────────────────────────────
#
# mo.md() renders a GitHub-flavoured markdown string as the cell's visual
# output.  This cell depends on `mo` (declared in the function signature) and
# produces no shared variables of its own — it only displays text.
@app.cell
def _(mo):
    mo.md("""
    # Building Footprint Area — `ny_ytown_buildings`

    This notebook demonstrates the QGIS–marimo integration in its simplest form:
    one QGIS computation, one marimo output.

    **What QGIS does:** opens the `ny_ytown_buildings` layer from `example.gpkg`,
    filters to features where `fid < 450000`, and accumulates
    geodesic area using `QgsDistanceArea`. The layer is in EPSG:4326 (WGS 84
    geographic coordinates), so the ellipsoid is set explicitly to ensure
    accurate square-metre results regardless of the layer's geographic location.

    **What marimo does:** receives the two scalar results (`total_m2`,
    `building_count`) as cell outputs and renders them.
    """)
    return


# ── Cell 3: QGIS computation ─────────────────────────────────────────────────
#
# This cell has no declared dependencies (empty function signature) because it
# is the entry point for the QGIS work.  It returns two plain Python scalars —
# `total_m2` and `building_count` — that the display cell below can consume.
#
# Variables prefixed with `_` are cell-private: marimo will not expose them to
# other cells, which avoids polluting the shared namespace with implementation
# details like `_lyr` or `_da`.
@app.cell
def _():
    import os as _os
    import sys as _sys

    # Make the QGIS Python bindings importable.  The bindings ship with QGIS
    # and live outside the project virtualenv, so we add their directory to
    # sys.path before any `from qgis.core import …` statement.
    _sys.path.insert(0, "/usr/share/qgis/python")

    # Qt requires a platform plugin to initialise even when there is no
    # display (e.g. running inside marimo's headless export pipeline or CI).
    # "offscreen" is a built-in Qt platform that satisfies the requirement
    # without opening a window.  setdefault() leaves the variable alone if it
    # was already set — important when running from inside a live QGIS session
    # via the Processing tool, where the real display platform is already
    # configured by the parent process.
    _os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from qgis.core import (
        QgsApplication,    # the QGIS application singleton
        QgsVectorLayer,    # opens a vector data source (GeoPackage, Shapefile, …)
        QgsDistanceArea,   # geodesic geometry measurement (length, area, distance)
        QgsProject,        # holds the current project's transform context
        QgsFeatureRequest, # query object: filter, attribute subset, spatial index
    )

    # QgsApplication must be created and initialised before any other QGIS
    # class is used.  The first argument is sys.argv (empty list here — no GUI
    # needed).  False means "no GUI" (headless mode).
    _qgs = QgsApplication([], False)
    _qgs.initQgis()

    # Locate the GeoPackage relative to THIS file, not os.getcwd().
    # os.getcwd() is unreliable: it reflects whichever directory launched
    # marimo (the terminal, the QGIS Processing tool, etc.) and changes
    # between environments.  __file__ is always the notebook's own path, so
    # os.path.dirname(__file__) is always the example/ directory where
    # example.gpkg lives — regardless of how the notebook was started.
    _gpkg = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "example.gpkg")

    # The OGR provider URI syntax for a GeoPackage layer is:
    #   /path/to/file.gpkg|layername=<layer>
    # The second argument is the display name shown in QGIS layer panels.
    # The third argument ("ogr") names the data provider.
    _lyr = QgsVectorLayer(f"{_gpkg}|layername=ny_ytown_buildings", "buildings", "ogr")

    # isValid() returns False if the file is missing, the layer name is wrong,
    # or the provider failed to open the data source.  Asserting early gives a
    # clear error message rather than a cryptic failure later.
    assert _lyr.isValid(), "Could not open ny_ytown_buildings"

    # QgsDistanceArea computes geodesic measurements on the ellipsoid.
    # setSourceCrs() tells it the coordinate reference system of the geometries
    # it will measure.  The transform context (from the project singleton)
    # provides any datum-shift grids needed for CRS conversions.
    _da = QgsDistanceArea()
    _da.setSourceCrs(_lyr.crs(), QgsProject.instance().transformContext())

    # Setting the ellipsoid name activates geodesic (true-earth-surface) mode.
    # Without this, QgsDistanceArea falls back to planar Cartesian measurement,
    # which is only accurate for projected CRS layers near their projection
    # centre.  "WGS84" matches the layer's own CRS (EPSG:4326).
    _da.setEllipsoid("WGS84")

    # QgsFeatureRequest is the QGIS equivalent of a SQL WHERE clause.
    # setFilterExpression() accepts QGIS expression syntax — field names must
    # be quoted with double-quotes, string literals with single-quotes.
    # This selects 39 of the 646 buildings (fid values range from 179 040 to
    # 4 970 908; the cut-off at 450 000 captures only the lower-fid subset).
    _request = QgsFeatureRequest().setFilterExpression('"fid" < 450000')

    # Iterate over the filtered features.  getFeatures() is a lazy generator —
    # it reads one feature at a time from disk rather than loading all 39 into
    # memory at once.  measureArea() returns square metres for a WGS84
    # ellipsoid source regardless of the layer's storage CRS.
    total_m2 = 0.0
    building_count = 0
    for _feat in _lyr.getFeatures(_request):
        total_m2 += _da.measureArea(_feat.geometry())
        building_count += 1

    # Return the two results as shared cell outputs.  marimo registers these
    # names and makes them available to any cell that lists them as arguments.
    return building_count, total_m2


# ── Cell 4: display ──────────────────────────────────────────────────────────
#
# This cell depends on `building_count`, `mo`, and `total_m2` — all produced
# by earlier cells.  marimo re-runs this cell automatically if any of those
# values change (e.g. if you edit the filter expression above and re-execute).
#
# mo.hstack() lays out a list of elements side-by-side.
# mo.stat() renders a single key metric with a label and an optional caption.
# The f-string format specs control number presentation:
#   :,   — thousands separator
#   .1f  — one decimal place
#   .4f  — four decimal places
@app.cell
def _(building_count, mo, total_m2):
    mo.hstack([
        mo.stat(
            value=f"{building_count}",
            label="Buildings measured",
            caption="fid < 450000",
        ),
        mo.stat(
            value=f"{total_m2:,.1f} m²",
            label="Total footprint area",
            caption="geodesic, WGS 84 ellipsoid",
        ),
        mo.stat(
            value=f"{total_m2 / 10_000:,.4f} ha",
            label="In hectares",
            # Integer division would lose precision; divide the float directly.
            caption=f"avg {total_m2 / building_count:,.1f} m² per building",
        ),
    ])
    return


# When the file is executed directly as a script (`python simple_marimo_qgis.py`
# or `uv run python simple_marimo_qgis.py`) rather than loaded by the marimo
# server, app.run() triggers a headless execution of all cells in topological
# order and prints outputs to stdout.
if __name__ == "__main__":
    app.run()
