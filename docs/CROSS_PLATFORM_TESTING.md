# Cross-Platform Testing Plan — Windows & macOS

The plugin and bridge were built and verified on **Linux (QGIS 4.0.3 / Qt 6)**
and **Windows (QGIS 4.0.3 / OSGeo4W / Python 3.12.13)**. This plan verifies —
and where needed, fixes — the platform-specific pieces, in preparation for QGIS
Plugin Repository submission (Phase 4).

> **Launch model:** the plugin runs notebooks on **QGIS's own Python interpreter**
> (`<qgis_python> -m marimo …`, from `runtime.qgis_python()`). There is no separate
> venv to build and no `uv` requirement; marimo just needs to be installed into
> QGIS's Python (the dock offers to do this). The historical "find the bundled
> interpreter and build a venv" steps below are only relevant for the optional
> standalone dev workflow.

The bridge itself is mostly portable: it uses the Python standard library
(`http.server`, `urllib`, `secrets`, `tempfile`) and `qgis.PyQt`. The risk is
concentrated in a few **Linux-shaped assumptions** in how notebooks are launched
and how PyQGIS is located. Fix those first (§1), then run the checklist (§4).

---

## 1. Platform-specific code — now handled (verify per platform)

The Linux-specific assumptions A1–A3 are **implemented** as of the cross-platform
fix; the testing below verifies they actually work on Windows/macOS hardware.

| # | Location | What it does now | Status |
|---|----------|------------------|--------|
| A1 | `plugin/ui/process.py` + `runtime.pyqgis_dir()` | PYTHONPATH's PyQGIS dir is **derived from the running QGIS** (`os.path.dirname(os.path.dirname(qgis.__file__))`), correct on every OS; Linux path only as a last-resort fallback | ✅ fixed |
| A2 | `qgis_bridge/_headless.py` | tries `import qgis` first; on failure adds an **OS-specific PyQGIS candidate** (Linux `/usr/share/qgis/python`; macOS `…/QGIS*.app/Contents/Resources/python`; Windows `…\QGIS*\apps\qgis\python` via glob) and retries | ✅ fixed |
| A3 | `plugin/ui/process.py` | crash-isolation flag is **platform-aware**: `creationflags=CREATE_NEW_PROCESS_GROUP` on Windows, `start_new_session=True` on POSIX | ✅ fixed |
| A4 | `plugin/bridge/convert.py` — `os.chmod(dir, 0o700)` | no-op on Windows (NTFS ACLs); harmless | OK as-is |
| A5 | interpreter resolution | `runtime.qgis_python()` derives QGIS's own interpreter live (Windows `sys.prefix\python.exe`; Unix `sys.executable`/`sys.prefix/bin`); the plugin launches `-m marimo` on it — no venv to build | ✅ fixed |

**To verify on each platform:** open the QGIS Python Console and confirm
`runtime.pyqgis_dir()` resolves, then run the checklist (§4) — the "🟢 Live" and
`import qgis_bridge` steps prove A1, the headless step proves A2, and the
crash-isolation teardown step proves A3.

---

## 2. Environment setup

The plugin runs notebooks on **QGIS's own interpreter**, so there is no venv to
build and `uv` is not required. The only setup is **installing marimo (and any
libraries notebooks import) into QGIS's Python** — the dock offers to do this on
first launch.

### Windows (OSGeo4W or standalone installer)

| Item | Typical location |
|------|------------------|
| PyQGIS bindings | `C:\Program Files\QGIS 4.x\apps\qgis\python` (resolved live by `runtime.pyqgis_dir()`) |
| Interpreter | derived from `sys.prefix` (test machine: `C:\OSGeo4W\apps\Python312\python.exe`) |
| Plugin dir | `%APPDATA%\QGIS\QGIS4\profiles\default\python\plugins\marimo_launcher` |

1. Install the plugin: build `marimo_launcher.zip` (`make package`, or download a
   release) → **Plugins ▸ Install from ZIP**.
2. Install marimo into QGIS's Python (the dock offers this automatically; manual
   equivalent):
   ```powershell
   & cmd /c "C:\OSGeo4W\bin\python-qgis.bat -m pip install marimo geopandas"
   ```

### macOS (QGIS.app)

| Item | Typical location |
|------|------------------|
| PyQGIS bindings | `/Applications/QGIS.app/Contents/Resources/python` (resolved live) |
| Interpreter | derived from `sys.executable` / `sys.prefix/bin` |
| Plugin dir | `~/Library/Application Support/QGIS/QGIS4/profiles/default/python/plugins/marimo_launcher` |

1. Install the plugin from ZIP as above.
2. Install marimo into QGIS's bundled Python. The bundle Python is often
   read-only/externally managed, so use `--user`:
   ```bash
   /Applications/QGIS.app/Contents/MacOS/bin/python3 -m pip install --user marimo geopandas
   ```

---

## 3. Pre-flight checks (per platform)

- [ ] QGIS interpreter resolves: Python Console
      `from marimo_launcher.runtime import qgis_python; print(qgis_python())` →
      an existing `python(.exe)`.
- [ ] marimo importable in that interpreter: dock launch does not prompt to
      install (or accept the prompt once), or run `<qgis_python> -c "import marimo"`.
- [ ] PyQGIS path discovered: Python Console `import os, qgis;
      print(os.path.dirname(os.path.dirname(qgis.__file__)))`.

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

### B. Dock — Setup, Browse & New
- [ ] Setup tab: environment report renders (QGIS / Python / GDAL / PROJ / GEOS /
      Qt versions, package table, CLI-tools table); **Refresh report** works
- [ ] Setup tab: **Save report as…** writes a Markdown file
- [ ] Setup tab: **Download examples…** fetches `example/` + `notebooks/` into a
      chosen folder (stdlib urllib+zipfile via a QgsTask)
- [ ] Browse tab: pick a directory, `.py` notebooks are listed
- [ ] **New…** creates a starter stub; launching it opens marimo in the browser
- [ ] First launch with marimo absent prompts to `pip install marimo` into QGIS's
      Python; after install + re-launch it runs
- [ ] The launched notebook reaches **🟢 Live** (proves `import qgis_bridge` +
      bundled-path injection works on this OS)
- [ ] Launch log written to `%TEMP%\marimo_qgis_logs\<notebook>.log` (or OS temp
      equivalent); no flashing console window

### C. Bridge features (launch each example from the dock)
- [ ] `live_layers.py` → 🟢 Live; dropdown lists project layers
- [ ] `live_layers.py` → pick a layer → GeoDataFrame table (geopandas read)
- [ ] `push_result.py` → buffer → **Push** → new layer appears in QGIS Layers panel
- [ ] `selection_analysis.py` → select features in QGIS → **Load** → table + extent
- [ ] `render_map.py` → **Render** → PNG of the canvas displays
- [ ] `reactive_processing.py` → slider → **Run** → `native:buffer` result inserted
- [ ] Raster: a `get_layer` on a raster layer returns data (needs `rioxarray`)

### D. Headless fallback
- [ ] From a terminal: `<qgis_python> -m marimo edit example/live_layers.py` →
      **⚪ Headless** (no bridge env, so headless is correct; `import qgis` works
      because it is QGIS's own interpreter)

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

- `README.md` Platform support table → mark macOS tested (Windows already is).
- `TROUBLESHOOTING.md` → add any platform-specific failure modes found (marimo
  missing from QGIS's Python, externally-managed pip on Linux/macOS, plugin dir
  location).
- `metadata.txt` → drop `experimental=True` once all three platforms pass.
