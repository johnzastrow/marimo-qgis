"""QGISBridgeAPI — the single point where the bridge touches the QGIS API.

This QObject lives on the Qt main thread. The HTTP server never calls its
handlers directly; it marshals each request here via
`QMetaObject.invokeMethod(..., BlockingQueuedConnection)` so every QGIS call runs
on the thread that owns the Qt/QGIS objects (see PLANNING.md §6, D3, D4).

Phase 1: project_state, list_layers, get_layer (vector -> FlatGeobuf).
Phase 2: get_layer_info, insert_layer, canvas_extent, selected_features.

`canvas_extent` and `selected_features` need `iface` (the QGIS desktop); when the
bridge runs without it (standalone/headless server, Phase 4) they return 503.
"""

from qgis.PyQt.QtCore import QBuffer, QByteArray, QIODevice, QObject, QSize, pyqtSlot
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsFeatureRequest,
    QgsMapRendererParallelJob,
    QgsMapSettings,
    QgsProject,
    QgsRasterLayer,
    QgsVectorLayer,
    QgsWkbTypes,
)

from .convert import layer_to_fgb, raster_to_tif

# Upper bound on an uploaded layer body (D2: bound everything). 256 MiB of
# FlatGeobuf is a very large vector layer for interactive analysis.
MAX_INSERT_BYTES = 256 * 1024 * 1024

# Upper bound on a rendered map dimension (D2). 4096 px is large for a notebook.
MAX_RENDER_PX = 4096


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

    def __init__(self, temp_store, iface=None, parent=None):
        super().__init__(parent)
        self._temp = temp_store
        self._iface = iface
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
            _log(f"dispatch error on {request.get('method')!r}: {exc!r}", "error")
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
        if method == "get_layer_info":
            return self._get_layer_info(request.get("name", ""))
        if method == "insert_layer":
            return self._insert_layer(request.get("name", ""), request.get("data"))
        if method == "canvas_extent":
            return self._canvas_extent()
        if method == "selected_features":
            return self._selected_features(request.get("name", ""))
        if method == "render_map":
            return self._render_map(request.get("width", 800), request.get("height", 600))
        if method == "list_algorithms":
            return self._list_algorithms()
        if method == "run_algorithm":
            return self._run_algorithm(request.get("alg_id", ""), request.get("params"))
        raise ApiError(404, "unknown method")

    # ---- read handlers ---------------------------------------------------

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
        layer = self._find_layer(name)
        if layer is None:
            raise ApiError(404, "layer not found")
        try:
            if isinstance(layer, QgsVectorLayer):
                path = self._temp.new_path(".fgb")
                layer_to_fgb(layer, path)
                return {"path": path, "format": "FlatGeobuf", "name": layer.name()}
            if isinstance(layer, QgsRasterLayer):
                path = self._temp.new_path(".tif")
                raster_to_tif(layer, path)
                return {"path": path, "format": "GeoTIFF", "name": layer.name()}
        except Exception as exc:  # noqa: BLE001
            _log(f"export failed for layer {name!r}: {exc!r}", "error")
            raise ApiError(500, "layer export failed")
        raise ApiError(404, "unsupported layer type")

    def _get_layer_info(self, name):
        layer = self._require_vector_layer(name)
        ext = layer.extent()
        return {
            "name": layer.name(),
            "crs": layer.crs().authid(),
            "feature_count": layer.featureCount(),
            "geometry_type": QgsWkbTypes.displayString(layer.wkbType()),
            "fields": [
                {"name": f.name(), "type": f.typeName()} for f in layer.fields()
            ],
            "extent": {
                "xmin": ext.xMinimum(),
                "ymin": ext.yMinimum(),
                "xmax": ext.xMaximum(),
                "ymax": ext.yMaximum(),
            },
        }

    def _canvas_extent(self):
        canvas = self._require_iface().mapCanvas()
        ext = canvas.extent()
        return {
            "xmin": ext.xMinimum(),
            "ymin": ext.yMinimum(),
            "xmax": ext.xMaximum(),
            "ymax": ext.yMaximum(),
            "crs": canvas.mapSettings().destinationCrs().authid(),
        }

    def _selected_features(self, name):
        iface = self._require_iface()
        layer = self._find_vector_layer(name) if name else iface.activeLayer()
        if not isinstance(layer, QgsVectorLayer):
            raise ApiError(404, "no vector layer (name not found or none active)")
        fids = layer.selectedFeatureIds()
        if not fids:
            raise ApiError(404, "no features selected")
        subset = layer.materialize(QgsFeatureRequest().setFilterFids(fids))
        path = self._temp.new_path(".fgb")
        layer_to_fgb(subset, path)
        return {
            "path": path,
            "format": "FlatGeobuf",
            "name": layer.name(),
            "count": len(fids),
        }

    # ---- write handler ---------------------------------------------------

    def _insert_layer(self, name, data):
        """Add an uploaded vector layer (FlatGeobuf bytes) to the project.

        The client uploads the layer bytes (D6) — the plugin writes them into
        its own private temp dir, never opening a client-supplied path. The
        features are copied into a memory layer so the project layer does not
        depend on the temp file (which is cleaned up on unload).
        """
        if not data:
            raise ApiError(400, "missing layer data")
        if len(data) > MAX_INSERT_BYTES:
            raise ApiError(413, "layer too large")
        name = name or "marimo_result"

        path = self._temp.new_path(".fgb")
        with open(path, "wb") as handle:
            handle.write(data)

        source = QgsVectorLayer(path, name, "ogr")
        if not source.isValid():
            raise ApiError(400, "uploaded data is not a valid vector layer")

        layer = source.materialize(QgsFeatureRequest())
        layer.setName(name)
        QgsProject.instance().addMapLayer(layer)
        return {
            "id": layer.id(),
            "name": layer.name(),
            "feature_count": layer.featureCount(),
        }

    # ---- render + processing ---------------------------------------------

    def _render_map(self, width, height):
        """Render the current map canvas to PNG bytes at the requested size."""
        canvas = self._require_iface().mapCanvas()
        width = max(1, min(int(width), MAX_RENDER_PX))
        height = max(1, min(int(height), MAX_RENDER_PX))

        settings = QgsMapSettings(canvas.mapSettings())
        settings.setOutputSize(QSize(width, height))

        job = QgsMapRendererParallelJob(settings)
        job.start()
        job.waitForFinished()

        buffer = QByteArray()
        device = QBuffer(buffer)
        device.open(QIODevice.OpenModeFlag.WriteOnly)
        job.renderedImage().save(device, "PNG")
        # Binary response (D-render): the server sends these bytes directly.
        return {"_bytes": bytes(buffer), "_content_type": "image/png"}

    def _list_algorithms(self):
        registry = QgsApplication.processingRegistry()
        algorithms = [
            {"id": alg.id(), "name": alg.displayName(), "group": alg.group()}
            for alg in registry.algorithms()
        ]
        return {"algorithms": algorithms}

    def _run_algorithm(self, alg_id, params):
        """Run a Processing algorithm; replace live-layer outputs with temp paths.

        `params` come from the client as JSON (INPUT may be a project layer name,
        which Processing resolves; OUTPUT is typically "TEMPORARY_OUTPUT"). Any
        QgsVectorLayer / QgsRasterLayer in the result is written to a temp file
        and returned as a path the client reads (the HTTP boundary cannot carry
        live layer objects — §6 run_algorithm note).
        """
        if not alg_id:
            raise ApiError(400, "missing algorithm id")
        import processing  # only available inside QGIS

        try:
            result = processing.run(alg_id, params or {})
        except Exception as exc:  # noqa: BLE001
            _log(f"run_algorithm {alg_id!r} failed: {exc!r}", "error")
            raise ApiError(400, "algorithm failed")

        out = {}
        for key, value in result.items():
            if isinstance(value, QgsVectorLayer):
                path = self._temp.new_path(".fgb")
                layer_to_fgb(value, path)
                out[key] = {"_layer": path, "format": "FlatGeobuf"}
            elif isinstance(value, QgsRasterLayer):
                path = self._temp.new_path(".tif")
                raster_to_tif(value, path)
                out[key] = {"_layer": path, "format": "GeoTIFF"}
            elif value is None or isinstance(value, (str, int, float, bool)):
                out[key] = value
            else:
                out[key] = str(value)  # stringify anything non-JSON-serialisable
        return {"result": out}

    # ---- helpers ---------------------------------------------------------

    def _require_iface(self):
        if self._iface is None:
            raise ApiError(503, "operation requires the QGIS desktop (no iface)")
        return self._iface

    def _require_vector_layer(self, name):
        if not name:
            raise ApiError(400, "missing layer name")
        layer = self._find_vector_layer(name)
        if layer is None:
            # 404 whether the name is unknown or non-vector — don't leak which.
            raise ApiError(404, "layer not found")
        return layer

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

    @staticmethod
    def _find_layer(name):
        """Resolve a layer NAME (case-insensitive, first match), any type.

        Name-only matching against the project — never a filesystem path (D2).
        """
        target = name.strip().lower()
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name().lower() == target:
                return layer
        return None
