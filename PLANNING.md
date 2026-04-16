# marimo-qgis — Product Planning: HTTP Bridge Architecture (with In-Process Option)

*Date: 2026-04-15*

---

## Contents

1. [Situation Assessment](#1-situation-assessment)
2. [The In-Process Alternative: Architecture and Trade-offs](#2-the-in-process-alternative-architecture-and-trade-offs)
3. [HTTP Server vs In-Process Embedding: Full Trade-off Analysis](#3-http-server-vs-in-process-embedding-full-trade-off-analysis)
4. [Features Available Right Now](#4-features-available-right-now)
5. [Use Cases, Failure Conditions, and Mode Boundaries](#5-use-cases-failure-conditions-and-mode-boundaries)
6. [Architecture Reference (Phases 1–4: HTTP)](#6-architecture-reference-phases-14-http)
7. [Phased Roadmap](#7-phased-roadmap)
8. [Notebook Materialization: Portable Headless Export](#8-notebook-materialization-portable-headless-export)
9. [What rqgis Code We Reuse](#9-what-rqgis-code-we-reuse)
10. [Example: What a Live Notebook Looks Like](#10-example-what-a-live-notebook-looks-like)
11. [Open Questions](#11-open-questions)

---

## 1. Situation Assessment

### What marimo-qgis does today

The existing repo is a **detached-process** integration:

```
uv run marimo edit notebook.py
  └── marimo kernel (subprocess)
        ├── QgsApplication([], False)   # its own headless QGIS instance
        ├── initQgis()
        └── reads/writes files directly — no running QGIS session involved
```

**Strengths:**
- Works. Full QGIS 4 + marimo integration proven on Linux.
- Self-contained notebooks — no plugin required.
- Exportable HTML reports (`marimo export html`).
- Reactive UI (sliders drive QGIS processing re-runs).

**Structural limitations:**
- Notebooks are **blind to any running QGIS session** — each initialises its own
  throwaway `QgsApplication`, loads its own layers from disk, and has no awareness of
  what the user has open in the desktop application.
- **One-way data flow**: notebook reads files, cannot push results into a live project.
- Notebooks carry Qt/offscreen boilerplate that confuses new users and breaks when
  `uv run` sandboxes the environment (PEP 723 issue).
- The launcher plugin is purely a `subprocess.Popen` wrapper — it adds no integration
  value once the notebook is open.

### What rqgis does (and what it proves)

rqgis is a mature QGIS 3.30 plugin that embeds a full R console in a Qt dock widget.
Its core insight is the **bidirectional bridge pattern** using Qt's cross-thread dispatch:

```
QGIS plugin (Python/Qt main thread)
  ├── QGISApi (QObject) — executes QGIS operations when called from the worker thread
  ├── RWorker (QObject on QThread) — owns the R bridge, dispatches via QMetaObject
  └── RBridge — manages an R subprocess, JSON protocol over stdin/stdout

R subprocess (separate OS process)
  └── QgisProject R6 object — sends JSON requests, receives JSON responses
```

The critical mechanism is `QMetaObject.invokeMethod(..., Qt.BlockingQueuedConnection)`.
This Qt primitive lets any thread call a slot on a QObject that lives on the Qt main
thread, block until it completes, and read the result — safely, without locks.

rqgis proves that a language kernel can have **live, bidirectional, thread-safe access
to the running QGIS project**. Its open roadmap items (QGIS 4 compatibility, LSP) are
things we land for free.

---

## 2. The In-Process Alternative: Architecture and Trade-offs

When considering how the marimo kernel should talk to QGIS, several IPC options exist:

| Approach | Elegance | Why |
|---|---|---|
| HTTP server on localhost | Low | Adds a network stack, port management, auth tokens, and request/response serialisation to what is a same-machine call. Debuggable but heavyweight. |
| Unix domain socket | Medium | Faster than TCP, no port conflicts, but still requires a wire protocol. Slightly better shape, same fundamental cost. |
| stdin/stdout pipes (rqgis) | N/A | Can't use: we don't own marimo's kernel stdio. marimo starts its own asyncio event loop and WebSocket server. |
| **In-process embedding** | **High** | If the marimo kernel runs in the same Python process as QGIS, cells can call `QMetaObject.invokeMethod` directly. No network, no serialisation protocol, no auth — Python objects cross a thread boundary. |

### The in-process architecture

marimo exposes `marimo.create_asgi_app()`, which lets us embed the marimo server
**inside an existing Python process** — the QGIS plugin process — in a background
asyncio thread. The kernel that executes notebook cells runs in that same thread,
in the same Python interpreter as QGIS.

The `qgis_bridge` module becomes a thin wrapper around `QMetaObject.invokeMethod`,
the exact same mechanism rqgis already uses — just without the subprocess and without
the JSON-over-pipes protocol between them.

```
QGIS process (Python, Qt main thread)
│
├── MarimoPlugin (manages lifecycle)
│
├── QGISBridgeAPI (QObject, lives on Qt main thread)
│     Executes QGIS operations on the thread that owns all Qt objects.
│     Returns plain Python objects (dicts, lists, GeoDataFrames) —
│     safe to pass across thread boundaries.
│
└── MarimoServerThread (daemon thread, asyncio event loop)
      ├── marimo ASGI server
      │     Serves the notebook UI to the user's browser via WebSocket.
      │     Browser still opens localhost:2718 — same as today.
      │
      └── marimo kernel (executes notebook cell code in this thread)
            └── cell code:
                  from qgis_bridge import QgisBridge
                  qgis = QgisBridge()   # finds QGISBridgeAPI via module-level ref
                  gdf = qgis.get_layer("roads")
                     ↑
                     QMetaObject.invokeMethod(
                         api, "dispatch",
                         Qt.BlockingQueuedConnection,       # blocks this thread
                         Q_ARG('PyQt_PyObject', request)    # until Qt thread responds
                     )
                     → Qt main thread: converts QgsVectorLayer → GeoDataFrame
                     → returns GeoDataFrame to kernel thread
                     NO HTTP. NO FILE TRANSFER. NO AUTH.
```

### How QgisBridge finds QGISBridgeAPI without a network

Both live in the same Python interpreter. A module-level reference is enough:

```python
# qgis_bridge/__init__.py
_api = None

def _register(api):          # called by plugin at startup
    global _api
    _api = api

class QgisBridge:
    def __init__(self):
        if _api is None:
            # Fallback: headless mode (existing marimo-qgis behaviour)
            raise RuntimeError("Not running inside QGIS — use headless mode instead")
        self._api = _api

    def get_layer(self, name):
        QMetaObject.invokeMethod(
            self._api, "dispatch",
            Qt.BlockingQueuedConnection,
            Q_ARG('PyQt_PyObject', {"method": "get_layer", "name": name})
        )
        return self._api.result   # GeoDataFrame, already converted on Qt thread
```

### Comparison to rqgis

The table below compares rqgis to **in-process mode** (§2's subject) and to
**HTTP mode** (the recommended default from §3 onward).

| Dimension | rqgis | This project (in-process) | This project (HTTP, default) |
|---|---|---|---|
| Language kernel | R subprocess (OS process) | marimo kernel (thread in QGIS process) | marimo kernel (separate OS process) |
| IPC mechanism | JSON over stdin/stdout pipes | `QMetaObject.invokeMethod` (in-process) | HTTP + JSON over loopback TCP |
| Data transfer | temp files (.fgb, .tif) | Python objects directly (no files for vectors) | temp files (.fgb, .tif) via HTTP response |
| Network required | No | No | Loopback only (127.0.0.1) |
| Auth required | No | No | Session token (env var) |
| Large raster transfer | .tif temp file | .tif temp file (unavoidable for format conversion) | .tif temp file (unavoidable for format conversion) |
| QGIS version | 3.30 (not 4) | 4.0 native | 4.0 native |
| Process isolation | N/A (R is already a subprocess) | No (kernel in QGIS process) | Yes (kernel is a separate process) |

In-process mode eliminates temp files for vectors at the cost of process isolation.
HTTP mode preserves the same temp-file pattern as rqgis while adding crash safety.

### Fallback: headless mode unchanged

When the plugin is not running, `MARIMO_QGIS_PORT` is absent from the environment and
`QgisBridge()` raises `RuntimeError`. Notebooks catch this and fall back to the
existing pattern: initialise their own `QgsApplication`, load from disk, no live
project access. Both modes can coexist in the same notebook via:

```python
from qgis_bridge import QgisBridge, HeadlessQGIS
try:
    qgis = QgisBridge()              # live mode: MARIMO_QGIS_PORT present → HTTP bridge
except RuntimeError:
    qgis = HeadlessQGIS()            # headless fallback: own QgsApplication from disk
```

There is no `MARIMO_QGIS_MODE` env var — mode is determined solely by the presence or
absence of `MARIMO_QGIS_PORT`. This keeps the interface surface minimal and avoids
conflicting signals.

---

## 3. HTTP Server vs In-Process Embedding: Full Trade-off Analysis

Both approaches are genuinely viable. This section works through the trade-offs
honestly so the architectural choice is documented and revisitable.

### What each approach looks like end-to-end

**HTTP server approach**

```
QGIS process                          marimo subprocess
├── MarimoPlugin                       └── marimo kernel
└── QgisBridgeServer                         └── cell code:
      └── aiohttp on 127.0.0.1:PORT              from qgis_bridge import QgisBridge
            ├── GET /api/layers                   qgis = QgisBridge()  # reads env vars only
            ├── GET /api/layer/{name}             gdf = qgis.get_layer("roads")
            ├── POST /api/insert                    → HTTP GET http://127.0.0.1:PORT/api/layer/roads
            └── GET /api/render                    → server saves .fgb to /tmp/abc.fgb
                                                   → HTTP response: {"path": "/tmp/abc.fgb"}
                                                   → geopandas.read_file("/tmp/abc.fgb")
```

`QgisBridge()` takes no arguments. It reads `MARIMO_QGIS_PORT` and `MARIMO_QGIS_TOKEN`
exclusively from environment variables — never from code. Hardcoding connection details
is actively refused (see Scenario 12).

**In-process embedding approach**

```
QGIS process
├── MarimoPlugin
├── QGISBridgeAPI (QObject, Qt main thread)
└── MarimoServerThread (asyncio thread)
      └── marimo kernel (same thread)
            └── cell code:
                  from qgis_bridge import QgisBridge
                  qgis = QgisBridge()   # module-level reference, no network
                  gdf = qgis.get_layer("roads")
                    → QMetaObject.invokeMethod(BlockingQueuedConnection)
                    → Qt thread: iterates features → builds GeoDataFrame
                    → GeoDataFrame returned as Python object
```

---

### Pros and cons

#### HTTP server

**Pros**

- **Process isolation.** The marimo kernel is a separate OS process. A crash, memory
  leak, or runaway computation in a notebook cannot corrupt or hang the QGIS process.
  QGIS stays alive; the user restarts the notebook process. This is the same isolation
  model that JupyterLab uses, and it is the reason Jupyter chose it.

- **Debuggability.** The bridge is observable with ordinary tools: `curl`, browser
  DevTools, Wireshark, or a simple `print()` in the server handler. The protocol is
  self-describing JSON. If something goes wrong, you can replay any request
  independently of QGIS.

- **Multiple simultaneous notebooks against the same server.** Any number of marimo
  processes can call the bridge server concurrently. HTTP itself is concurrent, but
  safe serialisation of QGIS operations is provided by
  `QMetaObject.invokeMethod(Qt.BlockingQueuedConnection)`: each HTTP handler dispatches
  to the Qt main thread, which processes one call at a time. aiohttp's async handlers
  queue on the QGIS side naturally, so no explicit locking is needed in the server code.

- **Language agnostic.** The HTTP API can be called by Jupyter notebooks, R scripts,
  shell scripts, or any future language kernel — not just marimo. This gives the bridge
  long-term value beyond the immediate use case.

- **marimo kernel isolation is preserved.** marimo's own sandbox and virtual
  environment isolation features (`uv run`, PEP 723 headers) continue to work exactly
  as designed. The kernel's Python environment does not need to contain QGIS libraries
  at all — only the thin `qgis_bridge` client package.

- **marimo API changes don't affect the bridge.** If marimo changes how it starts its
  kernel, restructures its ASGI app, or switches event loop implementations, the HTTP
  server is unaffected. The bridge is decoupled from marimo's internals.

- **Easier to port to other notebook systems.** If a user wants to call the bridge from
  a standard Jupyter kernel, a Quarto document, or a plain Python script, the HTTP API
  works unchanged.

**Cons**

- **Data transfer overhead for large layers.** Every `get_layer()` call writes the
  layer to a temp file (FlatGeobuf for vectors, GeoTIFF for rasters) and then the
  client reads it back. For a layer with millions of features this is slow and involves
  two full I/O passes. The in-process approach can convert directly in memory.

- **Port management complexity.** The server must bind to a free port at startup,
  communicate that port to the marimo subprocess (via env var or config file), and
  handle the case where the port is already in use. This is solvable but is real
  plumbing that must be written and maintained.

- **Authentication surface.** Requests from localhost are generally safe, but a session
  token is still needed to prevent other processes on the machine from querying the
  bridge (relevant on multi-user systems). The token must be generated, distributed
  to the subprocess, and validated on every request.

- **Extra dependency.** An HTTP server library (`aiohttp` or `flask`) must be added
  to the QGIS plugin's dependencies. These are not part of the QGIS 4 distribution
  and must be installed separately.

- **Latency per call.** A local TCP round-trip adds ~0.1–1 ms per call. For one-off
  layer loads this is imperceptible. For tight reactive loops (e.g., a slider that
  re-queries on every change) it can add up.

---

#### In-process embedding

**Pros**

- **No IPC overhead for vector data.** A `QgsVectorLayer` is iterated on the Qt main
  thread and the result is returned as a GeoDataFrame Python object across the thread
  boundary. No file I/O, no serialisation, no temp files. For large vector layers the
  performance difference is substantial.

- **Architectural simplicity.** There is no wire protocol, no server lifecycle to manage,
  no port to allocate, no auth token to distribute. The `qgis_bridge` module is a thin
  wrapper around a Qt primitive that both projects already depend on.

- **No additional dependencies.** `QMetaObject.invokeMethod` is part of PyQt6/PyQt5,
  which the QGIS plugin already imports. No new packages are needed.

- **Shared Python environment.** If a cell needs a QGIS type directly (e.g., to
  inspect a `QgsCoordinateReferenceSystem` object), it can import it from `qgis.core`
  without any serialisation step. The full PyQGIS API is available to cell code, not
  just the subset exposed through the bridge.

- **Instant startup.** No server socket bind, no port negotiation, no subprocess
  launch. The bridge is ready the moment the plugin loads.

**Cons**

- **No process isolation — the critical risk.** A notebook cell that calls
  `while True: pass`, allocates unbounded memory, or triggers a C-level segfault in a
  GDAL driver runs inside the QGIS process. The result is a frozen or crashed QGIS
  session. The user loses unsaved project work. This is the same reason Jupyter runs
  kernels as subprocesses, and it is a significant UX risk for a tool used by
  non-developers.

- **marimo embedding API is not stable or fully documented.** `marimo.create_asgi_app()`
  exists but its support for running arbitrary notebook paths, managing kernel
  lifecycle, and handling kernel restarts in an embedded context is not a first-class
  supported scenario. Each marimo version update becomes a potential breakage point for
  the embedding layer, not just for the public API. This is a meaningful ongoing
  maintenance burden.

- **asyncio + Qt event loop interaction requires care.** A `Qt.BlockingQueuedConnection`
  call from inside an asyncio coroutine blocks the asyncio event loop thread while
  waiting for the Qt main thread. For short operations this is fine. For a slow QGIS
  operation (rendering a complex map, running a Processing algorithm) it will stall the
  marimo WebSocket handler, which can cause the browser UI to appear frozen. Mitigating
  this requires wrapping blocking calls in `run_in_executor`, adding latency and
  complexity.

- **Concurrency race condition on `_api.result`.** The rqgis pattern stores the return
  value of a `BlockingQueuedConnection` call as `self.result` on the QObject. With a
  single R process this is safe. With multiple notebook cells potentially running
  concurrently (marimo supports parallel cell execution), two calls can race on the same
  `result` attribute. This requires a per-call lock or a redesigned return mechanism,
  adding complexity that HTTP handles for free via independent request/response pairs.

- **QGIS plugin environment constraints.** The marimo server thread shares the QGIS
  Python environment, including its `sys.path`, installed packages, and PyQt6 import
  state. Installing a package in the notebook (`pip install` from a cell) modifies the
  shared environment. Dependencies that conflict with PyQt6 or QGIS's own packages can
  destabilise the QGIS session.

- **Harder to debug.** There is no observable wire between the kernel and QGIS. When a
  `get_layer` call hangs, the symptoms are: asyncio thread blocked, Qt main thread
  busy, marimo UI frozen, no error message. Reproducing and diagnosing the deadlock
  requires understanding both the Qt event loop and the asyncio scheduler simultaneously.

- **No standalone notebook support.** A notebook that imports `qgis_bridge` can only
  run when the QGIS plugin is loaded. It cannot be shared with a colleague and run
  headlessly on a server. The HTTP approach preserves the option of running the bridge
  server standalone (separate from a QGIS desktop session) on a headless machine.

---

### Summary table

| Criterion | HTTP server | In-process |
|---|---|---|
| Process isolation (crash safety) | Yes — kernel crash can't kill QGIS | No — notebook crash = QGIS crash |
| Large vector transfer speed | Slow (temp file round-trip) | Fast (direct Python object) |
| Large raster transfer speed | Slow (same) | Slow (temp file still needed for format conversion) |
| Wire protocol complexity | Medium (JSON over HTTP) | None |
| Port / auth management | Required | Not needed |
| Extra dependencies | `aiohttp` or `flask` | None |
| marimo API coupling | Loose (only calls the kernel externally) | Tight (`create_asgi_app` internals) |
| Multi-notebook concurrency | Safe (HTTP serialises naturally) | Race condition risk on `_api.result` |
| asyncio / Qt loop interaction | None (separate processes) | Careful handling required |
| Debuggability | High (curl, logs, replay) | Low (no observable wire) |
| Notebook portability (share / CI) | Yes (run bridge server anywhere) | No (requires live QGIS plugin) |
| Full PyQGIS API in cells | No (only bridge methods) | Yes (direct import) |
| Startup time | ~200 ms (socket bind) | Instant |
| Per-call latency | ~0.5 ms (loopback TCP) | ~0 ms |

---

### Recommended approach: HTTP server with a performance escape hatch

The process isolation argument is decisive for a tool aimed at GIS analysts who are
not necessarily Python developers. A runaway cell should not destroy an unsaved QGIS
project. HTTP also sidesteps the asyncio/Qt interaction risk, the marimo embedding API
instability, and the concurrency race condition — three problems that each require
significant engineering to solve correctly in the in-process model.

The performance gap (temp file I/O for vector data) is real but manageable:

- FlatGeobuf write + read for a 50,000-feature layer takes ~200 ms on a local SSD.
  This is acceptable for interactive analysis where the user is looking at results,
  not benchmarking throughput.
- For very large layers, the bridge can offer a `get_layer_sample(n=1000)` method that
  returns only the first N features, which avoids the full transfer cost for exploratory
  work.
- If performance becomes a bottleneck in practice (Phase 4+), the bridge server can
  be extended with a shared-memory channel (e.g., Apache Arrow IPC over a memory-mapped
  file) for bulk data transfer while keeping the HTTP control plane. This is an additive
  optimisation, not an architectural replacement.

The in-process approach is the right answer if:
- The primary audience is experienced Python/QGIS developers who understand the
  isolation trade-off and want full PyQGIS access in cells.
- marimo stabilises and documents a first-class embedding API.
- The project later adds a "developer mode" flag that enables in-process operation
  for users who explicitly opt in.

Both modes can coexist: the plugin offers in-process as an opt-in advanced mode
(a checkbox in plugin settings), while HTTP is the default safe mode for general use.

### Features exclusive to one approach

Most capabilities are achievable with either approach, just with different effort.
A smaller set are genuinely exclusive — possible with one architecture and
structurally impossible (not just inconvenient) with the other.

#### Exclusively possible with in-process embedding

These features require actual Python objects from the live QGIS runtime to exist
inside the notebook's cell scope. HTTP cannot provide this because PyQGIS objects
are C++-backed Qt objects that cannot be serialised across a process boundary.

**1. Live PyQGIS objects in cell scope**

```python
# In-process: this just works
from qgis.core import QgsCoordinateReferenceSystem, QgsGeometry
layer = qgis.get_layer("roads")   # returns the actual QgsVectorLayer
crs   = layer.crs()               # QgsCoordinateReferenceSystem instance
wkt   = crs.toWkt()               # full WKT2 representation, no bridge endpoint needed
```

HTTP can return a GeoDataFrame representation of the layer's data, but it cannot
return the `QgsVectorLayer` object itself. Any PyQGIS method not explicitly exposed
by the bridge is inaccessible. In-process gives cells the full, unrestricted PyQGIS
surface with no mediation layer.

**2. QGIS signal/slot connections from cell code**

```python
# In-process: a cell can connect to any QGIS signal
from qgis.core import QgsProject

def on_layer_added(layer):
    print(f"Layer added: {layer.name()}")

QgsProject.instance().layerWasAdded.connect(on_layer_added)
```

This is not approximable with HTTP. Signals are a live in-process notification
mechanism — they fire synchronously inside the QGIS process and cannot be forwarded
over a request/response protocol without either polling (which misses events between
polls) or a persistent push channel (SSE/WebSocket from the bridge server — possible
but a significant engineering addition that still cannot replicate zero-latency
synchronous signal delivery).

**3. Registering new Processing algorithms in the live session**

```python
# In-process: a cell can define and register a new algorithm into the running registry
from qgis.core import QgsProcessingAlgorithm, QgsApplication

class MyAlgorithm(QgsProcessingAlgorithm):
    ...

QgsApplication.processingRegistry().addAlgorithm(MyAlgorithm())
# It now appears in the QGIS Processing Toolbox and can be called by other tools
```

HTTP can call algorithms that already exist in the registry. It cannot add new ones
to the live session because that requires the algorithm Python class to be present
in the QGIS process's memory.

**4. Full `iface` (QgisInterface) access**

```python
# In-process: iface is accessible if the plugin passes it to the bridge
iface.mapCanvas().setExtent(my_extent)
iface.messageBar().pushMessage("Analysis complete", Qgis.Success)
iface.actionSaveProject().trigger()
iface.setActiveLayer(my_layer)
```

`iface` is the QGIS GUI interface object. It controls the map canvas, layer panel,
message bar, toolbars, and map tools. HTTP could expose individual operations as
endpoints (`POST /api/zoom-to-extent`, etc.), but the set of `iface` methods is large
and mostly undocumented — building a complete HTTP wrapper is impractical. In-process
gives unrestricted access.

**5. Map canvas interaction — click events into notebook cells**

```python
# In-process: a cell can install a map tool that feeds click coordinates into marimo state
from qgis.gui import QgsMapToolEmitPoint

class ClickTool(QgsMapToolEmitPoint):
    def canvasReleaseEvent(self, event):
        point = self.toMapCoordinates(event.pos())
        # update a marimo reactive state with the clicked coordinate

tool = ClickTool(iface.mapCanvas())
iface.mapCanvas().setMapTool(tool)
```

This enables notebooks that are driven by interactive map clicks — select a point,
see an analysis of what's nearby. HTTP cannot replicate this: it has no push channel
from QGIS to the notebook, and map tool events fire at interactive speeds that polling
cannot match.

**6. Starting and committing layer edit sessions**

```python
# In-process: a cell can open, modify, and commit an edit session on a live layer
layer = qgis.get_layer("parcels")   # actual QgsVectorLayer
layer.startEditing()
for feature in layer.getFeatures():
    layer.changeAttributeValue(feature.id(), field_idx, new_value)
layer.commitChanges()
# Changes are immediately visible in the QGIS canvas
```

HTTP can expose `insert_layer` (add a new layer) but cannot express arbitrary
mid-session edits to an existing layer without a large, carefully designed edit
transaction API. In-process, the full editing API is available directly.

---

#### Exclusively possible with HTTP

These features require the notebook to be decoupled from the QGIS process. In-process
embedding couples them permanently; HTTP does not.

**1. Notebook execution without QGIS desktop — headless server mode**

```bash
# HTTP: start a lightweight bridge server (QgsApplication, no GUI) separately
# The server script lives in plugin/bridge/ because it imports from qgis.core.
python plugin/bridge/serve.py --port 8765

# Notebooks connect to it and run analysis without QGIS desktop open
MARIMO_QGIS_PORT=8765 MARIMO_QGIS_TOKEN=<token> uv run marimo run report.py
```

A headless `QgsApplication([], False)` can run the HTTP bridge server without a
display, window manager, or QGIS desktop session. This enables scheduled report
generation in CI, server-side rendering, and Docker deployments.

Note: the standalone server script (`plugin/bridge/serve.py`) is part of the plugin
package — it imports `qgis.core` and requires QGIS to be installed. It cannot live
in `qgis_bridge/`, which must remain QGIS-free. The `qgis_bridge` pip package is the
client only.

In-process embedding requires the QGIS plugin context — `iface`, a Qt event loop, and
the full desktop application — to be running.

**2. Non-Python language clients**

```r
# HTTP: any language can call the bridge
library(httr2)
layers <- request("http://localhost:8765/api/layers") |> req_perform() |> resp_body_json()
```

```bash
# Or from shell
curl http://localhost:8765/api/render > map.png
```

The HTTP API is language-agnostic. R scripts, Julia notebooks, bash pipelines, or any
other tool can query QGIS data through it. In-process embedding is Python-only by
construction — the `QMetaObject.invokeMethod` mechanism requires a Python caller in the
same interpreter.

**3. True process crash isolation**

If a notebook cell allocates unbounded memory, triggers a GDAL segfault, or calls
`os.kill(os.getpid(), signal.SIGKILL)`, the marimo subprocess dies. The HTTP bridge
server in QGIS continues running. The user can close the broken notebook, restart a
new marimo process, and reconnect to the bridge with their QGIS project intact.

In-process, the kernel runs in the QGIS process. A C-level crash (segfault in a
GDAL driver, stack overflow in a recursive PyQGIS call) terminates the entire process.
This is not a theoretical risk — GDAL and GEOS occasionally segfault on malformed or
unusually large inputs.

**4. Multiple simultaneous notebook sessions**

```
HTTP bridge server
  ├── marimo process A (roads analysis notebook)   ← HTTP client
  ├── marimo process B (population dashboard)      ← HTTP client
  └── marimo process C (catchment model)           ← HTTP client
```

All three notebooks call the same bridge server concurrently. The server serialises
QGIS main-thread operations and responds to each independently. There is no shared
state between sessions; each gets its own layer exports and render outputs.

In-process embedding uses a module-level `_api` singleton and a `result` side-channel.
Running multiple concurrent marimo servers in-process against the same singleton
requires per-call locking — solvable but non-trivial — and all kernels share the same
Python environment, meaning a package installation in one notebook affects all others.

**5. Notebook portability — share, run, and version without the plugin**

A notebook that uses the HTTP client (`from qgis_bridge import QgisBridge`) fails
gracefully with a clear error when the bridge server is not running. The notebook file
itself is portable: check it into git, share it with a colleague, run it in CI against
a test bridge server. The fallback to headless mode (`HeadlessQGIS`) also works
because the HTTP client and the headless initialiser are separate code paths.

A notebook that relies on in-process embedding can only execute when loaded inside the
QGIS plugin's managed marimo thread. It cannot be run from the command line
independently, cannot be tested in CI without the full QGIS desktop environment, and
cannot be shared with a colleague who has QGIS but not the plugin — the import of
`qgis_bridge` succeeds but `QgisBridge()` raises immediately.

---

#### Summary of exclusive features

| Feature | HTTP only | In-process only |
|---|---|---|
| Live `QgsVectorLayer` / `QgsFeature` objects in cells | | Yes |
| Connect to QGIS signals from cell code | | Yes |
| Register new Processing algorithms in live session | | Yes |
| Full `iface` access (canvas, message bar, tools) | | Yes |
| Map canvas click events → notebook cell | | Yes |
| Start/commit layer edit sessions | | Yes |
| Headless server mode (no QGIS desktop) | Yes | |
| Non-Python language clients (R, Julia, bash) | Yes | |
| Process crash isolation | Yes | |
| Multiple concurrent notebook sessions (safe) | Yes | |
| Notebook portability (share / CI without plugin) | Yes | |

The in-process exclusives are all about **depth of integration** — going further
into the QGIS runtime than a bridge API exposes. The HTTP exclusives are all about
**breadth of deployment** — running in more contexts and with more clients than
a single embedded session allows.

These lists inform the "both modes" recommendation: developers building deep
QGIS integrations want in-process; analysts sharing portable reports and CI pipelines
want HTTP. Neither feature set is small enough to ignore.

---

## 4. Features Available Right Now

All features listed here are achievable with the existing QGIS 4 API and existing
marimo capabilities. Nothing requires new QGIS or marimo APIs.

The **HTTP bridge mode** (Phases 1–4) and **in-process mode** (Phase 5, opt-in) each
make a different set of features available. A third mode — **headless** — is the
existing marimo-qgis behaviour and remains fully functional as a fallback throughout.

### Core bridge (Phase 1 — HTTP)

| Feature | QGIS API | HTTP transfer |
|---|---|---|
| List project layers | `QgsProject.instance().mapLayers()` | JSON response |
| Get vector layer as GeoDataFrame | `native:savefeatures` → `.fgb` temp file | File path in JSON; client reads with GeoPandas |
| Get raster layer | `gdal:translate` → `.tif` temp file | File path in JSON; client reads with rioxarray |
| Project metadata | `QgsProject.instance()` | JSON response |
| Layer metadata | `QgsVectorLayer` / `QgsRasterLayer` | JSON response |

### Bidirectional data flow (Phase 2 — HTTP)

| Feature | QGIS API | HTTP transfer | Requires `iface`? |
|---|---|---|---|
| Push vector layer into QGIS | GeoDataFrame → `.fgb` → `addMapLayer` | Client POSTs file path | No |
| Push raster into QGIS | array → `.tif` → `addMapLayer` | Client POSTs file path | No |
| Get canvas extent | `iface.mapCanvas().extent()` | JSON bbox | **Yes** |
| Get selected features | `iface.activeLayer().selectedFeatures()` → `.fgb` | File path in JSON | **Yes** |
| Layer info | fields, CRS, extent, geometry type, band count | JSON response | No |

### Map rendering (Phase 3 — HTTP)

| Feature | QGIS API | HTTP transfer | Requires `iface`? |
|---|---|---|---|
| Render current canvas view | `QgsMapRendererParallelJob` from canvas settings | PNG bytes in response body | **Yes** |
| Render custom extent + layers | Same, explicit `QgsMapSettings` | PNG bytes in response body | No |

### Processing algorithms (Phase 3 — HTTP)

| Feature | QGIS API | HTTP transfer |
|---|---|---|
| List algorithms | `QgsApplication.processingRegistry()` | JSON array |
| Run algorithm by layer name | `processing.run(alg_id, {"INPUT": layer_name})` — bridge resolves name to layer | JSON result dict |
| Push algorithm output to QGIS | result path → `addMapLayer` | JSON layer id |
| Reactive algorithm | slider → `POST /api/run` → `POST /api/insert` | Two sequential HTTP calls |

### marimo UI (all phases, all modes)

marimo features that work regardless of bridge mode — no bridge code involved:

| Feature | marimo API |
|---|---|
| Interactive tables | `mo.ui.table(gdf)` |
| Layer selector dropdown | `mo.ui.dropdown(options=layer_names)` |
| Reactive sliders | `mo.ui.slider(50, 500)` |
| Stat cards | `mo.stat(value=f"{area:.2f} ha", label="...")` |
| Embedded map image | `mo.image(png_bytes)` |
| Collapsible log output | `mo.accordion({"Buffer log": mo.md(log)})` |
| Layout | `mo.hstack([...])`, `mo.vstack([...])` |
| HTML report export | `marimo export html notebook.py` |
| Code-free view mode | `marimo run notebook.py` |
| Reactive DAG | change any UI input → only dependent cells re-run |

### What is NOT available in HTTP mode (honest limits)

These are hard limits of the HTTP architecture, not implementation gaps.
They become available only in Phase 5 in-process mode:

| Feature | Why HTTP cannot provide it |
|---|---|
| Live `QgsVectorLayer` objects in cell scope | PyQGIS C++ objects cannot cross a process boundary |
| Connect to QGIS signals from cell code | Signals are synchronous in-process events; HTTP has no equivalent push |
| Register new Processing algorithms in live session | Requires the class to exist in the QGIS process memory |
| Full `iface` access from cells | `iface` is a GUI object in the QGIS process; not serialisable |
| Map canvas click → cell reaction | No push channel from QGIS to notebook at interactive speeds |
| Start/commit live layer edit sessions | No edit transaction API in HTTP bridge |

### What is NOT available in any mode yet

| Feature | Blocker | Planned |
|---|---|---|
| Streaming Processing algorithm progress | `QgsProcessingFeedback` is not async-compatible | Phase 6 |
| marimo panel embedded inside QGIS window | Requires `QWebEngineView` | Phase 6 |
| Project-change push to notebook | SSE (HTTP) or signal (in-process) not yet wired | Phase 6 |
| QGIS 3.x support | QGIS 4 API assumed throughout | Not planned |
| Windows / macOS tested | Linux only confirmed | Phase 4 |
| LSP / autocomplete for PyQGIS in editor | Separate tooling effort | Not planned |

---

## 5. Use Cases, Failure Conditions, and Mode Boundaries

This section answers: for a given user scenario, which mode works, which mode fails,
and exactly why it fails. These are not edge cases — each represents a realistic
situation that will arise in practice.

### Where QGISBridgeAPI lives and what that means

`QGISBridgeAPI` is a `QObject` subclass that lives inside the QGIS plugin process.
It is **never imported by notebook code**. It cannot be: it imports from `qgis.core`,
`qgis.analysis`, and `qgis.PyQt`, which require QGIS to be initialised and running.
The marimo notebook subprocess has no QGIS initialisation — it only has `qgis_bridge`,
the HTTP client package, which has no QGIS dependency.

The split is clean and intentional:

```
plugin process               notebook subprocess
──────────────────           ──────────────────────────
QGISBridgeAPI     ←HTTP→     qgis_bridge.QgisBridge
  (QGIS-aware)                 (no QGIS dependency)
  lives here                   lives here
```

If `QGISBridgeAPI` were moved into `qgis_bridge` (the client package), every notebook
venv would require QGIS to be installed — breaking portability, CI use, and the
headless fallback.

### The `iface` boundary

Within HTTP mode, `QGISBridgeAPI` is split by whether an operation needs `iface`
(the QGIS GUI interface object):

- **`iface`-independent**: `list_layers`, `get_layer`, `insert_layer`, `layer_info`,
  `list_algorithms`, `run_algorithm`, `project_state`. These only need
  `QgsProject.instance()` and `QgsApplication`. They work in any context where QGIS
  is initialised — plugin mode or standalone headless server.

- **`iface`-dependent**: `canvas_extent`, `selected_features`, `render_map` (canvas
  view). These require the QGIS desktop application to be running with an open canvas.
  They are unavailable in standalone headless server mode and will return a clear error
  if called there.

This boundary must be explicit in the bridge server code: if `iface is None`, these
endpoints return `{"error": "canvas operations require QGIS desktop (iface unavailable)"}`.

### Can a notebook run without the plugin installed?

**Yes.** The `qgis_bridge` package is installable via `pip`/`uv` with no QGIS
dependency. A notebook that imports it behaves as follows depending on context:

| Context | `MARIMO_QGIS_PORT` env var | `QgisBridge()` result |
|---|---|---|
| Plugin running, launched from dock | Present (injected by plugin) | Connects to HTTP bridge — full live access |
| Launched from terminal, plugin running | Absent | Raises `RuntimeError` — fall back to `HeadlessQGIS` |
| Launched from terminal, no plugin | Absent | Raises `RuntimeError` — fall back to `HeadlessQGIS` |
| Launched against standalone bridge server | Present (set manually) | Connects to HTTP bridge — `iface` ops unavailable |
| In CI, no QGIS at all | Absent | Raises `RuntimeError` — `HeadlessQGIS` also fails unless QGIS is installed |

The try/except fallback pattern in notebooks handles every case gracefully:

```python
try:
    from qgis_bridge import QgisBridge
    qgis = QgisBridge()           # raises if MARIMO_QGIS_PORT absent
except RuntimeError:
    from qgis_bridge import HeadlessQGIS
    qgis = HeadlessQGIS()         # raises if QGIS not installed in this env
```

---

### Scenario walkthroughs

Each scenario names the user, the action, the mode, the outcome, and — if it fails —
the exact failure point and how to detect or mitigate it.

---

#### Scenario 1: GIS analyst, desktop, plugin installed — standard use

**User:** GIS analyst. QGIS 4 open with a road-network project. Plugin installed and
loaded. Opens a notebook from the dock widget.

**Mode:** HTTP (plugin injects env vars into subprocess).

**Outcome:** Full Phase 1–4 feature set. Lists live layers, pulls roads as GeoDataFrame,
runs a buffer algorithm, pushes result back as a new layer visible in the Layers panel.
Renders the canvas to a `mo.image()` call.

**Nothing fails.**

---

#### Scenario 2: GIS analyst, desktop, plugin installed — tries to react to map clicks

**User:** Same analyst. Wants a notebook cell that updates whenever they click on the
QGIS map canvas — click a point, get nearby features in the notebook.

**Mode:** HTTP.

**What fails:** There is no mechanism for QGIS to push events to the notebook
subprocess. The analyst cannot install a `QgsMapTool` from the notebook (it's a
different process), and there is no push channel for canvas click events over HTTP.

**Failure point:** No error is raised immediately — the feature simply does not exist.
The analyst would need to use `qgis.get_selected_features()` as a manual substitute
(select features in QGIS, then pull them) rather than a reactive click listener.

**Resolution:** Phase 5 in-process mode (if adopted). Until then, document the
`get_selected_features()` workaround.

---

#### Scenario 3: GIS analyst, desktop, plugin NOT installed — runs notebook from terminal

**User:** A colleague receives a notebook via git. They have QGIS 4 installed but have
not installed the marimo-qgis plugin. They run `uv run marimo edit live_layers.py`.

**Mode:** HeadlessQGIS fallback (no env vars → `QgisBridge()` raises → `HeadlessQGIS`).

**Outcome:** The notebook works, but in headless mode. It sees no live project —
it loads layers from the disk paths hardcoded in the `HeadlessQGIS` section. The
`list_layers()` dropdown is empty or shows only the hardcoded data.

**What fails:** Any cell that depends on live project layers that aren't on the
colleague's disk. The `get_canvas_extent()` and `render_map()` calls also fail because
`HeadlessQGIS` has no canvas.

**Failure point:** `HeadlessQGIS.get_canvas_extent()` raises `NotImplementedError`.
Should be caught explicitly.

**Resolution:** The notebook must handle the fallback cleanly. The try/except pattern
covers connection failure; individual `iface`-dependent calls need their own guards.
Document this in the example notebooks.

---

#### Scenario 4: Developer runs notebook in CI against no QGIS at all

**User:** A developer wants to test a notebook in GitHub Actions. The CI runner has no
QGIS installed.

**Mode:** Neither HTTP nor HeadlessQGIS is available.

**What fails:** `QgisBridge()` raises (no env vars). `HeadlessQGIS()` raises
(`ModuleNotFoundError: No module named 'qgis'`). The notebook cannot execute any
QGIS-dependent cell.

**Failure point:** The `except RuntimeError` block catches `QgisBridge()` failure,
but `HeadlessQGIS()` raises `ModuleNotFoundError`, which is not caught. The notebook
crashes at startup.

**Resolution A:** Install QGIS in the CI runner and use HeadlessQGIS (slow, large
image, but correct). This is how the existing marimo-qgis CI would work.

**Resolution B:** Use a standalone HTTP bridge server in the CI container — start a
headless `QgsApplication` server as a service in the workflow, set `MARIMO_QGIS_PORT`
and `MARIMO_QGIS_TOKEN`, then run the notebook. All `iface`-independent operations
work; wrap `iface`-dependent calls in try/except.

**Resolution C:** Separate QGIS-dependent cells from pure analysis cells. Run CI only
on the pure analysis cells using mock data. Document which cells require the bridge.

---

#### Scenario 5: Analyst requests canvas extent from standalone bridge server

**User:** A data engineer sets up a headless bridge server in Docker for scheduled
report generation. A notebook calls `qgis.get_canvas_extent()`.

**Mode:** HTTP, standalone server (no `iface`).

**What fails:** `canvas_extent` requires `iface.mapCanvas()`. The standalone server
was started with `iface=None`. The bridge server returns:
`{"error": "canvas_extent requires QGIS desktop (iface is unavailable)"}`.
The `qgis_bridge` client raises `RuntimeError` with that message.

**Failure point:** `qgis.get_canvas_extent()` in the notebook raises `RuntimeError`.

**Resolution:** In headless server mode, use `render_map(extent=bbox)` with an
explicit extent instead of reading the canvas extent. Or, catch the error and substitute
a project-wide bounding box from `qgis.list_layers()` metadata.

**The `iface` boundary is the single most important thing to document in the bridge
server setup guide.** Users who build notebooks against the plugin and then deploy
them against a headless server will hit this boundary on exactly these three methods:
`canvas_extent`, `selected_features`, `render_map` (canvas view).

---

#### Scenario 6: Developer enables in-process mode — notebook cell hangs

**User:** An experienced developer enables the "in-process mode (experimental)"
checkbox in plugin settings. They write a cell with an unintentional infinite loop:

```python
@app.cell
def _(gdf):
    results = []
    for row in gdf.iterrows():   # mistakenly iterates indefinitely
        results.append(process(row))
    return (results,)
```

**Mode:** In-process.

**What fails:** The cell runs in the marimo asyncio thread inside the QGIS process.
marimo's "Stop" button sends SIGINT to the kernel — but the kernel is the QGIS process.
QGIS receives SIGINT and may freeze or terminate depending on signal handling.

**Failure point:** QGIS hangs. The user must force-kill QGIS from the OS. Any
unsaved project work is lost.

**HTTP comparison:** In HTTP mode, SIGINT goes to the marimo subprocess.
The subprocess is killed; the plugin's `MarimoProcessManager` detects the process
death and marks the session as stopped. QGIS is unaffected and the project is intact.

**Resolution:** In-process mode should display a persistent warning in the dock widget:
*"In-process mode: a crashing notebook cell can crash QGIS. Save your project
frequently."* The plugin should also set a short autosave interval
(`QgsProject.instance().setAutoSaveInterval(60)`) when in-process mode is active.

---

#### Scenario 7: In-process cell triggers a GDAL segfault

**User:** Developer in in-process mode. A cell loads a corrupt GeoPackage that
triggers a C-level crash in GDAL's geometry parser.

**Mode:** In-process.

**What fails:** GDAL raises a C-level signal (SIGSEGV) inside the QGIS process.
Python's signal handler cannot catch SIGSEGV. The QGIS process terminates immediately.
All unsaved project work is lost. No error message is shown — the window simply
disappears.

**HTTP comparison:** The same corrupt GeoPackage, loaded by the marimo subprocess,
kills that subprocess. The HTTP bridge server catches the connection drop, marks the
session as failed, and QGIS remains running.

**Note:** This is not a contrived failure. GDAL and GEOS occasionally segfault on
malformed geometries, invalid coordinate values, or certain projection operations. Any
spatial analysis tool that processes user-provided data will encounter this eventually.

**Resolution:** This cannot be fully mitigated in in-process mode — C-level crashes
bypass Python's exception system. The only mitigation is clear user communication:
in-process mode is for experienced developers who understand the risk. HTTP mode is
the safe default for anyone working with untrusted or externally-sourced data.

---

#### Scenario 8: Developer wants to register a Processing algorithm from a notebook

**User:** A developer has written a custom `QgsProcessingAlgorithm` subclass and wants
to register it in the live QGIS session from a notebook cell, so it appears in the
Processing Toolbox and can be called from other workflows.

**Mode:** HTTP.

**What fails:** The algorithm class is defined in the marimo subprocess's Python
environment. Sending it to the QGIS process would require serialising a Python class
definition (not a data object) across the process boundary — Python's `pickle` cannot
serialise live class definitions in general, and there is no HTTP endpoint that accepts
arbitrary class definitions.

**Failure point:** There is no `POST /api/register-algorithm` endpoint and no way to
implement one that handles arbitrary Python classes. The developer would need to package
the algorithm as a QGIS plugin instead.

**HTTP comparison:** FAILS in HTTP mode.
**In-process comparison:** Works — the class is defined in the QGIS process memory
and can be passed directly to `QgsApplication.processingRegistry().addAlgorithm()`.

**Resolution for HTTP users:** Package the algorithm as a standalone QGIS Processing
script (the existing `processing/` pattern) or as a plugin. Register it outside the
notebook, then call it from the notebook via `qgis.run_algorithm()`.

---

#### Scenario 9: Analyst installs a Python package from inside an in-process cell

**User:** Developer in in-process mode. Wants to use a library not yet in the venv
and runs:

```python
@app.cell
def _():
    import subprocess
    subprocess.run(["pip", "install", "shapely==1.8"])   # old version
    import shapely
    return (shapely,)
```

**Mode:** In-process.

**What fails:** `pip install` installs into the QGIS Python environment — the same
environment QGIS itself uses. `shapely==1.8` conflicts with the version QGIS's
`qgis.core` depends on. QGIS may immediately crash on the next spatial operation, or
produce silent incorrect results. Other open notebooks sharing the environment are
affected immediately.

**HTTP comparison:** In HTTP mode, the marimo subprocess has its own isolated venv.
`pip install shapely==1.8` only affects that one subprocess's environment. QGIS is
unaffected. The next time the notebook is launched from a fresh venv, the conflict
is gone.

**Resolution:** In-process mode should document that package installation from cells
is prohibited. The plugin settings page should include a note that the in-process
kernel shares the QGIS Python environment.

---

#### Scenario 10: Two analysts open notebooks simultaneously (HTTP mode)

**User:** Two GIS analysts share a QGIS project on a desktop workstation. Both open
different notebooks from the dock widget at the same time.

**Mode:** HTTP, two simultaneous marimo subprocesses.

**Outcome:** Both notebooks connect to the same bridge server using the same port and
token. The bridge server handles requests concurrently: the HTTP server dispatches each
request to `QGISBridgeAPI` via `QMetaObject.invokeMethod`, which serialises access to
the Qt main thread. Each request completes before the next starts on the QGIS side;
both clients receive correct responses.

**Nothing fails.** Both analysts see the same layer list (they share a project). If
one pushes a new layer, it appears in both notebooks' next `list_layers()` call.

**In-process comparison:** Two simultaneous notebooks in in-process mode share the
`_api.result` side-channel. Without per-call locking, a race condition silently returns
the wrong GeoDataFrame to one caller. This is why Phase 5 requires fixing the race
condition before shipping.

---

#### Scenario 11: Analyst fetches a very large layer (5 million features)

**User:** An analyst calls `qgis.get_layer("national_roads")` on a layer with 5
million features.

**Mode:** HTTP.

**Outcome:** `native:savefeatures` writes all 5M features to a FlatGeobuf temp file.
Depending on geometry complexity, this takes 20–120 seconds and produces a file of
several gigabytes. GeoPandas then reads the entire file. The operation eventually
succeeds but is slow and consumes significant disk space.

**What fails:** Nothing fails hard, but the notebook appears frozen during the write.
marimo's UI shows the cell as running. If the operation takes more than ~30 seconds,
the analyst may assume it has hung.

**Resolution:** The bridge should support a `limit` parameter:
`GET /api/layer/{id}?limit=10000` — `QgsFeatureRequest().setLimit(10000)` on the QGIS
side, returns only the first N features. Document `get_layer(name, limit=None)` in
`QgisBridge` and recommend always using a limit during exploration. For the full
dataset, add `get_layer_sample()` as a convenience alias with `limit=1000`.

---

#### Scenario 12: Notebook shared via git — hardcoded port and token

**User:** A developer hardcodes the bridge port and token into a notebook instead of
reading from env vars:

```python
qgis = QgisBridge(port=2718, token="my-secret-token")
```

Then commits the notebook to git and shares it.

**What fails:** The hardcoded port may not match the dynamically-allocated port on
another machine. The hardcoded token is now in the git history and provides no
security. Any future change to the bridge server startup will silently break the
notebook.

**Resolution:** `QgisBridge()` should only ever read from environment variables and
refuse to accept hardcoded connection details. The constructor should raise if called
with explicit port/token arguments (or simply not accept them). The env-var pattern
is the only correct interface; document this prominently.

---

### Summary failure matrix

| Scenario | HTTP mode | In-process mode | HeadlessQGIS |
|---|---|---|---|
| Live layer list from desktop project | Works | Works | Fails — no live project |
| Canvas extent from plugin session | Works | Works | Fails — no canvas |
| Canvas extent from standalone server | **Fails** — no iface | N/A | Fails — no canvas |
| Render map from standalone server | **Fails** — no iface | N/A | Fails — no canvas |
| Selected features from notebook | Works (via iface) | Works (via iface) | **Fails** — no selection |
| React to map canvas click | **Fails** — no push channel | Works (Phase 5) | Fails |
| Register algorithm in live session | **Fails** — cross-process class | Works (Phase 5) | Fails |
| Notebook cell infinite loop | Subprocess killed; QGIS survives | **QGIS may hang** | Subprocess killed |
| GDAL segfault in cell | Subprocess crashes; QGIS survives | **QGIS crashes** | Subprocess crashes |
| Install package from cell | Only affects notebook venv | **Affects QGIS env** | Affects headless env |
| Multiple concurrent notebooks | Works (safe) | Race condition risk | N/A (one process per notebook) |
| Run notebook in CI without QGIS | Fails — no QGIS to connect to | N/A | Fails — no QGIS installed |
| Run notebook in CI with QGIS | Works (headless server) | N/A | Works |
| Share notebook via git | Works — portable | **Fails on recipient machine** | Works |
| Fetch 5M-feature layer | Slow but works | Fast | Slow but works |
| Push analysis result to QGIS | Works | Works | **Fails** — no live project |

---

## 6. Architecture Reference (Phases 1–4: HTTP)

### The two-process model

In the HTTP architecture there are always two separate OS processes:

```
┌─────────────────────────────────────────────────────────┐
│  QGIS process  (the plugin lives here)                  │
│                                                         │
│  MarimoPlugin                                           │
│    ├── QGISBridgeServer  (aiohttp, 127.0.0.1:<port>)   │
│    │     └── QGISBridgeAPI  (QObject, Qt main thread)  │
│    │           Handles all QGIS API calls.              │
│    │           Has full access to QgsProject,           │
│    │           iface, QgsApplication, processing.       │
│    ├── MarimoProcessManager                             │
│    │     Launches marimo subprocesses.                  │
│    │     Injects MARIMO_QGIS_PORT + TOKEN into env.    │
│    └── MarimoManagerDock  (Qt dock widget)              │
│                                                         │
└─────────────────────────────────────────────────────────┘
         ▲  HTTP (127.0.0.1, JSON + temp files)
         │
┌─────────────────────────────────────────────────────────┐
│  marimo process  (subprocess, no QGIS dependency)       │
│                                                         │
│  marimo server + kernel                                 │
│    └── notebook cell code                               │
│          from qgis_bridge import QgisBridge             │
│          qgis = QgisBridge()   # HTTP client only       │
│          gdf = qgis.get_layer("roads")                  │
│            → GET http://127.0.0.1:<port>/api/layer/roads│
│            ← {"path": "/tmp/abc.fgb"}                  │
│            → geopandas.read_file("/tmp/abc.fgb")        │
│                                                         │
└─────────────────────────────────────────────────────────┘
         browser  ◄──  WebSocket  ──►  marimo server
```

The bridge server and `QGISBridgeAPI` live entirely inside the QGIS plugin process.
The notebook process contains only `qgis_bridge`, which is a pure HTTP client with
no QGIS dependency of its own.

### Where QGISBridgeAPI lives — and why it must stay in the plugin

`QGISBridgeAPI` is a `QObject` subclass that:

- calls `QgsProject.instance()` to read layer state
- calls `iface.mapCanvas()` to get canvas extent and render maps
- calls `QgsApplication.processingRegistry()` to list and run algorithms
- uses `processing.run()` which requires the Processing framework to be initialised

All of these require QGIS to be running and initialised. They are not importable in
the marimo notebook process because that process has no QGIS. `QGISBridgeAPI` is
therefore plugin code and lives in `plugin/bridge/api.py`. The notebook never imports
it — notebooks only import `qgis_bridge` (the HTTP client).

The HTTP server (`QgisBridgeServer`) wraps `QGISBridgeAPI`: it receives HTTP requests
in an aiohttp handler, dispatches them to `QGISBridgeAPI` on the Qt main thread via
`QMetaObject.invokeMethod(Qt.BlockingQueuedConnection)` (the same mechanism rqgis
uses), and returns the result as a JSON response.

### Can the notebook run without the plugin?

Yes, in two ways:

**1. Headless fallback** — when `MARIMO_QGIS_PORT` is absent from the environment,
`QgisBridge()` raises `RuntimeError` and the notebook can catch it and fall back to
`HeadlessQGIS`, which initialises its own `QgsApplication` from disk files. This is
the existing marimo-qgis behaviour, unchanged. The notebook is portable: it runs from
the terminal with `uv run marimo edit notebook.py` without the plugin installed at all.

```python
@app.cell
def _():
    try:
        from qgis_bridge import QgisBridge
        qgis = QgisBridge()        # live mode: env vars present → HTTP bridge
    except RuntimeError:
        from qgis_bridge import HeadlessQGIS
        qgis = HeadlessQGIS()      # fallback: no plugin → own QgsApplication
    return (qgis,)
```

**2. Standalone bridge server** (Phase 4+) — `QGISBridgeServer` and `QGISBridgeAPI`
can be run as a standalone script with a headless `QgsApplication([], False)`,
without QGIS desktop at all. Because this script imports `qgis.core`, it lives in
the plugin package, not in `qgis_bridge` (the QGIS-free client):

```bash
python plugin/bridge/serve.py --port 8765   # no QGIS desktop, but QGIS must be installed
MARIMO_QGIS_PORT=8765 MARIMO_QGIS_TOKEN=... uv run marimo run report.py
```

This enables CI pipelines and Docker deployments. When running standalone, operations
that require `iface` (canvas extent, selected features, map render) are unavailable
and return a clear error; all other operations (`list_layers`, `get_layer`,
`insert_layer`, `run_algorithm`) work because they only require `QgsProject` and
`QgsApplication`.

### What the notebook package (`qgis_bridge`) contains

`qgis_bridge` is a small, pip-installable Python package with **no QGIS dependency**.
Its only runtime requirements are `requests` (or `httpx`) and `geopandas`. It can be
installed into any virtual environment — including one that has never seen QGIS.

```
qgis_bridge/
├── __init__.py       QgisBridge (HTTP client), HeadlessQGIS
├── _client.py        HTTP request helpers (auth header, error handling)
└── _headless.py      HeadlessQGIS — wraps existing marimo-qgis init pattern
```

`QgisBridge` reads `MARIMO_QGIS_PORT` and `MARIMO_QGIS_TOKEN` from the environment.
These are injected by `MarimoProcessManager` when the plugin launches the notebook
subprocess. When they are absent (notebook run from CLI without the plugin),
`QgisBridge()` raises immediately so the `try/except` pattern above catches it cleanly.

### Plugin file structure (Phases 1–4)

```
marimo-qgis/
├── plugin/
│   ├── __init__.py            classFactory() entry point
│   ├── metadata.txt           qgisMinimumVersion=4.0
│   ├── plugin.py              MarimoPlugin — starts bridge server, manages lifecycle
│   ├── provider.py            MarimoProvider — Processing Toolbox group (existing)
│   ├── algorithm.py           LaunchMarimoAlgorithm (existing, improved)
│   ├── bridge/
│   │   ├── api.py             QGISBridgeAPI (QObject) — all QGIS calls happen here
│   │   ├── server.py          QgisBridgeServer — aiohttp HTTP server in a thread
│   │   ├── auth.py            UUID token generation and per-request validation
│   │   └── convert.py         layer_to_fgb(), raster_to_tif(), temp file tracking
│   └── ui/
│       ├── dock.py            MarimoManagerDock — notebook list, launch/stop buttons
│       └── process.py         MarimoProcessManager — subprocess.Popen, env injection
├── qgis_bridge/               pip-installable client package (no QGIS dependency)
│   ├── __init__.py            QgisBridge, HeadlessQGIS
│   ├── _client.py             HTTP helpers
│   └── _headless.py           headless QgsApplication init
├── example/
│   ├── live_layers.py         NEW: live layer list + GeoDataFrame (bridge mode)
│   ├── push_result.py         NEW: push analysis result back to QGIS (bridge mode)
│   ├── render_map.py          NEW: render live map into notebook cell (bridge mode)
│   ├── reactive_processing.py NEW: slider → Processing algorithm → insert layer
│   ├── processing_demo.py     EXISTING — headless mode, unchanged
│   ├── gpkg_summary.py        EXISTING — headless mode, unchanged
│   └── simple_marimo_qgis.py  EXISTING — headless mode, unchanged
└── pyproject.toml
```

### QGISBridgeAPI dispatch table

Ported from rqgis `QGISApi.dispatch()`, adapted for QGIS 4. All methods run on the
Qt main thread inside the plugin process. HTTP handler calls each via
`QMetaObject.invokeMethod(Qt.BlockingQueuedConnection)`.

| Method | HTTP endpoint | Returns | QGIS 4 call | Needs `iface`? |
|---|---|---|---|---|
| `project_state` | `GET /api/project` | dict | `QgsProject.instance()` | No |
| `list_layers` | `GET /api/layers` | list of dicts | `QgsProject.instance().mapLayers()` | No |
| `get_layer` | `GET /api/layer/{name}` | temp file path | `native:savefeatures` → `.fgb`; `{name}` is the layer name (case-insensitive); first match wins if duplicate names exist | No |
| `insert_layer` | `POST /api/insert` | layer id (QGIS UUID) | `QgsProject.instance().addMapLayer()` | No |
| `get_layer_info` | `GET /api/layer-info/{name}` | dict | fields, CRS, extent, geometry; same name resolution as `get_layer` | No |
| `canvas_extent` | `GET /api/extent` | dict | `iface.mapCanvas().extent()` | **Yes** |
| `selected_features` | `GET /api/selected` | temp file path | `layer.selectedFeatures()` | **Yes** |
| `render_map` | `GET /api/render` | PNG bytes | `QgsMapRendererParallelJob` | **Yes** |
| `list_algorithms` | `GET /api/algorithms` | list of dicts | `QgsApplication.processingRegistry()` | No |
| `run_algorithm` | `POST /api/run` | dict | `processing.run(alg_id, params)` — see note | No |

The `iface` column matters for the standalone server mode (Phase 4+): methods that
require `iface` are only available when the plugin is running inside QGIS desktop.

**`run_algorithm` note — `TEMPORARY_OUTPUT` and the HTTP boundary:** When a Processing
algorithm is called with `"OUTPUT": "TEMPORARY_OUTPUT"`, QGIS returns a live
`QgsVectorLayer` object in the result dict. This object lives in the QGIS process and
cannot be serialised across HTTP. `QGISBridgeAPI.run_algorithm` must detect any output
value that is a `QgsVectorLayer` or `QgsRasterLayer` and replace it with a temp file
path (using `layer_to_fgb()` or `raster_to_tif()`) before building the JSON response.
Output values that are scalars (area in m², feature count, bounding box) are returned
directly. The client-side `QgisBridge.run_algorithm()` transparently reads any temp
file path into a GeoDataFrame before returning the result dict to the caller.

### MarimoProcessManager (Phases 1–4)

The plugin launches marimo notebooks as subprocesses. It does not embed marimo
in-process. The existing `algorithm.py` `subprocess.Popen` pattern is extended to
inject the bridge connection details:

```python
class MarimoProcessManager:
    def launch(self, notebook_path, mode="edit"):
        env = os.environ.copy()
        env["MARIMO_QGIS_PORT"]  = str(self._server.port)
        env["MARIMO_QGIS_TOKEN"] = self._server.token
        env.pop("QT_QPA_PLATFORM", None)   # don't force offscreen in subprocess

        self._proc = subprocess.Popen(
            ["uv", "run", "marimo", mode, notebook_path],
            env=env,
            cwd=os.path.dirname(notebook_path),
            start_new_session=True,   # subprocess crash can't kill QGIS
        )
```

`start_new_session=True` is the mechanism that enforces process isolation: the
subprocess gets its own process group, so a signal or crash in the notebook cannot
propagate to the QGIS parent process.

### Phase 5 addition: MarimoServerThread (in-process, opt-in)

When in-process mode is enabled via plugin settings, `MarimoProcessManager` is
replaced by `MarimoServerThread`, which embeds the marimo server inside the QGIS
process using `marimo.create_asgi_app()`. `QGISBridgeAPI` (the Qt-thread QObject with
all QGIS calls) is reused unchanged — it is the shared core of both modes. What
changes: `QgisBridgeServer` (the aiohttp HTTP layer) is **not used** in in-process
mode. Instead, `qgis_bridge.QgisBridge` calls `QGISBridgeAPI` directly via
`QMetaObject.invokeMethod`. The HTTP transport is bypassed entirely; the dispatch table
and data conversion routines in `QGISBridgeAPI` are identical.

---

## 7. Phased Roadmap

### What the HTTP bridge gives users that they don't have today

The current marimo-qgis tool is a launcher. It opens a notebook in the browser and
gets out of the way. Every notebook must initialise its own throwaway `QgsApplication`,
load layers from hardcoded file paths, and work in complete isolation from whatever the
user has open in QGIS. When the analysis is done, results live in the notebook — they
cannot be pushed back into the project.

The HTTP bridge changes this relationship fundamentally. Once Phase 1–4 is complete,
a user's workflow becomes:

**Before (today)**
> Open QGIS. Load a road network and catchment polygons. Open a terminal. Write a
> notebook that re-loads those same files from disk using hardcoded paths. Run the
> analysis. Screenshot the result. Manually add an output layer back into QGIS using
> "Add Vector Layer…".

**After (HTTP bridge)**
> Open QGIS. Load your data as you normally would. Click "Open notebook" in the
> marimo dock. The notebook already sees every layer in your project — no paths, no
> boilerplate. Pull any layer into a GeoDataFrame in one line. Run analysis with
> reactive sliders. Click a button to push the result back as a new layer that appears
> immediately in the Layers panel and map canvas.

Concretely, the bridge delivers capabilities that do not exist at all in the current
tool:

| Capability | Today | After HTTP bridge |
|---|---|---|
| See what layers are open in QGIS | No — loads from disk only | Yes — live layer inventory |
| Pull a live project layer into a notebook | No — re-load from file | Yes — one call, returns GeoDataFrame |
| React to QGIS selections | No | Yes — `get_selected_features()` |
| Render the live map inside a notebook cell | No | Yes — PNG via `render_map()` |
| Push an analysis result back into QGIS | No | Yes — `insert_layer()` adds to Layers panel |
| Run a Processing algorithm against a live layer | No | Yes — `run_algorithm()` by name |
| Drive a Processing algorithm with a UI slider | Partial (headless only) | Yes — reactive, against live data |
| Share a notebook that works for a colleague | Yes (headless) | Yes — fallback to headless if no plugin |
| Generate a report from a headless server or CI | Yes | Yes — standalone bridge server |

The notebook stops being a scratchpad that lives beside QGIS and becomes a
first-class analytical environment that is part of the same session.

---

### Implementation strategy

The roadmap proceeds in two tracks separated by a deliberate decision gate:

**Track A (Phases 1–4): HTTP bridge** — build a complete, production-quality product
using the HTTP server approach. This is the default path. It delivers the full feature
set available to HTTP (see §3), is safe for general-audience GIS analysts, is
portable, and is testable in CI without a running QGIS desktop.

**Track B (Phase 5, optional): In-process mode** — add `QMetaObject.invokeMethod`
based in-process embedding as an opt-in "developer mode" on top of the completed HTTP
implementation. This unlocks the six in-process-exclusive features (live PyQGIS
objects, signals, `iface`, canvas tools, edit sessions, algorithm registration) for
users who explicitly need them and accept the crash-isolation trade-off.

The two tracks share the `QGISBridgeAPI` QObject entirely. The only difference between
modes is whether `qgis_bridge` speaks HTTP to a subprocess or calls `invokeMethod`
to the same-process QObject. The `QGISBridgeAPI` dispatch table, the QGIS API calls
it makes, and the data conversion routines are identical in both modes.

```
Phase 1  ──► Phase 2  ──► Phase 3  ──► Phase 4  ══► SHIP (HTTP complete)
                                                         │
                                               (if in-process needed)
                                                         │
                                                      Phase 5
                                               (in-process opt-in mode)
```

The gate between Track A and Track B is an explicit product decision based on:
- Whether users are actually hitting the HTTP-exclusive limitations (no live PyQGIS
  objects, no signal connections, no `iface`)
- Whether the marimo embedding API (`create_asgi_app`) is stable enough to depend on
- Whether the crash-isolation trade-off is acceptable for the intended audience

If the gate is never crossed, the HTTP product is complete and correct on its own.

---

### Phase 1 — HTTP bridge foundation

**Goal:** Plugin starts an HTTP bridge server; notebooks have live read access to the
running QGIS project. A user can open a notebook in their browser, see the layers in
their QGIS project, and pull one into a GeoDataFrame — without initialising a
separate `QgsApplication` or writing any boilerplate.

**Plugin side**

- [ ] `plugin/bridge/server.py` — `QgisBridgeServer`: aiohttp app on
  `127.0.0.1:<random port>`, session token auth, request queue that dispatches to Qt
  main thread via `QMetaObject.invokeMethod`
- [ ] `plugin/bridge/api.py` — `QGISBridgeAPI` (QObject, Qt main thread):
  `project_state`, `list_layers`, `get_layer` (vector → FlatGeobuf temp file)
- [ ] `plugin/bridge/convert.py` — `layer_to_fgb(layer, path)`: uses
  `native:savefeatures`; temp file tracking and cleanup on plugin unload (port from
  rqgis `core/utils.py`)
- [ ] `plugin/bridge/auth.py` — generate UUID session token at server start; validate
  on every request via `Authorization: Bearer <token>` header
- [ ] `plugin/ui/process.py` — `MarimoProcessManager`: `subprocess.Popen` for
  `uv run marimo edit <notebook>`, inject `MARIMO_QGIS_PORT` and
  `MARIMO_QGIS_TOKEN` into subprocess env
- [ ] `plugin/plugin.py` — start `QgisBridgeServer` on plugin load; stop + clean up
  temp files on plugin unload; wire plugin state machine
  (`UNINITIALIZED → READY` on server bind)

**Client side**

- [ ] `qgis_bridge/__init__.py` — `QgisBridge()` (no arguments): reads
  `MARIMO_QGIS_PORT` / `MARIMO_QGIS_TOKEN` from env only; raises `RuntimeError` if
  either is absent; `list_layers()` → GET `/api/layers`; `get_layer(name)` → GET
  `/api/layer/{name}` → reads `.fgb` → returns GeoDataFrame
- [ ] `qgis_bridge/__init__.py` — `HeadlessQGIS`: wraps existing marimo-qgis
  headless pattern; `QgisBridge()` falls back to this when env vars absent

**Examples and docs**

- [ ] `example/live_layers.py` — live layer list dropdown + GeoDataFrame table
- [ ] Update `CLAUDE.md`, `README.md`, `MARIMO_QGIS.md`

**What works after Phase 1**

- Live layer inventory from the running QGIS project
- Pull any vector layer as a GeoDataFrame into notebook cells
- Headless fallback for notebooks run without the plugin
- marimo launched from the terminal; browser opens automatically

---

### Phase 2 — Bidirectional data flow + dock widget

**Goal:** Push analysis results back into QGIS as new layers; expose canvas extent
and selected features; add a dock widget to manage notebooks from within QGIS.

**Bridge extensions**

- [ ] `QGISBridgeAPI`: `insert_layer` (reads a temp file, calls `addMapLayer`),
  `canvas_extent`, `selected_features` (selected features → temp FlatGeobuf),
  `get_layer_info`
- [ ] `QgisBridgeServer`: `POST /api/insert`, `GET /api/extent`,
  `GET /api/selected`, `GET /api/layer-info/{id}`
- [ ] `qgis_bridge`: `insert_layer(gdf, name)`, `get_canvas_extent()`,
  `get_selected_features()`, `layer_info(name)`
- [ ] Raster `get_layer`: `gdal:translate` → temp `.tif` → returned path;
  client reads with rioxarray (port from rqgis `get_layer` raster branch)

**Dock widget**

- [ ] `plugin/ui/dock.py` — `MarimoManagerDock`: list of open notebooks (path,
  port, PID, status); Launch / Stop buttons; working directory display; settings
  shortcut. Structural pattern ported from rqgis `ui/dock.py`, simplified (no
  console or editor panel — marimo provides those in the browser).

**Examples**

- [ ] `example/push_result.py` — filter a layer, push result back as new layer
- [ ] `example/selection_analysis.py` — analyse selected features from active layer

**What works after Phase 2**

Full bidirectional data flow: notebook ↔ live QGIS project. The dock widget makes
the integration visible inside QGIS rather than requiring terminal awareness.

---

### Phase 3 — Map rendering + Processing bridge

**Goal:** Render the live QGIS map inside notebook cells; expose the Processing
algorithm registry; run algorithms reactively from notebook UI controls.

**Bridge extensions**

- [ ] `QGISBridgeAPI`: `render_map(width, height, extent=None)` →
  `QgsMapRendererParallelJob` → PNG bytes returned directly in HTTP response body
  (no temp file — PNG is already bytes)
- [ ] `QGISBridgeAPI`: `list_algorithms()` → algorithm id, name, group;
  `run_algorithm(alg_id, params)` → result dict with output paths/values
- [ ] `QgisBridgeServer`: `GET /api/render`, `GET /api/algorithms`,
  `POST /api/run`
- [ ] `qgis_bridge`: `render_map(width, height)` → PNG bytes → caller passes to
  `mo.image(...)`; `list_algorithms()` → DataFrame; `run_algorithm(id, params)`

**Examples**

- [ ] `example/render_map.py` — layer visibility checkboxes + re-render on change
- [ ] `example/reactive_processing.py` — slider → `run_algorithm("native:buffer")`
  → `insert_layer` → updates in QGIS canvas

**What works after Phase 3**

The full HTTP-mode feature set is implemented. All capabilities from §4 "Features
Available Right Now" are live. Phase 4 is deployment; Phase 5 is optional depth.

---

### Phase 4 — Cross-platform + distribution

**Goal:** Confirmed working on Windows and macOS; available in the QGIS Plugin
Repository; `qgis_bridge` on PyPI.

- [ ] Windows testing: QGIS OSGeo4W bundled Python; `uv` on PATH; aiohttp in the
  plugin's bundled dependencies; document in `TROUBLESHOOTING.md`
- [ ] macOS testing: `QGIS.app` bundled Python; same pattern
- [ ] CI: GitHub Actions — `ruff` lint, `uvx marimo check` on all example notebooks,
  smoke test of bridge server start/stop
- [ ] `metadata.txt` finalised; `make package` builds installable ZIP
- [ ] QGIS Plugin Repository submission
- [ ] `qgis_bridge` published to PyPI (`uv pip install qgis-bridge` in notebook venv)
- [ ] `TROUBLESHOOTING.md` updated with bridge-specific failure modes (port in use,
  token mismatch, aiohttp not found, QGIS version <4)

**Decision gate after Phase 4**

At this point the HTTP product is complete. Evaluate whether to continue to Phase 5
based on:

1. Are users hitting HTTP-exclusive limitations? (requests for live PyQGIS objects,
   signal connections, `iface` access, canvas tool integration, or edit sessions)
2. Is `marimo.create_asgi_app()` stable and documented enough to depend on across
   marimo minor versions?
3. Is the intended user base (GIS analysts vs Python developers) willing to accept
   the crash-isolation trade-off of in-process mode?

If the answer to any of these is no, stop here. The HTTP product is complete.

---

### Phase 5 — In-process mode (optional, developer-facing)

**Goal:** Add in-process embedding as an opt-in mode that unlocks the six
in-process-exclusive features for users who need them. HTTP mode continues to work
unchanged; this is purely additive.

**What changes**

- [ ] `plugin/ui/server.py` — `MarimoServerThread`: runs `marimo.create_asgi_app()`
  in a daemon asyncio thread inside the QGIS process; registers the notebook path
  and serves it at `localhost:2718`
- [ ] `plugin/bridge/api.py` — `QGISBridgeAPI` already exists and is unchanged.
  In-process mode calls it directly via `QMetaObject.invokeMethod` instead of HTTP.
- [ ] `qgis_bridge/__init__.py` — `QgisBridge` gets a `mode` argument:
  `QgisBridge(mode="http")` (default) or `QgisBridge(mode="inprocess")`. In-process
  mode reads a module-level reference to `QGISBridgeAPI` registered by the plugin at
  startup, not env vars.
- [ ] Per-call locking on `QGISBridgeAPI.result` to eliminate the concurrency race
  condition (required before in-process mode is safe)
- [ ] Plugin settings: checkbox "Enable in-process mode (experimental)" — when
  enabled, `MarimoServerThread` starts instead of `MarimoProcessManager`
- [ ] Documentation: clear warning that in-process mode means a crashing notebook
  cell can crash QGIS; recommended for developers only

**In-process-exclusive features unlocked in Phase 5**

Once Phase 5 is complete, notebook cells running in in-process mode can:

- Import and use any `qgis.core` / `qgis.gui` type directly
- Connect to QGIS signals (`QgsProject.layerWasAdded`, etc.)
- Access `iface` (passed into `qgis_bridge` by the plugin at startup)
- Install map canvas tools (`QgsMapToolEmitPoint`) that feed events into marimo state
- Register new `QgsProcessingAlgorithm` subclasses into the live registry
- Open, edit, and commit changes to live layers

**What does not change in Phase 5**

- HTTP mode is unaffected. Users who do not enable the setting continue on HTTP.
- `QGISBridgeAPI` dispatch table is unchanged — same QGIS API calls, same data
  conversion routines. The only difference is the transport layer.
- All existing example notebooks continue to work in HTTP mode.
- New in-process example notebooks are added alongside existing ones, clearly labelled.

---

### Phase 6 — Advanced (both modes)

These features are useful regardless of which mode is active:

- [ ] Project-change notifications: when QGIS layers are added/removed or the project
  is loaded, invalidate the layer cache in connected notebooks. HTTP mode: SSE push
  from bridge server. In-process mode: direct signal connection.
- [ ] `mo.ui.dropdown` pre-populated from live layer list, auto-refreshes on project
  change
- [ ] Layer style round-trip: read QGIS renderer symbology and apply it to Folium /
  Altair visualisations of the same layer data
- [ ] Notebook templates wizard in the dock widget (new notebook pre-filled with
  bridge boilerplate)
- [ ] marimo browser panel embedded in QGIS via `QWebEngineView` (show the notebook
  UI inside QGIS without a separate browser window)

---

## 8. Notebook Materialization: Portable Headless Export

### The problem it solves

When a user develops a notebook interactively against the bridge, the notebook contains
calls like `qgis.get_layer("roads")` and `qgis.get_canvas_extent()`. These work
perfectly in a live session — the bridge resolves layer names against the current
project and returns live data. But they silently fail when the same notebook is run
headlessly (no plugin, no bridge), because `HeadlessQGIS` has no idea which file
"roads" came from, what extent the canvas was at, or where the project data lives.

Today, users have to manually figure out file paths and hardcode them into the headless
section of the notebook. Materialization automates this: after an interactive session,
the notebook can be exported in a form that is self-contained enough to run headlessly
without any manual editing.

The resulting notebook is fully portable — a colleague with QGIS but no plugin can run
it from the terminal exactly as marimo-qgis works today.

### The roundtrip

```
Interactive development (bridge)          Headless execution (materialized)
────────────────────────────────          ──────────────────────────────────
qgis = QgisBridge()                       qgis = HeadlessQGIS()
                                            # loads from materialized paths,
gdf = qgis.get_layer("roads")             # no bridge, no plugin required
  → bridge resolves "roads" to
    /project/data/roads.gpkg              gdf = qgis.get_layer("roads")
  → exports to .fgb temp file               → reads /project/data/roads.gpkg
  → returns GeoDataFrame                    → returns GeoDataFrame (identical)
```

The try/except fallback pattern already provides the structure; materialization
populates the `HeadlessQGIS` side with everything it needs:

```python
try:
    qgis = QgisBridge()         # live: bridge resolves names from running project
except RuntimeError:
    qgis = HeadlessQGIS()       # headless: reads from materialized layer registry
```

### What gets materialized

#### File-backed vector layers → GeoPackage

File-backed vector layers (GeoPackage, Shapefile, PostGIS export, WFS snapshot) are
the common case and materialize cleanly. The bridge's `layer_info()` endpoint returns
the layer's source URI (`QgsVectorLayer.source()`). For layers that already live in a
local file, the source path is recorded directly. For remote or database-backed sources
(PostGIS, WFS), the layer is exported to a GeoPackage at materialization time.

All vector layers are packaged into a single `notebook_data.gpkg` file alongside the
notebook, with each layer stored as a named layer inside the GeoPackage:

```
my_notebook.py
notebook_data.gpkg          ← all materialized vector layers
  ├── layername=roads
  ├── layername=catchments
  └── layername=parcels
```

This keeps the data self-contained and avoids a scatter of individual Shapefile or
GeoPackage files. The materialized manifest records the GeoPackage path and layer name
for each logical layer name used in the notebook.

#### Raster layers → user choice of format

Raster layers are exported at materialization time. The user chooses the output format
from the dock widget's export dialog; the default is **GeoTIFF** for maximum
compatibility, but the dialog also offers Cloud-Optimised GeoTIFF (COG), NetCDF, and
any other format supported by `gdal:translate`. Each raster is written to a file
alongside the notebook:

```
my_notebook.py
notebook_data.gpkg
dem.tif                     ← exported raster (format chosen at export time)
landcover.tif
```

Large rasters are exported at their native resolution. The export dialog warns if the
total output size exceeds a threshold (default 500 MB) and offers a resolution
reduction option.

#### In-memory and scratch layers

Layers with no file-backed source URI (scratch layers created in QGIS, in-memory
algorithm outputs, manually drawn features) are detected during materialization. The
dock widget lists them and requires the user to either:

- **Export them** — they are written into `notebook_data.gpkg` as additional layers, or
- **Exclude them** — the materialized notebook skips them, and `HeadlessQGIS` raises a
  clear error if a cell tries to access them

#### Canvas extent

`get_canvas_extent()` returns a bounding box from the live canvas. The materialized
value is captured at export time as four floats and embedded as the default in the
`HeadlessQGIS` configuration. In headless mode, `get_canvas_extent()` returns this
static value instead of querying a live canvas.

#### Selected features

Selected features are ephemeral — there is nothing on disk to materialize. If a
notebook cell calls `get_selected_features()`, the materialized version must handle
the absence of a selection. Two options, both documented:

- **Snapshot at export time** — the selection at the moment of materialization is
  written into `notebook_data.gpkg` as a named layer (`_selection_<layername>`).
  `HeadlessQGIS.get_selected_features()` reads this snapshot.
- **Explicit guard** — the user wraps the call in a try/except that substitutes an
  empty GeoDataFrame or a hardcoded filter when running headlessly.

#### Processing algorithm outputs

Outputs generated by `run_algorithm()` during the session are temp files that do not
survive. The materialized notebook re-runs the algorithms from their inputs on each
headless execution — this is correct behaviour, since the inputs are materialized and
the algorithms are deterministic. No special handling is needed unless the algorithm
takes a very long time, in which case the user can choose to cache the output into
`notebook_data.gpkg` at export time.

### The materialization manifest

A `notebook_data.json` manifest file is written alongside the notebook. It records the
mapping from logical layer names to materialized paths, the captured canvas extent, and
any format metadata:

```json
{
  "materialized_at": "2026-04-15T14:32:00",
  "qgis_project_path": "/home/user/projects/catchments/catchments.qgz",
  "layers": {
    "roads":      {"type": "vector", "path": "notebook_data.gpkg", "layername": "roads"},
    "catchments": {"type": "vector", "path": "notebook_data.gpkg", "layername": "catchments"},
    "dem":        {"type": "raster", "path": "dem.tif", "format": "GTiff"}
  },
  "canvas_extent": {"xmin": -70.5, "ymin": 43.8, "xmax": -69.1, "ymax": 44.9, "crs": "EPSG:4326"},
  "selection_snapshots": {
    "parcels": {"path": "notebook_data.gpkg", "layername": "_selection_parcels"}
  }
}
```

`HeadlessQGIS.__init__()` looks for `notebook_data.json` in the same directory as
`__file__`. If present, it uses the manifest for layer resolution. If absent, it falls
back to the existing marimo-qgis headless behaviour (user-managed paths).

### How materialization is triggered

**Dock widget — "Export for headless use" button**

Available for any open notebook session. Opens a dialog showing:

1. All layers accessed this session (name, source type, size estimate)
2. In-memory layers flagged with an action required (export or skip)
3. Raster format selector (default: GeoTIFF)
4. Output directory (default: same directory as the notebook)
5. A size estimate for the total export

On confirm, the dock widget:
- Exports all vector layers into `notebook_data.gpkg` via `native:package` (QGIS
  "Package Layers" algorithm, which writes multiple layers into one GeoPackage)
- Exports rasters via `gdal:translate` in the chosen format
- Snapshots any current selections into `notebook_data.gpkg`
- Writes `notebook_data.json`

**Programmatic — `qgis.materialize(output_dir=".")`**

A bridge API call for use inside notebook cells or CI workflows. Takes the same steps
as the dock widget without a dialog, using GeoTIFF as the default raster format.
Returns the path to the written manifest file.

```python
@app.cell
def _(qgis):
    # After analysis is complete, export for headless use
    manifest_path = qgis.materialize(output_dir=".")
    mo.md(f"Exported to `{manifest_path}` — notebook is now portable.")
    return
```

### Limitations and honest constraints

| Situation | Behaviour |
|---|---|
| Layer source is a live PostGIS connection | Exported to GeoPackage at time of materialization — snapshot, not live |
| Layer source is a WFS service | Exported to GeoPackage — snapshot |
| In-memory layer, user chose "exclude" | `HeadlessQGIS.get_layer()` raises `KeyError` with clear message |
| Very large raster (>500 MB) | Warning shown; user can reduce resolution or exclude |
| Notebook calls `get_canvas_extent()` headlessly | Returns the static extent captured at export time |
| Notebook calls `render_map()` headlessly | Works — `HeadlessQGIS` renders against the materialized layers using the captured extent |
| Data on disk moves after materialization | Paths in manifest are absolute; notebook breaks if files are moved. Fix: keep notebook and `notebook_data.*` together and use relative paths. |
| Project CRS differs between sessions | The materialized GeoPackage stores data in its native CRS; QGIS reprojects on load as usual |

### Where this fits in the roadmap

Materialization is a **Phase 4** feature. It requires:
- `layer_info()` endpoint (Phase 2) to resolve source URIs
- `run_algorithm()` (Phase 3) for `native:package` and `gdal:translate` export calls
- A stable `HeadlessQGIS` API that reads the manifest (can be designed in Phase 1
  alongside `HeadlessQGIS` itself, even if the manifest writer comes later)

Phase 4 checklist additions:

- [ ] `plugin/bridge/api.py` — `materialize(layer_names, output_dir, raster_format)`
  method: resolves source URIs, calls `native:package` for vectors, `gdal:translate`
  for rasters, writes `notebook_data.json`
- [ ] `plugin/ui/dock.py` — "Export for headless use" button and dialog: layer list,
  in-memory layer flags, raster format selector, size estimate, confirm/cancel
- [ ] `qgis_bridge/_headless.py` — `HeadlessQGIS.__init__()` reads
  `notebook_data.json` from `os.path.dirname(__file__)` if present; falls back to
  existing behaviour if not
- [ ] `qgis_bridge/_headless.py` — `HeadlessQGIS.get_layer(name)` resolves from
  manifest: opens GeoPackage layer for vectors, rioxarray for rasters
- [ ] `example/materialization_demo.py` — NEW: interactive session → materialize →
  run headlessly, demonstrating the full roundtrip

---

## 9. What rqgis Code We Reuse

| rqgis source | What we take | Destination |
|---|---|---|
| `core/qgis_api.py` | Full logic for `list_layers`, `get_layer`, `insert_layer`, `get_layer_info`, `canvas_extent`, `selected_features`, `_resolve_layer` | `plugin/bridge/api.py` (ported to QGIS 4 API; `QGISBridgeAPI` methods return Python dicts/paths to the aiohttp handler, which serialises them to JSON for the HTTP response) |
| `core/thread.py` | `QObject.moveToThread` + signal/slot pattern; `QMetaObject.invokeMethod` with `BlockingQueuedConnection` | `plugin/bridge/api.py` and `plugin/plugin.py` |
| `core/utils.py` | Temp file tracking, cleanup on unload | `plugin/bridge/convert.py` |
| `main.py` | Plugin state machine (`UNINITIALIZED → INITIALIZING → READY`) | `plugin/plugin.py` |
| `ui/dock.py` | Dock widget structural pattern (QSplitter, corner buttons, state indicator) | `plugin/ui/dock.py` (simplified — no console, just notebook manager) |
| `core/logger.py` | Session logging for debug mode | `plugin/bridge/api.py` (optional) |

---

## 10. Example: What a Live Notebook Looks Like

### Phase 1–4: HTTP mode (default)

```python
# example/live_layers.py
# Requires: marimo-qgis plugin loaded in QGIS, bridge server running.
# Launch from the plugin dock, or from terminal:
#   uv run marimo edit example/live_layers.py
# The plugin injects MARIMO_QGIS_PORT and MARIMO_QGIS_TOKEN into the subprocess env.

import marimo
app = marimo.App(width="full")

@app.cell
def _():
    import marimo as mo
    return (mo,)

@app.cell
def _():
    from qgis_bridge import QgisBridge
    # Reads MARIMO_QGIS_PORT + MARIMO_QGIS_TOKEN from env — no URL or token in code.
    # Falls back to HeadlessQGIS automatically if env vars are absent.
    qgis = QgisBridge()
    return (qgis,)

@app.cell
def _(mo, qgis):
    layers = qgis.list_layers()   # DataFrame: name, id, type, CRS
    layer_selector = mo.ui.dropdown(
        options=layers["name"].tolist(),
        label="Select layer",
    )
    mo.vstack([mo.ui.table(layers), layer_selector])
    return (layer_selector,)

@app.cell
def _(mo, qgis, layer_selector):
    gdf = qgis.get_layer(layer_selector.value)   # GeoDataFrame via .fgb temp file
    mo.vstack([
        mo.md(f"### {layer_selector.value} — {len(gdf)} features"),
        mo.ui.table(gdf.drop(columns="geometry").head(50)),
    ])
    return (gdf,)

@app.cell
def _(mo, qgis):
    img = qgis.render_map(width=900, height=600)   # PNG bytes, no temp file
    mo.vstack([mo.md("## Current map view"), mo.image(img)])
    return

if __name__ == "__main__":
    app.run()
```

vs. the current headless pattern: **14 lines of QGIS boilerplate replaced by 3**,
and the notebook now sees the live QGIS project rather than loading its own.

### Phase 5: In-process mode (opt-in)

When "Enable in-process mode" is checked in plugin settings, the same notebook
import works identically — `QgisBridge()` detects the mode from the module-level
registration rather than env vars. The notebook code does not change. Cells gain
access to in-process-exclusive features by importing directly:

```python
@app.cell
def _():
    # In-process mode only: live PyQGIS objects are directly accessible.
    # No need to go through qgis_bridge — the QGIS interpreter is this interpreter.
    from qgis.core import QgsProject
    layer = QgsProject.instance().mapLayersByName("roads")[0]  # actual QgsVectorLayer
    crs = layer.crs().toWkt()    # full WKT2, no bridge endpoint needed
    return (layer, crs)

@app.cell
def _():
    # Connect to a QGIS signal from a cell (in-process mode only)
    from qgis.core import QgsProject
    def on_layer_added(layer):
        print(f"Layer added to project: {layer.name()}")
    QgsProject.instance().layerWasAdded.connect(on_layer_added)
    return
```

### Headless fallback (existing pattern, both modes)

When the plugin is not running, `QgisBridge()` raises and the notebook falls back to
the original headless pattern — unchanged from the current marimo-qgis implementation:

```python
@app.cell
def _():
    try:
        from qgis_bridge import QgisBridge
        qgis = QgisBridge()
    except RuntimeError:
        from qgis_bridge import HeadlessQGIS
        qgis = HeadlessQGIS()   # initialises own QgsApplication from disk files
    return (qgis,)
```

---

## 11. Open Questions

### Phase 1–4 (HTTP — must resolve before starting)

1. **aiohttp availability in QGIS plugin context**: aiohttp is not bundled with QGIS 4.
   The plugin must either vendor it, install it via `pip` into the QGIS Python
   environment during setup, or ship it as a bundled dependency in the plugin ZIP.
   Determine the installation mechanism before Phase 1 begins. Alternative: use
   Python's stdlib `http.server` or `socketserver` in a thread (no external dep) for
   Phase 1, replace with aiohttp in Phase 2 when concurrency matters.

2. **Port selection and conflict handling**: binding to `127.0.0.1:0` lets the OS
   choose a free port. Verify this works correctly in the QGIS plugin environment
   on all three platforms (Linux, Windows, macOS) and that the chosen port is correctly
   read back and passed to the subprocess env before the subprocess starts.

3. **Temp file cleanup on abnormal QGIS exit**: if QGIS crashes or is force-killed,
   the plugin's `unload()` method does not run and temp files are not deleted. Decide
   whether to use a fixed temp directory with a known prefix (so a startup sweep can
   clean old files) or accept that orphaned `.fgb` / `.tif` files accumulate in `/tmp`.

4. **Plugin Repository naming**: coordinate to avoid confusion with rqgis's "R Console"
   entry. Candidate names: "marimo Notebook Bridge", "marimo for QGIS", "marimo Launcher".

### Phase 5 (in-process — defer until gate decision)

5. **`marimo.create_asgi_app()` API stability**: the embedding API exists but running
   a specific notebook path in-process with a managed kernel lifecycle is not a
   first-class documented scenario. Read the marimo 0.21.x changelog and test against
   the current API before committing to Phase 5. If the API is not stable, Phase 5
   is deferred until it is.

6. **asyncio + `Qt.BlockingQueuedConnection`**: a synchronous `invokeMethod` call from
   inside an asyncio coroutine blocks the event loop thread until the Qt main thread
   responds. For slow operations (large layer export, map render) this stalls marimo's
   WebSocket handler, making the browser UI appear frozen. Mitigation: wrap in
   `loop.run_in_executor(None, ...)` to move the blocking call off the event loop
   thread. Profile and decide in Phase 5 design.

7. **Race condition on `QGISBridgeAPI.result`**: the rqgis pattern stores the return
   value as `self.result` on the QObject. With multiple in-process notebook threads
   calling `dispatch()` concurrently this is a race. Fix options: (a) per-call lock
   around the invoke + result read; (b) redesign `dispatch()` to return the value
   directly via `Q_RETURN_ARG` rather than a side-channel attribute. Must be resolved
   before Phase 5 ships. Not relevant for HTTP (each HTTP request has its own
   response object).
