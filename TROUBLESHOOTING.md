# Troubleshooting: Marimo + QGIS4 on Linux

This document captures every issue encountered running [marimo](https://marimo.io)
notebooks that use PyQGIS (QGIS4 Python bindings) on Ubuntu Linux with a desktop
session. Written so that the next person (or next session) can skip the two-day
debugging tour.

---

## System Context

| Component | Version / Path |
|-----------|----------------|
| QGIS | 4.0.0-Norrköping (`1:4.0.0+43questing`) |
| QGIS Python bindings | `/usr/share/qgis/python` |
| System Qt6 | 6.9.2 (`/lib/x86_64-linux-gnu/libQt6Core.so.6`) |
| System PyQt6 | `/usr/lib/python3/dist-packages/PyQt6/` |
| Python | 3.13.7 (system) |
| marimo | 0.21.1 |
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
Cell stations_analysis.py#cell=cell-2, line 10, in <module>
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

**Fix**: Always create the venv with `--system-site-packages`:

```bash
uv venv --python 3.13.7 --system-site-packages
```

**Verify**:

```bash
.venv/bin/python -c "import PyQt6; print(PyQt6.__file__)"
# Must print: /usr/lib/python3/dist-packages/PyQt6/__init__.py
# NOT anything under ~/.cache/uv/ or .venv/lib/
```

---

### Issue 4: uv Ignores `--python` and Uses Wrong Version

**Symptom**: `uv venv --python 3.13.7` creates a 3.12 venv. Cells fail with:

```
Python 3.12.12 is incompatible with requirement: >=3.13
```

**Root cause**: A `.python-version` file in the project directory overrides the
`--python` flag.

**Fix**:

```bash
rm -f .python-version
uv venv --python 3.13.7 --system-site-packages
```

---

### Issue 5: `pathlib.Path(__file__)` Raises `NameError` in Marimo Cells

**Error**:

```python
NameError: name '__file__' is not defined
```

**Root cause**: Marimo wraps each cell in a function. Inside that function, `__file__`
is not defined — it's a module-level attribute, not a cell-level one.

**Fix**: Use absolute paths directly:

```python
# Bad:
gpkg = pathlib.Path(__file__).parent / "stations.gpkg"

# Good:
gpkg = "/home/jcz/Github/marimo_qgis/stations.gpkg"
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
_gpkg = "/home/jcz/Github/marimo_qgis/stations.gpkg"
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
uv venv --python 3.13.7 --system-site-packages
uv pip install marimo pandas numpy
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
  .venv/bin/marimo export html stations_analysis.py -o /tmp/out.html && echo OK
```
