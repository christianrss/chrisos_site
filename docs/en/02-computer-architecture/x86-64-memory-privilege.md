---
id: x86-64-memory-privilege
lang: en
type: technical-chapter
volume: 02-computer-architecture
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/gdt.c
  - kernel/metal/idt.c
  - kernel/metal/mm.c
  - chrisvm/chris_arch.h
symbols:
  - mm_switch
depends_on:
  - cpu-datapath-isa
related:
  - virtual-memory
  - kernel-model
---

# x86-64 memory, privilege and architectural state

## Long mode

x86-64 long mode provides 64-bit general-purpose registers and a large virtual address space while retaining substantial historical architecture. Segmentation is greatly reduced for ordinary address calculation, yet segment selectors, descriptor tables and privilege metadata remain relevant to transitions and exception delivery.

ChrisOS links its kernel in the higher half. Its linker script uses an entry symbol `kstart` and places the kernel at a high canonical virtual address rather than assuming identity between physical and virtual addresses.

## Canonical virtual addresses

Not every 64-bit bit-pattern is a valid current x86-64 virtual address. Implementations support a defined virtual-address width, and high unused bits must form a canonical extension of the implemented sign bit. Software must therefore distinguish "64-bit integer" from "valid virtual address."

ChrisOS process mapping code rejects user addresses at or beyond its configured user boundary; kernel addresses occupy the high region.

## Rings and privilege

The architecture defines privilege levels conventionally numbered 0 through 3. Mainstream operating systems use ring 0 for the kernel and ring 3 for user programs.

Privilege is attached to execution state and descriptors. A ring-3 program cannot simply emit an instruction that rewrites CR3 or disables interrupts and expect success. The CPU validates whether the operation is permitted.

This provides a hardware basis for isolation:

```text
user program
   │ ring 3
   │ controlled transition
   ▼
kernel entry
   │ ring 0
   ├── validates request
   ├── accesses privileged state
   └── returns
```

## Control registers

Several control registers are central to kernel engineering.

| Register | Role relevant here |
|---|---|
| CR0 | global operating-mode and protection controls, including paging enable |
| CR2 | faulting linear address after a page fault |
| CR3 | physical base of the top-level page-translation structure plus architecture-defined control bits |
| CR4 | additional architectural features, including paging-related controls |

ChrisOS `mm_switch` writes CR3 when changing address spaces. That single machine instruction changes the translation context against which subsequent virtual memory references are interpreted.

## Descriptor tables

The GDT provides descriptors and selectors still required for code/data privilege conventions and the task-state segment. The IDT maps exception and interrupt vectors to handler descriptors.

A correct IDT entry is not merely a function pointer. It encodes target offset, selector, gate type and privilege/presence properties. The processor constructs the architectural transfer according to these fields.

## Exceptions

Exceptions are synchronous consequences of instruction execution. Examples include invalid opcode, general-protection fault and page fault. Interrupts from external devices are asynchronous relative to the currently executing instruction stream.

A kernel must preserve enough machine state to diagnose or recover from the event, determine its origin and either resume, terminate a process or fail the system in a controlled way.

## Architectural state in ChrisCPU

ChrisCPU has to represent the state that guest instructions can observe. The project's architectural state includes general registers, instruction pointer, flags and control/segment-related state required by the implemented subset.

The significance is methodological: ChrisOS kernel code provides concrete examples of *using* x86-64, while ChrisCPU provides concrete examples of *implementing the visible behavior* of x86-64.

## Architecture is not microarchitecture

None of these contracts require an emulator to reproduce speculative execution, physical register renaming or commercial cache hierarchies to be functionally correct for supported instructions. Those mechanisms affect timing and performance, not the basic architectural result.

This boundary also explains why QEMU or ChrisVM can run software compiled for an ISA without physically containing the same processor design.
