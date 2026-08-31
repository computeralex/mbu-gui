# MBU GUI for Winux — Design

Date: 2026-08-31
Status: draft for review
MBU release wrapped: mbu-20251115 (Ted Merrill)

## 1. Purpose

Axel on Winux (Ubuntu 24.04 + KDE Plasma, Windows-like theme) installed Ted Merrill’s MBU. It appears in the application menu and on the desktop. Click does nothing.

The existing “GUI” is `mbu.desktop`: `Terminal=false`, `Path=mbu` (relative), `Exec=` opens `gnome-terminal` then `sudo ./mbup`. Winux’s native terminal is Konsole. `gnome-terminal` is often missing, so the launch fails silently. Ted tested Mint/Ubuntu (GNOME), not KDE.

Axel wants what Casper does on Windows: a bootable backup that only copies what changed. MBU already does that in bash. This project is a real window around Ted’s scripts, not a rewrite of rsync or boot-fix.

This GUI does not speak for Ted. It is a separate wrapper.

## 2. Goals (first ship)

One `.deb` a Winux user can install. After install:

- Menu and desktop icon open a **window**, every time. Never “click and nothing.”
- Admin is KDE PolicyKit (`pkexec`), asked only when an action needs root.
- Walk setup: name live-system partitions if missing; pick and format a backup disk (`mbuformat` internals).
- Run a backup (`mbup`) with visible progress (rsync file list / current path).
- Show last run, errors on screen, and a reminder to unplug the backup disk (UUIDs are cloned).
- Mount/browse a backup (`mbumount` / `mbuclean`) without a terminal.
- Fail on screen.

## 3. Non-goals

- Rewriting rsync, UUID cloning, grub-install, or other backup logic in Ted’s scripts.
- Archival history / versioned backups (MBU does not do this).
- Schedulers, PayPal, accounts, or a store listing.
- An in-app file merge tool (open Dolphin; user may use meld).
- Supporting MBR/legacy boot.
- Guaranteeing filesystems other than ext4, swap, and EFI.
- Shipping `gnome-terminal` or keeping Ted’s `mbu.desktop` as the user-facing launcher.

## 4. License and warranty

Match MBU’s spirit, and be explicit.

Ted Merrill is the sole author of original MBU (`vendor/mbu` / the bundled copy). He released it uncopyrighted; public domain, or MIT or BSD at the user’s discretion; do not claim ownership of what he wrote.

This GUI is released the same way: public domain, or MIT or BSD at the user’s discretion. Do not claim ownership of this GUI either.

**No warranty.** This software is provided as-is. The authors of this GUI are not responsible for data loss, unbootable disks, failed backups, or anything else people do with it. We do not speak for Ted Merrill and do not offer his support.

That legal text lives in `LICENSE` only. Do not plaster it around the UI. The app still shows **operational** warnings (unplug the backup disk; this will wipe `sdb`) because those prevent mistakes.

## 5. Users and environment

- Primary: Winux 11 on Ubuntu 24.04 LTS, KDE Plasma, Windows-like theme. User may know Casper/Windows and not the terminal.
- Secondary: anyone who can install the `.deb` on Ubuntu 24.04 + KDE (e.g. Kubuntu). Nice if it also runs, not a requirement to theme for GNOME.
- Must run as a normal user for the window; root only via PolicyKit for disk operations.
- Hardware: GPT/UEFI, hot-pluggable backup disk. Same constraints as MBU.

## 6. Architecture

Three pieces, one package.

```
[Desktop/menu click]
        |
        v
[mbu-gui]  Python 3 + PySide6, runs as the user
        |  reads lsblk, logs; never silent
        |  pkexec only when user starts a privileged action
        v
[mbu-gui-helper]  same Python, runs as root via PolicyKit
        |  cwd = bundled MBU directory
        |  exports mbuDir / mbuLogDir / mbuMountDir / mbuOutDir
        v
[Ted’s scripts]  mbup, mbulib, mbuformat internals, mbumount, mbuclean
                 unchanged
```

### 6.1 Window (`mbu-gui`)

- Always starts as the logged-in user.
- Discovers disks/partitions with `lsblk --json` (no root required for this).
- Reads last-run from the master log file.
- Builds helper command lines; streams helper stdout/stderr into the log view.
- If `pkexec` is cancelled, missing, or the helper is not installed, **the window explains that**.

### 6.2 Helper (`mbu-gui-helper`)

- The only binary listed in the PolicyKit action.
- Subcommands: `backup`, `label-live`, `format-disk`, `write-format-table`, `mount`, `clean`.
- `cd`s to the bundled MBU script directory before invoking Ted’s programs.
- Sets:

  - `mbuDir` = bundled scripts (read-only under `/usr/share/mbu-gui/mbu`)
  - `mbuLogDir`, `mbuMountDir`, `mbuOutDir` = per-user state under the real user’s home (see §8)
  - `mbuMasterLogFile`, `mbuBackupLatestLogFile`, `mbuFormatLatestLogFile` accordingly
  - `mbuDoRsyncVerbose=y` on backup so file names appear on stdout

- Streams child output line-buffered.
- On backup/format failure, still attempts `./mbuclean`.
- Refuses to format, wipe, or `mbuFormatDisk` the disk that currently contains `/`.

### 6.3 Bundled MBU

Ship Ted’s `mbu-20251115` tree at `/usr/share/mbu-gui/mbu/`. Do not modify those files. Upgrading MBU later is replacing that tree.

Do not look for `~/mbu` in this version. One `.deb` is the whole install.

## 7. Driving Ted’s scripts

No stdin puppet-show against interactive prompts. Use flags and library entry points MBU already has.

| UI action | Helper runs |
|---|---|
| Start Backup | `./mbup ask=n fselection=<comma list>` where the list is the checked functions, and includes `-bootfix` when boot-fix is on |
| Name live partitions | `sfdisk --part-label <disk> <partnum> <set>-<function>` (or equivalent GPT label write) only on the disk that contains `/` |
| Prepare backup disk | `./mbulib mbuFormatTableWrite` (or the documented table writer) then `./mbulib mbuFormatDisk fake=n disk=<dev> pset=<name> tablefile=<path>` |
| First backup after format | Same as Start Backup with **all** functions + boot-fix |
| Browse | `./mbumount <set>` (non-interactive specs) |
| Unmount | `./mbuclean` |

`ask=n`: if zero or several backup sets match, mbup must fail rather than prompt. The window already chose the target set when more than one is connected; pass that choice by only having one attached, or fail with “unplug the extra backup disk / plug the one you want” if MBU cannot be told a target without prompting. If we find a clean non-interactive way to pass `outset` without editing Ted’s scripts, use it; otherwise require a single connected backup set for v1.

Boot-fix checkbox default: on. Turning it off still syncs whatever functions are checked; the UI warns that the backup may not boot if root/boot/efi are synced without boot-fix (Ted’s warning).

## 8. Paths

| What | Where |
|---|---|
| Ted’s scripts | `/usr/share/mbu-gui/mbu/` |
| Window launcher | `/usr/bin/mbu-gui` |
| Helper | `/usr/lib/mbu-gui/mbu-gui-helper` |
| Desktop file | `/usr/share/applications/mbu-gui.desktop` |
| Icon | Ted’s `mbu-icon.png`, installed so the desktop file uses an absolute or themed name that actually resolves |
| PolicyKit | `/usr/share/polkit-1/actions/org.linuxbackupsoftware.mbu-gui.policy` |
| User state | `~/.local/share/mbu-gui/{log,out,mount}` for the user who launched the window |

When the helper runs as root via `pkexec`, it must write state in **that user’s** home, not `/root`. Use `PKEXEC_UID` (or the uid passed explicitly by the window) to resolve the home directory. Create `log`, `out`, and `mount` as needed.

Desktop file:

- `Type=Application`
- `Terminal=false`
- `Exec=/usr/bin/mbu-gui` (absolute)
- No `Path=mbu`
- `Icon=` must resolve (absolute path is acceptable)
- `Categories=System;`
- `Name=MBU Backup`
- `Comment=Bootable disk backup`

Clicking this file must start the window without PolicyKit. PolicyKit happens later, inside the app.

The `.deb` installs the menu entry. On first successful window start, if `~/Desktop/mbu-gui.desktop` does not exist, the app copies the same launcher there (Ted’s installer put an icon on the desktop; Winux users expect that). Do not fail the app if Desktop is missing.

## 9. User interface

One main window. Windows-familiar, Qt system style (Breeze / Winux theme). Ted’s yellow MBU icon. Not a terminal emulator.

### 9.1 Home

- Title: **MBU Backup**
- Status line in plain language, e.g. “Backup disk `bak1` is connected” or “Plug in the backup disk”
- Last successful backup from `mbu.log` (timestamp + from-set + to-set), or “No backup yet”
- Primary button: **Start Backup**
  - Disabled with an on-screen reason when: live partitions are not MBU-named; no backup set is connected; a run is already in progress
- Secondary actions: **Set up this computer** · **Prepare a backup disk** · **Browse a backup**
- Persistent log pane (latest run / current run)

### 9.2 Start Backup

1. User clicks **Start Backup**.
2. Window shows partition-function checkboxes from the live set; boot-fix checked by default.
3. Confirm starts `pkexec` helper `backup`.
4. Log pane shows helper/rsync output. Parse verbose rsync lines into a “current file” label when possible. A determinate byte percent is not required (Ted’s rsync line has no `--info=progress2`).
5. Success: large banner **Unplug the backup disk now.** Explain one sentence: duplicate UUIDs confuse Linux if you leave it plugged in.
6. Failure: error text stays visible; helper still tries `mbuclean`.

### 9.3 Set up this computer (live-disk names)

One-time GPT **names** on the disk that contains `/`. Not a format. Not a wipe.

Safeguards:

- Identify the block device that currently contains the `/` mount. Only that disk’s partitions are listed.
- Propose a set name default `main` (user can change). Letters and digits only; no hyphen or space.
- Propose functions from mount points and type: `/` → `root`, `/home` → `home`, `/boot` → `boot`, `/boot/efi` or vfat ESP → `efi`, swap → `swap`, `/tmp` → `tmp`, otherwise the mount-point basename or a typed name.
- Show a preview table: device, size, mount, current PARTLABEL, proposed `set-function`.
- User must type the set name to enable **Apply names**.
- Helper writes PARTLABELs with `sfdisk --part-label` only. Refuse if the target disk is not the current `/` disk.
- After apply, re-read `lsblk` and show the new names. Then return home.

If names already conform (`set-function` on the `/` disk), this screen says so and offers to leave them alone.

### 9.4 Prepare a backup disk

- List whole disks that are **not** the `/` disk. Show name, size, model, existing PARTLABELs if any.
- User picks exactly one disk in v1 (multi-disk sets stay CLI). Helper passes a single `disk=`.
- User enters a new set name (letters/digits, not already in use, not the live set name).
- Hard confirm: type the device name (e.g. `sdb`). Copy on screen: **This will erase the disk.**
- Helper writes a format table from the live set (`mbuFormatTableWrite`), then `mbuFormatDisk`.
- If the table will not fit, fail on screen (Ted already errors when partitions won’t fit). Do not silently shrink in v1.
- After success, offer **Copy everything now** (full `mbup` all functions + boot-fix). User can skip and return home.
- Success path ends with the unplug banner.

### 9.5 Browse a backup

- Choose a connected backup set (not the live set).
- Mount via helper into `~/.local/share/mbu-gui/mount/<partname>`.
- Open that directory with `xdg-open` (Dolphin on Winux).
- **Unmount** runs `mbuclean`. If it fails because something is using the mount, say so: close the file manager, `cd` away, try again. Do not tell the user to unplug until unmount succeeds.
- After unmount, unplug reminder.

### 9.6 Copy and errors

- No legal disclaimer screens.
- Operational copy only, as above.
- Every failure has a visible message in the window. No `except: pass`. If the helper exit code is non-zero and stdout is empty, still show “The backup command failed (exit N).”

## 10. Safety rules (product)

These are MBU’s rules, enforced in the UI/helper:

1. Never format/wipe the disk that contains `/`.
2. Never run two privileged MBU operations at once from this app (disable buttons while a helper process is running).
3. After a successful backup or format+sync, show unplug reminder until the backup disk disappears from `lsblk`.
4. After browse, unmount before unplug.
5. First backup of a newly formatted disk copies **all** functions + boot-fix (Ted: UUIDs and top-level permissions).
6. Partition set/function names: alphanumeric only, one hyphen between them, unique PARTLABELs among currently attached disks.

## 11. Packaging (`.deb`)

Target: Ubuntu 24.04 / Winux.

Depends at least:

- `python3`
- `python3-pyside6` (Qt Widgets)
- `policykit-1`
- MBU runtime tools Ted already needs: `rsync`, `gdisk`, `e2fsprogs`, `util-linux` (lsblk, sfdisk, mount), `coreutils`, `bash`

Build with `dpkg-deb` (or equivalent) from a `packaging/` tree in this repo. A Makefile target `deb` produces the artifact.

The package name: `mbu-gui`. It **includes** Ted’s scripts. Installing it is sufficient; the user does not unpack a tarball.

Dev run without installing: `python3 -m mbu_gui` from the repo, locating `vendor/mbu`. If the PolicyKit policy is not installed, the window still opens; privileged actions show how to install the `.deb` or, for developers, document `pkexec`/`sudo` fallback in the README only.

## 12. Source layout

```
LICENSE
README.md
docs/superpowers/specs/2026-08-31-mbu-gui-design.md
src/mbu_gui/          # window, lsblk parsing, helper client
src/mbu_gui_helper/   # privileged CLI
data/                 # .desktop, polkit policy, icon install bits
packaging/            # debian control, install paths
tests/                # pytest
vendor/mbu/           # Ted’s mbu-20251115 tree, unmodified
```

Language: Python 3.12 as on Ubuntu 24.04. Qt via PySide6. No extra UI framework.

## 13. Testing

CI/local tests do **not** wipe disks.

Must test:

- `lsblk --json` fixtures → live disk detection, set/function parse, backup-set detection, “backup disk connected” status
- Live-name proposals from mount points
- Helper argument building for `mbup ask=n fselection=...`
- Helper refuses format/wipe/label when the target is the `/` disk
- Log parser: last DONE line from `mbu.log`
- GUI with a fake helper: window opens; disabled Start Backup reason; cancelled pkexec message; success shows unplug banner; failure stays on screen

Manual on a VM (not required to automate in v1): full format + backup against a loop device or spare disk.

## 14. Success for Axel

1. Install the `.deb` on Winux.
2. Icon in the menu and on the desktop.
3. Click → window appears (no gnome-terminal).
4. If partitions are unnamed: Set up this computer → names applied → still booted.
5. Prepare a backup disk → disk formatted with matching functions.
6. Start Backup → password dialog → progress in the window → unplug reminder.
7. Browse → files visible in Dolphin → Unmount → unplug reminder.
8. Pull the Konsole out of the loop; if something fails, the window says what failed.

## 15. Open choice (resolved for v1)

If two backup disks are plugged in, v1 does not add a target-set picker inside `mbup`. The home status tells the user to leave only the disk they want to update connected. A picker can be a later change if we find a non-interactive `outset` path that does not patch Ted’s scripts.
