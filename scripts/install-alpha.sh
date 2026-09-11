#!/bin/bash
# One-line install for MBU GUI alpha. This is not a finished release.
set -euo pipefail

REF="${MBU_GUI_REF:-v0.1.0-alpha.1}"
SRC="${MBU_GUI_SRC:-https://github.com/computeralex/mbu-gui.git}"
DEST="${MBU_GUI_DIR:-$HOME/mbu-gui}"
DEB_NAME="mbu-gui_0.1.0~alpha1_all.deb"

say() { printf '%s\n' "$*"; }
die() { say "$*" >&2; exit 1; }

confirm() {
    local reply=""
    if [[ -r /dev/tty ]]; then
        read -r -p "Type ALPHA to continue: " reply </dev/tty
    else
        die "No terminal to confirm on. Run this in a real terminal, not a pipe without /dev/tty."
    fi
    [[ "$reply" == "ALPHA" ]] || die "Stopped. Nothing was installed."
}

[[ "$(id -u)" -ne 0 ]] || die "Do not run this as root. It will sudo when it needs to."
command -v sudo >/dev/null || die "sudo is required."

cat <<'EOF'

  MBU GUI  —  ALPHA

  This is 0.1.0-alpha.1, for testing only. It can erase a disk.
  Make a copy of anything you care about before you continue.

  It is a mirror, not a file archive: what you delete here is
  deleted from the backup on the next run.

  You need a spare disk you are willing to lose. The computer must
  be UEFI + GPT. Turn Secure Boot off before you boot the backup
  disk. Unplug that disk after every backup.

  Winux / Ubuntu 24.04 only. One window at a time.

EOF

confirm

say "Installing build tools..."
# A leftover PPA (Kodi, old graphics drivers, etc.) that has no Release
# file for this Ubuntu version makes `apt-get update` fail. That is not
# an MBU problem, and -qq hid the line that named the dead source.
if ! sudo apt-get update; then
    say ""
    say "apt could not refresh every software source. That is usually an old"
    say "third-party PPA that does not support this Ubuntu version — not a"
    say "problem with MBU. The line above that starts with E: names it."
    say "You can remove it later with:  sudo add-apt-repository --remove ppa:NAME"
    say "Continuing with the sources that still work..."
    say ""
fi
sudo apt-get install -y git make dpkg python3 python3-pip

if [[ -e "$DEST" && ! -d "$DEST/.git" ]]; then
    die "$DEST already exists and is not a git checkout."
fi

if [[ -d "$DEST/.git" ]]; then
    say "Updating $DEST to $REF..."
    git -C "$DEST" fetch --tags origin
    git -C "$DEST" checkout --detach "$REF"
else
    say "Cloning $REF into $DEST..."
    git clone --branch "$REF" --depth 1 "$SRC" "$DEST"
fi

say "Building the package..."
make -C "$DEST/packaging" deb

say "Installing $DEB_NAME..."
sudo apt-get install -y "$DEST/packaging/$DEB_NAME"

say "Installing PySide6 (Ubuntu 24.04 has no package for it)..."
pip3 install --user --break-system-packages PySide6

cat <<EOF

  Installed. Start it with:  mbu-gui

  This is still alpha. Spare disk only. Secure Boot off to boot a clone.
  Unplug the backup disk when you are done.

EOF
