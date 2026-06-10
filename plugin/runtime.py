"""Process-wide handle to the running bridge server.

Holds a reference set by the plugin on startup and read by MarimoProcessManager
when it launches a notebook, so the notebook inherits the bridge connection
(MARIMO_QGIS_PORT / MARIMO_QGIS_TOKEN) without threading the server object through
every caller.
"""

_server = None


def set_server(server):
    """Record the running QgisBridgeServer (or None to clear on unload)."""
    global _server
    _server = server


def bridge_env():
    """Return the env vars that connect a notebook to the live bridge.

    Empty dict if no bridge is running, so callers can `env.update(bridge_env())`
    unconditionally.
    """
    if _server is None:
        return {}
    return {
        "MARIMO_QGIS_PORT": str(_server.port),
        "MARIMO_QGIS_TOKEN": _server.token,
    }
