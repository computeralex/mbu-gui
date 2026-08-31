###############################################################################
#       MBU - Merrill Backup Utility
#       Backup system for Linux PCs
#       by Ted Merrill   updated 2025-11-15
###############################################################################

NOTE! Latest releases should now be found at:
https://codeberg.org/TedMerrill/mbu/releases/
https://linuxbackupsoftware.org


Updates
===============================================================================
2025-11-15  Very minor documentation changes
2025-01-08  Fixed bootability bug. Be sure to upgrade to this version.
2024-10-25  Minor GUI enhancements and documentation updates
2024-08-09  Fixed bug that affected systems with nvme ssds



Overview
===============================================================================
MBU is an efficient data backup utility for Linux, creating bootable disks.

The primary goal of MBU is to provide a means of periodically backing up 
your disks on a personal Linux computer, such that if at any time the main 
disk(s) become broken, corrupted, lost or even just temporarily left behind,
you can instantly switch to backup disk(s) and resume, losing only
the work done since the last backup.
Or individual files may be retrieved in a straight forward way.
In the event that the original disk(s) is available again, use of the
original disk(s) may resume after any important files have been brought 
over from the modified backup disk.

Secondary goals include having efficient (quick) routine operation,
being able to use differently sized disks,
use of multiple disks in a set instead of just one,
and requiring no reconfiguration of your system 
(EXCEPT see below about disk partition names).

MBU does NOT provide archival history, apart from you collection of disks
containing backups.

MBU is made easy to use by it's system of automatically matching source
partitions to backup partitions (based on partition names).

Backups are made efficient by copying only files that have changed (via rsync).

Backups are made bootable by taking care of a number of issues that would
derail bootability.

Creating new backup disks is made simple, provided the new disks are at least
as big as the old disk(s); other cases somewhat harder.

Restore of individual files is made simple by being able to quickly and
easily mount the backup partitions for comparison with current files using
normal file inspection and merge tools.

Limitations: 
Currently only supports Linux file systems.
Tested only on ext4, swap and efi file systems, may be broken for others.
Does not support obsolete/legacy boot methods (MBR etc.)
Tested only on Linux Mint, should work on Ubuntu and other Debian derived
distributions, and probably works on many other distributions.

My particular use case: 
I have two homes that I go back and forth between.
I have good, and more or less identical, desktop computers at both locations.
The computers have no internal disks; instead I carry back and forth
a USB3 SSD "disk" which I reboot at each location.
The performance of the USB3 SSD is perfectly adequate, rebooting and
logging in takes less than 30 seconds, and Firefox does a good job of
restoring my tabs to almost where they were.
I have multiple backup disks (actual hard drives because they are cheaper) at
each location, and I alternate my use of backup disks at each location.
When I forget my main SSD then I fire up the alternate backup disks to get by.
When I need to upgrade to a bigger disk, I create larger partitions on the
bigger disk, do a backup to it, and then use the new disk as my main one.


Who I am, Support, License and all that
===============================================================================
I, Ted Merrill, am the sole author of the MBU software, which is uncopyrighted.
You can do whatever you want with this software so long as you don't claim
ownership of what I wrote.

I am a retired software engineer who needed a project to work on in my spare 
time. I have tried to create this software using professional standards.
I use it for my personal use.

This software is unsupported. I'd love to hear your experience,
and I may respond to thoughtful questions or observations emailed to
software AT embuildsw.com



Terminology (so you understand the rest of this document):
===============================================================================
Disk -- a mass storage device, including "solid state disks".
Partition -- a section of a "disk" which may contain a filesystem.
File System -- a directory tree holding files, that lives in a partition.
    Typical Linux installation might use a different partition, and thus
    a different file system, for the root partition (starting at /)
    and for example the home partition (starting at /home).
Mounting -- getting Linux to actually use the file system in a partition.
    The file system tree that is mounted replaces (until unmounted)
    a directory in the main Linux directory tree (called a "mount point").
Partition Table -- when a disk is partitioned, some space at the front
    of the disk is reserved for a partition table which identifies where
    on the disk each partition lives, and attributes of each partition.
Partition Name -- an optional field in each partition table entry that
    holds human-readable text.
    Linux distributions such as Ubuntu normally leave these blank, but
    MBU has found a great use for them.
    Otherwise, MBU requires no change to your system other than installing
    the MBU software.
Partition Set and Partition Function --
    This is purely an MBU thing.
    MBU has you set partition names of the form:
        set-function
    (that is a hyphen in between two alphanumeric words we are calling
    here "set" and "function").
    "Set" is a name you share with all partitions on the same disk
    (but different from those on backup disks!) and "function" is some
    text that identifies the purpose of the partition for you, and
    which should match the "function" part of names on a backup disk.


Typical Use Cases
===============================================================================
NOTE: Be sure to read the rest of this document, and perform installation and
setting up backup disks, before following these use cases!

The following assume that you have installed MBU in $HOME/mbu and named your
partitions in an MBU compatible way.
Adjust the instructions if you have installed MBU elsewhere.

Routine Backup Case
---------------------
(1) Make sure your system is fairly quiet to reduce the chance of 
inconsistent backups.

(2) Attach your backup disk(s); give them maybe 10 seconds to be recognized.

(3) Open a terminal window ("maximized" is a good idea) and enter the commands:
    sudo bash
    cd mbu
    ./mbup
OR simply double click the MBU desktop icon, which will do the above for you.

(4) There will an interactive dialog to ask a few questions, which typically
you can accept default answers to by just pressing ENTER.

(5) Stick around, or come back later and see how it ended.
Look at the summary reports at the end and be aware of e.g. running short
of disk space (always a good idea).

(6) It is IMPORTANT to then disconnect your backup disk to prevent later system 
confusion (see below).


Booting Up a Backup Disk (Set)
------------------------------
(1) See below about finding the latest disk (set) if you have multiple.

(2) Power off the computer.

(3) Ensure that the original disk (set) is not connected and that the
backup disk (set) IS connected!

(4) Power on the computer.
It should boot up as usual, but usuing your backup disk.
If the backup is a hard drive, it will boot far far slower than an SSD,
but it will get there.

(5) If you make any changes that you want to propogate to the original
disk(s), you will have to manually propogate these.
See below about restoring files.


Finding the Latest or Best Backup Disk (Set)
--------------------------------------------
(1) Of course, you could keep a handwritten log.
And it is always a good idea to physically store your backup disks in the
order of recent usage.
Failing that...

(2) If you have your active disk (set), you should look in the mbu/log
directory for the file mbu.log.
At the end of this you should see which disk (set) was last used.
There are date stamps for every operation, so if you are looking for
older versions of file(s), this may help.

(3) If the active disk (set) is not available, you can examine backup partitions
from your various backup disk sets, looking for a file at the top of each
file system named
    .mbudatestamp
Inspect the content of the file to see that the operation succeeded or not,
and if so then the time printed in the file is useful.
Select the backup disk (set) with the best timestamp in the filesystem
of interest (should be representative of all the file systems in the set).


Restoring Files from a Backup Disk (Set)
----------------------------------------
(1) If not already done, boot up the original disk (set) ...
making sure the backup is disconnected!

(2) After booting up (if necessary), connect the backup disk (set)
and give it perhaps 10 seconds to be recognized.

(3) From a terminal window
    cd
    sudo bash
    cd mbu
    ./mbumount
Follow the prompts and let it finish.

(4) You will find partitions mounted beneath the "mount" subdirectory,
which you can browse using a file manager or a terminal window.

(5) Tools such as meld can also help identify and copy/merge the changes.

(6) Be SURE to terminate all such tools (including cd'ing away in the case
of terminal sessions) so that the backup partitions can be cleanly unmounted.

(7) Unmount all the partitions by cd'ing to your mbu directory 
and running:
    ./mbuclean

(8) After mbuclean succeeds, disconnect the backup disk(s) to prevent
system confusion.

Alternative: after connecting the disk, you may be able to use a file manager
to do everything.


New Backup Disk 
-------------------------------------
The mbuformat program makes creating a new backup disk simple.

(1) If not already done, boot up the original disk (set) 
(making sure the backup is disconnected!)

(2) Before attaching the new disks, use the command
    lsblk
and observe what is connected to the system.

(3) Now connect the new disks.  Use the command
    lsblk
to see what has changed and to deduce what the device name is for your new disk.
It might for example be "sdb" or "sdc".
(It can take 10 seconds or more for a new disk to be recognized,
so try lsblk again if you don't see it yet).

(4) cd to your mbu directory and run
    sudo bash   # if necessary
    ./mbuformat
You will see questions labelled "MBUFORMAT" to which you must respond.

(5) mbuformat will ask for the path to a custom formatting table file; 
just press ENTER the first time (or every time if you prefer)
and it will generate a formatting table file for you.

(6) The formatting table file includes the important parameters including
partition size, but is not specific to a particular disk.
If your new disk(s) is the same size or larger than the active disk(s) you
will not need to modify the file, though you might want to.
You can modify the table file from a separate window before continuing, or
stop mbuformat and then start it again later and tell it your modified table.
See the section on formatting below for more information.

(7) mbuformat will ask you for the new backup disk device name, 
which you determined early using lsblk: for example, sdb or sdc.
For a multi-disk set, give the device names in the desired order to match
your formatting table file.

(8) mbuformat will also ask for a new partition set name.
Make sure it is one that you have not used before.
Partition set names should contain only letters and digits and certainly
never hyphens or spaces.

(9) After you tell mbuformat to continue, it will format using the
formatting table file, 
and your new disk(s) will be formatted but otherwise empty.

(10) mbuformat will then ask if you want to run ./mbup to copy files and
make the new disk bootable.
You can tell it to, or you can stop and later run ./mbup yourself,
perhaps with options you prefer better.
IMPORTANT: It is important to have mbup sync ALL your partitions
at least one time, so that file system UUIDs and permissions are properly set.
After that you can sync only ones you care about.

(11) Your new backup disk is now ready for all uses.

Alternative: You may be able to use a GUI disk formatting program.
You will have to enter each partition name and size individually, 
You will still need to run mbup at least once.


Optimized and Customized Routine Backup Cases
-----------------------------------------------
You can write your very own backup script in two lines that will avoid
having to interactively answer questions at all, for example,
assuming you have partitions named myset-root, myset-tmp and myset-home:
    #!/bin/bash
    cd $HOME/mbu && exec ./mbup ask=m fselection=-bootfix,root,tmp,home

You can modify $HOME/Desktop/mbu.desktop to do the following or to
invoke your custom script.


Customizing the Software
-------------------------
Most of the heavy lifting is done in mbulib (and qlib).
You can write your own customized backup software using mbulib,
provided you gain some comfort in bash scripting.

You can start with the custom script generated by mbup.
To see what mbup will do without actually doing it, run
    ./mbup scriptonly
mbup will tell you where you left the script.
You might copy the script to another location and 
modify your copy as you desire.

You can write a simple two line script to totally automate your experience,
barring unexpected errors of course:
#!/bin/bash
./mbup ask=m fselection=-bootfix,root,home,local

You might find qlib useful for totally unrelated projects.


Background
===============================================================================
A filesystem is a block of storage that holds a self-contained respository
of data in a directory tree.
In the Linux world, a filesystem lives on a "block device" that the Linux
kernel manages... a block of storage.
In the PC world, disks may be used in their entirety as block devices,
but are more commonly partitioned into sub-blocks, each of which is
a block device in it's own right, capable of holding a filesystem.
These sub-blocks are called "partitions".
This is a system introduced by Microsoft and used by Linux as well.
Unsurprisingly, there is space at the front of the disk reserved for
describing the partitioning (this is called the disk partition table);
there is also space at the end of the disk.
In ancient times, the partioning scheme used was called MBR, but
this has almost entirely been supplanted by a new scheme called GPT/UEFI.
If you happen to have an MBR formatted disk, you must upgrade it to GPT;
MBU works only with GPT partitioned disks.
Note that GPT requires the existence of dedicated "EFI" partition, 
specifically for getting your computer booted.
Also, MBU may only work for modern computers that boot using the UEFI
specification.

In a pure GPT/UEFI scheme (required by MBU, and will be present on PCs
unless you have a really old one), the first and last sectors of a disk
are reserved for recording the partition layout.
Partitions live in the remaining disk space.
One of the partitions must be an EFI partition.
The EFI partition contains a standard FAT32 file system,
and that must contain all needed boot code.
The firmware in your computer knows how to read the boot files in the EFI
partition and use them to boot up the computer.
The Linux GRUB software (that came with your linux distribution) 
installs such boot files, as well as other files that it will need, 
into the EFI partition.
None of these files have any knowledge of what type or size of disk they
reside on, or how the disk is partitioned.
(The files do depend on the CPU instruction set e.g. x86-64).

In the GPT scheme, each partition has a number of properties listed in
the partition table, such as the start and size of each partition,
and also including a human readable string called the partition label,
or as I prefer to call it, the partition name.
It seems that partition names are (usually?) unused (left blank in fact) in 
Linux and Microsoft distributions.
This leaves them free for use for our own purposes!
[Do not confuse partition names with for example file system labels,
which are part of the filesystem in a partition.]

One of the big concerns of MBU is to produce backup disks that are fully
bootable by themself.
This turns out to be rather involved, which springs from the very 
messy nature of the boot process.
Here are some of the issues:
(1) The computer firmware handles selecting a disk to boot, and
reading files from the EFI partition on that disk.
(2) The "EFI" partition in turn needs to know about specific files in
what will become /boot/grub. 
(3) Grub needs to use what will become /boot, including the Linux
kernel file ...  it needs to know what disk and partition to use.
It also needs to know what root partition to pass to Linux (does
not have to be the same one as /boot).
Disks do not come with unique identifiers (at least not commonly)
and are typically identified by the order that they are encountered,
which is problematic if you have more than one disk.
The solution has been adopted by the industry to identify disk partitions
containing file systems by a file system UUID... a random number
that serves as a kind of serial number for each file system.
(4) Once Linux starts running, it has only a root partition, and must
find all other file systems using /etc/fstab .
The commonly accepted method is to identify the partition based on it's
file system UUID.

From the above, you can see that an exact bit for bit copy of a disk 
to another disk should boot just as well as the original disk.
However, making an exact copy has a number of shortcomings:
(1) The disk must be entirely quiescent (to avoid inconsistencies),
meaning in practice you would have to reboot and run the backup when
booted from another disk... ugh.
(2) Copying an entire disk takes a lot of time.

MBU does not make an exact copy. Instead it attempts to ensure that
the same partitions, WITH THE SAME UUIDs, are present, and that the
files in the partitions are kept the same... but not exactly in the same
locations.

To make backups in a reasonable time, we want just to copy things that have
changed, and to sync some things for bootability.
This is what MBU does for backups:

(1) The rsync program is guided by file modification times, it quickly 
determines what files appear to have changed, and copies just those.

(2) rsync does not reliably copy over the permissions of the top level
directory of a filesystem. That must be added to the process.
This is particulary important for e.g. /tmp.

(3) For bootability (see above) the filesystem UUID of the backup filesystem
must agree with the active filesystem. MBU adds this.

(4) For bootability, at a minimum the root, efi and (optional) boot partitions
must be synced to the backup. Enabling "boot fix" does that.

MBU also does a variety of other chores in the path of reaching it's goals.
In order to copy files, the file systems need to be mounted to some
specific location; then unmounted when no longer needed  (to avoid possible
loss of data).

Be aware of the following possible issues:

(1) Your system software can get confused if there are multiple 
partitions connected which have the same UUID.
In particular this can happen during initial bootup, or when upgrading
your software.
To be safe, attach your backup disks only for the minimum required time,
while your computer is relatively quiescent.

(2) Although rsync takes some precautions, there is still the possibility
of data inconsistency in the backup. 
Inconsistency is when matching changes are required to multiple files, 
but not all of the changed files make it on to the backup.
To be safe, do backups only while your computer is relatively quiescent.



Overview of Requirements
===============================================================================
The MBU software is written assuming the following:

(1) You have multiple physical disks (multiple disk sets if using more than
one disk per instance) with one disk (disk set) to be active, and
additional disks (disk sets) for backup instances.
(It is recommend you physically label the disks with a marker!)
The backup disks must be hot pluggable and easily attached and detached.
You will need appropriate cabling and possibly adapters.
(Actual hard drives typically require a externally powered adapter).

(2) Backup disks must be big enough, and partitioned big enough, to hold
the files being backed up.
A backup disk CAN be smaller than the active disk, if you are not
using all of the active disk and are willing to push your luck :~)

(3) Disks MUST be set up for GPT booting (NOT the obsolete MBR method),
which includes having an EFI partition.
This is typical for a personal Linux installation, unless you have
something quite old (which can be converted if you have space for EFI).
(And very old computers might not support GPT/UEFI).

(4) You use a typical Linux distribution (only Ubuntu and Linux Mint tested).
This is mostly important for bootability fixing, which assumes using the
GRUB bootloader and grub-install program.

(5) Only fully supported for ext4 and efi file systems, and swap partitions.
This covers all partitions for a typical personal Linux installation.
It may or may not work for other file system types (untested).

(6) Partitions must be labelled in a certain way (see below).
This can be done on your active disk(s) while installing your 
linux distribution.  See below.

(7) You install the MBU software in a single directory of your choosing
(typically just by unpacking the distribution archive file, which
will create a directory called "mbu")... all files including
software, configuration, temporary and log files are created therein.
Operate the MBU software only while cd'd to that directory.
A good choice is to unpack the software in your home directory, and
then you will find the mbu subdirectory.

(8) The MBU software must be run as superuser, e.g. run:  sudo bash
It must also run from the mbu directory, e.g.: cd mbu


Overview of Warnings and Limitations
===============================================================================
IMPORTANT: Note the following:
(1) The following have not been tested and may not work:
-- Support for filesystem types other than ext4, swap and EFI.
-- Support for Linux distributions other than Ubuntu and Linux Mint.
-- Proper behavior in the presence of unnamed partitions.
-- Proper behavior in the presence of partitions with insane name.

 2) Do backups when the system is as quiet as possible.
MBU software is not suitable for systems that are continually generating
important multi-part data, as the data files saved may be inconsistent.
Files that change during a backup may cause the backup to abort,
which you should be able to recover from by simply restarting the backup.
In my experience, this rarely or never happens, especially since
automatic retries are used which should mostly obviate the problem.

(3) MBU software sets the file system labels in the file systems in the
backup partitions to be identical to the source file system.
While this helps is important for bootability, it can 
potentially cause a lot of confusion, so beware...  see next warning...

(4) You should be sure to turn off or disconnect the backup disk(s) when
not needed, to avoid confusion during software updates or when rebooting.
Do not reboot without disconnecting the backup disk(s) unless
you mean to possibly boot them, in which case you would disconnect
the original disk(s).

(5) If you are inspecting the backup files (see mbumount), be sure to
close programs inspecting the files, and to cd away from the mount 
directories, and then use ./mbuclean to remove the mounts.
Otherwise temporarily mounted file systems may remain
mounted, which can cause issues.
If you have used ./mbumount, be sure to run ./mbuclean later.
Do NOT disconnect backup disk without first doing this.

(6) MBU software rewrites the boot blocks / EFI partition using
grub-install provided by your linux distribution, which in turn uses
may other files provided by your operating system.
You may possibly need to run update-grub first before running MBU
software (make SURE that the backup disk(s) are disconnected).
Probably you don't need to worry about this, however.

(7) Boot fixing only works when syncing the active set.

(8) Do not run multiple instances of MBU software at the same time from the
same directory. You might run multiple instances if each is from a separate
directory, and if they don't try to access the same disks.

(9) Making a disk bootable is a fragile thing.
Changes to the way linux distributions work may make this break.
If the backup disk does not boot, you may be able to use boot-repair,
see e.g. https://help.ubuntu.com/community/Boot-Repair ... 
or similar utility.


Installation of MBU
===============================================================================
MBU may be installed before or after setting partition names.

MBU is distributed as a compressed tar (tgz) archive file.
Download this tgz file to somewhere on your computer.

For a re-installation (for example to upgrade to a newer version),
see the next section.

Bring up a terminal window.
It is recommended to expand the archive file directly into your home directory:
    cd
    tar xzvf pathtoarchivefile.tgz
where you replace "pathtoarchivefile" with the path to the archive file.
This will create the directory "mbu" beneath your home directory.
If you wish, you can now delete the archive (.tgz) file.

[You can put it somewhere else or rename it etc. Everything will still work
except that the Desktop launch icon won't work unless you modify mbu.desktop].

To install the desktop launch icon:
    cd
    cd mbu
    ./mbu-install

Please note that all MBU commands should be executed from a terminal shell
after cd'ing to the mbu directory!

Within the mbu directory you will find the following files:

mbu-install
mbu.desktop
mbu-icon.ping
-- These are all associated with the optional desktop launch icon

mbulib -- the basic software library, used by following programs.
    This is a bash script that is sourced by other bash scripts such as mbup.

qlib -- an even more basic software library.

qtemplate -- an example file to use as a starting point if you want to write
    your own scripts.

mbup -- command line program to perform backups

mbuformat -- format new backup disks

mbumount -- temporarily mount backup disks, allowing inspection of
    the files therein.

mbuclean -- unmount temporarily mounted backup disks.
    Do this BEFORE disconnecting backup disks if mbup has failed
    or if you have done mbumount.

mbuwipe -- effectively wipe content from disk partitions or drives.

also, various documentation files and examples

The following will be created automatically within the "mbu" directory
when MBU software is run.
You may remove them at any time (when not running MBU software) if you
desire.

mount -- directory containing mount points where mbu will mount partitions.
    Created as required.
    Do NOT place anything else in this directory as it will confuse MBU.

log -- directory where log files will be placed.
    Must exist (provided in the installation).
    Logs will be recreated as required.

out -- automatically generated scripts and tables are placed here.
    Created as required.


Upgrading MBU
===============================================================================
When a new version of MBU comes along, you may want to upgrade.
There are two ways of doing this.
You could do a new installation, e.g.:
    cd
    mv mbu mbu.old
    tar xzvf pathtoarchivefile.tgz
    cd mbu
    ./mbu-install
However this would lose useful history.
So recommended instead is the following:
    cd
    cp -a mbu mbu.old
    tar xzvf pathtoarchivefile.tgz
    cd mbu
    ./mbu-install
This will overwrite the distributed files while leaving your history.
After you are comfortable with your upgraded installation, 
you might delete mbu.old .


Partition Labelling Requirement
===============================================================================
MBU avoids reconfiguration of your system, with one simple exception.
MBU strives to make backup disks almost identical to the active disk(s),
but there has to be some way to tell them apart!
The solution is use of disk partition names (aka labels).
Fortunately, disk partition names are generally unused by other software.
Note that partition names are contained in the GPT boot blocks, NOT
in the partitions themselves! ... you can safely rewrite partitions
without changing the partition names, and vice versa.
Do not confuse partition names with file system labels, or with the various
uuid fields.

MBU expects a certain uniform scheme of labelling of partitions.

For each disk (or disk set), pick a set name that will be the first
part of partition names for that disk.
For example, I currently have the partition set name of "tm30" for my
active disk, and "tm31", "tm32", tm33" etc. for my backup disks.
The partition name root should consists only of letters and digits,
and certainly not spaces or hyphens.
The partition names on your disk (disk set) should then be created
by you by appending a simple descriptive text to the first part (set name)
with a hyphen in between.
This descriptive text is referred to as the "partition function".
The partition function should also be alphanumeric.
For example, on my active disk "tm30" I have an EFI partition named tm30-efi,
two linux root partitions named tm30-root1 and tm30-root2, a partition 
for /tmp labelled tm30-tmp, a swap partition named tm30-swap, and so on.
The partition functions are "roo1", "root2", "tmp" and "swap" respectively.
On my backup disk "tm31" I have corresponding tm31-efi, tm31-root1, tm31-root2,
tm31-tmp, tm31-swap etc.

To recap: The first part of the partition name (up to the hyphen) identifes
the disk (set) and this I call the partition set.
The second part identifies it's function (partition function).
The two are combined, with a hyphen in between, as the partition name.
And the partition name is stored in the partition table of the disk,
for each partition.

There are a variety of ways to set the partition names.

When installing a Linux distribution from scratch, there will be an option
for customized installation, which will take you into the disk formatting
tool (typically gparted).
This has options for partitioning, and crucially for us this includes
setting the partition names.

Should you not get it right during installation, NO WORRY!
Identify the running partition using lsblk (typically sda).
Assuming it is sda (check!) run:
    sudo gdisk /dev/sda
gdisk does nothing to the disk until you use the w command (see below).
At the gdisk prompt, enter
    h
for help, and 
    p
to print the partition table... just for your information.
For each partition to rename, enter 
    c
and then (unless there is only one partition) you will be prompted
to enter the partition number, and then again to enter the new name.
After repeating for all the partition names to be changed,
review your changes with
    p
and modify any as desired with the c command.
Use the command to write the changes to the disk:
    w
So long as you have not changed anything else, everything should
be good and your changes committed.
The "w" command also will cause gdisk to exit when done.
It may take a while to write the changes, even though they are small.

Following using gdisk, check there results with e.g.
    lsblk -o +PARTLABEL
In theory you might need to run partprobe or reboot to see the changes,
although I haven't found that to be true.
Sometimes it can take the operating system some seconds to see changes.

Alternately if you want, you can run gparted (as root) 
and operate on the backup disk(s) without any big hassle...
although if you wanted to modify the active disks, you would
have to do so from e.g. a rescue disk.

Fortunately, you do not need to go to this trouble for new backup disks!
See below about using mbuformat.

Note: You should only need to do partitioning labelling once for each disk,
unless you need to reformat the disk for some other reason  or change your
naming scheme.


Using mbuformat to Format Backup Disks
===============================================================================
(1) With the new disk(s) unattached, enter the command (as root):
    lsblk
and note what is there.

(2) Attach the new disk(s) and enter the command:
    lsblk
until you see the addition has been recognized; remember the added
device name (e.g. sdc).
Also, compare the sizes of the disks to help ensure sufficient space.

(3) From the mbu directory you can just run
    sudo bash
    cd $HOME/mbu
    ./mbuformat
and follow the prompts.
You can tell it to use a custom formatting table file (see below)
or have it automatically generate one (which you can modify, see below).
This will make a complete logical copy of the disk format 
(including creating empty file systems) and then
offer to do a backup to it using ./mbp (which you should accept).

(4) Exception: see below about partition customization.

Partition customization:
If your new backup disk(s) is smaller than the active disk(s),
or if you want to expand the size of your partitions in the process,
or spread out into multiple disks, or similar issues:
Stop mbuformat after generating a partition table file,
copy the partition table file to a different filename,
manually edit the file, then continue running mbuformat
(or run mbuformat again) and tell it to use the modified file.
The partition table file begins with comments that are intended
to explain how to use the file.
It is recommended to copy file it created to a safe place of yours,
named with a name you will understand, before modifying it.

CAUTION: mbuformat might not properly create file systems with
types other than those it has been tested on, which is mainly ext4.

CAUTION: there is vast confusion about whether, for example,
a kilobyte is 1000 bytes or 1024 bytes,
a megabyte is 1,000,000 bytes or 1024*1024 = 1,048,576 bytes,
or whether a gigabyte is 1,000,000,000 byes or
1024^3 = 1,073,741,824 bytes.
When we get to terrabytes, the difference is almost ten percent.
MBU (and gdisk) use the 1024^n forms, for good reason.
Disk storage is always precisely a multiple of 1024.
And assuming that disks were partitioned in multiples of M (1024^2)
then no loss of precision occurs if we use M
And the number of M is still (at this writing) small enough to be easily
humanly readable; 1 T is 1048576 M for example.

Even if everyone is using 1024^n forms, care must be taken when translating
between different forms.
For example, df reports in K (1024); if it reports 746628032 (that is in K)
you need to divide by 1024 to get slightly less than 729129M.


Other Disk Formatting Options besides MBU
===============================================================================
I do not recommend using gdisk for a total reformatting of a disk.
Use one of the graphical utilities instead.
Many or all of these support setting partition names.
Note that a repartitioned disk is incomplete as it does not yet have
filesystems installed (or worse, has old filesystems still in place).



Support for Multiple Disk per Set
===============================================================================
If you have multiple disks per set, make sure that one disk is primary and
contains the most essential file systems: efi partition, root file system,
/boot (if separate; usually part of root).
This may be required for booting to go well.

mbuformat handles multiple disks in one shot.


Programs used by MBU
===============================================================================
Programming language:
    bash, sed
System information:
    lsblk, df
File tools:
    rsync, rm, rmdir, mkdir, cp, chmod
File system tools:
    mount, umount
    mkfs.* e2fsck tune2fs
Formatting a disk:
    gdisk, wipefs
Fixing bootability
    grub-install
For desktop launch icon:
    gnome-terminal


Links
===============================================================================
Webpage: https://linuxbackupsoftware.org
Introductory video: https://youtu.be/OTsUQm7LFSQ
Download from: https://codeberg.org/TedMerrill/mbu/releases/
Download from (OLD versions only): https://sourceforge.net/projects/mbu/

# MBU Release mbu-20251115
