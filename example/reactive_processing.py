# DO NOT add a PEP 723 `# /// script` block (headless fallback imports PyQGIS).
# Manage deps via ./qgis-env.sh setup (needs geopandas).
#
# Phase 3 bridge demo: browse the Processing registry, and run an algorithm
# (native:buffer) reactively from a slider, inserting the result back into QGIS.
#
#   LIVE: click the marimo toolbar button → manager panel → Launch… → this file

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
def _(mo, mode):
    mo.md(
        "### 🟢 Live — run Processing algorithms against your project"
        if mode == "live"
        else "### ⚪ Headless — no live Processing registry (launch from QGIS)"
    )
    return


@app.cell
def _(mo, mode, qgis):
    # Searchable view of the Processing algorithm registry.
    if mode == "live":
        algorithms = qgis.list_algorithms()
        _out = mo.vstack(
            [
                mo.md(f"**{len(algorithms)} Processing algorithms available**"),
                mo.ui.table(algorithms, page_size=10),
            ]
        )
    else:
        _out = mo.md("_No live registry in headless mode._")
    _out
    return


@app.cell
def _(mode, qgis):
    names = [
        layer["name"]
        for layer in (qgis.list_layers() if mode == "live" else [])
        if layer.get("type") == "vector"
    ]
    return (names,)


@app.cell
def _(mo, names):
    layer = mo.ui.dropdown(
        options=names, value=names[0] if names else None, label="Layer"
    )
    distance = mo.ui.slider(1, 500, value=50, label="Buffer distance (layer units)")
    run = mo.ui.run_button(label="⚙ Run native:buffer → insert into QGIS")
    return distance, layer, run


@app.cell
def _(distance, layer, mo, names, run):
    mo.hstack([layer, distance, run]) if names else mo.md("_No live vector layers._")
    return


@app.cell
def _(distance, layer, mo, mode, qgis, run):
    # Reactive Processing: slider → native:buffer (in QGIS) → insert result back.
    if mode == "live" and run.value and layer.value:
        result = qgis.run_algorithm(
            "native:buffer",
            {
                "INPUT": layer.value,
                "DISTANCE": distance.value,
                "SEGMENTS": 8,
                "DISSOLVE": False,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
        )
        gdf = result["OUTPUT"]
        inserted = qgis.insert_layer(gdf, name=f"{layer.value}_buffer{distance.value}")
        _out = mo.vstack(
            [
                mo.md(
                    f"✅ `native:buffer` → {len(gdf)} features; inserted "
                    f"**{inserted['name']}** into the QGIS project."
                ),
                mo.ui.table(gdf.drop(columns=[gdf.geometry.name]).head(30)),
            ]
        )
    else:
        _out = mo.md("_Pick a layer and distance, then click Run._")
    _out
    return


if __name__ == "__main__":
    app.run()
