---
id: virtual-memory
lang: en
type: technical-chapter
volume: 05-memory
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/mm.c
  - kernel/metal/mm.h
  - kernel/metal/pmm.c
  - kernel/metal/proc.c
symbols:
  - mm_init
  - mm_map_cr3
  - map_4k
  - mm_translate
  - mm_switch
depends_on:
  - physical-memory
  - x86-64-memory-privilege
related:
  - tlb-shootdown
  - processes-syscalls
---

# Virtual memory and x86-64 page tables

## Address translation

Virtual memory inserts a translation between addresses used by software and physical memory/device addresses.

A process instruction may load from virtual address `V`. The CPU consults translation structures selected by CR3 and either obtains physical address `P` with permissions or raises a fault.

<figure class="figure">
<img src="../../assets/diagrams/memory.svg" alt="Four-level page translation with TLB">
<figcaption>Translation first checks cached TLB state and otherwise performs a page-table walk.</figcaption>
</figure>

## Four-level paging

For conventional 4 KiB pages in the common four-level x86-64 scheme, the virtual address selects indices into:

```text
63                         48 47    39 38    30 29    21 20    12 11      0
+----------------------------+--------+--------+--------+--------+----------+
| canonical extension        | PML4   | PDPT   | PD     | PT     | offset   |
+----------------------------+--------+--------+--------+--------+----------+
```

Each table entry points to the next table and contains permission/status bits. The final PTE identifies a physical frame.

## CR3

CR3 selects the top-level page-table hierarchy for the current translation context. Switching CR3 is therefore a fundamental process-isolation operation.

ChrisOS `mm_switch` writes the chosen physical page-table root to CR3.

## Page-table entries

A page-table entry combines a page-aligned physical address with flags. Relevant concepts include:

- present/not present;
- writable/read-only;
- user/supervisor;
- executable permission through NX when enabled;
- architecture-defined accessed/dirty and caching behavior.

Software must mask address and flag portions correctly.

## Building tables

Mapping one 4 KiB page may require intermediate PML4/PDPT/PD/PT pages that do not yet exist. `mm_map_cr3` walks the hierarchy and allocates missing table pages from PMM.

This creates the dependency MM → PMM.

If allocation fails midway, the mapping function must report failure without leaving a structure whose ownership is ambiguous.

## Higher-half kernel sharing

A process address space can have a private user region while sharing kernel high-half mappings. This avoids rebuilding identical kernel mappings for every process and permits controlled entry into the kernel after a user transition.

Sharing also creates synchronization obligations: changing a shared kernel mapping can affect multiple CPUs/address spaces.

## Translation helpers

`mm_translate` allows kernel code to inspect whether a virtual address is mapped and recover physical address/flags without blindly touching it. User-copy logic uses this type of operation to validate pointers safely.

## Page faults

A page fault occurs when translation cannot satisfy the requested access: missing mapping, forbidden write, privilege violation or other paging rule.

CR2 records the faulting linear address. The exception frame supplies execution context. The kernel can then decide whether the event belongs to a user process and can be contained or represents a kernel failure.

## Mapping is not allocation

MM manages translations. PMM manages physical ownership.

```text
PMM: "this frame is allocated"
MM : "this virtual address refers to that frame with these permissions"
```

The distinction prevents double-free and permits aliases or shared mappings.

## Concurrency

Page tables are shared kernel structures and are protected by the MM lock. Unmapping introduces an additional problem: another CPU can retain a stale TLB translation even after the in-memory PTE has changed.

Therefore correctness of virtual-memory teardown is not complete until TLB coherence is addressed.
