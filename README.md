# MBU GUI

**Alpha — for testing only.** This can erase a disk. Make a copy of anything
you care about before you run it. It is not finished software.

Install with:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/computeralex/mbu-gui/main/scripts/install-alpha.sh)"
```

That line prints the warning and waits for you to type `ALPHA`. Winux /
Ubuntu 24.04 + KDE. Spare disk only.

A window for Ted Merrill's MBU. This is a wrapper, not a rewrite. Original
MBU scripts live in `vendor/mbu`. A UEFI VM has completed a backup and
booted the clone with Secure Boot off. That is not the same as “safe for
your laptop.”

## What this is

MBU makes a **mirror** of this computer onto a spare disk. That copy can boot
if the firmware will load the copied EFI files. Each run makes the spare disk
match this computer exactly, so a file you delete here is gone from the backup
on the next run. It is not Time Machine and it is not a file archive.

## Before you install

- **Copy your data first.** Format and backup both write to a real disk.
- You need a **spare disk** you are willing to erase.
- The computer must be **UEFI + GPT**. Legacy BIOS / MBR is refused on purpose.
- **Turn Secure Boot off** before you try to boot the backup disk. Ted's docs
  never mention this. Firmware that still has Secure Boot on can see a complete
  ESP (`BOOTX64.EFI`, `shimx64.efi`) and still print `Access Denied`.
- Unplug the backup disk after every backup. MBU clones filesystem UUIDs.
  Leaving both disks attached can make Linux boot the wrong one.
- Run **one window** at a time.

## Known limits of this alpha

- We do not check that the backup disk is large enough. An undersized disk
  fails late, during the copy.
- Exit 0 means MBU finished, not that we verified the clone boots. Boot it
  once yourself, with Secure Boot off.
- PySide6 is a second install. Ubuntu 24.04 has no `python3-pyside6` package.
- There is no dry run. Confirming a format or a backup starts a write.
- Destination size, single-instance lock, and CI are not in this build.

See LICENSE for warranty. We do not speak for Ted Merrill.

## Install by hand

From the tag, if you do not want the one-liner:

```bash
git clone --branch v0.1.0-alpha.1 https://github.com/computeralex/mbu-gui.git
cd mbu-gui
make -C packaging deb
sudo apt install ./packaging/mbu-gui_0.1.0~alpha1_all.deb
pip3 install --user --break-system-packages PySide6
```

`--break-system-packages` is required because Ubuntu 24.04 marks system Python
as externally managed (PEP 668). Privileged actions need the `.deb` (PolicyKit).
The window still opens without it.

## License

The GUI (`src/`, `scripts/`, `packaging/`, `data/`) is **MIT**. No warranty
of any kind, express or implied. See `LICENSE`.

Ted Merrill's scripts in `vendor/mbu` are his. He released them uncopyrighted:
public domain, or MIT or BSD, at your discretion. Do not claim ownership of
what he wrote. This GUI does not speak for him.

This software can erase disks. You use it at your own risk.

## Run from this repo

```bash
sudo apt install python3-pytest
pip3 install --user --break-system-packages PySide6
python3 -m pytest
PYTHONPATH=src python3 -m mbu_gui
```
