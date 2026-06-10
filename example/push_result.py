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
        # Push a result back to QGIS

        **What this demonstrates.** Reading a live layer, buffering it with
        geopandas, previewing it, and pushing the result back into the running
        QGIS project as a new layer.

        **Dependencies.** The bundled `qgis_bridge` client; a running QGIS with
        the marimo plugin enabled (live mode); `geopandas`. Without the plugin it
        falls back to a headless `QgsApplication` (nothing to push into).

        **How it works.** The plugin runs a localhost HTTP bridge; this notebook
        calls `get_layer` and `insert_layer` over it.

        **▶ Run order** — this profile does not auto-run cells on open. Run them
        top to bottom (or *Run ▸ Run all cells*): **1)** connect · **2)** pick a
        layer + distance · **3)** preview · **4)** click Push.
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
        "🟢 **Live** — results can be pushed back to QGIS."
        if mode == "live"
        else "⚪ **Headless** — launch from QGIS to push results into a project."
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
    mo.md("### 2. Pick a source layer and buffer distance")
    return


@app.cell
def _(mo, names):
    source = mo.ui.dropdown(
        options=names,
        value=names[0] if names else None,
        label="Source layer",
        searchable=True,
        full_width=True,
    )
    distance = mo.ui.slider(
        0,
        1000,
        value=50,
        label="Buffer distance (layer units)",
        show_value=True,
        full_width=True,
    )

    (
        mo.vstack([source, distance], gap=0.75)
        if names
        else mo.md("_No live vector layers._")
    )
    return distance, source


@app.cell
def _(mo):
    mo.md("### 3. Preview the buffered layer")
    return


@app.cell
def _(distance, mo, mode, qgis, source):
    buffered = None
    if mode == "live" and source.value:
        src = qgis.get_layer(source.value)
        buffered = src.copy()
        buffered["geometry"] = src.geometry.buffer(distance.value)
        _preview = mo.vstack(
            [
                mo.md(
                    f"Buffered **{source.value}** by {distance.value} → "
                    f"{len(buffered)} features (CRS `{buffered.crs}`)"
                ),
                mo.ui.table(buffered.drop(columns=[buffered.geometry.name]).head(50)),
            ]
        )
    else:
        _preview = mo.md("_Select a layer (live mode) to compute a buffer._")
    _preview
    return (buffered,)


@app.cell
def _(mo):
    mo.md("### 4. Push it into QGIS — click the button, result appears below")
    return


@app.cell
def _(mo):
    push = mo.ui.run_button(label="⬆ Push buffered layer to QGIS", kind="success")
    push
    return (push,)


@app.cell
def _(buffered, mo, push, qgis, source):
    if push.value and buffered is not None:
        result = qgis.insert_layer(buffered, name=f"{source.value}_buffer")
        _msg = mo.md(
            f"✅ Inserted **{result['name']}** "
            f"(id `{result['id']}`, {result['feature_count']} features) — "
            "see the QGIS Layers panel."
        )
    else:
        _msg = mo.md("_Click the button to push the buffered layer into QGIS._")
    _msg
    return


if __name__ == "__main__":
    app.run()
