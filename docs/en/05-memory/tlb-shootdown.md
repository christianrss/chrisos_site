---
id: tlb-shootdown
lang: en
type: technical-chapter
volume: 05-memory
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/mm.c
  - kernel/metal/tlb_proto.c
  - kernel/metal/tlb_proto.h
  - kernel/metal/smp.c
symbols: []
depends_on:
  - virtual-memory
  - interrupts-smp
related:
  - heap-ownership
---

# TLB coherence and shootdown

## Why page-table memory is not enough

Processors cache recent virtual-to-physical translations in a Translation Lookaside Buffer (TLB). Updating a PTE in RAM does not guarantee another CPU immediately stops using a cached old translation.

This creates a dangerous teardown sequence:

```text
CPU 0                     CPU 1
-----                     -----
remove PTE
free physical frame       still has old TLB entry
reuse frame               access old virtual address
                           writes into reused frame
```

The page table in memory is correct, yet the system is corrupted.

## Local invalidation

A CPU can invalidate translations through architecture-defined operations or by switching relevant address-space state. That handles the local cache.

In SMP, every CPU that may have cached the mapping must participate before the physical frame is considered safe to reuse.

## Shootdown protocol

A TLB shootdown publishes an invalidation generation/range and causes participating CPUs to flush or acknowledge.

ChrisOS has a dedicated protocol model in `tlb_proto.c`. It tracks CPU states, observed generation, heartbeat/progress and whether reuse is safe.

The memory-management layer can send an IPI vector to online CPUs; the remote handler acknowledges after performing the required invalidation path.

## Generation model

A generation counter gives each published invalidation a monotonic identity. A CPU is current when its `seen` generation matches the published generation.

```text
publish generation N
       │
       ├── CPU0 seen=N
       ├── CPU1 seen=N
       └── CPU2 seen=N
              │
              ▼
          reuse allowed
```

If one online CPU remains behind, reusing the old frame is unsafe.

## Fencing a nonresponsive CPU

A difficult systems question appears when one CPU stops acknowledging. Waiting forever can deadlock the kernel. Reusing memory without acknowledgement can corrupt it.

The ChrisOS protocol models a fenced CPU state and requires additional evidence that the CPU has halted/flushed before considering reuse safe.

This is a stronger design than merely timing out and continuing.

## Polling and IPI paths

Early boot may not yet have a fully operational interrupt path on every AP. ChrisOS therefore retains a polling acknowledgement mechanism in addition to runtime IPI delivery.

This shows why initialization state matters to synchronization protocols: a mechanism valid after `sti` and APIC setup may not be available while those facilities are still being constructed.

## Lock interaction

The MM lock protects page-table mutations. However a remote TLB handler must not try to acquire the same MM lock while the initiating CPU waits under that lock, or the shootdown would deadlock.

The documented handler acknowledges without taking MM lock.

## Quarantine

If a translation cannot yet be proven gone, the corresponding physical memory should not immediately return to the general allocator. Quarantine delays reuse until the protocol establishes safety.

This converts an uncertain synchronization state into delayed reclamation rather than silent corruption.

## General lesson

Concurrent memory reclamation requires proving not just that an object is unreachable in the central data structure, but that no execution context retains a usable stale reference.

The TLB is a hardware example of the same broad lifetime problem encountered in lock-free data structures, DMA and asynchronous I/O.
