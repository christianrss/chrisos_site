---
id: hhdm
lang: en
type: technical-chapter
volume: 05-memory
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/bootinfo.c
  - kernel/metal/bootinfo.h
  - kernel/metal/pmm.c
  - kernel/metal/pmm.h
  - kernel/metal/mm.c
  - kernel/metal/mm.h
symbols:
  - bootinfo_init
  - bootinfo_get
  - bootinfo_phys_to_virt
  - pmm_selftest
  - mm_selftest
  - map_mmio_page
  - mm_virt_to_phys
depends_on:
  - boot-information
  - x86-64-memory-privilege
  - physical-memory
related:
  - pmm-algorithms
  - virtual-memory
  - page-table-layout
  - buses-mmio-dma
---

# Higher-half direct map

## Scope

A kernel often needs to dereference physical RAM that was allocated by the PMM, contains a page table, stores a DMA structure or belongs to another low-level subsystem. x86-64 code cannot load from a physical address directly: ordinary instructions use virtual addresses that are translated by the current page tables.

ChrisOS relies on the **higher-half direct map (HHDM)** supplied by Limine. The bootloader creates a virtual region in which normal physical memory is reachable at a fixed virtual offset. ChrisOS receives that offset during boot and uses it to convert a physical RAM address into a kernel virtual alias.

The conceptual relation is:

```text
hhdm_virtual = physical + hhdm_offset
```

This arithmetic is simple. Its validity is not. The resulting address is safe to dereference only when the bootloader actually mapped the physical range with suitable semantics. In particular, an MMIO device address is not transformed into a correct device mapping merely by adding the HHDM offset.

![Physical RAM, the HHDM offset and the separate MMIO path](../../assets/diagrams/hhdm-address-translation-en.svg)

This chapter separates three different ideas that are frequently conflated:

- physical-address ownership;
- virtual-address translation through HHDM;
- device/MMIO mappings with special page attributes.

## Why a direct map exists

Without a direct map, every time the kernel received a physical frame it would need to reserve a temporary virtual address, install a PTE, access the frame and later tear the mapping down.

A direct map instead keeps a stable kernel alias for a broad physical RAM range:

```text
physical frame P
       |
       | + HHDM offset
       v
kernel virtual address V
       |
       | page tables prepared by bootloader
       v
same physical frame P
```

This is particularly useful during early boot because:

- the PMM can return physical frames before higher-level allocators exist;
- page-table code can dereference page-table frames;
- self-tests can write directly to newly allocated RAM;
- the heap can turn claimed physical arenas into kernel pointers;
- low-level code avoids maintaining a temporary-mapping subsystem just to inspect RAM.

The direct map is therefore an addressability mechanism, not an ownership allocator.

## Limine request and boot contract

`bootinfo.c` declares a Limine HHDM request in the `.limine_requests` section. During `bootinfo_init`, ChrisOS requires a non-null HHDM response:

```text
if hhdm_request.response == 0:
    panic("HHDM Limine ausente")
```

The returned offset is stored in:

```text
info.hhdm_offset = hhdm->offset
```

Boot information is then marked ready.

The kernel also requires framebuffer, memory-map and multiprocessor responses before the boot-information layer is considered valid. HHDM is therefore part of a larger boot contract rather than an optional optimization in the current startup path.

The chosen offset is supplied by the bootloader. ChrisOS does not hard-code one canonical HHDM base in the reviewed source.

## Conversion helper

The public conversion path is:

```c
uint64_t bootinfo_phys_to_virt(uint64_t phys) {
    if (!bootinfo_ready) {
        panic(...);
    }
    return phys + info.hhdm_offset;
}
```

The helper provides two properties:

1. callers do not duplicate knowledge of where the HHDM begins;
2. conversion before `bootinfo_init` is rejected by panic.

It does **not** validate that the physical address belongs to normal RAM, to a current PMM allocation or even to a memory-map entry. It performs arithmetic after checking only boot-info readiness.

Thus the API contract is better stated as:

> Convert a physical address to the virtual address where the Limine HHDM would represent it, assuming that physical range is valid for HHDM access.

It is not a general “make any physical address safe to dereference” function.

## HHDM versus identity mapping

A direct map does not imply that virtual address equals physical address.

An identity mapping would satisfy:

```text
virtual = physical
```

whereas the HHDM satisfies:

```text
virtual = physical + offset
```

The distinction matters in low-level code because the same numeric physical address can be valid hardware state while being an invalid kernel pointer. Early firmware environments sometimes use identity mappings, which can hide bugs: code that accidentally casts a physical address to a pointer may appear to work until the kernel runs only in the higher half.

ChrisOS should therefore preserve the type distinction conceptually even though both values are represented as `uint64_t`. A physical frame returned by PMM must be converted or deliberately mapped before C dereference.

## Boot-order dependency

The usable order is:

```text
Limine establishes page tables and HHDM
    -> kernel enters
    -> bootinfo_init validates HHDM response
    -> bootinfo_ready = 1
    -> PMM initializes from memory map
    -> PMM/heap/MM code may use bootinfo_phys_to_virt
```

Calling the helper earlier is treated as an invariant violation and panics.

This ordering also means the PMM does not bootstrap the HHDM. The HHDM exists before PMM initialization; PMM merely consumes it.

## HHDM and the PMM

The PMM deals in physical frames.

For example, `pmm_selftest` allocates frames and converts each returned address through `bootinfo_phys_to_virt`. It writes distinct signatures through those HHDM aliases and reads them back.

That test validates a useful cross-layer path:

```text
Limine USABLE memory
   -> PMM marks frame free
   -> pmm_alloc claims physical frame
   -> HHDM converts frame to kernel virtual address
   -> CPU load/store reaches the same RAM
```

A successful HHDM access does not by itself prove the PMM should own the frame. Both contracts need to hold: the physical frame must be valid RAM and its allocation state must permit the access.

## HHDM and page-table construction

Page-table pages are ordinary physical frames. Memory-management code needs to treat their contents as arrays of PTEs while still storing physical addresses inside paging structures.

A common pattern is:

```text
page-table entry stores physical address
kernel implementation needs pointer to table bytes
pointer = HHDM(physical address)
```

This is why a direct map is foundational for a simple early page-table implementation.

The virtual pointer and physical address represent different namespaces. Accidentally storing an HHDM virtual pointer in a PTE where hardware expects a physical frame address would corrupt translation.

Conversely, dereferencing a raw physical address as a C pointer would access whatever virtual address happens to have that number, not “physical memory.”

## HHDM is not MMIO mapping

The clearest boundary is the Local APIC.

ChrisOS explicitly logs:

```text
HHDM + 0xFEE00000 is not a valid MMIO mapping; do not dereference
```

The boot-info code also inspects the Limine memory map and panics if the LAPIC physical address appears as `LIMINE_MEMMAP_USABLE`.

Why is simple offset addition insufficient?

Device memory may require:

- dedicated virtual mapping;
- cache-disable or write-through attributes;
- page-table permissions distinct from ordinary RAM;
- architecture/platform-specific ordering rules;
- an address range not included in the HHDM at all.

ChrisOS maps device pages through `map_mmio_page`, which allocates virtual space in a dedicated MMIO window and installs flags including `MM_PWT`, `MM_PCD` and `MM_NX`.

Therefore:

```text
HHDM arithmetic != MMIO mapping policy
```

## Framebuffer nuance

The framebuffer is also not just “free RAM.”

Limine provides a framebuffer virtual address directly in its response, and the memory map classifies framebuffer physical storage separately from USABLE RAM.

The PMM keeps framebuffer pages unavailable for general allocation.

Code should use the framebuffer mapping supplied/validated for graphics rather than assume that a framebuffer address can be treated like a PMM frame.

This illustrates a broader rule: addressability and allocatability are independent.

## Physical-to-virtual arithmetic and overflow

The conversion is unsigned 64-bit addition:

```text
virt = phys + offset
```

The current helper does not perform an explicit overflow or canonical-address check.

In the expected Limine contract, the bootloader provides a valid HHDM offset and maps the supported physical range into canonical higher-half addresses.

ChrisOS therefore delegates that layout guarantee to the boot protocol.

A more defensive abstraction could validate:

- physical address under a supported ceiling;
- arithmetic overflow;
- canonical x86-64 virtual-address form;
- whether the physical range is one of the mapped RAM classes.

The current implementation remains intentionally smaller.

## Canonical x86-64 addresses

x86-64 does not use every possible 64-bit value as a virtual address. Depending on paging mode, only a subset of high bits participate in translation, and the remaining high bits must follow canonical sign-extension rules.

A bootloader-selected higher-half mapping must therefore lie in a canonical region.

The HHDM concept is not “set the top bit.” It is a page-table layout in which a chosen high virtual interval translates to corresponding physical RAM.

ChrisOS does not reconstruct that mapping from scratch during `bootinfo_init`; it consumes the environment Limine established before kernel entry.

## Relationship to current CR3

An HHDM address works only while the active address space includes compatible higher-half mappings.

ChrisOS preserves kernel-space mappings when cloning process address spaces: `mm_clone_kernel_space` copies the upper half of the kernel PML4 into the new PML4.

That design allows kernel code to continue using HHDM/kernel addresses while a process CR3 is active.

This is an important invariant for system calls, exceptions and memory-management routines: switching to a process must not make core kernel mappings disappear.

## HHDM lifetime

The current architecture treats the Limine-established higher-half kernel mapping as persistent kernel infrastructure.

There is no code in the reviewed boot path that destroys the HHDM and replaces every use with another direct-map base.

This matters for source contracts: functions such as `pmm_selftest`, heap arena construction and table access rely on the mapping remaining valid after early boot.

If a future paging redesign relocates or removes the HHDM, every physical-to-pointer conversion site becomes part of that migration.

## Reverse translation is a different operation

The HHDM helper only computes physical -> HHDM virtual.

The reverse problem, “which physical address backs this arbitrary virtual address?”, is not generally solved by subtracting the HHDM offset because the virtual address might belong to:

- kernel executable mappings;
- process mappings;
- framebuffer;
- MMIO window;
- another alias.

ChrisOS provides `mm_virt_to_phys`, which walks the active page tables and handles large-page leaves.

For a known HHDM address, subtraction can be mathematically meaningful under the direct-map contract, but the general virtual-to-physical API is a page-table translation problem.

## Aliasing

The same physical frame can be mapped at more than one virtual address.

For example:

```text
physical frame P
  -> HHDM alias
  -> process/user mapping
  -> test mapping in a kernel virtual slot
```

All aliases refer to the same bytes.

The MM self-test demonstrates this property by mapping a PMM frame at a test virtual address, writing through that alias and checking the value through the HHDM pointer.

Aliasing has consequences for:

- cache coherence;
- permissions;
- TLB invalidation;
- lifetime management.

Freeing physical ownership while any alias remains live is unsafe.

## Memory attributes and aliases

Two virtual mappings of the same physical memory should not casually use conflicting cache/memory types.

Ordinary RAM and device MMIO have different requirements. This is another reason the HHDM must not be used as a universal alias for hardware registers.

The current MMIO path explicitly uses cache-control flags when mapping devices.

The HHDM's attributes come from the bootloader's paging setup and are appropriate for the RAM/direct-map contract it establishes.

## Security boundary

The HHDM maps physical RAM into privileged kernel virtual space. User-mode pages must not gain access to the HHDM merely because process page tables share upper-half kernel mappings.

Page-table privilege bits keep those kernel mappings supervisor-only.

A bug that marks HHDM entries user-accessible would effectively expose arbitrary physical RAM to processes, bypassing process isolation.

Thus HHDM security depends not only on its address being “high,” but on page-table permission bits and privilege enforcement.

## Performance characteristics

Direct-map translation is computationally cheap at the source level: conversion is one integer addition.

The actual memory access still passes through ordinary CPU address translation and caches.

Benefits include:

- no temporary-map setup per frame;
- stable pointers for kernel RAM;
- fewer page-table edits during early memory management.

Costs include:

- consumption of a large virtual-address region;
- permanent kernel mappings that must remain consistent across address spaces;
- larger blast radius if a physical address is incorrectly trusted.

The HHDM does not remove TLBs or page-table walks; it removes software mapping churn.

## Validation in current source

Current evidence includes:

- boot failure if the Limine HHDM response is absent;
- logging of the chosen HHDM offset;
- `bootinfo_phys_to_virt` readiness check;
- PMM self-test signatures through HHDM aliases;
- MM self-test that compares a test virtual mapping with the HHDM alias of the same frame;
- explicit rejection of treating the LAPIC HHDM arithmetic result as valid MMIO.

These tests cover useful integration boundaries but do not exhaustively prove the bootloader mapped every physical byte below the PMM ceiling.

## Failure modes

Important failure classes include:

- missing HHDM response;
- using conversion before bootinfo initialization;
- adding the offset to an MMIO physical address and dereferencing it;
- confusing virtual and physical addresses in a page-table entry;
- switching to a CR3 that omitted required kernel higher-half mappings;
- freeing a PMM frame while an HHDM/user/kernel alias remains in use;
- using an HHDM alias after a future redesign removed that mapping.

Most of these failures are architectural contract violations rather than arithmetic mistakes.

## Current limitations

The current HHDM abstraction is deliberately minimal:

- one global bootloader-provided offset;
- no typed distinction between RAM physical addresses and MMIO addresses at the function signature;
- no explicit overflow/canonical-address validation in the helper;
- no per-range query proving an address is HHDM-backed before conversion;
- no dynamic remapping or teardown;
- no abstraction for multiple direct-map regions.

Its simplicity is appropriate for the current kernel, provided callers preserve the RAM-versus-device boundary.

## Source map

`kernel/metal/bootinfo.c` declares the Limine HHDM request, validates the response, stores the offset, logs it and implements `bootinfo_phys_to_virt`.

`kernel/metal/pmm.c` uses HHDM in its self-test for allocated physical RAM.

`kernel/metal/mm.c` provides dedicated MMIO mapping, virtual-to-physical walking and a self-test that verifies aliases of one PMM frame.

The implementation claims in this chapter were reconciled against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.
