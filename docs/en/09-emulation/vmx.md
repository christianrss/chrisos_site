---
id: vmx
lang: en
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/Makefile
  - chrisvm/chris_arch.h
  - chrisvm/chrisvm.h
  - chrisvm/machine/machine.c
  - chrisvm/machine/machine.h
  - chrisvm/cpu/hv/chrishv.c
  - chrisvm/cpu/hv/vmx/vmx.h
  - chrisvm/cpu/hv/svm/svm.h
  - chrisvm/tests/test_chrisvm.c
symbols:
  - ChrisCpuBackend
  - ChrisArchitectureState
  - chrishv_backend
  - chris_backend_by_name
depends_on:
  - virtualization-chrishv
  - chris-architecture-state
  - x86-64-memory-privilege
related:
  - svm
  - ept-npt
  - chrisvm-machine
  - determinism-replay
---

# Intel VMX and the future ChrisHV backend

## Scope

Intel Virtual Machine Extensions, usually called VMX or Intel VT-x, add architectural support for running a guest execution context directly on a physical Intel processor while retaining controlled transfer back to a virtual-machine monitor.

VMX does **not** remove the need for a virtual machine.

It accelerates the CPU-execution part of that machine.

A complete VMM still needs:

- guest/host state ownership;
- memory virtualization;
- interrupt routing;
- I/O handling;
- device models;
- timing policy;
- exit dispatch;
- error recovery;
- teardown;
- security boundaries;
- validation.

This chapter separates Intel VMX architecture from the current ChrisOS implementation state.

At ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56, VMX support is not implemented.

The source states this directly in:

    chrisvm/cpu/hv/vmx/vmx.h

and ChrisHV initialization deliberately fails.

Therefore every VMX structure, instruction sequence and design below is architectural theory or an implementation plan unless explicitly identified as current ChrisOS behavior.

## Primary architectural reference

The normative source for VMX behavior is Intel's current Intel 64 and IA-32 Software Developer's Manual, especially the system-programming volumes covering VMX operation, VMCS fields, VM entry, VM exit, EPT, VPID and VMX instructions.

The documentation reviewed for this chapter is Intel SDM version 093, published by Intel in 2026.

Intel's manual, not this chapter, is authoritative for processor-specific requirements and capability bits.

VMX software must always derive supported controls from the processor's capability MSRs instead of assuming that one Intel processor behaves exactly like another.

## Current ChrisOS state

The current ChrisHV source says:

    There is no VMX, no SVM, and no KVM.

The VMX header says:

    Not started.

Selecting:

    --backend=chrishv

reaches chrishv_backend.

Its init callback prints a not-implemented message and returns failure.

The machine constructor then rejects the backend.

The ChrisVM test suite explicitly expects this failure.

This is important evidence.

ChrisOS currently has a backend abstraction for future hardware virtualization, not a partial VMX implementation.

## Host execution model matters

The current ChrisVM Makefile builds the frontend with ordinary host GCC:

    gcc ... -o ../build/chrisvm/chrisvm

The result is a normal host executable.

Direct VMX operation is privileged processor functionality.

A normal user-space process cannot simply execute VMXON and own VMCS/interrupt/memory virtualization directly under a conventional protected host operating system.

Therefore a real ChrisHV implementation must choose an execution architecture.

Credible options include:

1. a privileged ChrisOS/native monitor environment that owns the machine directly;
2. a host kernel module or driver that performs VMX operations on behalf of the ChrisVM frontend;
3. an existing host virtualization API such as Linux KVM;
4. a separate bare-metal hypervisor layer.

The current source explicitly says it does not use /dev/kvm.

That statement describes the present code, not a permanent architectural prohibition.

## Root and non-root operation

VMX introduces two execution modes orthogonal to ordinary x86 privilege rings:

    VMX root operation
    VMX non-root operation

The VMM normally executes in VMX root operation.

The guest normally executes in VMX non-root operation.

This is not equivalent to:

    root = ring 0
    non-root = ring 3

A guest kernel can run at guest CPL 0 while still executing in VMX non-root operation.

A host VMM can run at CPL 0 in VMX root operation.

VMX therefore adds a second control dimension above the guest's own ring model.

## Why VMX is needed

Without hardware virtualization, some guest operations historically could not be allowed to execute directly without compromising host control.

VMX allows the processor to execute guest instructions natively until configured conditions require monitor intervention.

The central control loop becomes:

    configure VMCS
        ↓
    VM entry
        ↓
    guest runs in non-root operation
        ↓
    exit-triggering event
        ↓
    VM exit
        ↓
    VMM inspects exit reason
        ↓
    emulate / update state / inject event
        ↓
    VMRESUME

This is fundamentally different from ChrisCPU, where every guest instruction is decoded and implemented by software.

## Capability detection

A VMM must not attempt VMX initialization merely because it is running on an Intel processor.

At minimum, software must establish that the processor advertises VMX capability through CPUID.

It must then inspect the relevant VMX capability MSRs.

Important classes include:

- IA32_VMX_BASIC;
- VMX control capability MSRs;
- CR0 fixed-bit requirements;
- CR4 fixed-bit requirements;
- EPT/VPID capability information;
- miscellaneous VMX capabilities.

Exact control legality is processor-dependent.

A future ChrisHV must expose capability detection as data, not scatter assumptions throughout setup code.

## IA32_FEATURE_CONTROL

VMX enablement is also affected by IA32_FEATURE_CONTROL.

Firmware commonly configures and locks this MSR.

A platform may support VMX in hardware while firmware policy prevents the intended use.

A robust implementation must distinguish:

- VMX absent;
- VMX present but disabled by firmware policy;
- VMX available for the intended mode;
- VMX already owned or unavailable because of the host environment.

Returning a generic "VMX failed" message would be inadequate for hardware bring-up.

## CR4.VMXE

Before VMXON, software must enable VMX operation through CR4.VMXE and satisfy architectural prerequisites.

CR0 and CR4 must also obey processor-reported fixed-bit constraints.

The usual implementation pattern is conceptually:

    cr0 = (cr0 | fixed0_cr0) & fixed1_cr0
    cr4 = (cr4 | fixed0_cr4) & fixed1_cr4
    cr4 |= VMXE

The actual order and legality must follow Intel's architecture.

The important design rule is that fixed-bit MSRs are authoritative.

Hard-coded control-register masks are unsafe across CPU generations.

## VMXON region

Entering VMX operation requires a VMXON region in physical memory.

The region must satisfy alignment and memory-type requirements reported by the processor.

Intel documents a 4 KiB-aligned region model.

The VMM reads the VMCS revision identifier from IA32_VMX_BASIC and writes the required revision value into the VMXON region before VMXON.

Conceptually:

    allocate VMXON region
    zero/prepare region
    write revision identifier
    obtain physical address
    VMXON [physical-address operand]

Successful VMXON places the logical processor into VMX operation.

It does not launch a guest.

## Per-CPU ownership

VMX operation is associated with a logical processor.

In an SMP host, each logical processor participating in virtualization needs correct per-CPU VMX lifecycle management.

That implies future ChrisHV state such as:

    ChrisHvCpu
        host cpu id
        VMXON region
        current VMCS ownership
        capability cache
        host stack
        exit context

The current ChrisMachine has one ChrisCpu and therefore does not yet solve this host-side per-CPU problem.

Even a single-vCPU guest can migrate between host CPUs unless the implementation pins execution or performs the required VMX lifecycle transitions.

## VMCS

The Virtual-Machine Control Structure, VMCS, defines the execution contract for a VMX guest.

The VMCS is not a C structure whose layout software may directly dereference.

Intel defines VMREAD and VMWRITE as the architectural interface to its fields.

A VMCS contains classes of state including:

- guest-state fields;
- host-state fields;
- VM-execution controls;
- VM-entry controls;
- VM-exit controls;
- VM-exit information;
- fields controlling event injection;
- addresses of optional control structures.

A future ChrisHV should treat VMCS encodings as an architecture interface, not map an invented struct over VMCS memory.

## VMCS region lifecycle

A typical lifecycle is:

    allocate aligned VMCS region
    write VMCS revision identifier
    VMCLEAR
    VMPTRLD
    VMWRITE required controls/state
    VMLAUNCH
    ...
    VMRESUME
    ...
    VMCLEAR before relinquishing ownership

The VMM must also respect active/current VMCS semantics.

VMCS state may be cached internally by the processor.

Correct teardown is therefore an architectural requirement, not merely memory cleanup.

## VMLAUNCH versus VMRESUME

The first entry using a VMCS uses VMLAUNCH.

Subsequent entries use VMRESUME after a successful launch.

Software must track launch state.

Using the wrong instruction is a VM-entry failure condition.

A useful future ChrisHV vCPU structure should make this state explicit:

    enum {
        VMCS_CLEAR,
        VMCS_LOADED,
        VMCS_LAUNCHED
    }

rather than infer it from unrelated fields.

## Guest-state fields

VMCS guest state represents the processor state to be loaded for VM entry and updated on VM exit.

Relevant categories include:

- general execution state;
- control registers;
- segment state;
- descriptor tables;
- RIP;
- RSP;
- RFLAGS;
- selected MSRs;
- interruptibility/activity state;
- paging/long-mode state.

ChrisOS already has:

    ChrisArchitectureState

as the backend-neutral CPU-state contract.

That structure is therefore the natural source/target for VMCS translation.

But it is not yet guaranteed to contain every VMX-required state field.

A VMX implementation must perform a field-by-field gap analysis instead of assuming direct completeness.

## Host-state fields

VM exit transfers control back to a host context described by VMCS host-state fields.

These fields include the host execution state required for safe continuation after an exit.

A direct bare-metal implementation therefore needs a deliberately constructed host context:

- CR3;
- stack;
- entry RIP;
- segment selectors;
- descriptor-table state;
- required MSRs.

This is one reason VMX is not just "execute VMLAUNCH".

The exit path is effectively a low-level context-transfer ABI.

## VM-execution controls

VMX execution controls determine which guest events are allowed to proceed and which cause VM exits.

Examples include controls around:

- I/O;
- MSR access;
- HLT;
- control-register access;
- exceptions;
- external interrupts;
- secondary processor-based controls;
- EPT;
- VPID.

The exact available set depends on the processor.

A ChrisHV implementation should derive controls through a helper similar to:

    adjusted = (desired | allowed0_required) & allowed1

using the correct capability MSR interpretation.

The implementation must then verify that required features remained enabled after adjustment.

## Capability-safe control construction

A dangerous pattern is:

    vmwrite(PIN_BASED_CONTROLS, CONSTANT)

because one CPU may require some bits to be one and reject others.

A safer abstraction is:

    vmx_adjust_controls(msr, desired, required)

which:

1. reads processor capability;
2. forces architecturally required ones;
3. clears unsupported ones;
4. fails if a ChrisHV-required feature cannot be enabled;
5. records the final effective value.

That effective value should be visible in diagnostics.

## I/O interception

VMX can cause guest I/O operations to exit to the monitor.

Fine-grained control can be provided through I/O bitmaps.

This maps naturally to the existing ChrisVM port-I/O device model.

A future flow can be:

    guest IN/OUT
        ↓
    VM exit
        ↓
    decode exit qualification
        ↓
    chris_io_in / chris_io_out
        ↓
    write result/update guest state
        ↓
    advance guest RIP
        ↓
    VMRESUME

This is one of the strongest reasons for keeping ChrisHV beneath ChrisMachine: the device-routing policy already exists independently of the CPU backend.

## MSR interception

VMX can selectively intercept RDMSR and WRMSR operations.

MSR bitmaps allow the VMM to avoid exits for MSRs that can safely execute directly while trapping others.

ChrisCPU currently implements only a limited MSR model.

ChrisHV must not expose arbitrary host MSR state to the guest merely because hardware execution makes that convenient.

The guest-visible MSR contract must remain the virtual CPU contract.

## CPUID

CPUID handling deserves particular care.

ChrisCPU returns a deterministic virtual CPUID identity rather than forwarding the host.

If ChrisHV allows guest CPUID to execute natively without interception, the same VM will expose the physical host CPU instead.

That would break backend equivalence and determinism.

Therefore ChrisHV should intercept CPUID and return the same versioned virtual CPUID policy as ChrisCPU unless the architecture intentionally changes.

## HLT

HLT is a common exit target for simple bring-up.

ChrisCPU currently converts HLT into a VM stop reason.

ChrisHV should define equivalent policy.

Depending on guest interrupt state, a production hypervisor may treat HLT as a blocked/waiting vCPU rather than terminal shutdown.

For current small ChrisVM guests, preserving observable ChrisCPU semantics may be more important than immediately modeling a full scheduler.

## Exceptions

VMX can be configured to exit on selected exceptions or let the guest receive them directly.

The choice affects backend equivalence.

ChrisCPU has an explicit software exception-delivery model.

ChrisHV needs a policy matrix identifying:

- exceptions executed entirely by hardware inside the guest;
- exceptions intercepted for monitor handling;
- exceptions that require synthetic injection;
- terminal monitor failures.

The goal is not to maximize exits.

It is to preserve the declared virtual architecture.

## VM exit

When a configured event occurs, the processor performs VM exit.

The VMCS exposes exit information such as:

- exit reason;
- exit qualification;
- guest linear/physical information for some exits;
- interruption information;
- instruction length where defined.

The monitor dispatch loop is conceptually:

    reason = vmread(EXIT_REASON)

    switch reason:
        CPUID
        I/O
        MSR
        HLT
        exception
        EPT violation
        external interrupt
        ...

Each handler must state whether it:

- modifies guest state;
- advances guest RIP;
- injects an event;
- resumes;
- stops the VM.

## RIP advancement

One of the most common hypervisor bugs is incorrect RIP advancement.

For an intercepted instruction emulated by the monitor, the guest normally needs to resume after that instruction.

For a fault-like condition intended to be delivered to the guest, RIP may need to remain at the faulting instruction.

VMX provides instruction-length information for relevant exits.

ChrisHV should centralize resume semantics rather than let every handler independently guess.

A helper contract could be:

    VMX_ACTION_RESUME_SAME_RIP
    VMX_ACTION_RESUME_NEXT_RIP
    VMX_ACTION_INJECT
    VMX_ACTION_STOP

## VM-entry failure

VMLAUNCH/VMRESUME can fail before guest execution begins.

This is distinct from a normal VM exit.

Failure can arise from invalid controls or invalid host/guest state.

A bring-up implementation needs diagnostics that identify:

- VM-instruction error where available;
- current controls;
- relevant guest-state fields;
- relevant host-state fields;
- capability MSRs;
- VMCS lifecycle state.

"VMLAUNCH failed" is not sufficient.

## Interrupt injection

The VMCS supports event injection for VM entry.

ChrisHV can use this to deliver virtual interrupts and exceptions into the guest.

The existing backend interface already contains:

    inject_irq(cpu, vector)

The software seam therefore exists.

A real implementation must define:

- when an interrupt becomes pending;
- whether the guest is currently interruptible;
- how IF and interruptibility state are respected;
- how pending events survive exits;
- whether interrupt-window exiting is used.

This must match the machine's interrupt-controller model as it evolves.

## External interrupts

A host interrupt arriving while a guest is running is not automatically the same thing as a guest interrupt.

The VMM must distinguish:

    host interrupt
    guest virtual interrupt

A physical device owned by the host may interrupt the VMM.

A virtual device event may need later injection into the guest.

Conflating the two breaks isolation.

## EPT

Extended Page Tables provide Intel's second-level address translation.

With EPT:

    guest virtual
        ↓ guest page tables
    guest physical
        ↓ EPT
    host physical

EPT is large enough to deserve its own chapter.

For VMX design, the key point is that hardware-assisted CPU execution does not eliminate ChrisVM's physical machine model.

EPT determines what host memory backs each guest-physical address.

Device MMIO still needs interception or deliberate mapping.

## EPT violations

An EPT violation is not the same as a guest #PF.

A guest page-table violation belongs to the guest architecture.

An EPT violation indicates second-level translation or access policy.

The hypervisor may use EPT violations for:

- demand mapping;
- MMIO trapping;
- dirty/access tracking;
- copy-on-write;
- protection;
- diagnostics.

ChrisHV must not inject #PF into the guest merely because an EPT violation occurred unless its machine model specifically requires an equivalent guest-visible event.

## VPID

Virtual Processor Identifiers can reduce translation invalidation costs across VM transitions.

Without VPID, conservative TLB invalidation can become expensive.

With VPID, translations can be associated with a virtual processor identity, subject to architecture rules.

A first bring-up implementation can prioritize correctness before VPID optimization.

However, the architecture should avoid baking "flush everything always" into higher-level APIs.

The existing backend method:

    invalidate_tlb

is a useful seam for later mapping to INVVPID/INVEPT policy.

## INVEPT and INVVPID

Once EPT or VPID state changes, stale translations can remain in processor caches.

Intel provides INVEPT and INVVPID operations for defined invalidation scopes.

A future ChrisHV memory subsystem needs an explicit rule:

    update translation structure
        ↓
    publish required ordering
        ↓
    issue appropriate invalidation
        ↓
    resume guest

Skipping invalidation can produce failures that look nondeterministic because stale translations depend on prior execution history.

## Unrestricted guest

Modern VMX implementations may support unrestricted guest mode.

This feature relaxes some historical guest-mode restrictions and is useful when virtualizing startup states.

ChrisVM boot protocol v1 currently starts directly in synthetic long mode.

Therefore unrestricted guest is not required merely to reproduce current ChrisVM guest startup.

It becomes more relevant if ChrisHV later aims to execute firmware, real-mode code or a bootloader transition path.

## VMX preemption timer

Some processors provide a VMX preemption timer.

It can bound guest execution before a forced VM exit.

ChrisCPU currently uses a logical max_steps budget.

These mechanisms are not equivalent.

A hardware timer counts processor-defined timer ticks, not ChrisCPU interpreter steps.

If backend equivalence or deterministic replay requires a logical instruction budget, ChrisHV needs a different accounting strategy, such as performance-counter-assisted control or explicit policy at exit points.

## Determinism

Hardware virtualization introduces nondeterministic sources that the current interpreter largely avoids:

- host scheduling;
- physical interrupt timing;
- variable VM-exit timing;
- host TSC behavior;
- hardware performance differences.

Therefore ChrisHV cannot claim deterministic equivalence merely because the guest instruction stream is the same.

The record/replay model must explicitly control or record external events and time sources.

## TSC virtualization

VMX provides facilities that can virtualize guest TSC behavior.

A stable ChrisHV design should decide whether the guest observes:

- host TSC;
- offset host TSC;
- scaled TSC where supported;
- a synthetic logical time model.

Forwarding host TSC would conflict with ChrisCPU's reproducibility goals.

The virtual CPU contract should choose one semantic model and make both backends conform where practical.

## Host and guest XSAVE/FPU state

ChrisArchitectureState currently reserves XMM storage but ChrisCPU does not implement the full modern extended-state architecture.

A hardware guest can execute many instructions directly unless controls or advertised CPUID prohibit them.

This creates a serious contract rule:

    ChrisHV must not advertise or permit architectural state
    that ChrisVM cannot save, restore or intentionally expose.

Before enabling broader instruction execution, ChrisHV needs a complete policy for FPU/SSE/AVX/XSAVE state or must constrain the guest-visible feature set accordingly.

## Security boundary

VMX is a privilege boundary.

Bugs in VM-exit handling can expose host state or corrupt host memory.

High-risk areas include:

- guest-controlled physical addresses;
- EPT construction;
- VMCS physical addresses;
- MSR loads/stores;
- I/O bitmap addresses;
- malformed exit qualifications;
- unchecked guest lengths;
- host stack corruption;
- state leakage across vCPUs.

All guest-derived values should be treated as untrusted input.

## Physical-address validation

VMX structures contain physical addresses supplied to the processor.

A future implementation must distinguish:

- guest physical address;
- host virtual address;
- host physical address.

These are not interchangeable.

The current ChrisVM emulator often uses host pointers directly because software performs memory routing.

VMX requires a much stricter physical-memory ownership layer.

A direct VMX backend cannot pass arbitrary malloc pointers as physical VMCS/EPT addresses without a mechanism that resolves/pins their host physical backing.

## DMA

EPT virtualizes CPU memory translation.

It does not automatically solve DMA isolation for physical devices.

If ChrisHV later passes hardware devices through to a guest, IOMMU configuration becomes part of the security model.

Current ChrisVM uses software device models, so device passthrough is outside the present scope.

## Error containment

VMX bring-up should be staged.

A safe progression is:

1. detect support only;
2. validate firmware policy;
3. enter and leave VMX operation without a guest;
4. create/clear/load one VMCS;
5. validate host-state exit path;
6. launch a minimal guest that exits immediately;
7. handle HLT;
8. handle CPUID;
9. handle port I/O;
10. add EPT-backed RAM;
11. add controlled MMIO;
12. add interrupt injection;
13. add teardown/recovery tests.

Trying to boot the full ChrisOS kernel first would make failures unnecessarily hard to localize.

## Minimal first guest

A useful first hardware guest is much smaller than ChrisOS.

For example, a guest that:

    CPUID
    OUT test-port
    HLT

can validate:

- VM entry;
- CPUID interception;
- I/O exit;
- guest state update;
- RIP advancement;
- HLT exit;
- VMRESUME;
- teardown.

Only after this path is stable should the implementation add complex paging or devices.

## ChrisArchitectureState bridge

The architectural goal of the existing backend seam is:

    ChrisArchitectureState
        ↕
    ChrisCPU software state
        or
    VMCS guest state

A future pair of functions could conceptually be:

    vmx_import_arch_state(vcpu, state)
    vmx_export_arch_state(vcpu, state)

These functions should be testable separately from VMLAUNCH.

They need exact rules for segment attributes, control registers, MSRs, activity state and unsupported fields.

## Backend-neutral machine behavior

ChrisMachine should remain the owner of:

- virtual RAM policy;
- serial device state;
- framebuffer state;
- I/O routing;
- MMIO routing;
- boot/image policy.

ChrisHV should own:

- host virtualization capability;
- VMX per-CPU state;
- VMCS;
- hardware guest execution;
- exit decoding;
- second-level translation integration.

This division prevents ChrisCPU and ChrisHV from becoming two incompatible virtual platforms.

## KVM as an alternative implementation path

Because current ChrisVM is a user-space host executable, Linux KVM is a practical architectural alternative.

KVM already owns privileged VMX/SVM execution in the host kernel.

A KVM-backed ChrisHV could keep the ChrisVM machine frontend in user space and use KVM ioctls for vCPU execution.

Trade-offs include:

- less direct control over raw VMX bring-up;
- dependence on Linux/KVM;
- easier safe access to hardware virtualization;
- faster implementation of a functional hardware backend.

A direct VMX path is more educational and gives deeper control, but requires a privileged execution environment.

The project should decide this boundary explicitly.

## Direct VMX as a research target

If ChrisOS wants to learn and own VMX itself, a direct backend is still a legitimate research goal.

It should then be framed as a different host architecture from the current ordinary user-space binary.

Possible forms include:

- running the monitor inside ChrisOS ring 0;
- a dedicated privileged Linux driver;
- a small bare-metal monitor.

The current Makefile alone cannot provide the privilege needed for VMXON.

## Validation against ChrisCPU

Once VMX executes guests, the most valuable tests are differential.

For a guest supported by both backends:

    run on ChrisCPU
    capture architectural result

    run on ChrisHV
    capture architectural result

then compare:

- RIP/RSP;
- GPRs;
- RFLAGS;
- control registers;
- virtual CPUID result;
- serial output;
- memory digest;
- exit reason;
- exception behavior.

This does not prove complete correctness, but it provides a powerful project-specific oracle.

## Negative tests

VMX code also needs negative tests.

Examples include:

- VMX unavailable;
- firmware-disabled VMX;
- invalid VMCS revision;
- unsupported desired control;
- invalid guest state;
- invalid host state;
- VM-entry failure;
- EPT misconfiguration;
- repeated init/shutdown;
- cleanup after partial allocation;
- execution on wrong host CPU.

Failure-path coverage is especially important because many VMX bugs occur before the guest executes one instruction.

## Diagnostics

Useful VMX diagnostics should expose:

- CPUID VMX capability;
- IA32_FEATURE_CONTROL state;
- IA32_VMX_BASIC revision/size;
- adjusted pin/primary/secondary controls;
- EPT/VPID capability summary;
- VMCS lifecycle state;
- VM-instruction error;
- exit reason and qualification;
- guest RIP;
- relevant guest linear/physical address;
- host CPU identifier.

These values should be available without requiring ad-hoc printf additions during every bring-up failure.

## Performance model

VMX does not make every guest operation free.

Performance depends strongly on VM-exit frequency.

Frequent exits for:

- I/O;
- CPUID;
- MSRs;
- page faults;
- timers;
- interrupts;

can dominate execution cost.

The design goal is usually to let safe guest operations execute directly and intercept only what the virtual machine must control.

Prematurely minimizing exits before correctness is established, however, makes debugging harder.

## Current source limitations

At the reviewed revision, ChrisOS contains none of the following VMX implementation components:

- CPUID VMX capability probe for ChrisHV;
- FEATURE_CONTROL validation;
- CR4.VMXE setup;
- VMXON allocation/entry;
- VMCS allocation;
- VMCLEAR/VMPTRLD;
- VMREAD/VMWRITE wrappers;
- control-MSR adjustment;
- host-state setup;
- guest-state VMCS translation;
- VMLAUNCH/VMRESUME;
- VM-exit assembly stub;
- exit dispatcher;
- EPT;
- VPID;
- INVEPT/INVVPID;
- interrupt-window handling;
- VMX teardown.

The absence is intentional and visible in the source.

## Implementation priorities for ChrisHV VMX

A reasonable implementation order is:

1. decide privileged host architecture: direct VMX environment versus KVM-like API;
2. add immutable capability discovery and diagnostic reporting;
3. add per-host-CPU VMXON ownership and teardown;
4. implement VMCS-region management;
5. implement control adjustment from capability MSRs;
6. create a minimal host-state/exit trampoline;
7. import/export the smallest valid ChrisArchitectureState subset;
8. launch a minimal guest;
9. implement CPUID, HLT and port-I/O exits;
10. connect existing ChrisVM serial/shutdown I/O;
11. add EPT for RAM;
12. add MMIO trapping;
13. add interrupt injection;
14. add complete failure cleanup;
15. add differential ChrisCPU/ChrisHV tests;
16. only then expand CPU features and performance optimizations.

## Revision note

At revision e05a17fd76333114a3fb5c2452f38ca747d4ac56, Intel VMX is an architectural target for ChrisHV, not an implemented backend. ChrisVM already contains useful seams — ChrisCpuBackend, ChrisArchitectureState and machine-level I/O/MMIO ownership — but the privileged VMX execution layer is absent. Because the current ChrisVM binary is an ordinary host executable, the project must first choose how privileged VMX ownership is provided before VMXON, VMCS management, VM entry/exit, EPT or hardware guest execution can exist.
