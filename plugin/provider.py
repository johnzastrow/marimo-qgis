from qgis.core import QgsProcessingProvider

from .algorithm import LaunchMarimoAlgorithm


class MarimoProvider(QgsProcessingProvider):
    """
    Processing provider that groups all marimo algorithms under the "marimo"
    entry in the Processing Toolbox.  New algorithms can be added by
    instantiating them inside loadAlgorithms().
    """

    def loadAlgorithms(self):
        self.addAlgorithm(LaunchMarimoAlgorithm())

    def id(self):
        # Unique string identifier — used internally by QGIS and in
        # algorithm IDs (e.g. "marimo:launchmarimo").
        return "marimo"

    def name(self):
        # Display name shown as the group header in the Processing Toolbox.
        return "marimo"

    def longName(self):
        return "marimo notebook launcher"
