# QGIS plugin entry point.
#
# QGIS calls classFactory(iface) when the plugin is loaded.  It must return
# an object with initGui() and unload() methods.
#
# Installation (Linux):
#   ln -s /path/to/marimo_qgis/plugin \
#         ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/marimo_launcher
#   Then: Plugins ▸ Manage and Install Plugins ▸ Installed ▸ enable "marimo Launcher"
#
# The symlink name (marimo_launcher) becomes the Python package name QGIS uses
# to import this __init__.py.  It must be a valid Python identifier.


def classFactory(iface):
    from .plugin import MarimoLauncherPlugin
    return MarimoLauncherPlugin(iface)
