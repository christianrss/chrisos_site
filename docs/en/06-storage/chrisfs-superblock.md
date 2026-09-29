---
id: chrisfs-superblock
lang: en
type: technical-chapter
volume: 06-storage
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/fs/cfs_format.h
  - kernel/fs/cfs.c
  - kernel/fs/cfs_fsck.c
  - kernel/fs/storage.c
  - kernel/fs/storage_limits.h
  - kernel/fs/block_device.h
  - tools/test_cfs_v5.c
  - tools/test_cfs_host.c
symbols:
  - CfsSuper
  - cfs_get16
  - cfs_get32
  - cfs_put16
  - cfs_put32
  - cfs_checksum
  - cfs_super_legacy
  - cfs_geom_for_count
  - cfs_super_geom_ok
  - cfs_super_encode
  - cfs_super_decode
  - cfs_format
  - cfs_mount
  - storage_format_if_empty
  - disk_has_cfs
  - cfs_fsck
depends_on:
  - chrisfs
  - block-storage
  - partitions-gpt
related:
  - chrisfs-inodes
  - chrisfs-journal
  - chrisfs-fsck
  - installation-real-hardware
---

# ChrisFS superblock and volume geometry

## Scope

The ChrisFS superblock is the first trust boundary between a raw block device and the filesystem. It identifies the volume, selects the on-disk format version and describes the locations and sizes of the bitmap, inode table, journal and data region.

ChrisFS stores the superblock at logical block address 0 of the filesystem-visible device. On a GPT installation that means LBA 0 of the ChrisFS partition view, not necessarily physical LBA 0 of the disk.

The current implementation supports three mountable on-disk versions:

~~~text
v3  compatibility format
v4  fixed 512-MiB geometry
v5  current dynamic-geometry format
~~~

Versions 1 and 2 are not mounted directly by the current decoder. Historical migration tools exist for older formats.

This chapter documents ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

![ChrisFS superblock validation and geometry flow](../../assets/diagrams/chrisfs-superblock-en.svg)

## Why the superblock is security-sensitive

Most later filesystem addresses are derived from superblock fields.

A corrupt value such as:

~~~text
inode_lba
journal_lba
data_lba
bitmap_sectors
~~~

can redirect later reads and writes to the wrong sectors.

For that reason ChrisFS does not cast sector 0 to a C struct. It parses fixed-width little-endian fields, verifies a checksum and applies geometry constraints before mounting.

The decoder is therefore part of the filesystem's attack and corruption surface.

## Persistent byte layout

The encoder writes the first 64 bytes of a 512-byte sector as follows:

| Offset | Size | Field | Meaning |
|---:|---:|---|---|
| 0 | 4 | magic | `CFS_MAGIC` |
| 4 | 2 | version | v3, v4 or v5 |
| 6 | 2 | sector size | must be 512 |
| 8 | 4 | total sectors | filesystem-visible sector count |
| 12 | 4 | bitmap LBA | first bitmap sector |
| 16 | 4 | bitmap sectors | bitmap length |
| 20 | 4 | inode LBA | first inode-table sector |
| 24 | 4 | inode count | must currently be 2048 |
| 28 | 4 | inode size | must be 128 |
| 32 | 4 | data LBA | first data sector |
| 36 | 4 | data sectors | data-region length |
| 40 | 4 | root inode | must be 0 |
| 44 | 4 | clean | clean/dirty state |
| 48 | 4 | generation | filesystem generation counter |
| 52 | 4 | journal LBA | first journal sector |
| 56 | 4 | journal sectors | journal-region length |
| 60 | 4 | checksum | checksum of bytes 0..59 |

Bytes 64 through 511 are zeroed by `cfs_super_encode`, but the decoder does not currently inspect or checksum them.

They are therefore effectively reserved, not integrity-protected metadata.

## Magic value

The magic constant is:

~~~text
0x31534643
~~~

In little-endian byte order this becomes:

~~~text
43 46 53 31
 C  F  S  1
~~~

or the ASCII text:

~~~text
CFS1
~~~

The same magic is retained across the current format versions; versioning is carried separately by the 16-bit version field.

## Little-endian encoding

ChrisFS uses explicit helpers:

~~~text
cfs_get16
cfs_get32
cfs_put16
cfs_put32
~~~

This makes the persistent ABI independent of compiler struct packing and native alignment.

Every multibyte field in the current superblock is little-endian.

There are no 64-bit superblock fields. Capacity and all region coordinates are consequently bounded by the 32-bit block ABI.

## Superblock checksum

`cfs_checksum` starts from:

~~~text
2166136261
~~~

and for each input byte performs:

~~~text
hash ^= byte
hash *= 16777619
~~~

This is the same arithmetic structure as 32-bit FNV-1a.

The encoder computes it over exactly:

~~~text
bytes 0..59
~~~

and stores the result at offset 60.

The decoder recomputes the same 60-byte checksum before accepting geometry.

### What the checksum protects

It covers:

- magic;
- version;
- sector size;
- all geometry fields;
- root inode constant;
- clean flag;
- generation;
- journal geometry.

It does not cover:

- the checksum field itself;
- bytes 64..511;
- any other filesystem sector.

This is corruption detection, not cryptographic authentication. Anyone able to rewrite the sector can also recompute the checksum.

## Version selection

`cfs_super_decode` accepts exactly:

~~~text
CFS_VERSION         = 5
CFS_VERSION_V4      = 4
CFS_VERSION_COMPAT  = 3
~~~

Any other version returns a decode error.

The runtime mount path maps any decode failure to:

~~~text
CFS_EFORMAT
~~~

rather than exposing the decoder's internal negative reason codes.

## Legacy v3/v4 geometry

For v3 and v4, the decoder does not trust arbitrary geometry from disk.

Instead it requires exact historical constants:

~~~text
total sectors      1,048,576
bitmap LBA         1
bitmap sectors     256
inode LBA          257
inode count        2,048
inode size         128
journal LBA        769
journal sectors    64
data LBA           833
data sectors       1,047,743
root inode         0
~~~

At 512 bytes per sector:

~~~text
1,048,576 sectors = 512 MiB
~~~

After verification, `cfs_super_legacy` reconstructs these values into the in-memory `CfsSuper`.

The on-disk `clean` and `generation` fields are retained.

## Why v3/v4 are fixed

The older format contract assumes known metadata addresses.

That has two advantages:

- old images remain deterministic;
- corrupt geometry cannot redirect metadata within those versions.

The trade-off is that an old filesystem does not automatically grow just because it is placed on a larger block device.

`cfs_mount` accepts a backing device larger than the superblock's total, but the filesystem continues to expose only its recorded 512-MiB geometry.

## v5 dynamic geometry

Version 5 moves the main volume geometry into validated superblock fields.

`cfs_geom_for_count` derives a layout from the block device's `sector_count`.

The fixed components are:

~~~text
superblock          1 sector
inode table       512 sectors
journal            64 sectors
~~~

The bitmap is the variable metadata component.

Each bitmap sector contains:

~~~text
512 bytes × 8 bits = 4096 allocation bits
~~~

and therefore describes up to 4096 data sectors.

## Geometry equation

Let:

~~~text
T = total sectors
B = bitmap sectors
F = 1 + 512 + 64 = 577 fixed metadata sectors
D = data sectors
~~~

Then the generated v5 layout satisfies:

~~~text
D = T - F - B
B × 4096 >= D
~~~

The algorithm iterates until the chosen bitmap is large enough to describe the data region that remains after reserving that bitmap.

The generated positions are then:

~~~text
bitmap_lba  = 1
inode_lba   = 1 + B
journal_lba = inode_lba + 512
data_lba    = journal_lba + 64
~~~

and:

~~~text
data_lba + data_sectors = total_sectors
~~~

for volumes created by `cfs_format`.

## Example: the historical 512-MiB size

For:

~~~text
T = 1,048,576
~~~

the calculation yields:

~~~text
B             = 256
bitmap_lba    = 1
inode_lba     = 257
journal_lba   = 769
data_lba      = 833
data_sectors  = 1,047,743
~~~

So v5 preserves the old physical addresses at the historical volume size.

This is verified in `test_cfs_v5.c`.

## Example: a slightly larger device

The v5 host test uses:

~~~text
T = 1,048,576 + 8,192
  = 1,056,768 sectors
~~~

The derived geometry becomes:

~~~text
bitmap sectors  258
inode LBA       259
journal LBA     771
data LBA        835
data sectors    1,055,933
~~~

The test then forces early data blocks to look allocated and confirms that a new file can allocate beyond the old 512-MiB filesystem boundary.

That proves the dynamic geometry is operational, not merely stored.

## Minimum representable v5 geometry

The geometry function rejects:

~~~text
total <= 578 sectors
~~~

With 579 sectors, it can construct:

~~~text
bitmap         1 sector
inode table  512 sectors
journal        64 sectors
data            1 sector
~~~

The one data sector is immediately consumed by the root directory during formatting, so this is structurally formatable but not meaningfully useful for file storage.

The normal boot auto-format path is more conservative: root discovery only considers blank writable disks with at least the historical `STOR_DISK_SECTORS` size.

## Maximum scale under the current ABI

`BlockDevice.sector_count` is a `uint32_t`.

At 512 bytes per sector, the theoretical addressable capacity is just under:

~~~text
2 TiB
~~~

The v5 geometry code also stores every region field in 32 bits.

For a near-maximum 32-bit sector count, the bitmap itself becomes roughly 512 MiB.

Because `cfs_format` zeroes metadata one 512-byte sector at a time before writing the initialized structures, formatting such a volume would require on the order of one million metadata writes before reaching the data region.

The format is therefore bounded not only by address width but also by the current initialization strategy.

## v5 geometry validator

`cfs_super_geom_ok` currently requires:

- bitmap sector count nonzero;
- data sector count nonzero;
- inode count exactly 2048;
- journal sector count at least 2;
- bitmap LBA nonzero;
- inode LBA greater than bitmap LBA;
- bitmap does not overlap the inode table;
- inode table does not overlap the journal;
- data region does not begin before the journal ends;
- data region ends no later than `total_sectors`;
- bitmap bit capacity covers all declared data sectors.

This is deliberately more flexible than `cfs_geom_for_count`.

A v5 volume does not have to use the exact layout generated by ChrisOS as long as it passes these invariants.

## Gaps are currently legal

The validator prevents overlap but does not require regions to be adjacent.

For example, it does not require:

~~~text
inode_lba   == bitmap_lba + bitmap_sectors
journal_lba == inode_lba + 512
data_lba    == journal_lba + journal_sectors
~~~

It also accepts:

~~~text
data_lba + data_sectors < total_sectors
~~~

which leaves unused sectors at the end of the filesystem-visible device.

This flexibility could support future alternative layouts, but there is currently no feature field describing why such gaps exist.

## Critical journal-size validation gap

The generated v5 geometry always reserves:

~~~text
CFS_JOURNAL_SECTORS = 64
~~~

However, `cfs_super_geom_ok` only checks:

~~~text
journal_sectors >= 2
~~~

The current journal supports:

~~~text
JNL_MAX_REC = 30
~~~

Each record consumes two sectors plus one journal-header sector.

A full transaction can therefore address through:

~~~text
1 + 30 × 2 = 61 journal sectors
~~~

from the start of the journal region.

A crafted v5 superblock can declare a journal much smaller than that and still pass geometry validation.

Later journal activity can then access sectors beyond the declared journal region.

Self-generated filesystems do not hit this problem because `cfs_format` always writes 64 sectors, but the decoder should validate the capacity required by the journal implementation.

## Integer-overflow validation gaps

Two current overlap checks perform 32-bit additions directly:

~~~text
bitmap_lba + bitmap_sectors
journal_lba + journal_sectors
~~~

before comparing their results to later regions.

Because these fields are unsigned 32-bit values, malformed values near `UINT32_MAX` can wrap modulo 2^32.

Other checks, such as:

~~~text
(uint64_t)inode_lba + CFS_INODE_SECTORS
(uint64_t)data_lba + data_sectors
~~~

already widen before addition.

For consistency and corruption hardening, all region-end calculations should use widened arithmetic before comparison.

## Fields that are fixed even in v5

Dynamic geometry does not mean every field is variable.

The decoder still requires:

~~~text
inode size   = 128
root inode   = 0
inode count  = 2048
sector size  = 512
~~~

So v5 can resize and relocate regions but does not yet describe a general family of arbitrary inode formats or sector sizes.

Changing those properties requires a new compatible format contract, not merely another v5 superblock value.

## Clean flag

The `clean` field sits at offset 44 and participates in the superblock checksum.

Formatting initializes it to:

~~~text
1
~~~

Journal begin sets it to zero before recording BEGIN.

Successful commit sets it back to one.

Boot storage logic uses the value as a boolean:

- nonzero: fsck may be skipped;
- zero: run fsck after mount.

The decoder does not constrain the field to exactly 0 or 1. Any nonzero 32-bit value is treated as clean by the later truth test.

## Generation counter

The `generation` field starts at 1 after format.

Filesystem mutation paths increment it, and journal begin uses the current generation as the journal sequence value.

It is also checksummed in the superblock.

The field is 32-bit and there is no explicit wrap policy. After enough increments it wraps according to unsigned arithmetic.

At current project scale that is not a practical near-term limit, but it is part of the persistent ABI.

## Formatting order

`cfs_format` computes geometry before writing anything.

It then:

1. zeroes all metadata sectors from superblock through the sector before `data_lba`;
2. marks data-block bitmap bit 0 as allocated;
3. initializes the fixed inode table;
4. creates root inode 0;
5. zeroes the root directory data sector;
6. writes the encoded superblock;
7. writes an EMPTY journal header;
8. calls `bd_flush`.

The superblock is therefore written late in formatting, after most metadata has already been initialized.

If formatting is interrupted earlier, sector 0 is likely still zero because the metadata-zeroing pass begins there.

That interacts with auto-format detection.

## Automatic formatting of blank media

`storage_format_if_empty` reads superblock sector 0.

Its decision is:

~~~text
valid ChrisFS superblock -> leave unchanged
invalid + first 8 bytes all zero -> format
invalid + any of first 8 bytes nonzero -> CFS_EFORMAT
~~~

This is intentionally conservative.

An unknown or damaged nonzero signature is not automatically destroyed.

The host test verifies that a sector beginning with `0xFF` is rejected and remains unmodified.

## Consequence of the eight-byte blank test

Only the first eight bytes determine whether an invalid superblock is considered blank enough to format.

Those bytes contain:

~~~text
magic
version
sector size
~~~

A sector with those eight bytes zero but arbitrary bytes later in the sector is considered blank by this helper.

The function does not inspect the rest of sector 0 before formatting.

This policy is simple and protects recognizable unknown formats, but it is not a full empty-disk detector.

## Root discovery

`disk_has_cfs` performs the same fundamental identification used for whole-disk and GPT-partition root discovery:

1. read filesystem-relative LBA 0;
2. run `cfs_super_decode`;
3. treat decode success as evidence of a ChrisFS volume.

For GPT partitions, this happens after the partition table identifies a candidate partition and `PartView` rebases its first sector to logical LBA 0.

The root filesystem is later fully mounted, journal replay is run and root inode 0 is validated as a directory.

## Mount-time relationship to backing capacity

After decoding, `cfs_mount` checks:

~~~text
dev->sector_count >= super.total_sectors
~~~

A smaller backing device is rejected.

A larger one is accepted.

This makes it possible to mount an existing ChrisFS image inside a larger partition without automatically expanding it.

There is currently no online grow operation that rewrites geometry to consume the extra sectors.

## What superblock validation does not prove

Even a valid superblock does not prove the rest of the filesystem is consistent.

The decoder does not verify:

- bitmap contents;
- inode checksums;
- root inode type;
- journal record validity;
- block ownership;
- directory graph;
- allocation leaks.

Mount subsequently validates the root inode and replays the journal.

`cfs_fsck` performs the deeper cross-structure checks.

The superblock decoder should therefore be viewed as geometry validation, not whole-filesystem certification.

## fsck and the superblock

`cfs_fsck` rereads LBA 0 directly from the block device and decodes it again.

If decode fails, it reports:

~~~text
super checksum
~~~

as its generic superblock corruption reason.

It then uses the decoded geometry to size its bitmap/seen maps and locate the inode, journal and data regions.

This means superblock correctness is a prerequisite for every deeper fsck invariant.

## Validation evidence

### v4 compatibility

`test_cfs_v5` first formats a normal current filesystem, rewrites the version field to v4, recomputes the checksum and confirms that:

- mount succeeds;
- in-memory version is v4;
- fsck succeeds;
- a file can be written and read.

Because the current 512-MiB v5 geometry matches the fixed v4 addresses, this is a direct compatibility test.

### v5 growth

The same test creates a sparse simulated block device larger than 512 MiB.

It verifies:

- v5 version in sector 0;
- stored total sector count;
- data geometry extending beyond the legacy end;
- successful mount;
- actual file allocation past the old boundary.

### corruption and auto-format protection

`test_cfs_host` verifies:

- I/O error reading the superblock produces `CFS_EIO`;
- a valid superblock is not reformatted;
- an unknown nonzero superblock prefix returns `CFS_EFORMAT`;
- the unknown data remains unchanged.

## Complexity

Superblock encode/decode is:

~~~text
O(1)
~~~

because it processes a fixed 512-byte sector and checks a small fixed set of fields.

Geometry calculation is also effectively O(1): it iterates only until bitmap size stabilizes and includes a small guard bound.

Formatting is not O(1). It clears:

~~~text
data_lba metadata sectors
~~~

before initializing the root.

Because bitmap size grows with volume capacity, metadata initialization cost also grows with disk size.

## Current limitations

At the documented revision:

- sector size is fixed at 512 bytes;
- all geometry fields are 32-bit;
- current practical address space is below 2 TiB;
- inode count is fixed at 2048;
- inode size is fixed at 128 bytes;
- root inode is fixed at 0;
- legacy v3/v4 volumes are fixed to 512 MiB;
- there is no online grow/shrink;
- reserved superblock bytes 64..511 are ignored and not checksummed;
- checksum is non-cryptographic;
- `clean` accepts arbitrary nonzero values;
- generation has no explicit wrap policy;
- v5 allows layout gaps with no feature description;
- v5 does not require the data region to consume the declared total capacity;
- journal length validation is weaker than the journal implementation requires;
- some region-end overlap checks use overflow-prone 32-bit addition;
- superblock decode alone does not prove filesystem consistency;
- formatting large v5 media can require a very large number of single-sector metadata writes.

## Roadmap boundary

A stronger future superblock contract should consider:

- 64-bit sector counts and LBAs;
- explicit feature/incompatibility flags;
- exact journal-capacity validation;
- widened arithmetic for every region calculation;
- explicit adjacency or gap descriptors;
- a documented reserved-field policy;
- stronger checksums or authenticated metadata where needed;
- backup/redundant superblocks;
- online filesystem grow support;
- more efficient initialization of large metadata ranges;
- explicit clean-state enum validation;
- test vectors for malformed but checksummed v5 geometry.

Those capabilities remain future work until implemented and covered by reproducible tests.

## Source map and revision note

`kernel/fs/storage_limits.h` defines the current constants and historical geometry. `kernel/fs/cfs_format.h` defines the persistent superblock format, checksum, legacy reconstruction, dynamic geometry and validation. `kernel/fs/cfs.c` consumes the geometry during format and mount. `kernel/fs/storage.c` uses superblock decode for root discovery and conservative auto-format decisions. `kernel/fs/cfs_fsck.c` revalidates the superblock before deeper consistency checks. `tools/test_cfs_v5.c` and `tools/test_cfs_host.c` provide the primary host-side evidence.

All current-behavior claims in this chapter were reconciled against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.
