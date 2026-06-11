"""Process-wide handle to the running bridge server.

Holds a reference set by the plugin on startup and read by MarimoProcessManager
when it launches a notebook, so the notebook inherits the bridge connection
(MARIMO_QGIS_PORT / MARIMO_QGIS_TOKEN) without threading the server object through
every caller.
"""

import os

_server = None


def qgis_bridge_dir():
    """Return the directory to add to a notebook's PYTHONPATH so `import
    qgis_bridge` works, or None if it cannot be found.

    The `qgis_bridge` package ships either INSIDE the plugin (QGIS-repo / zip
    install: `<plugin>/qgis_bridge`) or at the repo root next to the plugin
    (dev / symlink install: `<repo>/qgis_bridge`). Return whichever parent
    directory actually contains it.
    """
    plugin_dir = os.path.dirname(os.path.realpath(__file__))  # this file is in plugin/
    for candidate in (plugin_dir, os.path.dirname(plugin_dir)):
        if os.path.isdir(os.path.join(candidate, "qgis_bridge")):
            return candidate
    return None


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
