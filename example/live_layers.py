# DO NOT add a PEP 723 `# /// script` block: in headless fallback this notebook
# imports PyQGIS, and uv would sandbox it without --system-site-packages.
# Manage deps via ./qgis-env.sh setup.

import marimo

__generated_with = "0.23.9"

app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md(
        """
        # Live QGIS layers

        **What this demonstrates.** Listing the layers in your *running* QGIS
        project and pulling one into a GeoDataFrame — the simplest read-only use
        of the bridge.

        **Dependencies.** The bundled `qgis_bridge` client; a running QGIS with
        the marimo plugin enabled (live mode); `geopandas`. Without the plugin it
        falls back to a headless `QgsApplication` (no live layers).

        **How it works.** The plugin runs a localhost HTTP bridge; this notebook
        calls `project`, `list_layers` and `get_layer` over it.

        **▶ Run order** — this profile does not auto-run cells on open. Run them
        top to bottom (or *Run ▸ Run all cells*): **1)** connect · **2)** pick a
        layer (it loads as a GeoDataFrame).
        """
    )
    return


@app.cell
def _(mo):
    mo.md("### 1. Connect to QGIS — run the next cell")
    return


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
            f"🟢 **Live** — connected to QGIS project **{_title}** "
            f"({_p.get('layer_count', 0)} layers, CRS `{_p.get('crs', '?')}`)."
        )
    else:
        _msg = (
            "⚪ **Headless** — no plugin/bridge detected (own `QgsApplication`). "
            "Launch from QGIS (marimo toolbar button → manager panel → Launch…) "
            "with a project open to see live layers."
        )
    mo.md(_msg)
    return


@app.cell
def _(mo):
    mo.md("### 2. Pick a vector layer — it loads as a GeoDataFrame below")
    return


@app.cell
def _(mode, qgis):
    layers = qgis.list_layers() if mode == "live" else []
    names = [layer["name"] for layer in layers if layer.get("type") == "vector"]
    return (names,)


@app.cell
def _(mo, names):
    dropdown = mo.ui.dropdown(
        options=names,
        value=names[0] if names else None,
        label="Vector layer",
        searchable=True,
        full_width=True,
    )
    (
        dropdown
        if names
        else mo.md(
            "_No live vector layers — launch from QGIS with a vector project open._"
        )
    )
    return (dropdown,)


@app.cell
def _(dropdown, mo, mode, qgis):
    if mode == "live" and dropdown.value:
        gdf = qgis.get_layer(dropdown.value)
        _attrs = gdf.drop(columns=[gdf.geometry.name])
        _out = mo.vstack(
            [
                mo.md(f"#### `{dropdown.value}` — {len(gdf)} features, CRS `{gdf.crs}`"),
                mo.ui.table(_attrs.head(100)),
            ]
        )
    else:
        _out = mo.md("_Select a layer (live mode) to load it as a GeoDataFrame._")
    _out
    return


if __name__ == "__main__":
    app.run()
