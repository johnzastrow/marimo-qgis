from qgis.core import QgsApplication

from .provider import MarimoProvider


class MarimoLauncherPlugin:
    """
    Main plugin class.  QGIS instantiates this via classFactory() and calls:
      - initProcessing() early in startup (because hasProcessingProvider=yes
        in metadata.txt) to register the Processing provider
      - initGui() once the QGIS UI is ready
      - unload() when the plugin is disabled or QGIS exits
    """

    def __init__(self, iface):
        self.iface = iface
        self.provider = None

    def initProcessing(self):
        """Register the marimo Processing provider with QGIS."""
        self.provider = MarimoProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):
        # Processing provider is registered in initProcessing(), which QGIS
        # calls before initGui() when hasProcessingProvider=yes.  Nothing
        # extra is needed here unless we later add toolbar buttons or menus.
        self.initProcessing()

    def unload(self):
        """Remove the provider when the plugin is disabled or QGIS exits."""
        QgsApplication.processingRegistry().removeProvider(self.provider)
