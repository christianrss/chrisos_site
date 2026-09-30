---
id: chrisfs-fsck
lang: en
type: technical-chapter
volume: 06-storage
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/fs/cfs.h
  - kernel/fs/cfs.c
  - kernel/fs/cfs_format.h
  - kernel/fs/cfs_fsck.c
  - kernel/fs/fs_lock.h
  - kernel/fs/storage_limits.h
  - tools/test_cfs_fsck.c
  - tools/test_cfs_journal.c
  - tools/test_cfs_paths.c
  - tools/test_cfs_v5.c
  - tools/test_fuzz_cfs.c
symbols:
  - cfs_fsck
  - cfs_fsck_reason
  - fsck_maps_reset
  - note_block
  - note_ptr_table
  - check_dirents
  - walk_dir
  - cfs_super_decode
  - cfs_inode_decode
depends_on:
  - chrisfs
  - chrisfs-superblock
  - chrisfs-inodes
  - chrisfs-directories
  - chrisfs-journal
  - chrisfs-cache
related:
  - block-storage
  - resource-lifetime
  - testing-validation
---

# ChrisFS consistency checking and corruption detection

## Scope

`cfs_fsck` is the current ChrisFS consistency checker.

It is primarily a **read-only validator**. It does not rebuild metadata, rewrite the bitmap, reconnect orphaned files, repair checksums or choose winners when two structures disagree.

Its job is to detect classes of inconsistency across:

- the superblock;
- journal state;
- allocation bitmap;
- inode table;
- direct and indirect block ownership;
- root inode type;
- the reachable directory graph;
- allocation leaks.

The checker runs against an already mounted `Cfs` object and enters the same global filesystem lock used by normal ChrisFS operations.

This chapter documents behavior at ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

![ChrisFS fsck validation flow](../../assets/diagrams/chrisfs-fsck-en.svg)

## Return contract

A clean filesystem returns:

~~~text
CFS_OK = 0
~~~

If structural inconsistencies are detected, `cfs_fsck` usually returns a **positive count of detected errors**.

Fatal operational failures instead return normal negative ChrisFS status codes such as:

~~~text
CFS_EIO
CFS_EINVAL
CFS_ENOSPC
CFS_ENOTMOUNTED
CFS_ECORRUPT
~~~

This produces two distinct result classes:

~~~text
0       clean
> 0     consistency errors detected
< 0     checker could not complete normally
~~~

## First-reason string

`cfs_fsck_reason()` exposes a static human-readable reason.

`set_reason` writes only when the reason buffer is still empty.

Therefore:

~~~text
cfs_fsck_reason()
~~~

reports the **first detected reason**, not necessarily the only reason or the most severe reason.

The numeric positive return can count more problems than the one visible in the reason string.

On a clean result, the reason becomes:

~~~text
clean
~~~

## Read-only design

The checker performs block-device reads and updates only in-memory maps/state.

It does not call the normal metadata writers or `bd_write`.

`tools/test_cfs_fsck.c` records the block-device write count, corrupts an inode checksum, runs fsck and verifies that the write count does not increase.

That test establishes an important current property:

~~~text
fsck detects but does not repair
~~~

## Global serialization

`cfs_fsck` begins with:

~~~text
CFS_LOCK()
~~~

The checker therefore runs under the same global reentrant filesystem lock as normal ChrisFS APIs.

That protects shared checker/runtime assumptions from concurrent public ChrisFS mutations.

It also means fsck blocks ordinary filesystem activity while it performs potentially large full-volume scans.

## Mounted-filesystem requirement

fsck requires:

- non-null `Cfs`;
- `fs->mounted != 0`;
- non-null backing device.

Otherwise it returns:

~~~text
CFS_ENOTMOUNTED
~~~

with reason:

~~~text
not mounted
~~~

It is not currently a standalone tool that accepts an arbitrary unmounted raw device.

## Superblock stage

fsck reads LBA 0 directly from the backing block device.

It then calls:

~~~text
cfs_super_decode
~~~

This validates:

- ChrisFS magic;
- supported version;
- 512-byte sector size;
- superblock checksum;
- legacy fixed geometry for v3/v4;
- v5 inode count;
- v5 root inode number;
- v5 region ordering/capacity invariants.

If decode fails, fsck returns:

~~~text
CFS_ECORRUPT
~~~

with reason:

~~~text
super checksum
~~~

The reason string is broader than the exact decoder failure: unsupported version, invalid geometry and checksum errors are all collapsed into that single fsck-facing reason.

## Mounted-device size assumption

`cfs_mount` already verifies that:

~~~text
dev->sector_count >= super.total_sectors
~~~

before the filesystem becomes mounted.

fsck relies on that mounted-state precondition rather than repeating the same explicit sector-count comparison.

If the backing device changes after mount, later direct reads can still fail with an I/O error.

## Geometry copied into checker globals

After superblock decode, fsck records:

~~~text
data_lba
data_sectors
inode_lba
bitmap_lba
bitmap_sectors
journal_lba
~~~

in checker-global variables.

These globals are later used by:

- block range validation;
- allocation ownership accounting;
- inode reads;
- directory traversal.

Because the checker uses global scratch state, the global filesystem lock is part of its current correctness model.

## Bitmap working maps

fsck keeps two bitmaps in memory.

### On-disk allocation map

~~~text
g_bitmap
~~~

is a full copy of the filesystem allocation bitmap.

### Seen map

~~~text
g_seen
~~~

starts at zero and is populated as fsck discovers blocks referenced by inodes and pointer trees.

At the end, the two maps are compared.

This gives fsck its main cross-structure ownership invariant:

~~~text
referenced block <=> allocated block
~~~

subject to the checker limitations described later.

## Fixed versus dynamic map storage

For legacy-sized bitmaps up to:

~~~text
CFS_BITMAP_SECTORS = 256
~~~

fsck uses static arrays.

For larger v5 bitmaps it allocates both maps dynamically.

Required memory is approximately:

~~~text
2 × bitmap_sectors × 512 bytes
~~~

plus the checker’s other global buffers.

If either dynamic allocation fails, fsck returns:

~~~text
CFS_ENOSPC
~~~

with reason:

~~~text
bitmap size
~~~

This error means checker working-memory exhaustion, not necessarily filesystem data-space exhaustion.

## Bitmap-size arithmetic

Before allocating maps, fsck rejects:

~~~text
bitmap_sectors == 0
~~~

and guards:

~~~text
bitmap_sectors * 512
~~~

against 32-bit overflow.

The superblock decoder already performs additional geometry checks.

## Journal-state check

Before loading the allocation bitmap, fsck reads the journal header sector directly.

It inspects:

~~~text
magic
state
~~~

and reports:

- `journal magic` for unexpected nonzero magic;
- `journal dirty` for BEGIN;
- `journal pending replay` for COMMIT.

Zero magic and CJNL EMPTY are accepted.

## Journal check is intentionally shallow

The fsck journal check does **not** recompute the journal header checksum.

It also does not validate:

- sequence;
- record count;
- record payload checksums;
- target LBAs;
- record-slot bounds.

Mount-time `jnl_replay` is stricter about some of these details.

Therefore “fsck journal validation” is currently a state precheck, not a full journal-integrity audit.

## Superblock clean flag is not an fsck error

Although `CfsSuper` contains:

~~~text
clean
~~~

`cfs_fsck` does not add an error merely because:

~~~text
super.clean == 0
~~~

A dirty clean flag with an otherwise EMPTY journal and consistent structures can therefore produce:

~~~text
CFS_OK
reason = "clean"
~~~

The flag can still be used by higher-level boot logic as a reason to invoke fsck; fsck itself decides consistency from the structures it checks.

## Loading the allocation bitmap

fsck reads every declared bitmap sector directly through `bd_read`.

A failure returns:

~~~text
CFS_EIO
~~~

with reason:

~~~text
bitmap io
~~~

The checker bypasses the normal ChrisFS sector cache for this inspection.

## Inode-table scan

The checker iterates:

~~~text
id = 0 .. 2047
~~~

For each inode it reads the containing sector and decodes the selected 128-byte record.

There are four inodes per 512-byte sector, but the current implementation performs a block-device read for each inode ID.

So a complete scan can read the same inode-table sector four times.

This is correct but I/O-inefficient.

## Inode checksum

Every inode is decoded with:

~~~text
cfs_inode_decode
~~~

which verifies the 124-byte inode payload checksum.

Failure increments the error count and records:

~~~text
inode checksum
~~~

The checker then skips deeper checks for that inode.

## Free inodes

If an inode decodes correctly and has:

~~~text
type == CFS_INODE_FREE
~~~

fsck skips it.

It does not require all other fields of a free inode to be zero.

Consequently, a checksum-valid free inode with stale pointers is not itself reported as malformed.

If those stale blocks are still marked allocated but are not referenced by another live inode, the final bitmap-leak pass can still detect the allocation leak.

## Inode type

Non-free inodes must be:

~~~text
CFS_INODE_FILE
CFS_INODE_DIR
~~~

Any other type produces:

~~~text
inode type
~~~

and the inode is not traversed further.

## File-size upper bound

For each live inode, fsck computes:

~~~text
max_bytes = data_sectors × 512
~~~

capped at:

~~~text
0xFFFFFFFF
~~~

because the persistent inode size field is 32-bit.

If inode size exceeds that limit, fsck reports:

~~~text
size vs blocks
~~~

This is a volume-relative plausibility bound.

## Direct-block file-size validation

For regular files, fsck computes:

~~~text
need = ceil(size / 512)
~~~

Then for the 12 direct pointers:

- if the direct position is required by size, pointer must be nonzero;
- if it lies beyond EOF, pointer must be zero.

Violations report:

~~~text
size vs blocks
~~~

This is the strictest current size-versus-block validation in the checker.

## Indirect-size validation is less complete

After the direct-pointer checks, fsck traverses any nonzero:

- single-indirect tree;
- double-indirect tree;
- triple-indirect tree.

But it does **not** derive the exact required occupancy of those trees from file size.

Therefore a file can have:

- a size requiring indirect blocks while required indirect leaves are missing;
- extra indirect blocks beyond EOF;

without necessarily receiving a `size vs blocks` error, as long as the blocks that do exist are internally range/bitmap consistent.

The inode chapter documents the same asymmetry from the file-I/O side.

## Direct block ownership

A valid referenced data block passes through:

~~~text
note_block
~~~

That function verifies:

1. LBA is inside the declared data region;
2. block has not already been seen;
3. allocation bitmap marks it allocated.

Failures produce:

~~~text
block lba
duplicate block
bitmap missing
~~~

respectively.

## Duplicate-block detection

The seen bitmap treats every referenced data-region sector as a single-owner object.

If two file pointers, directory pointers or pointer-table entries reference the same block, the second reference reports:

~~~text
duplicate block
~~~

There is no legitimate shared-data-block or reflink model in current ChrisFS.

## Bitmap-missing detection

If metadata references a valid data-region LBA but the allocation bitmap bit is clear, fsck reports:

~~~text
bitmap missing
~~~

This detects the reverse of a leak:

~~~text
metadata says used
bitmap says free
~~~

Such a mismatch can enable later reallocation of a still-referenced block.

## Pointer-table traversal

`note_ptr_table` validates pointer blocks recursively.

Depth values are:

~~~text
1 single
2 double
3 triple
~~~

The pointer-table block itself is first recorded through `note_block`.

Then each nonzero 32-bit child pointer is read.

At depth 1, children are treated as data blocks.

At deeper levels, children are recursively treated as pointer-table blocks.

## Pointer-table I/O

If fsck cannot read a pointer-table block, it returns:

~~~text
CFS_EIO
~~~

with reason:

~~~text
indirect io
~~~

This is fatal to the current check rather than counted as a recoverable structural error.

## Recursive scratch preservation

Pointer traversal uses one global 512-byte scratch sector.

Before descending recursively, the function copies that sector to a 512-byte local stack buffer, recurses, then restores it.

Maximum supported pointer depth is fixed and small, so stack use is bounded by the indirection depth.

## Directories and extra indirection

Runtime directory lookup supports only:

~~~text
12 direct + 128 single-indirect blocks
~~~

However the generic inode ownership scan will also traverse nonzero:

- double-indirect;
- triple-indirect

pointers on a directory inode.

Those blocks can therefore be counted as legitimate “seen” allocations even though normal directory lookup never uses them.

fsck does not currently reject this mismatch between runtime directory semantics and generic inode pointer ownership.

## Root inode invariant

Inode 0 must be:

~~~text
CFS_INODE_DIR
~~~

If the global inode scan sees another type, it records:

~~~text
root type
~~~

The later directory walk checks the root again.

A malformed root can therefore contribute more than one counted error while still exposing the same first reason.

## Directory graph walk

After the complete inode/block ownership scan, fsck calls:

~~~text
walk_dir(root_inode)
~~~

This is a separate namespace traversal.

It uses:

~~~text
g_anc[2048]
~~~

as an ancestor stack marker.

When entering a directory, its bit becomes 1.

When leaving, it returns to 0.

## Cycle detection

If traversal reaches a directory inode whose ancestor marker is already set, fsck reports:

~~~text
dir cycle
~~~

This detects cycles along the current recursion path.

It directly addresses corruption such as a directory pointing to one of its ancestors.

## No permanent visited-directory set

`g_anc` is an ancestor set, not a global visited set.

After a directory is fully traversed, its marker is cleared.

Therefore two different parent dirents can reference the same directory inode and fsck can traverse that subtree twice without reporting “multiple parents.”

Current ChrisFS does not define directory hard links as a feature, so this is a missing namespace invariant.

A highly shared acyclic corrupted directory graph can also cause repeated subtree traversal.

## Directory-block coverage

`check_dirents` scans only:

~~~text
CFS_DIRECT_COUNT = 12
~~~

direct directory blocks.

Runtime directories can use:

~~~text
12 direct + 128 single-indirect
= 140 blocks
~~~

So namespace contents in single-indirect directory blocks are outside fsck’s directory-entry validation.

Their storage blocks are still accounted for by the generic pointer-tree ownership pass, but their names and inode references are not walked.

## Directory-entry checks

For each active dirent in the scanned direct blocks, fsck validates:

- inode ID is below 2048;
- name length is at most 64;
- referenced inode checksum decodes;
- child directories can be recursively walked.

Malformed ID or oversized name produces:

~~~text
dirent
~~~

## Incomplete name validation

fsck does not enforce all runtime path syntax on corrupted dirents.

It does not reject, for example, names containing:

- slash;
- backslash;
- embedded NUL inside the declared length;
- `.`;
- `..`.

It also treats entries with inode zero or name length zero as empty.

Thus namespace-corruption detection is narrower than path-parser validity.

## Duplicate-name detection is per block

The duplicate-name table is reset at the start of every 512-byte directory block.

Therefore fsck can detect equal names among the six dirents inside one block.

The same name appearing in two different directory blocks is not detected by this mechanism.

Runtime lookup returns the first matching entry found in scan order.

## Dirent type is not cross-checked

The persistent dirent contains a redundant one-byte type.

fsck loads the referenced inode but does not require:

~~~text
dirent.type == inode.type
~~~

Stale or corrupted dirent type metadata therefore passes this checker.

## Directory size is not reconciled

Directory inode `size` is intended to track:

~~~text
live dirent count × 80
~~~

The current fsck does not recount dirents and compare the result with directory inode size.

A directory can therefore have a checksum-valid but stale size field without being reported for that mismatch.

## Allocated-inode reachability

The global inode scan checks every live inode’s block ownership.

The directory graph walk checks only inodes reachable through the portion of the namespace it traverses.

There is no map requiring:

~~~text
every allocated non-root inode
must be reachable from root
~~~

Therefore an orphan inode can be structurally valid and own valid bitmap blocks without being reported simply for having no directory entry.

## Multiple file references

There is no inode link-count field.

fsck also does not count how many dirents reference each file inode.

Multiple namespace names pointing to one file inode are therefore not rejected as a distinct hard-link inconsistency.

## Final leak scan

After inode and namespace traversal, fsck scans every data-region bit.

If:

~~~text
bitmap = allocated
seen = not referenced
~~~

it reports:

~~~text
bitmap leak
~~~

This catches unreachable allocated blocks such as:

- failed allocation rollback;
- some release bugs;
- pointer metadata lost before linkage.

## Leak scan stops after the first leak

The final bitmap-leak loop executes:

~~~text
errors++
break
~~~

on the first leak.

Therefore multiple leaked blocks contribute only one error count from this final pass.

The reason remains the first reason encountered anywhere in fsck.

## Clean flag versus structural result

A filesystem can have a dirty superblock flag and still pass all structural checks.

Conversely, a superblock can claim clean while inode/bitmap structures are inconsistent.

Current fsck correctly focuses primarily on actual checked structures rather than trusting `clean`, but the clean flag itself is not audited as a consistency relation with journal state.

## Memory model and scalability

The dominant checker memory is:

~~~text
allocation bitmap copy
+ seen bitmap
~~~

Each uses one bit per bitmap-representable data block.

There is also a fixed name table:

~~~text
2048 × 65 bytes
≈ 130 KiB
~~~

plus ancestor markers and sector buffers.

For larger v5 volumes, bitmap working memory scales with the filesystem bitmap.

## I/O complexity

Ignoring repeated directory traversal, fsck approximately performs:

- one superblock read;
- one journal-header read;
- all bitmap-sector reads;
- 2048 inode reads;
- one read for each referenced pointer-table block;
- direct-directory-block reads during namespace traversal;
- additional child-inode reads during traversal.

The inode table itself contains only 512 sectors, so reading 2048 inode sectors is a notable avoidable factor of four.

## No cache acceleration

fsck intentionally uses direct `bd_read` calls rather than the normal ChrisFS cache.

Advantages:

- validation sees block-device contents directly;
- checker does not depend on cache replacement state.

Costs:

- repeated inode and namespace reads are not absorbed by the runtime sector cache.

## Validation evidence

### Dedicated fsck test

`tools/test_cfs_fsck.c` verifies:

- clean filesystem returns success;
- inode-checksum corruption is detected;
- reason is exactly `inode checksum`;
- fsck performs no writes.

### Journal test

`tools/test_cfs_journal.c` verifies:

- clean journal produces clean fsck;
- forced BEGIN state produces a positive result;
- reason becomes `journal dirty`.

### Path test

`tools/test_cfs_paths.c` performs normal namespace operations and requires clean fsck before and after remount.

### v5 test

`tools/test_cfs_v5.c` confirms legacy v4 compatibility and clean fsck on a normal legacy-sized image.

The larger v5 path primarily tests geometry/allocation rather than exhaustive fsck corruption cases.

### Fuzz smoke test

`tools/test_fuzz_cfs.c` generates 200 deterministic pseudo-random path-operation sequences and requires the resulting filesystem to pass fsck.

This is API fuzz smoke coverage, not raw on-disk corruption fuzzing.

## Missing corruption tests

There are no dedicated tests in the current tree for many checker reasons, including:

- `block lba`;
- `duplicate block`;
- `bitmap missing`;
- `bitmap leak`;
- `inode type`;
- `root type`;
- `dir cycle`;
- duplicate names across blocks;
- indirect-pointer corruption;
- orphan inode reachability;
- single-indirect directory dirent corruption;
- invalid dirent type;
- stale directory size;
- missing required indirect file blocks;
- extra indirect blocks beyond EOF;
- super.clean/journal-state combinations;
- large dynamic-map allocation failure.

These are natural targets for a stronger checker test suite.

## Current limitations

At the documented revision:

- validation only; no automatic repair;
- must run on a mounted filesystem object;
- first reason hides later reason categories;
- positive return count is not a complete count of every corrupted block;
- clean flag is not itself checked as an error;
- journal check does not validate header checksum or records;
- inode-table scan rereads sectors four times;
- free inode fields are not normalized/validated;
- file size is checked strictly only against direct pointers;
- required indirect occupancy is not fully validated;
- extra indirect blocks beyond EOF can be accepted as owned;
- directory double/triple pointers are not rejected;
- namespace scan covers only direct directory blocks;
- name syntax validation is incomplete;
- duplicate-name detection is block-local;
- dirent type is not checked against inode type;
- directory size is not reconciled with live entries;
- orphan allocated inodes are not rejected;
- multiple parent references to one directory are not rejected;
- multiple names for one file inode are not link-count checked;
- final bitmap-leak scan stops after the first leak;
- checker memory scales with bitmap size;
- no raw corruption fuzz suite exercises all invariants.

## Roadmap boundary

A stronger fsck should consider:

- standalone raw-device operation;
- explicit validate-only and repair modes;
- structured error reports rather than one first-reason string;
- per-error locations and inode/LBA context;
- one-pass inode-sector batching;
- exact file-size-to-direct/single/double/triple occupancy checks;
- directory pointer-level constraints;
- traversal of all runtime-supported directory blocks;
- full directory name validation;
- duplicate-name detection across the full directory;
- dirent/inode type consistency;
- root-reachability accounting for every allocated inode;
- explicit link-count/parent-count invariants;
- journal-header and record integrity checks;
- clean-flag/journal-state cross-validation;
- complete leak enumeration;
- repair policies for bitmap disagreement and orphan recovery;
- deterministic corruption injection for every reason string;
- block-image fuzzing of superblock, inode, pointer and dirent structures.

These remain roadmap items until implemented and validated.

## Source map and revision note

`kernel/fs/cfs_fsck.c` contains the checker state, ownership maps, pointer traversal, directory graph walk and final leak comparison. `kernel/fs/cfs_format.h` supplies superblock/inode decoders and geometry validation. `kernel/fs/cfs.h` defines status codes and the public fsck API. `kernel/fs/fs_lock.h` provides global serialization. The principal evidence comes from `test_cfs_fsck.c`, `test_cfs_journal.c`, `test_cfs_paths.c`, `test_cfs_v5.c` and `test_fuzz_cfs.c`.

All current-behavior claims in this chapter were reconciled against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.
