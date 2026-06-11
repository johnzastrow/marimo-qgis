"""Transport/auth/routing tests for the stdlib bridge server (no QGIS)."""

import json
import urllib.error
import urllib.request

from conftest import FAKE_PNG, TOKEN

from plugin.bridge.server import route_get


def _request(port, path, method="GET", data=None, token=TOKEN, content_type=None):
    url = f"http://127.0.0.1:{port}{path}"
    req = urllib.request.Request(url, data=data, method=method)
    if token is not None:
        req.add_header("Authorization", f"Bearer {token}")
    if content_type:
        req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read()
            return resp.status, resp.headers.get("Content-Type"), body
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers.get("Content-Type"), exc.read()


# ---- routing (pure function) ---------------------------------------------


def test_route_get_known_endpoints():
    assert route_get("/api/project") == {"method": "project_state"}
    assert route_get("/api/layers") == {"method": "list_layers"}
    assert route_get("/api/extent") == {"method": "canvas_extent"}
    assert route_get("/api/algorithms") == {"method": "list_algorithms"}
    assert route_get("/api/layer/roads") == {"method": "get_layer", "name": "roads"}
    assert route_get("/api/layer-info/roads") == {
        "method": "get_layer_info",
        "name": "roads",
    }
    assert route_get("/api/selected?layer=roads") == {
        "method": "selected_features",
        "name": "roads",
    }
    assert route_get("/api/render?width=10&height=20") == {
        "method": "render_map",
        "width": "10",
        "height": "20",
    }


def test_route_get_decodes_names_and_rejects_unknown():
    assert route_get("/api/layer/My%20Layer")["name"] == "My Layer"
    assert route_get("/api/bogus") is None
    assert route_get("/api/layer") is None  # missing name


# ---- auth (fail closed) ---------------------------------------------------


def test_auth_required(server):
    _, port = server
    assert _request(port, "/api/layers", token=None)[0] == 401
    assert _request(port, "/api/layers", token="wrong-token")[0] == 401
    assert _request(port, "/api/layers")[0] == 200


def test_localhost_only(server):
    httpd, _ = server
    assert httpd.server_address[0] == "127.0.0.1"


# ---- GET endpoints --------------------------------------------------------


def test_get_endpoints_ok(server):
    _, port = server
    for path in ("/api/project", "/api/layers", "/api/extent", "/api/algorithms",
                 "/api/layer/roads", "/api/layer-info/roads", "/api/selected"):
        status, ctype, _ = _request(port, path)
        assert status == 200, path
        assert "application/json" in ctype, path


def test_get_layer_unknown_is_404(server):
    _, port = server
    status, _, _ = _request(port, "/api/layer/ghost")
    assert status == 404


def test_unknown_endpoint_404(server):
    _, port = server
    assert _request(port, "/api/nope")[0] == 404


# ---- binary response (render) --------------------------------------------


def test_render_returns_png_bytes(server):
    _, port = server
    status, ctype, body = _request(port, "/api/render?width=4&height=4")
    assert status == 200
    assert ctype == "image/png"
    assert body == FAKE_PNG


# ---- POST endpoints -------------------------------------------------------


def test_post_insert_ok_and_bounds(server):
    _, port = server
    status, _, body = _request(
        port, "/api/insert?name=buf", method="POST", data=b"12345"
    )
    assert status == 200
    assert json.loads(body) == {"id": "mem_1", "name": "buf", "feature_count": 5}

    # empty body -> 400
    assert _request(port, "/api/insert", method="POST", data=b"")[0] == 400


def test_post_run_ok_and_bad_json(server):
    _, port = server
    payload = json.dumps({"alg_id": "native:buffer", "params": {"X": 1}}).encode()
    status, _, body = _request(
        port, "/api/run", method="POST", data=payload, content_type="application/json"
    )
    assert status == 200
    assert json.loads(body) == {"result": {"COUNT": 42, "AREA": 3.14}}

    # invalid JSON -> 400
    bad = _request(
        port, "/api/run", method="POST", data=b"not json",
        content_type="application/json",
    )
    assert bad[0] == 400


def test_post_unknown_endpoint_404(server):
    _, port = server
    assert _request(port, "/api/nope", method="POST", data=b"x")[0] == 404


def test_post_requires_auth(server):
    _, port = server
    assert _request(port, "/api/insert", method="POST", data=b"x", token=None)[0] == 401


# ---- error mapping --------------------------------------------------------


def test_api_error_maps_to_status(server, bridge):
    _, port = server
    # StubBridge returns {"_error": ..., "_status": 404} for an unknown layer.
    status, ctype, body = _request(port, "/api/layer/ghost")
    assert status == 404
    assert json.loads(body) == {"error": "layer not found"}
