"""HTTP client helpers for the QGIS bridge — standard library only.

Kept dependency-free (urllib, not requests) so `qgis_bridge` installs into any
notebook venv. All requests carry the Bearer token; non-2xx responses raise
BridgeError with the server's generic message.
"""

import json
import urllib.error
import urllib.request


class BridgeError(RuntimeError):
    """Raised when a bridge request fails (HTTP error or unreachable server)."""


class Client:
    """Minimal authenticated GET client against the localhost bridge."""

    def __init__(self, port, token, host="127.0.0.1", timeout=30):
        self._base = "http://{}:{}".format(host, int(port))
        self._token = token
        self._timeout = timeout

    def get(self, path):
        """GET `path`, return the parsed JSON body, or raise BridgeError."""
        req = urllib.request.Request(self._base + path)
        req.add_header("Authorization", "Bearer " + self._token)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            message = ""
            try:
                message = json.loads(exc.read().decode("utf-8")).get("error", "")
            except Exception:  # noqa: BLE001 — error body may be empty/non-JSON
                pass
            raise BridgeError("bridge {}: {}".format(exc.code, message)) from None
        except urllib.error.URLError as exc:
            raise BridgeError("bridge unreachable: {}".format(exc.reason)) from None
