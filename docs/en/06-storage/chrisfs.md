---
id: chrisfs
lang: en
type: technical-chapter
volume: 06-storage
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/fs/cfs.c
  - kernel/fs/cfs.h
  - kernel/fs/cfs_format.h
  - kernel/fs/storage_limits.h
symbols:
  - cfs_format
  - cfs_mount
  - cfs_read
  - cfs_write
  - cfs_fsck
depends_on:
  - block-storage
related:
  - installation-real-hardware
---

# ChrisFS: on-disk structures, allocation and journaling

## Filesystem role

A filesystem converts a block array into named persistent objects with metadata, directories and allocation rules. Its correctness must survive ordinary shutdown boundaries and, where promised, interrupted writes.

ChrisFS is the native filesystem used by the project workspace and installation path.

## Superblock

The superblock describes volume geometry and versioned format state. Current source includes fields for generation, clean status, journal location, total sectors, bitmap, inode region and data region.

The encoder writes fixed-width little-endian fields and a checksum. Decoding validates magic, version, sector size, checksum and geometry before trusting later offsets.

This is critical because corrupt geometry can turn a metadata read into an arbitrary block access.

## Dynamic geometry

Current `cfs_geom_for_count` calculates bitmap size from total sectors while keeping fixed inode and journal regions. A 512 MiB volume preserves legacy v4-compatible positions, while larger supported volumes can use a larger bitmap.

This is evidence that filesystem geometry is now computed rather than universally fixed to one historical image size. Compatibility logic remains explicit in the decoder.

## Inodes

An inode records file type, size, generation, data block references, identity/permission fields and time metadata.

Current format contains direct, indirect, double-indirect and triple-indirect references. Indirection lets a small inode address files larger than the number of direct pointers alone would permit.

```text
inode
 ├── direct blocks
 ├── indirect -> block of pointers
 ├── double indirect -> pointers -> pointers
 └── triple indirect -> three pointer levels
```

## Directories

Directory entries map names to inode numbers and file types. Path resolution parses components and repeatedly looks them up in directory objects.

Path parsing is security-sensitive because malformed names, excessive depth or invalid traversal can otherwise produce out-of-bounds accesses or policy bypass.

## Free-space bitmap

Data allocation uses a bitmap. A bit records whether a data-sector/block unit is available.

ChrisFS maintains `alloc_hint` because repeatedly scanning from zero can make large sequential copy workloads effectively quadratic. This is a performance property with architectural consequences during installation.

## Cache

The mounted `Cfs` object contains sector cache lines and hit/miss counters. Caching reduces repeated device I/O, but cache state must remain coherent with writes and journaling.

## Journal

The journal supports begin/log/commit/replay operations. Journaling does not mean every possible filesystem corruption is impossible; it defines which metadata/data updates participate in a recoverable transaction model.

A robust explanation must distinguish:

- the logical transaction;
- journal records persisted to disk;
- commit marker/order;
- application of final blocks;
- replay after an unclean mount.

## Locking

ChrisFS uses a yielding/reentrant filesystem lock in current source. Kernel holder identity incorporates CPU identity. The lock is not intended for interrupt-handler acquisition.

Filesystem locking differs from a raw spinlock because disk operations can take much longer than a short in-memory critical section.

## Permissions

The format defines read, write, execute and walk permission bits. The filesystem layer must apply those semantics consistently to path traversal and operations.

## fsck

`cfs_fsck` is a consistency validator. A filesystem checker reasons about cross-structure invariants: allocated blocks must correspond to reachable/owned metadata, references must remain in range, directories must be structurally valid and conflicting ownership must be detected.

## Format evolution

A filesystem format is an external persistent ABI. Changing a C struct is not enough. New versions must define on-disk encoding, compatibility and migration behavior.

That is why ChrisFS uses explicit encode/decode helpers rather than writing compiler-dependent struct layouts directly to disk.
