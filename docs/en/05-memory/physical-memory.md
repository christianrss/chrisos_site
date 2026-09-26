---
id: physical-memory
lang: en
type: technical-chapter
volume: 05-memory
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/pmm.c
  - kernel/metal/pmm.h
  - kernel/metal/bootinfo.c
symbols:
  - pmm_init
  - pmm_alloc
  - pmm_alloc_contig
  - pmm_alloc_dma32
  - pmm_free
depends_on:
  - atom-semiconductor
  - x86-64-memory-privilege
related:
  - virtual-memory
  - heap-ownership
---

# Physical memory management

## From DRAM capacity to allocatable frames

Firmware and the bootloader report physical address ranges with different meanings: usable RAM, reserved firmware regions, ACPI data, framebuffer/device regions and other categories. A kernel cannot treat every numerical physical address as free DRAM.

The physical memory manager (PMM) converts the usable subset into allocation units.

ChrisOS uses 4 KiB pages as its fundamental PMM unit. This aligns naturally with the ordinary x86-64 page size used by the virtual-memory layer.

## Frame allocation

A physical page allocator answers a different question from `malloc`:

> Which physical frame number can safely be assigned to a subsystem?

Its result is a physical address, not necessarily a directly dereferenceable C pointer.

ChrisOS uses the higher-half direct-map conversion from boot information when kernel code needs a virtual address corresponding to physical RAM.

## Bitmap-style state

A common PMM representation stores one bit or small state per physical frame. Free/used scanning can then locate an available page.

The allocator must reserve:

- the kernel image itself;
- page-table structures;
- bootloader/firmware-protected ranges;
- device memory that is not ordinary RAM;
- any allocations already consumed during early initialization.

Double allocation is catastrophic because two independent owners can overwrite one another.

## Contiguous allocation

Some consumers need physically contiguous pages: DMA buffers, large arenas or device descriptor regions. `pmm_alloc_contig` searches for a run rather than one arbitrary frame.

Contiguous physical memory is harder to guarantee as the system becomes fragmented. A mature kernel may add more advanced allocators or IOMMU strategies, but the basic ownership constraint remains.

## DMA32

`pmm_alloc_dma32` exists for devices that cannot address arbitrary 64-bit physical locations. A buffer that is valid RAM for the CPU can still be unreachable to a 32-bit-limited DMA engine.

This illustrates a central distinction:

```text
CPU-addressable RAM ≠ device-addressable RAM in every configuration
```

## Locking

PMM state is shared across CPUs and is protected by a spinlock. The documented implementation allows same-CPU recursion for paths where enumeration callbacks re-enter PMM operations and saves interrupt state on the outer acquisition.

This is not incidental bookkeeping. If two CPUs observe the same frame as free before either records allocation, both can receive the same page. The result is cross-subsystem corruption.

## PMM and heap

The heap obtains physical backing from the PMM. The reverse dependency is intentionally forbidden: PMM cannot depend on heap allocation without creating a recursion cycle at the foundation of memory management.

Current lock ordering documents heap → PMM as an allowed edge.

## Accounting and validation

A PMM should be able to account for free/allocated pages and detect invalid operations such as double free. Host tests can stress duplicate allocation, contiguous runs and cross-thread behavior, but host simulation is not identical to real interrupt/SMP execution.

The documentation therefore separates algorithmic host evidence from QEMU or physical-machine evidence.

## Physical ownership versus mapping

A frame may remain allocated while its virtual mapping changes. Conversely, removing a mapping does not by itself free the frame.

That separation is essential for shared pages, device mappings, page tables, JIT code and process teardown. The next chapter introduces virtual memory as a translation layer above PMM ownership.
