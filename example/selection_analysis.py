# DO NOT add a PEP 723 `# /// script` block (headless fallback imports PyQGIS).
# Manage deps via ./qgis-env.sh setup (needs geopandas).

import marimo

__generated_with = "0.23.9"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md("""
    # Analyse the QGIS selection

    **What this demonstrates.** Reading the features currently selected in
    QGIS into a GeoDataFrame and summarising them, plus showing the live
    map-canvas extent.

    **Dependencies.** The bundled `qgis_bridge` client; a running QGIS with
    the marimo plugin enabled (live mode); `geopandas`. Selection and extent
    require the QGIS desktop, so these are blank in headless mode.

    **How it works.** The plugin runs a localhost HTTP bridge; this notebook
    calls `get_canvas_extent` and `get_selected_features` over it.

    **▶ Run order** — this profile does not auto-run cells on open. Run them
    top to bottom (or *Run ▸ Run all cells*): **1)** connect · **2)** view
    the extent · **3)** select features in QGIS, then click to load them.
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ### 1. Connect to QGIS — run the next cell
    """)
    return


@app.cell
def _():
    import os
    import sys

    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)

    from qgis_bridge import HeadlessQGIS, QgisBridge

    try:
        qgis = QgisBridge()
        mode = "live"
    except RuntimeError:
        qgis = HeadlessQGIS()
        mode = "headless"
    return mode, qgis


@app.cell
def _(mo):
    mo.md("""
    ### 2. Current map-canvas extent
    """)
    return


@app.cell
def _(mo, mode, qgis):
    if mode == "live":
        e = qgis.get_canvas_extent()
        _out = mo.md(
            f"🟢 **Live** — canvas extent (`{e['crs']}`): "
            f"[{e['xmin']:.4f}, {e['ymin']:.4f}] – [{e['xmax']:.4f}, {e['ymax']:.4f}]"
        )
    else:
        _out = mo.md("⚪ **Headless** — no live canvas or selection.")
    _out
    return


@app.cell
def _(mo):
    mo.md("""
    ### 3. Select features in QGIS, then click to load them
    """)
    return


@app.cell
def _(mo):
    load = mo.ui.run_button(label="↻ Load current selection from QGIS", kind="success")
    load
    return (load,)


@app.cell
def _(load, mo, mode, qgis):
    if mode == "live" and load.value:
        try:
            gdf = qgis.get_selected_features()
            attrs = gdf.drop(columns=[gdf.geometry.name])
            numeric = attrs.select_dtypes("number")
            blocks = [
                mo.md(f"#### {len(gdf)} selected features (CRS `{gdf.crs}`)"),
                mo.ui.table(attrs.head(100)),
            ]
            if not numeric.empty:
                blocks += [
                    mo.md("##### Numeric summary"),
                    mo.ui.table(numeric.describe().reset_index()),
                ]
            _out = mo.vstack(blocks)
        except Exception as exc:  # noqa: BLE001 — surface "no selection" etc.
            _out = mo.md(f"⚠️ {exc}")
    else:
        _out = mo.md("_Select features in QGIS, then click the button._")
    _out
    return


if __name__ == "__main__":
    app.run()
