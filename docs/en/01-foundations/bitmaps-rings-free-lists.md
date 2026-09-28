---
id: bitmaps-rings-free-lists
lang: en
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/pmm.h
  - kernel/metal/pmm.c
  - kernel/metal/job.h
  - kernel/metal/job.c
  - kernel/metal/klog.c
  - kernel/fs/cfs.c
  - kernel/fs/cfs.h
  - compiler/jit/jit.c
symbols:
  - pmm_bitmap
  - bitmap_is_used
  - bitmap_set_used
  - bitmap_set_free
  - pmm_alloc
  - pmm_alloc_contig
  - dma32_free
  - JOB_QUEUE_CAP
  - job_submit
  - job_worker_once
  - klog_putc
  - klog_copy
  - block_alloc
  - block_free
  - JitVa
  - jit_va_alloc
  - jit_va_free
depends_on:
  - arrays-lists-stacks-queues
  - algorithmic-complexity
related:
  - graphs-union-find
  - physical-memory
  - pmm-algorithms
  - kernel-jobs-kthreads
  - chrisfs
  - jit-memory
---

# Bitmaps, ring buffers and free-list patterns

<div class="abstract">
Bitmaps, circular buffers and free lists are compact low-level structures used when allocation, bounded queues and reusable resources must be represented without large object overhead. Their apparent simplicity hides important invariants: what each bit means, how scans terminate, how head/tail states distinguish empty from full, whether overwrite is permitted, and whether a "free list" is actually linked or merely a reusable-slot table. This chapter develops those structures and reconciles them with current ChrisOS source. The physical memory manager uses a one-bit-per-4-KiB-page bitmap over a 32-GiB tracked range, with one meaning used and zero meaning free; its DMA32 suballocator uses the opposite convention, where set bits mean free. ChrisFS uses an on-disk allocation bitmap plus alloc_hint. The kernel job queue is a 1024-entry counted ring protected by a spinlock. The kernel log is an 8192-byte overwrite ring retaining the newest bytes. The JIT virtual-address reuse structure is a 128-entry slot table with a used flag and equal-size reuse; despite being described operationally as a freelist, it is not a pointer-linked free list.
</div>

## Compact structures in low-level systems

Kernel and runtime code frequently needs to answer one of three questions:

~~~text
is resource i free or used?
where is the next queued item?
which previously released object can be reused?
~~~

General-purpose maps and linked containers can solve those questions, but often with unnecessary memory and allocator dependence.

Compact structures exploit stronger constraints:

- resources have dense integer ids;
- capacity is fixed or bounded;
- FIFO ordering is required;
- reuse state can be represented by a bit or index.

The benefit is predictability, but only if the invariants are explicit.

## Bitmaps

A bitmap stores Boolean state by assigning one bit to each logical element.

For element index i:

~~~text
byte = i / 8
bit  = i % 8
mask = 1 << bit
~~~

Test:

~~~text
(bitmap[byte] & mask) != 0
~~~

Set:

~~~text
bitmap[byte] |= mask
~~~

Clear:

~~~text
bitmap[byte] &= ~mask
~~~

The crucial question is not the arithmetic. It is the meaning of 0 and 1.

## Bit semantics are part of the ABI

Two valid conventions are:

~~~text
1 = allocated
0 = free
~~~

or:

~~~text
1 = free
0 = allocated
~~~

Both work.

Mixing them does not.

The convention must be local and explicit, especially when multiple bitmaps coexist.

Current ChrisOS demonstrates both conventions in the same physical-memory subsystem.

## PMM bitmap representation

The PMM defines:

~~~text
PMM_PAGE     = 4096 bytes
PMM_MAX_PHYS = 32 GiB
~~~

Therefore the tracked page count is:

~~~text
32 GiB / 4 KiB = 8,388,608 pages
~~~

At one bit per page:

~~~text
8,388,608 / 8 = 1,048,576 bytes
~~~

so pmm_bitmap occupies 1 MiB.

Its convention is:

~~~text
bit 1 = page used/reserved
bit 0 = page free
~~~

bitmap_is_used, bitmap_set_used and bitmap_set_free implement this mapping directly.

## PMM initialization

pmm_init first fills the entire bitmap with 0xff:

~~~text
all tracked pages = used
~~~

It then examines the Limine memory map and clears bits only for usable physical ranges.

After that it re-reserves regions that must remain unavailable, including low memory and reserved/non-usable ranges.

This sequence is conservative:

~~~text
start unavailable
prove range usable
then mark free
re-reserve exclusions
~~~

A failed or incomplete memory-map classification therefore tends toward withholding memory rather than allocating an unknown frame.

## PMM allocation scan

pmm_alloc searches for one free page beginning at pmm_cursor.

If no page is found after the cursor, it retries from physical zero.

The underlying scan can skip an entire bitmap byte when:

~~~text
page is byte-aligned
and
pmm_bitmap[byte] == 0xFF
~~~

because all eight represented pages are used.

That optimization preserves correctness while reducing per-page checks across fully occupied regions.

The scan still has worst-case linear behavior in the searched physical range.

## Cursor/hint behavior

A cursor changes repeated first-fit scanning.

Without a hint, repeated allocations can repeatedly inspect the same occupied prefix.

With pmm_cursor, the allocator resumes nearer the previous allocation frontier.

On free:

~~~text
if freed_phys < pmm_cursor:
    pmm_cursor = freed_phys
~~~

so earlier reusable space becomes visible again.

A hint is not authoritative state.

If the hint is stale, the allocator must still remain correct; it should only affect search order and performance.

## Contiguous allocation

pmm_alloc_contig needs a run of count consecutive free pages.

A bitmap can represent availability compactly, but finding a long run still requires scanning.

The current PMM enumerates free runs and can also scan for a requested run.

Worst-case work is proportional to the range examined.

The bitmap alone does not give a logarithmic best-fit index.

A future system needing frequent large contiguous allocations could add:

- buddy metadata;
- free-run trees;
- segregated run lists;
- hierarchical bitmaps.

Those are alternatives, not current PMM claims.

## DMA32 bit mask uses the opposite convention

The PMM reserves a small DMA32 run for UHCI.

Its state is stored in a 32-bit integer named dma32_free.

Here:

~~~text
bit 1 = free
bit 0 = allocated
~~~

Allocation builds a contiguous mask:

~~~text
need = (1 << pages) - 1
mask = need << i
~~~

and accepts a range when:

~~~text
(dma32_free & mask) == mask
~~~

It then clears those bits.

Freeing sets them again.

This opposite convention is valid because the state is separate and functions are consistent, but it demonstrates why bit meaning must never be assumed from the word "bitmap."

## Bitmap scanning complexity

Testing one known bit is O(1).

Finding a free element is not automatically O(1).

A simple bitmap scan over n bits is:

~~~text
O(n)
~~~

in the worst case.

Word-at-a-time scanning can reduce constants by testing 32 or 64 bits at once.

CPU instructions such as count-trailing-zeros can quickly locate a set bit in a nonzero word.

Hierarchical bitmaps add summary levels so a non-full word can be located faster.

The representation and the search algorithm are separate design choices.

## ChrisFS allocation bitmap

ChrisFS also uses a bitmap for data-block allocation.

bitmap_get and bitmap_set translate a data-block index into:

- bitmap-sector LBA;
- byte within that sector;
- bit within that byte.

The convention is:

~~~text
1 = block used
0 = block free
~~~

block_alloc starts scanning from:

~~~text
fs->alloc_hint
~~~

and wraps around the data-block population.

When it claims a block, it sets the bit, zeroes the data block and advances alloc_hint.

When block_free releases a lower block, it may move alloc_hint backward.

The hint avoids the historical behavior of always rescanning from zero.

## Failure atomicity in ChrisFS block allocation

Allocation performs more than one state change.

Current sequence is conceptually:

1. find a free bit;
2. set the allocation bit;
3. zero the newly allocated block;
4. publish returned LBA.

If zeroing/writing fails after setting the bit, the code attempts:

~~~text
bitmap_set(index, 0)
~~~

to roll back the allocation state.

This is a small example of failure atomicity: a bitmap transition must not leave a block permanently allocated if initialization failed before ownership was returned.

Filesystem crash consistency and journaling require broader analysis in the ChrisFS chapters.

## Ring buffers

A ring buffer stores a logical sequence in a fixed physical array and wraps indices at capacity.

With capacity C:

~~~text
next(i) = (i + 1) mod C
~~~

The physical end of the array is therefore not the logical end of the queue.

Rings avoid shifting elements.

Push/pop can be O(1) when metadata is correct.

## The empty/full ambiguity

If a ring stores only head and tail, then:

~~~text
head == tail
~~~

can mean either empty or full after wraparound.

Common solutions:

1. keep an explicit count;
2. reserve one slot permanently;
3. keep a separate full flag;
4. use monotonically increasing sequence counters.

Each produces a different usable capacity.

A ring with array capacity C and one reserved slot holds at most C - 1 items.

A counted ring can use all C slots.

## ChrisOS job queue: counted FIFO ring

The job subsystem defines:

~~~text
JOB_QUEUE_CAP = 1024
~~~

and stores:

~~~text
g_queue[JOB_QUEUE_CAP]
g_q_head
g_q_tail
g_q_count
~~~

Initialization sets all three indices/count state values to zero.

Submission checks:

~~~text
g_q_count == JOB_QUEUE_CAP
~~~

to detect full.

Because count disambiguates the state, all 1024 physical entries are usable.

## Job submission invariant

Under g_q_lock, job_submit:

1. writes fn and arg at g_q_tail;
2. advances tail modulo capacity;
3. increments count;
4. increments inflight;
5. unlocks.

Conceptual invariant:

~~~text
0 <= g_q_count <= JOB_QUEUE_CAP
~~~

and the next insertion position is g_q_tail.

Full means count equals 1024.

Empty means count equals zero.

head and tail may be equal in either state; count resolves the ambiguity.

## Job removal

job_worker_once acquires the same queue lock.

If count is positive:

1. copy g_queue[g_q_head] into a local Job;
2. advance head modulo capacity;
3. decrement count;
4. unlock.

The callback is executed after releasing the queue lock.

That is important.

Running arbitrary job code while holding the queue lock would enlarge the critical section and could deadlock if the job itself interacts with queue operations.

## Ring concurrency

The job ring is not lock-free.

Its correctness relies on g_q_lock serializing head/tail/count and entry publication.

The completed/inflight counters use atomic operations separately.

A lock-free multi-producer/multi-consumer ring would require stronger per-slot or sequence-number rules. Merely making head and tail atomic is generally insufficient.

The chapter therefore classifies the current structure as a spinlock-protected counted ring.

## Saturation behavior

job_submit returns zero if:

~~~text
g_q_count == JOB_QUEUE_CAP
~~~

It does not overwrite an older job.

Callers that require eventual submission must implement retry/backpressure behavior.

The self-test does exactly that: it services work and retries when submission temporarily fails.

Bounded queue saturation is a policy decision, not just an implementation detail.

## Kernel log: overwrite ring

klog uses a different ring policy:

~~~text
KLOG_CAP = 8192
g_log[KLOG_CAP]
g_pos
g_len
~~~

Each new character is written at g_pos.

g_pos advances and wraps to zero.

g_len increases until it reaches KLOG_CAP, then saturates.

When the ring is full, future writes overwrite the oldest bytes.

This is appropriate for a diagnostic tail where recent events are more valuable than indefinite retention.

## Recovering logical order from klog

The newest n bytes are copied using:

~~~text
start = (g_pos + KLOG_CAP - n) % KLOG_CAP
~~~

Then:

~~~text
g_log[(start + i) % KLOG_CAP]
~~~

is copied for i from zero to n-1.

This reconstructs chronological order even when the physical data is split across the end and beginning of the array.

The log uses a spinlock around mutation and copy.

## Queue ring versus overwrite ring

The job queue and klog are both circular arrays, but their semantics differ.

| Property | Job queue | klog |
|---|---|---|
| payload | Job records | bytes |
| capacity | 1024 jobs | 8192 bytes |
| full policy | reject submission | overwrite oldest |
| empty/full disambiguation | explicit count | length + write position |
| consumer | workers | copy/read tail |
| synchronization | spinlock | spinlock |

Calling both merely "rings" is insufficient for reasoning about failure and saturation.

## Free lists

A free list represents reusable objects.

Classic linked representation:

~~~text
free_head -> object -> object -> object
~~~

A free object stores a next-free link.

Allocation removes an object from the list.

Freeing inserts one back.

If insertion/removal occurs at the head, both are O(1).

The trade-off is that free objects need link metadata and corruption of one link can damage the allocator.

## Intrusive free lists

In an intrusive free list, the resource object itself stores the next link while free.

This avoids separate node allocation.

Typical pattern:

~~~text
struct Slot {
    union {
        LivePayload live;
        uint32_t next_free;
    };
}
~~~

When the slot is live, the payload is meaningful.

When free, the same storage becomes list metadata.

This is compact but requires precise state transitions.

## Address-ordered free lists

A memory allocator can order free blocks by address.

Advantages:

- easier neighbor coalescing;
- deterministic walk order.

A size-segregated free list instead groups blocks by size class.

Advantages:

- faster approximate-fit search.

The best policy depends on fragmentation, latency and allocator complexity.

Current kernel heap.c is not documented here as a free-list allocator because its reviewed implementation scans sequential blocks inside arenas and marks them used/free rather than maintaining an explicit free-link chain.

## JIT reusable-VA structure

The JIT reserves a virtual-address window and maintains:

~~~text
JIT_VA_SLOTS = 128

struct JitVa {
    uint64_t virt;
    uint32_t pages;
    int used;
}
~~~

jit_va_alloc first linearly scans the table for:

~~~text
virt != 0
used == 0
pages == requested_pages
~~~

and reuses such a slot.

jit_va_free finds the matching virt and clears used.

This is reusable-slot bookkeeping, sometimes described operationally as a VA freelist.

Structurally, however, it is not a linked free list.

There is no free_head and no next-free pointer.

## Equal-size reuse invariant

The JIT table only reuses a released VA record when:

~~~text
stored_pages == requested_pages
~~~

A four-page VA extent is therefore not automatically split to satisfy a two-page request.

Likewise adjacent free entries are not merged.

This is a simple exact-size reuse policy.

Its advantages are low implementation complexity and stable mappings.

Its limitations include fragmentation of the reserved virtual-address window and O(128) scan cost.

## Bump frontier plus reusable slots

If no matching free record exists, jit_va_alloc allocates from:

~~~text
g_jit_virt_next
~~~

provided the requested range stays below JIT_VIRT_LIMIT.

It then records the new range in the first never-used metadata slot where virt == 0.

Thus the design combines:

- monotonic bump allocation for new VA ranges;
- fixed metadata slots;
- exact-size reuse of released ranges.

This is not the same as a general extent allocator.

## Free-list corruption concerns

A linked free list can fail through:

- cycles;
- duplicate insertion;
- dangling next pointers;
- allocated object remaining on the free list;
- ABA races in lock-free stacks.

A reusable-slot table has different failure modes:

- duplicate live ranges;
- used flag inconsistent with ownership;
- capacity of metadata slots exhausted;
- same VA returned twice;
- wrong-size reuse.

Classification matters because validation must target the actual representation.

## Complexity comparison

| Structure | Known-state operation | Search/allocation worst case |
|---|---:|---:|
| bitmap known bit | O(1) | — |
| linear bitmap allocation | — | O(n bits) |
| counted ring enqueue/dequeue | O(1) | O(1) |
| overwrite ring append | O(1) | O(1) |
| linked free-list head pop/push | O(1) | O(1) |
| JIT reusable-slot table | update O(1) once found | O(128) scan |
| CFS bitmap allocation | bit update O(1) after location | O(number of data blocks) |
| PMM contiguous bitmap search | mark O(k) for k pages | linear scan/search of runs |

Big-O must describe both representation lookup and state mutation.

## Cache and locality

Bitmaps are extremely dense: one cache line represents hundreds of resources.

Rings use contiguous arrays and generally have strong locality.

Linked free lists can scatter across memory and cause pointer-chasing misses.

Index-based or array-based free-slot tables trade fixed metadata for locality.

This is one reason low-level systems often prefer bitmaps and rings when resource ids are dense.

## Synchronization and ownership

The current examples use distinct concurrency policies:

- PMM bitmap: IRQ-safe recursive same-CPU PMM lock;
- job ring: spinlock around queue state;
- klog ring: spinlock around bytes and indices;
- ChrisFS bitmap: protected by the filesystem locking model;
- JIT VA slots: lifecycle is tied to JIT/MM ownership and current code is not presented as a lock-free allocator.

A bit operation such as OR or AND being machine-sized does not automatically make the higher-level allocation operation atomic.

Allocation is a read-modify-claim transaction over invariants, not merely one bit instruction.

## Security and defensive design

Compact metadata is often security-critical.

One corrupted bit can double-allocate a page.

One corrupted ring count can produce out-of-bounds access.

One free-list duplicate can return the same resource to multiple owners.

Defensive measures include:

- range validation before bit arithmetic;
- explicit capacity checks;
- consistency counters;
- poison/debug state;
- double-free detection;
- lock ownership rules;
- deterministic saturation policy;
- tests that force wraparound and full conditions.

The smaller the metadata, the more state each bit or index may control.

## Validation model

The deterministic checker for this chapter validates:

- bitmap set/clear/test arithmetic;
- opposite used/free bit conventions;
- first-fit scan with a moving hint;
- contiguous-bit run allocation;
- counted-ring FIFO behavior through wraparound;
- full rejection and complete capacity use;
- overwrite-ring retention of newest bytes;
- logical-copy reconstruction after wrap;
- classic linked free-list push/pop;
- JIT equal-size reusable-slot behavior;
- current source anchors for PMM bitmap, DMA32 mask, CFS bitmap and alloc_hint, job ring, klog ring and JIT slot table.

These checks validate the representations and the reviewed source contract. They do not replace PMM SMP stress, filesystem crash testing or JIT/TLB lifecycle tests.

## Current ChrisOS implementation boundary

At revision da3df29cb397932c43d32373871fb9380e688ade the source establishes:

- one-bit-per-page PMM allocation metadata;
- a 32-bit DMA32 free mask with inverted bit semantics;
- ChrisFS on-disk data-block allocation bitmap with alloc_hint;
- a 1024-entry counted FIFO job ring;
- an 8192-byte overwrite kernel-log ring;
- a 128-entry JIT VA reuse table with exact-size matching.

The source does not establish a generic reusable library implementing every bitmap, ring or free-list variant described in this chapter.

The JIT structure should not be mislabeled as a pointer-linked list.

## Revision provenance

Implementation-facing statements were reconciled against ChrisOS main revision da3df29cb397932c43d32373871fb9380e688ade.

Reviewed source:

- kernel/metal/pmm.h;
- kernel/metal/pmm.c;
- kernel/metal/job.h;
- kernel/metal/job.c;
- kernel/metal/klog.c;
- kernel/fs/cfs.h;
- kernel/fs/cfs.c;
- compiler/jit/jit.c.

The chapter distinguishes logical family names from concrete representations: a bitmap's bit convention is local, rings can reject or overwrite, and a reusable-slot table is not automatically a linked free list.
