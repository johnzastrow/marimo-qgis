# DO NOT add a PEP 723 `# /// script` block (headless fallback imports PyQGIS).
# Manage deps via ./qgis-env.sh setup.
#
# Phase 3 bridge demo: render the live QGIS map canvas into a notebook cell.
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
        "### 🟢 Live — render the current QGIS canvas below"
        if mode == "live"
        else "### ⚪ Headless — no live canvas to render (launch from QGIS)"
    )
    return


@app.cell
def _(mo):
    width = mo.ui.slider(200, 1600, value=800, step=50, label="Width (px)")
    height = mo.ui.slider(150, 1200, value=600, step=50, label="Height (px)")
    render = mo.ui.run_button(label="🗺 Render canvas")
    return height, render, width


@app.cell
def _(height, mo, render, width):
    mo.hstack([width, height, render])
    return


@app.cell
def _(height, mo, mode, qgis, render, width):
    # Re-render whenever the button is clicked (size is read at click time).
    if mode == "live" and render.value:
        png = qgis.render_map(width.value, height.value)
        _out = mo.image(src=png, alt="QGIS map canvas", width=width.value)
    else:
        _out = mo.md("_Click **Render canvas** to capture the current QGIS map view._")
    _out
    return


if __name__ == "__main__":
    app.run()
