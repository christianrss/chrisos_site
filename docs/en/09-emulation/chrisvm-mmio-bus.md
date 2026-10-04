---
id: chrisvm-mmio-bus
lang: en
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chrisvm.h
  - chrisvm/machine/machine.h
  - chrisvm/buses/mmio.c
  - chrisvm/cpu/emulator/mmu.c
  - chrisvm/cpu/emulator/operands.c
  - chrisvm/tests/test_chrisvm.c
symbols:
  - ChrisMmioSlot
  - chris_mmio_map
  - chris_mmio_find
  - chris_phys_read
  - chris_phys_write
depends_on:
  - chrisvm-memory-map
  - chrisvm-machine
related:
  - chrisvm-io-bus
  - chrisvm-devices
  - emulator-paging
---

# ChrisVM MMIO bus

## Scope

ChrisVM's generic MMIO layer connects guest physical addresses outside ordinary RAM/framebuffer backing to device callbacks.

Unlike the x86 port-I/O bus, MMIO is reached through the normal memory pipeline:

    guest instruction
      -> effective virtual address
      -> page translation
      -> guest physical address
      -> physical dispatcher
      -> MMIO slot
      -> device callback

The current implementation is enough to validate real memory-mapped device accesses in ChrisCPU, but it remains a bring-up bus rather than a complete device-memory subsystem.

Its strongest limitations are fixed capacity, unvalidated overlap, byte-serialized transactions, no MMIO trace implementation and no region permission/ordering model.

This chapter documents revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.

## Registration structure

Each ChrisMmioSlot contains:

- used;
- base;
- size;
- read callback;
- write callback;
- opaque context pointer.

ChrisMachine owns:

    ChrisMmioSlot mmio[CHRIS_MMIO_MAX]

with:

    CHRIS_MMIO_MAX = 8

The registration table is static and embedded in the machine object.

## Mapping a region

chris_mmio_map accepts:

    machine
    base
    size
    read callback
    write callback
    context

It rejects:

- null machine;
- size equal to zero.

It then stores the mapping in the first unused slot.

Registration fails once all eight slots are occupied.

The function does not reject overlapping mappings and does not validate callback pointers.

## Lookup

chris_mmio_find scans the slots from zero upward.

A slot matches when:

    pa >= base
    and
    pa - base < size

The subtraction-based test avoids needing to compute base + size in the comparison and therefore avoids one class of unsigned-end overflow.

When a match is found, the optional offset result becomes:

    pa - base

and the slot index is returned.

If no slot matches, the function returns minus one.

## First-match overlap policy

Because lookup is linear and stops at the first match, overlapping regions are resolved by registration order.

A later mapping can be completely or partially hidden by an earlier one.

This is deterministic but not a desirable implicit machine-description mechanism.

A static virtual platform should normally reject overlaps unless aliasing is intentionally modeled.

## MMIO is physical, not virtual

chris_mmio_map registers physical addresses.

A guest cannot access such a device merely because the region exists in the machine.

The guest's page tables must translate a virtual address to the registered physical address.

This separation is demonstrated by the MMIO integration test: the test registers a physical region at 0x06000000 and separately writes a PDE that maps the guest access to that region.

Therefore:

    MMIO registration != virtual mapping

This distinction becomes essential for higher-half kernels, user address spaces and device remapping.

## Physical dispatcher precedence

The generic MMIO registry is the final fallback in chris_phys_read/chris_phys_write.

The dispatcher checks, in order:

1. RAM;
2. framebuffer;
3. generic MMIO.

Therefore a registered MMIO slot does not override RAM or framebuffer.

An MMIO range overlapping RAM can exist in the table but remain unreachable for accesses wholly contained in RAM.

Likewise, framebuffer backing takes priority over generic MMIO.

## Read dispatch

If an access is not entirely contained in RAM or framebuffer, chris_phys_read enters the MMIO loop.

For every byte:

1. call chris_mmio_find(pa + i);
2. obtain the slot-relative offset;
3. call the device read callback with size 1;
4. keep the low byte of the returned value;
5. store it in the destination buffer.

If any byte cannot be resolved or a callback fails, the whole function returns failure.

## Write dispatch

chris_phys_write behaves similarly.

For every byte:

1. resolve the MMIO slot;
2. compute the relative offset;
3. call the write callback with size 1 and that byte value.

A failure stops the operation.

Earlier bytes may already have been written.

The operation is not transactional.

## Access width is not preserved

The most important semantic limitation is that generic MMIO callbacks always receive:

    size = 1

from the physical dispatcher.

A guest dword store therefore becomes four independent byte writes.

A guest qword load becomes eight byte reads.

This can change device behavior materially.

Real MMIO registers can depend on width:

- byte access may be invalid while dword is valid;
- one 32-bit write may latch state atomically;
- read side effects may occur once per transaction;
- write-one-to-clear fields may behave differently;
- partial writes may update only selected lanes.

The current bus preserves byte content for simple devices, not the original bus transaction.

## Contrast with port I/O

The port-I/O bus passes the decoded width directly to the device callback.

Thus:

    OUT dword -> one callback with size 4

while the current MMIO layer produces:

    memory dword store -> four callbacks with size 1

The two buses therefore have different transaction fidelity.

That distinction should remain explicit in device documentation.

## Cross-slot access

Because generic MMIO is resolved one byte at a time, a multi-byte request can cross from one MMIO slot to another.

Each byte is dispatched independently.

The current implementation does not reject such a crossing.

This behavior is deterministic, but it does not represent one atomic device transaction.

A future dispatcher should determine the owning region for the original access and decide whether crossing a region boundary is legal before invoking callbacks.

## Cross-region access with RAM or framebuffer

The byte-by-byte fallback does not correctly combine RAM/framebuffer with MMIO in a single access.

If an access begins inside RAM but extends beyond RAM, the RAM fast path fails because the entire range does not fit.

The fallback then tries to resolve every byte through generic MMIO, including bytes that still belong to RAM.

The result can fail even when both sides are individually backed.

This issue is part of the broader physical memory-map contract, but MMIO is where the fallback exposes it.

## Callback failure semantics

A device callback can return nonzero.

The physical layer turns that into a generic failure.

If the failure occurs behind a valid virtual translation, chris_va_read/chris_va_write generally treats a failed physical backing access as an emulator machine condition rather than a guest page-table fault.

There is no generic architectural "MMIO device callback failed" exception in x86.

Therefore device models need a clear convention:

- return success with device-defined status when the hardware would respond;
- reserve callback failure for emulator/model errors or truly absent backing.

## Missing callback validation

chris_mmio_map accepts null read or write pointers.

The dispatcher calls the matching direction directly.

A registered slot with a missing callback can therefore lead to invalid function-pointer use.

The current test device provides both handlers, so the ordinary path is safe.

The generic contract should either:

- reject null callbacks;
- or support explicit read-only/write-only regions with defined failure semantics.

## Test device at 96 MiB

test_chrisvm.c defines an eight-byte host cell and exposes it through MMIO at:

    0x06000000

The test callbacks treat offset as a byte position inside the 64-bit cell.

The write path updates one byte lane:

    shift = offset * 8

The read path extracts one byte lane.

Because the generic bus already serializes accesses by byte, this device is intentionally compatible with the current dispatcher.

The test guest writes 0x2a and reads it back through a mapped guest memory operand.

This validates the full path:

    decoded memory instruction
    -> virtual translation
    -> physical MMIO lookup
    -> write callback
    -> read callback
    -> guest register result

## MMIO and paging faults

A page-table failure happens before the MMIO bus.

If the virtual mapping is absent or violates permissions, the guest receives the appropriate paging fault and the physical MMIO callback is never reached.

If translation succeeds but the physical address has no backing region, the physical layer fails and ChrisVM can stop with CHRIS_EXIT_UNMAPPED.

This separation prevents absent virtual mapping and absent virtual hardware from being conflated.

## Framebuffer is not registered as generic MMIO

Although the framebuffer is memory-mapped from the guest's perspective, it is handled as a special physical region before the generic MMIO registry.

Its backing is ChrisFb.pix and it has its own fast path.

Therefore the term "MMIO" in the current codebase has two levels:

- memory-mapped devices conceptually, including framebuffer;
- the generic chris_mmio_map registry specifically.

The generic bus chapter refers to the second.

## Trace configuration gap

ChrisConfig exposes:

    trace_mmio

and ChrisCPU copies it into:

    cpu->trace_mmio

However, the inspected MMIO dispatcher does not consume that flag and does not emit MMIO transaction logs.

Therefore --trace-mmio is currently configuration/state without an implemented trace path.

This is a concrete observability gap.

A useful MMIO trace should include:

- RIP or instruction context;
- physical address;
- region/device;
- direction;
- original width;
- value;
- callback result.

Preserving original width requires fixing the byte-serialization problem first or recording both guest width and callback fragments.

## No memory-ordering model

The current MMIO path executes callbacks synchronously in interpreter order.

There is no explicit model of:

- posted writes;
- write combining;
- UC/WC memory types;
- fences;
- device ordering;
- cacheability;
- speculative access.

For a functional single-threaded interpreter this produces deterministic ordering, but it should not be mistaken for architectural MMIO ordering fidelity.

Future SMP and hardware-assisted execution will need a stronger contract.

## No region permissions

ChrisMmioSlot has no fields for:

- read-only;
- write-only;
- executable;
- allowed widths;
- alignment requirements;
- endian conversion;
- memory type.

Any policy must be implemented inside the callback.

A central region model could move common invariants into the bus.

## No automatic interrupt connection

MMIO registration only establishes address routing.

There is no associated IRQ line/vector in ChrisMmioSlot.

A device that needs interrupts must interact with CPU/machine interrupt facilities separately.

This is a healthy separation in principle, but future device registration may need a richer machine-device descriptor connecting address regions and interrupt topology.

## No device identity in the slot

The slot stores only callbacks and context.

There is no name/type identifier.

This makes debugging and generated memory maps less informative because the bus cannot report which logical device owns a range without external knowledge.

Adding a stable device identity would improve traces, diagnostics and collision reports.

## Capacity and lifecycle

There are eight MMIO slots.

There is no:

- unmap;
- resize;
- remap;
- hotplug;
- slot reset API.

The current static machine initializes its mappings once and keeps them for the machine lifetime.

That is sufficient for current tests.

## Hardware-virtualization boundary

A future ChrisHV backend will encounter guest MMIO through hardware virtualization exits or nested page-table mechanisms depending on implementation.

The backend should ultimately route device accesses into the same logical ChrisVM MMIO/device layer instead of creating independent device semantics.

To support that, the bus needs a width-preserving transaction API independent of the ChrisCPU byte-oriented physical implementation.

## Current validation evidence

The test suite demonstrates:

- generic MMIO registration;
- page mapping to MMIO;
- guest write reaching the device cell;
- guest read returning the stored value;
- physical unmapped behavior elsewhere.

The current tests do not cover:

- overlap;
- slot exhaustion;
- null handlers;
- transaction width;
- crossing slot boundaries;
- callback failure;
- trace_mmio;
- ordering semantics.

## Hardening priorities

The highest-value MMIO work is:

1. preserve the guest's original access width in device callbacks;
2. reject or explicitly model cross-region transactions;
3. reject unintended overlapping mappings;
4. support safe read-only/write-only handlers;
5. make --trace-mmio operational;
6. add device identity to mappings;
7. replace or deliberately formalize the eight-slot capacity;
8. define alignment and supported-width metadata;
9. separate machine/model failure from guest-visible device response;
10. add overlap, width, boundary and callback-failure tests;
11. unify framebuffer and generic MMIO under an authoritative physical-region model where practical;
12. design a backend-neutral MMIO transaction interface reusable by ChrisCPU and ChrisHV.

## Revision note

At revision e05a17fd76333114a3fb5c2452f38ca747d4ac56, ChrisVM has a functional generic MMIO registry and a verified guest-to-device path. Its current design is strongly byte-oriented: multi-byte guest operations lose transaction width and can be fragmented across slots. Combined with first-match overlap, fixed capacity and inactive trace_mmio configuration, this makes the bus suitable for simple bring-up devices but not yet a general high-fidelity MMIO subsystem.
