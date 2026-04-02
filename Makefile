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
	cp $(PLUGIN_SRC)/__init__.py  $(PLUGIN_NAME)/
	cp $(PLUGIN_SRC)/metadata.txt $(PLUGIN_NAME)/
	cp $(PLUGIN_SRC)/plugin.py    $(PLUGIN_NAME)/
	cp $(PLUGIN_SRC)/provider.py  $(PLUGIN_NAME)/
	cp $(PLUGIN_SRC)/algorithm.py $(PLUGIN_NAME)/
	zip -r $(ZIP_FILE) $(PLUGIN_NAME)/
	rm -rf $(PLUGIN_NAME)
	@echo "Built $(ZIP_FILE) — install via QGIS: Plugins ▸ Install from ZIP"

clean:
	rm -rf $(PLUGIN_NAME) $(ZIP_FILE)
