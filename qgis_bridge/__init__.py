"""qgis_bridge — notebook-side client for the marimo↔QGIS bridge.

Two ways to get a handle:

    from qgis_bridge import QgisBridge, HeadlessQGIS
    try:
        qgis = QgisBridge()       # live: plugin is running, talk to its project
    except RuntimeError:
        qgis = HeadlessQGIS()     # fallback: own headless QgsApplication

`QgisBridge` is a pure HTTP client (stdlib `urllib`) with no QGIS dependency, so
this package installs into any venv. `get_layer()` additionally needs `geopandas`
to materialise the returned FlatGeobuf as a GeoDataFrame.

Connection details come only from the environment the plugin injects:
`MARIMO_QGIS_PORT` and `MARIMO_QGIS_TOKEN`. If either is absent, `QgisBridge()`
raises `RuntimeError` so the fallback above triggers.
"""

import os
from urllib.parse import quote

from ._client import BridgeError, Client
from ._headless import HeadlessQGIS

__all__ = ["QgisBridge", "HeadlessQGIS", "BridgeError"]


class QgisBridge:
    """Client for the live QGIS project served by the plugin's bridge."""

    is_live = True

    def __init__(self):
        port = os.environ.get("MARIMO_QGIS_PORT")
        token = os.environ.get("MARIMO_QGIS_TOKEN")
        if not port or not token:
            raise RuntimeError(
                "Not running under the QGIS bridge "
                "(MARIMO_QGIS_PORT/MARIMO_QGIS_TOKEN unset). "
                "Launch the notebook from QGIS, or use HeadlessQGIS()."
            )
        self._client = Client(port, token)

    def project(self):
        """Return a dict describing the live QGIS project (title, CRS, count)."""
        return self._client.get("/api/project")

    def list_layers(self):
        """Return the list of layers in the live project (name, type, CRS, ...)."""
        return self._client.get("/api/layers")["layers"]

    def get_layer(self, name):
        """Return a project vector layer (resolved by name) as a GeoDataFrame."""
        import geopandas as gpd

        info = self._client.get("/api/layer/" + quote(name, safe=""))
        return gpd.read_file(info["path"])

    def layer_info(self, name):
        """Return metadata for a project layer (fields, CRS, extent, geometry)."""
        return self._client.get("/api/layer-info/" + quote(name, safe=""))

    def get_canvas_extent(self):
        """Return the current map-canvas extent and CRS (live QGIS only)."""
        return self._client.get("/api/extent")

    def get_selected_features(self, layer=None):
        """Return selected features of `layer` (or the active layer) as a GeoDataFrame."""
        import geopandas as gpd

        path = "/api/selected"
        if layer:
            path += "?layer=" + quote(layer, safe="")
        info = self._client.get(path)
        return gpd.read_file(info["path"])

    def insert_layer(self, gdf, name="marimo_result"):
        """Push a GeoDataFrame into the live QGIS project as a new memory layer.

        Returns the new layer's id/name/feature_count. The GeoDataFrame is sent
        as FlatGeobuf bytes (the plugin owns the file path it writes; see D6).
        """
        import os
        import tempfile

        fd, tmp = tempfile.mkstemp(suffix=".fgb")
        os.close(fd)
        try:
            gdf.to_file(tmp, driver="FlatGeobuf")
            with open(tmp, "rb") as handle:
                data = handle.read()
        finally:
            os.unlink(tmp)
        return self._client.post("/api/insert?name=" + quote(name, safe=""), data)
