"""Process-wide handle to the running bridge server.

Holds a reference set by the plugin on startup and read by MarimoProcessManager
when it launches a notebook, so the notebook inherits the bridge connection
(MARIMO_QGIS_PORT / MARIMO_QGIS_TOKEN) without threading the server object through
every caller.
"""

import os
import shutil
import sys

_server = None


def uv_executable():
    """Return the absolute path to the `uv` binary, or None if not found.

    QGIS on Windows is launched through the OSGeo4W shell, which rebuilds PATH
    and typically drops the user's `~/.local/bin` — exactly where the standalone
    uv installer puts `uv.exe`. So resolving `uv` from PATH alone (the implicit
    behaviour of `subprocess.Popen(["uv", ...])`) fails inside QGIS even though
    `uv` works fine in a normal terminal. We therefore resolve explicitly:

      1. an explicit override (`MARIMO_QGIS_UV` env var) wins;
      2. then PATH (correct whenever QGIS inherited a sane environment);
      3. then the well-known per-user install locations.
    """
    override = os.environ.get("MARIMO_QGIS_UV")
    if override and os.path.isfile(override):
        return override

    found = shutil.which("uv")
    if found:
        return found

    exe = "uv.exe" if sys.platform == "win32" else "uv"
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, ".local", "bin", exe),  # standalone installer (default)
        os.path.join(home, ".cargo", "bin", exe),  # cargo install
    ]
    if sys.platform == "win32":
        # pip --user lands in %APPDATA%\Python\Python3XX\Scripts\uv.exe
        appdata = os.environ.get("APPDATA")
        if appdata and os.path.isdir(os.path.join(appdata, "Python")):
            py_root = os.path.join(appdata, "Python")
            for sub in os.listdir(py_root):
                candidates.append(os.path.join(py_root, sub, "Scripts", exe))
    else:
        candidates += ["/usr/local/bin/uv", "/opt/homebrew/bin/uv", "/usr/bin/uv"]

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None


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


def pyqgis_dir():
    """Return the directory that holds the `qgis` package, or None.

    Derived from the running QGIS (this code runs inside the plugin, which *is*
    PyQGIS) so it is correct on every platform — Linux `/usr/share/qgis/python`,
    Windows `…\\apps\\qgis\\python`, macOS `…/Contents/Resources/python` — without
    hardcoding any of them. Added to a launched notebook's PYTHONPATH so it can
    `import qgis`.
    """
    try:
        import qgis

        return os.path.dirname(os.path.dirname(os.path.realpath(qgis.__file__)))
    except Exception:  # noqa: BLE001 — fall back to the caller's default
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
