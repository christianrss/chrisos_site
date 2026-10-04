---
id: chrisvm-spec
lang: en
type: specification
volume: 15-specifications
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chrisvm.h
  - chrisvm/chris_arch.h
  - chrisvm/machine/machine.h
  - chrisvm/machine/config.c
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
  - chrisvm/debug/trace.c
  - chrisvm/frontend/main.c
  - chrisvm/tests/test_chrisvm.c
  - chrisvm/Makefile
symbols:
  - chris_config_init
  - chris_machine_create
  - chris_machine_destroy
  - chris_backend_by_name
  - chris_run
  - chris_decode
  - chris_translate
  - chris_raise
  - chris_cpuid
  - chris_io_map
  - chris_mmio_map
depends_on:
  - specifications-policy
  - chrisvm-chriscpu
  - chris-architecture-state
  - chrisvm-machine
related:
  - chrisvm-boot-spec
  - emulator-theory
  - emulator-paging
  - emulator-exceptions
  - virtualization-chrishv
---

# ChrisVM specification

## Status and conformance boundary

This document specifies the guest-visible and host-facing contract implemented by ChrisVM at ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

It is a revision-bound implementation specification, not a claim of complete x86-64 PC compatibility.

A conforming implementation of this revision reproduces the behavior described here for the implemented subset. Behavior not implemented by the source is outside the contract even if real x86-64 hardware provides it.

The current executable CPU backend is **ChrisCPU**, a software interpreter. The **ChrisHV** backend exists only as an interface seam and intentionally fails initialization because VMX, SVM and KVM execution are not implemented in this revision.

## Architectural split

ChrisVM is the virtual machine/platform.

ChrisCPU is one CPU execution backend.

The architecture is:

    guest
      |
      v
    ChrisArchitectureState
      |
      +-- ChrisCPU interpreter
      |
      +-- ChrisHV seam (not functional)
      |
      v
    ChrisMachine
      +-- RAM
      +-- port I/O bus
      +-- MMIO bus
      +-- serial device
      +-- framebuffer
      +-- shutdown port

The CPU backend does not own the virtual platform.

The machine owns RAM and devices. A backend executes the shared architectural state against that machine.

## Configuration object

The public `ChrisConfig` fields are:

| Field | Meaning |
|---|---|
| `ram_size` | guest RAM size |
| `backend` | CPU backend name |
| `trace` | instruction trace |
| `trace_memory` | memory tracing switch |
| `trace_io` | port-I/O tracing switch |
| `trace_mmio` | MMIO tracing switch |
| `deterministic` | deterministic-execution policy flag |
| `max_steps` | execution step budget |
| `break_rip` | breakpoint address |
| `has_break` | breakpoint enabled |
| `debug` | interactive debugger |
| `headless` | suppress framebuffer viewer |
| `fb_dump` | framebuffer output path |

`chris_config_init` establishes:

    ram_size = 16 MiB
    backend = "chriscpu"
    deterministic = 1
    max_steps = 1,000,000

Other fields begin cleared.

The current command-line parser exposes backend, tracing, deterministic mode, debugger/headless behavior, breakpoint, framebuffer dump and max-step options. `ram_size` is currently an API-level field rather than a normal frontend command-line option.

## Machine creation constraints

`chris_machine_create` rejects RAM smaller than 2 MiB.

RAM must also be aligned to 2 MiB:

[
ram_size mod 2MiB = 0
]

The framebuffer device is fixed at physical address:

    0x02000000

or 32 MiB.

`chris_fb_attach` rejects a machine whose RAM extends above that base. Therefore the current complete machine topology effectively permits RAM up to 32 MiB while the fixed framebuffer is attached.

The default 16 MiB configuration satisfies this constraint.

## Machine resource limits

The current internal limits are:

    CHRIS_IO_MAX    = 8
    CHRIS_MMIO_MAX  = 8
    CHRIS_TRACE_RING = 256
    CHRIS_TX_MAX    = 8192

These are implementation limits, not architectural x86 limits.

A device model that requires more than eight independently registered port ranges or MMIO regions cannot be added without increasing or restructuring these tables.

## CPU count

The current machine creates exactly one CPU:

    backend->create_cpu(machine, 0)

There is no SMP topology, AP startup, local APIC timer model or inter-processor interrupt fabric in the current ChrisVM machine.

The shared state representation can evolve toward those features, but this revision is a single-vCPU machine.

## Shared architectural state

`ChrisArchitectureState` is the canonical CPU state exchanged through the backend interface.

It includes:

- 16 general-purpose registers;
- RIP;
- RFLAGS;
- CR0, CR2, CR3, CR4, CR8;
- CS, DS, ES, FS, GS, SS;
- TR and LDTR placeholders;
- GDTR and IDTR;
- EFER;
- STAR, LSTAR, CSTAR and FMASK;
- FS/GS/KERNEL_GS bases;
- APIC base;
- virtual TSC;
- 16 XMM storage slots;
- CPL.

The existence of a field does not imply complete execution support for the corresponding architectural facility.

For example, XMM storage exists in the common state, but CPUID explicitly does not advertise SSE support in this revision.

## Backend interface

A `ChrisCpuBackend` supplies:

    init
    create_cpu
    reset
    run
    inject_irq
    get_state
    set_state
    invalidate_tlb
    shutdown

The intent is that alternative execution engines import/export the same architecture state.

The interface is therefore a compatibility seam between CPU implementations, not proof that all future hardware-virtualization state mapping is already solved.

## ChrisHV status

Selecting:

    backend = "chrishv"

resolves to the `chrishv_backend` object.

Its initialization intentionally returns failure and reports that VMX/SVM are not implemented.

Tests explicitly verify that creating a machine with this backend fails.

Therefore the normative status is:

    chriscpu: implemented
    chrishv: reserved, non-functional

A frontend or document must not present ChrisHV as an available acceleration backend at this revision.

## ChrisCPU execution loop

ChrisCPU executes an instruction-oriented loop.

For each step it:

1. checks the configured RIP breakpoint;
2. fetches up to 15 bytes through guest virtual-memory translation;
3. decodes one instruction;
4. formats/pushes trace information;
5. executes the decoded operation;
6. advances RIP when the instruction did not explicitly change it;
7. considers pending IRQ delivery;
8. increments step count;
9. increments the virtual TSC by one.

The TSC therefore advances once per interpreted instruction in this backend.

It is deterministic execution accounting, not a model of physical CPU cycles.

## Instruction fetch

The current fetch helper requests 15 bytes one byte at a time through `chris_va_read` with execute access.

Fifteen bytes is the architectural x86 instruction-length ceiling.

Because all 15 bytes are fetched before decode, a short instruction close to a mapping boundary can cause access to bytes beyond the actual instruction.

This behavior is part of the current implementation and is a known precision limitation.

## Decoder contract

`chris_decode` accepts:

    byte buffer
    available length
    output ChrisInsn

Success returns a positive instruction length no greater than 15.

Failure returns a negative result.

Decode fuzz tests enforce:

[
1 le len le 15
]

for every successful decode, and require:

    insn.len == return_value

Malformed or unsupported instruction bytes ultimately produce `#UD` behavior through the interpreter.

## Implemented operation families

The decoder/executor architecture has explicit operation classes for:

- integer ALU;
- MOV;
- MOVZX/MOVSX;
- LEA;
- XCHG;
- PUSH/POP;
- PUSHF/POPF;
- JMP/Jcc;
- CALL/RET;
- shifts/rotates;
- unary integer operations;
- multiply/divide forms;
- IN/OUT;
- INT;
- IRETQ;
- HLT;
- NOP;
- flag-control instructions;
- LEAVE;
- CPUID;
- RDMSR/WRMSR;
- MOV to/from control registers;
- descriptor-table operations;
- SETcc;
- CMOVcc;
- STOS/REP STOS;
- explicit undefined/unimplemented classes.

This list describes implemented operation families, not every x86 opcode/form.

The decoder source remains the authority for exact accepted encodings.

## Notable unsupported CPU facilities

The current virtual CPU must not be treated as a complete AMD64 implementation.

Notable absent or incomplete areas include:

- x87 FPU execution;
- SSE/AVX execution;
- SYSCALL/SYSRET execution;
- complete system-instruction coverage;
- complete segmentation/privilege-transition behavior;
- debug-register model;
- hardware performance counters;
- full APIC/x2APIC behavior;
- SMP;
- complete architectural timing.

CPUID must remain conservative so guest software does not select unsupported paths.

## Deterministic CPUID

Host CPUID is never forwarded.

The virtual vendor string is:

    ChrisCPU    

Leaf 0 advertises maximum standard leaf 1.

Leaf 1 advertises only selected implemented features, including TSC, MSR, CMOV, APIC and PSE bits as encoded by the current source.

It does not advertise FPU or SSE.

Extended leaf `0x80000001` advertises long mode.

SYSCALL is not advertised because execution is not implemented even though EFER stores SCE-related state.

This prevents the host processor from silently changing guest-visible capabilities.

## RFLAGS and ALU behavior

Arithmetic flags are computed by the ChrisCPU flag helpers rather than delegated to the host CPU.

Tests verify representative carry, zero, sign, overflow, parity and auxiliary-carry outcomes.

This is necessary for deterministic architecture behavior across host machines.

A correct emulator result is defined by x86-visible state, not the host's native flags register.

## Virtual memory model

ChrisCPU implements four-level x86-64 page-table walking.

Virtual addresses must be canonical under the 48-bit rule.

The walker handles:

- PML4;
- PDPT;
- PD;
- PT;
- 1 GiB large pages;
- 2 MiB large pages;
- 4 KiB pages.

The implementation checks present, writable and user permissions.

NX is enforced only when EFER.NXE is enabled.

Accessed and dirty bits are written back to entries when appropriate.

## Page-fault semantics

For translation failures, the implementation constructs x86-style page-fault error bits for:

- present/protection;
- write;
- user;
- instruction fetch.

CR2 is set to the faulting virtual address before page-fault delivery.

Noncanonical addresses produce `#GP`.

Failure to read page-table memory or to resolve the final physical target can result in the monitor-facing `CHRIS_EXIT_UNMAPPED` state rather than a guest page fault.

## TLB status

The backend interface has an `invalidate_tlb` operation.

In ChrisCPU this increments a generation counter.

The current interpreter does not maintain a real translation cache comparable to a hardware TLB.

Page-table walks are performed directly.

Therefore TLB invalidation exists as an interface seam rather than a performance-significant translation cache in this revision.

## Exception delivery

`chris_raise` records exception vector/error state and attempts guest delivery.

If IDTR is zero, the event is reported to the monitor as:

    CHRIS_EXIT_EXCEPTION

If an IDT exists, ChrisCPU validates the selected gate and attempts to transfer control to it.

The current implementation accepts interrupt/trap gates and requires the IST field to be zero.

If ordinary exception delivery fails, ChrisCPU attempts a double fault.

If double-fault delivery also fails, the machine stops with:

    CHRIS_EXIT_TRIPLE

and dumps recent instruction trace information.

## Current exception-frame model

The current delivery code pushes a frame containing:

    SS
    old RSP
    RFLAGS
    CS
    RIP
    optional error code

before transferring to the handler.

This is the current ChrisCPU contract.

It is not a statement that every x86 privilege-transition case and hardware frame variant has been implemented.

## Interrupt injection

A backend can receive one pending interrupt vector.

ChrisCPU delivers it only when:

- the CPU is not halted by another exit condition;
- an IRQ is pending;
- RFLAGS.IF is set;
- the post-STI delay has elapsed.

The current model is intentionally simple.

There is no complete programmable interrupt-controller device driving multiple queued vectors.

## Exit reasons

The current public exit reasons are:

    CHRIS_EXIT_NONE
    CHRIS_EXIT_HLT
    CHRIS_EXIT_SHUTDOWN
    CHRIS_EXIT_EXCEPTION
    CHRIS_EXIT_TRIPLE
    CHRIS_EXIT_BREAK
    CHRIS_EXIT_STEP_LIMIT
    CHRIS_EXIT_UNMAPPED

These are monitor/backend outcomes.

They must not be conflated with guest process exit codes.

## Step limit

`chris_run` accepts a maximum number of interpreted steps.

If the CPU remains runnable after the budget is exhausted, the result is:

    CHRIS_EXIT_STEP_LIMIT

The default frontend budget is one million steps.

This gives deterministic termination for runaway guests in tests.

## Breakpoint semantics

A configured breakpoint compares the current RIP before instruction fetch.

When matched, execution stops with:

    CHRIS_EXIT_BREAK

The interactive debugger can also set a new breakpoint and execute one step or continue.

This is a monitor breakpoint, not an x86 DR0-DR7 hardware-breakpoint model.

## Trace ring

Every decoded instruction is recorded in a ring with:

- RIP;
- up to 15 raw bytes;
- formatted instruction text.

The ring contains 256 entries.

It is retained even when full textual tracing is disabled.

This allows recent execution history to be dumped during severe exception delivery failure.

## Port-I/O bus

The machine supports eight registered port ranges.

A range provides IN and OUT callbacks.

Valid access sizes are:

    1 byte
    2 bytes
    4 bytes

Reading an unmapped port succeeds and returns all ones for the requested width.

Writing an unmapped port is ignored and succeeds.

This is the current platform convention.

## Serial device

ChrisVM maps a simple 16550-like serial model at:

    0x3f8 .. 0x3ff

The implementation supports the register behaviors required by current guests, including:

- divisor-latch state;
- line/modem control;
- scratch register;
- transmit output;
- internal loopback used by tests.

Transmitted guest bytes are retained in an 8192-byte host buffer and can also be forwarded through a host hook.

It is not a full timing-accurate UART.

## Shutdown port

ChrisVM maps:

    0x501

A byte write whose low eight bits equal `1` marks machine shutdown and stops the CPU with:

    CHRIS_EXIT_SHUTDOWN

This is a ChrisVM-specific platform ABI.

It is not a standard PC ACPI poweroff mechanism.

## Physical memory dispatch

Physical accesses are resolved in this order:

1. guest RAM;
2. fixed framebuffer range;
3. registered MMIO region.

This ordering matters if future platform revisions permit overlap.

The current machine avoids normal RAM/framebuffer overlap by constraining RAM size.

## MMIO bus

The machine supports eight MMIO mappings.

Each mapping has:

- base;
- length;
- read callback;
- write callback;
- opaque context.

Current generic physical access breaks MMIO transfers into byte callbacks.

A multi-byte CPU access therefore becomes a series of one-byte device operations in the current model.

Device models whose registers require atomic wider transactions would need a stronger bus contract.

## Unmapped physical access

If a translated physical access is neither RAM, framebuffer nor registered MMIO, the physical operation fails.

ChrisCPU converts that condition into:

    CHRIS_EXIT_UNMAPPED

for ordinary execution paths.

This monitor-visible outcome distinguishes "page table mapped this address" from "the machine has an actual physical target there."

## Framebuffer device

The fixed framebuffer contract is:

    physical base: 0x02000000
    width:         640
    height:        480
    pitch:         2560 bytes
    pixel storage: 32 bits per pixel

The test guest writes values such as XRGB8888-style pixels directly into this linear memory.

Any write to the framebuffer marks it dirty.

The host can query individual pixels and dump the complete image.

## Framebuffer export

The frontend can export the framebuffer as:

- PNG when the path ends in `.png`;
- PPM otherwise.

If SDL2 is available and the run is not headless, the frontend can display the final dirty framebuffer in a software-rendered window.

This viewer is a host presentation convenience, not a guest GPU device.

## ELF guest model

The normal frontend accepts one ELF64 x86-64 guest file.

The ELF loader and boot protocol are specified separately in `chrisvm-boot-spec`.

The machine does not emulate firmware to discover this executable.

The host frontend loads it directly before CPU execution.

## Frontend success status

The command-line frontend returns success only when the machine ends through:

    CHRIS_EXIT_HLT

or:

    CHRIS_EXIT_SHUTDOWN

and any requested framebuffer dump succeeds.

Exceptions, triple faults, step limit, unmapped accesses and similar exits do not count as successful guest completion.

## Test evidence

`make -C chrisvm test` builds and executes:

- the ChrisVM test suite;
- an arithmetic/serial ELF guest;
- a framebuffer splash ELF guest.

The suite exercises, among other areas:

- integer flags;
- arithmetic;
- memory load/store;
- CALL/RET;
- serial loopback;
- unmapped I/O behavior;
- shutdown port;
- #UD, #PF, #GP and divide error;
- step-limit exit;
- CPUID;
- MSR access;
- malformed ELF rejection;
- ChrisHV refusal;
- 2000 deterministic decode-fuzz iterations;
- real MMIO mapping;
- multiply/divide cases;
- framebuffer stores;
- guest serial output.

This is strong implementation evidence for the current subset, not proof of complete x86 conformance.

## Determinism boundary

ChrisCPU avoids forwarding host CPUID and uses an explicit step budget.

The virtual TSC increments deterministically by instruction.

Those choices reduce host dependence.

However, the `deterministic` configuration field is not yet a complete record/replay engine.

There is no general event log capable of replaying asynchronous devices, timers, SMP races or external network input.

## Security and isolation boundary

ChrisVM is currently a development emulator.

Guest addresses are mediated through emulator memory structures rather than directly treated as host pointers, which is the correct isolation shape.

However, ChrisVM should not yet be treated as a hardened hostile-code sandbox.

Parser, decoder and device-model bugs can still compromise the host process.

Fuzzing and sanitizer coverage remain important.

## Current platform omissions

The current platform does not yet emulate the full device set required for the real ChrisOS kernel.

Major missing machine components include:

- BIOS/UEFI/Limine;
- PCI configuration mechanism/device tree sufficient for ChrisOS drivers;
- AHCI/NVMe/VirtIO block;
- PS/2/xHCI input platform;
- APIC/IOAPIC/timers sufficient for full kernel boot;
- SMP;
- ACPI;
- native network/audio devices;
- functional hardware-assisted backend.

These omissions are why ChrisVM does not yet replace QEMU as the general ChrisOS kernel platform.

## Conformance statement

At revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, a conforming ChrisVM implementation is a deterministic single-vCPU x86-64-subset virtual machine with:

- shared architecture state;
- software ChrisCPU execution;
- four-level paging;
- guest exception delivery;
- port I/O;
- MMIO;
- serial;
- fixed framebuffer;
- direct ELF boot;
- monitor break/trace/step limits.

Anything beyond that list must be demonstrated from the revisioned source and tests before being treated as part of the specification.

## Revision note

This specification was reconciled against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

Future changes to instruction coverage, boot protocol, memory map, device addresses, backend availability or exit semantics require either an explicit versioned specification update or preservation of the existing behavior for callers that depend on this revision.
