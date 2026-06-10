"""Generate a starter marimo + QGIS notebook for the dock's "New…" button.

The scaffold connects to the live bridge (falling back to headless), lets the user
pick a vector layer, and summarises it — a runnable starting point.

`qgis_bridge` must be importable in the notebook venv. In the dev/symlink layout
it lives next to the plugin's repo root, so we inject that path; once `qgis_bridge`
is installed (PyPI, Phase 4) the injected path is simply unused.
"""

import os

# The notebook body. A sentinel (not str.format) is used for substitution because
# the template itself contains f-string braces.
_TEMPLATE = '''# DO NOT add a PEP 723 `# /// script` block: this notebook imports PyQGIS in the
# headless fallback, and uv would sandbox it without --system-site-packages.
# Created by the marimo QGIS plugin.

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

        **What this demonstrates.** A starting point that reads the live QGIS
        project and summarises a layer. Replace the last cell with your own
        analysis.

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

    In the dev/symlink layout `qgis_bridge` sits at the repo root, next to the
    `plugin/` package this file lives in. Returns that root, or None if not found
    (e.g. a zip-installed plugin — then the notebook relies on an installed
    qgis_bridge).
    """
    plugin_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    repo_root = os.path.dirname(plugin_dir)
    if os.path.isdir(os.path.join(repo_root, "qgis_bridge")):
        return repo_root
    return None


def scaffold_notebook(bridge_root=None):
    """Return the text of a starter marimo + QGIS notebook."""
    return _TEMPLATE.replace("__BRIDGE_ROOT__", repr(bridge_root or ""))
