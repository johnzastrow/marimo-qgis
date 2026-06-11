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
import re
import subprocess
import sys
import tempfile

from ..runtime import bridge_env, pyqgis_dir, qgis_bridge_dir, qgis_python

# Windows: keep child consoles from flashing; output is captured to the log.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


# Bootstrap run as `<qgis_python> -c <this> <pkg>...` to install packages across
# platforms. Package names come in via argv (sys.argv[1:]). It is deliberately
# platform-agnostic via PROGRESSIVE FALLBACK rather than per-OS branching,
# because the interpreters differ:
#   - Windows/macOS QGIS ship their own writable Python WITH pip bundled, so the
#     first strategy (plain `pip install <pkg>`) succeeds.
#   - Linux QGIS uses the SYSTEM python (e.g. /usr/bin/python3), which often has
#     no `pip` module, is root-owned (can't write the system site), and on PEP
#     668 distros is "externally-managed". So it bootstraps pip via ensurepip,
#     then falls through to `--user` (installs to ~/.local, no root) and finally
#     `--user --break-system-packages` for externally-managed system pythons.
# Every attempt is echoed to stdout, which the dock captures to the log file.
# argv is dock-validated (validate_package_names) before reaching here, and we
# pass a list to subprocess (shell=False), so there is no shell/arg injection.
_INSTALL_BOOTSTRAP = r'''
import subprocess, sys

pkgs = sys.argv[1:]
if not pkgs:
    print("ERROR: no packages specified.", flush=True)
    sys.exit(2)

def run(args):
    print(">>> " + sys.executable + " " + " ".join(args), flush=True)
    return subprocess.call([sys.executable] + args)

def have_pip():
    return run(["-m", "pip", "--version"]) == 0

if not have_pip():
    print(">>> pip module missing; bootstrapping with ensurepip", flush=True)
    if run(["-m", "ensurepip", "--user"]) != 0:
        run(["-m", "ensurepip"])
    if not have_pip():
        print(
            "ERROR: pip is unavailable in this interpreter and ensurepip could "
            "not bootstrap it.\n"
            "Install pip via your OS package manager, e.g.:\n"
            "  sudo apt install python3-pip   (Debian/Ubuntu)\n"
            "then retry. Interpreter: " + sys.executable,
            flush=True,
        )
        sys.exit(3)

base = ["-m", "pip", "install"] + pkgs
rc = 1
for extra in ([], ["--user"], ["--user", "--break-system-packages"]):
    rc = run(base + extra)
    if rc == 0:
        print(">>> installed successfully: " + " ".join(pkgs), flush=True)
        sys.exit(0)
    print(">>> strategy failed (rc=%d); trying next" % rc, flush=True)

print("ERROR: all install strategies failed (rc=%d)." % rc, flush=True)
sys.exit(rc)
'''

# A pip requirement token we are willing to hand to the installer: a PEP 508
# distribution name, optionally with a simple version specifier. The leading
# char must be alphanumeric — this rejects anything starting with '-', which is
# what blocks pip-option injection (e.g. "--index-url http://evil/") through the
# Setup-tab field, and the character class forbids shell metacharacters.
_PKG_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*"          # distribution name
    r"(\[[A-Za-z0-9._,-]+\])?"               # optional extras, e.g. [all]
    r"([<>=!~]=?[0-9A-Za-z._*+!-]+(,[<>=!~]=?[0-9A-Za-z._*+!-]+)*)?$"  # version specs
)


def validate_package_names(raw):
    """Parse a whitespace/comma-separated package spec into safe pip tokens.

    Returns the list of tokens. Raises ValueError if the field is empty or any
    token is not a plain PEP 508 name (optionally with extras / a version
    specifier). This is an allowlist on user input that flows into a subprocess
    argv: it blocks argument injection (a token starting with '-' smuggling pip
    options) and shell-metacharacter tokens. Tokens are still passed to
    subprocess as a list (shell=False), so this is defence in depth.
    """
    # Split on whitespace only (NOT commas): a comma separates version
    # constraints within one spec, e.g. "shapely>=2.0,<3", so it must stay
    # inside the token. A trailing/leading comma from "geopandas, rasterio"
    # typing is stripped for friendliness.
    tokens = [t.strip(",") for t in (raw or "").split() if t.strip(",")]
    if not tokens:
        raise ValueError("Enter at least one package name.")
    bad = [t for t in tokens if not _PKG_RE.match(t)]
    if bad:
        raise ValueError(
            "Not valid package name(s): "
            + ", ".join(bad)
            + "\nUse plain names like 'geopandas' or 'rasterio>=1.3'."
        )
    return tokens


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
        # In-flight `pip install marimo` jobs. Held here (not discarded) so the
        # Popen is not garbage-collected mid-run — a dropped, still-running Popen
        # emits a ResourceWarning ("subprocess N is still running") from its
        # __del__. Reaped via reap_install() once the dock sees it has exited.
        self._installs = []

    def install_packages(self, packages):
        """Install one or more packages into QGIS's interpreter via the bootstrap.

        Runs `<qgis_python> -c <_INSTALL_BOOTSTRAP> <pkg>...`, which ensures pip
        exists and progressively falls back (plain -> --user -> --user
        --break-system-packages) so the same call works whether QGIS ships its
        own writable Python with pip (Windows/macOS) or runs on a pip-less,
        root-owned, externally-managed system Python (Linux).

        `packages` must be a non-empty list of tokens already validated by
        validate_package_names() — they are passed as subprocess argv (no shell).
        Output is captured to a log file rather than a console window (there is
        no console on Linux, and Windows' flashes shut too fast to read), so
        failures stay visible (the dock surfaces the log tail). The returned
        record's "proc" is retained on this manager so it is not GC'd while still
        running. Returns a record dict with "proc", "log" and "packages".
        """
        if not packages:
            raise ValueError("No packages to install.")
        python_exe = qgis_python()
        cmd = [python_exe, "-c", _INSTALL_BOOTSTRAP, *packages]

        # Own process group + suppressed console, mirroring notebook launches.
        if sys.platform == "win32":
            isolation = {
                "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | _NO_WINDOW
            }
        else:
            isolation = {"start_new_session": True}

        safe = "".join(c if c.isalnum() else "_" for c in packages[0])[:40]
        log_path = os.path.join(log_dir(), "pip_install_" + (safe or "pkgs") + ".log")
        fh = open(log_path, "w", encoding="utf-8", errors="replace")
        fh.write("=== package install ===\n")
        fh.write("python  : " + python_exe + "\n")
        fh.write("packages: " + " ".join(packages) + "\n")
        fh.write("command : " + python_exe + " -c <install bootstrap>\n")
        fh.write("=" * 40 + "\n\n")
        fh.flush()

        proc = subprocess.Popen(
            cmd, stdout=fh, stderr=subprocess.STDOUT, **isolation
        )
        record = {"proc": proc, "log": log_path, "_fh": fh, "packages": list(packages)}
        self._installs.append(record)
        return record

    def install_marimo(self):
        """Install marimo into QGIS's interpreter (thin wrapper, see
        install_packages). Kept as a named entry point for the dock preflight."""
        return self.install_packages(["marimo"])

    def reap_install(self, record):
        """Drop a finished install record and close its log handle."""
        self._close_log(record)
        try:
            self._installs.remove(record)
        except ValueError:
            pass

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
