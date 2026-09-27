---
id: systems-algorithms
lang: en
type: technical-chapter
volume: 01-foundations
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/pmm.c
  - kernel/metal/job.c
  - kernel/metal/mm.c
  - kernel/fs/cfs.c
  - kernel/fs/cfs.h
  - kernel/gfx/virtq.c
  - kernel/gfx/tile.c
  - compiler/chrisc/chrisc.c
  - chrisvm/machine/machine.h
  - chrisvm/cpu/emulator/decode.c
  - chrisvm/debug/trace.c
symbols:
  - pmm_alloc
  - pmm_alloc_contig
  - job_submit
  - job_worker_once
  - ChrisMachine
  - ChrisCpu
  - chris_decode
depends_on:
  - data-structures
  - algorithmic-complexity
related:
  - physical-memory
  - kernel-jobs-kthreads
  - chrisfs
  - virtio-gpu-virgl
  - compiler-pipeline
  - chrisvm-chriscpu
---

# Algorithms used by ChrisOS

<div class="abstract">
This chapter is an algorithmic map of the current ChrisOS <code>main</code> revision. It does not assign textbook labels by resemblance. Each entry identifies the representation actually visible in source, the operation performed, the principal invariant, complexity characteristics and concurrency model. The purpose is to connect foundational data-structure theory to concrete kernel, filesystem, graphics, compiler and emulator behavior.
</div>

## Reading the atlas

The same algorithm can be acceptable in one subsystem and unsuitable in another. ChrisOS currently uses many deliberately bounded structures: arrays, bitmaps and rings. These often trade asymptotically sophisticated lookup for deterministic memory use and implementation simplicity.

The table below is only an index; each subsystem volume should eventually carry the complete derivation.

| Subsystem | Current structure / algorithm |
|---|---|
| PMM | page bitmap, search cursor, run scan, dedicated DMA32 bit mask |
| kernel jobs | bounded circular FIFO under spinlock |
| page tables | fixed-depth x86-64 hierarchical walk |
| TLB coherence | generation/acknowledgement shootdown protocol |
| ChrisFS allocation | bitmap scan with mount-local allocation hint |
| ChrisFS data blocks | direct + multi-level indirect block addressing |
| ChrisFS metadata durability | small journal with BEGIN/COMMIT and replay |
| VirtIO | split ring descriptor/available/used protocol |
| software graphics | tile partitioning/binning and z-buffered raster work |
| ChrisC | bounded symbol/type structures and hand-written parsing/code generation |
| ChrisCPU | prefix/opcode decoder followed by explicit execute stage |
| ChrisVM tracing | fixed circular trace ring |
| ChrisVM buses | small fixed slot arrays with range matching |

## Physical memory manager: bitmap plus cursor

<code>kernel/metal/pmm.c</code> stores physical-page state in <code>pmm_bitmap</code>. One bit represents one physical page.

Testing a known page is O(1). The allocator, however, must find a free run.

<code>scan_usable_for_run(count, from_phys)</code> iterates Limine usable memory-map ranges, aligns them to page boundaries and scans the bitmap. It contains a small but important optimization: when the scan is byte-aligned and the bitmap byte equals <code>0xFF</code>, eight fully used pages are skipped at once.

The ordinary single-page path is:

    acquire PMM critical section
        ↓
    scan from pmm_cursor
        ↓ if no page
    wrap and scan from zero
        ↓
    mark selected page used
        ↓
    advance pmm_cursor
        ↓
    release PMM critical section

The cursor is a next-search hint, not a free-list index. Worst-case allocation remains O(P) in represented pages. Typical repeated allocation avoids restarting from physical zero.

### Invariants

- one bitmap bit corresponds to one page;
- reserved/non-usable pages remain marked used;
- counters track used/free state;
- selected contiguous runs are marked atomically under the PMM synchronization regime;
- <code>pmm_cursor</code> points to the next search starting region, not necessarily a free page.

### Concurrency

PMM uses a spinlock plus per-CPU recursion depth and saved interrupt flags. The recursion mechanism exists because a same-CPU callback path can claim pages while a scan already owns the PMM lock. Interrupts are disabled for the outer acquisition.

This is stronger information than “the allocator is thread-safe”: it explains why recursion is legal only under the same-CPU discipline.

## Contiguous physical allocation

<code>pmm_alloc_contig</code> first enumerates free runs with <code>pmm_foreach_free_run</code> and selects the first run large enough. It then claims that exact region. A fallback scan starts at zero.

This is first-fit over discovered free runs, backed by the same bitmap representation.

Worst-case time is O(P). There is no balanced extent tree or buddy hierarchy, so large contiguous allocations can become expensive or fail under fragmentation despite sufficient total free pages.

The advantage is low metadata complexity.

## DMA32 reserve

The PMM reserves a fixed 16-page region below 4 GiB for DMA32. Availability inside this small reserve is represented by a 32-bit mask, with one bit per page.

For a request of k pages, the code constructs a k-bit mask and shifts it across possible positions until a fully free contiguous subset is found.

Because the reserve size is a fixed 16 pages, the search is effectively bounded O(1) at system scale.

This is an example of choosing a specialized tiny structure instead of forcing the general PMM algorithm onto a constrained DMA use case.

## Kernel job queue: circular FIFO

<code>kernel/metal/job.c</code> defines:

- a fixed <code>Job g_queue[JOB_QUEUE_CAP]</code>;
- <code>g_q_head</code>;
- <code>g_q_tail</code>;
- <code>g_q_count</code>;
- a spinlock.

Enqueue writes at tail and advances:

    tail = (tail + 1) mod capacity

Dequeue reads at head and advances similarly.

Both are O(1), with no dynamic allocation. Full capacity is explicit: <code>job_submit</code> fails when count equals capacity.

### Representation rationale

Jobs are short records containing function and argument pointers. A bounded ring keeps storage stable, avoids allocation from worker paths and gives constant-time queue mutation.

The trade-off is saturation. Producers must handle a full queue; the self-test explicitly helps drain work while retrying submissions.

### Concurrency

Queue mutation is protected by <code>g_q_lock</code>. Completion/inflight counters use atomic addition. Work executes after releasing the queue lock, which prevents long jobs from serializing queue access.

## Worker scheduling algorithm

<code>job_worker_once</code> first services TLB protocol state, then removes at most one job, releases the lock and executes it.

The worker loop repeatedly:

1. checks whether the CPU has been fenced by TLB protocol;
2. services TLB polling;
3. enables AP interrupts when allowed;
4. dequeues/execut es one job;
5. executes <code>pause</code>.

This is a simple shared-queue worker model rather than per-CPU work stealing.

The architecture is easy to reason about but can make the single queue a contention point at larger CPU counts.

## Page-table walk

x86-64 translation is a hierarchical lookup through a fixed number of page-table levels. In ChrisOS, <code>kernel/metal/mm.c</code> maps, unmaps and translates by walking those tables.

With four architecture-defined levels, lookup is O(1) relative to the total number of virtual mappings, but it can involve several dependent memory references.

The data structure is effectively a sparse radix tree whose fan-out is determined by x86-64 page-table indexing.

This is an important case where “tree” does not mean a conventional pointer-based C binary tree.

## TLB shootdown: distributed acknowledgement

When a mapping changes on one CPU, other CPUs may retain stale TLB entries. ChrisOS uses a generation/seen protocol coordinated with an IPI vector and polling fallback.

The conceptual algorithm is:

    updater changes mapping
        ↓
    increment/publish generation
        ↓
    notify participating CPUs
        ↓
    each CPU invalidates / observes request
        ↓
    each CPU records generation seen
        ↓
    updater waits until required acknowledgements
        ↓
    physical memory may become reusable

The invariant is temporal: a frame must not be reused while another CPU can still translate through a stale mapping to that frame.

This algorithm is documented separately in the memory volume because complexity alone is not the hard part; ordering and membership are.

## ChrisFS block allocation: bitmap plus allocation hint

ChrisFS stores free/used block state in a bitmap. Earlier behavior rescanned from zero for each allocation, which made large sequential file creation increasingly expensive.

The current <code>Cfs.alloc_hint</code> records the next bitmap index to try.

The allocation path begins from the hint, scans for a free block and advances the hint after success. The optimization changes repeated allocation behavior from repeatedly revisiting the same occupied prefix toward an approximately forward-moving scan.

Worst case remains linear in data-sector count because the structure is still a bitmap without a free-extent tree.

This is a practical example of an algorithmic improvement that changes typical complexity without replacing the representation.

## ChrisFS block addressing

A ChrisFS inode contains direct block references and indirect, double-indirect and triple-indirect pointers.

The addressing hierarchy trades inode size for scalable file capacity.

For low logical block numbers, direct entries give immediate O(1) access. Larger positions require one or more pointer-table reads.

The structure resembles a fixed-depth tree:

    inode
     ├─ direct data blocks
     ├─ indirect → data pointers
     ├─ double indirect → pointer tables → data
     └─ triple indirect → two pointer-table layers → data

Depth is bounded by the format, so address translation is O(1) with respect to arbitrarily growing file size within format limits, but the number of I/O operations differs by level and cache state.

## ChrisFS journal

The current journal uses explicit states including <code>JNL_BEGIN</code>, <code>JNL_COMMIT</code> and empty state. The journal contains a bounded number of records.

At mount/recovery time:

- empty requires no action;
- an incomplete BEGIN can be discarded/cleared according to the current protocol;
- COMMIT triggers replay of recorded metadata operations and then cleanup.

The algorithm's purpose is not general database transactions. It is bounded metadata recovery for the filesystem's specific update model.

Complexity is O(R) in journal record count, with R capped by <code>JNL_MAX_REC</code>.

## Filesystem cache

The repository describes a small sector cache with bounded lines and an LRU-like clock/replacement policy. A bounded cache means lookup/replacement cost is controlled by a small constant even if implemented by linear scan.

This is another systems pattern: when the capacity is deliberately tiny, a simple O(C) scan with fixed C can be easier and fast enough compared with maintaining a tree or hash index.

## VirtIO split ring

VirtIO split queues consist of three logical regions:

1. descriptor table;
2. available ring written by the driver;
3. used ring written by the device.

The driver builds descriptor chains, publishes descriptor indices into the available ring with required memory ordering, updates the available index and notifies the device.

Completion observes the used index and reclaims the descriptor associated with a returned used element.

The crucial invariant is ownership/order, not only circular indexing:

    driver fills descriptor
        ↓
    memory barrier
        ↓
    driver publishes available entry/index
        ↓
    device consumes
        ↓
    device publishes used entry/index
        ↓
    driver observes after ordering barrier

Reordering these steps can expose partially initialized descriptors.

## Graphics: tile partitioning and binning

The software 3D path divides the framebuffer into fixed-size tiles. Triangle work is associated with tiles so separate jobs can process independent screen regions.

For screen dimensions W×H and tile size S:

    tiles_x = ceil(W / S)
    tiles_y = ceil(H / S)

Binning reduces the region each worker considers and creates a natural parallel work unit.

The important concurrency invariant is that two jobs must not concurrently write the same tile's color/depth region unless synchronization exists. Current graphics audit material explicitly tracks this race concern.

## Z-buffer

Depth buffering stores a depth value per pixel. For each candidate fragment:

1. compute/interpolate depth;
2. compare with stored depth;
3. if closer according to the chosen convention, update depth and color.

The depth test is O(1) per fragment but memory-bandwidth heavy. Overall raster cost depends on triangle coverage and overdraw.

The data structure is a dense array indexed like the framebuffer, chosen for constant-time spatial lookup.

## ChrisC compiler structures

<code>compiler/chrisc/chrisc.c</code> uses bounded internal tables for symbols and related compile state. The current implementation is intentionally not documented as a modern optimizing compiler pipeline with hash-indexed semantic graphs unless source supports that claim.

Symbol lookup in bounded arrays can be O(N) in symbol count. For the current scale, fixed storage avoids general allocator and container dependencies.

The broader compiler volume should document exact tokenization, parsing functions, type representation and emitted forms symbol by symbol.

## ChrisCPU decoder

<code>chrisvm/cpu/emulator/decode.c</code> performs explicit x86 instruction decoding.

The high-level sequence is:

    consume legacy/REX prefixes
        ↓
    choose operand/address size
        ↓
    read primary opcode
        ↓
    optional 0F extended opcode
        ↓
    decode ModR/M and optional SIB
        ↓
    decode displacement/immediate
        ↓
    populate ChrisInsn
        ↓
    execute stage consumes normalized form

The decoder is not a table-driven full x86 decoder at this revision; a substantial part is explicit conditional dispatch over opcode families.

Instruction length is architecture-bounded, so per-instruction decode work is bounded O(1), though constant cost varies by encoding.

## ChrisVM I/O and MMIO slot arrays

<code>ChrisMachine</code> contains fixed arrays of I/O and MMIO mapping slots. Each slot stores a range and callbacks/context.

With a small fixed slot count, mapping lookup can use linear search. The theoretical cost is O(S), but S is bounded by constants such as <code>CHRIS_IO_MAX</code> and <code>CHRIS_MMIO_MAX</code>.

This is preferable to introducing an interval tree before the machine model needs many devices.

If the VM grows to hundreds or thousands of regions, the structure should be reconsidered.

## ChrisVM trace ring

Each <code>ChrisCpu</code> contains a fixed <code>ChrisTraceEnt ring[CHRIS_TRACE_RING]</code> plus write index and count.

<code>chris_trace_push</code> advances the index and caps the count at ring capacity. Old entries are overwritten once full.

Append is O(1), allocation-free and bounded-memory—appropriate for diagnostic history that must not grow without limit.

The trade-off is intentional loss of oldest history.

## Cross-subsystem algorithm table

| Operation | Representation | Worst-case time | Allocation | Synchronization |
|---|---|---:|---|---|
| PMM single-page find | bitmap + cursor | O(P) | none | PMM spinlock/IRQ discipline |
| PMM DMA32 alloc | 16-bit-region mask | bounded constant | none | PMM critical section |
| job enqueue/dequeue | circular array | O(1) | none | queue spinlock |
| VA page-table walk | fixed radix hierarchy | O(1) architecture depth | page allocation only on map creation | MM lock/protocol dependent |
| ChrisFS block find | bitmap + hint | O(B) | metadata update | CFS locking |
| inode logical-block resolve | direct/indirect hierarchy | bounded depth | may allocate pointer/data blocks on growth | CFS locking |
| journal replay | bounded record array | O(R) | bounded scratch | mount/update serialization |
| VirtIO allocate/fill chain | software links + descriptors | O(chain length) | bounded descriptor pool | caller ownership |
| VirtIO publish one head | split ring | O(1) local work | no helper allocation | barriers + queue ownership |
| z test | dense depth buffer | O(1)/fragment | buffer preallocated | tile ownership |
| ChrisCPU decode | byte stream → ChrisInsn | bounded O(1)/instruction | none | CPU-local |
| VM trace append | circular trace array | O(1) | none | CPU-local in current model |

## Scaling thresholds and redesign criteria

The atlas is descriptive, not an endorsement that every current algorithm should remain forever.

Typical future thresholds:

- PMM fragmentation or large memory may justify hierarchical bitmaps, buddy allocation or extent indexes;
- a heavily parallel scheduler may need per-CPU queues and work stealing;
- many VM MMIO regions may justify an interval tree;
- larger compiler workloads may justify hashed symbol tables or arenas;
- filesystem scale may justify extent trees or B-tree indexes;
- graphics scale may require more aggressive spatial binning and GPU-resident structures.

Such changes should follow measurement and invariants, not fashion.

The key documentation rule is preserved across any redesign: every subsystem must state representation, invariant, algorithm, complexity, ownership and concurrency together.
