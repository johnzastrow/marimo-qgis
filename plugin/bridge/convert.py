"""Layer <-> file conversion and the private temp store for layer transfers.

The HTTP boundary cannot carry live PyQGIS objects, so vector layers are written
to a temporary FlatGeobuf file and the path is returned to the client, which
reads it with geopandas. (Raster -> GeoTIFF arrives in Phase 2.)

Security notes:
- All transfer files live in a single per-server directory created with
  `mkdtemp` and chmod 0700, so other local users cannot read exported data.
- File names are unguessable (`secrets.token_hex`), not derived from layer names
  or any client input — no path traversal, no collisions.
- `cleanup()` removes the whole directory; the plugin calls it on unload.
"""

import os
import secrets
import shutil
import tempfile


class TempStore:
    """Owns a private temp directory for layer-transfer files."""

    def __init__(self):
        self._dir = tempfile.mkdtemp(prefix="marimo_qgis_bridge_")
        # mkdtemp already creates 0700, but set it explicitly to be certain.
        os.chmod(self._dir, 0o700)

    @property
    def directory(self):
        return self._dir

    def new_path(self, suffix):
        """Return a fresh, unguessable file path inside the store."""
        return os.path.join(self._dir, secrets.token_hex(16) + suffix)

    def cleanup(self):
        """Delete the directory and everything in it. Safe to call twice."""
        shutil.rmtree(self._dir, ignore_errors=True)


def layer_to_fgb(layer, path):
    """Export a vector layer to FlatGeobuf at `path` using native:savefeatures.

    MUST run on the Qt main thread (it calls into the Processing framework);
    QGISBridgeAPI is the only caller.

    Returns:
        `path` on success.

    Raises:
        RuntimeError: if the algorithm produced no output file.
    """
    import processing  # imported lazily; only available inside QGIS

    processing.run("native:savefeatures", {"INPUT": layer, "OUTPUT": path})
    if not os.path.exists(path):
        raise RuntimeError("native:savefeatures produced no output file")
    return path
