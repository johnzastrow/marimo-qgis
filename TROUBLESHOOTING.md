# Troubleshooting Marimo + QGIS4

## Current Status

**WORKING**: Full QGIS4 + marimo integration confirmed via `marimo export html`.

- QGIS 4.0.0-Norrköping (`/usr/share/qgis/python`)
- `QgsApplication` initialises headlessly with `gui=False` + `QT_QPA_PLATFORM=offscreen`
- Sample data at `/usr/share/qgis/resources/data/world_map.gpkg`

**RESOLVED**: The previous "cells not executing" issue was a stale `__marimo__/session/` cache.
The session cache is only populated by the interactive edit server; `marimo export html` always re-executes.

## Verified Working

```bash
# QGIS imports work with this command:
cd /home/jcz/Github/marimo_qgis
PYTHONPATH=/usr/share/qgis/python uv run python -c "
import sys
sys.path.insert(0, '/usr/share/qgis/python')
from qgis.core import Qgis
print('QGIS Version:', Qgis.version())
"
# Output: QGIS Version: 4.0.0-Norrköping
```

## Setup (Working)

```bash
cd /home/jcz/Github/marimo_qgis
rm -rf .venv
uv venv --python 3.13.7 --system-site-packages
uv pip install marimo
```

## Notebook Format (Recommended)

```python
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "marimo",
# ]
# ///

import marimo as mo

__generated_with = "0.21.1"

app = mo.App()


@app.cell
def _():
    import sys as _sys
    _sys.path.insert(0, "/usr/share/qgis/python")
    import marimo as _mo
    _mo.md("# QGIS4 + Marimo Test")
    return


@app.cell
def _():
    import sys as _sys
    _sys.path.insert(0, "/usr/share/qgis/python")
    from qgis.core import Qgis as _Qgis
    
    qgis_info = {
        "QGIS Version": _Qgis.version(),
        "QGIS VERSION": _Qgis.QGIS_VERSION,
    }
    return (qgis_info,)
```

## Issues Encountered

### 1. Kernel Not Found / Cells Not Executing

**Symptoms**:
- `marimo edit` opens in browser but cells show no output
- Session cache shows empty outputs: `"outputs": []`
- No error messages in browser console

**What was tried**:
- Setting `PYTHONPATH` at command line
- Setting `sys.path` inside cells with underscore prefix (e.g., `_sys`)
- Using `--system-site-packages` for venv to get system PyQt6
- Adding `__generated_with` marker
- Using different import styles

**Possible causes**:
- Marimo's kernel process may not be starting properly
- The subprocess running the notebook cells may not have the PYTHONPATH set
- There may be a Qt/GUI initialization issue even in headless mode

### 2. Qt Version Mismatch

**Error**: `ImportError: /lib/x86_64-linux-gnu/libQt6Network.so.6: undefined symbol`

**Solution**: Use `--system-site-packages` flag when creating venv to use system's PyQt6:

```bash
uv venv --python 3.13.7 --system-site-packages
```

### 3. Python Version Mismatch

**Error**: `Python 3.12.12 is incompatible with requirement: >=3.13`

**Solution**: Use Python 3.13.7 explicitly:
```bash
uv venv --python 3.13.7
```

### 4. uv Auto-Resetting Python Version

**Issue**: uv was recreating the venv with Python 3.12 despite specifying 3.13

**Solution**: Remove `.python-version` file if it exists:
```bash
rm -f .python-version
```

## Next Steps

1. Try running marimo with `--sandbox` mode which creates isolated environment
2. Try different marimo versions
3. Check if there's a firewall or network issue preventing kernel from starting
4. Try running marimo in a completely fresh directory
5. Check if QGIS's Qt plugins need to be loaded differently
