"""Process-wide handle to the running bridge server.

Processing algorithms are instantiated by QGIS, not by the plugin object, so they
cannot reach the plugin instance to learn the bridge port/token. This tiny module
holds a reference set by the plugin on startup and read by any code that launches
a notebook, so the launched notebook inherits the bridge connection.
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
