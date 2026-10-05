---
id: chrisvm-history
lang: en
type: technical-chapter
volume: 16-history
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chrisvm.h
  - chrisvm/chris_arch.h
  - chrisvm/machine/machine.c
  - chrisvm/machine/boot.c
  - chrisvm/cpu/common/state.c
  - chrisvm/cpu/common/cpuid.c
  - chrisvm/cpu/common/exceptions.c
  - chrisvm/cpu/emulator/chriscpu.c
  - chrisvm/cpu/emulator/decode.c
  - chrisvm/cpu/emulator/execute.c
  - chrisvm/cpu/emulator/mmu.c
  - chrisvm/cpu/hv/chrishv.c
  - chrisvm/buses/io.c
  - chrisvm/buses/mmio.c
  - chrisvm/devices/serial/serial.c
  - chrisvm/devices/fb/fb.c
  - chrisvm/frontend/main.c
  - chrisvm/frontend/view.c
  - chrisvm/tests/test_chrisvm.c
symbols:
  - chris_machine_create
  - chris_load_elf
  - chris_boot
  - chris_run
  - chris_decode
  - chris_translate
  - chris_raise
  - chris_backend_by_name
depends_on:
  - architecture-history
related:
  - chrisvm-spec
  - chrisvm-boot-spec
  - chrisvm-chriscpu
  - chrisvm-machine
  - chrisvm-boot
  - emulator-paging
  - emulator-exceptions
  - virtualization-chrishv
---

# ChrisVM history

## Scope

ChrisVM is one of the youngest architectural branches in ChrisOS.

Unlike graphics or the native toolchain, its current shape did not emerge through dozens of visible subsystem refactorings. The Git history shows two concentrated implementation commits on 25 September 2026 that established almost all of the current ChrisVM foundation.

This chapter therefore avoids inventing a long evolution.

It records the actual sequence:

1. create an in-process x86-64 virtual machine with a software CPU;
2. direct-boot small lower-half ELF guests;
3. validate CPU, memory, I/O and exception behavior;
4. add a framebuffer guest and host visualization;
5. deliberately keep the production ChrisOS/QEMU path separate;
6. leave hardware virtualization as an explicit future backend seam.

The current source is reconciled at revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

## Why ChrisVM was a new architectural branch

Before ChrisVM, ChrisOS already relied heavily on QEMU for system validation.

QEMU provided a complete-enough virtual platform for:

- boot firmware/bootloader paths;
- PCI devices;
- storage;
- networking;
- graphics;
- SMP;
- broader PC-machine behavior.

ChrisVM did not begin as a drop-in QEMU replacement.

Its initial purpose was narrower:

> create a project-owned virtual-machine layer in which ChrisOS controls the CPU state model, instruction execution, memory translation and machine devices directly.

This distinction is visible in the very first ChrisVM commit message.

## 25 September 2026 — ChrisVM and ChrisCPU arrive

The foundational commit is:

    86f08da720c24ec6ee0b0179d6a97b3dbf0ca0f6

Message:

    Add a ChrisCPU interpreter and the ChrisVM machine foundation. (#17)

The commit added approximately 4,777 lines and created most of the current directory structure.

Major components included:

- public ChrisVM API;
- shared architectural CPU state;
- machine configuration and ownership;
- direct ELF boot;
- ChrisCPU interpreter;
- x86-64 decoder/executor;
- flags;
- operands;
- four-level MMU;
- exception delivery;
- deterministic CPUID;
- port-I/O bus;
- MMIO bus;
- serial device;
- trace/debug support;
- command-line frontend;
- arithmetic guest;
- tests;
- ChrisHV backend seam.

That is why ChrisVM history is concentrated: many architectural decisions were introduced together.

## The initial architecture already separated machine and CPU

The first commit did not make the interpreter itself "the virtual machine".

It separated:

    ChrisMachine
        owns RAM and devices

    ChrisArchitectureState
        owns guest-visible CPU state

    ChrisCpuBackend
        executes that state

    ChrisCPU
        software interpreter backend

    ChrisHV
        reserved hardware-assisted backend

This separation remains one of the strongest architectural decisions in the subsystem.

It makes the CPU execution mechanism replaceable without redefining machine RAM/device ownership.

## Shared architecture state was present from day one

The initial `chris_arch.h` already established a broad state model:

- general registers;
- RIP/RFLAGS;
- control registers;
- segment state;
- descriptor tables;
- EFER/MSR-related state;
- TSC;
- XMM storage slots;
- CPL.

Not every field had complete instruction support.

The important historical point is that the backend boundary was designed around **architectural state**, not around interpreter-private variables.

That made a future hardware-virtualization backend conceptually possible without changing the public machine contract.

## ChrisHV was intentionally non-functional

The first commit added:

    chrisvm/cpu/hv/chrishv.c

plus placeholder VMX/SVM headers.

However the commit message explicitly said:

> ChrisHV is only a refused backend.

The current code preserves that decision.

Selecting the ChrisHV backend resolves a backend object, but initialization fails intentionally because VMX/SVM/KVM execution is not implemented.

This is an important historical non-claim.

ChrisHV was introduced as an **architectural seam**, not as hidden or partial acceleration.

## The QEMU path stayed in place

The same foundational commit explicitly stated:

> the QEMU kernel path stays in place.

This sentence defines the relationship between the two projects at birth.

ChrisVM was not intended to invalidate the existing QEMU gates.

It was a controlled environment for owning more of the virtual hardware stack.

Historically, that made ChrisVM additive rather than replacement architecture.

## Direct ELF boot instead of firmware emulation

The first ChrisVM did not emulate:

- BIOS;
- UEFI;
- Limine;
- reset vector;
- firmware discovery.

Instead it used direct ELF loading.

The host:

1. reads an ELF64 guest;
2. copies PT_LOAD segments into guest RAM;
3. creates minimal x86-64 long-mode state;
4. builds identity page tables;
5. sets RIP/RSP;
6. begins interpreted execution.

This drastically reduced the initial machine scope.

## Why direct boot was a strategic simplification

A full PC boot path would require solving many unrelated components before one CPU instruction could be tested.

Direct boot allowed early validation of:

- instruction decoding;
- arithmetic;
- stack control flow;
- paging;
- exceptions;
- port I/O;
- serial output;
- shutdown behavior.

That made ChrisCPU testable in isolation from firmware and PCI complexity.

## Boot protocol v1 was lower-half by design

The current `chrisvm-boot-spec` records the direct-boot contract as protocol version 1.

The loader places PT_LOAD segments at their `p_vaddr` and builds identity mappings.

Higher-half ELF segments are rejected.

This restriction was not introduced later as a regression.

It is part of the original simplification that made the first ChrisVM manageable.

## Consequence: production ChrisOS kernel was not a valid guest

The production ChrisOS kernel is higher-half and depends on a richer boot-information contract.

Therefore the initial ChrisVM could not simply load the normal kernel ELF.

That was intentional.

The correct historical statement is:

> ChrisVM could boot purpose-built direct ELF guests, but not the production ChrisOS kernel.

This boundary remains visible in the second commit too.

## Arithmetic guest as executable proof

The first commit included a small assembly guest.

Its role was to exercise the new interpreter rather than prove a full operating system.

The guest covered basic operations such as:

- serial output;
- integer arithmetic;
- memory access;
- call/return;
- HLT.

The test expected specific register and serial results.

This was a good initial evidence strategy because failures could be attributed to the VM rather than to a large guest kernel.

## Deterministic execution was a design goal

ChrisCPU avoided forwarding host CPUID.

It provided a project-defined CPUID view.

Its virtual TSC advanced deterministically with interpreted instructions.

The frontend also used explicit maximum-step limits.

These decisions reduced host-dependent behavior.

They did not create full deterministic replay, but they made host tests much more reproducible.

## The decoder began with a bounded x86 subset

The initial decoder was already substantial, but it was not a complete x86-64 implementation.

The architecture separated:

- decode;
- operand resolution;
- execution;
- flags;
- MMU;
- exceptions.

This made missing instruction forms more explicit than a monolithic giant switch would.

Unsupported encodings could become `#UD` or decoder failures rather than accidental host behavior.

## Four-level paging existed in the first foundation

`mmu.c` arrived in the first commit.

It implemented the important x86-64 translation structure:

    PML4
      -> PDPT
          -> PD
              -> PT

including support for large pages.

This meant ChrisVM was not merely a flat-address bytecode emulator.

It was designed around guest-visible x86 paging behavior from the start.

## Exception delivery also arrived immediately

The foundational commit included `exceptions.c`.

The VM could distinguish:

- monitor-visible exception exits when the guest had no IDT;
- guest delivery through an IDT when available;
- double-fault attempts;
- triple-fault termination when delivery collapsed.

That gave the first ChrisVM a meaningful fault model rather than simply aborting the host process on guest errors.

## Port I/O and MMIO were separate buses from the beginning

The first commit created:

    chrisvm/buses/io.c
    chrisvm/buses/mmio.c

That separation mirrors real x86 machine structure.

Port I/O is addressed through the IN/OUT instruction space.

MMIO is reached through physical memory accesses.

Keeping those paths distinct made later devices easier to model and avoided baking device behavior directly into the CPU executor.

## Serial was the first real guest device

The first machine included a simple 16550-like serial device at the traditional COM1 base.

Serial is historically a good first virtual device because it provides:

- observable guest output;
- simple port I/O;
- register semantics;
- loopback testing;
- no complex DMA requirement.

It gave ChrisVM an external behavior channel before graphics existed.

## Trace history was present from the foundation

The first commit added instruction trace support.

The current system retains a bounded trace ring containing recent RIP/bytes/formatted instruction data.

This becomes particularly useful when exception delivery fails and the VM reaches severe termination conditions.

Historically, debugging support was not deferred until after the interpreter "worked".

It was part of the initial machine.

## Tests were introduced with the architecture

The first ChrisVM commit also included a substantial host test file.

This matters because ChrisVM was not born as a visual demo only.

Tests covered areas such as:

- flags;
- arithmetic;
- memory;
- control flow;
- I/O;
- exceptions;
- CPUID/MSR behavior;
- malformed ELF;
- ChrisHV rejection;
- decoder fuzzing.

The exact suite evolved slightly in the next commit, but testability was foundational.

## 25 September — framebuffer support arrives less than one hour later

The second major commit is:

    be4307a28afb9b923549243d0f85a7358fcbf1b2

Message:

    Draw the boot splash on the ChrisVM framebuffer.

The commit added:

- framebuffer device;
- host viewer;
- splash guest;
- more decoder/executor support;
- more tests;
- framebuffer integration into machine/boot paths.

This was the only major structural extension to ChrisVM in the current Git history.

## Fixed framebuffer contract

The framebuffer was added at a fixed physical address:

    0x02000000

with:

    640 x 480
    32 bits per pixel

The guest could write directly to linear framebuffer memory.

The host could then:

- inspect pixels;
- dump PNG/PPM output;
- show the frame in an SDL window when available.

This created the first visual ChrisVM guest without requiring a GPU device model.

## REP STOS expanded the CPU for a concrete guest need

The splash guest fills the framebuffer using `REP STOS`.

The second commit therefore expanded decode/execute support so a useful graphics workload could run.

This illustrates a recurring emulator development pattern:

    define a small guest
        |
        v
    discover missing architectural instruction behavior
        |
        v
    implement and test only what the guest requires
        |
        v
    keep unsupported behavior explicit

That is preferable to claiming broad ISA completeness before evidence exists.

## Host visualization remained outside guest architecture

The SDL viewer does not become a guest GPU.

The guest sees a linear framebuffer.

The host chooses how to present it.

This separation matters:

    guest contract:
        memory-backed framebuffer

    host convenience:
        PNG/PPM/SDL display

A future guest device model can change without redefining what SDL means.

## The production kernel remained rejected

The second commit message explicitly states:

> The ChrisOS kernel ELF stays rejected.

This is one of the most important historical facts in the subsystem.

Even after a visible splash worked, ChrisVM did not claim production-kernel boot support.

Graphics success did not erase the lower-half/direct-boot limitations.

## Two commits established almost the whole present structure

Path history for major ChrisVM files shows only these two commits.

For example:

- `chriscpu.c`: introduced in the foundation commit;
- `mmu.c`: introduced in the foundation commit;
- `exceptions.c`: introduced in the foundation commit;
- `chrishv.c`: introduced in the foundation commit;
- `machine.c`: foundation + framebuffer commit;
- `boot.c`: foundation + framebuffer commit;
- `decode.c`: foundation + framebuffer commit;
- `test_chrisvm.c`: foundation + framebuffer commit.

That is why this history chapter is shorter in chronological phases than graphics or toolchain history.

The architecture was designed in a relatively concentrated burst.

## Current ChrisVM still reflects the original split

At revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, the key model remains:

    guest ELF
       |
       v
    ChrisMachine
       |
       +-- RAM
       +-- I/O bus
       +-- MMIO bus
       +-- serial
       +-- framebuffer
       |
       v
    ChrisArchitectureState
       |
       v
    ChrisCPU

with ChrisHV still reserved and refused.

The foundational architecture has therefore been stable since introduction.

## Current machine remains intentionally small

ChrisVM still does not emulate the complete machine required by production ChrisOS.

Major absent platform areas include:

- UEFI/BIOS/Limine;
- full PCI topology;
- ACPI;
- APIC/IOAPIC platform;
- storage controllers;
- production network devices;
- USB host controller stack;
- full SMP;
- complete GPU device path;
- hardware-assisted CPU backend.

This is consistent with the original goal.

## Current boot protocol remains direct-boot v1

The current boot code still:

- accepts ELF64 x86-64;
- loads lower-half PT_LOAD segments;
- creates identity mappings;
- enters long mode directly;
- starts at CPL0;
- does not construct the normal ChrisOS Limine handoff.

Thus the historical limitation remains a current compatibility boundary.

## ChrisVM versus QEMU

The two systems solve different layers.

### QEMU path

Best suited to validating ChrisOS against a richer PC-like environment with existing device models and firmware/boot integrations.

### ChrisVM path

Best suited to owning and testing:

- the CPU state model;
- instruction decoder;
- execution semantics;
- guest page translation;
- exceptions;
- simple device models;
- deterministic host tests.

A future ChrisVM could grow toward QEMU replacement for selected workflows, but that is not the current architecture.

## ChrisCPU versus ChrisHV

The backend seam expresses a future architecture:

    shared architecture state
       /               \
      v                 v
  ChrisCPU          ChrisHV
 software           hardware-assisted

Only the left path is implemented.

The existence of the right path in source is useful because it forces the state/backend interface to be considered early.

It must not be reported as acceleration support.

## Decoder fuzzing became part of the evidence

The current test suite includes deterministic decode fuzzing.

Random byte strings are passed to the decoder and the test verifies that successful decodes have bounded legal lengths.

This is useful because x86 decoding is one of the highest-risk parser surfaces in an emulator.

The fuzz test does not establish ISA conformance, but it strengthens malformed-input robustness.

## Malformed ELF testing protects the host boundary

ChrisVM's direct-boot model means the host parses guest ELF input.

That parser is therefore part of the trust boundary.

Tests reject malformed images rather than copying arbitrary offsets into guest RAM.

This is historically important: direct boot simplified the machine, but it moved more responsibility into the host loader.

## Exit reasons formalized machine outcomes

The current public interface distinguishes outcomes such as:

- HLT;
- shutdown;
- exception;
- triple fault;
- breakpoint;
- step limit;
- unmapped physical access.

This design follows naturally from the first architecture.

A virtual machine needs to distinguish:

    guest completed/stopped intentionally

from:

    emulator or guest reached a fault condition

without crashing the host process.

## Debugging model remained monitor-oriented

Breakpoints are monitor breakpoints on RIP, not a full implementation of x86 debug registers.

Trace history is host-side diagnostic state.

This reflects ChrisVM's original purpose as a development emulator rather than a transparent production hypervisor.

## Historical milestones

| Date | Commit | Architectural meaning |
|---|---|---|
| 2026-09-25 21:28 UTC | `86f08da` | ChrisVM machine, ChrisCPU, paging, exceptions, buses, serial, direct ELF boot and tests introduced |
| 2026-09-25 22:25 UTC | `be4307a` | fixed linear framebuffer, splash guest, host PNG/SDL view and extra execution support |

The compressed timeline is itself meaningful.

ChrisVM was introduced as a coherent subsystem rather than assembled through a long chain of unrelated experiments.

## What did not happen

Several tempting historical claims are false at the reviewed revision:

- ChrisVM did not replace QEMU;
- ChrisVM did not boot the production ChrisOS kernel;
- ChrisHV did not become functional;
- the framebuffer did not become a GPU model;
- adding paging did not make the interpreter fully x86-64 conformant;
- adding XMM storage did not imply SSE implementation;
- CPUID state did not imply host CPUID passthrough.

The project source and commit messages are unusually clear about these non-claims.

## Architectural lessons

### Start with an executable subset

A small direct-boot guest made CPU/MMU testing possible before firmware/device completeness.

### Keep machine ownership separate from CPU execution

This created a clean backend seam for future acceleration.

### Add tests with the first implementation

ChrisVM's architecture was testable from its first commit.

### Preserve explicit refusal for unsupported backends

A backend that fails clearly is safer than one that silently falls back while claiming acceleration.

### Visual output does not imply full platform compatibility

The splash guest proved framebuffer/instruction behavior, not production-kernel boot.

## Current maturity statement

At revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, ChrisVM is best described as:

> a deterministic, host-testable, single-vCPU x86-64-subset virtual machine with direct ELF boot, four-level paging, exception handling, serial, port I/O, MMIO and a fixed framebuffer.

It is not yet:

> a complete PC virtualizer capable of replacing QEMU for the production ChrisOS boot path.

The historical record supports that distinction from the first commit onward.

## Future history boundary

A future entry belongs in this chapter when ChrisVM crosses a real architectural boundary such as:

- production ChrisOS kernel boot;
- higher-half/boot-information protocol v2;
- functional PCI/device topology;
- SMP;
- functional ChrisHV backend;
- hardware-assisted execution;
- a stable disk/network device model;
- replacement of a QEMU validation class.

Smaller decoder opcode additions belong in implementation documentation, not necessarily in architecture history.

## Revision note

This chapter was reconciled against current ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56` and the two foundational ChrisVM commits listed above.

The central historical fact is stability of intent: ChrisVM began as a project-owned, testable emulator alongside QEMU, and the current source still reflects that original boundary.
