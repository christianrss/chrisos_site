---
id: chrisfs-cache
lang: en
type: technical-chapter
volume: 06-storage
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/fs/cfs.h
  - kernel/fs/cfs.c
  - kernel/fs/fs_lock.h
  - kernel/fs/storage_limits.h
  - tools/test_cfs_host.c
  - tools/test_cfs_lock.c
  - tools/test_cfs_indirect.c
symbols:
  - CfsCacheLine
  - Cfs
  - cache_reset
  - cache_drop_lba
  - cache_victim
  - cache_read
  - cache_write_raw
  - cache_write
  - cfs_cache_hits
  - cfs_cache_misses
  - CFS_READAHEAD
  - bitmap_get
  - bitmap_set
  - block_alloc
  - block_free
  - alloc_hint
  - CFS_LOCK
depends_on:
  - chrisfs
  - chrisfs-superblock
  - chrisfs-inodes
  - chrisfs-journal
related:
  - chrisfs-directories
  - chrisfs-fsck
  - block-storage
  - spinlocks
---

# ChrisFS cache and block allocation

## Scope

ChrisFS combines two small but central mechanisms in the mounted `Cfs` object:

- a 64-line sector cache;
- a bitmap allocator with a moving allocation hint.

The cache is intentionally simple:

- one 512-byte sector per line;
- linear tag lookup;
- write-through behavior;
- no dirty lines;
- approximate LRU replacement using an age counter.

The allocator is similarly compact:

- one bit per data-region sector;
- allocation and free routed through the same cached bitmap sectors;
- one `alloc_hint` to avoid restarting every search at bit zero.

These mechanisms are tightly coupled to the journal and global filesystem lock. Cache writes are the interception point used by journaling, while allocation mutates bitmap sectors through that same write path.

This chapter documents ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

![ChrisFS cache and allocator](../../assets/diagrams/chrisfs-cache-en.svg)

## In-memory cache structure

Each cache line is:

~~~text
data[512]
lba
age
valid
~~~

The number of lines is fixed by:

~~~text
CFS_CACHE_LINES = 64
~~~

Therefore the payload capacity is exactly:

~~~text
64 × 512 = 32,768 bytes
= 32 KiB
~~~

plus tag/age/valid metadata and normal C-structure padding.

There is no dynamically sized cache based on RAM or device capacity.

## Cache belongs to one mounted Cfs object

The cache array lives inside:

~~~text
struct Cfs
~~~

along with:

- the mounted superblock;
- shared 512-byte scratch sector;
- age clock;
- hit/miss counters;
- journal state;
- allocation hint.

The cache is therefore per mounted `Cfs` object, not process-global.

The filesystem lock is global, however, so two independent mounted `Cfs` instances are still serialized by the current lock design.

## Cache reset

`cache_reset`:

- sets cache clock to zero;
- resets hit counter;
- resets miss counter;
- marks all 64 lines invalid;
- clears each stored LBA and age.

It does not zero each 512-byte line payload because invalid lines are never consulted.

`cfs_mount` calls `cache_reset` before journal replay.

That prevents stale cache content from a previous mount state from influencing the newly mounted filesystem.

## Tag lookup

`cache_read` linearly scans all 64 cache lines.

For every line whose:

~~~text
valid == 1
&& line.lba == requested_lba
~~~

it selects the copy with the greatest age.

Normally there should be at most one valid line for an LBA.

The “greatest age” selection plus later duplicate invalidation is defensive behavior against duplicate cache lines.

## Duplicate invalidation

On a cache hit, `cache_read` performs a second full scan and invalidates any other valid line with the same LBA.

On miss and on raw writes, `cache_drop_lba` invalidates every matching line before installing a new copy.

So the implementation aggressively restores the invariant:

~~~text
at most one valid cache line per LBA
~~~

even if an earlier bug or bypass path created duplicates.

## Hit path

On hit:

1. increment `cache_hits`;
2. invalidate duplicate copies;
3. increment global cache clock;
4. store that age in the winning line;
5. copy 512 bytes to the caller buffer.

The hit path does not touch the backing `BlockDevice`.

## Miss path

On miss:

1. increment `cache_misses`;
2. invalidate any stale matching line;
3. choose a victim;
4. issue one-sector `bd_read`;
5. populate the victim;
6. increment age clock;
7. copy the cached payload to the caller.

If `bd_read` fails, the selected victim is not marked valid.

The old victim content may already have been selected logically, but because no dirty writeback exists, eviction itself cannot lose unpersisted data.

## Victim policy

`cache_victim` returns:

1. the first invalid line, if any;
2. otherwise the valid line with smallest `age`.

This approximates LRU.

It is exact with respect to the monotonic age values as long as the 32-bit cache clock has not wrapped.

The implementation has no explicit wrap handling.

After approximately:

~~~text
2^32 cache touch/write events
~~~

the age counter returns to zero and “smallest age means oldest” temporarily stops matching true recency.

This is a long-running edge case rather than an ordinary workload limit.

## Write-through design

ChrisFS has no dirty cache lines.

`cache_write_raw`:

1. writes the new sector to the backing device;
2. if the write fails, returns `CFS_EIO`;
3. invalidates cached copies of that LBA;
4. chooses a victim;
5. installs the successfully written sector as a fresh cache line;
6. updates age.

The device write therefore precedes cache replacement.

A failed device write does not install the requested new bytes as valid cached state.

## Raw versus journal-aware writes

There are two write helpers.

### `cache_write_raw`

Writes directly to the home LBA and refreshes the cache.

It bypasses journal interception.

Used by mechanisms such as:

- journal header/record management;
- replay;
- selected superblock writes.

### `cache_write`

When:

~~~text
jnl_active == 1
&& jnl_data == 0
~~~

it first calls:

~~~text
jnl_log(...)
~~~

and only then calls:

~~~text
cache_write_raw(...)
~~~

This makes the cache write layer the central interception point for current journal coverage.

The journal chapter explains why this does not provide full transactional ordering.

## No delayed writeback

Because every normal write reaches `bd_write` immediately:

- eviction never needs to flush a dirty line;
- `cfs_sync` does not iterate cache lines;
- there is no dirty-list state;
- cache memory pressure cannot itself trigger persistence work.

`cfs_sync` simply delegates to:

~~~text
bd_flush(fs->dev)
~~~

to ask the underlying block layer to flush its own state.

## Read-ahead is a separate path

Aligned file reads can bypass the one-sector cache.

`cfs_read_at` detects a run of physically contiguous file blocks and reads up to:

~~~text
CFS_READAHEAD = 16 sectors
~~~

in one `bd_read`.

Maximum run payload:

~~~text
16 × 512 = 8192 bytes
= 8 KiB
~~~

The buffer is the global static:

~~~text
g_cfs_ra[8192]
~~~

rather than a per-`Cfs` allocation.

## Read-ahead requires physical contiguity

The code begins with one mapped file block and extends the run only while:

~~~text
next_lba == first_lba + run
~~~

and each next block:

- resolves successfully;
- lies inside the data region;
- fits in the requested read amount;
- keeps the run below 16 sectors.

Logical adjacency in the file is not enough.

Fragmented files fall back to the ordinary one-sector cache path.

## Read-ahead bypasses cache population

When a multi-sector read-ahead run succeeds, ChrisFS:

1. performs direct `bd_read` into `g_cfs_ra`;
2. calls `cache_drop_lba` for every sector in the run;
3. copies the buffer to the caller.

It does **not** populate those sectors into the cache.

This design avoids stale cache copies after the bypass, but repeated large sequential reads do not automatically warm the sector cache.

## Cache counters exclude read-ahead bypasses

`cache_hits` and `cache_misses` are updated only inside `cache_read`.

A direct multi-sector read-ahead:

- is a physical device read;
- is not a cache hit;
- is not a cache miss according to these counters.

Therefore the counters measure one-sector cache activity, not total filesystem I/O behavior.

They should not be interpreted as a complete device-I/O hit ratio.

## Cache counter API

The public getters are:

~~~text
cfs_cache_hits()
cfs_cache_misses()
~~~

Both enter the global filesystem lock.

That keeps counter reads consistent with cache activity and permits reentrant calls on the same lock owner.

The host test verifies that a normal mount/write/read sequence produces at least one hit and one miss.

It does not assert an exact replacement trace.

## Bitmap structure

Allocation state is stored as one bit per data-region sector.

For data-region-relative block index `i`:

~~~text
bitmap sector = bitmap_lba + i / 4096
byte offset   = (i / 8) % 512
bit offset    = i % 8
~~~

because:

~~~text
512 bytes × 8 = 4096 block bits per bitmap sector
~~~

A set bit means allocated.

A clear bit means available.

## Absolute and relative addresses

The allocator operates on a relative bitmap index.

Allocated blocks are returned as absolute filesystem-visible LBAs:

~~~text
absolute_lba = super.data_lba + index
~~~

Free performs the inverse:

~~~text
index = lba - super.data_lba
~~~

with a data-region range check first.

## Bitmap reads use the cache

`bitmap_get` calls:

~~~text
cache_read(fs, bitmap_sector, fs->sector)
~~~

and then extracts one bit.

Sequential allocation therefore repeatedly references the same bitmap sector while scanning nearby bits.

After the first miss, following bit probes in that sector can be cache hits.

This is important because one bitmap sector represents 4096 allocatable data sectors.

## Bitmap writes are read-modify-write

`bitmap_set`:

1. reads the containing bitmap sector through the cache;
2. modifies one bit in `fs->sector`;
3. writes the entire 512-byte bitmap sector through `cache_write`.

One block allocation or free therefore causes a full-sector bitmap write.

If journaling is active with metadata logging enabled, that entire bitmap sector can also consume one journal record.

## Allocation hint

The mounted `Cfs` contains:

~~~text
uint32_t alloc_hint
~~~

A source comment explains why it exists:

the allocator previously restarted every search at block zero, making multi-megabyte file copies effectively quadratic enough to stall the installation path.

With the hint, allocation usually continues near the previous successful allocation.

## Initial hint

`cfs_mount` clears the complete `Cfs` object before initialization.

There is no later explicit `alloc_hint` assignment during mount.

Therefore the initial value is:

~~~text
0
~~~

The root directory data block is already marked allocated in the bitmap, so the first ordinary allocation typically skips index 0 and finds the next free index.

## Allocation search

`block_alloc` computes:

~~~text
start = alloc_hint
~~~

If the hint is outside the current data region, start becomes zero.

It then scans at most:

~~~text
super.data_sectors
~~~

candidate bits.

The index wraps once around the data region.

Therefore every allocation is bounded and can discover a free block anywhere in the bitmap.

## Successful allocation

When a free index is found:

1. set the bitmap bit;
2. zero a 512-byte scratch sector;
3. write zeros to the newly allocated data block;
4. set:
   ~~~text
   alloc_hint = index + 1
   ~~~
5. return the absolute data LBA.

The zero write ensures previously freed contents are not exposed through normal allocation.

## Allocation rollback

If the zeroing write for the newly allocated block fails, `block_alloc` attempts:

~~~text
bitmap_set(index, 0)
~~~

to undo the allocation.

But that rollback return value is ignored:

~~~text
(void)bitmap_set(...)
~~~

So an I/O failure during the zeroing stage can be followed by a second failure while clearing the bitmap, leaving an allocated bit for a block the caller never received.

fsck can later classify such unreachable allocation as a bitmap leak.

## Free path

`block_free` first validates the absolute LBA against the current data region.

It then computes the relative index.

If:

~~~text
index < alloc_hint
~~~

it moves the hint backward to that index.

Finally it clears the bitmap bit.

This biases future allocation toward newly created holes below the previous search frontier.

## Free does not zero the block

The free path only clears the allocation bit.

It does not overwrite the data sector.

The contents remain on disk until the block is reallocated.

Normal allocation zeroes the block before returning it, so standard reuse does not expose those old bytes.

This is not a secure-erasure mechanism.

## Allocation locality

Because successful allocation sets the hint to the following index, ordinary sequential file growth tends to obtain physically consecutive data blocks when the bitmap has a sufficiently large free run.

That has two beneficial consequences:

- fewer bitmap-sector misses during allocation;
- `cfs_read_at` can later use 16-sector contiguous read-ahead runs.

There is no extent allocator or fragmentation metric, so locality is a side effect of first-fit-from-hint rather than an explicit allocation policy.

## Fragmentation behavior

When the hint reaches allocated space, `block_alloc` continues scanning until it finds the next zero bit.

Freed lower blocks can move the hint backward.

Over time, this creates a first-fit-like reuse pattern.

There is no:

- best-fit policy;
- extent reservation;
- per-file locality group;
- free-run tree;
- fragmentation-aware placement.

The algorithm optimizes simplicity and bounded search rather than layout quality.

## Worst-case allocator complexity

One allocation can inspect up to every data-sector bit:

~~~text
O(data_sectors)
~~~

in the worst case.

However, because each cached bitmap sector contains 4096 bits and `alloc_hint` normally advances, sequential free-space allocation is much cheaper in practice.

Without the hint, allocating N sequential blocks from a growing prefix could repeatedly rescan all prior bits and approach quadratic behavior.

## Cache complexity

With a fixed 64-line array:

### Hit lookup

~~~text
O(64)
~~~

for the initial scan plus another `O(64)` duplicate cleanup.

### Miss

~~~text
O(64)
~~~

tag scan, duplicate drop and victim selection, plus one device read.

### Raw write

~~~text
O(64)
~~~

duplicate invalidation plus victim selection, plus one device write.

The constant is small and predictable, but there is no hash table or direct-mapped indexing.

## Interaction with the global filesystem lock

Public ChrisFS operations use:

~~~text
CFS_LOCK()
~~~

from `fs_lock.h`.

The lock is:

- global;
- reentrant by owner;
- spin-based with `pause`;
- shared by all current ChrisFS activity.

This is necessary for current cache/allocator correctness because the following state is shared and mutable:

- cache tags/data/ages;
- `fs->sector`;
- `alloc_hint`;
- journal state;
- global read-ahead buffer.

The lock therefore serializes otherwise independent file operations.

## Reentrant locking

`cfs_read` enters the lock and then calls `cfs_read_at`, which also enters it.

The lock tracks:

~~~text
owner
depth
~~~

and permits the same owner to re-enter.

In the kernel, owner identity is based on current CPU plus one.

The header explicitly warns not to acquire this lock from interrupt context.

## Concurrency validation

`tools/test_cfs_lock.c` runs one writer thread and one reader thread against the same mounted filesystem.

The writer repeatedly replaces an eight-byte file with:

~~~text
AAAAAAAA
BBBBBBBB
~~~

The reader verifies that every successful read contains one consistent repeated byte rather than a torn mixture.

The final filesystem must also pass fsck.

This validates coarse-grained serialization under the host lock model.

It does not validate parallel scalability because the implementation intentionally serializes the operations.

## Cache validation evidence

`tools/test_cfs_host.c` checks that after format, mount, write, remount and reads:

~~~text
cfs_cache_hits(&fs) > 0
cfs_cache_misses(&fs) > 0
~~~

That confirms both paths are exercised.

There is no dedicated cache test that asserts:

- exact LRU victim order;
- 64-to-65-line eviction boundary;
- duplicate-line repair;
- age-clock wrap;
- read-ahead/cache interaction;
- failed-write cache preservation.

## Allocation validation evidence

The host suite exercises:

- large file writes;
- directory growth;
- bitmap I/O failure;
- near-capacity namespace behavior.

`test_cfs_indirect.c` writes and reads 70,000 bytes and finishes with fsck.

The wider test suite and installation path exercise the allocation hint indirectly through large copies.

There is no dedicated unit test that explicitly measures allocation probe counts with and without fragmentation.

## Direct block-device bypasses

Not every ChrisFS read or write passes through the cache.

Examples include:

- format-time raw writes;
- some mount diagnostics;
- fsck's direct block-device inspection;
- multi-sector read-ahead.

Therefore cache coherence is maintained only for the normal runtime paths that explicitly invalidate or reset relevant lines.

The global lock prevents concurrent fsck/runtime mutation from being a supported parallel pattern.

## Current limitations

At the documented revision:

- fixed 64-line cache;
- linear cache lookup;
- 32-bit age counter with no wrap repair;
- no adaptive sizing;
- no dirty/write-back mode;
- no prefetch insertion into cache;
- read-ahead I/O excluded from hit/miss counters;
- global lock serializes every ChrisFS instance;
- one shared scratch sector per mounted `Cfs`;
- one global 8-KiB read-ahead buffer;
- allocator is bitmap first-fit-from-hint;
- worst-case allocation scan is linear in data-sector count;
- no extent allocator;
- no fragmentation metric or locality policy;
- allocation zero-write rollback can itself fail and is ignored;
- free does not securely erase old data;
- bitmap changes are full-sector read-modify-write operations;
- repeated bitmap writes can pressure the small journal;
- no dedicated cache replacement or allocator-probe test suite.

## Roadmap boundary

A stronger cache/allocation subsystem could consider:

- indexed cache lookup;
- explicit wrap-safe LRU epochs or CLOCK replacement;
- per-filesystem or per-CPU cache partitioning;
- optional write-back with explicit durability semantics;
- read-ahead cache warming;
- counters that distinguish cache reads, readahead reads and raw metadata I/O;
- extent or run-aware allocation;
- free-space summaries to avoid long bitmap scans;
- transactional allocation rollback;
- dedicated allocator fragmentation metrics;
- secure-discard support where backing devices permit it;
- finer-grained locking;
- deterministic eviction and failure-injection tests.

These remain roadmap items until implemented and validated in source.

## Source map and revision note

`kernel/fs/cfs.h` defines `CfsCacheLine`, `Cfs` and the cache counters. `kernel/fs/cfs.c` implements cache lookup/replacement, read-ahead, bitmap access, allocation and free. `kernel/fs/fs_lock.h` defines the global reentrant filesystem lock. `kernel/fs/storage_limits.h` fixes sector size and the 64-line cache. `tools/test_cfs_host.c`, `test_cfs_lock.c` and `test_cfs_indirect.c` provide the principal host-side evidence.

All current-behavior claims in this chapter were reconciled against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.
