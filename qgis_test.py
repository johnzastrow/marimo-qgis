# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "marimo",
# ]
# ///

import marimo

__generated_with = "0.21.1"

app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    mo.md("""# QGIS4 + Marimo""")
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

    return Qgis, QgsApplication, qgs


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
