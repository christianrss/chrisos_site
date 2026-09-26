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

<div class="abstract">Datapaths, control, instruction sets, x86-64 execution, privilege, caches, memory hierarchy, buses, MMIO and DMA.</div>

## Scope

This volume defines the terminology and relationships required before implementation detail. General concepts remain separate from ChrisOS-specific decisions; when a chapter crosses into implementation, its source revision and relevant files are declared in frontmatter.

## Core chapters

1. [CPU datapath and ISA](cpu-datapath-isa.md)
2. [Machine code and relocatable meaning](machine-code.md)
3. [Registers, aliases and flags](x86-registers-flags.md)
4. [Instruction encoding and decoding](x86-instruction-encoding.md)
5. [x86-64 memory and privilege](x86-64-memory-privilege.md)
6. [Privilege rings and controlled entry](privilege-rings.md)
7. [Buses, MMIO and DMA](buses-mmio-dma.md) — expansion pending.

The [curriculum](../learning-path.md) also tracks unwritten prerequisites and subsequent chapters on caches, coherence, atomics, PCI and ACPI. A linked page is not a declaration of complete coverage.

## Reading rule

Lower-layer details need not be memorized, but terms used by higher layers are defined before their first technical use. Diagrams show flow and responsibility; tables record contracts, layouts and states.
