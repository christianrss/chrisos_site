---
id: gpt-esp
lang: en
type: technical-chapter
volume: 13-real-hardware
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/fs/install.c
  - kernel/fs/part.c
  - kernel/fs/part.h
  - kernel/fs/cfs_format.h
  - kernel/fs/storage_limits.h
  - tools/check_install_img.py
  - scripts/qemu.mk
  - iso_root/boot/limine/limine.conf
symbols:
  - write_gpt_backup
  - write_esp
  - gpt_find_cfs
  - part_open
depends_on:
  - installation-real-hardware
related:
  - uefi-disk-boot
  - block-storage
  - validation-evidence
---

# GPT and EFI System Partition

## Scope

The ChrisOS installer constructs its partition table and EFI System Partition directly in kernel code.

There is no call to a generic GPT library, `sgdisk`, `parted`, `mkfs.fat`, or firmware formatting service.

The implementation therefore owns every on-disk byte required for:

- protective MBR;
- primary GPT header;
- primary GPT entry array;
- backup GPT entry array;
- backup GPT header;
- EFI System Partition FAT16 structures;
- UEFI fallback loader path;
- Limine configuration and kernel placement.

This chapter documents that exact format and the parser used later to rediscover ChrisFS.

## Disk geometry assumptions

All offsets are expressed in 512-byte logical sectors.

The block-device interface exposes sector count as a 32-bit value.

The installer therefore builds GPT using 32-bit-addressable media even though GPT fields are 64-bit on disk.

The current storage drivers also reject capacities that exceed their 32-bit sector-count model.

## Protective MBR

LBA zero is zeroed and then populated with one protective partition entry.

The important fields are:

```text
partition type = 0xEE
start LBA      = 1
length         = sectors - 1
signature      = 0x55AA
```

The length is saturated to `0xFFFFFFFF` if necessary.

No active flag is set.

No BIOS bootstrap program is installed into the MBR.

Its purpose is partition-protection compatibility, not legacy boot.

## Primary GPT entry array

The installer reserves:

```text
128 entries
128 bytes per entry
16,384 bytes total
32 sectors
```

beginning at:

```text
LBA 2
```

The entire array is held in `g_entries`, zeroed, then the first two entries are filled.

Unused entries remain zero.

## Partition alignment

The GPT header declares first usable LBA 34, but the ESP begins at:

```text
LBA 2048
```

This creates a conventional 1 MiB alignment for the first partition.

The gap between GPT entries and the ESP is intentionally left unused.

The ChrisFS partition begins immediately after the ESP, whose length is itself a multiple of 2048 sectors, so the second partition remains 1 MiB aligned as well.

## Partition 1 type

The first entry uses the standard EFI System Partition GUID in GPT on-disk byte order.

Its range is:

```text
start = 2048
end   = 2048 + esp_sectors - 1
```

For all currently valid installations:

```text
esp_sectors = 65536
```

which is exactly 32 MiB.

## Partition 2 type

The second entry uses a ChrisOS-specific partition type GUID:

```text
43524653-3100-4000-8000-000000000001
```

The bytes are stored in GPT's mixed-endian on-disk representation.

This GUID identifies the ChrisFS partition.

The installed range is:

```text
start = 2048 + esp_sectors
end   = disk_sectors - 34
```

The final 33 sectors remain available for backup GPT entries and header.

## Compatibility with older images

The GPT parser in `part.c` accepts two partition type GUIDs when searching for ChrisFS:

- the ChrisOS-specific GUID;
- the standard Linux filesystem data GUID.

The second is retained so older installer images can still mount.

New installations use the ChrisOS GUID.

## Partition unique GUIDs

The installer writes only simple fixed values into the unique-GUID fields:

```text
partition 1 -> low distinguishing byte 1
partition 2 -> low distinguishing byte 2
```

The rest is zero.

These values are not generated uniquely per disk.

That means the "unique partition GUID" property of GPT is not actually satisfied across installations.

## Disk GUID

The primary GPT header's disk GUID is also constructed as a fixed pattern rather than generated per installation.

Multiple disks installed by ChrisOS may therefore share the same disk GUID.

This is safe enough for isolated QEMU test disks but can create ambiguity in tooling or firmware environments that expect globally unique identifiers.

## Primary GPT header

The primary header is written to:

```text
LBA 1
```

with:

```text
signature            "EFI PART"
revision             0x00010000
header size          92 bytes
current LBA          1
backup LBA           last sector
first usable LBA     34
last usable LBA      sectors - 34
entry-array LBA      2
entry count          128
entry size           128
```

The partition-entry CRC32 is written into the header.

The header CRC32 is then computed with its own CRC field zero.

## GPT CRC implementation

ChrisOS uses the standard reflected CRC32 polynomial:

```text
0xEDB88320
```

initialized with all ones and complemented at the end.

The same algorithm is independently reproduced in `tools/check_install_img.py` using Python's `zlib.crc32`.

This gives a useful independent check of the on-disk header.

## Backup entry array

The installer copies the complete 32-sector primary entry array from LBAs 2..33 to:

```text
sectors - 33
through
sectors - 2
```

The entries are copied byte-for-byte.

Because partition entries contain absolute start/end LBAs, no transformation is required for the backup copy.

## Backup header

The primary header is read into a temporary buffer and adapted.

The backup header sets:

```text
current LBA      = sectors - 1
alternate LBA    = 1
entry-array LBA  = sectors - 33
```

Its CRC field is cleared and recomputed.

The completed backup header is written to the final sector.

## Backup GPT is not used for recovery at runtime

Although the installer correctly emits a backup header and entry table, `gpt_find_cfs` reads only the primary header at LBA 1.

If the primary GPT is damaged but the backup GPT is intact, ChrisOS does not currently attempt recovery from the final sector.

A future parser should fall back to the backup copy and verify that the two views are mutually consistent.

## What the host checker verifies

After the QEMU installation gate, `check_install_img.py` verifies:

- protective MBR signature;
- protective type `0xEE`;
- primary GPT signature;
- primary GPT header CRC;
- backup GPT signature;
- backup GPT header CRC;
- ChrisFS type GUID in partition entry 2;
- ChrisFS superblock at the declared LBA.

This is a useful independent parser.

## What the checker does not yet verify

The current checker does not validate:

- GPT partition-entry CRC against the entry array;
- primary/backup entry-array equivalence;
- primary/backup usable-range consistency;
- unique GUID properties;
- partition overlap;
- ESP FAT consistency;
- file contents/hashes.

The image can pass the current checker while still containing some classes of structural errors.

## Runtime GPT parser

`gpt_find_cfs` is the kernel-side parser used during root discovery.

It reads the primary GPT header at LBA 1 and requires:

```text
"EFI PART"
```

It then copies the first 92 header bytes, zeros the CRC field, and validates the header CRC.

This protects the root-discovery path from accepting an obviously damaged primary header.

## Runtime entry-array CRC gap

The GPT header contains a CRC for the entire partition-entry array.

The installer writes that value.

However, `gpt_find_cfs` does not currently read the declared array and validate its CRC before trusting individual entries.

A corrupted ChrisFS entry can therefore be considered if the primary header itself still has a valid CRC.

This is an important integrity gap in runtime partition discovery.

## Parser entry limits

The parser obtains:

- entry-array LBA;
- entry count;
- entry size

from the GPT header.

It accepts entry sizes of at least 128 bytes and caps the entry count at 128.

The entry-array start LBA must fit in 32 bits.

This reflects the storage layer's 32-bit sector model.

## Entry scanning

For each entry, the parser computes the sector and offset from:

```text
index * entry_size
```

It loads a new 512-byte sector whenever the entry offset returns to zero.

For the standard 128-byte entry size, four entries fit exactly in one sector.

It then compares the type GUID with the ChrisFS and compatibility Linux GUIDs.

## Parser limitation for unusual entry sizes

The implementation holds only one 512-byte sector in `ent`.

If an entry size causes a single GPT entry to cross a 512-byte sector boundary, the current pointer arithmetic does not assemble the entry from multiple sectors.

The installed format always uses 128-byte entries, so this does not affect ChrisOS-generated disks.

It does mean `gpt_find_cfs` is not a fully general GPT parser.

## Partition LBA validation

For a matching partition, the parser requires:

```text
start != 0
start <= end
end <= 0xFFFFFFFF
```

It returns:

```text
lba   = start
count = end - start + 1
```

The parser does not itself require `end` to be below the actual parent-device sector count.

## Partition clipping behavior

`part_open` rejects a start beyond the parent device but clips an oversized count to the remaining sectors.

That makes partition views robust against one class of overlong range, but it also means malformed GPT metadata can be silently truncated rather than rejected as inconsistent.

For a hardware-grade parser, GPT geometry should be validated before constructing the partition view.

## Partition view

`part_open` creates a synthetic `BlockDevice`.

Reads and writes are translated as:

```text
parent_lba = partition_start + local_lba
```

The partition view always reports 512-byte sectors.

This is how ChrisFS is mounted without teaching the filesystem about GPT offsets.

## ESP filesystem type

The installer formats the ESP as FAT16.

The BPB contains:

```text
bytes/sector      512
sectors/cluster   4
reserved sectors  1
FAT copies        2
root entries      512
media byte        0xF8
hidden sectors    esp_lba
filesystem label  FAT16
```

The volume label is:

```text
CHRISOS ESP
```

## FAT size

The sectors-per-FAT value depends on the selected ESP branch.

For the effective current 32 MiB ESP:

```text
sectors per FAT = 64
```

The implementation holds the FAT in:

```text
uint16_t g_fat[16384]
```

Each entry represents one FAT16 cluster.

## Root directory

FAT16 uses a fixed root-directory region rather than a cluster chain.

The installer reserves:

```text
512 entries * 32 bytes
= 16384 bytes
= 32 sectors
```

for the root directory.

The root contains directory entries for:

```text
EFI
BOOT
```

## Data-region start

The installer computes:

```text
root = 1 + 2 * sectors_per_fat
data = root + 32
```

relative to the ESP start.

Cluster 2 maps to the first 2 KiB data cluster.

The cluster-to-sector translation is:

```text
esp_lba + data + (cluster - 2) * 4
```

## Reserved directory clusters

The implementation reserves:

```text
cluster 2 -> /EFI
cluster 3 -> /EFI/BOOT
cluster 4 -> /BOOT
cluster 5 -> /BOOT/LIMINE
```

Their FAT entries are marked end-of-chain.

File allocation begins at cluster 6.

## EFI loader path

The UEFI fallback loader is installed at:

```text
/EFI/BOOT/BOOTX64.EFI
```

This is the standard x86-64 removable/default UEFI path.

It allows firmware to boot the disk without requiring a pre-created NVRAM boot entry.

## Kernel path

The kernel is installed at:

```text
/BOOT/KERNEL.ELF
```

using the short 8.3 directory name:

```text
KERNEL  ELF
```

The Limine config refers to it case-insensitively as:

```text
boot():/boot/kernel.elf
```

## Limine configuration path

The source file in ChrisFS is:

```text
BOOT/LIMINE.CFG
```

Inside the ESP it becomes:

```text
/BOOT/LIMINE/limine.conf
```

The installer creates:

- one long-file-name directory entry for `limine.conf`;
- the corresponding 8.3 entry `LIMINE  CFG`.

## FAT LFN implementation

The long-name helper writes one LFN entry with sequence value:

```text
0x41
```

which means one final LFN fragment.

This is enough for `limine.conf`, which fits inside a single 13-character FAT LFN slot.

The code is not a general arbitrary-length LFN writer.

## File allocation

Files are copied in 2 KiB chunks, exactly one cluster at a time.

The FAT entry for each cluster points to the next cluster, and the final cluster receives:

```text
0xFFFF
```

The file's directory entry stores the first cluster and original byte size.

Unused bytes in the last cluster are zero-filled.

## File-size ceiling

`require_boot_files` rejects any required boot file larger than:

```text
8 MiB
```

The cluster allocator also refuses to grow beyond approximately 16,000 cluster indexes.

These checks protect the fixed FAT array and current ESP implementation.

They also impose a practical ceiling on future kernel/loader growth unless the ESP writer is generalized.

## No read-back verification during install

After writing ESP sectors, the installer reports success based on write return codes.

It does not read the files back and compare their contents with the source files.

The later host checker confirms directory-entry names but not hashes or full FAT-chain contents.

A physical installer should verify data contents before reporting completion.

## QEMU proof

The strongest current proof comes from `test-qemu-install`.

After installation, the image checker examines GPT and ESP markers.

The same disk is then booted by OVMF with no ChrisOS ISO attached as the boot source.

The guest reaches:

```text
cfs mounted
desktop 60Hz
```

This demonstrates that the GPT/ESP arrangement is sufficient for the tested UEFI firmware environment.

## Physical-hardware caveats

The on-disk structures are conventional enough to be inspectable by standard firmware and OS tools, but several implementation choices remain experimental:

- fixed disk/partition GUIDs;
- no Secure Boot chain;
- FAT16 writer specialized to one layout;
- no post-write content hash verification;
- no backup-GPT recovery;
- no partition-entry CRC validation at runtime;
- no general GPT parser;
- 32-bit sector addressing;
- no legacy BIOS boot installation.

These constraints should be part of any hardware support claim.

## Immediate hardening priorities

The GPT/ESP path should evolve toward:

1. unique disk and partition GUID generation;
2. validation of partition-entry CRC in runtime GPT parsing;
3. backup-GPT fallback when primary GPT is damaged;
4. overlap and usable-range validation;
5. generic entry reading across sector boundaries;
6. full FAT consistency checking after write;
7. read-back SHA-256 verification of ESP files;
8. explicit release limits for ESP/kernel size;
9. Secure Boot signing support if required;
10. independent GPT/FAT validation in physical-hardware gates.

## Revision note

This chapter was written against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. ChrisOS currently generates a complete primary/backup GPT and a specialized 32 MiB FAT16 ESP sufficient for its QEMU+OVMF disk-boot gate. The implementation is intentionally narrow and should not yet be treated as a general GPT/FAT management library.
