"""HeadlessQGIS — the fallback when a notebook runs without the QGIS plugin.

When `MARIMO_QGIS_PORT`/`TOKEN` are absent (notebook launched from the terminal,
no plugin), `QgisBridge()` raises and the notebook falls back to this: it
initialises its own headless `QgsApplication` so PyQGIS works, and reads vector
files from disk into GeoDataFrames.

There is no live project in headless mode, so `list_layers()` is empty and
`get_layer()` takes a **file path** rather than a project layer name.
"""


def _pyqgis_candidates():
    """Likely PyQGIS-bindings directories for the current OS (version-agnostic).

    Only used as a fallback: a venv built against QGIS's own interpreter usually
    has `qgis` importable already. On a Linux *system* install the bindings live
    outside site-packages, so the directory must be added to sys.path.
    """
    import glob
    import os
    import sys

    if sys.platform.startswith("linux"):
        return ["/usr/share/qgis/python"]
    if sys.platform == "darwin":
        return sorted(
            glob.glob("/Applications/QGIS*.app/Contents/Resources/python"),
            reverse=True,
        )
    if sys.platform == "win32":
        roots = {
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramW6432", r"C:\Program Files"),
        }
        found = []
        for root in roots:
            found += glob.glob(os.path.join(root, "QGIS*", "apps", "qgis", "python"))
        return sorted(set(found), reverse=True)
    return []


class HeadlessQGIS:
    """Self-contained headless QGIS context (own QgsApplication)."""

    is_live = False

    def __init__(self):
        import os
        import sys

        # Force the offscreen Qt platform before any QgsApplication is created
        # (the only point Qt reads QT_QPA_PLATFORM).
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

        # Prefer the interpreter's own qgis (venv built against QGIS's Python);
        # otherwise add a known PyQGIS location for this OS and retry.
        try:
            from qgis.core import QgsApplication
        except ImportError:
            for candidate in _pyqgis_candidates():
                if os.path.isdir(candidate) and candidate not in sys.path:
                    sys.path.insert(0, candidate)
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
