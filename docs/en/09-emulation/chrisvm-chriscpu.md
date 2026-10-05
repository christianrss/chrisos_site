---
id: chrisvm-chriscpu
lang: en
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chrisvm.h
  - chrisvm/chris_arch.h
  - chrisvm/machine/machine.c
  - chrisvm/machine/machine.h
  - chrisvm/machine/boot.c
  - chrisvm/cpu/emulator/chriscpu.c
  - chrisvm/cpu/emulator/decode.c
  - chrisvm/cpu/emulator/execute.c
  - chrisvm/cpu/emulator/mmu.c
  - chrisvm/cpu/common/exceptions.c
  - chrisvm/cpu/common/cpuid.c
  - chrisvm/tests/test_chrisvm.c
symbols:
  - chris_machine_create
  - chris_load_elf
  - chris_boot
  - chris_run
  - chris_decode
  - chris_execute
  - chris_translate
  - chris_raise
  - chris_cpuid
depends_on:
  - emulator-theory
  - x86-64-memory-privilege
related:
  - chrisvm-machine
  - chrisvm-boot
  - emulator-paging
  - emulator-exceptions
  - virtualization-chrishv
  - chrisvm-spec
---

# ChrisVM and ChrisCPU

## Scope

ChrisVM is the project-owned virtual machine and platform model. ChrisCPU is its software x86-64 execution backend.

They are separate abstractions.

ChrisVM owns the guest machine: RAM, I/O and MMIO registrations, serial state, framebuffer state, configuration, boot state and the active CPU backend. ChrisCPU owns the execution loop that interprets guest x86-64 instructions against the shared architectural state.

That separation is the central design decision of the subsystem:

~~~text
guest program
    |
    v
ChrisMachine
    |
    +-- RAM
    +-- port I/O
    +-- MMIO
    +-- serial
    +-- framebuffer
    |
    v
ChrisArchitectureState
    |
    v
ChrisCpuBackend
    |
    +-- ChrisCPU   implemented interpreter
    |
    +-- ChrisHV    reserved, currently refused
~~~

A future hardware-assisted backend should execute the same machine contract rather than creating a second virtual platform.

## Machine configuration

`ChrisConfig` controls the host-side machine configuration.

Current defaults are:

| Setting | Default |
|---|---:|
| RAM | 16 MiB |
| backend | `chriscpu` |
| deterministic mode | enabled |
| maximum steps | 1,000,000 |
| tracing | disabled |
| framebuffer dump | disabled |

Machine creation rejects RAM smaller than 2 MiB and RAM sizes that are not multiples of 2 MiB.

That requirement is connected to the current boot page-table construction, which maps guest RAM with 2 MiB pages.

The default configuration is intentionally small. ChrisVM is currently a development emulator, not a complete PC compatibility target.

## Machine ownership and lifetime

`chris_machine_create()` performs the high-level ownership sequence:

1. initialize or copy configuration;
2. resolve the requested CPU backend;
3. initialize the backend;
4. allocate zeroed guest RAM;
5. attach the serial device;
6. attach the framebuffer;
7. create CPU 0.

Failure at any stage unwinds the resources already allocated.

`chris_machine_destroy()` shuts down the CPU backend and releases:

- CPU state;
- framebuffer storage;
- guest RAM;
- the machine object itself.

The CPU backend therefore does not own the virtual platform. It receives a pointer to the machine and executes against resources owned by `ChrisMachine`.

## Bounded machine structures

The current internal machine model is intentionally fixed-size in several places.

Relevant bounds include:

| Structure | Bound |
|---|---:|
| port-I/O registrations | 8 |
| MMIO registrations | 8 |
| instruction trace ring | 256 entries |
| serial transmit capture | 8192 bytes |
| CPUs created by the current machine path | 1 |

These are implementation bounds, not architectural x86 limits.

Saturating such a table is therefore a machine-model limitation, not evidence that the corresponding hardware architecture has the same bound.

## Shared architectural state

`ChrisArchitectureState` is the common CPU-state contract.

It contains:

- 16 general-purpose 64-bit registers;
- RIP and RFLAGS;
- CR0, CR2, CR3, CR4 and CR8;
- CS, DS, ES, FS, GS and SS;
- TR and LDTR;
- GDTR and IDTR;
- EFER;
- STAR/LSTAR/CSTAR/FMASK;
- FS, GS and kernel-GS bases;
- APIC base;
- virtual TSC;
- storage for 16 XMM registers;
- current privilege level.

The presence of a field does not prove full instruction support for that architectural facility.

For example, XMM storage exists, but CPUID deliberately does not advertise SSE.

The shared state exists so that backend code does not define incompatible versions of the same virtual CPU.

## Backend contract

`ChrisCpuBackend` is a vtable with operations for:

- backend initialization;
- CPU creation;
- reset;
- run;
- interrupt injection;
- state export/import;
- TLB invalidation;
- shutdown.

ChrisCPU implements this contract in software.

ChrisHV is reserved behind the same interface but remains intentionally non-functional at the reviewed revision.

The design therefore has a backend seam without claiming that both backends are operational.

## Boot model

ChrisVM boot protocol v1 does not emulate the full PC startup sequence.

It does not execute:

- reset-vector firmware;
- BIOS;
- UEFI;
- Limine.

Instead, the host loader accepts a deliberately restricted ELF64 guest, loads supported PT_LOAD segments into guest RAM and then calls `chris_boot()`.

The boot routine installs enough architectural state to enter a 64-bit guest directly:

- GDT;
- initial page tables;
- CR0/CR3/CR4 state;
- EFER long-mode state;
- stack;
- segment state;
- fixed framebuffer mapping;
- CPL 0.

The production higher-half ChrisOS kernel is still outside this v1 contract.

Purpose-built ChrisVM guests are the supported boot target.

## Guest RAM and framebuffer

Guest RAM is host-allocated zeroed memory.

The public helpers `chris_write_ram()` and `chris_read_ram()` go through the physical-memory access layer rather than exposing the raw host pointer.

The fixed framebuffer contract uses:

- physical base `0x02000000`;
- 640 × 480 pixels;
- 32 bits per pixel.

The framebuffer is a simple machine device, not a VirtIO-GPU model.

The guest writes the mapped framebuffer while host tooling can inspect or display the resulting pixels.

## Instruction fetch

ChrisCPU fetches at most 15 bytes from the current RIP because x86 instructions are bounded to 15 bytes.

Each byte is fetched through virtual-memory translation with execute access.

This matters: instruction fetch is not allowed to bypass paging merely because the interpreter lives in the host process.

A failed executable-memory translation therefore participates in the same guest fault machinery as other virtual accesses.

## Decode model

`chris_decode()` converts raw x86 bytes into a bounded `ChrisInsn` structure.

The decoder tracks information such as:

- operand size;
- address size;
- REX fields;
- ModRM and SIB fields;
- displacement;
- immediate;
- condition code;
- ALU operation;
- lock/REP prefixes;
- instruction-specific form metadata.

It supports a deliberate subset of x86-64.

Unsupported or malformed encodings must not be interpreted as arbitrary host behavior.

They are rejected or converted to guest-visible invalid-opcode handling.

## Execution loop

The core loop in `chriscpu.c` follows this sequence:

~~~text
check breakpoint
    |
fetch up to 15 bytes
    |
decode
    |
format/trace
    |
clear rip_dirty
    |
execute
    |
if RIP was not explicitly changed:
    RIP += instruction length
    |
advance step counters / virtual time
    |
consider pending interrupt
~~~

The `rip_dirty` rule is essential.

Branch, call, return, exception or other control-transfer logic that writes RIP marks that fact so the generic sequential path does not also advance RIP.

Without this invariant, control-flow instructions would effectively apply two RIP updates.

## Step limit

Execution is bounded by `max_steps`.

A guest that spins indefinitely can therefore end with:

    CHRIS_EXIT_STEP_LIMIT

instead of trapping the host process in an unbounded interpreter loop.

This is especially useful for deterministic tests and malformed guests.

It is a host-side execution safety bound, not an x86 architectural exception.

## Exit reasons

The public architecture defines explicit machine exit reasons including:

- HLT;
- shutdown;
- exception;
- triple fault;
- breakpoint;
- step limit;
- unmapped physical access.

The distinction matters because "execution stopped" is not one semantic state.

A guest reaching HLT is different from an interpreter detecting an unmapped backing address.

Test code can assert the expected exit class instead of inferring outcome from process termination.

## Virtual address translation

`chris_translate()` implements four-level x86-64 page translation.

The walk follows:

~~~text
CR3
 |
 v
PML4
 |
 v
PDPT
 |
 v
PD
 |
 v
PT
~~~

The current implementation also recognizes 1 GiB and 2 MiB large pages.

A conventional 4 KiB translation can require up to four page-table-entry reads.

Thus, without a modeled TLB cache, interpreted virtual memory access has substantially higher host cost than a direct array access.

## Permission checks

The translator checks several guest-visible protection rules:

- present;
- writable;
- user/supervisor;
- CR0.WP behavior;
- NX when EFER.NXE is active;
- canonical virtual addresses.

It also updates accessed and dirty bits where applicable.

A non-canonical virtual address is not treated as an ordinary page-not-present condition; it is converted into general-protection behavior by the virtual-memory access helpers.

## Cross-page memory operations

`chris_va_read()` and `chris_va_write()` split accesses at 4 KiB boundaries.

That means one guest load or store that crosses a page boundary can require multiple translations and physical accesses.

This preserves page-granular protection behavior instead of assuming that translation of the first byte authorizes the whole host copy.

## Page-fault state

When translation fails with a page fault:

- CR2 receives the faulting virtual address;
- an x86-style page-fault error value is assembled;
- `chris_raise()` is invoked with vector 14.

If the page-table structure itself points outside modeled physical memory, the emulator can terminate with `CHRIS_EXIT_UNMAPPED` rather than fabricating a guest page fault for host backing that does not exist.

## Exception delivery

`chris_raise()` first tries normal guest exception delivery.

If no IDT is installed, the exception becomes monitor-visible:

    CHRIS_EXIT_EXCEPTION

with the vector and error retained.

When a usable IDT exists, ChrisCPU reads the gate, validates it, builds an interrupt frame on the guest stack, loads the target code segment and transfers RIP to the handler.

If exception delivery itself fails, ChrisCPU attempts a double fault.

A second delivery failure becomes:

    CHRIS_EXIT_TRIPLE

and the trace ring is dumped.

This produces a useful distinction between a guest exception and a collapse of guest exception delivery.

## Interrupt injection

The backend interface contains an interrupt-injection operation.

ChrisCPU stores a pending vector and later delivers it when the interrupt flag permits delivery.

The implementation also models the one-instruction STI delay before accepting a pending interrupt.

The current machine, however, is still single-vCPU and lacks the complete timer/APIC/IOAPIC platform required by the production kernel.

Interrupt machinery in the CPU should not be confused with a complete PC interrupt platform.

## Deterministic CPUID

`chris_cpuid()` never forwards the host processor wholesale.

Leaf 0 exposes the vendor string:

    ChrisCPU    

The modeled leaf 1 advertises only a small supported set including TSC, MSR, CMOV, APIC and PSE-related bits.

It explicitly avoids advertising FPU and SSE.

The extended leaf advertises long mode, while SYSCALL is not advertised because execution support is not implemented even though related EFER state exists.

This is a critical emulator invariant:

> guest capability discovery must not claim instructions or facilities the execution backend cannot honor.

## Deterministic time

The architecture state contains a virtual TSC.

ChrisCPU advances virtual execution state as interpreted instructions run rather than exposing uncontrolled host timing as the guest's primary execution clock.

This improves reproducibility.

It is not full deterministic replay: external inputs and future devices would require additional event recording to establish that stronger property.

## Debugging and trace

Each CPU keeps a 256-entry instruction trace ring.

Trace entries retain:

- RIP;
- instruction length;
- up to 15 instruction bytes;
- formatted instruction text.

The frontend can also stop on a configured RIP breakpoint.

These are monitor/debugger facilities, not a complete implementation of x86 debug registers and hardware breakpoints.

## Complexity and performance

ChrisCPU is an interpreter.

For (N) guest instructions, the base execution cost is approximately:

[
T(N) = O(N cdot (D + E + M))
]

where:

- (D) is decode work;
- (E) is instruction-specific execution;
- (M) is virtual-memory translation and device-access work.

Memory-heavy workloads can dominate because each guest memory access may trigger a page-table walk.

The current goal is correctness, inspectability and controlled tests rather than near-native throughput.

Hardware-assisted execution belongs to the separate future ChrisHV path.

## Validation evidence

`chrisvm/tests/test_chrisvm.c` currently exercises named cases including:

- arithmetic flags;
- CPU ADD behavior;
- memory plus CALL/RET;
- serial and port I/O;
- fault behavior;
- CPUID/MSR;
- multiply/divide and MSR behavior;
- ELF acceptance/rejection;
- deterministic decoder fuzzing;
- real MMIO callbacks;
- STOS and framebuffer splash.

Fault tests explicitly cover invalid opcode, page fault, general protection, divide error and step-limit termination.

The page-fault test also checks CR2.

These are host-executed ChrisVM tests. They are not a claim of full x86-64 conformance.

## Decoder fuzzing

The test suite feeds deterministic pseudo-random byte strings into `chris_decode()`.

A successful decode must have a legal bounded instruction length.

This is useful parser hardening for a decoder that consumes attacker-like arbitrary bytes.

It does not prove semantic correctness for every accepted instruction.

## Security boundary

ChrisVM executes guest state inside the host process.

It should therefore be treated as experimental emulation code, not as a hardened sandbox for hostile binaries.

Bounds checks, explicit translation, malformed-ELF tests and decode fuzzing reduce accidental corruption risk, but they do not establish a formal isolation boundary between malicious guest input and the host process.

A future security claim would require dedicated host-isolation analysis.

## Concurrency model

The current machine creates CPU 0 only.

There is no current multiprocessor execution model in which several host threads concurrently mutate one `ChrisMachine`.

As a result, current CPU/machine structures do not model the synchronization problems that a multi-vCPU implementation would introduce.

SMP support would require explicit rules for:

- shared RAM ordering;
- interrupt routing;
- atomic guest operations;
- device concurrency;
- CPU lifecycle;
- deterministic scheduling.

Those are future architecture questions, not hidden capabilities.

## Current limitations

The current ChrisVM/ChrisCPU platform does not provide:

- production ChrisOS kernel boot;
- UEFI/BIOS/Limine execution;
- complete x86-64 ISA coverage;
- functional ChrisHV;
- full PCI;
- mature VirtIO platform devices;
- APIC/IOAPIC/timer platform sufficient for production ChrisOS;
- SMP;
- production storage/network devices;
- a full GPU model;
- hardened hostile-guest isolation.

These limitations define the boundary between the current development emulator and a general-purpose PC virtualizer.

## Architectural role

ChrisVM is most useful today as a project-owned execution laboratory.

It allows ChrisOS to test assumptions about:

- CPU state;
- decoding;
- flags;
- page translation;
- exception delivery;
- I/O and MMIO;
- simple devices;
- direct boot.

QEMU remains the broader integration environment for the production operating-system path.

The two environments are complementary rather than interchangeable.

## Revision note

This chapter was reconciled against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

The current implementation is accurately described as a deterministic, single-vCPU, software-interpreted x86-64 subset machine with direct ELF boot and explicit fault/device models. It must not be described as a complete x86 PC emulator or as a hardware-accelerated hypervisor.
