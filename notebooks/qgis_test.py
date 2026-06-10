# DO NOT add a PEP 723 `# /// script` block to QGIS notebooks.
# When marimo is launched via `uv run`, it auto-sandboxes any notebook that
# has inline script metadata, creating a fresh isolated environment without
# --system-site-packages.  That environment has no PyQt6, so every
# `from qgis.core import ...` fails with ModuleNotFoundError.
# Manage dependencies via the project venv instead — build it with
# ./qgis-env.sh setup, which targets QGIS's own Python (no version pin):
#   ./qgis-env.sh setup
#
# Run with:  uv run marimo edit notebooks/qgis_test.py
#            uv run marimo run  notebooks/qgis_test.py
#
# No wrapper script is needed.  The QGIS init cell handles both
# sys.path (equivalent to PYTHONPATH) and QT_QPA_PLATFORM before
# QgsApplication is created — the only point at which Qt reads them.

import marimo

__generated_with = "0.21.1"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md(
        """
        **What this demonstrates.** A smoke test — confirms the PyQGIS bindings
        import and initialise, and prints the running QGIS version.

        **Dependencies.** PyQGIS only (its own headless `QgsApplication`). No data
        file, no plugin/bridge.

        **How it works.** Initialises `QgsApplication` and reads version info.
        **▶ Run the cells in order, top to bottom** (this profile does not
        auto-run on open; or use *Run ▸ Run all cells*).
        """
    )
    return


@app.cell
def _(mo):
    mo.md("""
    # QGIS4 + Marimo
    """)
    return


@app.cell
def _():
    import sys
    import os

    sys.path.insert(0, "/usr/share/qgis/python")

    # QGIS needs QgsApplication initialized before most APIs work.
    # Pass gui=False for headless/offscreen use.
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from qgis.core import QgsApplication, Qgis

    qgs = QgsApplication([], False)
    qgs.initQgis()
    return (Qgis,)


@app.cell
def _(Qgis, mo):
    mo.md(f"""
    ## QGIS Version Info

    | Field | Value |
    |-------|-------|
    | Version string | `{Qgis.version()}` |
    | Version int | `{Qgis.versionInt()}` |
    | Release name | `{Qgis.releaseName()}` |
    """)
    return


@app.cell
def _(mo):
    import glob as _glob

    _sample_files = (
        _glob.glob("/usr/share/qgis/resources/data/**/*.gpkg", recursive=True)
        + _glob.glob("/usr/share/qgis/resources/data/**/*.shp", recursive=True)
    )

    _msg = (
        "**Sample QGIS data files found:**\n" + "\n".join(f"- `{f}`" for f in _sample_files[:5])
        if _sample_files
        else "_No sample `.gpkg`/`.shp` files found in `/usr/share/qgis/resources/data/`._"
    )
    mo.md(_msg)
    return


if __name__ == "__main__":
    app.run()
