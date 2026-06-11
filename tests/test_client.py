"""Tests for the qgis_bridge client against the stub server (no QGIS).

Covers the stdlib-only paths. Methods that materialise files into GeoDataFrames
(`get_layer`, `get_selected_features`, `insert_layer`) wrap the same HTTP calls
exercised in test_server.py plus a `geopandas` read, so they are not re-tested
here to keep CI free of heavy geo dependencies.
"""

import os

import pytest

from conftest import FAKE_PNG, TOKEN

from qgis_bridge import BridgeError, QgisBridge


@pytest.fixture
def client(server, monkeypatch):
    """A QgisBridge pointed at the stub server via the env vars it reads."""
    _, port = server
    monkeypatch.setenv("MARIMO_QGIS_PORT", str(port))
    monkeypatch.setenv("MARIMO_QGIS_TOKEN", TOKEN)
    return QgisBridge()


def test_no_env_raises_runtime_error(monkeypatch):
    monkeypatch.delenv("MARIMO_QGIS_PORT", raising=False)
    monkeypatch.delenv("MARIMO_QGIS_TOKEN", raising=False)
    with pytest.raises(RuntimeError):
        QgisBridge()


def test_project_round_trip(client):
    assert client.is_live is True
    assert client.project()["title"] == "Demo"


def test_list_layers_round_trip(client):
    names = [layer["name"] for layer in client.list_layers()]
    assert names == ["roads"]


def test_layer_info_and_extent(client):
    assert client.layer_info("roads")["feature_count"] == 3
    extent = client.get_canvas_extent()
    assert extent["crs"] == "EPSG:4326"


def test_render_map_returns_bytes(client):
    assert client.render_map(640, 480) == FAKE_PNG


def test_run_algorithm_scalar_passthrough(client):
    result = client.run_algorithm("native:buffer", {"INPUT": "roads"})
    assert result == {"COUNT": 42, "AREA": 3.14}


def test_wrong_token_raises_bridge_error(server, monkeypatch):
    _, port = server
    monkeypatch.setenv("MARIMO_QGIS_PORT", str(port))
    monkeypatch.setenv("MARIMO_QGIS_TOKEN", "WRONG")
    bad = QgisBridge()
    with pytest.raises(BridgeError) as excinfo:
        bad.project()
    assert "401" in str(excinfo.value)


def test_list_algorithms_dataframe(client):
    pd = pytest.importorskip("pandas")  # only this test needs pandas
    frame = client.list_algorithms()
    assert isinstance(frame, pd.DataFrame)
    assert list(frame["id"]) == ["native:buffer"]


def test_unreachable_server_raises_bridge_error(monkeypatch):
    # Point at a closed port to exercise the URLError branch.
    monkeypatch.setenv("MARIMO_QGIS_PORT", "1")  # port 1: connection refused
    monkeypatch.setenv("MARIMO_QGIS_TOKEN", TOKEN)
    client = QgisBridge()
    with pytest.raises(BridgeError):
        client.project()


def test_repo_root_on_path():
    # Sanity: the package imports without QGIS (qgis_bridge is QGIS-free).
    assert "qgis_bridge" in os.sys.modules
