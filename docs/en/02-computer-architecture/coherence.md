---
id: coherence
lang: en
type: technical-chapter
volume: 02-computer-architecture
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/spin.h
  - kernel/metal/spin.c
  - kernel/metal/smp.h
  - kernel/metal/smp.c
  - kernel/metal/mm.h
  - kernel/metal/mm.c
  - compiler/kcc/kcc.c
  - chrisvm/machine/machine.c
  - chrisvm/machine/machine.h
  - chrisvm/chris_arch.h
  - chrisvm/cpu/emulator/chriscpu.c
symbols:
  - spin_lock
  - spin_unlock
  - cas_u32
  - atomic_add_u32
  - smp_init
  - smp_current_cpu
  - mm_tlb_shootdown_range
  - mm_tlb_poll
  - ChrisMachine
  - ChrisCpuBackend
depends_on:
  - cache-hierarchy
  - x86-64-memory-privilege
related:
  - atomics-memory-model
  - interrupts-smp
  - tlb-shootdown
---

# Cache coherence and multiprocessor memory

## The correctness problem created by private copies

A uniprocessor cache can be treated as a private performance structure between one execution engine and lower memory. A multiprocessor changes the problem. If two processors can cache the same physical memory block, each processor can hold a private copy while software expects one shared memory location.

Assume physical address X initially contains 0. CPU 0 reads X and obtains a cached copy. CPU 1 also reads X. CPU 0 then stores 1. If CPU 1 is allowed to continue reading its old private copy indefinitely, the machine has stopped behaving like the shared-memory system expected by normal SMP software. Cache coherence constrains these copies so that ownership and visibility transitions remain consistent.

Coherence is therefore not merely a cache-hit optimization. It is a correctness mechanism over copies of the same coherent block. A coherent implementation must communicate when write ownership changes, when another participant requests the line, when a modified line is evicted, or when a requester needs bytes newer than DRAM.

![Conceptual coherent multiprocessor and MESI state machine](../../assets/diagrams/coherence-en.svg)

The diagram is conceptual. Real processors may use snooping, distributed directories, probe filters, hierarchical fabrics, noninclusive caches, victim structures and implementation-specific transient states. Software must rely on the documented architectural memory model rather than an assumed internal topology.

## Coherence, memory ordering and synchronization are different layers

These mechanisms solve different problems.

| Layer | Question | Typical mechanisms |
|---|---|---|
| Cache coherence | What happens when several coherent agents hold copies of one line? | probes, invalidation, ownership transfer, directory state |
| Memory consistency / ordering | In what orders may loads and stores become observable? | architectural ordering rules, fences, locked instructions |
| Software synchronization | Which execution may enter a critical section or publish data? | spinlocks, mutexes, atomics, condition protocols |
| Translation coherence | How are stale address translations removed? | TLB invalidation and shootdown |

A coherent machine can still allow memory operations to become observable in an order different from source order. A fence constrains ordering, but does not replace the line-ownership machinery of coherence. A lock is a software protocol built on atomicity and ordering. A TLB shootdown solves a different cache problem entirely: stale address translation.

This distinction is essential in ChrisOS because its native SMP kernel uses coherent ordinary memory for locks while also implementing explicit TLB shootdown for page-table changes.

## The single-writer, multiple-reader invariant

A useful safety rule for invalidation-based coherence is:

> At most one coherent participant may possess write permission for a cache line at one time.

Multiple processors may hold readable copies. Before one processor modifies the line, it must reach a state in which competing copies no longer have conflicting rights.

The coherence unit is usually a cache line, not a C field. If two unrelated variables share one line, writes to either variable can move ownership of the whole line. This is the basis of false sharing.

The rule can be expressed as permissions:

| Permission | Number of holders | May read? | May write without another coherence transaction? |
|---|---:|---:|---:|
| Invalid | 0 useful copies | no | no |
| Shared read | one or more | yes | no |
| Exclusive clean | one | yes | yes, after local state promotion |
| Exclusive modified | one | yes | yes |

The names vary across protocols, but the exclusivity invariant is more important than the labels.

## MESI as a teaching protocol

MESI provides four useful stable states.

| State | Meaning in the teaching model | Local read | Local write |
|---|---|---|---|
| Modified (M) | only valid copy; differs from lower memory | hit | hit |
| Exclusive (E) | only valid copy; clean | hit | local transition to M |
| Shared (S) | clean copy; peers may also have copies | hit | ownership transaction required |
| Invalid (I) | no usable copy | acquisition required | ownership acquisition required |

MESI is not a universal description of every x86 implementation. AMD documents MOESI, adding an Owned state. Commercial processors also use transient and internal states that are not architectural software interfaces. MESI here is an auditable model for explaining stable-state invariants.

### Read miss

With both processors Invalid:

~~~text
CPU0 read X
    issue a shared/read request
    if no other coherent copy exists:
        CPU0 -> Exclusive
    otherwise:
        participating copies -> Shared
~~~

If another cache owns a Modified copy, the requester must receive the newest bytes. Returning stale DRAM while a newer modified copy exists would break coherence.

### Write to Shared or Invalid

~~~text
CPU0 wants to write X
    request exclusive ownership
    invalidate competing coherent copies
    obtain required acknowledgements
    ensure the current data is present
    CPU0 -> Modified
    perform the store
~~~

The request may be broadcast or directory-targeted. The stable-state rule does not require a particular interconnect.

### Read of a line modified elsewhere

~~~text
CPU1 read X
CPU0 owns X in Modified
    locate the current owner
    transfer or write back the newest bytes
    downgrade CPU0 as required
    install a readable copy for CPU1
~~~

In simple MESI both may become Shared. In MOESI, the former owner may become Owned and remain responsible for supplying the dirty value.

## Transient states are required by real implementations

Stable states hide latency. Ownership transfer takes time. A controller can be waiting for data, waiting for invalidation acknowledgements, writing back a victim, responding to a probe, or retrying after resource pressure.

A detailed simulator may need transient states conceptually like:

~~~text
I -> IS    read request issued, data pending
S -> SM    ownership requested, invalidation acks pending
M -> MI    writeback / eviction pending
~~~

A controller must not expose a line as writable before the protocol has established exclusive ownership. Many difficult coherence bugs occur only in races between transient actions, such as simultaneous misses, probe-versus-eviction, queue exhaustion, or competing requests for ownership.

A functional emulator can avoid this entire state space by not modeling caches. A timing/coherence simulator cannot claim protocol fidelity while omitting it.

## Snooping and directory organizations

Snooping and directories answer how participants discover coherence actions.

### Snooping

A small system can use a logically broadcast fabric.

1. A core issues a read or ownership request.
2. Peer caches observe the request.
3. Peers respond according to their state.
4. The requester completes after required responses arrive.

The conceptual model is simple, but broadcast traffic scales poorly. Real machines use filters, hierarchical fabrics and topology-aware optimizations.

### Directory coherence

A directory records which agents may hold a line and which agent owns write permission.

~~~text
directory entry
    tag
    coherence state
    optional owner
    sharer set
~~~

A full P-bit sharer vector costs O(P) bits per tracked line for P processors. Sparse encodings reduce common-case storage but require overflow handling. Directories reduce broadcast but add lookup, storage and message-routing complexity.

MESI/MOESI and snoop/directory are not competing names for the same thing. MESI/MOESI describes permissions and relationships. Snoop or directory mechanisms describe how the machine coordinates the transitions.

## Invalidation, update and traffic

Invalidation-oriented coherence makes competing copies unusable before a writer proceeds. Later readers reacquire the line. Update protocols instead distribute new data to peers that already have copies.

Updates can save a later read miss when many consumers immediately need every new value, but they can waste bandwidth when peers never read the updates. Coherence design is therefore a balance among latency, bandwidth, storage, topology and controller complexity.

## False sharing and line ping-pong

Consider a 64-byte line:

~~~text
offset 0: counter_a   written only by CPU0
offset 4: counter_b   written only by CPU1
~~~

There is no source-level conflict if the variables are independently owned. The coherence protocol, however, sees one line.

~~~text
CPU0 obtains line for write -> CPU1 copy invalidated
CPU1 obtains line for write -> CPU0 copy invalidated
CPU0 obtains line for write -> CPU1 copy invalidated
...
~~~

This ownership ping-pong can dominate performance even though neither processor reads the other's counter.

Mitigations follow ownership rather than folklore:

- separate heavily written per-CPU state onto different lines;
- batch or aggregate updates;
- partition mutable data by processor;
- reduce global hot counters;
- measure before introducing padding.

Padding everything can enlarge working sets, waste cache capacity and increase TLB pressure. It is not a universal optimization.

## Atomics require coherence but are not identical to coherence

An atomic read-modify-write must appear indivisible with respect to participating observers. On a coherent write-back machine, the implementation normally needs unique ownership of the relevant line while the operation commits.

The protocol provides a unique writable copy. The instruction defines the atomic transformation. The memory model defines ordering around it.

ChrisOS currently wraps compiler synchronization builtins in kernel/metal/spin.c.

~~~c
int cas_u32(volatile uint32_t *cell, uint32_t expected, uint32_t desired) {
    return __sync_bool_compare_and_swap(cell, expected, desired);
}
~~~

spin_lock repeatedly performs CAS from 0 to 1 and executes pause after a failed attempt. spin_unlock uses __sync_lock_release. atomic_add_u32 uses __sync_fetch_and_add.

For the self-hosted KCC path, the inspected compiler emits lock cmpxchg for supported compare-and-swap operations and lock xadd for supported fetch-and-add operations. These are architectural x86 synchronization primitives. Their atomicity and ordering contract belongs to the next chapter; coherence is the lower-level mechanism that makes a shared line a meaningful ownership domain.

## What native ChrisOS SMP currently does

The kernel is already written for more than one physical or virtual x86 processor.

smp_init reads the bootloader multiprocessor response, allocates stacks for application processors, publishes AP entry points and waits for cpu_online_count to reach the expected value. AP startup increments that count with __sync_fetch_and_add.

The AP stack range also identifies the executing CPU. smp_current_cpu derives the AP index from the current stack instead of trusting a shared LAPIC mapping. Per-CPU ownership requires correct participant identity; confusing CPUs can corrupt acknowledgement protocols.

Kernel locks protect mutable shared structures. The current locking documentation defines an ordering among JIT, memory-management, heap, physical-memory and selected subsystem locks. Coherence makes lock words and protected bytes visible across CPUs, but it does not prevent deadlock. Lock ordering is software policy.

## TLB shootdown demonstrates a separate coherence domain

Page-table modification shows why data-cache coherence is not enough.

A processor may coherently observe the newest page-table bytes in ordinary memory and still use a stale translation already cached in its TLB. ChrisOS therefore uses explicit translation invalidation.

The current shootdown path conceptually performs:

1. publish the virtual range requiring invalidation;
2. identify online target CPUs;
3. send LAPIC IPI vector 0xF0 where possible;
4. each target executes mm_tlb_poll, performs invlpg over the range and acknowledges the generation;
5. the initiating CPU waits before allowing affected physical frames to be safely reused.

A stalled participant can prevent safe reuse. The current code includes fencing and quarantine behavior rather than assuming every acknowledgement arrives.

This is software-managed translation coherence. It must not be described as a data-cache coherence protocol.

## DMA and coherent I/O

A DMA-capable device can be another participant in the memory system. Whether CPU cache maintenance is required around DMA depends on the platform.

On a coherent I/O platform, the interconnect participates in a protocol that preserves required visibility. On a noncoherent platform, software may need explicit clean/invalidate operations or mappings with special cache attributes.

Therefore:

- volatile does not create DMA coherence;
- a memory barrier does not automatically write back arbitrary dirty lines for a noncoherent device;
- coherent CPU caches do not prove that a given device path is coherent.

Driver documentation must state the platform contract before relying on coherence.

## Self-modifying code and instruction visibility

Instruction fetch is another distinct problem. A core can write bytes that later become instructions. Architectures specify procedures for making those modifications visible to instruction fetch and for ordering the transition between writing and execution.

Data-cache coherence alone must not be used as a complete proof of instruction-fetch synchronization. JIT code requires reasoning about:

1. data ownership while generated bytes are written;
2. mapping permissions and TLB correctness;
3. architecture-defined instruction-fetch synchronization before execution.

ChrisOS already has explicit TLB work in the JIT lifecycle. That does not by itself prove a complete instruction-cache publication sequence for every architecture.

## Current ChrisCPU: one vCPU and no guest coherence model

The present ChrisVM machine model contains one CPU pointer. machine.c calls backend->create_cpu(m, 0), and the CPU-backend documentation defines create_cpu as allocating vCPU 0.

The interpreter does not currently model:

- private guest L1/L2 cache lines;
- MESI/MOESI states;
- cache-to-cache transfer;
- snoop or probe queues;
- a coherence directory;
- coherence latency;
- simultaneous execution of multiple guest vCPUs.

Guest memory operations eventually reach shared host backing memory through the functional physical-memory path described in the cache-hierarchy chapter.

The consequence is precise: the native ChrisOS kernel has real SMP synchronization requirements, but the current ChrisCPU direct guest path cannot yet reproduce races requiring two guest processors.

The host CPU's real caches still make the ChrisVM process execute correctly and affect wall-clock performance. They are host microarchitecture, not simulated guest caches.

## Requirements for multiprocessor ChrisCPU

Allocating more ChrisCpu structures is insufficient. A credible SMP design needs explicit contracts.

### Shared machine and vCPU topology

~~~text
ChrisMachine
    shared guest physical memory
    device and interrupt routing
    vCPU[0..N-1]
    guest memory-order semantics
    optional guest cache/coherence model
    deterministic scheduler or parallel executor
~~~

A deterministic interleaver improves reproducibility. Parallel host threads may improve throughput but introduce host races that must be synchronized independently of the guest semantics.

### Atomic guest memory transactions

A locked guest instruction cannot be implemented as:

~~~text
read
compute
write
~~~

if another vCPU can interleave between those stages. The emulator needs an indivisible guest transaction or an equivalent line/global synchronization mechanism.

### Explicit memory model

Even without simulated caches, several vCPUs require defined guest ordering. The emulator must not accidentally inherit unspecified behavior from the host compiler or host ISA. Guest loads, stores, locked operations and fences need deliberate semantics.

### AP startup and interrupts

The virtual platform must eventually provide AP discovery, LAPIC state, interprocessor interrupts and per-vCPU interrupt delivery. If every direct guest boot remains on vCPU 0, ChrisOS SMP cannot be validated there.

### Optional cache fidelity

A functional SMP emulator may deliberately expose coherent shared memory without cache timing. That is a valid architectural model if documented. A simulator that claims MESI behavior or cache timing must additionally model per-line state, transitions, outstanding messages and timing/resource limits.

## Testable protocol invariants

For one line across all modeled caches, a MESI-like stable-state checker can enforce:

~~~text
number of M copies <= 1
number of E copies <= 1
if one M exists, every other copy is I
if one E exists, every other copy is I
an M copy contains the authoritative newest value
all S copies contain the same coherent value
~~~

The checker included with this chapter exercises:

- first read producing Exclusive;
- a second reader producing Shared copies;
- a write upgrade invalidating peers;
- a read intervention from Modified;
- competing writes;
- line-granularity false-sharing ping-pong.

It is deliberately small enough to audit. It is not a model of a specific Intel or AMD microarchitecture.

## Coherence performance costs

Coherence creates traffic beyond ordinary capacity misses. A store may require:

- ownership request latency;
- invalidation messages;
- acknowledgement latency;
- data transfer from a peer cache;
- dirty victim writeback;
- interconnect or directory queueing.

A line present locally in Shared state can therefore require a coherence upgrade before a store. A read miss can receive data from another cache without DRAM being the critical source.

Meaningful performance work should distinguish local cache misses, ownership upgrades, invalidations, remote-cache transfers, false sharing, interconnect saturation and NUMA effects where relevant. Wall-clock time alone does not identify the cause.

## Correctness boundaries for ChrisOS

The inspected native kernel assumes coherent x86 shared memory for ordinary cacheable RAM, which is appropriate for the current x86 SMP target.

That does not prove:

- every DMA path is coherent;
- volatile is synchronization;
- all widths and alignments are atomic;
- TLB entries are automatically coherent;
- current ChrisCPU models multiprocessor caches;
- the compiler may freely reorder accesses around synchronization;
- padding always improves performance.

Each item requires its own architectural rule, software protocol or measurement.

## Validation and revision limits

This chapter is reconciled against ChrisOS revision da3df29cb397932c43d32373871fb9380e688ade.

Run:

~~~text
python scripts/check_coherence_examples.py
~~~

The checker reproduces the teaching MESI transitions and false-sharing trace. It does not execute ChrisOS, benchmark hardware, validate Intel or AMD implementation details, or prove the kernel free of races.

Changes to spin.c, smp.c, the TLB protocol, ChrisCpuBackend, guest-memory execution, AP startup or the locking model should trigger review.

The next chapter treats atomicity and the x86 memory-order contract separately. Coherence constrains copies of a location; the memory model constrains observable ordering among operations.

## Primary references

- Intel, Intel 64 and IA-32 Architectures Software Developer's Manual, System Programming Guide: multiprocessor management, memory ordering and locked operations.
- AMD, AMD64 Architecture Programmer's Manual, Volume 2: System Programming, Memory System chapter.
- AMD, AMD64 Architecture Programmer's Manual, Volume 1: Application Programming, cache-coherency and MOESI overview.
