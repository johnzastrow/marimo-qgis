"""Environment introspection + example downloader for the Setup tab.

Everything here runs inside QGIS's own Python interpreter, so it reports exactly
what a launched notebook will see (same interpreter, same site-packages, same
GDAL/PROJ/Spatialite). `report_markdown()` builds a shareable Markdown report;
`download_examples()` fetches the repo's example/notebook folders.
"""

import os
import shutil
import site
import subprocess
import sys
from datetime import datetime
from importlib import metadata as importlib_metadata

from .runtime import qgis_python, uv_executable

# Repo source for the "Download examples" button.
_REPO = "johnzastrow/marimo-qgis"
_BRANCH_ZIP = "https://github.com/{repo}/archive/refs/heads/{branch}.zip"

# Packages a marimo + QGIS notebook is likely to care about. Reported with their
# installed version, or "—" if absent, so the user can see what is available in
# QGIS's Python before relying on it in a notebook.
_RELEVANT_PACKAGES = [
    "marimo",
    "numpy",
    "pandas",
    "polars",
    "pyarrow",
    "geopandas",
    "shapely",
    "pyproj",
    "fiona",
    "pyogrio",
    "rasterio",
    "matplotlib",
    "altair",
    "plotly",
    "duckdb",
    "sqlalchemy",
    "scipy",
    "requests",
]

# CLI utilities QGIS workflows commonly shell out to. (uv is reported separately
# in the marimo & uv section, resolved even when QGIS's PATH omits it.)
_CLI_UTILITIES = ["gdalinfo", "ogr2ogr", "ogrinfo", "spatialite", "proj"]

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _safe(fn, default="unavailable"):
    """Run a probe, returning `default (reason)` instead of raising."""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 — a missing probe must not break the report
        return f"{default} ({exc})"


def _pkg_version(name):
    try:
        return importlib_metadata.version(name)
    except importlib_metadata.PackageNotFoundError:
        return None
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc}"


def _req_name(requirement):
    """The bare distribution name from a requirement string, e.g.
    "pandas>=2.0; extra=='recommended'" -> "pandas"."""
    import re

    match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", requirement or "")
    return match.group(1) if match else None


def _marimo_closure():
    """Lower-cased names of marimo and everything in its dependency tree.

    Walks `requires` transitively so the report's "relevant" set captures the
    whole marimo stack (starlette, uvicorn, narwhals, …), not just marimo
    itself. Optional/extra deps are included when present — they are intersected
    with what is actually installed by the caller.
    """
    closure = set()
    queue = ["marimo"]
    while queue:
        name = queue.pop()
        key = name.lower()
        if key in closure:
            continue
        closure.add(key)
        try:
            reqs = importlib_metadata.distribution(name).requires or []
        except Exception:  # noqa: BLE001 — not installed / malformed; skip
            continue
        for req in reqs:
            dep = _req_name(req)
            if dep and dep.lower() not in closure:
                queue.append(dep)
    return closure


def _installed_with_location():
    """Map lower-name -> (name, version, location) for every installed dist.

    `location` is "user" for the per-user site (where the dock's --user installs
    land) or "system" otherwise, so the report shows what *you* added on top of
    QGIS's base Python versus what shipped with it.
    """
    try:
        user_site = (site.getusersitepackages() or "").lower()
    except Exception:  # noqa: BLE001
        user_site = ""
    out = {}
    for dist in importlib_metadata.distributions():
        try:
            name = dist.metadata["Name"]
        except Exception:  # noqa: BLE001
            name = None
        if not name:
            continue
        key = name.lower()
        if key in out:
            continue  # first on sys.path wins, mirroring import resolution
        try:
            version = dist.version
        except Exception as exc:  # noqa: BLE001
            version = f"error: {exc}"
        try:
            path = str(dist.locate_file("")).lower()
        except Exception:  # noqa: BLE001
            path = ""
        location = "user" if user_site and path.startswith(user_site) else "system"
        out[key] = (name, version, location)
    return out


def _dock_installed():
    """Lower-cased names of packages installed through the dock's Setup tab.

    Recorded by the dock in QgsSettings on each successful install. This is the
    cross-platform signal for "what the user added": on Windows/macOS the dock
    installs into the bundled (writable) site-packages, so the per-user-site
    heuristic below can't see them — this list can. Empty/absent is fine.
    """
    try:
        import json

        from qgis.core import QgsSettings

        raw = QgsSettings().value("marimo/installed_packages", "")
        names = json.loads(raw) if raw else []
    except Exception:  # noqa: BLE001 — settings/qgis optional; degrade quietly
        return set()
    out = set()
    for spec in names:
        base = _req_name(spec)
        if base:
            out.add(base.lower())
    return out


def _relevant_packages():
    """Installed packages available to marimo and/or QGIS, as (name, ver, loc).

    The "relevant" set, intersected with what is actually installed, is:
      - the curated QGIS/data shortlist (_RELEVANT_PACKAGES),
      - marimo's full dependency closure (the marimo stack),
      - packages installed through the dock (cross-platform; from QgsSettings),
      - packages in the per-user site (a Linux signal for manual --user installs).
    This keeps the QGIS + marimo stack plus anything you added (e.g. anthropic),
    while dropping unrelated OS/system packages (apt, dbus, …) that only add
    noise to a shareable report. Sorted by name.
    """
    installed = _installed_with_location()
    relevant = {p.lower() for p in _RELEVANT_PACKAGES}
    relevant |= _marimo_closure()
    relevant |= _dock_installed()
    relevant |= {k for k, (_n, _v, loc) in installed.items() if loc == "user"}
    rows = [installed[k] for k in relevant if k in installed]
    return sorted(rows, key=lambda r: r[0].lower())


def _site_dirs():
    """Directories packages install into / import from, for the report.

    Shows where a `--user` install lands (user site) vs the interpreter's own
    site-packages, so the user can confirm an install went somewhere importable.
    """
    dirs = []
    try:
        if site.ENABLE_USER_SITE:
            dirs.append(("user site", site.getusersitepackages()))
    except Exception:  # noqa: BLE001
        pass
    try:
        for path in site.getsitepackages():
            dirs.append(("site-packages", path))
    except Exception:  # noqa: BLE001
        pass
    return dirs


def _run_version(cmd):
    """Run `cmd` and return its first stdout/stderr line (for `--version`)."""
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=30,
        creationflags=_NO_WINDOW if sys.platform == "win32" else 0,
    )
    out = (result.stdout or result.stderr or "").strip().splitlines()
    return out[0] if out else "(no output)"


# ---- individual probes ---------------------------------------------------


def _qgis_version():
    from qgis.core import Qgis

    return Qgis.QGIS_VERSION


def _gdal_version():
    from osgeo import gdal

    return gdal.__version__


def _proj_version():
    try:
        from osgeo import osr

        return (
            f"{osr.GetPROJVersionMajor()}."
            f"{osr.GetPROJVersionMinor()}."
            f"{osr.GetPROJVersionMicro()}"
        )
    except Exception:  # noqa: BLE001 — fall back to pyproj
        import pyproj

        return pyproj.proj_version_str


def _geos_version():
    try:
        import shapely

        return shapely.geos_version_string
    except Exception:  # noqa: BLE001
        from qgis.core import Qgis

        return Qgis.geosVersion()


def _spatialite_version():
    import sqlite3

    sqlite_ver = sqlite3.sqlite_version
    con = sqlite3.connect(":memory:")
    try:
        con.enable_load_extension(True)
        con.load_extension("mod_spatialite")
        sl = con.execute("SELECT spatialite_version()").fetchone()[0]
        return f"SpatiaLite {sl} (SQLite {sqlite_ver})"
    except Exception as exc:  # noqa: BLE001
        return f"SQLite {sqlite_ver}; mod_spatialite not loadable ({exc})"
    finally:
        con.close()


def _qt_version():
    from qgis.PyQt.QtCore import PYQT_VERSION_STR, QT_VERSION_STR

    return f"Qt {QT_VERSION_STR} / PyQt {PYQT_VERSION_STR}"


def _uv_info():
    uv = uv_executable()
    if not uv:
        return "not found"
    return f"{_run_version([uv, '--version'])}  [{uv}]"


# ---- report --------------------------------------------------------------


def report_markdown():
    """Build a comprehensive Markdown report of the QGIS Python environment."""
    py = qgis_python()
    lines = []
    add = lines.append

    add("# marimo-qgis Environment Report")
    add("")
    add(f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_")
    add("")
    add(
        "This describes the **QGIS Python interpreter** that launched notebooks "
        "run on. marimo and any libraries a notebook imports must be installed "
        "in *this* interpreter."
    )
    add("")

    add("## QGIS")
    add(f"- Version: {_safe(_qgis_version)}")
    add(f"- Platform: {sys.platform}")
    add("")

    add("## Python (notebook runtime)")
    add(f"- Version: {sys.version.splitlines()[0]}")
    add(f"- Interpreter: `{py}`")
    add(f"- sys.prefix: `{sys.prefix}`")
    add(f"- sys.base_prefix: `{sys.base_prefix}`")
    for label, path in _site_dirs():
        add(f"- {label}: `{path}`")
    add("")

    add("## Geospatial stack")
    add(f"- GDAL: {_safe(_gdal_version)}")
    add(f"- PROJ: {_safe(_proj_version)}")
    add(f"- GEOS: {_safe(_geos_version)}")
    add(f"- SpatiaLite/SQLite: {_safe(_spatialite_version)}")
    add(f"- Qt bindings: {_safe(_qt_version)}")
    add("")

    add("## marimo & uv")
    marimo_ver = _pkg_version("marimo")
    add(f"- marimo: {marimo_ver or 'NOT INSTALLED — the plugin can install it'}")
    add(f"- uv: {_safe(_uv_info)}")
    add("")

    packages = _safe(_relevant_packages, default=None)
    if isinstance(packages, list):
        add(f"## Packages available to marimo & QGIS ({len(packages)})")
        add("")
        add(
            "Installed packages relevant to QGIS and marimo — the QGIS/data "
            "stack, marimo's full dependency tree, and anything you installed "
            "yourself (e.g. via the Setup tab). Unrelated OS/system packages are "
            "omitted. `location` is `user` for your per-user site or `system` "
            "for QGIS's own site-packages."
        )
        add("")
        add("| Package | Version | Location |")
        add("| --- | --- | --- |")
        for name, ver, loc in packages:
            add(f"| {name} | {ver} | {loc} |")
        add("")
    else:
        add("## Packages available to marimo & QGIS")
        add("")
        add(f"_Could not enumerate packages: {packages}_")
        add("")

    add("## CLI utilities on PATH")
    add("")
    add("| Tool | Path |")
    add("| --- | --- |")
    for tool in _CLI_UTILITIES:
        found = shutil.which(tool)
        add(f"| {tool} | {found if found else '—'} |")
    add("")

    return "\n".join(lines)


# ---- example downloader --------------------------------------------------


def download_examples(dest_dir, branch="main", folders=("example", "notebooks"),
                      progress=None):
    """Download `folders` from the repo branch zip into `dest_dir`.

    Stdlib only (urllib + zipfile) so it needs no extra packages. Returns the
    list of files written. `progress` (optional) is called with an int 0-100.
    """
    import tempfile
    import urllib.request
    import zipfile

    url = _BRANCH_ZIP.format(repo=_REPO, branch=branch)
    fd, tmp_zip = tempfile.mkstemp(suffix=".zip")
    os.close(fd)

    def _hook(block_num, block_size, total_size):
        if progress and total_size > 0:
            progress(min(100, int(block_num * block_size * 100 / total_size)))

    written = []
    try:
        urllib.request.urlretrieve(url, tmp_zip, reporthook=_hook)
        with zipfile.ZipFile(tmp_zip) as archive:
            for member in archive.namelist():
                if member.endswith("/"):
                    continue
                # archive paths look like "marimo-qgis-main/example/foo.py"
                parts = member.split("/")
                if len(parts) < 2 or parts[1] not in folders:
                    continue
                rel_parts = parts[1:]  # drop the "<repo>-<branch>" root
                target = os.path.join(dest_dir, *rel_parts)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with archive.open(member) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out)
                written.append(target)
    finally:
        try:
            os.remove(tmp_zip)
        except OSError:
            pass
    return written
