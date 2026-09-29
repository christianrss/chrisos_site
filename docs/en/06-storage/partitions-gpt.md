---
id: partitions-gpt
lang: en
type: technical-chapter
volume: 06-storage
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/fs/part.h
  - kernel/fs/part.c
  - kernel/fs/install.c
  - kernel/fs/storage.c
  - kernel/fs/block_device.h
  - kernel/fs/bdev.h
  - kernel/fs/bdev.c
  - kernel/fs/storage_limits.h
  - tools/check_install_img.py
  - scripts/qemu.mk
symbols:
  - PartView
  - gpt_find_cfs
  - part_open
  - part_read
  - part_write
  - install_device
  - write_gpt_backup
  - crc32
  - gpt_crc
  - discover_root
  - check_install_img.py
depends_on:
  - block-storage
  - ata
  - ahci
  - nvme
  - virtio-block
  - usb-storage
related:
  - chrisfs
  - uefi
  - installation-real-hardware
  - resource-lifetime
---

# Partition tables and GPT

## Scope

ChrisOS uses GPT in two different directions:

1. **boot-time discovery**: read a disk's primary GPT and locate a partition suitable for ChrisFS;
2. **installation**: destructively create a protective MBR, primary GPT, backup GPT, EFI System Partition and ChrisFS partition.

The implementation is intentionally compact. It supports the GPT structures needed by the current installer and root-discovery path rather than a general partition-management subsystem.

The reader accepts ChrisOS's dedicated ChrisFS type GUID and, for backward compatibility, the standard Linux filesystem-data type GUID. The installer writes a dedicated ChrisFS type GUID and a standard EFI System Partition type GUID.

This chapter documents ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

![ChrisOS GPT discovery and installation path](../../assets/diagrams/partitions-gpt-en.svg)

## Why a partition view exists

Storage drivers expose whole disks through `BlockDevice`. Filesystems, however, may live inside a bounded LBA range.

ChrisOS solves this with `PartView`:

~~~c
typedef struct PartView {
    BlockDevice *parent;
    uint32_t start;
    uint32_t count;
    BlockDevice dev;
} PartView;
~~~

A partition view is not a separate hardware device. It is an address-translation layer:

~~~text
partition LBA x
    -> parent LBA start + x
~~~

Its `BlockDevice` inherits:

- sector size 512;
- logical sector count equal to the partition length;
- writable flag from the parent.

Read and write operations forward directly to the parent driver's function pointers after adding the partition start offset.

## Partition-range enforcement

`part_open` rejects:

- null output pointer;
- null parent;
- zero length;
- start outside the parent disk.

If the requested partition extends past the end of the parent, ChrisOS clamps its length:

~~~text
count = parent.sector_count - start
~~~

Normal callers then use generic `bd_read`/`bd_write` on the partition `BlockDevice`, so relative-LBA bounds are checked before `part_read` or `part_write` translates them.

The partition adapter itself does not add another bounds check. Its safety therefore depends on callers using the generic block helpers rather than invoking the function pointers directly with unchecked coordinates.

## Flush semantics

The partition view currently sets:

~~~text
flush = 0
~~~

instead of forwarding the parent's flush callback.

That means partitioning can discard persistence semantics even if a future parent block device implements an explicit flush operation.

Today many ChrisOS storage backends also have `flush = 0`, so the limitation is mostly architectural rather than a regression on the current validated paths.

## GPT basics used by ChrisOS

With 512-byte sectors, the installer writes the standard layout:

~~~text
LBA 0                  protective MBR
LBA 1                  primary GPT header
LBA 2..33              primary partition-entry array
...
LBA N-33..N-2          backup partition-entry array
LBA N-1                backup GPT header
~~~

The entry array is configured as:

~~~text
128 entries × 128 bytes = 16384 bytes = 32 sectors
~~~

The GPT header size written by the installer is 92 bytes, revision 1.0.

## Protective MBR

The installer writes a legacy MBR sector at LBA 0.

Important fields include:

~~~text
partition type = 0xEE
start LBA      = 1
length         = disk sectors - 1
signature      = 0x55AA
~~~

The protective entry prevents GPT disks from looking unpartitioned to MBR-only tools.

The ChrisOS GPT reader does not validate the protective MBR during boot discovery. It reads the primary GPT header directly from LBA 1.

The host-side installation checker does validate the protective MBR signature and `0xEE` partition type.

## GPT type GUIDs

ChrisOS defines a dedicated ChrisFS partition type:

~~~text
43524653-3100-4000-8000-000000000001
~~~

The on-disk byte sequence stored in GPT mixed-endian form is:

~~~text
53 46 52 43 00 31 00 40 80 00 00 00 00 00 00 01
~~~

The boot-time reader accepts either this GUID or the Linux filesystem-data GUID:

~~~text
0FC63DAF-8483-4772-8E79-3D69D8477DE4
~~~

The Linux GUID is retained so older ChrisOS installer images can still mount.

This compatibility behavior means type GUID matching alone does not prove that a partition actually contains ChrisFS. Root discovery later validates the ChrisFS superblock before claiming the partition.

## Primary GPT discovery

`gpt_find_cfs` reads sector 1 and first validates the signature:

~~~text
EFI PART
~~~

If the signature does not match exactly, the disk is not accepted as GPT by this function.

The reader then copies the first 92 bytes into a temporary buffer, clears bytes 16 through 19, computes CRC-32 and compares it against the stored header CRC.

The CRC polynomial is the usual reflected CRC-32 polynomial:

~~~text
0xEDB88320
~~~

with initial state `0xFFFFFFFF` and final bitwise complement.

## Header fields consumed

After CRC validation, the reader extracts only the fields required to locate entries:

- partition-entry-array starting LBA at byte 72;
- number of entries at byte 80;
- entry size at byte 84.

It requires:

~~~text
entry_array_lba != 0
entry_array_lba <= 0xFFFFFFFF
entry_size >= 128
entry_count >= 1
~~~

The number of entries is capped at 128.

The current reader does **not** validate many other GPT header fields, including:

- revision;
- header-size field;
- current-LBA field;
- backup-LBA field;
- first/last usable LBA;
- disk GUID;
- partition-entry-array CRC;
- header location consistency with LBA 1.

The hardcoded CRC calculation over 92 bytes also assumes the expected GPT header size rather than honoring the header's own size field.

## Partition-entry scanning

For each entry, ChrisOS computes:

~~~text
offset = (index * entry_size) % 512
sector = entry_array_lba + (index * entry_size) / 512
~~~

When `offset == 0`, it reads that sector into a 512-byte buffer.

It then compares the first 16 bytes of the entry against the accepted type GUIDs.

For the canonical 128-byte GPT entries written by ChrisOS, four entries fit exactly in each sector and the algorithm works as intended.

### Entry-size boundary limitation

The reader accepts any `entry_size >= 128`, but its buffering logic assumes the fields it reads remain inside the currently loaded 512-byte sector.

It does not reject entry sizes that cause an entry to straddle a sector boundary.

A standards-compliant but unusual GPT using a larger or non-divisor entry size could therefore make the parser read past the logical entry bytes available in the buffer.

The installer itself always writes 128-byte entries, so the project's generated images stay within the safe path.

## Entry fields consumed

For a matching partition type, ChrisOS reads:

~~~text
first LBA  at entry + 32
last LBA   at entry + 40
~~~

Both are 64-bit little-endian values.

A candidate is rejected when:

~~~text
start == 0
start > end
end > 0xFFFFFFFF
~~~

The block interface is still 32-bit, so GPT's full 64-bit addressing range is not exposed.

The resulting partition length is:

~~~text
end - start + 1
~~~

and returned as a 32-bit sector count.

## What is not inspected in an entry

The reader does not use:

- unique partition GUID;
- attributes;
- UTF-16 partition name.

It stops at the first acceptable type GUID.

There is no API to enumerate all partitions, search by partition name or expose multiple GPT child devices.

Current GPT support is therefore root-discovery oriented rather than a general partition manager.

## Root-discovery order

`discover_root` searches in three phases.

### Phase 1 — whole-disk ChrisFS

For every non-RAM block device, ChrisOS first checks whether sector 0 directly decodes as a ChrisFS superblock.

If so, the whole disk becomes root.

### Phase 2 — GPT ChrisFS partition

If no whole-disk root is found, ChrisOS calls `gpt_find_cfs`.

For a matching entry it opens a `PartView`, then validates that the partition's sector 0 contains a valid ChrisFS superblock.

Only after that second check does it claim the physical disk index as the boot/root device while using the partition view as `g_disk`.

### Phase 3 — blank writable disk

If neither form exists, the code may format a sufficiently large zeroed writable whole disk.

This ordering preserves compatibility with both early whole-disk ChrisFS images and newer GPT installs.

## Why GUID matching is followed by filesystem validation

The reader deliberately accepts both ChrisFS and Linux filesystem-data type GUIDs.

That would be unsafe if the GUID alone selected root.

Instead, ChrisOS creates a partition view and runs:

~~~text
disk_has_cfs(partition)
~~~

which calls the ChrisFS superblock decoder.

Thus an arbitrary Linux filesystem partition with the accepted Linux type GUID does not become root unless its first sector actually matches ChrisFS metadata.

## Installer partition geometry

`install_device` creates two GPT entries.

### Partition 1 — EFI System Partition

Type GUID:

~~~text
C12A7328-F81F-11D2-BA4B-00A0C93EC93B
~~~

Start:

~~~text
LBA 2048
~~~

Size depends on disk capacity:

~~~text
16384 sectors   on smaller disks
65536 sectors   when disk sectors > 200000
~~~

At 512 bytes per sector these correspond to 8 MiB and 32 MiB.

The ESP is formatted as FAT16 by the installer and receives the EFI bootloader, kernel and Limine configuration.

### Partition 2 — ChrisFS

Start:

~~~text
2048 + ESP sectors
~~~

End:

~~~text
disk sectors - 34
~~~

This leaves the final 33 sectors for the backup GPT entry array plus backup header.

## Alignment

The ESP begins at LBA 2048:

~~~text
2048 × 512 = 1 MiB
~~~

This gives conventional 1-MiB alignment.

The ChrisFS partition begins immediately after the ESP. Because both configured ESP sizes are multiples of 2048 sectors, ChrisFS is also 1-MiB aligned.

## Minimum target size

The installer refuses a disk smaller than:

~~~text
2048
+ ESP sectors
+ STOR_DISK_SECTORS
+ 64
~~~

where:

~~~text
STOR_DISK_SECTORS = 1048576
~~~

The fixed ChrisFS geometry therefore remains central to install sizing.

The extra tail margin also ensures room for backup GPT structures.

## Partition-entry array generation

The installer allocates a static:

~~~text
128 × 128 byte
~~~

entry array.

Only entries 0 and 1 are populated.

Entry 0 receives:

- EFI System Partition type GUID;
- a minimal unique GUID with first byte 1;
- ESP start/end LBAs.

Entry 1 receives:

- ChrisFS type GUID;
- a minimal unique GUID with first byte 2;
- ChrisFS start/end LBAs.

The remaining 126 entries remain zero.

### Unique GUID quality

The current per-partition unique GUIDs are not randomly or globally generated. Only one byte is set for each.

The disk GUID is similarly minimal: the installer sets byte 56 of the header to `0x43` and leaves the remaining GUID bytes zero.

These fields are structurally nonzero enough for the project's own images, but they do not provide globally unique identifiers as GPT intends.

## Partition-entry-array CRC

The installer computes CRC-32 over all:

~~~text
16384 bytes
~~~

of the primary entry array and stores it at header offset 88.

This is correct for its configured 128 entries × 128 bytes.

The boot-time GPT reader currently does **not** verify this CRC.

The host-side installation checker also currently focuses on header CRC and selected structural fields rather than verifying the entry-array CRC.

## Primary GPT header

The installer writes:

~~~text
signature             "EFI PART"
revision              0x00010000
header size           92
current LBA           1
backup LBA            sectors - 1
first usable LBA      34
last usable LBA       sectors - 34
entry-array LBA       2
entry count           128
entry size            128
entry-array CRC       computed CRC32
~~~

It then computes the header CRC with the header-CRC field zeroed.

## Backup GPT generation

`write_gpt_backup` copies the 32 primary entry-array sectors:

~~~text
LBA 2..33
~~~

to:

~~~text
LBA sectors-33 .. sectors-2
~~~

It reads the primary header, then changes:

~~~text
current LBA      = sectors - 1
backup LBA       = 1
entry-array LBA  = sectors - 33
~~~

The header CRC field is zeroed and recalculated.

The resulting header is written to the last sector.

The entry-array CRC remains valid because the copied backup entries are byte-for-byte identical to the primary array.

## Installation failure model

GPT creation is destructive.

Before installation, `install_disk` requires the target to be considered installable by the block registry.

Automatic install also requires an explicit target name and prints:

~~~text
WARNING: ALL DATA ON THIS DISK WILL BE LOST
~~~

The installer does not implement a transaction or rollback journal for partition-table creation.

A failure after writing LBA 0, the primary entry array or primary header can therefore leave a partially rewritten disk.

The backup GPT is written before the ESP and ChrisFS formatting, which improves metadata redundancy once that stage succeeds, but does not make installation atomic.

## Write ordering

The main order is:

~~~text
protective MBR
-> primary partition entries
-> primary GPT header
-> backup partition entries/header
-> ESP format and boot files
-> ChrisFS format
-> optional system-tree copy
-> filesystem sync
~~~

There is no explicit block-device flush between GPT metadata stages because the current block abstraction generally lacks durable flush semantics.

Therefore crash consistency during installation is weaker than the logical order suggests.

## Backup GPT in discovery

Although the installer writes a backup GPT and the checker validates its signature/header CRC, `gpt_find_cfs` does not fall back to it.

If the primary header at LBA 1 is corrupted, ChrisOS root discovery fails even when the backup GPT at the end of disk is intact.

Recovery from backup GPT is therefore a roadmap item, not current behavior.

## CRC behavior

Both `part.c` and `install.c` implement the same reflected CRC-32 algorithm independently.

The host checker uses Python's `zlib.crc32`.

The duplicated C implementations currently agree with the generated images, but centralizing the algorithm would reduce drift risk.

Complexity is linear in the number of bytes hashed:

~~~text
O(header bytes + partition-entry bytes)
~~~

For the fixed installer layout this is tiny.

## 32-bit block-layer boundary

GPT supports 64-bit LBAs, but ChrisOS's `BlockDevice` uses 32-bit:

~~~text
uint32_t lba
uint32_t sector_count
~~~

The reader explicitly rejects partition end LBAs above `0xFFFFFFFF`.

The installer also receives its disk size from a 32-bit `sector_count`.

At 512 bytes per sector, the practical addressing ceiling is about 2 TiB.

Full GPT-scale disks require a future 64-bit block ABI.

## Validation evidence

The most important integration gate is `test-qemu-install`.

It:

1. prepares a source ChrisOS disk;
2. creates a 560-MiB blank AHCI target;
3. requests automatic installation to the `ahci` device;
4. requires logs including:
   - `install auto`;
   - `install tree copied`;
   - `install gpt+esp+cfs disk=ahci`;
5. runs `tools/check_install_img.py` on the resulting image;
6. boots the installed target again through OVMF;
7. requires `cfs mounted` and `desktop 60Hz`.

The host checker validates:

- protective MBR signature/type;
- primary GPT signature;
- primary header CRC;
- backup GPT signature;
- backup header CRC;
- ChrisFS type GUID in the second entry;
- ChrisFS superblock at the entry's start LBA;
- presence of required ESP directory data.

There is also an in-kernel RAM-disk installer self-test that verifies GPT creation and selected ESP content.

## Current limitations

At the documented revision, GPT support is limited to:

- primary-GPT discovery only;
- no backup-GPT fallback during boot;
- no MBR partition parsing;
- no hybrid-MBR support;
- at most 128 scanned GPT entries;
- first matching ChrisFS/Linux-data type only;
- no general partition enumeration API;
- no partition names;
- no attribute handling;
- no unique-GUID lookup;
- no validation of GPT revision;
- no validation of header-size field;
- header CRC hardcoded over 92 bytes;
- no validation of current/backup LBA relationships;
- no validation of first/last usable LBA;
- no validation of disk GUID;
- no partition-entry-array CRC verification in the reader;
- incomplete handling of unusual entry sizes crossing 512-byte sectors;
- 32-bit LBA and sector-count limits;
- partition views do not forward parent flush;
- no hotplug-aware partition lifetime;
- installer GUIDs are not globally unique;
- installation is destructive and non-transactional;
- no explicit durable flush barriers between metadata stages.

## Roadmap boundary

A fuller partition subsystem should provide 64-bit LBAs, generic partition enumeration, strict GPT-header validation, partition-entry-array CRC validation, safe handling of arbitrary valid entry sizes, backup-GPT recovery, names/attributes/unique GUIDs, protective-MBR validation, optional MBR compatibility, flush propagation and installation recovery.

The installer should also generate real random or deterministic-unique disk and partition GUIDs and use durable write barriers when storage backends expose them.

Those capabilities remain future work until implemented and covered by tests.

## Source map and revision note

`kernel/fs/part.c` implements GPT lookup and the bounded partition view. `kernel/fs/part.h` defines `PartView`. `kernel/fs/storage.c` uses GPT discovery during root selection. `kernel/fs/install.c` writes the protective MBR, primary and backup GPTs, ESP and ChrisFS partition. `tools/check_install_img.py` validates generated install images. `scripts/qemu.mk` provides the full install-and-reboot integration gate.

All current-behavior claims in this chapter were reconciled against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.
