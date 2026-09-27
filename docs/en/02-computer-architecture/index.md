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

<div class="abstract">This volume bridges digital logic and operating-system-visible machine behavior: datapaths, pipelines, speculation, instruction sets, x86-64 execution, privilege, memory hierarchy, buses, MMIO, DMA and platform discovery.</div>

## Scope

The volume explains both the architectural contract consumed by ChrisOS and the implementation ideas needed to understand physical processors and ChrisCPU.

The intended chain is:

~~~text
combinational + sequential logic
    ↓
datapath and control
    ↓
pipeline
    ↓
hazards / forwarding
    ↓
branch prediction / speculation
    ↓
renaming / out-of-order / retirement
    ↓
ISA
    ↓
machine-code encoding
    ↓
register / privilege / memory semantics
    ↓
DRAM controller + cache hierarchy
    ↓
coherence + atomics
    ↓
buses / PCIe / MMIO / DMA
    ↓
ACPI platform discovery
    ↓
ChrisOS
~~~

## Datapath and microarchitecture

The curriculum now treats these as distinct subjects:

1. CPU datapath and ISA.
2. Pipeline structure.
3. Data/control hazards and forwarding.
4. Branch prediction and speculation.
5. Register renaming, out-of-order execution and retirement.

The ISA is an externally visible contract. Pipeline and OoO mechanisms are possible internal implementations of that contract.

ChrisCPU currently targets the architectural contract rather than reproducing a speculative physical microarchitecture. This difference is explicit throughout the volume.

## Machine code and x86-64

The next group covers:

1. Machine code and relocatable meaning.
2. x86-64 registers, aliases and flags.
3. Instruction encoding and decoding.
4. x86-64 memory and privilege.
5. Privilege rings and controlled entry.

This provides the direct prerequisite chain for ChrisAsm, KCC, ChrisCPU and the ChrisOS kernel.

## Memory system

The memory sequence is:

1. DRAM organization and the memory-controller role.
2. Cache hierarchy and locality.
3. Multiprocessor coherence.
4. Atomic operations and memory ordering.

This keeps physical DRAM cells, architectural memory and cache-coherent SMP semantics as separate layers.

## Devices and platform

The platform path covers:

1. buses, port I/O, MMIO and DMA;
2. PCI/PCIe configuration and device discovery;
3. ACPI platform description.

These chapters bridge instruction execution to the devices that ChrisOS actually controls.

## Reading rule

General theory and current ChrisOS/ChrisCPU behavior are always separated.

A physical processor may pipeline and execute instructions out of order while exposing the same ISA state transitions that ChrisCPU currently interprets sequentially.

A linked or authored page is not automatically considered complete; coverage and depth gates remain authoritative.
