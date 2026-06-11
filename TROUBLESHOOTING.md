# Troubleshooting: Marimo + QGIS4 on Linux

This document captures every issue encountered running [marimo](https://marimo.io)
notebooks that use PyQGIS (QGIS4 Python bindings) on Ubuntu Linux with a desktop
session. Written so that the next person (or next session) can skip the two-day
debugging tour.

---

## System Context

| Component | Version / Path |
|-----------|----------------|
| QGIS | 4.0.3-Norrköping |
| QGIS Python bindings | `/usr/share/qgis/python` |
| System Qt6 | 6.9.2 (`/lib/x86_64-linux-gnu/libQt6Core.so.6`) |
| System PyQt6 | `/usr/lib/python3/dist-packages/PyQt6/` |
| Python | 3.14.4 (system) — must match QGIS's compiled bindings; don't pin a fixed version |
| marimo | 0.23.9 |
| uv | for package management |
| OS | Ubuntu "Questing" (development build) |

---

## Architecture: How marimo Executes Cells

Understanding this is essential for debugging any environment issue.

### `marimo export html` / `marimo run`

Cells execute in **the same process** as the marimo CLI, using Python **threads**.
The process already has `PYTHONPATH`, `QT_QPA_PLATFORM`, etc. set from the shell.
This mode almost always works cleanly.

### `marimo edit` (interactive browser editor)

Cells execute in a **separate subprocess**, spawned via:

```python
# marimo/_session/managers/kernel.py
multiprocessing.get_context("spawn").Process(target=runtime.launch_kernel, ...)
```

The `spawn` start method (unlike `fork`) creates a **brand-new Python interpreter**
from scratch. It does **not** inherit the parent's loaded shared libraries. It **does**
inherit:

- Environment variables (`os.environ`) — but only those set **before** the subprocess
  is created, not those set inside cells after the fact.
- The parent's `sys.path` (serialised and restored by the multiprocessing spawn
  infrastructure).

**This asymmetry is the source of most "works in export, breaks in edit" bugs.**

---

## Issues and Fixes

### Issue 1: Qt Symbol Error — `undefined symbol: Qt_6_PRIVATE_API`

**Error** (shown in marimo browser console, not in terminal):

```
Cell notebooks/stations_analysis.py#cell=cell-2, line 10, in <module>
    from qgis.core import (...)
ImportError: /lib/x86_64-linux-gnu/libQt6Network.so.6: undefined symbol:
    _ZN14QObjectPrivateC2Ei, version Qt_6_PRIVATE_API
```

**Why it's confusing**: The same import succeeds when tested directly with
`.venv/bin/python` or via `marimo export html`. This makes it look like a QGIS or
Qt installation bug, but it isn't.

**Root cause** (confirmed via `/proc/self/maps` diagnostic in the live kernel):

The notebook had a PEP 723 `/// script` inline metadata block that listed
`pyqt6==6.10.2` as a dependency (added during a previous debugging attempt):

```python
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "marimo",
#     "pandas",
#     "numpy",
#     "pyqt6==6.10.2",    # ← the killer line
# ]
# ///
```

When `marimo edit` sees this block, it uses uv to resolve and install dependencies
into a **temporary environment** (`~/.cache/uv/builds-v0/.tmp*/`). This temp env:

1. **Replaces the venv entirely** — the venv's site-packages are absent from `sys.path`.
2. **Installs bundled PyQt6 6.10.2** with its own `libQt6Core.so.6` and
   `libQt6Network.so.6`.
3. **Loads that bundled libQt6Core 6.10.2 before QGIS runs.** When QGIS then tries to
   load the system `libQt6Network.so.6` (6.9.2), it can't find its expected symbol in
   the already-loaded 6.10.2 libQt6Core → `ImportError`.

The diagnostic that revealed this — a cell reading `/proc/self/maps` — showed the
uv-cached PyQt6 Qt6 libs already loaded, and `sys.path` containing only uv temp dirs
with no venv entry at all.

**Fix**: Remove the `/// script` block entirely. The venv (`--system-site-packages`)
already has everything needed via the system packages.

```python
# DELETE this block from the top of the notebook:
# /// script
# requires-python = ">=3.13"
# dependencies = [...]
# ///
```

**What we ruled out** before finding the real cause:

- Qt display plugins, `DISPLAY` env var, `QT_QPA_PLATFORM` timing — not the cause.
- marimo importing Qt at startup — confirmed zero Qt modules loaded by marimo itself.
- Simulated `multiprocessing.spawn` tests pass because they don't trigger marimo's
  `/// script` dependency resolution.

**Rule**: Do not use `/// script` inline metadata in notebooks that depend on system
libraries (QGIS, system Qt6). The uv-managed environment it creates does **not** have
`--system-site-packages` and will install conflicting bundled wheels.

---

### Issue 2: Cells Show No Output in `marimo edit` (Stale Session Cache)

**Symptoms**:

- `marimo edit` opens in the browser, cells appear, but show no output and no errors.
- `__marimo__/session/*.json` files contain `"outputs": []`.

**Root cause**: Stale session cache from a previous (crashed or interrupted) session.
The interactive server reads and displays the cached state rather than re-running cells.

**Fix**: Delete the cache directory and restart:

```bash
rm -rf __marimo__/session/
./marimo-qgis edit notebook.py
```

**Note**: `marimo export html` **always** re-executes cells from scratch — it never
uses the session cache. This is why export can succeed when the browser UI shows
nothing: the cache is stale, but the export is fresh.

---

### Issue 3: PyQt6 / Qt6 Version Mismatch (venv without system-site-packages)

**Error**:

```
ModuleNotFoundError: No module named 'PyQt6'
```

or, if a different PyQt6 is found:

```
ImportError: libQt6Core.so.6: cannot open shared object file
```

**Root cause**: QGIS Python bindings (`qgis._core.so`) link against the **system**
Qt6. The system PyQt6 (at `/usr/lib/python3/dist-packages/PyQt6/`) also uses the
system Qt6. A venv created **without** `--system-site-packages` cannot see system
PyQt6 and may find a bundled PyQt6 wheel (with its own incompatible Qt6) instead.

**Fix**: Always create the venv with `--system-site-packages`, against the
interpreter QGIS uses (let the helper detect it rather than pinning a version):

```bash
./qgis-env.sh setup
# manual equivalent:
#   uv venv --python "$(./qgis-env.sh path)" --system-site-packages
```

**Verify**:

```bash
.venv/bin/python -c "import PyQt6; print(PyQt6.__file__)"
# Must print: /usr/lib/python3/dist-packages/PyQt6/__init__.py
# NOT anything under ~/.cache/uv/ or .venv/lib/
```

---

### Issue 4: uv Ignores `--python` and Uses Wrong Version

**Symptom**: `uv venv --python <version>` creates a venv on a *different* Python
than requested (e.g. a 3.12 venv). Cells then fail with an incompatibility or a
`ModuleNotFoundError: No module named 'PyQt6'` because that Python has no matching
system PyQt6.

```
Python 3.12.12 is incompatible with requirement: >=3.13
```

**Root cause**: A `.python-version` file in the project directory overrides the
`--python` flag. Passing a bare version (not a path) can also let uv pick one of
its own downloaded standalone builds instead of the system interpreter.

**Fix** — remove the pin and target QGIS's actual interpreter by path:

```bash
rm -f .python-version
./qgis-env.sh setup
# manual equivalent:
#   uv venv --python "$(./qgis-env.sh path)" --system-site-packages
```

---

### Issue 5: Locating data files — use `__file__`, not `os.getcwd()` or hardcoded paths

**Symptom**: A notebook opens its data file when launched one way but fails with
`AssertionError` / "Could not open `<layer>`" when launched another way — most often
from the QGIS Processing Toolbox, where the working directory differs from the repo.

**Root cause**: `os.getcwd()` reflects wherever the *process* was started, which varies
by launch method, so a path resolved against it points somewhere else.

An earlier version of this guide claimed `__file__` was undefined inside a marimo cell.
That is **not** true on current marimo: cells can read `__file__`, and it always points
at the notebook's own path. (Verified by exporting a one-cell notebook that prints
`os.path.dirname(os.path.abspath(__file__))`.)

**Fix**: Resolve data files relative to the notebook via `__file__` — this is what the
notebooks in this repo do, and it is portable across machines and launch methods:

```python
import os
gpkg = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stations.gpkg")
layer = QgsVectorLayer(gpkg, "stations", "ogr")
```

Avoid both of these:

```python
# Fragile — depends on the launch directory:
gpkg = "stations.gpkg"

# Non-portable — breaks on any other machine or after moving the repo:
gpkg = "/home/jcz/Github/marimo_qgis/notebooks/stations.gpkg"
```

---

### Issue 6: Cross-cell Namespace and Variable Visibility

**Symptom**: A name defined in one cell is not visible in another, or silently
shadows an expected value.

**Root cause**: Marimo's reactive execution model tracks cell outputs via their
`return` statements. Variables NOT returned from a cell are local to that cell and
invisible to others.

**Fix**: Always return everything a downstream cell will need:

```python
@app.cell
def _():
    from qgis.core import QgsApplication, Qgis, QgsVectorLayer
    qgs = QgsApplication([], False)
    qgs.initQgis()
    return Qgis, QgsApplication, QgsVectorLayer, qgs  # explicit exports
```

Use underscore-prefixed names for things that must stay local:

```python
import os as _os
_gpkg = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "stations.gpkg")
layer = QgsVectorLayer(_gpkg, "stations", "ogr")
return (layer,)  # _gpkg stays local, not exported
```

---

## Debugging Checklist

When something works in `marimo export html` but fails in `marimo edit`:

1. **Is the failing code in a cell that runs early?** Check if it runs before Qt env
   vars are set. Move those vars to the wrapper script.

2. **Is the error about a missing symbol or library?** Check whether multiple Qt6
   versions exist on the machine:

   ```bash
   find /home ~/.cache /opt -name "libQt6Core.so.6" 2>/dev/null
   ldconfig -p | grep Qt6Core
   ```

3. **Is the session cache stale?** Delete `__marimo__/session/` and retry.

4. **Does it work in a direct Python test?**

   ```bash
   PYTHONPATH=/usr/share/qgis/python QT_QPA_PLATFORM=offscreen \
     .venv/bin/python -c "from qgis.core import QgsApplication, Qgis; print(Qgis.version())"
   ```

5. **Does it work in a spawn subprocess?** Write a test script (not `-c`) and test:

   ```python
   # /tmp/test_spawn.py  — must be a file, not -c, for spawn to work
   import multiprocessing, os

   def test():
       os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
       from qgis.core import Qgis
       print(Qgis.version())

   if __name__ == "__main__":
       p = multiprocessing.get_context("spawn").Process(target=test)
       p.start()
       p.join()
   ```

   ```bash
   PYTHONPATH=/usr/share/qgis/python .venv/bin/python /tmp/test_spawn.py
   ```

6. **Check which PyQt6 the venv finds**:

   ```bash
   .venv/bin/python -c "import PyQt6; print(PyQt6.__file__)"
   # Must point to /usr/lib/python3/dist-packages/PyQt6/
   ```

---

## Working Configuration

### Wrapper Script (`marimo-qgis`)

```bash
#!/bin/bash
export PYTHONPATH=/usr/share/qgis/python
export QT_QPA_PLATFORM=offscreen
export QT_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/qt6/plugins
cd /path/to/notebook/dir
exec .venv/bin/marimo "$@"
```

### Venv Creation

```bash
./qgis-env.sh setup
# manual equivalent:
#   uv venv --python "$(./qgis-env.sh path)" --system-site-packages
#   uv pip install marimo pandas numpy
```

### Notebook QGIS Init Cell Pattern

```python
@app.cell
def _():
    import sys, os

    sys.path.insert(0, "/usr/share/qgis/python")

    # Belt-and-suspenders: wrapper sets QT_QPA_PLATFORM=offscreen before
    # Python starts. setdefault here covers direct invocations.
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from qgis.core import (
        QgsApplication,
        Qgis,
        QgsVectorLayer,
        QgsDistanceArea,
        QgsPointXY,
        QgsProject,
    )

    qgs = QgsApplication([], False)
    qgs.initQgis()

    return Qgis, QgsApplication, QgsDistanceArea, QgsPointXY, QgsProject, QgsVectorLayer, qgs
```

### Verification

```bash
# Static export — confirms cells execute correctly end-to-end
PYTHONPATH=/usr/share/qgis/python QT_QPA_PLATFORM=offscreen \
  .venv/bin/marimo export html notebooks/stations_analysis.py -o /tmp/out.html && echo OK
```

---

## Bridge (plugin) issues

The marimo QGIS plugin runs a localhost HTTP **bridge**; notebooks launched from
its dock reach the live project through the bundled `qgis_bridge` client. Common
failure modes:

### Notebook shows "⚪ Headless" when you expected "🟢 Live"

The notebook didn't receive the bridge connection. Causes, most common first:

- **The plugin is running stale code.** The installed plugin must be a *symlink*
  to `plugin/` (not an old copied directory), and **QGIS must be restarted**
  after pulling changes that add new sub-modules — a running plugin keeps the old
  code in memory. Check **Log Messages ▸ "marimo bridge"** for
  `bridge listening on 127.0.0.1:<port>`. If it's absent, the bridge never
  started.
- **The notebook was opened before the bridge started**, or in a tab left over
  from a previous session. Close it and **Launch it again** from the dock.
- **You ran it from the terminal** (`uv run marimo edit …`) instead of from the
  dock. Terminal launches have no bridge env, so headless is correct there.

### `bridge failed to start: …` in the "marimo bridge" log

The server couldn't bind or a bridge module failed to import. The plugin is
fail-safe (it still loads), but there's no live bridge. Read the logged
exception; restart QGIS after fixing. A stuck port from a previous crash is rare
(the bridge binds an OS-assigned ephemeral port, not a fixed one).

### `ModuleNotFoundError: No module named 'qgis_bridge'`

The notebook process couldn't find the client. When launched from the dock the
plugin adds the directory containing `qgis_bridge` to `PYTHONPATH` (it ships
inside the plugin). If you see this, the plugin is likely stale (restart QGIS),
or you launched the notebook outside the plugin. Standalone notebooks add the
repo root to `sys.path` themselves — only works when run from inside the repo.

### `ModuleNotFoundError: No module named 'geopandas'` (or `rioxarray`)

`get_layer` / `get_selected_features` / `insert_layer` read FlatGeobuf into a
GeoDataFrame and need **geopandas**; raster `get_layer` needs **rioxarray**
(optional). Install into the notebook venv: `./qgis-env.sh setup` (adds
geopandas), and `uv pip install rioxarray` if you fetch rasters.

### `BridgeError: bridge 401` / `bridge unreachable`

- **401** — the notebook's `MARIMO_QGIS_TOKEN` doesn't match the running server.
  Usually a notebook left open from a previous QGIS session; relaunch it.
- **unreachable** — QGIS (and its bridge) closed while the notebook stayed open.
  Reopen QGIS and relaunch the notebook.

### Plugin won't enable / not listed

The plugin requires **QGIS 4.0+** (`qgisMinimumVersion=4.0`). On QGIS 3 it will
not load. `uv` must be on `PATH` for the dock to launch notebooks.
