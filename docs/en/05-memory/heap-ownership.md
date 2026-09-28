---
id: heap-ownership
lang: en
type: technical-chapter
volume: 05-memory
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/heap.c
  - kernel/metal/heap.h
  - kernel/metal/pmm.c
  - kernel/metal/pmm.h
  - kernel/metal/spin.c
  - kernel/metal/spin.h
  - kernel/metal/kthread.c
  - kernel/metal/job.c
  - tools/test_pmm_heap_smp.c
symbols:
  - heap_init
  - heap_grow
  - heap_claim_run
  - add_arena_phys
  - kmalloc
  - kmalloc_in_arenas
  - kfree
  - coalesce_forward
  - heap_used_bytes
  - heap_free_bytes
  - heap_arena_count
  - heap_selftest
depends_on:
  - physical-memory
  - pmm-algorithms
  - hhdm
related:
  - spinlocks
  - resource-lifetime
  - tlb-shootdown
  - kernel-jobs-kthreads
---

# Kernel heap, ownership and allocation lifetime

## Scope

The physical-memory manager and the kernel heap solve different allocation problems.

The PMM owns physical pages. Its natural unit is 4096 bytes, and it reasons about physical addresses, free-page accounting and contiguous runs.

Kernel subsystems frequently need objects much smaller than one page: descriptors, strings, graphics buffers, compiler scratch memory, filesystem work buffers, network transfer state and private kthread stacks.

ChrisOS places a heap allocator above the PMM. The heap claims contiguous physical runs, accesses them through the higher-half direct map, subdivides them into variable-sized blocks and serializes heap metadata with a spinlock.

The current implementation is intentionally simple:

- 16-byte payload alignment;
- a 16-byte header per block;
- first-fit search;
- splitting of sufficiently large free blocks;
- forward-only coalescing;
- up to 32 arenas;
- arena growth from contiguous PMM runs;
- minimum arena size of 16 pages;
- a 32 MiB physical-memory reserve kept outside opportunistic heap growth.

![ChrisOS heap allocation lifecycle](../../assets/diagrams/heap-ownership-en.svg)

The heap is also an ownership boundary. Once PMM pages are claimed as an arena, PMM must not independently allocate those pages until the heap relinquishes them. At the current revision, heap arenas are not returned to PMM during normal operation.

## Heap metadata layout

Each heap block begins with:

~~~c
struct heap_block {
    uint64_t size;
    uint32_t used;
    uint32_t pad;
};
~~~

The structure occupies 16 bytes, matching HEAP_USER_OFF.

The user-visible pointer is therefore:

~~~text
block address + 16 bytes
~~~

and the next block is found by:

~~~text
next = current header
     + 16-byte header
     + current payload size
~~~

The payload size stored in the header does not include the header itself.

This gives the allocator a compact implicit linked structure: blocks do not store explicit next/previous pointers. Traversal derives the next address arithmetically.

## Alignment

HEAP_ALIGN is 16 bytes.

kmalloc rounds every nonzero request upward:

~~~text
need = align_up(size, 16)
~~~

The arena base is also required to be 16-byte aligned.

Because the header is exactly 16 bytes, every payload returned by user_from_block remains 16-byte aligned when block boundaries are constructed correctly.

The allocator therefore satisfies common x86-64 ABI alignment requirements for ordinary scalar, pointer and SIMD-friendly objects, although it does not provide an API for alignment greater than 16 bytes.

kmalloc(0) returns null.

## Arenas

The heap maintains a fixed array:

~~~text
HEAP_ARENA_MAX = 32
~~~

Each heap_arena stores:

- base: HHDM virtual address of the first byte;
- limit: total arena size in bytes.

The arena's backing pages must be physically contiguous because heap_grow uses pmm_alloc_contig.

The heap itself does not require neighboring arenas to be adjacent to each other.

Every arena begins as one free block:

~~~text
header at arena base
payload size = arena bytes - 16
used = 0
~~~

Once registered, that arena can be subdivided repeatedly.

## Why the heap uses HHDM

PMM allocation returns a physical address.

C code cannot assume that physical addresses are directly dereferenceable.

add_arena_phys converts the arena physical base through bootinfo_phys_to_virt.

The heap then operates entirely on the resulting kernel virtual address.

Conceptually:

~~~text
PMM physical run
      |
      v
bootinfo_phys_to_virt
      |
      v
kernel HHDM address
      |
      v
heap metadata + payloads
~~~

This makes the heap dependent on the direct-map contract documented in the HHDM chapter.

## Heap initialization

heap_init executes before normal concurrent heap use.

It:

1. initializes heap_lock;
2. clears the arena count;
3. marks the heap not ready;
4. verifies PMM has more free memory than the configured reserve;
5. scans PMM free runs through pmm_foreach_free_run;
6. claims suitable pieces through heap_claim_run;
7. falls back to heap_grow if no arena was obtained;
8. marks the heap ready;
9. tallies and logs used/free heap capacity.

The initial scan attempts to populate multiple arenas from available physical runs rather than creating only one fixed heap span.

## Physical-memory reserve

PMM_KEEP is currently:

~~~text
32 MiB
~~~

The heap converts it to pages through keep_pages.

Both heap_claim_run and heap_grow refuse to consume memory that would cross this reserve.

The intent is not to let general kernel heap growth absorb every PMM page.

This reserve remains available for allocations that specifically require raw physical pages, page tables, device structures, process backing or other non-heap uses.

The reserve is a policy boundary, not a hard physical partition. It is enforced through free-page accounting at allocation time.

## Initial run claiming

pmm_foreach_free_run invokes heap_claim_run for each usable free run.

heap_claim_run computes the maximum amount it can take while preserving PMM_KEEP.

If the resulting size is below HEAP_MIN_ARENA_PAGES, it skips that run without failing the overall scan.

HEAP_MIN_ARENA_PAGES is:

~~~text
16 pages = 64 KiB
~~~

For a usable run, the callback calls pmm_claim_at to reserve the pages in PMM accounting and then add_arena_phys to expose them as a heap arena.

If arena registration fails after claiming, the pages are returned with pmm_free_contig.

That is a concrete partial-failure rollback path.

## PMM recursion during heap initialization

A subtle interaction occurs during heap_init.

pmm_foreach_free_run holds the PMM lock while invoking its callback.

heap_claim_run can call pmm_claim_at, which enters PMM again on the same CPU.

A non-recursive spinlock would deadlock here.

The PMM handles this explicitly with per-CPU recursion depth.

At outer entry it:

1. saves local interrupt state and executes CLI;
2. acquires pmm_lock;
3. sets pmm_depth[cpu] = 1.

Nested same-CPU entry increments the depth without reacquiring the lock.

The outermost leave releases the lock and restores the previous IF state.

This recursion support exists specifically for controlled same-CPU PMM nesting. It does not make arbitrary subsystem spinlocks recursively lockable.

## Heap growth after initialization

Normal kmalloc first searches existing arenas.

If no block fits, it calls heap_grow while still holding heap_lock.

heap_grow calculates enough pages for:

~~~text
requested payload + one header
~~~

then rounds up to at least 16 pages.

It checks the PMM reserve, caps the request to available pages and asks PMM for a contiguous run.

If the requested contiguous run fails, it retries with the minimum 16-page arena.

If that also fails, heap growth fails.

Thus an allocation can fail even when PMM has many free pages if there is no sufficiently large contiguous run compatible with the reserve.

## Lock ordering

The code documents the current lock ordering directly:

~~~text
heap_lock -> PMM lock
~~~

kmalloc holds heap_lock while heap_grow calls PMM functions.

The reverse dependency must not occur.

The PMM source explicitly states that PMM must not allocate from the heap.

That gives an acyclic relationship:

~~~text
heap may enter PMM
PMM must not enter heap
~~~

If PMM called kmalloc while pmm_lock was held, another CPU could produce the cycle:

~~~text
CPU A: heap_lock -> waits for pmm_lock
CPU B: pmm_lock  -> waits for heap_lock
~~~

The absence of that reverse edge is part of heap correctness.

## First-fit allocation

kmalloc_in_arenas scans arenas in array order.

Inside each arena it scans blocks from the base forward.

The first block satisfying:

~~~text
used == 0
size >= need
~~~

is selected.

Therefore allocation policy is first-fit.

If there are A arenas and B total blocks, a worst-case unsuccessful search is O(B), bounded indirectly by heap history and arena capacity.

There is no size-segregated free list, tree, slab cache or buddy structure inside the heap.

## Splitting

Suppose a free block has size F and the aligned request is N.

The unused payload remainder is:

~~~text
leftover = F - N
~~~

The allocator creates a second free block only when:

~~~text
leftover >= HEAP_USER_OFF + HEAP_ALIGN
         >= 16 + 16
         >= 32 bytes
~~~

That ensures the remainder can hold its own 16-byte header and at least one 16-byte payload unit.

The new header is placed immediately after the allocated payload.

The selected block is resized to N and marked used.

If the remainder is smaller than 32 bytes, the whole original block becomes the allocation, so that small tail becomes internal fragmentation.

## Freeing

kfree accepts null as a no-op.

For a non-null pointer it requires:

- heap has been initialized;
- pointer is 16-byte aligned;
- pointer lies within the user-address range of some registered arena;
- computed block header is currently marked used.

A successful free clears used and runs coalesce_forward.

A detected double free causes panic.

A pointer outside every arena also causes panic.

## Pointer-validation limitation

Current kfree validation is useful but not complete.

arena_of_user verifies that the pointer is inside an arena and alignment verifies a 16-byte boundary.

The allocator then computes:

~~~text
block = user - 16
~~~

It does not first walk the arena to prove that the supplied user pointer exactly matches the payload start of a real block boundary.

Therefore an arbitrary 16-byte-aligned interior address inside an arena can cause the allocator to interpret preceding payload bytes as a heap_block header.

Depending on those bytes, the result may panic or corrupt metadata.

This is a current robustness limitation.

Possible future defenses include explicit block magic values, boundary validation by traversal, canaries or stronger allocator metadata.

## Forward-only coalescing

coalesce_forward merges a free block with immediately following free blocks.

It does not search for or merge with a preceding free block.

That makes fragmentation dependent on free order.

If block B is freed and later its preceding block A is freed, freeing A can merge A+B because B is forward-adjacent.

If A is freed first and B is freed later, freeing B does not merge backward into A.

The allocator may therefore retain adjacent free blocks as separate regions.

This is a deliberate consequence of the simple metadata format: there is no previous-block pointer or boundary tag.

## Arena reclamation

Current kfree does not return empty arenas to PMM.

Even if every block inside an arena becomes free, the arena remains registered and reserved for future heap reuse.

That makes arena lifetime effectively kernel-lifetime after acquisition.

Benefits:

- no need to coordinate arena removal with concurrent heap traversals;
- no physical-contiguity reconstruction problem;
- later allocations can reuse the capacity cheaply.

Costs:

- PMM cannot reclaim unused heap arenas;
- an early heap expansion permanently transfers those pages into the heap pool until reboot.

A future allocator could add empty-arena reclamation, but it would need explicit synchronization and ownership transfer back to PMM.

## Allocation contents

kmalloc does not zero returned payload memory.

A reused block can contain bytes written by the previous owner.

Callers that require initialized memory must clear or initialize it themselves.

This is normal for a malloc-like primitive, but it matters for correctness and confidentiality if data is copied across trust boundaries.

There is currently no kcalloc or zeroing-allocation interface in heap.h.

## Accounting

heap_tally walks every block in every arena and sums payload sizes based on used state.

heap_used_bytes and heap_free_bytes call it under heap_lock.

These metrics count block payload capacity, not:

- the 16-byte metadata overhead of each block;
- unusable internal fragments folded into allocations;
- PMM bookkeeping;
- virtual-space overhead.

They therefore describe allocator payload state, not exact total physical cost.

heap_arena_count reports narenas under the same lock.

## Concurrency

Normal heap allocation and free are serialized by one global heap_lock.

That makes metadata operations straightforward and allows cross-CPU free: an object allocated on one CPU can be freed on another.

tools/test_pmm_heap_smp explicitly tests that case.

The trade-off is scalability.

Every kmalloc, kfree and heap accounting traversal contends on the same lock.

There are no per-CPU caches or arena-local locks.

For the current CPU count and experimental design this is simple, but allocator contention can become significant as parallel kernel work grows.

## Ownership examples in current source

The heap is used across many kernel subsystems.

Examples include:

- kthread private stacks;
- graphics backbuffers and 3D buffers;
- compiler and linker work memory;
- CLVM buffers;
- filesystem work buffers;
- network transfer buffers;
- shader data.

The allocation primitive does not encode ownership.

Ownership is established by subsystem control flow.

For example, kthread_create allocates a private stack. kthread_join detaches the stack from the slot under g_slot_lock, releases the slot lock, and only then calls kfree.

That order avoids holding the slot lock while entering the heap and makes the destroy path explicit.

## Allocation failure as a transaction

Multi-object callers must treat allocation as a transaction.

A common safe pattern is:

~~~text
allocate A
allocate B
if B fails:
    free A
    report failure
~~~

The repository contains several callers that explicitly free earlier allocations on later failure.

This is part of ownership discipline.

The heap cannot discover which subsystem should release an object; it only knows whether a block is currently marked free or used.

## Self-test

heap_selftest validates several basic invariants:

1. allocations of 16, 64 and 256 bytes succeed;
2. returned pointers are distinct;
3. all are 16-byte aligned;
4. written contents remain intact;
5. freeing the middle 64-byte block allows a new 64-byte request to reuse exactly that pointer;
6. neighboring live blocks are not corrupted by reuse;
7. used/free tallies can be reported.

The exact-pointer reuse check is evidence of the current first-fit behavior.

## SMP host validation

tools/test_pmm_heap_smp performs broader host-side testing with four pthread workers.

It tests PMM concurrent allocation first, then heap behavior.

For the heap it performs:

- single-thread alignment/reuse/accounting checks;
- four concurrent allocation/free workers;
- variable aligned allocation sizes;
- repeated writes into live blocks;
- cross-CPU free of a block allocated on CPU 0 and freed while host CPU identity is 2.

This is stronger evidence than a boot-only smoke test because it exercises heap_lock under concurrent host threads.

It is still not a formal proof against all races or metadata corruption.

## Failure modes

Important current failure classes are:

### Heap used before initialization

kmalloc, kfree and accounting functions panic when called before the required initialization state.

### PMM reserve reached

Growth fails rather than consume the protected reserve.

### Physical fragmentation

pmm_alloc_contig may fail even with enough total free pages.

### Arena table full

No more than 32 arenas can be registered.

### Double free

Detected through block->used == 0 and treated as panic.

### Foreign pointer

Pointer outside all arenas is rejected.

### Interior aligned pointer

Not fully validated and can be misinterpreted as a header.

### Fragmentation

First-fit plus forward-only coalescing can leave usable bytes split into regions too small for a request.

## Security and robustness properties

Current positive properties include:

- fixed alignment checks;
- arena bounds checks;
- double-free detection;
- global metadata serialization;
- PMM reserve;
- explicit PMM accounting when claiming arenas.

Current missing hardening includes:

- heap canaries;
- red zones;
- guard pages;
- poisoning on free;
- zero-on-allocate;
- quarantine for recently freed heap objects;
- per-allocation owner/type metadata;
- exact payload-boundary validation;
- use-after-free detection.

The heap is therefore a functional kernel allocator, not a hardened debugging allocator.

## Performance model

The main allocation cost is first-fit traversal.

A successful early hit can be cheap.

A late hit or failure scans many blocks.

Splitting is O(1).

Forward coalescing can walk through multiple consecutive free blocks, so freeing a block is O(K) in the number of immediately following free blocks.

heap_tally is O(B) over all blocks.

Heap growth adds PMM contiguous-run search cost.

A global spinlock serializes all of these operations.

## Current limitations

At the reviewed revision:

- maximum 32 arenas;
- arena minimum 64 KiB;
- arenas require physically contiguous PMM runs;
- arenas are never returned to PMM;
- one global heap lock;
- first-fit only;
- no backward coalescing;
- no realloc/calloc/aligned-allocation API;
- payloads are not cleared;
- no hardened metadata;
- no complete validation that kfree receives an exact allocation boundary.

These are current implementation facts, not roadmap completion claims.

## Revision boundary

This chapter was reconciled against ChrisOS main revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.

The current source-backed ownership chain is:

~~~text
PMM owns free physical pages
   -> heap claims contiguous pages
   -> arena owns those pages
   -> allocated block transfers payload use to caller
   -> kfree returns block to arena
   -> arena retains physical pages for future heap allocations
~~~

Future arena reclamation, slab caches, hardened metadata or per-CPU allocation paths will require this ownership model to be updated.
