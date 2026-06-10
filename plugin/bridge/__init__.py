# marimo-qgis bridge (plugin side).
#
# This package runs INSIDE the QGIS process and exposes the running QGIS
# project to marimo notebooks over a localhost HTTP bridge.
#
# Submodules (import the one you need; this __init__ stays import-light so the
# transport/auth layer can be unit-tested without a running QGIS):
#   auth.py     — Bearer token generation + constant-time validation
#   convert.py  — vector layer -> FlatGeobuf temp file; private temp store
#   api.py      — QGISBridgeAPI (QObject, Qt main thread): all QGIS calls
#   server.py   — QgisBridgeServer: stdlib http.server on 127.0.0.1, marshals
#                 each request to the Qt main thread
#
# api.py imports qgis.* and is therefore only importable inside QGIS;
# server.py and auth.py depend only on the standard library.
#
# See PLANNING.md §6 (architecture) and §8 (build decisions D1–D4).
