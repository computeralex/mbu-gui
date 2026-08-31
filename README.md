# MBU GUI

A window for Ted Merrill's MBU on Winux (Ubuntu 24.04 + KDE).

This is a wrapper, not a rewrite. Original MBU scripts live in `vendor/mbu`.

## Run from this repo

```bash
sudo apt install python3-pyside6 python3-pytest
python3 -m pytest
PYTHONPATH=src python3 -m mbu_gui
```

Privileged actions need the `.deb` (PolicyKit policy). The window still opens without it.

## Install

```bash
make -C packaging deb
sudo apt install ./packaging/mbu-gui_0.1.0_all.deb
```

See LICENSE for warranty. We do not speak for Ted Merrill.
