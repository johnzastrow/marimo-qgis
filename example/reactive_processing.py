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
    mo.md(
        """
        # Reactive Processing → QGIS

        **What this demonstrates.** Driving a QGIS Processing algorithm
        (`native:buffer`) from a marimo slider and inserting the result back into
        the live QGIS project — a reactive analysis loop.

        **Dependencies.** The bundled `qgis_bridge` client; a running QGIS with
        the marimo plugin enabled (live mode); `geopandas`. Without the plugin it
        falls back to a headless `QgsApplication` (no live Processing registry).

        **How it works.** The plugin runs a localhost HTTP bridge; this notebook
        calls `list_layers`, `run_algorithm` and `insert_layer` over it.

        **▶ Run order** — this profile does not auto-run cells on open. Run them
        top to bottom (or *Run ▸ Run all cells*): **1)** connect · **2)** pick a
        layer + distance · **3)** click Run to buffer & insert.
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
        "🟢 **Live** — connected to the QGIS project."
        if mode == "live"
        else "⚪ **Headless** — launch from QGIS for a live Processing registry."
    )
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
def _(mo):
    mo.md("### 2. Pick a layer and buffer distance, then click **Run**")
    return


@app.cell
def _(mo, names):
    # Controls created AND displayed here; the result cell below reads their values.
    layer = mo.ui.dropdown(
        options=names,
        value=names[0] if names else None,
        label="Layer",
        searchable=True,
        full_width=True,
    )
    distance = mo.ui.slider(
        1,
        500,
        value=50,
        label="Buffer distance (layer units)",
        show_value=True,
        full_width=True,
    )
    run = mo.ui.run_button(label="Run native:buffer → insert", kind="success")

    (
        mo.vstack([layer, distance, run], gap=0.75)
        if names
        else mo.md("_No live vector layers — open a project with a vector layer._")
    )
    return distance, layer, run


@app.cell
def _(mo):
    mo.md("### 3. Result — appears after you click **Run**")
    return


@app.cell
def _(distance, layer, mo, mode, qgis, run):
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


@app.cell
def _(mo, mode, qgis):
    # Reference: browse the Processing registry (optional).
    if mode == "live":
        algorithms = qgis.list_algorithms()
        _out = mo.vstack(
            [
                mo.md(f"#### Reference — {len(algorithms)} Processing algorithms"),
                mo.ui.table(algorithms, page_size=10),
            ]
        )
    else:
        _out = mo.md("_No live registry in headless mode._")
    _out
    return


if __name__ == "__main__":
    app.run()
