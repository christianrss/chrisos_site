---
id: installation-real-hardware
lang: en
type: technical-chapter
volume: 13-real-hardware
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/fs/install.c
  - kernel/fs/install.h
  - kernel/fs/bdev.c
  - kernel/fs/bdev.h
  - kernel/fs/storage.c
  - kernel/fs/storage_limits.h
  - kernel/fs/cfs_format.h
  - kernel/metal/bootinfo.c
  - kernel/lang/clvm_sys.c
  - SYS/DRV/INSTALL.CC
  - scripts/qemu.mk
  - tools/check_install_img.py
  - iso_root/boot/limine/limine.conf
symbols:
  - install_disk
  - install_auto
  - install_selftest
  - install_device
  - write_gpt_backup
  - write_esp
  - bd_installable
  - storage_init
depends_on:
  - block-storage
  - power-on-kstart
related:
  - gpt-esp
  - uefi-disk-boot
  - hardware-profile
  - bringup-diagnostics
  - driver-compatibility
  - validation-evidence
---

# Installation and real hardware

## Scope

ChrisOS has a real destructive disk installer and a QEMU gate that proves a disk produced by that installer can boot through UEFI.

That is stronger than a design sketch, but it is not yet equivalent to a supported physical-hardware installer.

The current implementation should be understood as:

- an x86-64 UEFI disk installer;
- operating on ChrisOS block devices;
- requiring a source ChrisFS system tree;
- writing a new GPT, EFI System Partition, and ChrisFS partition;
- validated end-to-end under QEMU with OVMF;
- not yet validated as a generally safe installer for arbitrary physical disks.

The difference matters because installation is one of the few ChrisOS operations that intentionally destroys existing storage state.

## Destructive operation boundary

`install_disk(index)` accepts only a block-device slot that passes `bd_installable`.

The target must:

- exist;
- be writable;
- not be marked boot, root, or test;
- not be RAM;
- not be a partition view.

If accepted, the installer rewrites sector zero, GPT metadata, the EFI System Partition, and the ChrisFS region.

There is no in-place installation mode and no partition-preserving mode.

All previous partitioning and filesystem data on the selected target must be considered destroyed.

## Block-device registry

ChrisOS has a global block-device registry with:

```text
BD_SLOTS = 8
```

Device kinds include:

```text
ATA
AHCI
NVMe
VirtIO
USB
RAM
partition
other
```

The installer operates through the common `BlockDevice` read/write interface rather than directly through controller-specific code.

That is a useful architectural boundary: GPT, FAT16, and ChrisFS formatting do not need separate implementations for ATA, AHCI, or NVMe.

## Current installable storage paths

At boot, `storage_init` probes:

- legacy ATA/IDE;
- AHCI;
- NVMe;
- VirtIO block;
- USB mass storage.

Writable devices from these paths may become install targets if they are not already the root/boot device.

This list describes implemented software paths, not a hardware compatibility guarantee.

Each driver has narrower assumptions than the generic device category suggests.

## 512-byte-sector requirement

The storage stack and installer are built around:

```text
512-byte sectors
```

CFS explicitly rejects a different sector size.

The NVMe driver accepts a namespace only when its LBA data size is 2^9 bytes, also 512 bytes.

Therefore native 4 KiB logical-sector devices are not currently an installation target.

## Addressable disk size

The common `BlockDevice.sector_count` is 32-bit.

ATA, AHCI, and NVMe paths also reject device capacities whose sector count requires high 32-bit words.

At 512 bytes per sector, the practical addressing ceiling is approximately 2 TiB.

A larger physical drive may be unsupported or exposed only if a controller reports a compatible reduced range; it must not be assumed safe.

## PCI discovery limitations

AHCI and NVMe probes scan PCI buses 0 through 7, devices 0 through 31, and functions 0 through 7.

That covers common QEMU and simple PC topologies, but it is not full recursive PCIe bridge enumeration.

Hardware located behind a topology not visible through that scan may not be discovered.

The physical-hardware profile must therefore record actual controller discovery, not merely the nominal controller type.

## Minimum target size

The installer requires room for:

- 2048 sectors before the ESP;
- the ESP;
- at least `STOR_DISK_SECTORS = 1,048,576` sectors for the ChrisFS requirement used by the installer check;
- final GPT structures and guard sectors.

For any disk large enough to pass the minimum, the code selects the larger ESP:

```text
ESP = 65,536 sectors = 32 MiB
```

The resulting minimum is:

```text
1,116,224 sectors
545.03125 MiB
```

The QEMU integration target is 560 MiB and therefore clears this boundary.

## Why the smaller ESP branch is effectively unreachable

The code initially defines a 16,384-sector ESP for disks of at most 200,000 sectors and switches to 65,536 sectors above that.

However, the minimum CFS/storage requirement already requires a disk far larger than 200,000 sectors.

Thus every successful installation in the present implementation uses the 65,536-sector ESP path.

The smaller ESP branch exists in source but is not reachable for a valid current install.

## On-disk layout

The resulting disk is:

```text
LBA 0             protective MBR
LBA 1             primary GPT header
LBA 2..33         primary GPT entries
LBA 2048..        EFI System Partition
after ESP         ChrisFS partition
last 33 sectors   backup GPT entries + header
```

The primary GPT table contains 128 entries of 128 bytes each.

Only the first two partition entries are populated.

## Partition 1: EFI System Partition

Partition one uses the standard EFI System Partition type GUID.

It starts at:

```text
LBA 2048
```

and, for a valid current install, spans 65,536 sectors.

The installer formats this partition itself as FAT16.

It does not call firmware, mtools, mkfs.fat, or a host utility.

## Partition 2: ChrisFS

The second partition starts immediately after the ESP:

```text
cfs_lba = 2048 + esp_sectors
```

and extends through:

```text
disk_sectors - 34
```

The installer opens that range through a partition view and calls `cfs_format`.

CFS v5 computes geometry from the partition's actual sector count, so the filesystem is no longer fixed to exactly 512 MiB.

## Protective MBR

Sector zero contains a protective MBR entry of type:

```text
0xEE
```

covering the disk after LBA zero, clamped to the 32-bit MBR length field.

The MBR contains no ChrisOS legacy BIOS bootstrap code.

That fact is important for hardware expectations.

## UEFI-only installed disk

The ISO build supports BIOS and UEFI because the ISO is post-processed with Limine's BIOS installer.

The physical disk installer does not perform an equivalent BIOS installation.

It creates a GPT/ESP and places:

```text
EFI/BOOT/BOOTX64.EFI
```

on the ESP.

Therefore the disk produced by the current installer should be considered an **x86-64 UEFI boot disk**, not a legacy-BIOS-installed disk.

## Secure Boot

No Secure Boot signing path, shim integration, enrolled key workflow, or signed ChrisOS EFI chain is present in the inspected repository.

The current UEFI validation uses OVMF without establishing a Secure Boot chain.

Physical systems should therefore be expected to require Secure Boot disabled unless a separately validated signing path is added.

## GPT construction

The installer writes:

- GPT signature;
- revision 1.0;
- 92-byte header;
- primary and backup LBAs;
- usable range;
- 128 entries × 128 bytes;
- partition-entry CRC32;
- header CRC32.

The backup entry array is copied near the end of the disk and the backup header is rewritten with its own current/alternate LBAs and entry-table location.

This is substantially more complete than writing only a primary GPT.

## Fixed GPT identifiers

The disk GUID and partition unique-GUID fields are constructed from fixed byte patterns in the installer.

They are not generated randomly per installation.

As a result, multiple ChrisOS-installed disks can carry duplicate GPT identities.

That is acceptable for the current controlled test images but is undesirable for general physical deployment, especially when several ChrisOS disks are attached simultaneously.

## FAT16 ESP implementation

The ESP is generated manually.

Important parameters include:

```text
512 bytes/sector
4 sectors/cluster
2 FAT copies
512 root-directory entries
FAT16
```

The filesystem uses 2 KiB clusters.

The FAT table is held in a fixed 16,384-entry in-memory array.

The current 32 MiB ESP remains within that implementation envelope.

## ESP boot files

Before destructive installation starts, `require_boot_files` requires these source files to exist in the running filesystem:

```text
BOOT/KERNEL.ELF
EFI/BOOT/BOOTX64.EFI
BOOT/LIMINE.CFG
```

Each must be non-empty and no larger than 8 MiB.

The installer then places their contents in the ESP as:

```text
/EFI/BOOT/BOOTX64.EFI
/BOOT/KERNEL.ELF
/BOOT/LIMINE/limine.conf
```

The configuration source name and installed ESP path are therefore not identical.

## Limine configuration

The current installed configuration contains:

```text
/ChrisOS
    protocol: limine
    path: boot():/boot/kernel.elf
    resolution: 1920x1080x32
```

Limine is still an external bootloader.

ChrisOS relies on Limine protocol revision 3 for framebuffer, memory map, HHDM, multiprocessor information, and command-line data.

Replacing the bootloader is not required for kernel self-hosting, but the bootloader remains part of the physical compatibility boundary.

## Framebuffer requirement

Early boot requires Limine to provide a framebuffer.

ChrisOS rejects boot when no framebuffer is returned or when:

```text
bpp != 32
```

The requested configuration asks for 1920×1080×32.

Physical firmware does not have to expose that exact mode, but a usable 32-bpp Limine framebuffer must ultimately be supplied.

There is no text-only fallback for a missing framebuffer in the inspected boot path.

## Source system requirement

The installer is not currently a conventional "boot the ISO and install to the only disk" workflow.

`storage_init` runs before `install_auto`.

The system first needs a root filesystem, and the installer copies the source tree from the currently mounted ChrisFS.

The QEMU gate provides a separate:

```text
install-src.img
```

containing the system tree and boot payload.

That source disk becomes the running root while a second blank AHCI disk becomes the target.

A physical installation workflow therefore needs an equivalent source ChrisFS environment, not only the ISO.

## Tree copied into ChrisFS

When `copy_os` is enabled, the installer recursively copies:

```text
SYS
APPS
LIB
GAMES
BOOT
SRC
BIN
```

from the running root into the newly formatted target CFS partition.

The ESP is populated separately.

The `EFI` directory is not copied into target ChrisFS because its required EFI payload has already been written into the ESP.

## Automatic installation markers

The automated path is enabled by:

```text
BOOT/INSTALL.AUTO
```

It also requires:

```text
BOOT/INSTALL.TARGET
```

whose first token must exactly equal an installable block-device name.

If no target name is present, the installer prints the available names and sector counts and refuses to install.

If more than one installable device has the same requested name, it refuses the ambiguous selection.

## Dry-run marker

When:

```text
BOOT/INSTALL.DRY
```

exists, the automatic path identifies the target and prints the selection but does not call the destructive installer.

This is the safest current path for checking automatic target resolution.

It does not provide a full GPT layout preview or hash of the intended source payload.

## Device names are not physical identities

Current block-device names are generic strings such as:

```text
ata
ahci
nvme
virtio-blk
usb
```

They are not model numbers, serial numbers, PCI paths, or WWNs.

Therefore exact string selection is still weaker than selecting a uniquely identified physical drive.

A production-grade physical installer should display and verify immutable device identity plus capacity.

## Graphical installer path

`SYS/DRV/INSTALL.CC` provides an application-level installer UI.

It lists disk kinds and marks devices whose flags indicate system use.

Its prompt says:

```text
keys 1-9 pick target
```

but the current code directly handles only three numeric selections and calls `disk_install(index)`.

That syscall requires the CLVM `CAP_DISK_ADMIN` capability.

## Graphical installer safety gap

The graphical path does not present:

- model;
- serial;
- capacity;
- partition preview;
- destructive confirmation dialog;
- dry-run step.

A key press can reach `install_disk` directly.

`bd_installable` still protects root/boot/test devices, but that is not sufficient for arbitrary multi-disk physical systems.

This UI should remain experimental.

## Temporary write before explicit installation

During normal `storage_init`, ChrisOS calls `bdev_rw_tests`.

For each writable, non-root, non-RAM disk, it:

1. reads the last sector;
2. writes a test pattern;
3. reads it back;
4. attempts to restore the original sector.

This occurs before `install_auto`.

On a GPT disk, the last sector normally contains the backup GPT header.

Although the implementation restores the saved sector, a power failure, controller error, or failed restore during this test could damage existing metadata.

For physical-hardware safety, destructive or temporary-write probing should not occur on unapproved disks.

## Automatic formatting during root discovery

Root discovery also has a write path before the explicit installer.

If ChrisOS cannot find an existing CFS root, it searches writable non-RAM devices.

When a candidate is large enough and the first eight bytes of sector zero are all zero, `storage_format_if_empty` may format it as CFS and claim it as root.

This is convenient for controlled blank test disks but means "blank device discovery" is not strictly read-only.

A physical live environment should disable this behavior unless explicitly requested.

## Installation self-test

`install_selftest` builds a RAM-backed fake block device and executes the installer without copying the full OS tree.

It checks at least:

- install success;
- primary GPT signature;
- an ESP directory sector.

This provides cheap boot-time structural coverage of installer logic.

It is not a substitute for persistent-media validation.

## Host-side image checker

After QEMU installation, `tools/check_install_img.py` verifies:

- protective MBR signature/type;
- primary GPT signature and CRC;
- backup GPT signature and CRC;
- ChrisFS partition type GUID;
- ChrisFS superblock at the declared start LBA;
- ESP directory presence for BOOTX64.EFI;
- ESP kernel entry;
- `limine.conf` long filename.

This gives independent host-side structural validation of the produced image.

## QEMU installation gate

`make test-qemu-install` performs an end-to-end integration sequence.

It:

1. clones a source ChrisFS image;
2. inserts kernel, BOOTX64.EFI, Limine config, and automatic-install markers;
3. creates a fresh 560 MiB target;
4. attaches that target through QEMU AHCI;
5. waits for installation log markers;
6. runs the host image checker;
7. starts a second QEMU instance with OVMF;
8. boots using the installed disk;
9. requires `cfs mounted` and `desktop 60Hz`.

This is meaningful evidence.

## Evidence classification

The current state can be classified as:

```text
installer algorithms       host/QEMU validated
GPT + FAT16 + CFS layout   host checked
disk-only UEFI boot        QEMU + OVMF validated
physical AHCI install      not established
physical NVMe install      not established
physical USB install       not established
legacy BIOS disk boot      not implemented by installer
Secure Boot                not established
```

The phrase "real-hardware installer" should therefore describe the intended target domain, not a completed compatibility claim.

## Required physical-hardware gate

Before installation on a real machine is treated as supported, the project should record:

1. motherboard/system model;
2. firmware vendor/version;
3. UEFI mode and Secure Boot state;
4. target controller PCI identity;
5. target disk model, serial, sector size, and capacity;
6. discovery logs before any write;
7. dry-run target identity;
8. installation logs;
9. post-install GPT/ESP inspection from an independent OS;
10. cold reboot from the installed disk;
11. ChrisOS build/hash identity after boot;
12. repeated read/write and clean reboot results.

A successful one-off boot is evidence, but it is not yet a hardware support matrix.

## Immediate safety priorities

Before routine physical use, the highest-value changes are:

1. remove write probes from unapproved disks;
2. disable automatic blank-disk formatting in physical/live mode;
3. expose model/serial/capacity and stable device identity;
4. add a second destructive confirmation step;
5. make dry-run show exact GPT ranges and copied artifacts;
6. generate unique GPT disk/partition GUIDs;
7. verify copied ESP file contents after writing;
8. verify the target GPT/ESP/CFS before reporting completion;
9. provide rollback/recovery guidance;
10. create explicit physical-hardware gates per controller class.

## Revision note

This chapter was reconciled against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. The current installer is a real GPT/FAT16/CFS x86-64 UEFI installer with a successful QEMU+OVMF disk-only boot gate. It should not yet be treated as a generally safe physical installer because device identity is weak and normal storage initialization can write to non-root disks before explicit installation approval.
