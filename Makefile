PLUGIN_NAME = marimo_launcher
PLUGIN_SRC  = plugin
ZIP_FILE    = $(PLUGIN_NAME).zip

.PHONY: package clean help

help:
	@echo "Targets:"
	@echo "  package  — build $(ZIP_FILE) for installation via QGIS Plugin Manager"
	@echo "  clean    — remove build artefacts"

package: clean
	mkdir -p $(PLUGIN_NAME)
	# Copy the entire plugin source tree so new sub-packages (bridge/, ui/, ...)
	# are included automatically — never enumerate files by hand, or they get
	# silently dropped from the zip and the installed plugin breaks on import.
	cp -r $(PLUGIN_SRC)/. $(PLUGIN_NAME)/
	# Bundle the notebook-side client INSIDE the plugin so users who install
	# only the plugin (no pip) can `import qgis_bridge` from launched notebooks
	# (MarimoProcessManager adds the plugin dir to the notebook's PYTHONPATH).
	cp -r qgis_bridge $(PLUGIN_NAME)/
	# Bundle the LICENSE — required for publication on plugins.qgis.org.
	cp LICENSE $(PLUGIN_NAME)/
	# Strip Python caches that may have been copied in.
	find $(PLUGIN_NAME) -name '__pycache__' -type d -prune -exec rm -rf {} +
	find $(PLUGIN_NAME) -name '*.pyc' -delete
	zip -r $(ZIP_FILE) $(PLUGIN_NAME)/
	rm -rf $(PLUGIN_NAME)
	@echo "Built $(ZIP_FILE) — install via QGIS: Plugins ▸ Install from ZIP"

clean:
	rm -rf $(PLUGIN_NAME) $(ZIP_FILE)
