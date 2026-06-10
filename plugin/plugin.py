from qgis.core import Qgis, QgsApplication

from . import runtime
from .provider import MarimoProvider


def _log(message, level="info"):
    levels = {
        "info": Qgis.MessageLevel.Info,
        "warning": Qgis.MessageLevel.Warning,
        "error": Qgis.MessageLevel.Critical,
    }
    QgsApplication.messageLog().logMessage(
        message, "marimo bridge", levels.get(level, Qgis.MessageLevel.Info)
    )


class MarimoLauncherPlugin:
    """
    Main plugin class.  QGIS instantiates this via classFactory() and calls:
      - initProcessing() early in startup (because hasProcessingProvider=yes
        in metadata.txt) to register the Processing provider
      - initGui() once the QGIS UI is ready
      - unload() when the plugin is disabled or QGIS exits

    On load it also starts the localhost HTTP bridge (plugin/bridge) so notebooks
    launched from QGIS can read the live project. Bridge startup is fail-safe: if
    it cannot bind, the Processing launcher still works and notebooks fall back to
    headless mode.
    """

    def __init__(self, iface):
        self.iface = iface
        self.provider = None
        self._temp = None
        self._api = None
        self._server = None

    def initProcessing(self):
        """Register the marimo Processing provider with QGIS."""
        self.provider = MarimoProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):
        # Processing provider is registered in initProcessing(), which QGIS
        # calls before initGui() when hasProcessingProvider=yes.
        self.initProcessing()
        self._start_bridge()

    def _start_bridge(self):
        """Start the HTTP bridge server on the Qt main thread (fail-safe)."""
        try:
            # Imported here (not at module top) so a missing dependency or an
            # import error cannot block the whole plugin from loading.
            from .bridge.api import QGISBridgeAPI
            from .bridge.convert import TempStore
            from .bridge.server import QgisBridgeServer

            self._temp = TempStore()
            # The API QObject is created on the main thread (initGui runs there)
            # and parented to nothing — we hold the only reference.
            self._api = QGISBridgeAPI(self._temp)
            self._server = QgisBridgeServer(self._api).start()
            runtime.set_server(self._server)
            _log(f"bridge listening on 127.0.0.1:{self._server.port}")
        except Exception as exc:  # noqa: BLE001 — never break plugin load
            _log(f"bridge failed to start: {exc!r}", "error")
            self._stop_bridge()

    def _stop_bridge(self):
        """Stop the server, free the temp store, clear the runtime handle."""
        runtime.set_server(None)
        if self._server is not None:
            try:
                self._server.stop()
            except Exception as exc:  # noqa: BLE001
                _log(f"bridge stop error: {exc!r}", "warning")
            self._server = None
        self._api = None
        if self._temp is not None:
            self._temp.cleanup()
            self._temp = None

    def unload(self):
        """Remove the provider and tear down the bridge."""
        self._stop_bridge()
        if self.provider is not None:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
