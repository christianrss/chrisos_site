---
id: algorithmic-complexity
lang: en
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
- kernel/gfx/virtq.c
- kernel/gfx/virtq.h
symbols:
- virtq_alloc
- virtq_publish
- virtq_take
- virtq_reclaim
- virtq_init
depends_on:
- data-representation-layout
related:
- data-structures
- systems-algorithms
---

# Algorithm analysis and systems cost models

<div class="abstract">
Algorithm analysis provides a language for reasoning about growth, resource bounds and trade-offs, but systems software requires more than Big-O notation. Cache locality, allocation, synchronization, bounded capacity, interrupt context, worst-case latency and hardware interaction can dominate an implementation whose asymptotic complexity appears favorable. This chapter develops complexity analysis specifically for kernels, compilers, drivers, graphics and emulators.
</div>

## What an algorithm is

An algorithm is a finite procedure that transforms input state into output state while preserving specified invariants.

For systems documentation, describing an algorithm requires at least:

- input representation;
- preconditions;
- operation sequence;
- maintained invariants;
- termination condition;
- output/postcondition;
- failure behavior;
- resource consumption.

A function name is not an algorithm description. “Allocate a page” omits the representation of free state, search policy, synchronization and what happens when no page exists.

## Input size

Complexity statements need a defined size variable.

Examples:

- n = number of array elements;
- p = number of physical pages;
- h = page-table depth;
- v = vertices;
- t = triangles;
- b = blocks in a file;
- s = source-code length;
- q = number of queued jobs.

Without the variable, saying an operation is “linear” is incomplete.

## Big-O

Big-O gives an upper growth class: f(n) is O(g(n)) when f does not grow faster than a constant multiple of g beyond some point.

Common classes:

| Class | Example |
|---|---|
| O(1) | indexed array access |
| O(log n) | balanced tree lookup |
| O(n) | linear scan |
| O(n log n) | comparison sort |
| O(n²) | all-pairs nested scan |
| O(2^n) | exhaustive subset search |

Big-O deliberately ignores constant factors and lower-order terms. That is useful for scalability but insufficient for low-level performance by itself.

## Omega and Theta

Big-O is an upper bound. Omega describes a lower bound. Theta describes asymptotically tight growth.

If an array scan always examines every element, runtime is Theta(n), not merely O(n).

Precise terminology matters when comparing designs. An operation that is O(n) but usually exits immediately has a different expected profile from one that is Theta(n).

## Worst, average and expected case

Systems software often prioritizes worst-case behavior.

A hash table may have expected O(1) lookup but O(n) worst case. That can be acceptable in a desktop utility and dangerous in a hard real-time interrupt path.

Documentation should distinguish:

- worst case;
- best case;
- average case under a stated distribution;
- expected case for randomized/probabilistic structures;
- amortized cost across a sequence.

## Amortized analysis

A dynamic array append may occasionally require O(n) copying when capacity grows, yet if capacity doubles, a long sequence of appends has amortized O(1) cost per append.

Amortized complexity is not a probability. It spreads occasional expensive operations across a sequence.

In kernels, an amortized design still needs consideration of where the expensive individual operation may occur. A rare O(n) resize inside an interrupt-disabled critical section can be unacceptable despite favorable amortized cost.

## Space complexity

Memory is a first-class resource.

An algorithm can reduce time by storing more metadata, precomputed tables or caches. Page allocators, filesystem caches, JITs and graphics pipelines all exchange memory for speed.

Space analysis should count:

- persistent structure size;
- temporary scratch space;
- recursion/stack depth;
- fragmentation;
- alignment and padding;
- duplicated or cached state.

On a kernel path, allocation itself may be constrained or forbidden.

## Locality

Two O(n) algorithms can differ by an order of magnitude because of memory access patterns.

Sequential traversal of a contiguous array benefits from spatial locality and hardware prefetching. Following pointers through scattered nodes can cause cache and TLB misses.

A useful systems cost model therefore includes:

    algorithmic operations
    + memory hierarchy misses
    + synchronization
    + device latency

The asymptotic class remains important, but the machine executes memory references, not abstract steps.

## Branch predictability

Control flow also has hardware cost. A branch whose outcome is highly predictable may be cheap; data-dependent unpredictable branches can repeatedly flush speculative work.

Branchless transformations can improve some hot loops, but they may execute more operations or reduce readability.

Optimization requires measurement on the actual workload rather than assuming fewer branches is always better.

## Allocation cost

An algorithm that allocates one node per operation depends on the allocator's behavior.

Questions include:

- Is allocation O(1), a scan, or a tree lookup?
- Can it sleep?
- Does it take a global lock?
- Can it fail?
- Does it fragment memory?
- Must the object be physically contiguous?

A textbook data structure cannot be evaluated independently of its allocator in kernel code.

## Lock complexity

A theoretically O(1) operation can block behind a contended global spinlock for an unbounded practical duration relative to local work.

Concurrency analysis therefore adds:

- lock acquisition order;
- contention domain;
- critical-section length;
- progress property;
- interrupt/preemption state;
- cache-line bouncing.

Big-O describes work, while synchronization describes coordination cost.

## Progress properties

Concurrent algorithms are sometimes classified as:

- blocking: one stalled owner can delay others;
- lock-free: system-wide progress is guaranteed;
- wait-free: every operation finishes in bounded own steps;
- obstruction-free: progress occurs without contention.

A spinlock-protected queue is blocking in this formal sense even if its ordinary critical section is short.

The stronger categories are not automatically better; complexity, memory reclamation and proof burden rise substantially.

## Bounded versus dynamic structures

Operating systems often prefer fixed-capacity tables or rings.

A bounded array can provide:

- predictable memory use;
- no allocator dependency;
- simple failure behavior when full;
- stable addresses.

The cost is a hard capacity limit and possibly linear scans.

Dynamic trees or hash tables scale further but introduce allocation, more complex teardown and failure paths.

The correct structure depends on the system's scale and invariants, not on generic preference.

## Real-time and latency bounds

For real-time work, average throughput is insufficient. The key quantity can be maximum response latency.

An O(log n) tree may still be unsuitable if it allocates or takes an unpredictable lock. A fixed-size O(n) scan with small bounded n can have a tighter worst-case bound.

Asymptotic notation assumes n can grow. Systems often intentionally cap n so a simpler algorithm has a stronger practical bound.

## Device latency

Drivers interact with devices whose completion time is not proportional to CPU instruction count.

A storage operation may spend microseconds or milliseconds waiting on hardware. CPU complexity still matters for queue management, but end-to-end latency includes the device.

Polling and interrupts also change cost. Polling burns CPU while waiting; interrupts add entry/exit and coordination overhead but release CPU time.

## Throughput versus latency

Latency measures time for one operation. Throughput measures operations completed per unit time.

Batching can improve throughput while increasing individual latency.

Graphics command buffers, block I/O queues and network packet processing often exploit batching. Interactive paths may prefer smaller batches.

Documentation should state which objective the algorithm optimizes.

## Tail latency

The 99th or 99.9th percentile can matter more than the average for responsive systems.

Long pauses can arise from:

- lock contention;
- allocator slow paths;
- cache misses;
- page faults;
- device retries;
- queue buildup;
- garbage collection;
- large critical sections.

A design with excellent mean performance can still feel unstable if tail latency is high.

## Complexity of page-table translation

A four-level x86-64 page-table walk has a bounded number of hierarchy steps, so with fixed architecture depth it is O(1) relative to address-space size.

However, each level can require a memory access. Hardware TLBs exist because four dependent memory accesses per ordinary load/store would be expensive.

This is a good example of why O(1) does not mean “cheap.”

## Complexity of bitmap allocation

A bitmap records one state bit per resource unit. Testing a known position is O(1). Finding a free position by scanning can be O(n) in the number of represented units.

A cursor or hint improves typical behavior by avoiding repeated scans from zero but does not remove the worst case.

Bit-level density makes the representation memory-efficient and cache-friendly compared with storing a full record for every page.

## Complexity of ring queues

A fixed-capacity circular queue with head, tail and count supports enqueue/dequeue in O(1).

The cost is bounded capacity. Full and empty states must be represented unambiguously, and multi-producer/multi-consumer access requires synchronization.

The structure is common in kernels and devices because indices move without relocating elements.

## Compiler complexity

A lexer usually scans source approximately linearly in source length. Parser complexity depends on grammar and parser strategy. Symbol lookup depends on representation: linear arrays, hash maps or trees have different cost.

Optimization passes may traverse intermediate representation repeatedly, multiplying cost by program size and number of passes.

Compiler performance must therefore document both the theoretical algorithm and current bounded implementation choices.

## Graphics complexity

Rasterization cost depends on geometry and covered pixels.

A naive triangle loop that tests every screen pixel is roughly O(T × W × H). Bounding boxes reduce work to pixels near each triangle. Tile binning first associates triangles with tiles so parallel workers process smaller regions.

Z-buffer depth testing adds O(1) work per candidate fragment but also memory bandwidth.

Asymptotic models provide structure; actual performance depends heavily on vectorization, cache behavior and overdraw.

## Emulator complexity

A simple interpreter performs fetch/decode/execute per guest instruction. Runtime is approximately proportional to guest instruction count multiplied by decoder/executor cost.

A JIT pays compilation cost up front to reduce repeated execution cost. Whether JIT wins depends on how often code is reused.

This is a classic time-space and setup-versus-steady-state trade-off.

## Measurement

Complexity predicts scaling; benchmarking observes a particular implementation on a particular workload.

A sound engineering process uses both:

1. derive algorithmic expectations;
2. identify constant-factor risks;
3. measure representative workloads;
4. profile hotspots;
5. change the algorithm or representation if evidence justifies it;
6. verify correctness again.

Benchmarks without a model can optimize noise. Models without measurement can optimize the wrong cost.

## Documentation rule

Every implementation-facing chapter in this corpus should, when applicable, record a compact algorithm table:

| Operation | Structure | Time | Space/side effect | Synchronization |
|---|---|---|---|---|
| example lookup | array | O(n) worst | no allocation | subsystem lock |
| example enqueue | ring | O(1) | bounded capacity | queue lock |

The table does not replace explanation. It makes hidden performance and concurrency contracts visible.

The following chapter introduces the core data structures used to realize these algorithms.

## A source-derived queue cost model

In `kernel/gfx/virtq.c`, `virtq_alloc(q, n, head)` does not obtain an arbitrary chain in constant time. It walks n software links, assigns NEXT flags and detaches those descriptors from the free list. Its local work is O(n), while its rejection of n greater than `nfree` happens before traversal. `virtq_publish` writes one ring entry and advances one index, so its local work is O(1). `virtq_take` returns at most one completion per call. `virtq_reclaim` follows the allocated chain, costing O(n) for a valid n-descriptor chain.

| Operation | Scaling parameter | Local work | External wait included? |
|---|---|---|---|
| Initialize | Queue capacity Q | O(Q) | No |
| Allocate chain | Descriptor count n | O(n) | No |
| Set one descriptor | Fixed 16-byte layout | O(1) | No |
| Publish one head | One ring entry | O(1) | No |
| Take one completion | One used entry | O(1) | No |
| Reclaim valid chain | Descriptor count n | O(n) | No |

For a request using n descriptors, the bookkeeping sum is O(n) even though publication alone is constant-time. Device processing, bus traffic, interrupt delivery and caller polling add separate terms. If a caller polls until completion, an unbounded device delay can produce an unbounded number of O(1) calls. Constant cost per poll does not establish a completion deadline.

The arrays reserve capacity for `VQ_MAX = 128`, so the shipped implementation has a fixed upper storage bound. Describing the family as O(Q) remains useful for understanding what changes if that bound is raised. Treating every bounded program as O(1) would hide the difference between touching one descriptor and touching all 128. Both the parameterized model and the actual bound belong in the documentation.

Locality differs from allocation behavior. These helpers allocate no host heap memory themselves, and descriptor bytes are contiguous. Nevertheless, traversing software links and publishing to device-shared memory can have different cache and synchronization costs. The source does not explain a measured throughput advantage over every alternative, so no such conclusion is justified without a workload and measurement.

An alternative bitmap could search for free descriptors and reduce link metadata, but obtaining a chain would still require identifying n entries and establishing ownership. A larger batched submission API could amortize publication barriers over several heads, at the cost of a different latency and synchronization contract. These are design alternatives, not claims that the current implementation already performs batching. Complexity analysis is most useful when it states which contract an optimization would change.
