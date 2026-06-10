"""MarimoProcessManager — launches marimo notebooks as detached subprocesses.

Each notebook runs in its own OS process (crash isolation via
`start_new_session=True`, so a runaway cell cannot take QGIS down). The bridge
connection (`MARIMO_QGIS_PORT` / `MARIMO_QGIS_TOKEN`) is injected into the
subprocess environment so the notebook's `qgis_bridge.QgisBridge()` can reach the
live QGIS project.

This is the programmatic launch path (used by the Phase 2 dock widget). The
Processing "Launch marimo notebook" algorithm performs the same env injection via
`plugin.runtime.bridge_env()`.
"""

import os
import subprocess

from ..runtime import bridge_env


class MarimoProcessManager:
    """Launches and tracks marimo notebook subprocesses."""

    def __init__(self):
        self._procs = []

    def launch(self, notebook_path, mode="edit", cwd=None):
        """Launch `marimo <mode> <notebook_path>` with the bridge env injected.

        Returns the Popen handle. Raises FileNotFoundError if `uv` is not on PATH.
        """
        env = os.environ.copy()
        # Defence in depth: notebooks self-configure sys.path, but make the
        # bindings discoverable to the marimo server process too.
        env["PYTHONPATH"] = "/usr/share/qgis/python"
        # The subprocess has a real display; do not force the offscreen platform.
        env.pop("QT_QPA_PLATFORM", None)
        # Connect the notebook to the live bridge (no-op if no server running).
        env.update(bridge_env())

        proc = subprocess.Popen(
            ["uv", "run", "marimo", mode, notebook_path],
            cwd=cwd or os.path.dirname(notebook_path),
            env=env,
            start_new_session=True,  # crash isolation: own process group
        )
        self._procs.append(proc)
        return proc

    def processes(self):
        """Return the list of launched Popen handles (for a future dock UI)."""
        return list(self._procs)

    def forget(self):
        """Stop tracking detached notebooks (they keep running; the user owns them)."""
        self._procs = []
