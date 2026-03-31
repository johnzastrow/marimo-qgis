"""
Launch marimo Notebook — QGIS Processing Script

Add to the Processing Toolbox via:
  Processing Toolbox ▸ Scripts (⚙) ▸ Add Script to Toolbox… ▸ select this file

The algorithm will appear under  marimo ▸ Launch marimo notebook.
"""

from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingOutputString,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFile,
    QgsProcessingParameterString,
)


class LaunchMarimoAlgorithm(QgsProcessingAlgorithm):

    NOTEBOOK    = "NOTEBOOK"
    MODE        = "MODE"
    WORKING_DIR = "WORKING_DIR"
    URL         = "URL"

    # ------------------------------------------------------------------ meta

    def createInstance(self):
        return LaunchMarimoAlgorithm()

    def name(self):
        return "launchmarimo"

    def displayName(self):
        return "Launch marimo notebook"

    def group(self):
        return "marimo"

    def groupId(self):
        return "marimo"

    def shortHelpString(self):
        return (
            "Launches a marimo notebook editor or viewer in your browser "
            "as a detached subprocess.\n\n"
            "The notebook runs in its own Python process with QGIS bindings "
            "available (qgis.core, qgis.analysis, etc.). It does not share "
            "state with the running QGIS instance — each notebook initialises "
            "its own QgsApplication.\n\n"
            "Working directory controls relative paths inside the notebook "
            "(e.g. paths built with os.getcwd()). Defaults to the QGIS "
            "project home folder, or the notebook's own directory if no "
            "project is open."
        )

    # ------------------------------------------------------------ parameters

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFile(
                self.NOTEBOOK,
                "Notebook (.py file)",
                behavior=QgsProcessingParameterFile.Behavior.File,
                extension="py",
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.MODE,
                "Launch mode",
                options=[
                    "edit  —  interactive editing in the browser",
                    "run   —  view only (no code editing)",
                ],
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.WORKING_DIR,
                "Working directory  (leave blank to use QGIS project home)",
                defaultValue="",
                optional=True,
            )
        )
        self.addOutput(
            QgsProcessingOutputString(self.URL, "Notebook URL")
        )

    # --------------------------------------------------------------- execute

    def processAlgorithm(self, parameters, context, feedback):
        import os
        import subprocess
        from qgis.core import QgsProject

        notebook = self.parameterAsFile(parameters, self.NOTEBOOK, context)
        mode     = ["edit", "run"][self.parameterAsEnum(parameters, self.MODE, context)]
        cwd      = self.parameterAsString(parameters, self.WORKING_DIR, context).strip()

        if not cwd:
            cwd = QgsProject.instance().homePath() or os.path.dirname(notebook)

        # Inherit the QGIS environment (DISPLAY / WAYLAND_DISPLAY).
        #
        # PYTHONPATH: defence-in-depth.  Notebooks self-configure via
        #   sys.path.insert(0, "/usr/share/qgis/python")
        # inside their QGIS init cell, so they do not depend on this variable.
        # Setting it here ensures the marimo *server* process also finds the
        # bindings if it needs them before the first cell runs.
        #
        # QT_QPA_PLATFORM: do NOT inherit any "offscreen" value from the QGIS
        # process — the subprocess has a real display and needs a real platform.
        # Notebooks use os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"),
        # so if this env var is absent they fall back to offscreen themselves;
        # if we leave it unset here they will correctly detect the live display.
        env = os.environ.copy()
        env["PYTHONPATH"] = "/usr/share/qgis/python"
        env.pop("QT_QPA_PLATFORM", None)

        cmd = ["uv", "run", "marimo", mode, notebook]

        feedback.pushInfo(f"Notebook     : {notebook}")
        feedback.pushInfo(f"Mode         : {mode}")
        feedback.pushInfo(f"Working dir  : {cwd}")
        feedback.pushInfo(f"Command      : {' '.join(cmd)}")

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=cwd,
                env=env,
                start_new_session=True,
            )
        except FileNotFoundError:
            feedback.reportError(
                '"uv" not found.\n'
                "Install uv:  curl -LsSf https://astral.sh/uv/install.sh | sh\n"
                "Then restart QGIS so the updated PATH is inherited."
            )
            return {self.URL: ""}

        url = "http://localhost:2718"
        feedback.pushInfo(f"PID          : {proc.pid}")
        feedback.pushInfo(f"URL          : {url}")
        feedback.pushInfo(
            "marimo will be ready in a few seconds. "
            "Your browser should open automatically."
        )
        return {self.URL: url}
