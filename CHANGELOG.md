# Changelog

All notable changes to the **marimo Launcher** QGIS plugin are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Versions correspond to `plugin/metadata.txt` `version=`.

## [Unreleased]

## [0.6.0] - 2026-06-12

### Added
- Setup-tab environment report now lists **"Packages available to marimo &
  QGIS"** — installed packages relevant to the QGIS/data stack and marimo's full
  dependency tree, plus anything you installed yourself, each annotated with its
  `location` (`user` per-user site vs `system` site-packages). Unrelated
  OS/system packages (apt, dbus, …) are omitted so a saved report is a clean,
  shareable inventory.
- The report shows the interpreter's **site-package directories** (user site +
  system site-packages), so you can see where a `--user` install lands.
- The dock now **records packages it installs** (in QgsSettings) so they appear
  in the report on every platform — important on Windows/macOS, where dock
  installs go into the bundled site-packages and can't be told apart by location.

## [0.5.0] - 2026-06-12

### Added
- **"Detect packages"** button (Browse tab): inspects the selected notebook and
  pre-fills the Setup-tab package field for review/install. It reuses marimo's
  own intelligence — reads PEP 723 `# /// script` dependencies (via marimo's
  `read_pyproject_from_script`) and maps imports missing from QGIS's Python to
  PyPI names through marimo's 776-entry table (e.g. `cv2` → `opencv-python`).
- **Post-install verification**: after a detect-driven install the dock re-probes
  the notebook's imports and warns if a package name was wrong or insufficient
  (e.g. a slim distribution needing an extra like `pydantic-ai-slim[anthropic]`)
  instead of failing silently.

### Notes
- Packages are installed into **QGIS's own Python**, not marimo's "install with
  uv" sandbox venv (which a dock-launched notebook can't import from).

## [0.4.1] - 2026-06-12

### Removed
- The crash-based "auto-offer to install a missing package" path. Testing showed
  it never fired for missing imports: `marimo edit` catches `ModuleNotFoundError`,
  keeps the server alive, and surfaces the error in the **browser** (not the
  captured log, and the process doesn't exit). The Setup-tab installer remains
  the supported way to add packages; install by reading the name off the browser
  error (or via "Detect packages").

## [0.4.0] - 2026-06-11

### Added
- **Setup-tab package installer**: a field + Install button to install arbitrary
  Python packages into QGIS's own interpreter (where notebooks run), using the
  same cross-platform pip bootstrap as the marimo preflight.

### Security
- Package names are allowlist-validated (`validate_package_names`: PEP 508 names
  with optional extras/version specs). A leading `-` is rejected to block
  pip-argument injection (e.g. `--index-url`), and tokens are passed as
  subprocess argv (`shell=False`) as defence in depth.

## [0.3.3] - 2026-06-11

### Fixed
- Toolbar icon rendered broken: `marimoqgis.svg` was sized as a full US-Letter
  page, so QGIS scaled the page (not the artwork) into the square toolbar slot.
  Replaced with a 180×180 square SVG cropped to the mark.

## [0.3.2] - 2026-06-11

### Changed
- marimo install is now a **pip-only, cross-platform bootstrap**: ensures pip
  (via `ensurepip` when the module is missing), then progressively falls back
  `plain → --user → --user --break-system-packages`. The same call works whether
  QGIS ships its own writable Python with pip (Windows/macOS) or runs on a
  pip-less, root-owned, externally-managed system Python (Linux). No `uv` on the
  install path.

### Fixed
- On a Linux system Python with neither pip nor ensurepip, the install now prints
  a clear, actionable message (`sudo apt install python3-pip`) instead of a
  cryptic `No module named pip`.

## [0.3.1] - 2026-06-11

### Fixed
- `ResourceWarning: subprocess N is still running` from the marimo install — the
  `pip install` subprocess was discarded and garbage-collected mid-run. It is now
  tracked on the process manager and polled to completion, with output captured
  to a log and a completion/failure dialog. This also gives the install real
  feedback on Linux/macOS (the old code only opened a visible console on Windows).

## [0.3.0] - 2026-06-11

### Added
- **Launch model: run notebooks on QGIS's own Python interpreter**
  (`<qgis_python> -m marimo …`, derived live from the running QGIS). Always
  ABI-compatible with PyQGIS and tracks QGIS Python upgrades automatically — no
  version to pin and no separate virtualenv.
- **Setup tab** with an environment report (QGIS / Python / GDAL / PROJ / GEOS /
  SpatiaLite / Qt versions, packages, CLI tools), Save-report, and
  Download-examples.
- Per-launch logging to `…/marimo_qgis_logs/<notebook>.log`, suppressed console
  window, and an early-exit dialog surfacing the log tail.

### Changed
- `uv` is now **optional / dev-only** — removed from the plugin launch path.

### Fixed
- Windows `AssertionError: SRE module mismatch` (console flashed and closed) —
  caused by the old `uv run` building a Python 3.14 venv against QGIS's 3.12
  stdlib. Eliminated by launching on QGIS's own interpreter.

## [0.2.1] - 2026-06-11

### Added
- `marimoqgis.svg` toolbar icon and native dock toggle. (Baseline prior to the
  QGIS-own-Python launch model.)

[Unreleased]: https://github.com/johnzastrow/marimo-qgis/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/johnzastrow/marimo-qgis/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/johnzastrow/marimo-qgis/compare/v0.4.1...v0.5.0
[0.4.1]: https://github.com/johnzastrow/marimo-qgis/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/johnzastrow/marimo-qgis/compare/v0.3.3...v0.4.0
[0.3.3]: https://github.com/johnzastrow/marimo-qgis/compare/v0.3.2...v0.3.3
[0.3.2]: https://github.com/johnzastrow/marimo-qgis/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/johnzastrow/marimo-qgis/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/johnzastrow/marimo-qgis/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/johnzastrow/marimo-qgis/releases/tag/v0.2.1
