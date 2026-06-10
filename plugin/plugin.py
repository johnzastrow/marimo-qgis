import os

from qgis.core import Qgis, QgsApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction


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
    GUI plugin. QGIS instantiates this via classFactory() and calls initGui()
    once the UI is ready and unload() on teardown.

    initGui():
      - starts the localhost HTTP bridge (plugin/bridge) so notebooks launched
        from QGIS can read/write the live project (fail-safe: a bridge error
        never blocks the plugin from loading);
      - adds the marimo manager dock (hidden on load) and a toolbar button (plus
        a Plugins-menu entry) that toggles it.

    The dock launches notebooks via MarimoProcessManager, which injects the
    bridge connection into the subprocess environment.
    """

    MENU = "marimo"

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(os.path.realpath(__file__))
        self._temp = None
        self._api = None
        self._server = None
        self._pm = None
        self._dock = None
        self._action = None

    def initGui(self):
        self._start_bridge()
        self._add_ui()

    # ---- bridge lifecycle ------------------------------------------------

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
            # and parented to nothing — we hold the only reference. iface is
            # passed so canvas_extent / selected_features can reach the desktop.
            self._api = QGISBridgeAPI(self._temp, iface=self.iface)
            self._server = QgisBridgeServer(self._api).start()
            _log(f"bridge listening on 127.0.0.1:{self._server.port}")
        except Exception as exc:  # noqa: BLE001 — never break plugin load
            _log(f"bridge failed to start: {exc!r}", "error")
            self._stop_bridge()

    def _stop_bridge(self):
        """Stop the server, free the temp store, clear the runtime handle."""
        from . import runtime

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

    # ---- UI (toolbar button + dock) --------------------------------------

    def _add_ui(self):
        """Add the manager dock (hidden) and a toolbar button that toggles it."""
        try:
            from qgis.PyQt.QtCore import Qt

            from . import runtime
            from .ui.dock import MarimoManagerDock
            from .ui.process import MarimoProcessManager

            self._pm = MarimoProcessManager()
            runtime.set_server(self._server)

            self._dock = MarimoManagerDock(self._pm, self._server)
            self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._dock)
            self._dock.hide()  # revealed on demand from the toolbar

            icon_path = os.path.join(self.plugin_dir, "icons", "marimo.svg")
            self._action = QAction(
                QIcon(icon_path), "marimo Notebooks", self.iface.mainWindow()
            )
            self._action.setCheckable(True)
            self._action.setToolTip("Show/hide the marimo notebook manager")
            # Two-way sync: button toggles the dock; closing the dock unchecks it.
            self._action.toggled.connect(self._dock.setVisible)
            self._dock.visibilityChanged.connect(self._action.setChecked)

            self.iface.addToolBarIcon(self._action)
            self.iface.addPluginToMenu(self.MENU, self._action)
        except Exception as exc:  # noqa: BLE001 — never break plugin load
            _log(f"UI failed to load: {exc!r}", "error")

    def _remove_ui(self):
        if self._action is not None:
            try:
                self.iface.removeToolBarIcon(self._action)
                self.iface.removePluginMenu(self.MENU, self._action)
            except Exception as exc:  # noqa: BLE001
                _log(f"toolbar removal error: {exc!r}", "warning")
            self._action = None
        if self._dock is not None:
            try:
                self.iface.removeDockWidget(self._dock)
                self._dock.deleteLater()
            except Exception as exc:  # noqa: BLE001
                _log(f"dock removal error: {exc!r}", "warning")
            self._dock = None
        self._pm = None

    # ---- teardown --------------------------------------------------------

    def unload(self):
        """Remove the UI and tear down the bridge."""
        self._remove_ui()
        self._stop_bridge()
