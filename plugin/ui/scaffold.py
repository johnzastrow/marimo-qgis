"""Generate a starter marimo + QGIS notebook for the dock's "New…" button.

The scaffold connects to the live bridge (falling back to headless), lets the user
pick a vector layer, and summarises it — a runnable starting point.

`qgis_bridge` must be importable in the notebook venv. In the dev/symlink layout
it lives next to the plugin's repo root (dev), or bundled inside the plugin
(QGIS-repo / zip install); we inject that path so the notebook can import it.
"""

# The notebook body. A sentinel (not str.format) is used for substitution because
# the template itself contains f-string braces.
_TEMPLATE = '''# =============================================================================
# STARTER STUB — created by the marimo QGIS plugin.
#
# This is a minimal, working example: it connects to the live QGIS project and
# summarises a layer. It is meant as a starting point — extend it with your own
# cells and analysis, and replace the summary cell at the bottom with your work.
# =============================================================================
#
# DO NOT add a PEP 723 `# /// script` block: this notebook imports PyQGIS in the
# headless fallback, and uv would sandbox it without --system-site-packages.

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
        # New marimo + QGIS notebook

        > **This is a starter stub** created by the marimo QGIS plugin — a
        > minimal working example for you to build on. Add your own cells and
        > replace the summary at the bottom with your analysis.

        **What this demonstrates.** Connecting to the live QGIS project and
        summarising a layer — the smallest end-to-end example.

        **Dependencies.** The `qgis_bridge` client; a running QGIS with the
        marimo plugin enabled (live mode); `geopandas`. Without the plugin it
        falls back to a headless `QgsApplication` (no live layers).

        **How it works.** The plugin runs a localhost HTTP bridge; this notebook
        calls `project`, `list_layers` and `get_layer` over it.

        **▶ Run order** — this profile does not auto-run cells on open. Run them
        top to bottom (or *Run ▸ Run all cells*): **1)** connect · **2)** pick a
        layer (it is summarised below).
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

    # Make the qgis_bridge client importable (dev/symlink layout).
    _bridge_root = __BRIDGE_ROOT__
    if _bridge_root and _bridge_root not in sys.path:
        sys.path.insert(0, _bridge_root)

    from qgis_bridge import HeadlessQGIS, QgisBridge

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
        _msg = f"\U0001f7e2 **Live** — {_p.get('layer_count', 0)} layers in the project"
    else:
        _msg = "⚪ **Headless** — launch from QGIS to see live layers"
    mo.md(_msg)
    return


@app.cell
def _(mo):
    mo.md("### 2. Pick a layer — it is summarised below")
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
        options=names,
        value=names[0] if names else None,
        label="Layer",
        searchable=True,
        full_width=True,
    )
    layer
    return (layer,)


@app.cell
def _(layer, mo, mode, qgis):
    # Summarise the selected layer.
    if mode == "live" and layer.value:
        gdf = qgis.get_layer(layer.value)
        _attrs = gdf.drop(columns=[gdf.geometry.name])
        _out = mo.vstack(
            [
                mo.md(f"#### `{layer.value}` — {len(gdf)} features, CRS `{gdf.crs}`"),
                mo.ui.table(_attrs.head(50)),
            ]
        )
    else:
        _out = mo.md("_Pick a layer (live mode) to summarise it._")
    _out
    return


if __name__ == "__main__":
    app.run()
'''


def qgis_bridge_root():
    """Return the directory to put on sys.path so `import qgis_bridge` works.

    Resolves `qgis_bridge` whether it is bundled inside the plugin (zip install)
    or at the repo root (dev/symlink). Delegates to the shared helper.
    """
    from ..runtime import qgis_bridge_dir

    return qgis_bridge_dir()


def scaffold_notebook(bridge_root=None):
    """Return the text of a starter marimo + QGIS notebook."""
    return _TEMPLATE.replace("__BRIDGE_ROOT__", repr(bridge_root or ""))
