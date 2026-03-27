# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "marimo",
# ]
# ///

import marimo as mo

__generated_with = "0.21.1"

app = mo.App()


@app.cell
def _():
    import sys as _sys

    _sys.path.insert(0, "/usr/share/qgis/python")
    import marimo as _mo

    _mo.md("# QGIS4 + Marimo Test")
    return


@app.cell
def _():
    import sys as _sys

    _sys.path.insert(0, "/usr/share/qgis/python")
    from qgis.core import Qgis as _Qgis

    qgis_info = {
        "QGIS Version": _Qgis.version(),
        "QGIS VERSION": _Qgis.QGIS_VERSION,
    }
    return (qgis_info,)
