# Cross-Platform Testing Plan — Windows & macOS

The plugin and bridge were built and verified on **Linux (QGIS 4.0.3 / Qt 6 /
Python 3.14)**. This plan verifies — and where needed, fixes — the
platform-specific pieces on Windows and macOS, in preparation for QGIS Plugin
Repository submission (Phase 4).

The bridge itself is mostly portable: it uses the Python standard library
(`http.server`, `urllib`, `secrets`, `tempfile`) and `qgis.PyQt`. The risk is
concentrated in a few **Linux-shaped assumptions** in how notebooks are launched
and how PyQGIS is located. Fix those first (§1), then run the checklist (§4).

---

## 1. Linux-specific assumptions to fix before testing

| # | Location | Linux assumption | Windows | macOS |
|---|----------|------------------|---------|-------|
| A1 | `plugin/ui/process.py` — `PYTHONPATH` | `"/usr/share/qgis/python"` hardcoded | `…\apps\qgis\python` | `…/QGIS.app/Contents/Resources/python` |
| A2 | `qgis_bridge/_headless.py` — `sys.path.insert(...)` | `"/usr/share/qgis/python"` hardcoded | same as A1 | same as A1 |
| A3 | `plugin/ui/process.py` — `subprocess.Popen(start_new_session=True)` | POSIX `setsid` for crash isolation | no effect; use `creationflags=CREATE_NEW_PROCESS_GROUP` | works (POSIX) |
| A4 | `plugin/bridge/convert.py` — `os.chmod(dir, 0o700)` | enforces private temp dir | no-op (NTFS ACLs); harmless | works |
| A5 | venv / deps tooling | `qgis-env.sh` is bash + detects the system Python | bash unavailable; QGIS bundles its own Python | bash available; QGIS bundles its own Python |

**A1/A2 are blocking** — PyQGIS won't be found at the Linux path, so notebooks
fall back to headless (or fail to import `qgis`). Recommended fix: derive the
PyQGIS path from the running QGIS instead of hardcoding. Inside the plugin
(which *is* PyQGIS) the path is discoverable:

```python
# A robust, cross-platform PyQGIS path, computed in the plugin process:
import os, qgis
PYQGIS_PATH = os.path.dirname(os.path.dirname(qgis.__file__))  # the dir holding qgis/
```

`MarimoProcessManager` can compute this once and inject it (it already builds
`PYTHONPATH` from a list). For `_headless.py` (which runs in the notebook venv,
not the plugin), prefer a venv built against QGIS's own interpreter so `import
qgis` works without a hardcoded path; keep the Linux default as a fallback.

**A3** — make the isolation flag platform-aware:

```python
import sys, subprocess
kw = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if sys.platform == "win32" \
     else {"start_new_session": True}
subprocess.Popen([...], **kw)
```

> Track these as code changes; this plan assumes A1–A3 are applied before the
> Windows/macOS runs (otherwise expect headless-only behaviour).

---

## 2. Environment setup

QGIS bundles its **own** Python + PyQt6 on Windows and macOS (unlike Linux, where
it uses the system Python). So the notebook venv should be built against QGIS's
**bundled** interpreter, and `uv` must be on the `PATH` that QGIS inherits.

### Windows (OSGeo4W or standalone installer)

| Item | Typical location |
|------|------------------|
| PyQGIS bindings | `C:\Program Files\QGIS 4.x\apps\qgis\python` |
| Bundled interpreter | `C:\Program Files\QGIS 4.x\apps\Python3XX\python.exe` |
| Qt6 plugins | `C:\Program Files\QGIS 4.x\apps\qt6\plugins` |
| Plugin dir | `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\` (QGIS 4 may use `QGIS4`) |

1. Install **uv** (https://docs.astral.sh/uv/); confirm `uv --version` in a normal
   terminal, and that QGIS sees it (launch QGIS from the **OSGeo4W Shell** so it
   inherits `PATH`, or add uv to the system `PATH`).
2. Build the notebook venv against QGIS's bundled Python (manual — `qgis-env.sh`
   is bash):
   ```powershell
   uv venv --python "C:\Program Files\QGIS 4.x\apps\Python3XX\python.exe" --system-site-packages
   uv pip install marimo pandas numpy matplotlib geopandas
   ```
3. Install the plugin: build `marimo_launcher.zip` (`make package` on a machine
   with `make`, or download a release) → **Plugins ▸ Install from ZIP**.

### macOS (QGIS.app)

| Item | Typical location |
|------|------------------|
| PyQGIS bindings | `/Applications/QGIS.app/Contents/Resources/python` |
| Bundled interpreter | `/Applications/QGIS.app/Contents/MacOS/bin/python3` |
| Plugin dir | `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/` |

1. `brew install uv` (or the standalone installer); confirm QGIS inherits `PATH`
   (launch QGIS from Terminal for the first test, or add uv to a login PATH).
2. Build the venv against QGIS's bundled Python:
   ```bash
   uv venv --python /Applications/QGIS.app/Contents/MacOS/bin/python3 --system-site-packages
   uv pip install marimo pandas numpy matplotlib geopandas
   ```
3. Install the plugin from ZIP as above.

---

## 3. Pre-flight checks (per platform)

- [ ] `uv --version` works in a terminal, **and** QGIS can see `uv` (Plugins ▸
      Python Console: `import shutil; print(shutil.which("uv"))` → not `None`).
- [ ] PyQGIS path discovered: Python Console `import os, qgis;
      print(os.path.dirname(os.path.dirname(qgis.__file__)))`.
- [ ] Notebook venv imports both: `import PyQt6; import qgis.core` from the venv
      interpreter.

---

## 4. Functional test checklist (run identically on Windows and macOS)

Open a QGIS project with **at least one vector layer** (and one raster, for the
raster step). Then:

### A. Install & startup
- [ ] Plugin enables without error (Plugins ▸ Manage and Install ▸ Installed)
- [ ] Restart QGIS; **Log Messages ▸ "marimo bridge"** shows
      `bridge listening on 127.0.0.1:<port>`
- [ ] The **marimo toolbar button** appears and toggles the dock; **Plugins ▸
      marimo** menu entry present

### B. Dock — Browse & New
- [ ] Browse tab: pick a directory, `.py` notebooks are listed
- [ ] **New…** creates a starter stub; launching it opens marimo in the browser
- [ ] The launched notebook reaches **🟢 Live** (proves `import qgis_bridge` +
      bundled-path injection works on this OS)

### C. Bridge features (launch each example from the dock)
- [ ] `live_layers.py` → 🟢 Live; dropdown lists project layers
- [ ] `live_layers.py` → pick a layer → GeoDataFrame table (geopandas read)
- [ ] `push_result.py` → buffer → **Push** → new layer appears in QGIS Layers panel
- [ ] `selection_analysis.py` → select features in QGIS → **Load** → table + extent
- [ ] `render_map.py` → **Render** → PNG of the canvas displays
- [ ] `reactive_processing.py` → slider → **Run** → `native:buffer` result inserted
- [ ] Raster: a `get_layer` on a raster layer returns data (needs `rioxarray`)

### D. Headless fallback
- [ ] From a terminal: `uv run marimo edit example/live_layers.py` → **⚪ Headless**
      (no crash; `import qgis` works via the venv)

### E. Teardown / isolation
- [ ] Disable the plugin → bridge stops (no `bridge listening` after), dock and
      toolbar button removed, temp dir cleaned (no leftover `marimo_qgis_bridge_*`)
- [ ] A notebook crash (e.g. raise in a cell) does **not** crash QGIS (process
      isolation — verifies A3)

---

## 5. Results template

Record per platform; attach the "marimo bridge" log and any tracebacks.

| Check | Windows (QGIS 4.x) | macOS (QGIS 4.x) | Notes |
|-------|--------------------|------------------|-------|
| A. Install & startup | | | |
| B. Dock Browse/New | | | |
| C1 live_layers list | | | |
| C2 get_layer (vector) | | | |
| C3 push_result insert | | | |
| C4 selection + extent | | | |
| C5 render_map | | | |
| C6 reactive buffer | | | |
| C7 raster get_layer | | | |
| D. headless fallback | | | |
| E. teardown / isolation | | | |

---

## 6. Documentation to update after testing

- `README.md` Platform support table → mark Windows/macOS tested.
- `TROUBLESHOOTING.md` → add any platform-specific failure modes found (uv not on
  PATH, QGIS Python path, plugin dir location).
- `metadata.txt` → drop `experimental=True` once all three platforms pass.
