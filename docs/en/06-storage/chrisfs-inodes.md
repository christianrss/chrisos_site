---
id: chrisfs-inodes
lang: en
type: technical-chapter
volume: 06-storage
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/fs/cfs_format.h
  - kernel/fs/cfs.c
  - kernel/fs/cfs_fsck.c
  - kernel/fs/storage_limits.h
  - tools/test_cfs_indirect.c
  - tools/test_cfs_maxwrite.c
  - tools/test_cfs_fsck.c
symbols:
  - CfsInode
  - cfs_inode_encode
  - cfs_inode_decode
  - inode_read
  - inode_write
  - inode_alloc
  - inode_release
  - inode_ptr_free
  - inode_ptr_prune
  - free_ptr_levels
  - block_alloc
  - block_free
  - ptr_block_get
  - ptr_block_set
  - file_lba
  - cfs_write
  - cfs_write_at
  - cfs_truncate
  - cfs_unlink
  - cfs_fsck
depends_on:
  - chrisfs
  - chrisfs-superblock
related:
  - chrisfs-directories
  - chrisfs-journal
  - chrisfs-cache
  - chrisfs-fsck
---

# ChrisFS inodes and block indirection

## Scope

ChrisFS inodes are the persistent objects that connect names and directory entries to file metadata and data blocks.

The current format uses a fixed 128-byte inode ABI, a fixed table of 2048 inode slots, and four block-addressing levels:

~~~text
12 direct pointers
1 single-indirect pointer
1 double-indirect pointer
1 triple-indirect pointer
~~~

All stored block pointers are 32-bit absolute LBAs relative to the filesystem-visible `BlockDevice`. They are not data-region-relative block numbers.

This chapter follows inode state from its on-disk encoding through allocation, lookup, block growth, shrinking, release and fsck validation.

Current behavior was reconciled against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

![ChrisFS inode block addressing](../../assets/diagrams/chrisfs-inodes-en.svg)

## Fixed inode-table geometry

The current constants are:

~~~text
inode size       128 bytes
inode count      2048
inode sectors    512
sector size      512 bytes
~~~

Therefore:

~~~text
4 inodes per sector
2048 × 128 = 512 × 512 = 262,144 bytes
~~~

A compile-time assertion in `storage_limits.h` enforces that the configured inode table exactly matches those numbers.

In v5, the inode table may move because the bitmap grows, but its size and number of slots remain fixed.

## Inode identifiers

Inode IDs are table indexes:

~~~text
0 .. 2047
~~~

Inode 0 is permanently reserved as:

~~~text
CFS_ROOT_INODE = 0
~~~

Normal inode allocation starts at 1.

That leaves at most:

~~~text
2047 non-root inode slots
~~~

for files and directories combined.

There is no dynamic inode-table growth.

## On-disk inode layout

Every inode occupies exactly 128 bytes.

| Offset | Size | Field |
|---:|---:|---|
| 0 | 2 | type |
| 2 | 2 | flags |
| 4 | 4 | size |
| 8 | 4 | generation |
| 12 | 48 | 12 direct pointers |
| 60 | 4 | single-indirect pointer |
| 64 | 4 | double-indirect pointer |
| 68 | 4 | uid |
| 72 | 4 | gid |
| 76 | 4 | mode |
| 80 | 4 | triple-indirect pointer |
| 84 | 4 | mtime low |
| 88 | 4 | mtime high |
| 92 | 32 | reserved/zero on encode |
| 124 | 4 | checksum |

The encoder explicitly zeros all 128 bytes before writing fields.

That means bytes 92..123 are currently reserved and emitted as zero.

The decoder verifies the checksum but otherwise ignores those reserved bytes. A manually generated inode can therefore place nonzero values there and remain accepted if its checksum is recomputed.

## Inode types

The current type values are:

~~~text
0 = free
1 = file
2 = directory
~~~

The runtime and fsck reject unsupported nonzero types.

A free inode is represented by a fully zeroed logical inode, encoded with a valid checksum.

This is important: a free slot is not an all-zero 128-byte disk region, because the final checksum field is populated by `cfs_inode_encode`.

## Inode checksum

The inode checksum uses the same 32-bit FNV-1a-like function as the superblock.

It covers:

~~~text
bytes 0..123
~~~

and is stored at bytes 124..127.

The checksum therefore protects:

- type;
- flags;
- size;
- generation;
- all block pointers;
- uid/gid/mode;
- mtime;
- reserved bytes 92..123.

`inode_read` refuses a checksum mismatch with:

~~~text
CFS_ECORRUPT
~~~

The host fsck test explicitly flips the stored checksum of inode 1 and verifies that fsck reports:

~~~text
inode checksum
~~~

without writing to the disk.

## Inode read/write mapping

Four inodes share one sector.

For inode ID `id`:

~~~text
sector = inode_lba + id / 4
offset = (id % 4) × 128
~~~

`inode_read`:

1. bounds-checks the ID against `super.inode_count`;
2. reads the containing sector through the filesystem cache;
3. decodes and validates the selected 128-byte record.

`inode_write`:

1. reads the containing 512-byte sector;
2. re-encodes only the selected inode slot;
3. writes the whole sector through the cache.

Thus inode updates are sector-level read-modify-write operations.

## Allocation policy

`inode_alloc` scans linearly:

~~~text
ID 1 -> 2047
~~~

and stops at the first inode whose type is `CFS_INODE_FREE`.

When a free slot is found it is initialized as a file inode:

~~~text
type       = FILE
generation = fs.super.generation + 1
uid        = 0
gid        = 0
mode       = READ|WRITE|EXEC|WALK
flags      = same four compatibility bits
~~~

Directory creation first allocates a file-style inode and then changes its type to directory before linking it into the parent.

There is no inode allocation bitmap and no inode allocation hint.

Worst-case inode allocation is therefore:

~~~text
O(2048)
~~~

inode reads per allocation.

At the current fixed table size that cost is bounded, but it does not scale to a large inode namespace.

## Allocation failure behavior

Inode allocation itself writes the newly initialized inode before returning its ID.

Higher-level creation must then add a directory entry.

If directory insertion fails, `cfs_create` and `cfs_mkdir` attempt to write a zeroed inode back to the slot.

This is local rollback rather than a general resource transaction.

A crash or lower-layer failure between inode allocation and higher-level linkage can still require fsck-level reasoning.

## Permissions stored in the inode

The current persistent fields are:

~~~text
uid
gid
mode
flags
~~~

New objects use:

~~~text
uid = 0
gid = 0
mode = 15
flags = 15
~~~

The permission bits are:

~~~text
READ  = 1
WRITE = 2
EXEC  = 4
WALK  = 8
~~~

For compatibility, effective mode is selected as:

1. `mode`, when nonzero;
2. low permission bits from `flags`, when present;
3. all permissions for any non-free inode when both fields are zero.

The current runtime also rejects objects whose uid is not zero.

So the format has uid/gid fields, but the implementation is not yet a Unix ownership model.

## Generation and modification time

An allocated inode receives a generation derived from the current filesystem generation.

Whole-file writes increment:

~~~text
inode.generation++
~~~

Modification time is stored as:

~~~text
mtime_lo
mtime_hi
~~~

which together form a 64-bit value.

`inode_stamp` increments the global ChrisFS logical clock and records it into those two fields.

The timestamp is therefore controlled by the filesystem clock state rather than being generated from hardware directly inside the inode layer.

## Block pointers are absolute LBAs

An inode's pointers contain logical block addresses in the backing filesystem device.

For a GPT-root filesystem this means addresses inside the `PartView`, not physical whole-disk LBAs.

A nonzero pointer is expected to satisfy:

~~~text
super.data_lba <= lba < super.data_lba + super.data_sectors
~~~

The bitmap tracks the same data-region blocks by relative index:

~~~text
bitmap index = lba - data_lba
~~~

Data blocks and pointer-table blocks use the same allocator and bitmap.

## Pointer-block format

Each pointer-table sector contains:

~~~text
512 / 4 = 128
~~~

little-endian 32-bit LBAs.

There is no header, magic, checksum or level tag in a pointer block.

Its interpretation comes entirely from the inode field and traversal depth.

A zero pointer means “not allocated.”

## Direct addressing

The first:

~~~text
12 blocks
~~~

come from:

~~~text
direct[0..11]
~~~

Capacity:

~~~text
12 × 512 = 6144 bytes
~~~

Direct pointers require no additional metadata block after the inode itself.

## Single indirection

After the direct region, the inode's `indirect` field points to one 512-byte pointer block.

That table contains 128 data-block LBAs.

Capacity contributed:

~~~text
128 × 512 = 65,536 bytes
~~~

Cumulative direct + single-indirect capacity:

~~~text
140 blocks
71,680 bytes
~~~

The directory implementation intentionally stops at this level, giving directories the same 140-block structural ceiling.

## Double indirection

The `double_indirect` field points to a table of up to 128 intermediate pointer blocks.

Each intermediate block points to 128 data blocks.

Capacity contributed:

~~~text
128 × 128 = 16,384 blocks
16,384 × 512 = 8,388,608 bytes
~~~

Cumulative direct + single + double:

~~~text
16,524 blocks
8,460,288 bytes
~~~

This cumulative size is:

~~~text
CFS_MAX_FILE_SIZE
~~~

and is the hard limit used by the whole-file `cfs_write` API and `cfs_truncate`.

## Triple indirection

After the double-indirect range, `file_lba` uses `triple_indirect`.

The tree is:

~~~text
inode.triple_indirect
    -> level-1 table
        -> level-2 table
            -> data block
~~~

The triple region contributes:

~~~text
128³ = 2,097,152 blocks
~~~

The full address tree can describe:

~~~text
12 + 128 + 16,384 + 2,097,152
= 2,113,676 blocks
= 1,082,202,112 bytes
≈ 1.008 GiB
~~~

This is the structural pointer-tree ceiling, not the effective public-API file-size limit.

## Effective public file-size limits

There are three distinct ceilings in current code.

### Whole-file APIs

`cfs_write` and `cfs_truncate` enforce:

~~~text
CFS_MAX_FILE_SIZE
= 8,460,288 bytes
≈ 8.07 MiB
~~~

This stops exactly after double indirection.

### Incremental write/read APIs

`cfs_write_at` and `cfs_read_at` use:

~~~text
CFS_MAX_FILE_BYTES
= CFS_DATA_SECTORS × 512
= 536,444,416 bytes
≈ 511.6 MiB
~~~

Crucially, `CFS_DATA_SECTORS` here is the **legacy compile-time 512-MiB geometry constant**, not `fs->super.data_sectors`.

Therefore a larger v5 filesystem does not increase this API ceiling.

Incremental writes can exercise triple indirection, but only up to the legacy-derived ~511.6-MiB limit.

### Pointer-tree limit

`file_lba` itself permits up to:

~~~text
CFS_MAX_BLOCKS_V4 = 2,113,676 blocks
~~~

subject also to:

~~~text
block < fs->super.data_sectors
~~~

That is broader than the public incremental API on normal volumes.

The name `CFS_MAX_BLOCKS_V4` is historical/misleading because the value includes triple indirection used by current code.

## Block allocation

`file_lba(..., alloc=1)` allocates missing structures lazily.

A newly required data or pointer block is obtained through `block_alloc`.

`block_alloc`:

1. scans bitmap bits from `alloc_hint`;
2. marks the selected bit allocated;
3. zeroes the full 512-byte block;
4. if the zero write fails, attempts to clear the bitmap bit;
5. advances `alloc_hint`;
6. returns the absolute data-region LBA.

This means newly reused blocks are cleared before being exposed through an inode.

## Lazy tree construction

The indirect trees are created only as needed.

For the first single-indirect block:

1. allocate `inode.indirect`;
2. read its selected pointer;
3. allocate a data block when zero;
4. store the new LBA in the pointer table.

Double indirection adds one intermediate table.

Triple indirection can add two intermediate table levels before allocating the data block.

All pointer-table writes use the same write-through cache as normal filesystem metadata.

## Allocation rollback gaps

Tree growth is not an all-or-nothing allocation transaction.

Examples:

- a new data block may be allocated successfully and then `ptr_block_set` may fail;
- a new intermediate pointer table may be allocated but not yet persisted in its parent;
- the in-memory inode may receive a newly allocated root pointer but later inode persistence may fail.

In those failure windows, the bitmap can retain allocated blocks that are no longer reachable from persistent inode metadata.

fsck detects such leftovers as:

~~~text
bitmap leak
~~~

but does not automatically repair them.

## Non-sparse invariant

The current fsck model expects ordinary file blocks to exist for the range implied by `inode.size`.

For direct blocks, fsck explicitly reports:

~~~text
size vs blocks
~~~

when a required pointer is zero.

The filesystem does not define an on-disk sparse-hole representation.

## Distant `write_at` can violate that invariant

`cfs_write_at` updates:

~~~text
inode.size = offset + size
~~~

when extending a file.

It then allocates only blocks actually touched starting at `offset`.

It does **not** allocate or zero every missing block between the old EOF and a distant new offset.

For example, writing one byte at block 8 of an empty file can leave direct blocks 0..7 unallocated while the inode size says those bytes exist.

Later sequential reads can encounter missing pointers and return:

~~~text
CFS_ECORRUPT
~~~

and fsck can report:

~~~text
size vs blocks
~~~

This is not working sparse-file support; it is a current extension-path gap.

A safe caller should currently avoid extending a file across unallocated full-block gaps.

## Shrinking through `cfs_write`

For whole-file replacement with a smaller size, `cfs_write`:

1. calculates old and required block counts;
2. rewrites/allocates all blocks still needed;
3. walks old blocks beyond the new EOF and frees their bitmap bits;
4. calls `inode_ptr_prune`;
5. persists the smaller inode.

For files already within `CFS_MAX_FILE_SIZE`, this prunes direct/single/double metadata according to the new block count.

## Pointer pruning

`inode_ptr_prune` can:

- clear unused direct pointers;
- clear unused entries from a single-indirect table;
- free a whole double-indirect tree when no longer needed;
- free unnecessary double-indirect intermediate tables;
- clear unused double-indirect leaf pointers.

If the new size needs at most 12 blocks, it calls `inode_ptr_free`, which also frees the triple-indirect pointer-tree metadata.

## Triple-size files and whole-file rewrite

A file enlarged with `cfs_write_at` beyond:

~~~text
CFS_MAX_FILE_SIZE
~~~

cannot subsequently be replaced by `cfs_write`.

Before beginning the write, `cfs_write` explicitly treats:

~~~text
inode.size > CFS_MAX_FILE_SIZE
~~~

as:

~~~text
CFS_ECORRUPT
~~~

Likewise, `cfs_truncate` eventually delegates to `cfs_write`.

So triple-indirect files can be created by incremental writes, but the whole-file rewrite/truncate path does not support them.

Unlink remains the practical release path.

## Inode release for files

`inode_release` handles regular files by computing the number of blocks implied by file size and then:

1. resolving each block through `file_lba(..., alloc=0)`;
2. freeing every reachable data block;
3. freeing indirect pointer-table structures through `inode_ptr_free`;
4. zeroing the inode;
5. encoding it back as a free inode.

For a triple-indirect file this means the data leaves are freed first and the pointer-table hierarchy is freed afterward.

## Pointer-table teardown

`inode_ptr_free` directly frees:

- the single-indirect table;
- all second-level tables plus the double-indirect root;
- the triple-indirect pointer structure through `free_ptr_levels`.

For triple indirection, `free_ptr_levels` recursively frees pointer-table blocks.

It does not free triple data leaves by itself; regular-file release already freed those leaves by iterating the file blocks.

That separation is correct only when the caller has handled the data blocks first.

## Directory-release leak at the single-indirect level

Directories can grow to:

~~~text
12 direct + 128 single-indirect data blocks
~~~

`dir_remove` clears directory entries but does not free empty directory blocks or shrink the pointer structure.

When an empty directory is finally released, `inode_release` takes its non-file branch and frees only:

~~~text
direct[0..11]
~~~

before calling `inode_ptr_free`.

For `n->indirect`, `inode_ptr_free` frees the pointer-table block itself but does **not** walk and free the directory data blocks referenced by that table.

Therefore a directory that previously grew beyond 12 data blocks can leave its single-indirect directory blocks allocated after `rmdir`.

Those blocks become unreachable bitmap allocations and can be reported by fsck as leaks.

This is a current resource-lifetime bug, not intended directory semantics.

## `block_free` behavior

Freeing a block only clears its bitmap bit.

The old 512 bytes are not zeroed at free time.

They are zeroed later if the block is selected again by `block_alloc`.

Consequences:

- ordinary reallocation does not expose stale contents to a new file;
- raw disk examination can still recover old bytes from a free block before reuse;
- a metadata corruption that references a freed block could expose stale content.

There is no secure-delete guarantee.

## fsck block ownership model

fsck maintains a “seen” bitmap independently from the allocation bitmap.

For every referenced data or pointer block it checks:

1. LBA lies in the data region;
2. the block has not already been referenced;
3. the allocation bitmap marks it used.

Violations are reported as:

~~~text
block lba
duplicate block
bitmap missing
~~~

After walking every inode, fsck scans the allocation bitmap for used blocks that were never seen.

That reports:

~~~text
bitmap leak
~~~

This catches many allocation-lifetime bugs even though fsck does not repair them.

## fsck traversal of pointer trees

For:

~~~text
inode.indirect
~~~

fsck walks one pointer-table level.

For:

~~~text
inode.double_indirect
~~~

it walks two.

For:

~~~text
inode.triple_indirect
~~~

it walks three.

Both pointer tables and data blocks count as owned blocks.

A pointer-table block is therefore not “free metadata”; it consumes ordinary data-region capacity and must have a bitmap bit.

## fsck file-size checks

For files, fsck computes a maximum size from the mounted volume:

~~~text
max_bytes = super.data_sectors × 512
~~~

capped at:

~~~text
0xFFFFFFFF
~~~

because inode size is a 32-bit field.

It also verifies direct pointers against the number of blocks required by file size.

However, the current direct-pointer size-vs-block check is not mirrored with the same completeness across all single/double/triple positions; the deeper trees are primarily ownership/range traversed.

Therefore fsck's validation of large-file pointer completeness is not as strict as its direct-block validation.

## Validation evidence

### Indirect addressing

`test_cfs_indirect.c` writes and reads:

~~~text
70,000 bytes
~~~

which exceeds direct-only capacity and requires the single-indirect path.

It then runs fsck.

This validates the single-indirect implementation.

### Whole-file maximum

`test_cfs_maxwrite.c` probes exactly:

~~~text
CFS_MAX_FILE_SIZE
CFS_MAX_FILE_SIZE + 1
~~~

and verifies that the first succeeds while the second returns `CFS_EFBIG`.

The maximum-size success case reaches through double indirection.

### Inode checksum

`test_cfs_fsck.c` corrupts inode 1's checksum and verifies read-only fsck detection.

### Missing dedicated triple test

There is currently no dedicated `test_cfs_triple`, large-`write_at` boundary test or sparse-gap test in the source tree.

Triple-indirect behavior is implemented, but it has materially less explicit test coverage than single/double paths.

## Complexity

### Inode allocation

~~~text
O(number of inode slots)
~~~

with a fixed current maximum of 2048.

### Direct block lookup

~~~text
O(1)
~~~

with no pointer-block read.

### Single indirection

Conceptually O(1), requiring one pointer-table access.

### Double indirection

Conceptually O(1), requiring up to two pointer-table accesses.

### Triple indirection

Conceptually O(1), requiring up to three pointer-table accesses.

The asymptotic lookup remains constant because tree depth is fixed, although I/O cost increases by level and cache behavior matters.

### File release

Regular-file release is:

~~~text
O(number of file blocks)
~~~

because `inode_release` resolves and frees each data block before tearing down pointer tables.

## Current limitations

At the documented revision:

- inode table is fixed at 2048 entries;
- only 2047 non-root objects can exist;
- inode allocation is a full linear scan;
- inode size is fixed at 128 bytes;
- inode size field is 32-bit;
- block pointers are 32-bit absolute LBAs;
- pointer blocks have no independent checksum or type tag;
- all data and pointer blocks share one bitmap;
- allocation rollback is incomplete across multi-block tree growth;
- no sparse-file representation exists;
- distant `write_at` can create missing interior blocks;
- whole-file APIs stop at ~8.07 MiB;
- incremental APIs use a legacy-derived ~511.6-MiB constant rather than dynamic v5 capacity;
- triple-indirect files cannot be rewritten/truncated through the whole-file API;
- triple indirection lacks dedicated boundary testing;
- freeing does not zero data immediately;
- directory release can leak single-indirect data blocks;
- fsck does not fully verify required occupancy for every deep pointer position.

## Roadmap boundary

A stronger inode/block layer should consider:

- dynamic or bitmap-indexed inode allocation;
- a unified file-size contract based on mounted geometry;
- 64-bit file sizes and LBAs;
- explicit sparse-hole semantics or rejection of distant extension;
- complete rollback for failed tree growth;
- checksummed or otherwise protected pointer blocks;
- shared generic traversal for allocation, pruning, fsck and release;
- correct release of all directory indirect data blocks;
- truncation support for triple-indirect files;
- exact deep-tree occupancy validation in fsck;
- dedicated direct/single/double/triple boundary tests;
- crash/failure injection at every pointer-allocation stage.

Those are roadmap items until implemented and reproducibly validated.

## Source map and revision note

`kernel/fs/cfs_format.h` defines the 128-byte persistent inode ABI and checksum. `kernel/fs/storage_limits.h` defines inode count, pointer fan-out and size constants. `kernel/fs/cfs.c` implements inode I/O, allocation, block mapping, growth, pruning and release. `kernel/fs/cfs_fsck.c` validates inode checksums, block ranges, duplicate ownership and bitmap leaks. `tools/test_cfs_indirect.c`, `test_cfs_maxwrite.c` and `test_cfs_fsck.c` provide the principal host-side evidence.

All current-behavior claims in this chapter were reconciled against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.
