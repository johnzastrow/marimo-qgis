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

import json
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
        """Return a project layer (resolved by name) from the live project.

        Vector layers come back as a GeoDataFrame (geopandas); raster layers as
        an xarray DataArray (rioxarray, an optional dependency).
        """
        info = self._client.get("/api/layer/" + quote(name, safe=""))
        if info.get("format") == "GeoTIFF":
            try:
                import rioxarray
            except ImportError:
                raise BridgeError(
                    "reading raster layers needs rioxarray (pip install rioxarray)"
                ) from None
            return rioxarray.open_rasterio(info["path"])
        import geopandas as gpd

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

    def render_map(self, width=800, height=600):
        """Render the live QGIS map canvas and return PNG bytes.

        Pass the result to `marimo.image(...)` to show it in a cell.
        """
        return self._client.get_bytes(
            f"/api/render?width={int(width)}&height={int(height)}"
        )

    def list_algorithms(self):
        """Return the Processing algorithm registry (id/name/group) as a DataFrame."""
        import pandas as pd

        return pd.DataFrame(self._client.get("/api/algorithms")["algorithms"])

    def run_algorithm(self, alg_id, params=None):
        """Run a Processing algorithm and return its result dict.

        Layer outputs (TEMPORARY_OUTPUT) come back as temp-file paths and are
        read into GeoDataFrames (vector) or rioxarray DataArrays (raster);
        scalar outputs (counts, areas, ...) pass through unchanged.
        """
        body = json.dumps({"alg_id": alg_id, "params": params or {}}).encode("utf-8")
        result = self._client.post("/api/run", body, content_type="application/json")
        out = {}
        for key, value in result["result"].items():
            if isinstance(value, dict) and "_layer" in value:
                if value.get("format") == "GeoTIFF":
                    import rioxarray

                    out[key] = rioxarray.open_rasterio(value["_layer"])
                else:
                    import geopandas as gpd

                    out[key] = gpd.read_file(value["_layer"])
            else:
                out[key] = value
        return out
