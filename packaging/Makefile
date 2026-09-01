PKG := mbu-gui
VERSION := 0.1.0
ARCH := all
DEB := $(PKG)_$(VERSION)_$(ARCH).deb

REPO := $(abspath $(CURDIR)/..)
BUILD := $(CURDIR)/build
DEST := $(BUILD)/$(PKG)

.PHONY: deb clean

deb:
	rm -rf $(BUILD)
	mkdir -p $(DEST)/DEBIAN
	mkdir -p $(DEST)/usr/bin
	mkdir -p $(DEST)/usr/lib/mbu-gui
	mkdir -p $(DEST)/usr/share/mbu-gui
	mkdir -p $(DEST)/usr/share/applications
	mkdir -p $(DEST)/usr/share/polkit-1/actions
	mkdir -p $(DEST)/var/lib/mbu-gui
	cp $(CURDIR)/debian/control $(DEST)/DEBIAN/control
	cp $(REPO)/scripts/mbu-gui $(DEST)/usr/bin/mbu-gui
	cp $(REPO)/scripts/mbu-gui-helper $(DEST)/usr/lib/mbu-gui/mbu-gui-helper
	cp -a $(REPO)/src/mbu_gui $(DEST)/usr/lib/mbu-gui/mbu_gui
	cp -a $(REPO)/src/mbu_gui_helper $(DEST)/usr/lib/mbu-gui/mbu_gui_helper
	cp -a $(REPO)/vendor/mbu $(DEST)/usr/share/mbu-gui/mbu
	cp $(REPO)/data/mbu-icon.png $(DEST)/usr/share/mbu-gui/mbu-icon.png
	cp $(REPO)/data/mbu-gui.desktop $(DEST)/usr/share/applications/mbu-gui.desktop
	cp $(REPO)/data/org.linuxbackupsoftware.mbu-gui.policy \
		$(DEST)/usr/share/polkit-1/actions/org.linuxbackupsoftware.mbu-gui.policy
	find $(DEST)/usr/lib/mbu-gui -type d -name __pycache__ -prune -exec rm -rf {} +
	chmod 0755 $(DEST)/usr/bin/mbu-gui
	chmod 0755 $(DEST)/usr/lib/mbu-gui/mbu-gui-helper
	chmod 0755 $(DEST)/DEBIAN
	chmod 0644 $(DEST)/DEBIAN/control
	dpkg-deb --root-owner-group --build $(DEST) $(CURDIR)/$(DEB)

clean:
	rm -rf $(BUILD) $(CURDIR)/$(DEB)
