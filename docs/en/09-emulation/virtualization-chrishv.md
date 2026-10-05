---
id: virtualization-chrishv
lang: en
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chris_arch.h
  - chrisvm/machine/machine.c
  - chrisvm/cpu/hv/chrishv.c
  - chrisvm/cpu/hv/vmx/vmx.h
  - chrisvm/cpu/hv/svm/svm.h
symbols:
  - chris_backend_by_name
  - chrishv_backend
depends_on:
  - chrisvm-chriscpu
related:
  - chrisvm-machine
  - chrisvm-spec
  - vmx
  - svm
  - ept-npt
  - x86-64-memory-privilege
---

# Hardware virtualization and the ChrisHV boundary

## Scope

ChrisHV is the reserved hardware-assisted CPU backend for ChrisVM.

At the reviewed revision, it does **not** execute Intel VMX, AMD SVM or Linux KVM. Its current implementation is deliberately a refused backend that preserves the future backend interface without pretending that hardware virtualization already works.

This distinction is the foundation of the chapter:

~~~text
implemented today
    |
    +-- ChrisVM machine model
    +-- shared ChrisArchitectureState
    +-- ChrisCpuBackend interface
    +-- ChrisCPU software interpreter
    +-- ChrisHV backend name and vtable
    +-- explicit initialization failure

not implemented today
    |
    +-- VMXON / VMCS
    +-- VMRUN / VMCB
    +-- EPT / NPT
    +-- hardware vCPU execution
    +-- VM-exit dispatch
    +-- hardware interrupt injection
~~~

The VMX, SVM and EPT/NPT chapters describe the external architecture needed by that future work. This page defines how those mechanisms fit into the ChrisOS design and what must remain true at the backend boundary.

## Current source state

`chrishv.c` is intentionally small.

Its leading comment states that the current round only reserves the seam and provides:

- no VMX;
- no SVM;
- no KVM.

`hv_init()` calls a helper that prints:

    chrishv: not implemented (no VMX/SVM in this round)

and returns failure.

The remaining backend operations are inert or return failure.

The VMX and SVM headers also state that their implementations have not started.

This is not an accidental incomplete code path hidden behind a working label. It is an explicit non-capability.

## Backend selection

`chris_backend_by_name()` recognizes two names:

    chriscpu
    chrishv

The existence of both names means the machine layer understands two backend identities.

It does **not** mean both can create a CPU.

During `chris_machine_create()`, the selected backend is initialized before guest RAM and the rest of the machine complete construction. Because ChrisHV initialization fails, machine creation fails rather than silently switching to ChrisCPU.

That fail-closed behavior is important for truthful testing.

## Why silent fallback would be wrong

Suppose a command requested:

    --backend chrishv

and the system quietly ran ChrisCPU instead.

A guest might complete successfully, but the result would prove only interpreter behavior.

The user could incorrectly report:

- VMX works;
- SVM works;
- second-level translation works;
- hardware VM exits work.

Explicit refusal prevents that evidence-class error.

For backend validation, "unavailable" is more correct than "passed using a different backend."

## Interpretation versus hardware virtualization

ChrisCPU executes the guest by software interpretation.

For each guest instruction it performs work such as:

1. translate guest RIP;
2. fetch bytes;
3. decode x86;
4. execute the operation in C;
5. update `ChrisArchitectureState`;
6. model faults, I/O and control transfer.

Hardware virtualization changes the CPU execution mechanism.

The physical processor executes guest instructions directly in a restricted guest mode until configured events transfer control back to the virtual-machine monitor.

The machine model still exists; what changes is who executes ordinary guest instructions.

## Intel VMX execution model

Intel VMX distinguishes VMX root operation and VMX non-root operation.

A hypervisor runs in root operation.

The guest normally executes in non-root operation.

Transitions into guest execution are VM entries. Events configured for interception or architectural conditions can cause VM exits back to the monitor.

A VMCS contains guest state, host state, execution controls and VM-exit information.

A future ChrisHV VMX backend would therefore need to translate between:

    ChrisArchitectureState
        |
        v
    VMCS guest-state fields

and between ChrisVM policy and the relevant VM-execution controls.

The current repository does none of this yet.

## AMD SVM execution model

AMD SVM uses a Virtual Machine Control Block, or VMCB.

The `VMRUN` instruction enters guest execution using that control block.

The VMCB contains guest state and controls describing which guest operations or events should be intercepted.

Conceptually, the ChrisHV mapping is analogous:

    ChrisArchitectureState
        |
        v
       VMCB

but the VMX and SVM control formats are not interchangeable.

A real dual-vendor backend requires vendor-specific implementation beneath the common ChrisVM backend contract.

## Shared state is the portability boundary

The key project decision already exists in `chris_arch.h`.

The source comment requires ChrisCPU and future ChrisHV implementations to share one `ChrisArchitectureState` rather than forking separate architectural models.

That state includes:

- GPRs;
- RIP/RFLAGS;
- control registers;
- segment state;
- descriptor tables;
- EFER and selected MSRs;
- TSC;
- XMM storage;
- CPL.

For hardware execution, some of those fields could remain resident in VMCS/VMCB state while the guest runs.

The backend contract still needs explicit import/export semantics so the rest of ChrisVM can observe a coherent state at exits, resets, debug boundaries and shutdown.

## State synchronization problem

Hardware-assisted execution introduces a problem the interpreter largely avoids.

With ChrisCPU, the authoritative state is the in-memory `ChrisArchitectureState`.

With VMX or SVM, authoritative state may temporarily live in processor virtualization structures.

A backend therefore needs rules for:

- which fields are loaded before entry;
- which fields are read after exit;
- which fields are cached;
- when external machine code can mutate state;
- when a TLB invalidation requires hardware action;
- how debug reads obtain a consistent snapshot.

Without a clear rule, the machine and hardware backend can disagree about guest state.

## VM exits

A VM exit is not automatically an error.

It is a control transfer from hardware guest execution to the monitor.

Possible classes include events such as:

- selected I/O instructions;
- control-register access;
- CPUID depending on controls;
- exceptions or interrupts depending on configuration;
- second-level translation violations;
- HLT;
- privileged virtualization-sensitive operations.

A future ChrisHV dispatcher must convert each configured exit into one of three broad actions:

1. emulate and resume;
2. reflect/inject an event to the guest;
3. terminate or report a machine exit.

The exact policy belongs to the project backend, not merely to the CPU feature.

## Avoiding unnecessary exits

Hardware virtualization is useful partly because ordinary guest instructions can execute without interpreter dispatch.

If ChrisHV configured every common operation to exit, it could preserve semantics but lose much of the performance reason for using hardware virtualization.

Backend design therefore balances:

- observability;
- device emulation needs;
- correctness;
- isolation;
- number of exits.

The performance chapter should eventually measure entry/exit frequency rather than assuming hardware virtualization is automatically fast.

## Guest I/O still needs ChrisVM

Hardware execution does not remove the virtual machine.

A guest instruction such as port output may cause a VM exit.

ChrisHV would then need to route the operation through the same ChrisVM I/O model used by the interpreter.

Likewise, memory-mapped devices still need an ownership and dispatch policy.

Conceptually:

~~~text
guest instruction on hardware CPU
        |
        v
      VM exit
        |
        v
     ChrisHV
        |
        v
ChrisVM I/O or MMIO bus
        |
        v
 virtual device
~~~

This is why ChrisHV belongs beneath ChrisVM rather than replacing it.

## Interrupt injection

The common backend vtable already contains an interrupt-injection operation.

ChrisCPU implements pending-interrupt state in software.

A hardware backend would need to map the same machine-level request into vendor-specific event-injection facilities and honor architectural interruptibility state.

This must preserve guest-visible semantics such as interrupt masking and delivery boundaries.

A simple "write vector then enter guest" model is not sufficient for all x86 states.

## Second-level translation

Normal guest paging translates:

[
GVA ightarrow GPA
]

Hardware virtualization also needs to map guest physical memory onto host physical memory:

[
GPA ightarrow HPA
]

Intel EPT and AMD NPT provide hardware support for that second stage.

Combined:

[
GVA ightarrow GPA ightarrow HPA
]

ChrisCPU currently performs guest translation in software and then accesses the host-backed machine memory model.

A future ChrisHV backend cannot simply pass arbitrary host virtual pointers as guest physical addresses. It needs a defined backing-memory strategy and second-level page tables or an equivalent host virtualization interface.

## Memory ownership

ChrisVM currently owns guest RAM as a host allocation.

A hardware backend would need to pin, map or otherwise expose appropriate backing pages to the virtualization mechanism.

That introduces new lifetime rules:

- backing must remain valid while referenced by EPT/NPT;
- unmapping must invalidate stale translations;
- machine teardown must disable hardware execution before freeing pages;
- shared/device memory needs explicit permissions;
- framebuffer/MMIO regions may require different mappings from ordinary RAM.

These rules do not exist in the current stub because hardware execution is absent.

## Capability detection

A real ChrisHV backend must fail before enabling virtualization when the host CPU or platform cannot support the required mechanism.

For Intel, that implies checking VMX capability and the platform's permitted VMX enable state before entering VMX operation.

For AMD, SVM capability and firmware-disable state must be inspected before `VMRUN` is possible.

The current source performs none of these checks because it intentionally fails earlier.

Future code should distinguish:

- CPU feature absent;
- firmware disabled;
- feature locked/unavailable;
- initialization error;
- runtime VM-entry failure.

Those are different diagnostic classes.

## Privilege and host environment

VMX/SVM setup is privileged.

A userspace process cannot normally execute arbitrary VMXON/VMRUN sequences without an operating-system virtualization interface or privileged execution context.

This is especially important for ChrisVM because the current emulator is a host program.

A future implementation must choose its host model explicitly:

- direct privileged code in a suitable environment;
- an operating-system interface such as KVM;
- another controlled execution layer.

The current comments explicitly state that KVM is not used.

## Direct VMX/SVM versus KVM

These are different engineering paths.

### Direct VMX/SVM

ChrisHV would own:

- capability setup;
- virtualization enablement;
- control structures;
- guest entry;
- exit decoding;
- second-level tables;
- interrupt injection.

### KVM-backed execution

The host kernel would own a substantial portion of hardware virtualization, while ChrisVM would communicate through KVM's API.

The current repository has implemented neither path.

Choosing one later changes the host boundary, testing model and portability assumptions.

## Error cleanup is part of correctness

Virtualization setup acquires state that cannot be abandoned casually.

A future backend must unwind failures in reverse ownership order.

Conceptually:

~~~text
detect capability
  -> enable virtualization
  -> allocate control structure
  -> configure memory virtualization
  -> load guest state
  -> enter guest
~~~

If entry fails, teardown must not leave active control structures, pinned pages or enabled per-CPU virtualization state leaked across machine destruction.

This is especially important when tests repeatedly create and destroy VMs.

## Multi-vCPU implications

ChrisVM currently creates one CPU.

Hardware virtualization eventually makes parallel vCPU execution tempting, but adding more vCPUs changes the machine contract.

It introduces:

- concurrent guest RAM access;
- virtual interrupt routing;
- atomic guest operations;
- AP startup;
- shared device synchronization;
- inter-vCPU invalidation;
- deterministic scheduling challenges.

ChrisHV should not introduce SMP accidentally as a side effect of hardware execution.

Single-vCPU equivalence is the safer first milestone.

## Equivalence with ChrisCPU

The strongest early validation strategy is differential execution.

For a guest supported by both backends:

1. initialize identical machine state;
2. run a bounded workload under ChrisCPU;
3. run the same workload under ChrisHV;
4. compare architectural state;
5. compare memory;
6. compare I/O/device-visible results;
7. compare exit classification.

Exact cycle/TSC behavior may require normalization, but architectural results should agree for the tested subset.

This turns ChrisCPU into a semantic reference instead of discarding it after hardware acceleration arrives.

## Minimum VMX milestone

A truthful first Intel milestone would be much narrower than "ChrisHV works."

For example:

- host capability detected;
- VMX activation succeeds;
- one VMCS is created;
- a minimal 64-bit guest enters;
- guest executes a bounded register-only sequence;
- HLT or selected event exits;
- state is recovered correctly;
- teardown returns host CPU state cleanly.

Only after such a gate exists should the VMX page claim executable support.

## Minimum SVM milestone

A comparable AMD milestone would require:

- SVM capability detected;
- VMCB allocated/configured;
- minimal guest state loaded;
- `VMRUN` enters guest;
- a controlled intercept returns;
- architectural state is recovered;
- teardown is clean.

SVM should not be reported as implemented merely because an empty header exists.

## Security boundary

Hardware virtualization can provide stronger CPU isolation primitives than an interpreter, but it does not automatically make a virtual machine secure.

Security still depends on:

- second-level page permissions;
- exit handlers;
- device emulation;
- host mappings;
- DMA policy;
- interrupt handling;
- validation of guest-provided state.

A bug in a virtual device or memory mapping can still cross the intended boundary.

No such security claim is justified for the current ChrisHV stub.

## Performance model

The primary hardware-virtualization cost is no longer software interpretation of every ordinary instruction.

Instead, important costs include:

- VM entry/exit;
- second-level translation and TLB behavior;
- intercepted I/O;
- event injection;
- device emulation;
- synchronization;
- host scheduler interaction.

A workload with few exits can benefit strongly from direct execution.

A workload causing constant exits can lose much of that advantage.

Performance must therefore be measured from actual backend behavior.

## Current validation evidence

The strongest present evidence for ChrisHV is negative and intentional:

- backend name resolves;
- backend initialization fails;
- the source states VMX/SVM/KVM are absent;
- VMX header says implementation not started;
- SVM header says implementation not started.

That evidence is useful.

It proves that selecting ChrisHV does not silently masquerade as successful hardware acceleration.

## Entry and exit as a transaction

A hardware-backed vCPU run should be treated as a state transaction.

Before entry, ChrisHV must establish the guest state and execution controls that the processor will consume. After exit, it must recover the fields needed by ChrisVM before any machine-level observer assumes that `ChrisArchitectureState` is current.

Conceptually:

~~~text
machine state
    -> backend import
    -> hardware control state
    -> VM entry
    -> guest execution
    -> VM exit
    -> backend export
    -> coherent machine state
~~~

The transaction must also define what happens when entry itself fails. In that case there is no valid guest execution interval, but partially prepared backend resources may still require cleanup.

This model avoids an ambiguous middle state in which some registers live in `ChrisArchitectureState` while others have already changed in VMCS/VMCB state.

## Backend observability

Hardware acceleration should not make failures less diagnosable than the interpreter.

A future ChrisHV implementation should expose structured diagnostics for at least:

- capability detection;
- virtualization-enable failure;
- control-structure validation failure;
- VM-entry failure;
- VM-exit reason;
- second-level translation violation;
- event-injection failure;
- teardown failure.

The diagnostic must identify the backend and stage without leaking host-privileged state unnecessarily.

For equivalence testing, the project should also preserve a bounded trace around the final entry/exit boundary when practical. The goal is not to log every native guest instruction, but to make backend transitions attributable to a specific machine state and exit reason.

## Current limitations

At revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, ChrisHV lacks:

- VMX initialization;
- SVM initialization;
- KVM integration;
- VMCS/VMCB allocation;
- VM entry;
- VM exit handling;
- EPT/NPT;
- hardware event injection;
- hardware vCPU lifecycle;
- state synchronization;
- hardware-backend tests;
- SMP hardware execution.

Every item above is future work.

## Roadmap sequence

A defensible implementation order is:

1. capability detection and diagnostics;
2. one vendor, one CPU, no devices beyond existing simple machine state;
3. control-structure lifecycle;
4. minimal guest entry/exit;
5. state import/export;
6. second-level memory translation;
7. port-I/O and MMIO exits;
8. event injection;
9. differential tests against ChrisCPU;
10. broader devices;
11. SMP only after single-vCPU semantics are stable;
12. second vendor backend.

The sequence minimizes simultaneous unknowns.

## Architectural invariant

ChrisHV should preserve this invariant:

> CPU execution backend may change, but the guest-visible ChrisVM machine contract must not change merely because execution moved from interpretation to hardware virtualization.

That means backend choice should not silently alter:

- RAM layout;
- boot protocol;
- device addresses;
- serial behavior;
- framebuffer contract;
- machine exit semantics.

Vendor-specific details belong below the backend interface.

## Revision note

This chapter was reconciled against ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56` and against current Intel VMX and AMD SVM architectural documentation.

The implementation claim is deliberately narrow: **ChrisHV is a reserved, fail-closed backend seam. Hardware-assisted execution is not implemented.**
