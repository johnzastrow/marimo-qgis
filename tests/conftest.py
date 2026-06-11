"""Shared test fixtures: a stub bridge + a running stdlib HTTP server.

These tests exercise the bridge's transport, auth, routing and the qgis_bridge
client WITHOUT a running QGIS. The QGIS-side `QGISBridgeAPI` (which calls
`QgsProject`, `processing.run`, the renderer, ...) is replaced by `StubBridge`,
so the security-critical and protocol surface is covered on a plain runner.
"""

import sys
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

# Make the repo root importable (plugin.*, qgis_bridge).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from plugin.bridge.auth import TokenAuth  # noqa: E402
from plugin.bridge.server import make_handler  # noqa: E402

TOKEN = "test-token-123"
FAKE_PNG = b"\x89PNG\r\n\x1a\nFAKE"


class StubBridge:
    """Stands in for QgisBridgeServer: real auth, canned `call_api` (no QGIS)."""

    def __init__(self):
        self.auth = TokenAuth(token=TOKEN)
        self.calls = []

    def call_api(self, request):
        self.calls.append(request)
        method = request["method"]
        if method == "project_state":
            return {"title": "Demo", "file_name": "", "crs": "EPSG:4326", "layer_count": 2}
        if method == "list_layers":
            return {"layers": [{"name": "roads", "type": "vector", "crs": "EPSG:4326"}]}
        if method == "get_layer":
            if request["name"] == "roads":
                return {"path": "/tmp/x.fgb", "format": "FlatGeobuf", "name": "roads"}
            return {"_error": "layer not found", "_status": 404}
        if method == "get_layer_info":
            return {"name": request["name"], "fields": [], "feature_count": 3}
        if method == "canvas_extent":
            return {"xmin": 0, "ymin": 0, "xmax": 1, "ymax": 1, "crs": "EPSG:4326"}
        if method == "selected_features":
            return {"path": "/tmp/s.fgb", "count": 2, "name": request["name"] or "active"}
        if method == "insert_layer":
            return {"id": "mem_1", "name": request["name"], "feature_count": len(request["data"])}
        if method == "render_map":
            return {"_bytes": FAKE_PNG, "_content_type": "image/png"}
        if method == "list_algorithms":
            return {"algorithms": [{"id": "native:buffer", "name": "Buffer", "group": "Vector"}]}
        if method == "run_algorithm":
            return {"result": {"COUNT": 42, "AREA": 3.14}}
        return {"_error": "unknown method", "_status": 404}


@pytest.fixture
def bridge():
    return StubBridge()


@pytest.fixture
def server(bridge):
    """A running ThreadingHTTPServer wired to the stub bridge. Yields (httpd, port)."""
    import threading

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(bridge))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd, httpd.server_address[1]
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)
