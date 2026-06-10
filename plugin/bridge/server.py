"""QgisBridgeServer — a localhost HTTP bridge over the standard library.

Decision D1 (PLANNING.md §8): the server uses `http.server.ThreadingHTTPServer`
instead of aiohttp, so it needs nothing installed into QGIS's Python.

Threading model (D4): the HTTP server runs in its own daemon thread and handles
each request in a worker thread. Worker threads NEVER call the QGIS API directly
— they call `QgisBridgeServer.call_api`, which marshals the request to the Qt
main thread via `QMetaObject.invokeMethod(..., BlockingQueuedConnection)`, under
a lock so the single result slot on QGISBridgeAPI is concurrency-safe.

Security (D2): binds 127.0.0.1 only; every request must present the Bearer token;
unknown routes 404; missing/invalid token 401; errors return a generic message.

The HTTP handler depends only on `bridge.auth` and `bridge.call_api`, so the
routing/auth layer is unit-testable without a running QGIS (the Qt import is
deferred to `call_api`).
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

from .auth import TokenAuth


def route(path):
    """Map a URL path to a request dict, or None if no route matches.

    Phase 1 (GET only):
        /api/project          -> project_state
        /api/layers           -> list_layers
        /api/layer/<name>     -> get_layer(name)
    """
    parts = [p for p in path.split("/") if p]
    if parts == ["api", "project"]:
        return {"method": "project_state"}
    if parts == ["api", "layers"]:
        return {"method": "list_layers"}
    if len(parts) == 3 and parts[0] == "api" and parts[1] == "layer":
        return {"method": "get_layer", "name": unquote(parts[2])}
    return None


def make_handler(bridge):
    """Build a request handler bound to `bridge` (needs .auth and .call_api)."""

    class _Handler(BaseHTTPRequestHandler):
        server_version = "marimoQGISBridge/1"
        protocol_version = "HTTP/1.1"

        # Silence the default stderr access log; the plugin logs via QGIS.
        def log_message(self, fmt, *args):
            pass

        def _send_json(self, status, payload):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            # Auth first — fail closed on any deviation.
            if not bridge.auth.authorize(self.headers.get("Authorization")):
                self._send_json(401, {"error": "unauthorized"})
                return

            request = route(urlparse(self.path).path)
            if request is None:
                self._send_json(404, {"error": "unknown endpoint"})
                return

            result = bridge.call_api(request)
            if isinstance(result, dict) and "_error" in result:
                self._send_json(result.get("_status", 500), {"error": result["_error"]})
                return
            self._send_json(200, result)

    return _Handler


class QgisBridgeServer:
    """Owns the HTTP server thread and the bridge -> Qt-main-thread dispatch."""

    def __init__(self, api, auth=None, host="127.0.0.1"):
        self._api = api
        self.auth = auth or TokenAuth()
        self._dispatch_lock = threading.Lock()
        # Bind to port 0 so the OS assigns a free ephemeral port.
        self._httpd = ThreadingHTTPServer((host, 0), make_handler(self))
        self._thread = None

    @property
    def port(self):
        return self._httpd.server_address[1]

    @property
    def token(self):
        return self.auth.token

    def start(self):
        self._thread = threading.Thread(
            target=self._httpd.serve_forever, name="marimo-bridge", daemon=True
        )
        self._thread.start()
        return self

    def stop(self):
        """Shut down the server and join its thread (call from the main thread)."""
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def call_api(self, request):
        """Marshal `request` to QGISBridgeAPI on the Qt main thread.

        Serialised by a lock so QGISBridgeAPI's single result slot is safe across
        concurrent worker threads (D4). Qt symbols are imported lazily so this
        module stays importable (and testable) without QGIS.
        """
        from qgis.PyQt.QtCore import QMetaObject, Qt, Q_ARG

        with self._dispatch_lock:
            QMetaObject.invokeMethod(
                self._api,
                "dispatch",
                Qt.ConnectionType.BlockingQueuedConnection,
                Q_ARG("PyQt_PyObject", request),
            )
            return self._api.take_result()
