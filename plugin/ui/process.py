"""MarimoProcessManager — launches and tracks marimo notebook subprocesses.

Notebooks run on QGIS's OWN Python interpreter (via `<qgis_python> -m marimo`),
discovered live from the running QGIS so it tracks Python upgrades automatically
and is always ABI-compatible with the PyQGIS bindings. Each notebook runs in its
own OS process (crash isolation, so a runaway cell cannot take QGIS down). The
bridge connection (`MARIMO_QGIS_PORT` / `MARIMO_QGIS_TOKEN`) is injected into the
subprocess environment so the notebook's `qgis_bridge.QgisBridge()` can reach the
live QGIS project.

The dock widget launches notebooks through this; the bridge connection is read
from `plugin.runtime.bridge_env()`.
"""

import os
import subprocess
import sys
import tempfile

from ..runtime import bridge_env, pyqgis_dir, qgis_bridge_dir, qgis_python

# Windows: keep child consoles from flashing; output is captured to the log.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


# Cache of interpreters known to have marimo. Probing costs a full interpreter
# startup + `import marimo` (~1.5s), so we run it at most once per interpreter per
# session. Only positive results are cached: a negative stays uncached so that an
# install (or a later fix) is picked up on the next launch without a restart.
_MARIMO_OK = set()


def marimo_available(python_exe=None):
    """True if `import marimo` succeeds in the given (or QGIS's) interpreter.

    Used as a preflight so a missing install — e.g. after QGIS upgrades to a new
    Python with a fresh site-packages — produces a clear, actionable prompt
    instead of a process that dies on `ModuleNotFoundError`. The (expensive)
    subprocess probe is cached after the first success to keep launches snappy.
    """
    python_exe = python_exe or qgis_python()
    if python_exe in _MARIMO_OK:
        return True
    try:
        result = subprocess.run(
            [python_exe, "-c", "import marimo"],
            capture_output=True,
            timeout=60,
            creationflags=_NO_WINDOW if sys.platform == "win32" else 0,
        )
    except Exception:  # noqa: BLE001 — treat any failure as "not available"
        return False
    if result.returncode == 0:
        _MARIMO_OK.add(python_exe)
        return True
    return False


def log_dir():
    """Directory holding per-notebook launch logs (created if missing)."""
    path = os.path.join(tempfile.gettempdir(), "marimo_qgis_logs")
    os.makedirs(path, exist_ok=True)
    return path


def _log_path_for(notebook_path):
    """A stable per-notebook log path (overwritten on each launch)."""
    base = os.path.splitext(os.path.basename(notebook_path))[0] or "notebook"
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in base)
    return os.path.join(log_dir(), safe + ".log")


class MarimoProcessManager:
    """Launches marimo notebooks and tracks the live subprocesses."""

    def __init__(self):
        # Each record: {"path": str, "mode": str, "proc": Popen, "log": str,
        #               "_fh": file handle (closed when the process is pruned)}
        self._records = []

    def launch(self, notebook_path, mode="edit", cwd=None):
        """Launch `<qgis_python> -m marimo <mode> <notebook_path>`.

        Runs on QGIS's own interpreter with the bridge env injected. Returns the
        record dict (includes "proc" and "log").
        """
        python_exe = qgis_python()

        env = os.environ.copy()
        # PYTHONPATH for the notebook process: the PyQGIS bindings (discovered
        # from the running QGIS, so it is correct on Linux/Windows/macOS), plus
        # the directory holding the bundled `qgis_bridge` client so notebooks can
        # `import qgis_bridge` without a pip install (it ships in the plugin).
        paths = [pyqgis_dir() or "/usr/share/qgis/python"]
        bridge_dir = qgis_bridge_dir()
        if bridge_dir:
            paths.append(bridge_dir)
        env["PYTHONPATH"] = os.pathsep.join(paths)
        # The subprocess has a real display; do not force the offscreen platform.
        env.pop("QT_QPA_PLATFORM", None)
        # Connect the notebook to the live bridge (no-op if no server running).
        env.update(bridge_env())

        # Crash isolation: give the notebook its own process group so a runaway
        # cell cannot take QGIS down. The mechanism differs by platform.
        if sys.platform == "win32":
            # CREATE_NO_WINDOW: stdout/stderr are captured to the log below, so
            # we suppress the flashing console window that otherwise opens (and
            # vanished too fast to read any error). CREATE_NEW_PROCESS_GROUP keeps
            # crash isolation.
            isolation = {
                "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | _NO_WINDOW
            }
        else:
            isolation = {"start_new_session": True}

        run_cwd = cwd or os.path.dirname(notebook_path)
        cmd = [python_exe, "-m", "marimo", mode, notebook_path]

        # Capture all subprocess output to a log file so failures are visible
        # (the console window closing instantly otherwise hides every error).
        log_path = _log_path_for(notebook_path)
        fh = open(log_path, "w", encoding="utf-8", errors="replace")
        fh.write("=== marimo launch ===\n")
        fh.write("command : " + subprocess.list2cmdline(cmd) + "\n")
        fh.write("cwd     : " + run_cwd + "\n")
        fh.write("python  : " + python_exe + "\n")
        fh.write("PYTHONPATH: " + env.get("PYTHONPATH", "") + "\n")
        fh.write("bridge  : " + ("connected" if bridge_env() else "none") + "\n")
        fh.write("=" * 40 + "\n\n")
        fh.flush()

        proc = subprocess.Popen(
            cmd,
            cwd=run_cwd,
            env=env,
            stdout=fh,
            stderr=subprocess.STDOUT,
            **isolation,
        )
        record = {
            "path": notebook_path,
            "mode": mode,
            "proc": proc,
            "log": log_path,
            "_fh": fh,
        }
        self._records.append(record)
        return record

    def running(self):
        """Return records for still-running notebooks (prunes exited ones)."""
        alive, dead = [], []
        for r in self._records:
            (alive if r["proc"].poll() is None else dead).append(r)
        for r in dead:  # close log handles for processes that have exited
            self._close_log(r)
        self._records = alive
        return list(self._records)

    @staticmethod
    def _close_log(record):
        fh = record.get("_fh")
        if fh is not None and not fh.closed:
            try:
                fh.close()
            except Exception:  # noqa: BLE001
                pass

    def stop(self, proc):
        """Terminate one launched notebook process group (best effort)."""
        try:
            proc.terminate()
        except Exception:  # noqa: BLE001 — process may already be gone
            pass

    def stop_all(self):
        """Terminate every tracked notebook (used only if explicitly requested)."""
        for record in self._records:
            self.stop(record["proc"])
            self._close_log(record)
        self._records = []
