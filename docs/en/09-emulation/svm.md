---
id: svm
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
  - vmx
  - ept-npt
  - chrisvm-machine
  - determinism-replay
---

# AMD SVM and the future ChrisHV backend

## Scope

AMD Secure Virtual Machine, normally referred to as SVM or AMD-V, provides hardware support for running guest software directly on an AMD64 processor while allowing a virtual-machine monitor to intercept selected operations and preserve isolation.

SVM solves the same broad problem as Intel VMX, but its control structures, instructions and lifecycle are different.

For ChrisHV, SVM should therefore be a sibling backend implementation under the same machine and architectural-state contracts, not a set of VMX wrappers renamed for AMD.

At ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56, SVM is not implemented.

The source states:

    AMD SVM backend for ChrisHV.
    Not started. VMX comes first, on the ISA of the development machine.

This chapter documents the AMD architecture relevant to a future ChrisHV backend while keeping the implementation boundary explicit.

## Primary architectural reference

The normative source is AMD64 Architecture Programmer's Manual, Volume 2: System Programming, chapter 15, Secure Virtual Machine.

The revision reviewed for this chapter is AMD publication 24593, revision 3.44, March 2026.

That manual is authoritative for:

- SVM feature discovery;
- VMCB layout;
- intercept semantics;
- VMRUN;
- VMLOAD/VMSAVE;
- nested paging;
- ASID/TLB behavior;
- interrupt virtualization;
- newer SVM capability extensions.

A ChrisHV implementation must inspect processor-reported capabilities instead of assuming every AMD64 CPU supports the same SVM extensions.

## Current ChrisOS state

Current ChrisHV initialization fails before reaching any vendor-specific virtualization path.

The SVM header contains no structures or executable implementation.

There is currently no:

- SVM CPUID probe;
- EFER.SVME setup;
- VM_HSAVE_PA ownership;
- VMCB definition;
- VMRUN wrapper;
- #VMEXIT dispatcher;
- nested paging;
- ASID allocator;
- TLB-control implementation;
- event injection;
- AVIC;
- SEV integration.

Therefore SVM is an architectural target only.

## SVM versus VMX

VMX and SVM should not be treated as instruction-for-instruction equivalents.

Conceptually both provide:

    guest state
    execution controls
    entry into guest
    exit to monitor
    second-level translation
    event injection
    TLB-management support

But their concrete mechanisms differ.

Intel centers the design around VMXON state plus a VMCS accessed through VMREAD/VMWRITE.

AMD centers SVM around a memory-resident Virtual Machine Control Block, VMCB, consumed by VMRUN.

The ChrisHV backend abstraction should normalize behavior at the machine boundary, not hide every hardware difference internally.

## Feature discovery

AMD exposes SVM capability through extended CPUID leaves.

A future backend should determine at least:

- whether SVM is present;
- the supported SVM feature set;
- ASID capacity;
- nested-paging capability;
- optional interrupt-virtualization features;
- optional clean-bit and decode-assist behavior;
- any feature required by the selected ChrisHV mode.

Capability discovery should produce a stable internal structure such as:

    ChrisSvmCaps

rather than repeated CPUID tests spread throughout runtime code.

## EFER.SVME

SVM execution requires enabling the Secure Virtual Machine Enable bit in EFER.

Conceptually:

    read EFER
    set SVME
    write EFER

This is privileged state.

As with direct VMX, an ordinary user-space ChrisVM process under a conventional host OS cannot simply take ownership of SVM hardware.

The project therefore needs the same privileged-host decision described for VMX:

- direct execution in a privileged ChrisOS/bare-metal environment;
- a host kernel component;
- or a virtualization API such as KVM.

## VM_HSAVE_PA

Before executing guest transitions, SVM uses VM_HSAVE_PA to identify a host-save area in physical memory.

The monitor provides a properly allocated physical page and writes its address to the corresponding MSR.

The processor uses this area as part of the host-state world-switch mechanism.

This is host-global/per-logical-processor virtualization state, not guest RAM.

A future ChrisHV implementation must make ownership explicit and pair allocation with teardown.

## VMCB

The Virtual Machine Control Block is the central SVM data structure.

Unlike VMCS, the VMCB has an architecturally defined memory layout that software reads and writes directly.

It contains two major conceptual areas:

- control area;
- state-save area.

The control area describes interception and virtualization policy.

The state-save area represents guest architectural state.

A future ChrisSvmVcpu can therefore own one VMCB plus related host metadata.

## VMCB alignment and physical ownership

VMRUN identifies a VMCB by physical address.

This means ChrisHV must distinguish:

- host virtual pointer used by C;
- host physical address consumed by the CPU;
- guest physical addresses stored inside guest state.

A malloc pointer is not automatically a valid VMCB physical address.

A direct SVM implementation needs pinned/owned physically addressable memory and an explicit translation from host virtual mapping to host physical address.

## Control area

The VMCB control area contains virtualization policy such as:

- instruction intercepts;
- exception intercepts;
- I/O permission-map base;
- MSR permission-map base;
- ASID;
- TLB-control request;
- virtual interrupt controls;
- nested-paging controls;
- event injection;
- exit information;
- clean bits;
- optional feature-specific fields.

This area should be modeled as processor-facing state.

Higher-level ChrisHV policy should not manipulate offsets throughout unrelated code.

## State-save area

The state-save area contains guest state used by world switches.

Relevant categories include:

- segment registers and attributes;
- descriptor tables;
- control registers;
- EFER;
- RIP;
- RSP;
- RFLAGS;
- RAX;
- selected MSRs and system state.

ChrisArchitectureState is the natural backend-neutral bridge.

However, the mapping is not necessarily one-to-one.

The SVM implementation must define explicit import/export rules and document any state that ChrisArchitectureState currently lacks.

## VMRUN

VMRUN performs the central host-to-guest transition.

The monitor provides the physical VMCB address according to AMD's calling convention and executes VMRUN.

The processor:

- saves required host state;
- loads guest state and controls from the VMCB;
- executes the guest;
- exits back to the monitor when an intercepted or exit-generating event occurs;
- updates VMCB exit/state fields.

The exact world-switch contract is defined by AMD architecture and must be implemented in privileged low-level code.

## World-switch wrapper

A production-quality backend should not scatter raw VMRUN inline assembly through C code.

A narrow architecture wrapper should own:

- host callee-saved state;
- VMRUN invocation;
- return path;
- host stack assumptions;
- required clobbers;
- error/exit capture.

That wrapper forms an ABI between generic ChrisHV C code and the SVM world switch.

## VMLOAD and VMSAVE

SVM provides VMLOAD and VMSAVE for selected architectural state associated with a VMCB.

Their role is distinct from simply copying the VMCB in software.

A future backend needs a deliberate rule describing which state is:

- loaded by VMRUN;
- loaded/saved through VMLOAD/VMSAVE;
- maintained explicitly by software;
- represented in ChrisArchitectureState.

Guessing this boundary can produce state leakage or incorrect resume behavior.

## Intercepts

SVM lets the monitor configure interception of selected instructions, exceptions and events.

Examples relevant to ChrisHV include:

- CPUID;
- HLT;
- I/O;
- MSR access;
- control-register operations;
- selected exceptions;
- external-interrupt handling modes.

The initial bring-up should intercept more rather than less.

Once semantics are proven, unnecessary intercepts can be removed for performance.

## CPUID interception

ChrisCPU exposes a fixed virtual CPUID identity.

A hardware SVM guest executing native CPUID without interception would expose the host AMD processor.

That would immediately break backend equivalence.

Therefore ChrisHV should intercept CPUID and feed the same versioned virtual CPU policy used by ChrisCPU, or explicitly define a new virtual CPU model shared by both backends.

## I/O interception

SVM supports I/O interception with an I/O permission map.

This maps cleanly to the existing ChrisVM I/O bus.

The expected future flow is:

    guest IN/OUT
        ↓
    #VMEXIT
        ↓
    inspect exit information
        ↓
    chris_io_in / chris_io_out
        ↓
    update guest result
        ↓
    advance guest RIP correctly
        ↓
    VMRUN

This reuse should prevent serial/shutdown device semantics from being duplicated inside ChrisHV.

## MSR interception

SVM supports an MSR permission map.

ChrisHV should use it to preserve the guest-visible virtual MSR contract.

Allowing arbitrary host MSRs through natively would expose host-specific state and may create a security boundary failure.

The long-term design should classify MSRs into:

- emulated/intercepted;
- virtualized through hardware support;
- intentionally unsupported;
- safe passthrough only if explicitly part of the virtual CPU model.

## #VMEXIT

SVM returns control to the VMM through #VMEXIT semantics and writes exit information into the VMCB.

The control area contains fields identifying the reason and additional exit data.

A dispatcher can be structured around:

    exit_code
    exit_info1
    exit_info2
    exit_int_info
    decode assists where available

Handlers then decide whether to:

- emulate;
- inject an event;
- change mappings;
- resume;
- stop the virtual machine.

## Decode assist

Some SVM processors provide decode-assist information that reduces the amount of instruction decoding the VMM must perform for selected exits.

A future backend should use capability detection before relying on these fields.

The implementation must remain correct when an optional assist is unavailable.

ChrisCPU already contains an x86 decoder, which may provide a useful fallback for some emulation paths, but hardware-exit metadata and software decoder semantics must be reconciled carefully.

## RIP advancement

As with VMX, incorrect RIP advancement is a major source of hypervisor bugs.

Some exits correspond to an instruction that the VMM emulates and then skips.

Other exits represent conditions that must be reinjected without advancing the guest.

The SVM backend should expose explicit resume actions rather than modifying RIP ad hoc in each handler.

## Nested paging

AMD nested paging provides second-level translation.

The conceptual path is:

    guest virtual
        ↓ guest page tables
    guest physical
        ↓ nested page tables
    system physical

This is AMD's counterpart to Intel EPT.

Nested paging is covered more deeply in the EPT/NPT chapter.

For SVM design, the key point is that the guest can retain its own CR3/page-table model while ChrisHV controls the translation from guest physical memory into host/system physical memory.

## Nested page faults

Nested-page translation failures are hypervisor-level events, not ordinary guest page faults.

ChrisHV may use them for:

- MMIO trapping;
- lazy population;
- access control;
- dirty tracking;
- copy-on-write;
- diagnostics.

The backend must distinguish a guest #PF from a nested-page fault and avoid incorrectly exposing second-level failures as guest first-level paging faults.

## nCR3

Nested paging requires a root for the nested translation hierarchy.

The VMCB provides the relevant nested-paging state, including the nested CR3/root.

That root is host-owned virtualization metadata.

It is not the guest's CR3 and must not be exposed as such through ChrisArchitectureState.

## ASIDs

SVM tags translations with Address Space Identifiers.

ASIDs reduce the need to flush TLB state on every world switch.

The VMM can assign different ASIDs to guest address spaces or nested translation contexts according to AMD's rules.

A future ChrisHV should have an ASID allocator with:

- reserved invalid value handling;
- rollover policy;
- generation tracking;
- flush behavior;
- per-host-CPU ownership where required.

## TLB control

AMD specifies explicit TLB-control behavior in the VMCB.

Changing guest paging or nested-paging state does not imply that every stale translation is automatically removed.

The VMM is responsible for requesting appropriate invalidation.

The existing backend method:

    invalidate_tlb

is a natural generic seam, but SVM-specific behavior must account for ASID and nested-page context.

## INVLPGA

AMD provides INVLPGA for invalidating translations associated with an address/ASID context.

A mature backend may use targeted invalidation rather than global flushing.

Correctness comes first.

An initial implementation can use conservative invalidation as long as the architecture permits it and the cost is acceptable.

## Clean bits

SVM VMCB clean bits let software tell the processor which groups of VMCB state did not change since the previous run.

This can reduce reprocessing overhead.

Clean bits are an optimization contract, not merely cache hints with no correctness implications.

If software modifies a covered field but incorrectly leaves the corresponding clean indication set, the processor may use stale internal state.

Therefore early bring-up should favor conservative dirtying until state ownership is proven.

## Fields not covered by clean bits

AMD explicitly documents some VMCB fields that are not represented by clean bits, including runtime/exit-sensitive state.

This is important for backend design because "VMCB unchanged" cannot be represented by one global flag.

ChrisHV should hide clean-bit bookkeeping behind setters or state-group tracking instead of requiring every caller to remember the architecture manually.

## Interrupt virtualization

SVM provides facilities for virtual-interrupt handling.

Basic ChrisHV support needs to preserve:

- pending virtual interrupt state;
- guest IF semantics;
- interrupt shadow/state;
- priority behavior where modeled;
- correct injection timing.

The existing inject_irq backend method can serve as the generic entry point.

The hardware-specific backend then translates that request into VMCB virtual-interrupt/event state.

## AVIC

Newer AMD processors may support Advanced Virtual Interrupt Controller features.

AVIC can reduce interrupt-virtualization exits.

It is not necessary for first ChrisHV bring-up.

The implementation should treat AVIC as an optional optimization after basic interrupt injection and virtual APIC semantics are correct.

## Pause filtering

SVM includes mechanisms such as PAUSE filtering on supporting processors.

These can reduce exits or improve scheduling behavior for guests spinning on PAUSE.

Again, this is performance work, not a prerequisite for proving a minimal hardware backend.

## Determinism

SVM introduces the same determinism challenges as VMX:

- host scheduling;
- physical interrupt timing;
- hardware TSC;
- variable exit timing;
- host-specific performance behavior.

A hardware-assisted backend must not silently inherit host time or host CPUID if the ChrisVM virtual architecture promises stable results.

The record/replay model should treat hardware backends as consumers of a controlled event stream where practical.

## TSC virtualization

AMD SVM provides mechanisms relevant to guest time virtualization.

ChrisHV must define one guest-visible time model.

Possible approaches include:

- native host TSC;
- offset/scaled host time when supported;
- synthetic time coordinated with the VM architecture.

For equivalence with ChrisCPU's logical progression, direct host TSC passthrough is undesirable unless the project intentionally changes the contract.

## Host-state isolation

A guest must not inherit unintended host state.

High-risk categories include:

- MSRs;
- debug registers;
- segment state;
- extended processor state;
- performance state;
- TSC/time;
- speculative/security-sensitive controls.

The SVM world-switch layer should explicitly document which state the hardware saves/restores and which state software must manage.

## FPU and extended state

Hardware execution can expose instructions that ChrisCPU does not emulate.

If CPUID advertises SSE/AVX/XSAVE features, ChrisHV must safely preserve their state and define their virtual semantics.

A simple first backend should intentionally expose only a feature set it can save, restore and validate.

## Security boundary

SVM executes untrusted guest code directly on the host processor.

The VMM must protect:

- host memory;
- VMCB;
- host-save area;
- nested page tables;
- IOPM/MSRPM;
- host stacks;
- device-model memory;
- per-vCPU metadata.

Every guest-controlled address or exit field should be validated before it indexes host data.

## IOPM and MSRPM ownership

The I/O Permission Map and MSR Permission Map are host-owned control structures referenced by physical address.

They should be immutable or deliberately versioned during guest execution.

A guest must never be able to remap or overwrite them.

Their memory should remain pinned/owned for as long as the VMCB references them.

## SEV is not baseline SVM

AMD Secure Encrypted Virtualization, including SEV-ES and SEV-SNP, builds on the AMD virtualization ecosystem but changes the trust and state-sharing model substantially.

A first ChrisHV SVM backend should not imply SEV support merely because it uses SVM.

SEV introduces additional firmware protocols, encrypted guest state and memory-integrity/security semantics.

Those deserve separate implementation and documentation.

## Privileged-host architecture

The same practical issue identified for VMX applies to SVM.

The current ChrisVM frontend is a normal host executable.

Direct VMRUN requires privileged execution.

Therefore the project must choose:

- run SVM inside a privileged ChrisOS environment;
- add a host kernel driver;
- use KVM or another host virtualization API;
- or run a bare-metal monitor.

The current source has no such layer.

## KVM path on AMD hosts

Linux KVM can expose AMD hardware virtualization to user-space VMMs while the kernel handles privileged SVM ownership.

A KVM-backed ChrisHV could therefore preserve most of ChrisMachine in user space.

The trade-off is the same as on Intel:

- less raw architecture ownership;
- faster path to a working hardware backend;
- dependence on host kernel/API;
- simpler privilege and physical-memory management.

The project may choose direct SVM later for educational or research goals.

## Minimal bring-up sequence

A staged SVM implementation can proceed as:

1. detect SVM capability;
2. verify host policy allows use;
3. allocate host-save area;
4. set EFER.SVME;
5. initialize one VMCB;
6. intercept a minimal set of operations;
7. create valid guest long-mode state;
8. execute VMRUN;
9. handle one simple exit such as HLT;
10. add CPUID interception;
11. add I/O interception;
12. add nested paging;
13. add interrupt injection;
14. add teardown and repeated-run tests.

This minimizes the number of moving parts at each milestone.

## Minimal guest

A first guest can be:

    CPUID
    OUT test-port
    HLT

This is sufficient to exercise:

- world switch;
- intercept configuration;
- exit decode;
- virtual CPUID;
- I/O bus integration;
- guest RIP progression;
- HLT handling;
- repeated VMRUN.

The full ChrisOS kernel should not be the first hardware test.

## ChrisArchitectureState bridge

The intended backend architecture remains:

    ChrisArchitectureState
        ↕
    ChrisCPU state
        or
    SVM VMCB state

A future implementation should provide explicit conversion routines such as:

    svm_import_arch_state(vcpu, state)
    svm_export_arch_state(vcpu, state)

These functions should be testable with synthetic VMCBs before real guest execution.

## Backend-neutral machine model

ChrisMachine should remain responsible for:

- RAM policy;
- serial;
- framebuffer;
- I/O routing;
- MMIO routing;
- boot/image behavior.

The SVM backend should own:

- host SVM capability;
- host-save area;
- per-vCPU VMCB;
- VMRUN world switch;
- exit decoding;
- nested-page integration;
- hardware interrupt injection.

This is the same architectural boundary intended for VMX.

## Differential validation

Once SVM works, guests supported by ChrisCPU should run on both backends.

Useful comparisons include:

- GPRs;
- RIP/RSP;
- RFLAGS;
- CRs;
- virtual CPUID;
- serial output;
- RAM digest;
- exit reason;
- exception behavior;
- framebuffer digest where relevant.

Differential tests help identify whether divergence comes from the hardware backend or the generic machine model.

## Negative validation

SVM failure paths should be tested deliberately.

Examples:

- SVM unsupported;
- SVM disabled by platform policy;
- invalid physical VMCB address;
- malformed control state;
- invalid guest state;
- invalid nested-page root;
- ASID rollover;
- stale-TLB scenarios;
- repeated init/shutdown;
- partial-allocation cleanup;
- migration to a host CPU without matching setup.

## Diagnostics

Useful bring-up diagnostics should expose:

- SVM CPUID availability;
- SVM feature bits;
- ASID capacity;
- EFER.SVME state;
- host-save physical address;
- VMCB physical address;
- intercept configuration;
- nested paging enable/root;
- current ASID;
- TLB-control request;
- exit code;
- exit info fields;
- guest RIP;
- relevant guest physical/linear address.

Without this information, SVM bring-up becomes trial-and-error.

## Performance

SVM performance depends heavily on world-switch and exit frequency.

Frequent exits for CPUID, I/O, MSRs, interrupts or memory faults can dominate runtime.

Optimization priorities after correctness include:

- minimizing unnecessary intercepts;
- using nested paging;
- using ASIDs effectively;
- using VMCB clean bits correctly;
- leveraging decode assists;
- improving interrupt virtualization.

The backend should measure before optimizing.

## Current source limitations

At the reviewed revision, ChrisOS contains none of the following SVM implementation pieces:

- SVM capability structure;
- EFER.SVME management;
- VM_HSAVE_PA setup;
- VMCB structure/wrapper;
- intercept setup;
- IOPM/MSRPM allocation;
- VMRUN wrapper;
- VMLOAD/VMSAVE integration;
- #VMEXIT dispatcher;
- nested paging;
- ASID allocator;
- TLB-control logic;
- INVLPGA policy;
- interrupt injection;
- AVIC;
- SEV.

This is consistent with the source statement that SVM has not started.

## Implementation priorities for ChrisHV SVM

A reasonable order is:

1. decide privileged host architecture;
2. add capability discovery and diagnostics;
3. allocate/manage per-host-CPU SVM state;
4. implement host-save and EFER.SVME lifecycle;
5. define one VMCB abstraction;
6. add a narrow assembly world-switch wrapper;
7. import/export a minimal ChrisArchitectureState subset;
8. launch a minimal guest;
9. handle HLT, CPUID and port I/O;
10. connect existing ChrisVM devices;
11. add NPT for RAM;
12. add MMIO trapping;
13. add ASID/TLB policy;
14. add interrupt injection;
15. add robust teardown;
16. add ChrisCPU/SVM differential tests;
17. only then add optional performance/security extensions.

## Revision note

At revision e05a17fd76333114a3fb5c2452f38ca747d4ac56, AMD SVM is not implemented in ChrisHV. The project contains only the vendor-specific placeholder header and a generic hardware-backend seam. A real SVM backend will require privileged ownership of SVM hardware, host-save state, VMCB management, VMRUN/#VMEXIT handling, nested paging, ASIDs and interrupt virtualization while preserving the same ChrisMachine and ChrisArchitectureState contracts used by ChrisCPU and the planned VMX backend.
