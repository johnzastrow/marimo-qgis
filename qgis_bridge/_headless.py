"""HeadlessQGIS — the fallback when a notebook runs without the QGIS plugin.

When `MARIMO_QGIS_PORT`/`TOKEN` are absent (notebook launched from the terminal,
no plugin), `QgisBridge()` raises and the notebook falls back to this: it
initialises its own headless `QgsApplication` so PyQGIS works, and reads vector
files from disk into GeoDataFrames.

There is no live project in headless mode, so `list_layers()` is empty and
`get_layer()` takes a **file path** rather than a project layer name.
"""


class HeadlessQGIS:
    """Self-contained headless QGIS context (own QgsApplication)."""

    is_live = False

    def __init__(self):
        import os
        import sys

        # Make PyQGIS importable and force the offscreen Qt platform before any
        # QgsApplication is created (the only point Qt reads QT_QPA_PLATFORM).
        if "/usr/share/qgis/python" not in sys.path:
            sys.path.insert(0, "/usr/share/qgis/python")
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

        from qgis.core import QgsApplication

        self._app = QgsApplication([], False)
        self._app.initQgis()

    def project(self):
        """No live project in headless mode."""
        return {"live": False, "title": None, "file_name": None, "layer_count": 0}

    def list_layers(self):
        """Headless has no running project — returns an empty list."""
        return []

    def get_layer(self, path):
        """Read a vector file from disk into a GeoDataFrame.

        In headless mode the argument is a filesystem path (not a project layer
        name), since there is no live project to resolve names against.
        """
        import geopandas as gpd

        return gpd.read_file(path)
