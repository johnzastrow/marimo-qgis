"""MarimoManagerDock — a QGIS dock widget to launch and manage marimo notebooks.

Two tabs:
  - Browse: pick a directory, list its .py notebooks, Launch one, or create a new
    marimo + QGIS notebook from a scaffold.
  - Running: the notebooks launched this session (path + PID), with Stop.

Launching goes through MarimoProcessManager, which injects the bridge connection.
All Qt imports go through `qgis.PyQt` (D3) so the code works on Qt5 and Qt6.
"""

import os

from qgis.core import QgsProject, QgsSettings
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .scaffold import qgis_bridge_root, scaffold_notebook

_DIR_SETTING = "marimo/browse_dir"


class MarimoManagerDock(QDockWidget):
    """Dock widget for browsing, launching, creating and managing notebooks."""

    def __init__(self, process_manager, server=None, parent=None):
        super().__init__("marimo", parent)
        self.setObjectName("MarimoManagerDock")
        self._pm = process_manager
        self._server = server
        self._settings = QgsSettings()
        self._browse_dir = self._settings.value(_DIR_SETTING, "") or (
            QgsProject.instance().homePath() or os.path.expanduser("~")
        )
        self._build_ui()
        self.refresh()

    # ---- construction ----------------------------------------------------

    def _build_ui(self):
        container = QWidget(self)
        layout = QVBoxLayout(container)

        self._status = QLabel(self._bridge_status(), container)
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        tabs = QTabWidget(container)
        tabs.addTab(self._build_browse_tab(), "Browse")
        tabs.addTab(self._build_running_tab(), "Running")
        layout.addWidget(tabs)

        self.setWidget(container)

    def _build_browse_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        row = QHBoxLayout()
        self._dir_edit = QLineEdit(self._browse_dir, tab)
        self._dir_edit.setReadOnly(True)
        browse = QPushButton("Browse…", tab)
        browse.clicked.connect(self._on_browse)
        row.addWidget(self._dir_edit)
        row.addWidget(browse)
        layout.addLayout(row)

        self._file_list = QListWidget(tab)
        self._file_list.itemDoubleClicked.connect(self._on_launch_file)
        layout.addWidget(self._file_list)

        buttons = QHBoxLayout()
        launch = QPushButton("Launch", tab)
        launch.setToolTip("Open the selected notebook (double-click works too)")
        launch.clicked.connect(self._on_launch_file)
        new = QPushButton("New…", tab)
        new.setToolTip("Create a new marimo + QGIS notebook from a starter template")
        new.clicked.connect(self._on_new)
        rescan = QPushButton("Refresh", tab)
        rescan.clicked.connect(self._refresh_files)
        for widget in (launch, new, rescan):
            buttons.addWidget(widget)
        layout.addLayout(buttons)

        return tab

    def _build_running_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self._running_list = QListWidget(tab)
        layout.addWidget(self._running_list)

        buttons = QHBoxLayout()
        stop = QPushButton("Stop", tab)
        stop.setToolTip("Stop the selected running notebook")
        stop.clicked.connect(self._on_stop)
        rescan = QPushButton("Refresh", tab)
        rescan.clicked.connect(self.refresh)
        buttons.addWidget(stop)
        buttons.addWidget(rescan)
        layout.addLayout(buttons)

        return tab

    # ---- status + refresh ------------------------------------------------

    def _bridge_status(self):
        if self._server is not None:
            return f"🟢 Bridge: 127.0.0.1:{self._server.port}"
        return "⚪ Bridge: not running (notebooks fall back to headless)"

    def refresh(self):
        """Refresh the status line and both lists."""
        self._status.setText(self._bridge_status())
        self._refresh_files()
        self._refresh_running()

    def _refresh_files(self):
        self._file_list.clear()
        if not os.path.isdir(self._browse_dir):
            return
        for name in sorted(os.listdir(self._browse_dir)):
            if name.endswith(".py") and os.path.isfile(
                os.path.join(self._browse_dir, name)
            ):
                item = QListWidgetItem(name)
                item.setData(
                    Qt.ItemDataRole.UserRole, os.path.join(self._browse_dir, name)
                )
                self._file_list.addItem(item)

    def _refresh_running(self):
        self._running_list.clear()
        for record in self._pm.running():
            proc = record["proc"]
            item = QListWidgetItem(
                f"{os.path.basename(record['path'])}  (PID {proc.pid})"
            )
            item.setToolTip(record["path"])
            item.setData(Qt.ItemDataRole.UserRole, proc)
            self._running_list.addItem(item)

    # ---- actions ---------------------------------------------------------

    def _set_dir(self, directory):
        self._browse_dir = directory
        self._settings.setValue(_DIR_SETTING, directory)
        self._dir_edit.setText(directory)
        self._refresh_files()

    def _on_browse(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select a notebook directory", self._browse_dir
        )
        if directory:
            self._set_dir(directory)

    def _launch(self, path):
        try:
            self._pm.launch(path, mode="edit")
        except FileNotFoundError:
            self._status.setText("✗ 'uv' not found on PATH — install uv and restart QGIS.")
            return
        self.refresh()

    def _on_launch_file(self):
        item = self._file_list.currentItem()
        if item is not None:
            self._launch(item.data(Qt.ItemDataRole.UserRole))

    def _on_new(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "New marimo notebook",
            os.path.join(self._browse_dir, "notebook.py"),
            "Python notebooks (*.py)",
        )
        if not path:
            return
        if not path.endswith(".py"):
            path += ".py"
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(scaffold_notebook(qgis_bridge_root()))
        except OSError as exc:
            QMessageBox.warning(self, "marimo", f"Could not create notebook:\n{exc}")
            return

        # Move the browse directory to the new file's folder and select it.
        self._set_dir(os.path.dirname(path))
        for row in range(self._file_list.count()):
            item = self._file_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == path:
                self._file_list.setCurrentItem(item)
                break

    def _on_stop(self):
        item = self._running_list.currentItem()
        if item is None:
            return
        proc = item.data(Qt.ItemDataRole.UserRole)
        if proc is not None:
            self._pm.stop(proc)
        self.refresh()
