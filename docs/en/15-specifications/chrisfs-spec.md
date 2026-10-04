---
id: chrisfs-spec
lang: en
type: specification
volume: 15-specifications
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/fs/storage_limits.h
  - kernel/fs/cfs_format.h
  - kernel/fs/cfs.h
  - kernel/fs/cfs.c
  - kernel/fs/cfs_fsck.c
  - tools/cfs_mkdisk.c
  - tools/cfs_migrate_v1v2.c
  - tools/cfs_migrate_v2v3.c
  - tools/test_cfs_v5.c
  - tools/test_cfs_fsck.c
  - tools/test_cfs_indirect.c
  - tools/test_cfs_journal.c
  - tools/test_cfs_maxwrite.c
  - tools/test_cfs_chmod.c
  - tools/test_cfs_paths.c
symbols:
  - cfs_format
  - cfs_mount
  - cfs_super_encode
  - cfs_super_decode
  - cfs_inode_encode
  - cfs_inode_decode
  - cfs_dirent_encode
  - cfs_dirent_decode
  - jnl_begin
  - jnl_log
  - jnl_commit
  - jnl_replay
  - cfs_fsck
depends_on:
  - specifications-policy
  - chrisfs
  - block-storage
related:
  - chrisfs-cache
  - chrisfs-inodes
  - chrisfs-fsck
  - chrisfs-journal
  - fault-injection
---

# ChrisFS on-disk format

## Status

ChrisFS is the native filesystem format used by ChrisOS.

This document specifies **ChrisFS version 5** as implemented at ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

The current mounter also accepts version 4 and compatibility version 3 superblocks.

Versions 1 and 2 are not mounted directly by the current superblock decoder; separate migration tools contain legacy readers for those historical layouts.

## Fundamental units

The filesystem uses a fixed logical sector size:

    512 bytes

The default disk geometry remains:

    1,048,576 sectors
    536,870,912 bytes
    512 MiB

Version 5 is not restricted to exactly that size.

Its formatter derives bitmap/data geometry from the block device's actual sector count.

## Magic and versions

The constants are:

    CFS_MAGIC          = 0x31534643
    CFS_VERSION        = 5
    CFS_VERSION_V4     = 4
    CFS_VERSION_COMPAT = 3

In little-endian byte order, the magic bytes are:

    C F S 1

The magic name remains `CFS1` even though the filesystem format has evolved through later version numbers.

## Endianness

All on-disk integer encoding helpers write explicit little-endian bytes.

ChrisFS therefore has an explicit little-endian disk format rather than relying on native struct layout.

This applies to superblocks, inodes, directory entries, pointer blocks and journal metadata.

## High-level volume layout

The logical regions are:

    LBA 0                superblock
    bitmap_lba...        allocation bitmap
    inode_lba...         inode table
    journal_lba...       metadata journal
    data_lba...          data/pointer blocks

Version 5 stores these positions and lengths in the superblock.

The formatter normally places the regions contiguously in the order above.

## Legacy 512 MiB geometry

For the traditional 512 MiB image, the constants are:

    superblock        LBA 0
    bitmap            LBA 1..256
    inode table       LBA 257..768
    journal           LBA 769..832
    data              LBA 833..

Specifically:

    CFS_BITMAP_LBA      = 1
    CFS_BITMAP_SECTORS  = 256
    CFS_INODE_LBA       = 257
    CFS_INODE_SECTORS   = 512
    CFS_JOURNAL_LBA     = 769
    CFS_JOURNAL_SECTORS = 64
    CFS_DATA_LBA        = 833

For 1,048,576 sectors this leaves:

    1,047,743 data sectors

or 536,444,416 bytes of data-region address space.

## Version-5 dynamic geometry

Version 5 computes bitmap size from the actual sector count.

The inode table remains fixed at 512 sectors and the journal at 64 sectors.

The bitmap grows until it has at least one bit for every data sector.

Conceptually, if (B) is bitmap sectors and (D) is data sectors:

[
B cdot 512 cdot 8 ge D
]

while:

[
1 + B + 512 + 64 + D = total_sectors
]

The formatter iterates until these conditions converge.

This lets v5 use sectors beyond the historical 512 MiB boundary.

## Version-4 and version-3 compatibility

For superblock versions 4 and 3, the current decoder requires the historical fixed geometry.

It validates the stored:

- total sector count;
- bitmap location/size;
- inode location/count/size;
- data location/size;
- root inode;
- journal location/size.

Thus old v4/v3 compatibility does not silently reinterpret arbitrary new geometry.

Tests explicitly convert a freshly formatted 512 MiB v5 superblock to version 4 and confirm mount, fsck, read and write behavior.

## Superblock location

The superblock occupies sector:

    LBA 0

Its meaningful serialized fields occupy the first 64 bytes.

The rest of the 512-byte sector is zero when encoded by the current writer.

## Superblock layout

| Offset | Size | Field |
|---:|---:|---|
| 0 | 4 | magic |
| 4 | 2 | version |
| 6 | 2 | sector size |
| 8 | 4 | total sectors |
| 12 | 4 | bitmap LBA |
| 16 | 4 | bitmap sectors |
| 20 | 4 | inode-table LBA |
| 24 | 4 | inode count |
| 28 | 4 | inode size |
| 32 | 4 | data LBA |
| 36 | 4 | data sectors |
| 40 | 4 | root inode |
| 44 | 4 | clean flag |
| 48 | 4 | generation |
| 52 | 4 | journal LBA |
| 56 | 4 | journal sectors |
| 60 | 4 | checksum |

The checksum covers bytes 0 through 59.

## Superblock checksum

ChrisFS uses a 32-bit FNV-1a-style checksum:

    initial = 2166136261
    hash ^= byte
    hash *= 16777619

The superblock stores:

[
checksum = FNV1a32(bytes[0..59])
]

A checksum mismatch causes superblock decode failure.

## Geometry validation

For v5, the decoder validates structural constraints including:

- bitmap exists;
- data region exists;
- inode count equals 2048;
- journal has at least two sectors;
- metadata regions are ordered/non-overlapping;
- data end does not exceed total sectors;
- bitmap contains enough bits for every data sector.

It also requires:

    inode_size = 128
    root_inode = 0

## Inode table

The inode table contains:

    CFS_INODE_COUNT = 2048

fixed-size records.

Each record is:

    CFS_INODE_SIZE = 128 bytes

With 512-byte sectors, four inodes fit per sector.

Therefore 2048 inodes require exactly 512 sectors.

## Inode types

The serialized inode type values are:

    0 = free
    1 = file
    2 = directory

Other values are invalid for current fsck semantics.

## Inode layout

| Offset | Size | Field |
|---:|---:|---|
| 0 | 2 | type |
| 2 | 2 | flags |
| 4 | 4 | file size |
| 8 | 4 | generation |
| 12 | 48 | 12 direct block LBAs |
| 60 | 4 | single-indirect LBA |
| 64 | 4 | double-indirect LBA |
| 68 | 4 | uid |
| 72 | 4 | gid |
| 76 | 4 | mode |
| 80 | 4 | triple-indirect LBA |
| 84 | 4 | mtime low |
| 88 | 4 | mtime high |
| 92 | 32 | reserved/zero in current encoder |
| 124 | 4 | checksum |

The inode checksum covers bytes 0 through 123.

## Inode checksum

The same FNV-1a-style helper is applied to the first 124 bytes.

If checksum verification fails, inode decode fails.

Fsck reports:

    inode checksum

for this corruption class.

The fsck host test deliberately flips a checksum byte and verifies that corruption is detected without writing to the disk.

## Root inode

The root inode number is:

    0

Formatting initializes inode 0 as a directory.

Its first direct pointer references the first data sector.

The formatter also sets the first allocation-bitmap bit because that data block is already owned by root.

## Block bitmap

The allocation bitmap describes **data-region sectors**, not absolute disk LBAs.

Bitmap index:

[
i = lba - data_lba
]

Bit 1 means the corresponding data sector is allocated.

A bitmap sector contains:

[
512 cdot 8 = 4096
]

allocation bits.

## Data blocks

The allocation unit is one 512-byte sector.

Data-region sectors serve multiple purposes:

- ordinary file data;
- directory-entry blocks;
- single-indirect pointer blocks;
- double-indirect pointer blocks;
- triple-indirect pointer blocks.

Pointer blocks contain 32-bit little-endian LBAs.

## Direct pointers

Each inode contains 12 direct LBAs.

Thus the direct region covers:

[
12 cdot 512 = 6144
]

bytes of file data.

## Single indirect

One indirect block contains:

    512 / 4 = 128

32-bit block pointers.

The single-indirect level therefore contributes 128 data blocks.

## Double indirect

A double-indirect root points to up to 128 single-indirect tables.

Capacity:

[
128^2 = 16,384
]

data blocks.

## Triple indirect

A triple-indirect root adds:

[
128^3 = 2,097,152
]

possible data-block pointers.

Together with direct/single/double levels, the addressing tree has a theoretical structural capacity of:

    2,113,676 blocks

before other bounds are applied.

The actual filesystem and API limits are smaller because of disk size and the 32-bit inode file-size field.

## Whole-file API limit

The buffered `cfs_write()` and `cfs_truncate()` path deliberately uses the older direct+single+double ceiling:

    CFS_MAX_BLOCKS = 16,524
    CFS_MAX_FILE_SIZE = 8,460,288 bytes

approximately 8.06 MiB.

`tools/test_cfs_maxwrite.c` verifies that exactly this size succeeds and one byte more returns `CFS_EFBIG`.

This is an API limit, not proof that triple-indirect fields are unused.

## Offset-write limit

`cfs_write_at()` can use the deeper addressing path and checks against:

    CFS_MAX_FILE_BYTES = data_sectors * 512

subject also to the 32-bit offset/size arithmetic and the 32-bit inode size field.

Therefore applications must not assume all write APIs share the same maximum-file-size contract.

## Directory-entry format

Each directory entry occupies:

    CFS_DIRENT_SIZE = 80 bytes

Layout:

| Offset | Size | Field |
|---:|---:|---|
| 0 | 4 | inode number |
| 4 | 1 | type |
| 5 | 1 | name length |
| 6 | 2 | flags |
| 8 | 64 | name bytes |
| 72 | 8 | reserved/zero |

Names are stored inline.

There is no separate string table.

## Directory density

With 80-byte entries in a 512-byte sector:

    CFS_DIRENTS_PER_SECTOR = 6

because integer division is used.

The remaining 32 bytes of the sector are not part of a seventh directory entry.

## Empty directory slots

A directory entry is treated as unused when inode or name length is zero.

Because the root inode is 0, ordinary directory entries do not use inode 0 as a child target.

The root is reached by the filesystem's root semantics rather than by a child dirent.

## Names and paths

Maximum component/name length is:

    64 bytes

Maximum path length is:

    512 bytes

Maximum parsed depth is:

    32 components

Path matching is byte-for-byte and therefore case-sensitive.

Tests explicitly demonstrate distinct names:

    foo
    Foo

## Path syntax

The current parser:

- permits an optional leading `/`;
- rejects empty interior components;
- rejects trailing slash after a non-root path;
- rejects backslash;
- rejects `.`;
- rejects `..`;
- rejects components longer than 64 bytes;
- rejects depth above 32.

The root can be represented by an empty path or `/` in APIs that permit root access.

## Directory block limit

Directory traversal uses:

    CFS_DIR_MAX_BLOCKS =
    CFS_DIRECT_COUNT + CFS_PTRS_PER_BLOCK

or:

    12 + 128 = 140 blocks

for directory contents.

This is a runtime directory limit even though file inodes can address deeper indirect trees.

At six entries per sector, the simple theoretical slot ceiling is 840 directory entries before other semantic constraints.

## Permission bits

Current permission bits are:

    READ  = 1
    WRITE = 2
    EXEC  = 4
    WALK  = 8

and:

    CFS_PERM_ALL = 15

The inode contains both `mode` and legacy-compatible low permission bits in `flags`.

## Permission compatibility rule

Effective mode is chosen in this order:

1. nonzero `mode`;
2. low permission bits from `flags`;
3. for a non-free legacy inode, default to all permissions.

This preserves compatibility with older inode records that did not carry the modern mode field semantics.

## UID/GID status

New inodes are initialized with:

    uid = 0
    gid = 0

The current permission checker rejects access when inode uid is nonzero.

Therefore the persisted uid/gid fields exist, but the current runtime is not a general multi-user UNIX permission model.

It effectively operates around owner 0 plus the four ChrisFS permission bits.

## Modification time

Modification time is stored as two 32-bit words:

    mtime_lo
    mtime_hi

forming a 64-bit value:

[
mtime = lo | (hi << 32)
]

The current filesystem clock is an internal monotonically advanced value unless the caller sets a nonzero time through `cfs_set_now()`.

The on-disk field itself does not define an external epoch in this revision.

## Journal overview

ChrisFS reserves a small metadata journal.

The constants are:

    JNL_MAGIC   = 0x4C4E4A43
    JNL_EMPTY   = 0
    JNL_BEGIN   = 1
    JNL_COMMIT  = 2
    JNL_MAX_REC = 30

The default journal occupies 64 sectors.

## Journal header

The first journal sector contains:

| Offset | Size | Field |
|---:|---:|---|
| 0 | 4 | journal magic |
| 4 | 4 | sequence |
| 8 | 4 | state |
| 12 | 4 | record count |
| 16 | 4 | checksum |

The checksum covers bytes 0 through 15.

The remainder of the sector is zero in normal writes.

## Journal record layout

Each journal record consumes two sectors.

At:

[
journal_lba + 1 + 2i
]

the metadata sector stores:

| Offset | Size | Field |
|---:|---:|---|
| 0 | 4 | target LBA |
| 4 | 4 | checksum of 512-byte payload |

The following sector contains the complete 512-byte replacement data.

At 30 records, the journal consumes:

    1 + 30*2 = 61 sectors

inside the default 64-sector region.

## Journal semantics

`jnl_begin` marks the superblock unclean and writes a BEGIN header.

For metadata writes, `jnl_log` stores the replacement sector in the journal before the target metadata sector is written.

`jnl_commit` writes COMMIT and then transitions the journal header to EMPTY, finally marking the superblock clean.

On mount:

- EMPTY requires no replay;
- BEGIN is discarded as an incomplete transaction;
- COMMIT replays recorded replacement sectors, then clears the journal.

This is a small **redo-oriented metadata journal**.

It is not an undo log and it does not provide full data journaling.

## Data-write policy

During whole-file/offset data writes, the implementation sets `jnl_data` so ordinary file-data sector writes are not individually journaled.

Metadata updates are the journaled portion.

Therefore a successful metadata journal must not be interpreted as proof of full ordered-data or power-loss atomicity.

Crash-consistency testing remains an explicit validation roadmap item.

## Clean flag and generation

The superblock contains:

    clean
    generation

Transactions mark the filesystem unclean at begin and clean after commit.

Filesystem operations also advance generation as metadata evolves.

These fields support state tracking, but they do not replace journal validation/checksums.

## Mount procedure

A successful mount requires:

1. 512-byte block device sector size;
2. readable/valid superblock;
3. supported version;
4. valid checksum/geometry;
5. backing device at least as large as the stored filesystem geometry;
6. successful journal replay/drop handling;
7. root inode decodes correctly;
8. root inode is a directory.

Failure is reported through ChrisFS error codes rather than silently reformatting inside `cfs_mount`.

## Format procedure

`cfs_format` requires a writable 512-byte-sector block device.

It:

1. derives v5 geometry from sector count;
2. zeroes metadata through the start of data;
3. marks data bitmap bit 0 allocated;
4. initializes all inode records with valid checksums;
5. initializes root inode 0 as directory;
6. points root direct[0] at first data sector;
7. initializes root permissions;
8. zeros the root data block;
9. writes the superblock;
10. initializes an EMPTY journal;
11. flushes the block device.

## Fsck

`cfs_fsck` is read-only with respect to normal validation.

It checks major invariants including:

- superblock checksum;
- journal state;
- inode checksums/types;
- block LBA range;
- duplicate block ownership;
- bitmap missing bits;
- bitmap leaks;
- direct/indirect/double/triple pointer trees;
- root type;
- directory cycles;
- duplicate names in a directory;
- invalid dirents;
- file size versus block mapping.

The test suite verifies corruption detection and explicitly checks that fsck does not write to the disk.

## Fsck result model

A clean filesystem returns:

    CFS_OK

and reason:

    clean

Detected structural problems return a positive error count where applicable, while I/O/setup failures can return negative ChrisFS error codes.

`cfs_fsck_reason()` reports the first classified reason.

## Error codes

The public API defines negative error codes for classes such as:

- invalid argument;
- I/O;
- format;
- not found;
- already exists;
- no space;
- file too large;
- name too long;
- corruption;
- not mounted;
- not directory;
- not empty;
- is directory;
- cross-device;
- permission denied.

On-disk format consumers should not encode these runtime numeric values into persistent metadata unless a later format explicitly defines such a field.

## Cache is not on-disk state

The 64-line ChrisFS cache, hit/miss counters and LRU-style age values belong to runtime state.

They are not part of the disk format.

A raw disk image contains no cache metadata.

## Migration history

The repository contains explicit readers for historical v1 and v2 layouts in:

    tools/cfs_migrate_v1v2.c
    tools/cfs_migrate_v2v3.c

Despite their historical filenames, their destination creation path calls the current `cfs_format()`.

At this revision that means newly written destination media follows the current format implementation rather than freezing the original historical target version implied by the tool name.

New compatibility tooling should state source and destination versions explicitly.

## Current v5 evidence

The v5 test suite verifies that:

- a 512 MiB v5 image preserves the historical region addresses;
- changing that superblock to v4 remains mountable;
- v4 read/write/fsck still works;
- a v5 volume larger than the old disk size stores the larger sector count;
- its data region extends past the old end;
- allocation can occur beyond the historical 512 MiB boundary.

This is direct evidence for the main v5 change: dynamic volume geometry.

## Format limitations

ChrisFS v5 currently lacks several features common in mature filesystems:

- extent trees;
- sparse-file semantics as a formal contract;
- symbolic links;
- hard links;
- rich timestamps;
- general multi-user permission model;
- ACL lists;
- xattrs;
- checksums on ordinary data sectors;
- copy-on-write;
- snapshots;
- scalable inode allocation beyond 2048 inodes;
- large directory indexing;
- full data journaling.

These are outside the current format.

## Versioning rule

An incompatible change requires a new filesystem version when it changes persisted interpretation of:

- superblock fields;
- inode layout;
- directory-entry layout;
- pointer-tree semantics;
- permission fields;
- journal record semantics;
- checksum rules;
- bitmap meaning;
- region geometry rules.

A reader may add compatibility for older versions, but it must not reinterpret old bytes under new semantics without an explicit compatibility rule.

## Conformance summary

A conforming ChrisFS v5 implementation must at minimum preserve:

- 512-byte logical sectors;
- little-endian encoding;
- `CFS1` magic;
- v5 superblock field offsets/checksum;
- 128-byte inode records and checksum;
- 80-byte directory entries;
- 64-byte names;
- data-sector bitmap semantics;
- direct/single/double/triple pointer interpretation;
- root inode 0;
- journal header/record representation;
- dynamic geometry invariants.

Runtime API limits such as the 8.06 MiB whole-file write ceiling must be documented separately from the raw format's pointer-tree capacity.

## Revision note

This specification was reconciled against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

The key v5 change is dynamic volume geometry while retaining compatibility with fixed-geometry v4/v3 images. The format already contains richer pointer and metadata fields than some high-level APIs currently exploit, so disk-format capability and API capability must remain clearly separated.
