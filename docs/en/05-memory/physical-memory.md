---
id: physical-memory
lang: en
type: technical-chapter
volume: 05-memory
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/pmm.c
  - kernel/metal/pmm.h
  - kernel/metal/bootinfo.c
  - kernel/metal/bootinfo.h
  - kernel/metal/spin.c
  - kernel/metal/spin.h
  - kernel/metal/heap.c
symbols:
  - pmm_init
  - pmm_alloc
  - pmm_alloc_contig
  - pmm_alloc_dma32
  - pmm_free
  - pmm_free_contig
  - pmm_foreach_free_run
  - pmm_claim_at
  - pmm_usable_pages
  - pmm_used_pages
  - pmm_free_pages
  - pmm_selftest
  - bootinfo_phys_to_virt
depends_on:
  - atom-semiconductor
  - x86-64-memory-privilege
related:
  - hhdm
  - pmm-algorithms
  - virtual-memory
  - heap-ownership
---

# Physical memory management

## Scope

The physical memory manager (PMM) owns the question beneath virtual memory and the heap: **which physical 4 KiB frames are currently available for assignment, and which are already reserved or claimed?**

A physical frame is not a C allocation and not a virtual mapping. The PMM returns physical addresses. Other subsystems decide whether those frames back page tables, process pages, heap arenas, DMA buffers, graphics resources or other kernel state. Dereferencing ordinary RAM requires an appropriate virtual mapping, which ChrisOS commonly obtains from the Limine higher-half direct map (HHDM).

The current ChrisOS PMM is a bounded bitmap allocator with:

- 4 KiB allocation units;
- a fixed 32 GiB physical-address ceiling;
- one bit of allocation state per managed frame;
- a next-fit-like cursor for single-page allocation;
- free-run enumeration and first-fit contiguous allocation;
- a dedicated 16-page DMA32 subpool;
- interrupt-safe spinlock protection with deliberate same-CPU recursion;
- accounting for the allocatable pool;
- an early runtime self-test.

This chapter documents the implementation that exists at revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. It does not substitute a textbook buddy allocator or NUMA design for the code actually present.

## Physical frames versus virtual addresses

ChrisOS defines:

```text
PMM_PAGE     = 4,096 bytes
PMM_MAX_PHYS = 32 GiB
```

A return value from `pmm_alloc()` is a physical address aligned to 4 KiB. It is not automatically a valid pointer in the current virtual address space.

For ordinary RAM, code can use:

```text
virtual = physical + hhdm_offset
```

through `bootinfo_phys_to_virt`. That helper requires initialized boot information and performs the HHDM offset addition.

The distinction matters because physical ownership and virtual translation are independent contracts:

- PMM ownership says whether a frame may be reused;
- page tables say which virtual addresses translate to that frame;
- HHDM gives a convenient kernel alias for normal physical RAM;
- MMIO regions require device-appropriate mappings and must not be treated as ordinary RAM merely because they have physical addresses.

Unmapping a virtual page does not itself return the frame to the PMM. Conversely, allocating a frame does not automatically create a process mapping.

## Managed address space and bitmap size

The fixed 32 GiB ceiling yields:

```text
32 GiB / 4 KiB = 8,388,608 frames
```

One bit per frame requires:

```text
8,388,608 / 8 = 1,048,576 bytes
```

so `pmm_bitmap` is a static 1 MiB array.

This metadata exists regardless of how much RAM is installed. The benefit is deterministic, allocation-free PMM metadata available before the heap. The cost is a fixed 1 MiB kernel image/data footprint and an architectural limit: physical RAM at or above 32 GiB is outside this allocator's representable range and is not allocated by it.

A frame number is transformed into bitmap coordinates as:

```text
page = phys / 4096
byte = page / 8
bit  = page % 8
```

A set bit means used/reserved; a clear bit means free.

Lookup and single-bit mutation are O(1).

## Initialization strategy: start fully reserved

`pmm_init` begins by filling the entire bitmap with `0xFF`. Therefore every representable frame starts in the safest state: unavailable.

Only frames explicitly reported as `LIMINE_MEMMAP_USABLE` are released.

This ordering is safer than beginning with an all-free bitmap and trying to enumerate every possible exclusion. Unknown, firmware-owned or unsupported memory types remain reserved automatically unless the code deliberately makes them free.

The initialization sequence is:

```text
initialize PMM lock
mark all managed frames used
free_count = 0
used = 0
usable = 0

for each Limine memmap entry:
    if type == USABLE:
        release complete 4 KiB frames in that range

reserve physical 0 .. 1 MiB

for selected reserved/non-RAM types:
    mark intersecting frames used

usable = free_count
used = 0
cursor = 0

reserve dedicated DMA32 pool
```

The executable/module reservation loop is repeated in the current source. Because setting an already-used bit is idempotent, the repetition does not double-decrement the free count.

## Alignment rules for memory-map ranges

Memory-map ranges can begin or end at addresses that are not page aligned. The PMM treats usable and reserved ranges conservatively in opposite directions.

For a usable range:

```text
start = align_up(base, 4 KiB)
end   = align_down(base + length, 4 KiB)
```

Only complete frames wholly inside the usable range become free.

For a range being reserved:

```text
start = align_down(base, 4 KiB)
end   = align_up(base + length, 4 KiB)
```

Every frame touched by the protected range remains unavailable.

This prevents partial pages at firmware/device boundaries from being handed to normal allocators.

## Memory-map categories and reclamation policy

Because the bitmap starts fully used, non-USABLE Limine categories remain unavailable by default. The source also explicitly marks several categories used, including:

- reserved memory;
- ACPI NVS;
- bad memory;
- bootloader-reclaimable memory;
- executable/modules;
- framebuffer memory.

The first 1 MiB is reserved independently of the Limine type.

The current PMM has no later phase that converts bootloader-reclaimable or other reclaimable categories into general free pages. Therefore “reclaimable” in firmware/boot protocol terminology does not mean ChrisOS currently reclaims it.

The kernel executable is protected through the bootloader memory-map classification rather than by directly converting `__kernel_start` and `__kernel_end` into physical reservation ranges. Those linker symbols are logged for diagnostics.

## Accounting semantics

Three counters are exposed:

- `pmm_usable`;
- `pmm_used`;
- `pmm_free_count`.

Their meanings are narrower than “all RAM in the machine.”

After static initialization reservations, `pmm_usable` is set to the number of frames in the allocator's usable pool. `pmm_used` is then reset to zero. Static firmware/kernel reservations are therefore not counted as “used allocations” in this counter.

Normal claims increment `pmm_used` and decrement `pmm_free_count`. Normal frees perform the reverse.

The reserved DMA32 arena is claimed after `pmm_usable` is established, so its 16 pages appear as used from the allocatable pool. Under valid operations, the intended accounting relation is:

```text
pmm_usable = pmm_used + pmm_free_count
```

The relationship describes the post-initialization allocatable pool, not the whole physical address space.

## Single-page allocation

`pmm_alloc` enters the PMM critical section and calls `scan_usable_for_run(1, pmm_cursor)`.

If no frame is found at or after the cursor, it retries from physical zero.

This is a next-fit-like policy:

1. prefer free memory after the previous successful claim;
2. wrap to the beginning when necessary;
3. return zero if no usable free frame exists.

Physical address zero is not a valid allocation result because the low 1 MiB is reserved. Therefore zero can safely act as the failure sentinel.

When a run is claimed, `claim_run`:

- sets all corresponding bitmap bits;
- decrements free count;
- increments used count;
- moves `pmm_cursor` to the first byte after the claimed run.

When a lower-address frame is later freed, `pmm_free_contig` moves the cursor backward to that address. This makes recently released lower frames eligible for early reuse.

## Scanning optimization

`scan_usable_for_run` walks only Limine entries whose type is USABLE. It never searches arbitrary bitmap-clear addresses outside those ranges.

During the walk, if the current page is aligned to the first bit of a bitmap byte and that byte equals `0xFF`, the allocator skips all eight represented pages at once.

Thus a long fully allocated area can be skipped at eight-page granularity rather than checking every bit independently.

The worst-case search is still O(P) in managed usable pages, but fully used spans reduce the constant factor.

## Contiguous allocation

`pmm_alloc_contig(count)` implements a first-fitting free-run search rather than repeatedly calling the single-page allocator.

It first invokes `pmm_foreach_free_run`, whose callback stops on the first run with at least `count` pages. The chosen run is then claimed with `pmm_claim_at`.

If that path does not produce an allocation, the code falls back to `scan_usable_for_run(count, 0)`.

A contiguous request of (k) pages therefore requires:

```text
physical interval = [base, base + k * 4096)
```

with every represented frame free at claim time.

Worst-case discovery remains O(P); validation/claim of a selected run is O(k).

Contiguity is a physical property. A virtually contiguous buffer could instead be built from unrelated frames, but devices or subsystems without scatter/gather support may require true physical contiguity.

## Enumerating free runs

`pmm_foreach_free_run(cb, user)` exposes free physical extents to higher layers.

For each USABLE memory-map region it:

1. aligns the range to full pages;
2. caps the upper address at 32 GiB;
3. scans bitmap state;
4. coalesces consecutive free pages into a run;
5. invokes the callback when the run ends;
6. stops early if the callback returns zero.

The heap uses this API during initialization. Its callback can claim a portion of a free run with `pmm_claim_at`, which creates the need for deliberate PMM lock recursion described below.

This interface avoids constructing a temporary heap-allocated extent list during early boot.

## Claim-at operation

`pmm_claim_at(phys, pages)` is an explicit ownership transition for a caller that already selected an extent.

Before mutating state it checks every requested page:

- nonzero request length;
- nonzero base;
- 4 KiB alignment and under 32 GiB through `page_in_range`;
- bitmap currently free.

Only after the complete run passes validation does it call `claim_run`. This prevents partial claims where the first pages become owned and a later collision aborts the request.

The operation is O(k) to validate plus O(k) to set state.

## Freeing frames

`pmm_free` is a one-page wrapper around `pmm_free_contig`.

The contiguous free path rejects zero base or zero count by returning. For every requested page it verifies alignment/range with `page_in_range`; an invalid physical address triggers `panic`.

If the bitmap bit is set, the function clears it, increments free count and decrements used count when nonzero.

An important current property is that **an already-free frame does not trigger a double-free panic**. The code simply leaves it free. There is also no allocation-owner/provenance table proving that the caller owns the range being returned.

Therefore the PMM relies on caller discipline for ownership correctness. This differs from the heap, whose `kfree` explicitly detects a block already marked free.

A future PMM hardening layer could add allocation tags, debug poisoning, owner IDs or strict double-free assertions.

## Locking and same-CPU recursion

PMM state is shared and protected by `pmm_lock`.

The outermost `pmm_enter`:

1. determines the current CPU index;
2. saves RFLAGS/interrupt-enable state and executes `cli` through `irq_save`;
3. acquires the spinlock;
4. records recursion depth 1.

If the same CPU enters PMM again while its depth is nonzero, the function increments the per-CPU depth and does not attempt to reacquire the spinlock.

Nested `pmm_leave` calls decrement depth. The outermost leave releases the spinlock and restores IF only if it had been enabled before entry.

This recursion is intentional. `heap_init` calls `pmm_foreach_free_run` while PMM is locked; its callback may call `pmm_claim_at`, which enters PMM again on the same CPU.

A normal non-recursive spinlock would deadlock in that path.

## Lock ordering with the heap

The source documents a one-way dependency:

```text
heap lock -> PMM lock
```

PMM must not allocate memory from the heap.

That direction prevents a cycle where:

```text
heap owns heap_lock and waits for PMM
PMM owns pmm_lock and waits for heap
```

The PMM bitmap, counters and recursion arrays are static specifically so the allocator can function without heap allocation.

## DMA32 reserved subpool

Some devices cannot address memory above 4 GiB. ChrisOS reserves a small DMA32 pool during PMM initialization.

The pool size is:

```text
16 pages * 4 KiB = 64 KiB
```

`pmm_reserve_dma32` claims a 16-page free run through the ordinary PMM scanner, then validates that the run ends below the 4 GiB limit.

If successful:

- `dma32_base` stores the physical base;
- the underlying 16 frames remain marked used in the global PMM bitmap;
- `dma32_free` becomes a 16-bit availability mask stored in a 32-bit integer.

Suballocations from `pmm_alloc_dma32(pages)` search this mask for consecutive 1 bits. The mask is then cleared for the selected subrange.

This creates two ownership layers:

```text
global PMM: whole 64 KiB arena is claimed
DMA32 mask: individual pages inside the arena are free/used
```

Consequently DMA32 suballocation does not increment/decrement global PMM used/free counters; those pages were already removed from the general pool when the arena was reserved.

## DMA32 limitations

The DMA32 arena is intentionally small and simple.

Requests are rejected when:

- no pool was reserved;
- page count is zero;
- more than 16 pages are requested;
- no contiguous bit run exists in the pool.

`pmm_free_dma32` returns bits to the secondary mask but never releases the backing arena to the global PMM.

The reservation algorithm first asks the general scanner for a 16-page run and only afterward checks the 4 GiB ceiling. It does not pass a “below 4 GiB” bound into the scanner itself. The current behavior is adequate for the expected memory-map ordering and small UHCI-oriented pool, but it is not a general zone allocator.

A larger system would typically model DMA zones explicitly rather than maintaining one fixed 64 KiB island.

## PMM interaction with heap reserve policy

`PMM_KEEP` is defined as 32 MiB and is used by the heap layer, not by PMM allocation itself.

The heap computes a number of pages to keep outside heap arenas and refuses to consume the PMM below that reserve. Thus:

- PMM exposes available frames;
- heap policy decides how much of that pool it may convert into heap arenas.

This separation is useful because the physical allocator does not need to know every higher-level consumer's reserve policy.

## Complexity summary

| Operation | Current strategy | Worst-case cost |
|---|---|---:|
| Bitmap state check | direct bit lookup | O(1) |
| Single-page allocate | cursor scan + wrap | O(P) |
| Contiguous allocate | free-run first-fit | O(P + k) |
| Claim known run | validate then mark | O(k) |
| Free k pages | linear clear | O(k) |
| Enumerate free runs | bitmap/memmap walk | O(P) |
| DMA32 allocate | scan 16-bit pool | O(16) |
| Counters | locked read | O(1) |

Here (P) is the number of managed pages scanned and (k) is the requested run length.

The eight-page skip for bytes equal to `0xFF` improves common used-region scanning constants but does not change the asymptotic bound.

## Fragmentation behavior

The PMM has no compaction and no buddy-order structure.

Single-page allocations can create holes throughout the physical pool. Total free page count may therefore be large while a large contiguous allocation fails.

The next-fit cursor helps distribute single-page searches and allows freed lower addresses to become early candidates, but it does not solve external fragmentation.

Consumers requiring large contiguous buffers must be prepared for failure or use architectural alternatives such as scatter/gather DMA, IOMMU mappings or earlier reservation.

## Self-test

`pmm_selftest` runs during boot immediately after `pmm_init`.

It:

1. allocates three pages;
2. verifies all three physical addresses are nonzero and distinct;
3. converts them through HHDM;
4. writes a different 64-bit signature to each page;
5. reads signatures back;
6. frees two pages;
7. allocates one page again;
8. requires the returned address to be one of the released pages;
9. logs accounting;
10. frees the remaining test allocations.

This validates basic uniqueness, HHDM-backed RAM access and reuse.

It does not prove:

- contiguous allocator correctness under fragmentation;
- DMA32 mask behavior;
- concurrent multi-CPU stress;
- double-free detection;
- memory-map overlap handling;
- RAM above the 32 GiB ceiling.

Those require separate tests if they become release-critical claims.

## Failure and misuse boundaries

The PMM uses different failure policies depending on the contract:

- allocation exhaustion returns physical zero;
- invalid contiguous free alignment/range panics;
- invalid `pmm_claim_at` request returns zero;
- repeated free of an already-clear bit is silently ignored;
- DMA32 invalid requests return zero/no-op;
- HHDM helper use before bootinfo initialization panics.

This mixture means callers must understand each API individually; “PMM errors always panic” is not true.

The most dangerous misuse is freeing a frame still referenced by a page table, DMA engine or other CPU. Bitmap correctness alone cannot detect outstanding translations or device ownership. Virtual-memory teardown therefore has to coordinate TLB invalidation/quarantine before physical reuse.

## Security and isolation implications

Physical allocator bugs cross abstraction boundaries immediately.

If one frame is allocated to two owners, a process page, page table, device buffer or kernel structure can overwrite another subsystem's data. A premature free can later become an information leak or arbitrary memory corruption when the same frame is reassigned.

The current PMM provides mutual exclusion and bitmap uniqueness for valid allocation calls, but it does not track owner identity, reference counts or zero-on-allocation policy globally. Higher layers such as process page commit explicitly zero pages when their security contract requires it.

Therefore “allocated by PMM” does not imply “sanitized for user exposure.”

## Current limitations

The current design deliberately remains small. Important limitations are:

- fixed 32 GiB physical ceiling;
- fixed 1 MiB bitmap metadata;
- no NUMA awareness;
- no buddy orders or per-CPU page caches;
- no physical compaction;
- no page reference counts;
- no ownership/provenance tags;
- no strict double-free rejection;
- no general DMA-zone allocator;
- only a 64 KiB dedicated DMA32 subpool;
- no later reclamation of bootloader-reclaimable memory;
- no automatic zeroing of every allocated frame;
- contiguous allocation remains fragmentation-sensitive.

These are implementation properties, not requirements of a PMM in general.

## Architectural evolution

A future PMM can evolve without changing the fundamental ownership contract.

Likely directions include:

- dynamic metadata sized to discovered RAM;
- explicit DMA32/normal/high zones;
- buddy allocation for efficient power-of-two contiguous runs;
- per-CPU free-page caches for reduced lock contention;
- NUMA-local pools;
- reference counts for shared frames;
- debug owner/provenance tracking;
- page poisoning and zeroing policies;
- reclaim of bootloader/firmware-reclaimable ranges after their lifetime ends.

Any replacement must preserve the ordering relationship with heap and virtual-memory teardown: a frame cannot re-enter the free pool while stale CPU/device references may still exist.

## Source map

The allocator, bitmap, cursor, DMA32 arena, counters, lock recursion and self-test are implemented in `kernel/metal/pmm.c` and declared in `pmm.h`.

`kernel/metal/bootinfo.c`/`bootinfo.h` provide the Limine memory-map entries and HHDM conversion.

`kernel/metal/spin.c`/`spin.h` define the CAS spinlock and interrupt save/restore primitives used by PMM.

`kernel/metal/heap.c` demonstrates free-run enumeration, recursive claim-at use and the 32 MiB higher-level reserve policy.

These implementation claims were reconciled against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.
