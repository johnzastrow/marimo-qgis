"""QGISBridgeAPI — the single point where the bridge touches the QGIS API.

This QObject lives on the Qt main thread. The HTTP server never calls its
handlers directly; it marshals each request here via
`QMetaObject.invokeMethod(..., BlockingQueuedConnection)` so every QGIS call runs
on the thread that owns the Qt/QGIS objects (see PLANNING.md §6, D3, D4).

Phase 1 methods: project_state, list_layers, get_layer (vector -> FlatGeobuf).
"""

from qgis.PyQt.QtCore import QObject, pyqtSlot
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsProject,
    QgsVectorLayer,
)

from .convert import layer_to_fgb


def _log(message, level="info"):
    """Write to the QGIS 'marimo bridge' log tab. Details stay server-side."""
    levels = {
        "info": Qgis.MessageLevel.Info,
        "warning": Qgis.MessageLevel.Warning,
        "error": Qgis.MessageLevel.Critical,
    }
    QgsApplication.messageLog().logMessage(
        message, "marimo bridge", levels.get(level, Qgis.MessageLevel.Info)
    )


class ApiError(Exception):
    """Handler-level error carrying an HTTP status and a safe, generic message."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


class QGISBridgeAPI(QObject):
    """All QGIS reads/writes for the bridge. Main-thread only."""

    def __init__(self, temp_store, parent=None):
        super().__init__(parent)
        self._temp = temp_store
        self._result = None

    # ---- main-thread entry point (called via invokeMethod) ---------------

    @pyqtSlot("PyQt_PyObject")
    def dispatch(self, request):
        """Run a request dict on the main thread and stash the result.

        The result is read back via take_result() after the blocking invoke
        returns. The server serialises calls with a lock, so the single
        `_result` slot is safe across concurrent HTTP worker threads (D4).

        On error, stores a dict with `_error` (generic message) and `_status`
        (HTTP code) — fail closed, with detail sent only to the QGIS log.
        """
        try:
            self._result = self._handle(request)
        except ApiError as exc:
            self._result = {"_error": exc.message, "_status": exc.status}
        except Exception as exc:  # noqa: BLE001 — last-resort guard, must not propagate
            _log(f"dispatch error on {request!r}: {exc!r}", "error")
            self._result = {"_error": "internal error", "_status": 500}

    def take_result(self):
        """Return the last result and clear it."""
        result, self._result = self._result, None
        return result

    # ---- request handling ------------------------------------------------

    def _handle(self, request):
        method = request.get("method")
        if method == "project_state":
            return self._project_state()
        if method == "list_layers":
            return self._list_layers()
        if method == "get_layer":
            return self._get_layer(request.get("name", ""))
        raise ApiError(404, "unknown method")

    def _project_state(self):
        project = QgsProject.instance()
        return {
            "title": project.title(),
            "file_name": project.fileName(),
            "crs": project.crs().authid(),
            "layer_count": project.count(),
        }

    def _list_layers(self):
        layers = []
        for layer in QgsProject.instance().mapLayers().values():
            is_vector = isinstance(layer, QgsVectorLayer)
            layers.append(
                {
                    "id": layer.id(),
                    "name": layer.name(),
                    "type": "vector" if is_vector else layer.__class__.__name__,
                    "crs": layer.crs().authid(),
                    "feature_count": layer.featureCount() if is_vector else None,
                }
            )
        return {"layers": layers}

    def _get_layer(self, name):
        if not name:
            raise ApiError(400, "missing layer name")
        layer = self._find_vector_layer(name)
        if layer is None:
            # 404 whether the name is unknown or non-vector — don't leak which.
            raise ApiError(404, "layer not found")
        path = self._temp.new_path(".fgb")
        try:
            layer_to_fgb(layer, path)
        except Exception as exc:  # noqa: BLE001
            _log(f"export failed for layer {name!r}: {exc!r}", "error")
            raise ApiError(500, "layer export failed")
        return {"path": path, "format": "FlatGeobuf", "name": layer.name()}

    @staticmethod
    def _find_vector_layer(name):
        """Resolve a layer NAME (case-insensitive, first match) to a vector layer.

        Client input is matched against project layer names only — it is never
        treated as a file path, so there is no traversal surface (D2).
        """
        target = name.strip().lower()
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsVectorLayer) and layer.name().lower() == target:
                return layer
        return None
