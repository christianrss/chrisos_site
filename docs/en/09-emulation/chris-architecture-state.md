---
id: chris-architecture-state
lang: en
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chris_arch.h
  - chrisvm/chrisvm.h
  - chrisvm/machine/machine.c
  - chrisvm/machine/boot.c
  - chrisvm/cpu/common/state.c
  - chrisvm/cpu/emulator/chriscpu.c
  - chrisvm/cpu/emulator/execute.c
  - chrisvm/cpu/emulator/mmu.c
  - chrisvm/cpu/hv/chrishv.c
symbols:
  - ChrisArchitectureState
  - ChrisSeg
  - ChrisDtr
  - ChrisCpuBackend
  - chris_arch_reset
  - cpu_get
  - cpu_set
  - chris_boot
depends_on:
  - chrisvm-chriscpu
  - emulator-paging
  - x86-registers-flags
related:
  - chrisvm-machine
  - determinism-replay
  - virtualization-chrishv
---

# ChrisArchitectureState: the shared CPU-state contract

## Purpose

ChrisArchitectureState is the central architectural-state record used by ChrisVM. It is the project boundary between the guest-visible x86-64 machine state and whichever CPU backend executes that state.

The source states this design requirement directly: ChrisCPU executes the structure today, while a future ChrisHV backend is intended to import and export the same logical state through hardware virtualization structures such as VMCS or VMCB. The goal is to avoid creating one architectural model for the interpreter and a second, subtly different model for hardware-assisted execution.

This is an important separation:

- ChrisArchitectureState describes guest architectural state;
- ChrisCpu contains backend/runtime control state;
- ChrisMachine owns RAM, devices, configuration and the selected backend.

Those three layers overlap in execution, but they are not interchangeable.

This chapter documents the state contract at ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.

## Structure overview

The current state groups the following categories:

| Category | Fields |
|---|---|
| general-purpose registers | gpr[16], with named aliases rax through r15 |
| control flow | rip, rflags |
| control registers | cr0, cr2, cr3, cr4, cr8 |
| segment state | cs, ds, es, fs, gs, ss |
| system segments | tr, ldtr |
| descriptor tables | gdtr, idtr |
| extended control/MSR state | efer, star, lstar, cstar, fmask |
| base MSRs | fs_base, gs_base, kernel_gs_base |
| interrupt-controller-related state | apic_base |
| time-like state | tsc |
| SIMD storage | xmm[16][16] |
| privilege state | cpl |

The structure intentionally contains more state than the current interpreter actively uses. That makes it a forward-looking contract, but it also means field presence must not be confused with implemented instruction semantics.

## General-purpose registers

The first field is a union exposing the sixteen 64-bit general-purpose registers in two forms.

The indexed form is:

    gpr[0] ... gpr[15]

The named form is:

    rax rcx rdx rbx rsp rbp rsi rdi
    r8  r9  r10 r11 r12 r13 r14 r15

The project defines constants for the first eight register indices, beginning with CHRIS_GPR_RAX equal to zero and CHRIS_GPR_RSP equal to four. Decoder and operand helpers use register numbers directly, while machine-facing APIs such as chris_get_gpr and chris_set_gpr also expose indexed access.

Because the array and named members occupy the same union storage, updating one view updates the other. This avoids synchronizing duplicate copies of GPR state.

The register-order contract is therefore significant. A future backend importing VMCS/VMCB or host-register state must preserve this exact logical mapping even if its internal storage is different.

## RIP and RFLAGS

rip is the current guest instruction pointer.

In the interpreter loop, instruction fetch begins at arch.rip. Most instructions do not write RIP directly; after execution the generic loop adds the decoded instruction length unless rip_dirty was set by a control-flow operation.

Instructions such as JMP, CALL, Jcc, INT, IRETQ and HLT can manipulate RIP through dedicated execution paths.

rflags stores the modeled x86 flags word. The reset helper establishes the project invariant that bit 1 is set:

    RFLAGS = 2

Arithmetic helpers update only selected status bits. Other paths manipulate IF, DF, TF, RF and VM where implemented.

RFLAGS is therefore not just an ALU result register. It is shared by arithmetic, conditional execution, interrupts, string operations and exception delivery.

## Reset state

chris_arch_reset performs two operations:

1. zero the entire ChrisArchitectureState;
2. set:
   - RFLAGS to 2;
   - CR0 to PE | NE.

This is a minimal project reset state, not a complete model of architectural x86 reset.

It does not place the processor in the real hardware reset vector state, does not emulate 16-bit real mode startup, and does not initialize firmware-visible platform state.

ChrisVM boot protocol v1 builds a synthetic long-mode starting state on top of this reset record.

## Boot-time state construction

chris_boot creates a local ChrisArchitectureState and calls chris_arch_reset.

install_tables then augments it with the boot protocol's long-mode state:

- CR0 receives PE, NE, WP and PG;
- CR3 points to the generated PML4;
- CR4 receives PAE;
- EFER receives LME and LMA;
- GDTR points to the generated GDT;
- CS is initialized as the long-mode code segment;
- SS, DS and ES are initialized from the data descriptor;
- RFLAGS is forced to 2;
- CPL is set to zero.

chris_boot then sets:

- RIP to the guest entry point;
- RSP to the selected stack address.

Finally, the complete state is passed through:

    backend->set_state(cpu, &st)

This is one of the most important uses of the backend abstraction in the current code. Boot does not need to know whether the backend stores the architectural state as a C structure, a VMCS/VMCB mapping or another internal representation.

## ChrisCPU state import/export

The ChrisCPU backend implements state transfer in the simplest possible way.

cpu_get performs:

    *out = cpu->arch

cpu_set performs:

    cpu->arch = *in

The complete structure is copied by value.

This gives the interpreter exact field-for-field import/export semantics for the current compiler build. It also means no validation, normalization or side effects occur during state import.

For example, cpu_set does not:

- validate CR0/CR4 combinations;
- validate canonical RIP;
- verify segment descriptors;
- recalculate CPL from CS;
- invalidate translation state;
- normalize reserved RFLAGS bits;
- reconcile duplicated segment/base state.

That behavior is acceptable for the current controlled boot path, but it is an important contract boundary for future migration, snapshot restore and debugger state injection.

## The backend interface

ChrisCpuBackend defines the execution seam:

- init;
- create_cpu;
- reset;
- run;
- inject_irq;
- get_state;
- set_state;
- invalidate_tlb;
- shutdown.

get_state and set_state are the architectural bridge. They are the functions that should make the rest of ChrisVM independent of the backend's internal CPU-state representation.

ChrisCPU currently stores ChrisArchitectureState directly inside ChrisCpu. A real ChrisHV backend would likely have to translate at least part of that state into hardware virtualization control structures and possibly host-side shadow state.

The logical state contract should remain stable even if the physical storage changes.

## ChrisHV is only a reserved seam today

The current chrishv.c explicitly states that hardware virtualization is not implemented in this revision.

hv_init fails. As a result, chris_machine_create rejects the chrishv backend before a usable CPU instance is created.

The remaining ChrisHV callbacks are stubs, including hv_get and hv_set.

Therefore ChrisArchitectureState is currently a shared architectural design contract, but only ChrisCPU provides a functioning implementation of state import/export.

Documentation must not describe VMCS/VMCB synchronization as implemented behavior yet.

## Control registers

The state stores CR0, CR2, CR3, CR4 and CR8.

### CR0

The current interpreter uses selected CR0 bits including:

- PE;
- NE;
- WP;
- PG.

WP and PG directly affect MMU behavior.

### CR2

CR2 receives the faulting virtual address for modeled page faults and some monitor-unmapped diagnostics.

### CR3

CR3 identifies the PML4 root used by the four-level page walker.

The MMU masks its low twelve bits and does not implement PCID semantics.

### CR4

The boot path currently establishes PAE. Other modern CR4 features are not broadly modeled.

### CR8

CR8 exists in the state, MOV-CR access path and public machine getter/setter.

The inspected implementation does not yet connect CR8 to a modeled local-APIC task-priority mechanism. Its presence therefore represents architectural storage ahead of complete interrupt-priority semantics.

## Segment state

ChrisSeg contains:

- selector;
- base;
- limit;
- attributes.

ChrisArchitectureState stores ordinary segments:

- CS;
- DS;
- ES;
- FS;
- GS;
- SS;

and system-segment-style records:

- TR;
- LDTR.

The segment structure represents both the visible selector and cached descriptor-derived state. That is useful because real x86 segment registers have hidden descriptor-cache state in addition to the selector value.

However, the current implementation does not provide complete segment loading or privilege semantics for every field.

CS has a dedicated loading helper used by exception delivery. DS/ES/FS/GS/SS, TR and LDTR do not yet have equivalent complete architectural state-transition machinery.

Field existence therefore must not be interpreted as full segmentation compatibility.

## GDTR and IDTR

ChrisDtr stores:

- base;
- limit.

gdtr and idtr use that representation.

The current executor implements a subset of SGDT, SIDT, LGDT and LIDT, and exception delivery uses IDTR while code-segment loading uses GDTR.

Unlike the segment structure, a descriptor-table register needs only the architecturally visible base and limit in this model.

The state does not store a predecoded descriptor cache for the complete GDT/IDT; descriptors remain in guest memory.

## EFER

The state includes EFER and defines project constants for:

- SCE;
- LME;
- LMA;
- NXE.

The boot protocol sets LME and LMA.

The MMU consumes NXE when deciding whether the high NX bit in paging entries forbids instruction execution.

SCE exists as a defined state bit, but the inspected decoder/executor does not implement a SYSCALL/SYSRET instruction path in this revision.

This is an example of the distinction between state storage and instruction support.

## STAR, LSTAR, CSTAR and FMASK

The state stores the syscall-related MSRs:

- STAR;
- LSTAR;
- CSTAR;
- FMASK.

RDMSR and WRMSR can access these modeled slots.

However, without implemented SYSCALL/SYSRET execution, these MSRs currently behave primarily as stored architectural state rather than active control-flow configuration.

A future syscall implementation should consume them through the same state record rather than creating separate backend-specific fields.

## FS_BASE, GS_BASE and KERNEL_GS_BASE

The state contains explicit MSR-backed bases:

- fs_base;
- gs_base;
- kernel_gs_base.

RDMSR/WRMSR can access them.

At the same time, the state also contains ChrisSeg fs and gs, each with its own base field.

That means the representation currently permits values such as:

    fs.base != fs_base

Nothing in cpu_set reconciles those fields automatically.

The current decoder also discards segment-override identity and the execution path does not provide general FS/GS-relative addressing semantics.

Therefore this duplication is not yet an active consistency problem for broad guest execution, but it is a future state-model issue that must be resolved before FS/GS addressing and SWAPGS-style semantics become complete.

## APIC base

apic_base models MSR IA32_APIC_BASE storage.

RDMSR/WRMSR can access it.

The current ChrisVM platform does not yet have a mature APIC/IOAPIC/SMP implementation tied to the field. As with CR8, the state slot exists ahead of complete platform semantics.

## TSC

tsc is stored inside ChrisArchitectureState and therefore treated as part of guest architectural state.

The ChrisCPU run loop increments it once for each interpreted instruction:

    cpu->arch.tsc++

This makes the counter deterministic with respect to interpreter retirement count, but it is not a model of real processor cycles, wall-clock time or actual hardware TSC frequency.

The current x86 decoder does not implement a guest RDTSC instruction path. The field therefore advances internally even though general guest code cannot yet read it through RDTSC.

For deterministic replay this distinction is important: the current TSC is a logical instruction counter-like architectural value, not a timing simulator.

## XMM storage

The state reserves:

    xmm[16][16]

That is sixteen 128-bit storage slots corresponding structurally to XMM0 through XMM15.

In the inspected ChrisCPU decoder/executor, broad SSE/AVX instruction decoding is not implemented. Search results show no ChrisVM execution path consuming this state.

The storage is therefore a reserved architectural slot, not evidence of working SIMD emulation.

When SIMD execution is added, the project will also need to decide whether MXCSR and wider YMM/ZMM state belong in the same state contract.

## CPL

The structure stores cpl as a separate integer.

The MMU uses:

    cpl == 3

to classify user-mode memory accesses.

Boot initializes cpl to zero.

This is operationally simple, but it allows cpl to diverge from CS selector privilege information because no invariant currently forces:

    cpl == (cs.sel & 3)

chris_seg_load_cs updates CS but does not update cpl in the inspected implementation.

That creates a concrete state-consistency boundary. Future privilege transitions must define whether CPL is derived state, authoritative state, or validated redundant state.

Keeping both independently mutable without reconciliation would make paging permission checks disagree with code-segment privilege state.

## Architectural state versus runtime control state

Not every CPU-related field belongs in ChrisArchitectureState.

ChrisCpu separately stores runtime/emulator state such as:

- steps;
- halted;
- exit_reason;
- exception diagnostics;
- delivering;
- pending IRQ and vector;
- sti_delay;
- rip_dirty;
- tlb_gen;
- tracing configuration;
- breakpoint state;
- trace ring.

Those fields affect execution but are not all guest-visible architectural registers.

This separation is conceptually correct. However, it has an important consequence: copying only ChrisArchitectureState is not sufficient for a bit-exact emulator continuation snapshot.

For example, restoring architectural state without restoring a pending IRQ, STI delay or partially relevant monitor condition can change subsequent execution.

That issue belongs directly to future determinism/replay and migration design.

## Machine state is separate again

ChrisMachine owns platform state outside the CPU:

- RAM;
- I/O registrations;
- MMIO registrations;
- serial state;
- framebuffer;
- backend pointer;
- loaded entry point;
- boot/shutdown state;
- configuration.

A complete VM snapshot would need to combine:

    architectural CPU state
    + backend runtime state
    + machine/device state
    + memory

ChrisArchitectureState intentionally covers only the first category.

## A current abstraction leak in the public API

Although ChrisCpuBackend defines get_state and set_state, several machine-facing helper functions access the interpreter's internal structure directly.

Examples in machine.c include:

- chris_set_gpr;
- chris_get_gpr;
- chris_get_rip;
- chris_get_rflags;
- chris_get_cr;
- chris_set_cr.

They read or write:

    m->cpu->arch

instead of calling backend->get_state or backend->set_state.

This works because ChrisCPU currently stores its architectural state exactly there.

It would not automatically work for a future ChrisHV backend whose authoritative state lives in VMCS/VMCB or another backend representation.

This is a concrete layering gap.

A backend-neutral public API should route architectural reads and writes through the backend state contract, or define a synchronization rule that guarantees cpu->arch is always an authoritative shadow.

## Direct state mutation has no validation side effects

The same public setters directly modify state without architecture-specific side effects.

For example, chris_set_cr can change CR3 directly.

It does not:

- invalidate a future TLB;
- validate control-register combinations;
- flush translations;
- check canonicality implications;
- update dependent backend control fields.

Because the current MMU has no TLB, direct CR3 mutation becomes visible immediately and does not currently create stale translations.

That accidental safety will disappear if a TLB is introduced.

The state API therefore needs a distinction between:

- raw snapshot import;
- architecturally executed register writes;
- debugger-forced state mutation.

Those operations should not necessarily have identical side effects.

## Struct layout is not a serialization ABI

ChrisArchitectureState is a C structure containing unions, nested structures, arrays and an int field.

Its logical fields form an architectural contract, but its in-memory byte layout should not automatically be treated as a durable file or network format.

Potential problems include:

- compiler padding;
- alignment differences;
- ABI differences;
- endianness;
- future field insertion;
- width assumptions for int;
- version evolution.

A stable snapshot or migration format should serialize named fields explicitly and include a version/schema identifier.

Using raw sizeof(ChrisArchitectureState) bytes as a long-lived snapshot format would couple saved images to one compiler ABI and source revision.

## State import needs normalization rules

A future robust set_state contract should define what happens when input state is inconsistent or architecturally invalid.

Examples include:

- RFLAGS bit 1 clear;
- noncanonical RIP;
- CR0.PG enabled without required paging mode prerequisites;
- EFER.LMA inconsistent with other control state;
- CPL inconsistent with CS privilege;
- segment selector inconsistent with cached descriptor attributes;
- FS/GS segment base inconsistent with base MSRs;
- CR3 with unsupported PCID bits;
- XMM state without associated MXCSR semantics.

The current cpu_set intentionally performs none of these checks.

That makes it a raw state transfer primitive, not an architectural validation boundary.

## Testing evidence

The current ChrisVM tests exercise many fields indirectly:

- GPR getters after instruction execution;
- RFLAGS after ALU operations;
- CR2 after page fault;
- CR/MSR behavior;
- RIP progression through control flow;
- boot initialization;
- paging permissions;
- exception state;
- TSC increment inside the interpreter loop.

The tests also verify that selecting the chrishv backend is currently rejected.

However, the inspected suite does not provide a dedicated round-trip test that:

1. populates every ChrisArchitectureState field;
2. calls backend set_state;
3. calls backend get_state;
4. compares every logical field.

Such a test would be valuable before ChrisHV begins implementing real state translation.

## Hardening priorities

The highest-value next work for the state contract is:

1. add a complete backend-neutral state round-trip test for every field;
2. route public architectural getters/setters through get_state/set_state or define an authoritative shadow-state contract;
3. distinguish raw state restore from architecturally executed register writes;
4. define normalization and validation rules for imported state;
5. make CPL consistency with CS explicit;
6. define the canonical relationship among FS/GS cached bases and FS_BASE/GS_BASE MSRs;
7. version a stable serialization format instead of dumping the C structure;
8. separate deterministic logical TSC behavior from future real-time or hardware-assisted TSC virtualization;
9. add MXCSR and wider vector state only when the execution model actually supports them;
10. define which runtime fields outside ChrisArchitectureState must accompany snapshots and migration;
11. ensure future CR3/CR0/CR4 mutations trigger the required translation invalidation behavior;
12. make ChrisHV state import/export tests share the same logical fixtures as ChrisCPU.

## Revision note

At revision e05a17fd76333114a3fb5c2452f38ca747d4ac56, ChrisArchitectureState is a coherent shared logical register-state model and ChrisCPU implements full-structure copy import/export. The design is a strong backend seam, but several surrounding APIs still assume the interpreter's in-memory cpu->arch layout directly. ChrisHV remains a stub, state import is unvalidated, CPL and segment privilege can diverge, and the structure is not yet suitable as a durable serialization ABI. Those boundaries should be resolved before hardware virtualization, migration or deterministic snapshot/replay rely on the state contract.
