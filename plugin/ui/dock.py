"""MarimoManagerDock — a QGIS dock widget to launch and manage marimo notebooks.

Two tabs:
  - Browse: pick a directory, list its .py notebooks, Launch one, or create a new
    marimo + QGIS notebook from a scaffold.
  - Running: the notebooks launched this session (path + PID), with Stop.

Launching goes through MarimoProcessManager, which injects the bridge connection.
All Qt imports go through `qgis.PyQt` (D3) so the code works on Qt5 and Qt6.
"""

import os
import re

from qgis.core import QgsApplication, QgsProject, QgsSettings, QgsTask
from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..environment import download_examples, report_markdown
from ..runtime import qgis_python
from .process import marimo_available, validate_package_names
from .scaffold import qgis_bridge_root, scaffold_notebook

_DIR_SETTING = "marimo/browse_dir"


class MarimoManagerDock(QDockWidget):
    """Dock widget for browsing, launching, creating and managing notebooks."""

    def __init__(self, process_manager, server=None, parent=None):
        super().__init__("marimo", parent)
        self.setObjectName("MarimoManagerDock")
        self._pm = process_manager
        self._server = server
        self._install_record = None  # in-flight `pip install marimo`, if any
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
        tabs.addTab(self._build_setup_tab(), "Setup")
        tabs.addTab(self._build_browse_tab(), "Browse")
        tabs.addTab(self._build_running_tab(), "Running")
        layout.addWidget(tabs)

        self.setWidget(container)

    def _build_setup_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        intro = QLabel(
            "Inspect the QGIS Python environment your notebooks run on, save a "
            "report to share, or download the example notebooks.",
            tab,
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self._env_text = QPlainTextEdit(tab)
        self._env_text.setReadOnly(True)
        self._env_text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self._env_text)

        buttons = QHBoxLayout()
        refresh = QPushButton("Refresh report", tab)
        refresh.clicked.connect(self._on_refresh_report)
        save = QPushButton("Save report as…", tab)
        save.setToolTip("Write the environment report to a Markdown file")
        save.clicked.connect(self._on_save_report)
        download = QPushButton("Download examples…", tab)
        download.setToolTip(
            "Fetch the example/ and notebooks/ folders from GitHub into a folder"
        )
        download.clicked.connect(self._on_download_examples)
        for widget in (refresh, save, download):
            buttons.addWidget(widget)
        layout.addLayout(buttons)

        # Install extra Python packages into QGIS's own interpreter (the one the
        # notebooks run on). They MUST go here, not into a separate venv — a
        # venv has no PyQGIS and reintroduces the ABI mismatch the launch model
        # exists to avoid. Uses the same cross-platform pip bootstrap as the
        # marimo preflight.
        pkg_label = QLabel(
            "Install Python packages into QGIS's Python (e.g. geopandas, "
            "rasterio). Notebooks pick them up on next launch.",
            tab,
        )
        pkg_label.setWordWrap(True)
        layout.addWidget(pkg_label)

        pkg_row = QHBoxLayout()
        self._pkg_edit = QLineEdit(tab)
        self._pkg_edit.setPlaceholderText("geopandas rasterio shapely>=2.0")
        self._pkg_edit.returnPressed.connect(self._on_install_packages)
        pkg_install = QPushButton("Install", tab)
        pkg_install.setToolTip("Install the listed packages into QGIS's Python")
        pkg_install.clicked.connect(self._on_install_packages)
        pkg_row.addWidget(self._pkg_edit)
        pkg_row.addWidget(pkg_install)
        layout.addLayout(pkg_row)

        # Populate the report once the panel is constructed.
        self._on_refresh_report()
        return tab

    def _on_install_packages(self):
        """Validate the Setup-tab package field and start a tracked install."""
        try:
            packages = validate_package_names(self._pkg_edit.text())
        except ValueError as exc:
            QMessageBox.warning(self, "Install packages", str(exc))
            return
        if self._install_record is not None:
            QMessageBox.information(
                self,
                "Install packages",
                "An install is already in progress — please wait for it to "
                "finish.",
            )
            return
        py = qgis_python()
        reply = QMessageBox.question(
            self,
            "Install packages?",
            "Install into QGIS's Python:\n"
            f"  {py}\n\n  " + ", ".join(packages) + "\n\n"
            "This runs pip (falling back to a per-user install where the system "
            "Python is read-only). Proceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self._install_record = self._pm.install_packages(packages)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(
                self, "Install packages", f"Could not start the install:\n{exc}"
            )
            return
        self._status.setText(
            "Installing " + ", ".join(packages) + " … you'll be notified when "
            "it finishes."
        )
        QTimer.singleShot(1500, self._check_install)

    def _on_refresh_report(self):
        self._env_text.setPlainText(report_markdown())

    def _on_save_report(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save environment report",
            os.path.join(self._browse_dir, "qgis_environment.md"),
            "Markdown (*.md);;All files (*)",
        )
        if not path:
            return
        if not os.path.splitext(path)[1]:
            path += ".md"
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(self._env_text.toPlainText())
        except OSError as exc:
            QMessageBox.warning(self, "Setup", f"Could not save report:\n{exc}")
            return
        self._status.setText(f"Saved environment report to {path}")

    def _on_download_examples(self):
        dest = QFileDialog.getExistingDirectory(
            self, "Where should the examples be saved?", self._browse_dir
        )
        if not dest:
            return
        self._status.setText("Downloading examples from GitHub…")

        def _work(task):
            return download_examples(
                dest,
                branch="main",
                folders=("example", "notebooks"),
                progress=task.setProgress,
            )

        def _done(exception, result=None):
            if exception is not None:
                QMessageBox.warning(
                    self, "Download examples", f"Download failed:\n{exception}"
                )
                self._status.setText("Example download failed.")
                return
            count = len(result or [])
            self._status.setText(f"Downloaded {count} files to {dest}")
            # Jump the Browse tab to the freshly downloaded notebooks.
            notebooks = os.path.join(dest, "notebooks")
            self._set_dir(notebooks if os.path.isdir(notebooks) else dest)

        # Run off the UI thread so QGIS stays responsive during the download.
        self._dl_task = QgsTask.fromFunction(
            "Download marimo-qgis examples", _work, on_finished=_done
        )
        QgsApplication.taskManager().addTask(self._dl_task)

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
        if not self._ensure_marimo():
            return
        record = self._pm.launch(path, mode="edit")
        self._status.setText(
            f"Launching {os.path.basename(path)} … log: {record['log']}"
        )
        # marimo's web server takes a moment to come up; if the process is already
        # gone shortly after launch it died on startup — surface the log so the
        # error isn't lost with the (now suppressed) console window.
        QTimer.singleShot(3000, lambda: self._check_early_exit(record))
        self.refresh()

    def _ensure_marimo(self):
        """Preflight: ensure marimo is importable in QGIS's Python; offer to
        install it if not.

        This is what makes a QGIS Python upgrade graceful — after an upgrade the
        new interpreter has a fresh site-packages with no marimo, and instead of
        a notebook that dies on ModuleNotFoundError the user gets a clear prompt
        to reinstall into the (newly-detected) interpreter.
        """
        if marimo_available():
            return True
        py = qgis_python()
        reply = QMessageBox.question(
            self,
            "Install marimo?",
            "marimo is not installed in QGIS's Python:\n"
            f"  {py}\n\n"
            "Install it now? This runs pip (falling back to a per-user install "
            "where the system Python is read-only). Progress is logged and "
            "you'll be notified when it finishes.\n\n"
            "Note: on some Linux setups QGIS uses the system Python, which may "
            "need pip first (e.g. 'sudo apt install python3-pip').",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            self._status.setText("marimo is required to launch notebooks.")
            return False
        # Start pip as a tracked subprocess (output logged, Popen retained so it
        # is not GC'd mid-run) and poll for completion — this keeps QGIS
        # responsive and works on Linux, where there is no console to watch.
        try:
            self._install_record = self._pm.install_marimo()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(
                self, "marimo", f"Could not start the install:\n{exc}"
            )
            return False
        self._status.setText(
            "Installing marimo … this can take a minute; you'll be notified "
            "when it finishes."
        )
        QTimer.singleShot(1500, self._check_install)
        return False

    def _check_install(self):
        """Poll the in-flight pip install and report when it finishes.

        Shared by the marimo preflight and the Setup-tab package installer — the
        message is driven by the record's "packages" so both paths get a clear,
        accurate result (success notice or failure dialog with the log tail).
        """
        record = self._install_record
        if record is None:
            return
        proc = record["proc"]
        if proc.poll() is None:
            QTimer.singleShot(1500, self._check_install)  # still installing
            return

        self._install_record = None
        self._pm.reap_install(record)
        pkgs = ", ".join(record.get("packages", [])) or "packages"
        if proc.returncode == 0:
            self._status.setText(f"Installed: {pkgs}")
            QMessageBox.information(
                self,
                "Install complete",
                f"Installed into QGIS's Python:\n  {pkgs}\n\nLaunched notebooks "
                "pick this up on their next start.",
            )
        else:
            tail = self._read_log_tail(record["log"])
            self._status.setText(f"Install of {pkgs} failed — see the dialog.")
            QMessageBox.warning(
                self,
                "Install failed",
                f"pip exited with code {proc.returncode} installing {pkgs}.\n\n"
                f"Log file:\n{record['log']}\n\n--- last output ---\n{tail}",
            )

    def _check_early_exit(self, record):
        proc = record["proc"]
        if proc.poll() is None:
            return  # still running — healthy
        tail = self._read_log_tail(record["log"])
        # A notebook that dies on a missing import is the common case for users
        # who need geo packages (geopandas, rasterio, …). Offer to install the
        # missing one into QGIS's Python instead of just showing the traceback.
        missing = self._missing_module(tail)
        if missing and self._install_record is None and self._offer_install(
            missing, os.path.basename(record["path"])
        ):
            return
        QMessageBox.warning(
            self,
            "marimo notebook exited",
            f"The notebook process exited (code {proc.returncode}) right after "
            f"launch.\n\nLog file:\n{record['log']}\n\n"
            f"--- last output ---\n{tail}",
        )

    @staticmethod
    def _missing_module(text):
        """Top-level package name from a `ModuleNotFoundError` in the log, if any.

        The import name (e.g. `rasterio`) usually matches the pip distribution
        name; where it differs the user can correct it via the Setup-tab field.
        """
        match = re.search(
            r"ModuleNotFoundError: No module named ['\"]([A-Za-z0-9_]+)",
            text,
        )
        return match.group(1) if match else None

    def _offer_install(self, package, notebook):
        """Offer to install a missing package; start it if accepted.

        Returns True if an install was started (so the caller skips the generic
        exit dialog), False otherwise.
        """
        try:
            packages = validate_package_names(package)
        except ValueError:
            return False  # not a clean name — fall through to the exit dialog
        reply = QMessageBox.question(
            self,
            "Missing package",
            f"'{notebook}' exited because the Python package '{package}' is not "
            "installed in QGIS's Python.\n\nInstall it now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return False
        try:
            self._install_record = self._pm.install_packages(packages)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(
                self, "Install packages", f"Could not start the install:\n{exc}"
            )
            return False
        self._status.setText(
            f"Installing {package} … re-launch the notebook when it finishes."
        )
        QTimer.singleShot(1500, self._check_install)
        return True

    @staticmethod
    def _read_log_tail(log_path, max_lines=40):
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as handle:
                lines = handle.readlines()
        except OSError as exc:
            return f"(could not read log: {exc})"
        tail = lines[-max_lines:]
        return "".join(tail).strip() or "(log was empty)"

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
