---
id: cache-hierarchy
lang: en
type: technical-chapter
volume: 02-computer-architecture
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/mm.h
  - kernel/metal/mm.c
  - chrisvm/cpu/emulator/mmu.c
  - chrisvm/buses/mmio.c
symbols:
  - map_mmio_page
  - chris_translate
  - chris_va_read
  - chris_phys_read
  - chris_phys_write
depends_on:
  - cpu-datapath-isa
  - x86-64-memory-privilege
related:
  - coherence
  - atomics-memory-model
  - buses-mmio-dma
---

# Caches and memory hierarchy

## Scope and physical motivation

An instruction names an architectural operation; it does not prescribe the number of clock cycles needed to obtain its operands. Registers, SRAM arrays, interconnects and DRAM have different capacities, access costs and placement constraints. A large array needs address decoding, wires and sensing circuitry over a larger physical area. DRAM additionally operates through banks and rows and requires refresh. A processor cannot turn arbitrarily large memory into a single-cycle register file merely by increasing clock frequency.

A cache retains a subset of information obtainable elsewhere. Its usefulness depends on locality: temporal locality reuses information recently accessed, while spatial locality accesses nearby addresses. The cache exploits these patterns by retaining recently useful blocks and transferring adjacent bytes together. A cache line is that transfer and bookkeeping unit; it is not a page, a C object or an individual machine word.

The organization below is a conceptual hardware hierarchy, not a topology discovered on a particular computer. Capacities, sharing domains, inclusivity and latencies must be obtained for the actual processor. The ChrisCPU interpreter reviewed here does not instantiate this hierarchy as a timing model.

![Conceptual cache hierarchy and separate device route](../../assets/diagrams/cache-hierarchy-en.svg)

| Structure | Information retained | Typical reason for a miss | What a miss does not imply |
|---|---|---|---|
| Instruction/data cache | Bytes grouped into cache lines | The requested block is absent | A virtual-memory fault |
| TLB | Address translations and permissions | The translation is absent | The data bytes are absent from all caches |
| Page-walk cache | Intermediate translation information | A walk component is absent | A disk access |
| OS file cache | File or block contents | Software has no usable cached copy | A CPU-cache miss is the only cost |

Translation and data access interact, but remain separate mechanisms. A TLB miss may trigger a walk through page tables whose bytes are already cached. A page fault instead indicates a condition that requires architectural exception handling. Conflating these events produces incorrect explanations of both performance and correctness.

## Line representation and address decomposition

Consider an illustrative cache with capacity C bytes of data, line size B bytes and A ways per set. The number of sets is S = C/(B×A). For power-of-two B and S, a simple physically indexed model decomposes address p into an offset, set index and tag:

```text
block  = floor(p / B)
offset = p mod B
set    = block mod S
tag    = floor(block / S)
```

The selected set holds A candidate lines. Each candidate needs a valid indicator and tag; a write-back design additionally needs dirty state, and a coherent design needs protocol state. Data capacity alone excludes these metadata costs. Invalid lines must never produce a hit merely because an old tag happens to match.

For a 32 KiB, eight-way, 64-byte-line example, S = 64. Six address bits select a byte and six select the set. Address 0x12340 has block number 1165, set 13, tag 18 and offset zero. Address 0x13340 has the same set and a different tag. Their separation is 4096 bytes: S×B. This arithmetic describes the example; it is not a promise that every real cache uses these index bits. Real designs can use hashing or different indexing at different levels.

A software model can search all A ways in O(A) operations. Hardware may compare tags concurrently; software complexity is therefore not a prediction of hardware hit latency. If every set uses the same line count, raw storage is S×A×B plus metadata. For fixed total capacity, more ways reduce some conflict patterns but require more tag comparisons and more complex selection.

## Hit, fill, eviction and ownership

A blocking teaching model can process a read as follows:

```text
split address into tag, set and byte offset
search valid ways in the set
if a matching tag exists:
    update replacement metadata
    return requested bytes
choose an invalid way, otherwise choose a victim
if the victim is dirty:
    write its old block to the lower level
fetch the requested block from the lower level
install data and tag; mark valid and clean
update replacement metadata
return requested bytes
```

The critical invariant is that every valid entry identifies the block represented by its data. Installation must not expose a new tag with old bytes. A dirty victim must not be overwritten before its modified information has been preserved. An access crossing a line boundary may require two lookups and two fills. It is not automatically atomic merely because the source program uses one expression.

Real nonblocking caches track outstanding misses, merge requests to the same block and allow independent work to proceed while a fill is pending. These mechanisms require finite tracking resources. Saturation can stall new accesses even when execution units are otherwise available. A simulator that updates data immediately on every miss cannot reproduce this queueing behavior without explicit timing and resource models.

Replacement chooses which resident block loses its place. Least recently used replacement retains an ordering of recency; an exact A-way ordering has A! possible permutations and needs at least ceil(log2(A!)) bits to encode. Implementations often choose approximate policies. A FIFO policy, random selection and tree-based pseudo-LRU have different behavior; naming any of them as the hardware policy requires evidence for that processor.

## Miss classification and associativity

A compulsory miss occurs on the first access to a block in the modeled execution. A capacity miss occurs because the working set exceeds the available capacity even in a fully associative comparison cache. A conflict miss arises from placement restrictions: enough blocks contend for the same set despite capacity elsewhere. This classification depends on the reference trace and comparison model, not merely on seeing that an access was slow.

In the example above, nine blocks separated by 4096 bytes compete for eight ways in one set. Under exact LRU, repeatedly reading the nine blocks in order causes all accesses after warm-up to miss. The live payload is only 576 bytes, much smaller than 32 KiB. Increasing total free memory does not cure this access pattern. Changing placement, the stride, associativity or traversal order can change it.

Sequential traversal of 32-bit elements uses sixteen elements from each 64-byte line when aligned. With no reuse and no prefetching, it incurs approximately one fill per sixteen elements. Reading one such element from each different line uses only four of the sixty-four fetched bytes: useful-byte efficiency is 6.25%. That efficiency describes transfer utilization, not the total application speedup available from changing layout.

## Latency, bandwidth and a bounded numerical model

Average memory access time is useful when its assumptions are explicit. Let t1 be the L1 lookup cost, m1 its miss probability, t2 the additional L2 lookup cost after an L1 miss, m2 the conditional L2 miss probability, and tm the additional memory cost after an L2 miss. A serial, blocking model gives:

```text
AMAT = t1 + m1 × (t2 + m2 × tm)
```

Using illustrative costs of 4, 12 and 180 cycles and miss probabilities 0.05 and 0.20 yields 6.4 cycles. Reducing m1 to 0.02 yields 4.96 cycles. These are calculated examples, not measured ChrisOS performance. Mixing an unconditional L2 miss rate with this conditional formula double-counts filtering and gives the wrong answer.

| L1 miss probability | Conditional L2 miss probability | Calculated cycles/access |
|---:|---:|---:|
| 0.00 | 0.20 | 4.00 |
| 0.02 | 0.20 | 4.96 |
| 0.05 | 0.20 | 6.40 |
| 0.10 | 0.20 | 8.80 |
| 0.20 | 0.20 | 13.60 |

This model does not account for overlapping misses, prefetching, writebacks, coherence traffic or memory-controller scheduling. A pointer chain has dependent addresses and exposes latency: the next load cannot start until the previous pointer arrives. Independent streams can overlap requests and eventually become bandwidth limited. For a simplified stream with effective bandwidth W bytes/s and latency L seconds, approximately W×L bytes must be outstanding to sustain that bandwidth. Dividing by line size estimates the required concurrent line transfers, provided other resources do not become limiting.

## Writes, memory types and device semantics

Write-through propagates a write to the next level as part of the policy; buffering may still delay physical completion. Write-back retains modified bytes and marks the line dirty until a later transfer. Write allocation specifies whether a write miss first obtains a line; it is a separate decision. A successful CPU store is not equivalent to persistence on storage or completion of a device command.

For x86 mappings, cache-control interpretation involves architectural memory types and their selection rules. PWT and PCD bits must not be treated as independent universal switches divorced from PAT, MTRRs and the paging level. Consult the processor specification before changing them. In particular, a framebuffer memory range and a register whose read acknowledges an interrupt have different access semantics. Repeating, combining or speculating register operations can change device behavior.

`map_mmio_page` in the reviewed kernel requires page-aligned physical input. It reserves one virtual page from the MMIO window under `mm_enter`/`mm_leave`, checks window exhaustion, and calls `map_4k` with `MM_PRESENT | MM_WRITE | MM_PWT | MM_PCD | MM_NX`. Misalignment and exhaustion invoke `panic`. This establishes the flags requested by this mapping helper; it does not prove the effective memory type for every platform or that all device mappings use this helper.

The helper installs a supervisor mapping because it does not request `MM_USER`; NX requests non-executable access. Page allocation of the virtual window and mapping installation are separate steps. Driver correctness additionally requires access widths, ordering, device ownership and the relevant completion protocol. `volatile` alone supplies neither a CPU-cache policy nor a complete synchronization protocol.

## What the current ChrisCPU actually models

`chris_translate` walks guest paging structures and checks architectural access conditions. The inspected routine does not implement cache tags, cache replacement, a data-cache miss penalty or PAT/MTRR timing. `chris_va_read` translates access chunks and dispatches them through `chris_phys_read`. Its chunk size is limited by a 4 KiB boundary. That split is a translation/access boundary, not a modeled cache-line size.

In `chris_phys_read` and `chris_phys_write`, an access wholly inside RAM uses host `memcpy`. A wholly contained framebuffer access uses its backing array; writes additionally mark the framebuffer dirty. Remaining physical accesses are resolved through the MMIO table and callbacks, byte by byte. `chris_mmio_find` scans the bounded table, so this fallback costs O(n×M) for n bytes and M mapping slots in the worst case. RAM copying costs O(n) bytes of host work. Neither expression denotes guest cycles.

An MMIO callback failure or unmapped byte returns an error. A multi-byte operation can already have performed earlier callbacks before a later failure. Therefore this path is not a transaction with rollback. RAM and framebuffer range checks use subtraction after a base check to bound accesses. These details explain functional dispatch and failure behavior; they do not demonstrate fidelity to every physical device's access-width requirements.

The host processor naturally caches the emulator's arrays, instructions and metadata. Those host caches affect elapsed time, but they are not guest caches exposed by this model. A faster host run can reflect compiler choices or host locality while leaving every simulated guest instruction unchanged. Conversely, adding a guest cache simulator can slow host execution while representing a faster hypothetical guest machine.

## Correctness, security and optimization boundaries

Data-cache coherence, memory ordering and TLB invalidation solve distinct problems. Coherence constrains copies of a memory location. Ordering constrains observations across operations. A TLB shootdown removes obsolete translations. None is a substitute for the others. Recycling a physical frame while another CPU still holds its old translation is an ownership error that a coherent data cache cannot repair.

Cache state can also carry timing information across protection boundaries. Page permissions prevent architectural reads but do not by themselves establish complete timing isolation. This chapter does not certify a mitigation strategy for ChrisOS. Such a claim requires a threat model, identified sharing domains and tests for the relevant processor and execution environment.

Useful layout changes include contiguous arrays, separating frequently accessed fields from cold fields, blocking a matrix traversal to retain useful subregions, and avoiding unnecessary full-frame copies. Padding every object to a cache line can increase memory consumption and TLB pressure. Optimizing a layout requires measuring the dominant access pattern and accounting for those costs, rather than treating alignment as universally beneficial.

## Validation and revision limits

The source reconciliation for this chapter is tied to `da3df29cb397932c43d32373871fb9380e688ade`. The address split, conflict sequence and AMAT examples are reproducible with `python scripts/check_cache_examples.py`. That script checks a deliberately simplified model; it does not execute the kernel or establish native cache timings.

For a hardware performance investigation, record CPU identification, cache topology, compiler flags, workload, working-set sizes, warm-up policy and repeated measurements. Separate cold from warm runs and dependent from independent accesses. Counters need model-specific definitions; a generic label such as “cache miss” is insufficient to identify the event counted. Emulator wall time must be reported separately from any explicitly modeled guest cycles.

Further implementation work would require a declared timing model, line and queue state, memory-type handling and coherence rules before ChrisCPU could claim cache simulation. These are future requirements, not features inferred from the existing physical-memory accessor. The following chapters develop coherence and atomic ordering independently of this capacity and locality model.

## Primary reference

- [Intel 64 and IA-32 Software Developer's Manuals](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html), system programming sections on memory cache control, paging attributes and multiprocessor memory. The architectural manual governs memory-type behavior; numerical examples and the teaching cache above are explicitly independent illustrative models.
