# DO NOT add a PEP 723 `# /// script` block (headless fallback imports PyQGIS).
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
        # Render the QGIS map

        **What this demonstrates.** Capturing the live QGIS map canvas as a PNG
        and displaying it inside a notebook cell, at a size you choose.

        **Dependencies.** The bundled `qgis_bridge` client; a running QGIS with
        the marimo plugin enabled (live mode). Rendering needs the QGIS desktop,
        so it is unavailable in headless mode.

        **How it works.** The plugin runs a localhost HTTP bridge; this notebook
        calls `render_map(width, height)` which returns PNG bytes shown with
        `mo.image`.

        **▶ Run order** — this profile does not auto-run cells on open. Run them
        top to bottom (or *Run ▸ Run all cells*): **1)** connect · **2)** set the
        size and click Render.
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
        "🟢 **Live** — render the current QGIS canvas below."
        if mode == "live"
        else "⚪ **Headless** — no live canvas to render (launch from QGIS)."
    )
    return


@app.cell
def _(mo):
    mo.md("### 2. Set the size and click **Render canvas**")
    return


@app.cell
def _(mo):
    width = mo.ui.slider(
        200, 1600, value=800, step=50, label="Width (px)", show_value=True, full_width=True
    )
    height = mo.ui.slider(
        150, 1200, value=600, step=50, label="Height (px)", show_value=True, full_width=True
    )
    render = mo.ui.run_button(label="Render canvas", kind="success")

    mo.vstack([width, height, render], gap=0.75)
    return height, render, width


@app.cell
def _(height, mo, mode, qgis, render, width):
    if mode == "live" and render.value:
        png = qgis.render_map(width.value, height.value)
        _out = mo.image(src=png, alt="QGIS map canvas", width=width.value)
    else:
        _out = mo.md("_Click **Render canvas** to capture the current QGIS map view._")
    _out
    return


if __name__ == "__main__":
    app.run()
