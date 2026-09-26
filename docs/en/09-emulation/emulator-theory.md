---
id: emulator-theory
lang: en
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - cpu-datapath-isa
  - buses-mmio-dma
related:
  - chrisvm-chriscpu
  - virtualization-chrishv
---

# Machine emulation: architectural state and instruction interpretation

## Emulator versus virtualizer

A machine emulator implements the visible behavior of a target machine in software. It may run on a completely different host ISA.

A hardware virtualizer uses processor virtualization facilities to execute much guest code directly on compatible hardware while trapping privileged/sensitive events.

The distinction is mechanism, not user interface.

## Architectural state

An x86-64 emulator needs a representation of state visible to the guest: general registers, RIP, RFLAGS, segment/control state, selected MSRs and the machine memory/device environment.

Microarchitectural structures such as commercial branch predictors are unnecessary unless the emulator aims to reproduce timing/performance rather than functional ISA behavior.

## Fetch, decode, execute

```text
RIP
 ↓
fetch instruction bytes
 ↓
decode prefixes/opcode/operands
 ↓
resolve operands
 ↓
execute semantics
 ↓
update flags/state
 ↓
deliver exception/interrupt if required
 ↓
commit next RIP
```

Variable-length x86 decoding makes it particularly important to track exact consumed length and addressing-mode semantics.

## Memory translation

A guest load is not a host pointer dereference. The emulator must apply guest segmentation/paging rules, detect faults and then access the virtual machine's physical map.

The physical map may resolve to RAM, framebuffer, MMIO or no device.

## Exceptions

If an instruction is invalid, divides by zero or accesses an unmapped page, the emulator must produce the architectural exception behavior expected by guest software.

An emulator that simply terminates the host process on every guest exception cannot boot an operating system that expects to install handlers.

## I/O and devices

IN/OUT instructions dispatch through a port bus. Physical addresses outside RAM may dispatch through MMIO. The executor should not contain device-specific branches for every model; buses provide registration and lookup.

## Determinism

An emulator can make time, entropy and external input explicit machine dependencies. When those are controlled, execution becomes reproducible, improving debugging and future record/replay.

## Performance techniques

A direct interpreter is easiest to validate. Faster emulators can add decoded-block caches, translation lookaside caches or dynamic binary translation/JIT.

Optimization should follow a validated semantic baseline because a fast incorrect decoder is harder to debug than a slow correct one.

## Testing

Small guest programs can isolate one instruction/exception contract. Full-kernel boot then tests interactions impossible to cover with unit cases alone.

Both are necessary: unit tests localize failures; system boot exposes missing combinations.
