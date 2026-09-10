# Test VM setup

A throwaway VM for exercising MBU GUI without risking a real disk. The VM has
to be built a specific way, because MBU cannot back up an arbitrary Linux
install.

## Why the firmware choice matters

MBU finds partitions by their **GPT partition name** (`<set>-root`,
`<set>-efi`, and so on) and makes the clone bootable by copying a real EFI
system partition.

An MBR (msdos) partition table has no name field at all — a partition entry is
16 bytes of type byte and LBA numbers. `sfdisk --part-label` against an MBR
disk rewrites the table, reports success, and silently discards the name. A
legacy-BIOS install also has no EFI partition to copy.

So a BIOS/MBR VM can never be an MBU source. The app now detects this and says
so instead of looping through "Set up this computer", but the only fix is to
install in UEFI mode. **Pick UEFI when the VM is created; it cannot practically
be switched afterwards.**

## Host packages

```bash
sudo apt install qemu-kvm libvirt-daemon-system virt-manager ovmf
```

`ovmf` supplies the UEFI firmware for guests. Without it, virt-manager offers
no UEFI option and you will end up with BIOS/MBR again.

## Creating the VM

In virt-manager, tick **Customize configuration before install** on the last
page of the wizard, then set Overview → **Firmware** to `UEFI x86_64`. Leave
Secure Boot off; it adds nothing here and complicates booting a clone.

Or with `virt-install`, which is less easy to get wrong:

```bash
virt-install \
  --name winux-test \
  --boot uefi \
  --memory 4096 --vcpus 2 \
  --disk path=/var/lib/libvirt/images/winux-system.qcow2,size=40,serial=WINUXLIVE01 \
  --disk path=/var/lib/libvirt/images/winux-backup.qcow2,size=40,serial=MBUBACKUP01 \
  --cdrom /path/to/ubuntu-24.04-desktop-amd64.iso \
  --os-variant ubuntu24.04
```

Two disks, both 40G. The second one is the backup target. Let the installer
partition the first disk automatically — in UEFI mode it produces GPT with an
ESP, which is what MBU needs.

## Disk serials are required

Formatting refuses any disk that reports no persistent hardware id, because a
kernel name like `sdb` is reassigned on replug and must never be the only thing
identifying a disk about to be erased. Virtio disks report no serial unless you
set one, so set one per disk.

With `virt-install`, `serial=` above does it. For an existing VM, add to each
`<disk>` in `virsh edit <vm>`:

```xml
<serial>MBUBACKUP01</serial>
```

Verify inside the guest — every disk you intend to use must show a SERIAL,
a WWN, or a PTUUID:

```bash
lsblk -o NAME,SERIAL,WWN,PTUUID
```

## Confirming the VM is usable before you start

```bash
# Must print gpt for the system disk, not dos.
lsblk -dno NAME,PTTYPE

# Must list an EFI partition, normally vfat at /boot/efi.
lsblk -o NAME,FSTYPE,SIZE,MOUNTPOINT
```

A system disk reporting `dos` means the installer ran in BIOS mode. Rebuild
with UEFI rather than trying to convert it.

The confirmation code the format page asks you to type is the last 8 characters
of the disk's hardware id, so a serial of `MBUBACKUP01` yields a code of
`UBACKUP01`. Setting readable serials makes the wipe confirmation easier to
check.

## Installing the app in the guest

```bash
git clone https://github.com/computeralex/mbu-gui.git
cd mbu-gui && git checkout v0.1.0-alpha.1
cd packaging && make deb
sudo dpkg -i ./mbu-gui_0.1.0~alpha1_all.deb
pip3 install --break-system-packages PySide6
```

PySide6 is not packaged for Ubuntu 24.04, so it is not an apt dependency.

Use `dpkg -i` rather than `apt install ./...` when reinstalling the same
upstream version. `dpkg -i` always unpacks what you hand it.

Close and reopen the GUI after installing; a running instance keeps the old
Python modules loaded.

## Things worth testing that only a VM makes safe

Snapshot the VM before each of these so you can rewind.

- Prepare the backup disk, then back up, and confirm the clone boots when the
  system disk is detached.
- Yank the backup disk mid-copy (detach it in virt-manager) and confirm the
  warning about possibly-cloned UUIDs survives a restart of the app.
- Boot with **both** disks attached after a successful backup. The firmware may
  land on the clone; the app must refuse to back up and report the set
  mismatch, rather than copying the clone over the real system disk. This is
  the most important test in the list and the hardest to do safely on metal.
- Re-select a disk, detach and reattach a different one to shift the kernel
  names, then confirm the format still refuses the stale code.
