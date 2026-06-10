# DO NOT add a PEP 723 `# /// script` block: in headless fallback this notebook
# imports PyQGIS, and `uv run` would sandbox it without --system-site-packages,
# breaking the import. Manage deps via the project venv (./qgis-env.sh setup;
# the bridge client also needs geopandas).
#
# Two ways to run:
#   - LIVE:     QGIS ▸ Processing Toolbox ▸ marimo ▸ "Launch marimo notebook"
#               (the plugin injects MARIMO_QGIS_PORT/TOKEN → reads your open project)
#   - HEADLESS: uv run marimo edit example/live_layers.py
#               (no plugin → own QgsApplication; no live layers)

import marimo

__generated_with = "0.23.9"

app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    import os
    import sys

    # Make the repo-root `qgis_bridge` package importable from example/.
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)

    from qgis_bridge import HeadlessQGIS, QgisBridge

    # Live mode if the plugin launched us (env vars present); else headless.
    try:
        qgis = QgisBridge()
        mode = "live"
    except RuntimeError:
        qgis = HeadlessQGIS()
        mode = "headless"

    return mode, qgis


@app.cell
def _(mo, mode, qgis):
    if mode == "live":
        _p = qgis.project()
        _title = _p.get("title") or _p.get("file_name") or "(untitled project)"
        _msg = (
            f"### 🟢 Live bridge\n"
            f"Connected to QGIS project **{_title}** "
            f"({_p.get('layer_count', 0)} layers, CRS `{_p.get('crs', '?')}`)."
        )
    else:
        _msg = (
            "### ⚪ Headless\n"
            "No plugin/bridge detected — running an own `QgsApplication`. "
            "Launch this notebook from QGIS (Processing ▸ marimo ▸ Launch marimo "
            "notebook) with a project open to see live layers."
        )
    mo.md(_msg)
    return


@app.cell
def _(mode, qgis):
    # Live vector layers available for selection.
    layers = qgis.list_layers() if mode == "live" else []
    names = [layer["name"] for layer in layers if layer.get("type") == "vector"]
    return (names,)


@app.cell
def _(mo, names):
    dropdown = mo.ui.dropdown(
        options=names,
        value=names[0] if names else None,
        label="Vector layer",
    )
    return (dropdown,)


@app.cell
def _(dropdown, mo, names):
    dropdown if names else mo.md(
        "_No live vector layers — launch from QGIS with a vector project open._"
    )
    return


@app.cell
def _(dropdown, mo, mode, qgis):
    # Pull the selected project layer across the bridge as a GeoDataFrame.
    if mode == "live" and dropdown.value:
        gdf = qgis.get_layer(dropdown.value)
        _attrs = gdf.drop(columns=[gdf.geometry.name])
        _out = mo.vstack(
            [
                mo.md(
                    f"### `{dropdown.value}` — {len(gdf)} features, CRS `{gdf.crs}`"
                ),
                mo.ui.table(_attrs.head(100)),
            ]
        )
    else:
        _out = mo.md("_Select a layer (live mode) to load it as a GeoDataFrame._")
    _out
    return


if __name__ == "__main__":
    app.run()
