"""Environment introspection + example downloader for the Setup tab.

Everything here runs inside QGIS's own Python interpreter, so it reports exactly
what a launched notebook will see (same interpreter, same site-packages, same
GDAL/PROJ/Spatialite). `report_markdown()` builds a shareable Markdown report;
`download_examples()` fetches the repo's example/notebook folders.
"""

import os
import shutil
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

    add("## Python packages relevant to marimo + QGIS")
    add("")
    add("| Package | Version |")
    add("| --- | --- |")
    for name in _RELEVANT_PACKAGES:
        ver = _pkg_version(name)
        add(f"| {name} | {ver if ver else '—'} |")
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
