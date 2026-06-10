"""MarimoManagerDock — a QGIS dock widget to launch and manage marimo notebooks.

Simplified from the rqgis dock pattern (PLANNING.md §7): no console/editor panel
— marimo provides those in the browser. This dock just lists running notebooks
(path + PID), launches new ones (with the bridge connection injected via
MarimoProcessManager), stops them, and shows the bridge status.

All Qt imports go through `qgis.PyQt` (D3) so the code works on Qt5 and Qt6.
"""

import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class MarimoManagerDock(QDockWidget):
    """Dock widget listing/launching marimo notebooks."""

    def __init__(self, process_manager, server=None, parent=None):
        super().__init__("marimo", parent)
        self.setObjectName("MarimoManagerDock")
        self._pm = process_manager
        self._server = server
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        container = QWidget(self)
        layout = QVBoxLayout(container)

        self._status = QLabel(self._bridge_status(), container)
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        self._list = QListWidget(container)
        layout.addWidget(self._list)

        buttons = QHBoxLayout()
        launch = QPushButton("Launch…", container)
        launch.setToolTip("Pick a notebook (.py) and open it with the bridge connected")
        launch.clicked.connect(self._on_launch)
        buttons.addWidget(launch)

        stop = QPushButton("Stop", container)
        stop.setToolTip("Stop the selected running notebook")
        stop.clicked.connect(self._on_stop)
        buttons.addWidget(stop)

        refresh = QPushButton("Refresh", container)
        refresh.clicked.connect(self.refresh)
        buttons.addWidget(refresh)

        layout.addLayout(buttons)
        self.setWidget(container)

    def _bridge_status(self):
        if self._server is not None:
            return f"🟢 Bridge: 127.0.0.1:{self._server.port}"
        return "⚪ Bridge: not running (notebooks fall back to headless)"

    def refresh(self):
        """Rebuild the running-notebook list and the bridge status line."""
        self._status.setText(self._bridge_status())
        self._list.clear()
        for record in self._pm.running():
            proc = record["proc"]
            item = QListWidgetItem(
                f"{os.path.basename(record['path'])}  (PID {proc.pid})"
            )
            item.setToolTip(record["path"])
            item.setData(Qt.ItemDataRole.UserRole, proc)
            self._list.addItem(item)

    def _on_launch(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a marimo notebook", "", "Python notebooks (*.py)"
        )
        if not path:
            return
        try:
            self._pm.launch(path, mode="edit")
        except FileNotFoundError:
            self._status.setText("✗ 'uv' not found on PATH — install uv and restart QGIS.")
            return
        self.refresh()

    def _on_stop(self):
        item = self._list.currentItem()
        if item is None:
            return
        proc = item.data(Qt.ItemDataRole.UserRole)
        if proc is not None:
            self._pm.stop(proc)
        self.refresh()
