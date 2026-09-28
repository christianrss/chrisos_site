---
id: memory-controller-dram-organization
lang: en
type: technical-chapter
volume: 02-computer-architecture
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chrisvm.h
  - chrisvm/machine/machine.h
  - chrisvm/machine/machine.c
  - chrisvm/buses/mmio.c
  - kernel/metal/bootinfo.h
  - kernel/metal/bootinfo.c
  - kernel/metal/pmm.h
  - kernel/metal/pmm.c
symbols:
  - ChrisConfig
  - ChrisMachine
  - chris_machine_create
  - chris_phys_read
  - chris_phys_write
  - bootinfo_memmap_count
  - bootinfo_memmap_entry
  - pmm_init
depends_on:
  - sram-dram
  - transmission-lines-differential-signals
  - buses-mmio-dma
  - cache-hierarchy
related:
  - physical-memory
  - coherence
  - atomics-memory-model
  - pmm-algorithms
---

# DRAM organization and memory controllers

## Scope

Operating-system memory management usually begins from a physical memory map: ranges are usable, reserved, firmware-owned, device-mapped or unavailable. That view is intentionally above the electrical and scheduling machinery that makes DRAM respond to a physical address.

Below the page allocator sits a hierarchy of channels, ranks, banks, rows, columns, command timing and refresh. A memory controller translates requests from CPU/interconnect domains into DRAM commands while preserving ordering, timing, data integrity and fairness.

This chapter connects those layers without collapsing them:

- a **page frame** is an operating-system allocation unit;
- a **cache line** is a cache/coherence transfer unit;
- a **DRAM row** is an array-activation unit;
- a **burst** is a data-transfer unit on the memory interface;
- a **channel/rank/bank** is part of physical DRAM organization;
- the **memory controller** schedules commands subject to device timing and architecture rules.

The current ChrisOS kernel does not implement a DRAM controller driver. It consumes firmware/bootloader memory information and manages page frames. The current ChrisVM implementation is even more abstract: guest RAM is a zero-initialized host byte buffer, and in-range physical reads/writes use <code>memcpy</code>. No channel, rank, bank, row-buffer or timing model exists in the reviewed source.

![From CPU requests through a memory controller to channel, rank, bank and row](../../assets/diagrams/memory-controller-dram-organization-en.svg)

## From the DRAM cell to the system address space

A DRAM cell represents a bit using charge associated with a small capacitor controlled by an access transistor. Charge leaks, so information must be refreshed periodically.

A memory chip organizes many cells into arrays. Cells are not individually selected from the external bus in the way software addresses bytes. Instead, the DRAM device uses internal organization and commands:

1. select a bank;
2. activate a row into the bank's row buffer/sense amplifiers;
3. issue column-oriented read/write commands;
4. transfer data as a burst;
5. eventually precharge the bank so another row can be activated.

The row buffer is physically tied to sense amplification. "Opening a row" means the selected row's cell contents are sensed and represented in the row-buffer circuitry.

This explains why two accesses to the same bank can have very different costs depending on whether the required row is already open.

## Terminology hierarchy

Physical memory products and controllers expose several nested concepts.

| Level | Meaning |
|---|---|
| Channel | Independent command/data interface controlled by the memory controller |
| DIMM/module | Packaged memory module connected to one or more channels/subchannels |
| Rank | Group of DRAM devices participating together in a transfer |
| Chip/device | Individual DRAM integrated circuit |
| Bank group | Grouping used by newer DDR generations for timing/resource rules |
| Bank | Independently activated DRAM array domain |
| Row | Large set of cells activated into row-buffer circuitry |
| Column | Position selected from an active row for a read/write burst |
| Burst | Sequence of data transfers performed by one column command |

The exact hierarchy varies by DRAM generation and module topology. Documentation should therefore distinguish general concepts from a specific DDR standard or DIMM configuration.

## Channels

Multiple memory channels increase parallelism and aggregate bandwidth because independent requests can be sent over independent data/command paths.

If a channel transfers D bits per data beat at effective rate R transfers/s, an idealized raw data bandwidth is:

    bandwidth = (D / 8) * R bytes/s

For C identical independent channels:

    aggregate_peak = C * (D / 8) * R

This is a peak transfer calculation, not sustained application bandwidth. Command overhead, refresh, turnarounds, row conflicts, queueing, cache behavior and read/write mixes reduce delivered bandwidth.

A controller may interleave physical address regions across channels so sequential cache lines distribute traffic. The exact address-bit mapping is platform-specific.

## Ranks

A rank contains devices that collectively provide the data width required by a memory transfer. A controller selects a rank, then communicates with devices in that rank in parallel.

Multiple ranks can improve capacity and sometimes provide additional scheduling opportunities, but switching ranks can introduce timing/turnaround constraints.

Ranks are not operating-system NUMA nodes. A NUMA node is a higher-level locality domain involving processors, controllers and memory access costs. Several ranks may exist inside one NUMA node.

## Banks and bank-level parallelism

A DRAM bank can keep one row active while another bank performs independent work. This enables **bank-level parallelism**.

Suppose two accesses target:

    request A -> bank 0, row 10
    request B -> bank 1, row 42

The controller may overlap portions of their timing if the standard and shared resources allow it.

If both target bank 0 but different rows, the second must generally wait for the current row to close/precharge and the new row to activate.

Therefore address mapping strongly influences parallelism.

## Rows, columns and the row buffer

A row activation moves a large amount of internal state into the sense-amplifier/row-buffer domain.

Three common access cases are:

### Row hit

The desired row is already active in the selected bank.

Typical path:

    READ/WRITE column command -> burst

This avoids precharge and activation for that request.

### Row closed

No row is active.

Typical path:

    ACTIVATE -> wait required delay -> READ/WRITE -> burst

### Row conflict

A different row is active.

Typical path:

    PRECHARGE -> wait -> ACTIVATE new row -> wait -> READ/WRITE -> burst

A row conflict therefore consumes more command latency than a row hit.

This is why controller scheduling can improve throughput by exploiting row locality, although excessive preference for row hits can starve other requests.

## Address mapping

The CPU provides a physical address. The memory controller maps physical-address bits or transformed/hash-derived bits into:

- channel;
- rank;
- bank group;
- bank;
- row;
- column;
- byte position within transfer.

A simple illustrative mapping could be:

    low bits        -> byte/burst offset
    next bits       -> column
    selected bits   -> channel/bank
    high bits       -> row

Real systems can XOR address bits to reduce hot spots and distribute traffic.

The operating system often does not know the complete mapping. When it does know topology through platform interfaces, it can make locality-aware decisions, but software page numbers should not be assumed to map linearly to DRAM rows.

## DDR transfer principle

DDR means data is transferred on both transitions of a clocking relationship, while modern devices also use internal prefetch organization so the external data rate can exceed the core array command frequency.

Marketing transfer rates such as MT/s describe transfers per second, not CPU clock frequency.

For a 64-bit data interface:

    bytes_per_transfer = 64 / 8 = 8

At effective rate R MT/s:

    ideal_bandwidth_GBps ~= 8 * R / 1000

with unit conventions stated explicitly.

ECC DIMMs may have additional physical data bits, but user payload width and correction metadata must not be confused when computing useful bandwidth.

## Commands

At a conceptual level, important DRAM commands include:

- ACTIVATE — select/open a row;
- READ — transfer data from columns of the active row;
- WRITE — transfer data into columns of the active row;
- PRECHARGE — close an active row and prepare the bank;
- REFRESH — restore charge state according to refresh requirements.

Actual standards include additional command/state rules. A simulator should implement only the subset matching its declared model and should not label simplified timing as a faithful DDR-generation implementation unless verified against that specification.

## Timing parameters as constraints

Common timing names describe minimum separations between events. They are not independent "latencies" that can simply be added in every case.

Conceptually:

| Parameter | Constraint represented |
|---|---|
| tRCD | ACTIVATE to allowed column access |
| tCL / CAS latency | read-command-related data timing |
| tRP | PRECHARGE to subsequent ACTIVATE |
| tRAS | minimum active-row duration |
| tRC | row-cycle constraint |
| tRRD | spacing between activates under defined bank relationships |
| tFAW | limit on number of activates in a rolling window |
| tWR | write recovery before precharge |
| tRFC | refresh-cycle occupancy |
| tREFI | nominal refresh interval relationship |

The exact definition and units depend on the DRAM standard and operating point.

A correct controller model treats these as state-machine constraints over commands. It does not assign one fixed "DRAM latency" to every memory request.

## Row-hit latency versus request latency

A request's observed memory latency includes more than DRAM intrinsic timings:

    request latency =
        queue wait
        + command scheduling delay
        + row-state delay
        + bus turnarounds
        + data transfer
        + interconnect/controller overhead

If the request arrives behind many older requests, queueing may dominate.

Therefore a simulator that models tRCD and tCL but ignores request queues can still produce unrealistic latency under load.

## Open-page and close-page policy

After accessing a row, the controller can:

- keep it open, hoping for another row hit;
- precharge early, reducing future row-conflict cost.

An **open-page** policy favors locality when repeated accesses hit the same row.

A **close-page** policy can be better for workloads with little row reuse or heavy contention.

Adaptive controllers estimate future usefulness.

The policy affects performance, not architectural correctness, provided timing and ordering rules are maintained.

## Request queues

A memory controller usually has finite queues.

A request record can include:

- physical address;
- read/write type;
- arrival time;
- requester/core;
- decoded channel/rank/bank/row/column;
- dependency/order metadata;
- completion callback/tag.

Finite queues create backpressure. When a queue is full, upstream caches/interconnects cannot inject unlimited misses.

A timing-oriented ChrisCPU/ChrisVM model would need explicit queue capacity; an unbounded vector hides saturation behavior.

## FR-FCFS scheduling

A classic memory-scheduling policy is First-Ready First-Come-First-Serve (FR-FCFS).

Simplified logic:

1. among commands that are legal now, prefer requests that can make progress immediately, often row hits;
2. among equally ready requests, prefer the oldest.

This improves row-buffer locality and throughput compared with strict FIFO in many workloads.

However, row-hit preference can starve a request that repeatedly conflicts with a hot row. Practical schedulers add age thresholds, fairness windows or per-requester controls.

For a teaching simulator, FR-FCFS is useful because it demonstrates the trade-off between throughput and fairness.

## Scheduling complexity

With Q queued requests, a naive scheduler can scan all Q requests each cycle and evaluate timing readiness:

    O(Q)

If it also compares ordering constraints or searches for row hits, constant factors grow.

A simulator can maintain per-bank queues and ready sets to reduce selection cost.

Hardware scheduling occurs in parallelized logic; software algorithmic complexity is not a prediction of physical scheduler delay.

## Read/write turnarounds

The data bus changes direction between reads and writes. Turning around the bus can impose bubbles due to electrical and protocol timing.

Controllers often batch writes:

- serve reads to minimize latency;
- when write queue reaches a threshold, drain a group of writes;
- switch back to reads.

This improves bus efficiency but can increase individual request latency.

A realistic timing model therefore needs separate read/write queue state or at least explicit direction-change penalty.

## Refresh

DRAM charge decays, so cells require refresh.

Refresh consumes time during which some or all memory resources are unavailable, depending on the refresh mechanism and device organization.

A model can represent refresh as periodic scheduled events that:

1. become due according to a configured interval;
2. block affected banks/ranks for a refresh duration;
3. obey postponement/pull-in rules if modeled;
4. prevent starvation of mandatory refresh.

A simulator that omits refresh can still be useful for functional behavior but cannot claim complete DRAM timing.

## Temperature and refresh

Physical retention characteristics depend on conditions such as temperature. Real systems can adjust refresh behavior according to device/platform rules.

An educational emulator usually does not need thermal coupling, but documentation must not imply that one hard-coded refresh interval describes every real system.

## ECC

Error-correcting code memory adds redundancy so certain data corruption patterns can be detected and often corrected.

At a high level, an ECC path may:

1. compute check bits when writing a data word;
2. store data plus check information;
3. recompute syndrome on read;
4. correct supported error classes;
5. report corrected or uncorrectable events.

ECC is separate from virtual-memory protection. A page can be mapped correctly while its physical storage experiences a bit error.

A future memory model could inject deterministic bit faults to test error-reporting paths, but current ChrisVM guest RAM has no ECC model.

## Scrubbing

Memory scrubbing periodically reads memory, corrects recoverable ECC errors and writes corrected data back, preventing accumulation.

This is a reliability mechanism above basic access scheduling.

A simulator that introduces ECC faults should also define whether scrubbing exists; otherwise long-run error behavior is arbitrary.

## Memory ordering versus DRAM scheduling

CPU memory-order semantics constrain what effects software may observe. DRAM scheduling can reorder physical command service internally, but it cannot violate the visibility contract established by caches, coherence, ordering rules and controller/interconnect logic.

For example, servicing a later read before an earlier unrelated read at DRAM can be legal if architectural ordering requirements are still preserved.

Thus:

- **program order**;
- **cache/coherence order**;
- **memory-controller queue order**;
- **DRAM command order**

are different layers.

A memory controller simulator should not infer architectural legality solely from arrival order.

## Coherence and memory controllers

In coherent systems, most CPU loads/stores interact with caches first. DRAM often sees:

- cache-line fills after misses;
- dirty writebacks;
- prefetch traffic;
- non-temporal or special memory traffic depending on architecture.

The memory controller generally does not implement the complete CPU cache-coherence protocol itself, though system architecture can integrate coherence agents around the controller.

A standalone DRAM model below the cache hierarchy can accept line-sized memory transactions rather than individual CPU instructions.

## Cache-line granularity versus burst granularity

A cache line might be 64 bytes while the memory channel transfers smaller chunks per beat/burst.

The controller and PHY deliver enough burst data to fill or write back a cache line.

Software should not equate:

    one load instruction
    one cache line
    one DRAM command
    one burst

These are different units. One unaligned load may touch two cache lines; one line fill may involve multiple bus transfers; row activation covers much more data than one line.

## NUMA

Non-Uniform Memory Access systems attach memory closer to some CPU/socket domains than others.

A physical address belongs to a locality domain. Accessing remote memory can traverse additional interconnect links and incur different latency/bandwidth.

NUMA is above individual DRAM bank structure but below many OS placement decisions.

An OS can use topology information to:

- place pages near executing CPUs;
- bind threads and memory;
- migrate pages;
- balance bandwidth.

ChrisOS's current PMM does not implement a NUMA allocator in the reviewed files. It treats usable physical pages from the boot memory map as one allocation universe up to its configured physical limit.

## Firmware initialization boundary

On ordinary PC-class systems, the OS usually does not train DRAM from raw power-on electrical state. Firmware/platform initialization configures the memory controller and DRAM before normal bootloader/kernel execution.

The kernel then receives a physical memory map describing ranges it may use.

This distinction prevents a common conceptual error: a page allocator is not a DRAM training algorithm.

The current ChrisOS path reflects this abstraction boundary. <code>bootinfo.c</code> requests a Limine memory map and <code>pmm_init</code> marks usable/reserved page ranges. The PMM does not issue ACTIVATE/PRECHARGE/REFRESH commands.

## ChrisOS boot memory view

<code>bootinfo_memmap_count</code> and <code>bootinfo_memmap_entry</code> expose the bootloader-provided map.

<code>pmm_init</code> starts with pages marked unavailable, then:

1. iterates usable memory-map ranges;
2. marks page-aligned usable frames free;
3. reserves low physical memory;
4. reserves memory-map categories that must not be allocated;
5. establishes allocator accounting and cursor state;
6. reserves a DMA32 pool.

This logic operates on 4 KiB page frames. It does not know which DRAM row contains a frame.

The distinction is intentional: OS allocation policy and memory-controller scheduling solve different problems.

## ChrisVM guest RAM today

At revision <code>e05a17fd76333114a3fb5c2452f38ca747d4ac56</code>:

- <code>CHRIS_RAM_DEFAULT</code> is 16 MiB;
- configuration stores <code>ram_size</code>;
- machine creation rejects RAM below 2 MiB or sizes not aligned to 2 MiB;
- <code>chris_machine_create</code> allocates a zero-filled host buffer with <code>calloc</code>;
- <code>ChrisMachine</code> stores the pointer in <code>ram</code> and length in <code>ram_size</code>.

For in-range physical addresses, <code>chris_phys_read</code> and <code>chris_phys_write</code> use <code>memcpy</code> directly between guest RAM storage and caller buffers.

Out-of-range physical accesses may route to framebuffer or MMIO handling.

Therefore current ChrisVM RAM is a functional physical-address byte store, not a DRAM timing simulator.

## Consequences of the current ChrisVM abstraction

Current guest RAM has no modeled:

- channel selection;
- rank;
- bank/bank group;
- row/column;
- row-buffer state;
- ACT/PRE/READ/WRITE commands;
- refresh;
- controller queue;
- scheduling policy;
- bus turnaround;
- ECC;
- NUMA distance;
- variable latency;
- bandwidth saturation.

A byte access and a megabyte copy consume host execution time, but that host time is not defined as guest DRAM timing.

The <code>deterministic</code> configuration field does not turn host <code>memcpy</code> timing into a deterministic guest memory model.

## Functional correctness versus timing correctness

For current ChrisVM goals, contiguous host storage has advantages:

- simple physical-address semantics;
- deterministic contents;
- fast unit tests;
- straightforward snapshots/debugging;
- no accidental dependence on a speculative timing model.

A future timing model should therefore be optional and layered under a stable functional memory interface rather than replacing simple RAM storage.

Functional backend:

    physical request -> immediate byte-store operation

Timing backend:

    physical request
        -> decode address topology
        -> enqueue controller request
        -> schedule legal commands
        -> advance simulated cycles
        -> complete byte-store operation

Both can use the same backing byte array for actual data.

## Proposed memory-controller model for ChrisVM

A first educational timing model can use explicit topology:

    channels = C
    ranks_per_channel = R
    banks_per_rank = B
    rows_per_bank = N
    row_bytes = S

Controller state:

    Channel {
        read_queue
        write_queue
        bus_direction
        available_cycle
        Rank ranks[]
    }

    Bank {
        open_row
        next_activate_cycle
        next_precharge_cycle
        next_read_cycle
        next_write_cycle
    }

The backing data remains <code>m->ram</code>. The model determines *when* a request completes, not where data is stored in the host process.

## Address decoder

A deterministic configurable decoder can map line address to topology.

For example:

    line = physical_address / cache_line_size
    channel = line % C
    line /= C
    bank = line % B
    line /= B
    column_line = line % lines_per_row
    row = line / lines_per_row

This is intentionally simple and should be labeled as a simulator mapping.

A more advanced mode can XOR selected bits to study bank distribution.

The decoder should be a pure function so tests can verify exact mappings.

## Command legality

Each bank/rank/channel maintains the earliest cycle at which commands are legal.

For an ACTIVATE at cycle t:

    legal if t >= bank.next_activate_cycle
             and rank/channel activate-window constraints permit it

After issuing ACTIVATE, update:

    bank.open_row = requested_row
    bank.next_read_cycle = t + tRCD
    bank.next_write_cycle = t + tRCD
    bank.next_precharge_cycle = max(previous, t + tRAS)

After PRECHARGE:

    bank.open_row = NONE
    bank.next_activate_cycle = t + tRP

After READ/WRITE, additional same-bank, cross-bank, turnaround and bus constraints are updated according to the selected simplified timing model.

This event/state-machine approach is preferable to assigning a single latency constant.

## Request lifecycle

A timing request can move through states:

    NEW
      -> QUEUED
      -> WAITING_FOR_PRECHARGE
      -> WAITING_FOR_ACTIVATE
      -> READY_FOR_COLUMN
      -> DATA_TRANSFER
      -> COMPLETE

A row hit can skip precharge/activate phases.

A row conflict traverses all relevant phases.

Keeping state explicit makes traces and correctness assertions possible.

## Scheduling policy

A first controller can support selectable policies:

### FIFO

Oldest request first when legal.

Benefits:
- simple;
- predictable;
- strong fairness.

Limitations:
- poor row locality.

### FR-FCFS

Prefer ready row hits, then oldest request.

Benefits:
- demonstrates row-buffer optimization.

Limitations:
- can starve conflicting requests.

### Age-capped FR-FCFS

Prefer row hits unless a request age exceeds a threshold.

This provides a useful fairness experiment without implementing a research-grade scheduler.

## Read/write drain mode

Controller state can expose:

    mode = READS | WRITES

Transition to write-drain when:

    write_queue >= high_watermark
    OR no reads are pending

Transition back when:

    write_queue <= low_watermark
    AND reads exist

This makes bus-turnaround behavior observable.

Queue thresholds should be configuration, not hidden constants.

## Refresh model

A simplified rank refresh model can maintain:

    next_refresh_due
    refresh_busy_until

When refresh is due, the scheduler must reserve the affected resources and delay regular commands.

The model should document whether it implements:

- all-bank refresh;
- per-bank refresh;
- postponement;
- temperature effects.

If only all-bank periodic blocking is implemented, it should say so explicitly.

## Timing units

A simulator must choose one time base:

- memory clock cycles;
- controller cycles;
- picoseconds/nanoseconds;
- global ChrisCPU cycles.

Using global simulated CPU cycles is simple but couples memory timing to CPU frequency.

Using absolute picoseconds is more composable:

    event_time_ps

CPU and DRAM components can then convert their frequency-domain events to a common timeline.

For an initial ChrisCPU teaching model, a single abstract cycle can still be valid if all parameters are defined in that same unit and no claim of physical calibration is made.

## Queueing and backpressure interface

A nonblocking memory API might expose:

    request_id = mem_submit(address, size, type, callback/tag)

    mem_tick(now)

    mem_poll(request_id, &result)

A full queue returns a retry/backpressure result rather than silently accepting unlimited requests.

This allows future cache/CPU timing models to stall or continue other work while memory is pending.

The current synchronous <code>chris_phys_read/write</code> can remain as the functional API.

## Data integrity and transaction boundaries

Timing should not change the data semantics.

For a read:
- bytes are copied into the result when the request reaches completion under the model.

For a write:
- data can be buffered at submission but should become backing-store-visible at the model's defined commit point.

The simulator should define behavior for overlapping writes and reads. Program/coherence ordering belongs to upstream layers; the controller cannot arbitrarily violate transaction order constraints handed to it.

## MMIO is not DRAM

The current <code>chris_phys_read/write</code> checks guest RAM first, then framebuffer/MMIO paths.

A future DRAM timing layer must preserve this distinction:

- RAM addresses -> memory-controller model;
- framebuffer/device regions -> device/MMIO model.

Sending MMIO through a DRAM row scheduler would be architecturally wrong.

The physical-address map therefore needs a region classifier before DRAM topology decoding.

## DMA interaction

DMA-capable devices access physical memory without executing CPU load/store instructions.

A timing-aware controller should accept requesters other than CPU cache misses:

    requester = CPU0 | CPU1 | DEVICE_X | ...

This enables experiments with:

- bandwidth competition;
- fairness;
- DMA bursts;
- memory-controller saturation.

Current ChrisOS already has DMA-related page constraints such as a DMA32 pool in the PMM. That allocation constraint is separate from DRAM scheduling.

## Page allocation and DRAM locality

The PMM chooses physical page frames. If the OS knows address-to-channel/bank mapping, allocation policy can influence memory parallelism.

Possible research policies include:

- channel-aware page coloring;
- bank-aware allocation;
- NUMA-local placement;
- bandwidth partitioning.

Current ChrisOS PMM does not use DRAM topology metadata in the reviewed source. Any such policy belongs to future work and would require a reliable topology source.

## Security considerations

DRAM organization can create observable timing differences through row hits/conflicts and shared controller queues. Physical row adjacency also matters to disturbance phenomena such as Rowhammer.

A functional byte-array model intentionally does not reproduce these effects.

If ChrisVM later models row timing or disturbance, security documentation should distinguish:

- timing observation;
- row-conflict channels;
- refresh effects;
- fault injection/disturbance;
- ECC mitigation.

A partial timing model should not be presented as a faithful Rowhammer simulator without electrical/device-level validation.

## Determinism

For reproducible documentation and testing, a controller model should define:

- topology;
- address mapping;
- all timing parameters;
- queue capacities;
- scheduling policy;
- initial open-row state;
- refresh phase;
- arbitration tie-breaking.

Tie-breaking should use stable age/request IDs instead of host thread scheduling.

Then identical request streams produce identical traces.

## Trace format

Useful trace events:

    cycle 1200 SUBMIT R id=41 pa=0x12345000 ch=0 rank=0 bank=3 row=291
    cycle 1201 PRE bank=3
    cycle 1215 ACT bank=3 row=291
    cycle 1229 READ id=41 col=64
    cycle 1243 COMPLETE id=41

This lets readers inspect why latency occurred.

A trace should separate physical-address decoding from command scheduling so mapping bugs can be diagnosed independently.

## Validation: address decoder

Property tests should verify:

- decoded values remain within configured ranges;
- addresses in one cache line map consistently;
- advancing by configured row size changes column/row as intended;
- channel/bank interleaving matches the declared formula;
- mapping is deterministic.

Round-trip encode/decode can be implemented for simple linear mappings.

## Validation: timing constraints

For every command trace, assert:

- ACT does not violate next-activate constraints;
- READ/WRITE does not occur before activation delay;
- PRECHARGE does not violate active/write-recovery timing;
- refresh exclusion is respected;
- bus direction changes obey configured delay.

Rather than only checking final request latency, validate the command sequence itself.

## Validation: row cases

Directed tests:

### Row hit

Two reads to same bank and row.

Expected:
- first request opens row;
- second uses existing row;
- no PRE/ACT required for second request under open-page policy.

### Row conflict

Second request targets same bank, different row.

Expected:
- close/precharge;
- activate new row;
- column access only after timing permits.

### Bank parallelism

Requests to different banks.

Expected:
- overlap allowed subject to shared channel/rank constraints.

### Queue saturation

Submit more requests than capacity.

Expected:
- explicit backpressure;
- no dropped request.

### Refresh collision

Request arrives during required refresh.

Expected:
- completion delayed according to declared refresh model.

## Validation: functional equivalence

Timing mode must produce the same final memory bytes as functional mode for the same architecturally legal transaction sequence.

A differential harness can:

1. initialize identical backing memory;
2. apply requests immediately in functional reference according to commit order;
3. submit equivalent timed requests;
4. run until all complete;
5. compare memory and read results.

Timing can differ; data semantics cannot.

## Performance metrics

Useful counters:

- total read/write requests;
- bytes transferred;
- row hits;
- row misses/closed-row accesses;
- row conflicts;
- average/max queue depth;
- average read latency;
- average write latency;
- channel utilization;
- bank utilization;
- read/write turnaround cycles;
- refresh-blocked cycles;
- scheduler fairness/oldest-request age;
- backpressure events.

Row-buffer hit rate:

    row_hit_rate = row_hits / column_requests

Average queueing delay:

    avg_queue_delay = sum(issue_time - arrival_time) / requests

These describe the configured model, not a physical DIMM unless calibrated.

## Model calibration boundary

A simulator can operate at several fidelity levels:

1. **functional RAM** — current ChrisVM byte store;
2. **fixed-latency memory** — simple timing abstraction;
3. **bank/row timing model** — explicit queues and row state;
4. **DDR-generation command model** — standard-specific command constraints;
5. **PHY/electrical model** — signaling, training, analog effects.

ChrisVM currently operates at level 1.

A proposed controller should state its level explicitly. A bank/row model should not claim PHY fidelity.

## Current limitations

The reviewed ChrisOS/ChrisVM source does not implement:

- DRAM training;
- channel/rank/bank topology discovery in the kernel PMM;
- DRAM command scheduling;
- timing constraints;
- row-buffer policy;
- refresh timing;
- ECC modeling;
- NUMA page allocation;
- memory-controller contention;
- guest DRAM latency.

These are theory/future-model concepts in this chapter.

## Roadmap boundary

A disciplined evolution path is:

1. keep current functional RAM as the default reference;
2. add a generic asynchronous memory-request interface;
3. add fixed deterministic latency;
4. add topology/address decoding;
5. add bank open-row state;
6. add ACT/PRE/READ/WRITE timing constraints;
7. add finite queues and FIFO scheduling;
8. add FR-FCFS and fairness;
9. add read/write turnaround and drain modes;
10. add refresh;
11. connect a future cache/timing CPU backend;
12. add DMA requesters;
13. only then consider ECC, NUMA experiments or standard-specific calibration.

Each step should remain differential-testable against functional memory semantics.

## Revision record

This chapter was reconciled against ChrisOS <code>main</code> revision <code>e05a17fd76333114a3fb5c2452f38ca747d4ac56</code>. Current implementation claims are restricted to the declared source files. DRAM topology, controller scheduling and timing mechanisms are architecture theory and proposed future ChrisVM modeling, not features of the present guest RAM implementation.
