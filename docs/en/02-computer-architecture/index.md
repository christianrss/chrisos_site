---
id: volume-02-computer-architecture
lang: en
type: volume-index
volume: 02-computer-architecture
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
---

# Computer architecture

<div class="abstract">This collection connects digital logic to the machine contract consumed by ChrisOS and emulated by ChrisCPU. It separates architectural state from microarchitectural implementation and then extends the machine model through memory hierarchy, buses and platform discovery.</div>

## Dependency chain

~~~text
digital logic and stored state
    ↓
datapath and control
    ↓
ISA-visible state
    ↓
pipeline and hazard handling
    ↓
prediction, speculation and retirement
    ↓
machine-code encoding
    ↓
x86-64 registers, flags and addressing
    ↓
privilege and protection
    ↓
DRAM organization and memory controller
    ↓
cache hierarchy
    ↓
coherence and memory ordering
    ↓
MMIO / DMA / buses
    ↓
PCI Express
    ↓
ACPI platform description
    ↓
boot and kernel
~~~

## Architecture and microarchitecture

The ISA defines software-visible state and transitions. Microarchitecture defines one implementation strategy for producing those transitions.

The curriculum therefore separates:

1. CPU datapath and ISA;
2. pipeline organization;
3. hazards and forwarding;
4. branch prediction and speculation;
5. register renaming, out-of-order execution and retirement.

ChrisCPU currently models architectural semantics rather than a speculative physical pipeline.

## Machine-code layer

The next sequence defines the binary contract required by assemblers, compilers, emulators and the kernel:

1. machine code;
2. x86-64 register aliases and flags;
3. instruction encoding and addressing modes;
4. memory and privilege;
5. controlled transitions between privilege levels.

## Memory-system layer

The memory-system sequence distinguishes:

1. physical DRAM organization and memory-controller policy;
2. cache hierarchy;
3. cache coherence;
4. atomic operations and memory ordering.

A physical DRAM cell, architectural memory location, cache line and virtual page are distinct abstractions.

## Platform layer

Device interaction proceeds through:

1. buses, port I/O, MMIO and DMA;
2. PCI and PCI Express discovery/configuration;
3. ACPI platform description.

These topics establish the platform prerequisites required by boot, interrupt routing, storage, graphics and networking.

## Evidence boundaries

Physical processor mechanisms are documented from architecture/vendor specifications and standard computer-architecture theory.

ChrisCPU source establishes only the behavior implemented by the emulator. Host-CPU behavior is not attributed to the guest model unless explicitly implemented.
