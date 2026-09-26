---
id: power-on-kstart
lang: en
type: technical-chapter
volume: 03-boot
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/start.c
  - kernel/metal/bootinfo.c
  - kernel/metal/linker.ld
symbols:
  - kstart
depends_on:
  - x86-64-memory-privilege
related:
  - elf-linking
  - kernel-model
---

# From power-on to `kstart`

## Reset is not a C function call

When a physical machine powers on or resets, the processor begins from an architecture-defined reset state. It does not know about ChrisOS, C, ELF symbols or a kernel stack. Platform firmware establishes enough hardware state to discover and start a boot target.

Modern PC systems commonly use UEFI. Legacy BIOS follows a different historical boot path. ChrisOS currently relies on Limine as an external bootloader rather than implementing firmware discovery itself.

## Responsibilities by layer

```text
power/reset
   ↓
CPU reset architecture
   ↓
platform firmware
   ↓
boot manager / bootloader
   ↓
ELF kernel image
   ↓
Limine protocol information
   ↓
kstart
   ↓
ChrisOS initialization
```

Each layer deliberately removes responsibilities from the next one.

Firmware knows how to reach boot media and firmware services. Limine knows how to load the kernel and provide boot protocol data. The kernel begins after those earlier transitions.

## The executable image

The kernel is an ELF64 executable produced according to `kernel/metal/linker.ld`. The linker script declares `ENTRY(kstart)` and organizes program headers/sections so the loader can place the image correctly.

The C identifier `kstart` therefore becomes part of a binary contract: the linker records its resolved address as the ELF entry point.

## Higher-half execution

ChrisOS is linked into a high virtual address region. This means the addresses used by compiled kernel code are not simple low physical addresses.

A bootloader must establish or cooperate with mappings that make the linked virtual addresses meaningful before control arrives at the kernel.

This is one reason a raw "copy kernel to RAM and jump to the first byte" loader is insufficient for a sophisticated kernel image.

## Boot information

The kernel needs machine facts that cannot be compiled into the binary:

- memory map;
- framebuffer description;
- higher-half direct-map information;
- processor/SMP information;
- boot-time configuration and protocol responses.

`kernel/metal/bootinfo.c` concentrates the interpretation of Limine-provided data. Treating boot responses as untrusted external inputs is important because every later allocator and driver relies on the resulting state.

## `kstart` ordering

`kernel/metal/start.c` is the principal architectural sequence. Initialization order is not cosmetic. Later subsystems depend on invariants established earlier.

At the documented revision, the sequence includes early serial/build information, boot-data processing, descriptor/interrupt foundations, physical and virtual memory, heap/process infrastructure, graphics bring-up, SMP/APIC work, ACPI/storage/filesystem, language/runtime services, desktop and network initialization.

A simplified dependency graph is:

<figure class="figure">
<img src="../../../assets/diagrams/boot.svg" alt="ChrisOS boot dependency flow">
<figcaption>Major initialization stages. The exact source order remains authoritative for a specific revision.</figcaption>
</figure>

## Why serial appears early

A graphical desktop cannot diagnose failures that occur before graphics or storage exists. Serial output is therefore initialized as early as practical. Early logging reduces the number of subsystems required to observe a fault.

This is a general kernel-engineering pattern: the first diagnostic channel should depend on less machinery than the components it diagnoses.

## Interrupt state

Early initialization often occurs with maskable interrupts disabled because handlers, stacks, routing and global state may not yet be safe. Enabling interrupts is an architectural milestone: after it, asynchronous code can execute between ordinary instructions.

Therefore every lock, global structure and driver reachable from an interrupt must already satisfy its concurrency contract before interrupts are enabled.

## Bootloader independence and self-hosting

Self-hosting the kernel compiler does not imply that the project must remove Limine. These are separate dependency questions.

A self-hosted kernel build asks whether ChrisOS can produce its own kernel executable. A self-written bootloader asks whether ChrisOS replaces the external program that loads that executable. The former can be achieved while retaining the latter.

## ChrisVM contrast

ChrisVM boot protocol v1 intentionally starts much later in the architectural process: it prepares a 64-bit environment, initial page tables and a small machine contract directly. It does not emulate BIOS or UEFI for that milestone.

This contrast is useful. A machine emulator may define a virtual platform with a purpose-built boot contract, while a real PC kernel depends on the platform and bootloader contracts available on physical/standard virtual hardware.
