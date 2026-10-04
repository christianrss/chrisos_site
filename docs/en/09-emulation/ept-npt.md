---
id: ept-npt
lang: en
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chris_arch.h
  - chrisvm/chrisvm.h
  - chrisvm/machine/machine.c
  - chrisvm/machine/machine.h
  - chrisvm/buses/mmio.c
  - chrisvm/cpu/emulator/mmu.c
  - chrisvm/cpu/hv/chrishv.c
  - chrisvm/cpu/hv/vmx/vmx.h
  - chrisvm/cpu/hv/svm/svm.h
symbols:
  - ChrisArchitectureState
  - chris_translate
  - chris_phys_read
  - chris_phys_write
  - chrishv_backend
depends_on:
  - vmx
  - svm
  - emulator-paging
  - chrisvm-memory-map
related:
  - chrisvm-mmio-bus
  - chrisvm-machine
  - determinism-replay
---

# EPT and NPT: second-level translation for ChrisHV

## Scope

Hardware virtualization introduces a second address-translation problem that the current ChrisCPU interpreter does not need to express as hardware page tables.

A guest operating system normally translates:

    guest virtual address
        ↓ guest page tables
    guest physical address

A hardware-assisted VMM must then translate that guest-physical address into memory owned by the host:

    guest physical address
        ↓ EPT or NPT
    host/system physical address

Intel calls this second-level mechanism Extended Page Tables, EPT.

AMD calls the analogous mechanism nested paging, commonly abbreviated NPT.

At ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56, ChrisHV implements neither EPT nor NPT.

The current ChrisCPU path instead performs guest paging in software and then routes the resulting physical address through ChrisMachine.

This chapter documents the architectural role of EPT/NPT, their relationship to the existing ChrisVM memory model and the requirements for adding them without confusing guest faults with hypervisor faults.

## Current ChrisCPU translation path

ChrisCPU currently evaluates guest paging explicitly in:

    chris_translate

The function starts from:

    cpu->arch.cr3

and walks the guest's own x86-64 page tables.

It checks:

- canonical addressing;
- Present;
- Writable;
- User;
- NX when EFER.NXE is enabled;
- large-page state;
- Accessed;
- Dirty.

The output is a guest-physical address.

ChrisCPU then calls:

    chris_phys_read
    chris_phys_write

to route that physical address into the machine's RAM, framebuffer or generic MMIO.

Therefore current ChrisVM has two conceptual stages already:

    guest VA
        ↓ software guest walk
    ChrisVM guest PA
        ↓ software machine dispatcher
    host allocation/device callback

The second stage exists conceptually, but not as hardware second-level paging.

## What changes with ChrisHV

With hardware-assisted execution, the physical CPU performs the guest's first-stage page walk.

If the guest is allowed to run with its own CR3 and paging controls, the VMM needs hardware to constrain what those guest-physical results can reach.

EPT/NPT provides that constraint.

The hardware path becomes:

    guest instruction
        ↓
    guest linear address
        ↓ guest page-table walk by CPU
    guest physical address
        ↓ EPT/NPT walk by CPU
    host/system physical address

This permits direct guest execution while keeping host memory isolated.

## Why direct guest physical addresses are unsafe

Guest software controls its own page tables.

Without second-level translation, a malicious or buggy guest could try to construct mappings to physical addresses belonging to:

- the host kernel;
- the hypervisor;
- another VM;
- device MMIO;
- VMX/SVM control structures;
- host stacks;
- page tables used by the VMM.

EPT/NPT makes the guest-physical address an intermediate namespace rather than a raw host physical address.

This is fundamental to isolation.

## Three address spaces

A ChrisHV implementation must keep three concepts distinct:

    GVA = guest virtual address
    GPA = guest physical address
    HPA/SPA = host/system physical address

The same numeric value can appear in more than one namespace while representing different objects.

A common hypervisor bug is passing one namespace into an API expecting another.

Type discipline can help.

For example:

    typedef uint64_t GuestVirtualAddress;
    typedef uint64_t GuestPhysicalAddress;
    typedef uint64_t HostPhysicalAddress;

even if the underlying representation remains uint64_t.

## Relationship to ChrisMachine RAM

ChrisMachine currently owns guest RAM as one host allocation:

    m->ram

For ChrisCPU, that pointer is enough because software copies bytes directly.

For EPT/NPT, the processor needs host physical backing.

A future hardware backend therefore needs a memory-ownership layer that can:

- allocate/pin host pages;
- determine their physical addresses where direct hardware tables require them;
- map guest-physical pages to those host pages;
- preserve lifetime while the guest is running;
- unmap safely during teardown.

A normal user-space pointer is not itself an EPT/NPT physical target.

## EPT overview

Intel EPT provides a hardware-managed second page-table walk.

The EPT root is selected through an EPT pointer, EPTP, configured as part of VMX execution controls.

The table hierarchy resembles x86-64 paging structurally but has EPT-specific entry semantics.

An EPT translation controls whether a guest-physical access may:

- read;
- write;
- execute.

The final leaf identifies the host physical backing and attributes required by EPT.

## EPT permissions

EPT permissions are independent of the guest's own page-table permissions.

An access succeeds only when both translation layers permit it.

Conceptually:

    guest permission
    AND
    EPT permission

A guest page can therefore be Writable in the guest page table but read-only in EPT.

This is useful for:

- copy-on-write;
- dirty tracking;
- watchpoints;
- protected hypervisor metadata;
- MMIO trapping.

The second-level restriction cannot grant an access that the first-level guest paging denies.

## EPT execute control

EPT includes execute permission separately from read and write.

This enables a hypervisor to enforce execute policy independently of the guest's first-stage NX configuration.

A future ChrisHV should avoid using EPT execution permission as a substitute for guest architectural NX semantics.

Guest #PF/NX behavior belongs to first-stage paging.

EPT execute restrictions are hypervisor policy.

## EPT large pages

EPT can map large page sizes when supported and correctly aligned.

Large pages reduce second-level page-table depth and TLB pressure.

They can improve performance for large contiguous guest RAM regions.

However, large mappings reduce protection granularity.

A hypervisor that needs page-level dirty tracking, MMIO holes or copy-on-write may need to split a large mapping into smaller leaves.

Initial ChrisHV bring-up should favor simple correctness over aggressive large-page use.

## EPT violation

When an EPT translation denies or cannot satisfy an access in a way that produces an EPT violation, VMX exits to the VMM.

The exit information identifies details about the attempted access.

An EPT violation is a hypervisor-level event.

It is **not** automatically a guest page fault.

The guest may have a perfectly valid first-stage translation to a GPA that ChrisHV intentionally left unmapped in EPT.

## EPT misconfiguration

Intel also distinguishes EPT misconfiguration from ordinary EPT violation.

A misconfiguration indicates the EPT structures contain an invalid combination or reserved-state problem.

This generally means the hypervisor constructed an invalid EPT entry.

That should be treated as a VMM bug or corrupted hypervisor state, not converted into a guest-visible page fault.

Diagnostics should include the GPA, EPTP and relevant entry chain where possible.

## MMIO trapping with EPT

EPT can help route MMIO.

One simple design is:

- map RAM GPAs in EPT;
- leave device MMIO GPAs unmapped or access-restricted;
- receive EPT violation on guest access;
- classify the GPA using ChrisMachine's physical map;
- dispatch to the software device model;
- emulate the access;
- resume the guest.

This extends the current ChrisVM device model into hardware-assisted execution.

However, memory-instruction emulation is more complex than port I/O because the backend must know:

- access width;
- read/write direction;
- guest register effects;
- instruction length;
- atomicity/locking semantics;
- partial-access behavior.

The current generic MMIO path already loses original transaction width, so hardware backend design should not reproduce that limitation unintentionally.

## Directly mapped MMIO

Not every MMIO region must be trapped.

A hypervisor may directly map safe passthrough/shared memory regions into second-level tables.

That is a different security model.

Current ChrisVM devices are software models, so the safest first ChrisHV design is to trap virtual MMIO rather than pass physical host devices through.

## EPT accessed and dirty state

On supporting processors, EPT can maintain accessed/dirty information.

These bits are useful for:

- migration;
- snapshotting;
- dirty-page tracking;
- memory-management research.

Capability detection is required before relying on them.

A first implementation can operate without advanced dirty tracking as long as the chosen EPT mode is valid on the host CPU.

## INVEPT

Changing EPT structures does not mean every processor cache instantly forgets old translations.

Intel provides INVEPT for EPT-related invalidation.

The required invalidation scope depends on the change and supported capabilities.

A safe memory-update sequence is conceptually:

    modify EPT entry
        ↓
    publish ordering
        ↓
    INVEPT appropriate scope
        ↓
    resume guest

Skipping required invalidation can expose stale permissions or stale physical mappings.

## EPTP ownership

Each EPT context has a root and configuration encoded through EPTP.

ChrisHV must treat EPTP as per-address-space/per-VM virtualization state, not a global constant.

Future scenarios that may require multiple EPT contexts include:

- snapshots;
- copy-on-write versions;
- nested virtualization research;
- fast switching between memory views;
- execute-only instrumentation views.

The first implementation can use one EPT root per VM.

## NPT overview

AMD nested paging solves the same second-stage translation problem.

The VMCB enables nested paging and identifies a nested-page-table root, commonly described through nCR3.

The processor then performs:

    guest linear
        ↓ guest paging
    guest physical
        ↓ nested paging
    system physical

The guest continues to own its first-stage page tables.

The VMM owns the nested hierarchy.

## NPT entry model

AMD nested page tables use paging structures closely related to AMD64 page translation.

Permissions and page-size behavior must follow the AMD architecture.

A ChrisHV implementation should not attempt to use one binary table format for both EPT and NPT merely because both are multi-level trees.

The generic layer should abstract mapping intent:

    map GPA range
    unmap GPA range
    set permission
    invalidate context

and let vendor backends encode entries correctly.

## Nested page fault

When nested translation fails, SVM produces a nested-page-fault exit to the VMM.

This differs from a guest #PF.

The backend should classify:

    guest first-stage fault
    versus
    nested second-stage fault

correctly.

A first-stage #PF should normally remain guest architectural behavior.

A nested fault is a VMM memory-management event.

## NPT and ASIDs

AMD ASIDs tag guest translations and reduce flush overhead.

Nested-paging state participates in TLB-management rules.

Changing nCR3 or nested mappings requires correct invalidation policy.

ASID reuse without generation/flush discipline can expose stale translations from an older address space.

Therefore ASID allocation and NPT mapping management are one subsystem, not independent optimizations.

## TLB invalidation on AMD

AMD provides VMCB TLB-control mechanisms and INVLPGA-related operations.

The backend should define an invariant:

    no guest resumes with a stale translation
    that violates current nested-page policy

The first implementation may use conservative flushes.

Optimization should come after correctness and measurement.

## EPT versus NPT abstraction

The generic ChrisHV memory layer should represent semantics rather than vendor entry formats.

A useful conceptual API could be:

    slat_create(vm)
    slat_destroy(vm)

    slat_map(gpa, hpa, size, permissions)
    slat_unmap(gpa, size)
    slat_protect(gpa, size, permissions)

    slat_flush(context)

where SLAT means second-level address translation.

Vendor-specific implementations would then provide:

    vmx_ept_*
    svm_npt_*

This preserves one machine-memory policy while keeping EPT/NPT encoding separate.

## Region model

Second-level mappings should be derived from an authoritative ChrisMachine physical-region description.

Current ChrisMachine has implicit region policy:

1. RAM;
2. framebuffer;
3. generic MMIO.

A hardware backend needs a richer generated map containing at least:

- GPA start;
- size;
- region type;
- RAM backing;
- permissions;
- trap/direct-map policy;
- device identity;
- dirty/snapshot policy.

Without one authoritative map, EPT/NPT and software physical dispatch can diverge.

## RAM mapping

Guest RAM is the easiest first second-level mapping.

A minimal implementation can:

- allocate a fixed RAM size;
- pin backing pages;
- map GPA 0..ram_size to host physical pages;
- enable read/write/execute according to the initial research model;
- avoid mapping all other GPA space.

This immediately isolates the guest from arbitrary host physical memory.

## Framebuffer mapping

The current framebuffer is a separate host allocation at guest physical:

    0x02000000

For ChrisHV, there are at least two designs:

1. directly map framebuffer backing into second-level translation;
2. trap accesses and route through a software MMIO/device path.

Direct mapping is faster and fits the current linear framebuffer model.

But it also means dirty tracking must be obtained through hardware A/D state, write protection/trapping or another explicit mechanism.

Current ChrisCPU simply sets fb.dirty on software writes.

Backend equivalence therefore requires a new dirty-state strategy.

## Dirty tracking equivalence

This is a concrete example of how hardware acceleration changes observability.

Current software path:

    guest write
        ↓
    chris_phys_write
        ↓
    framebuffer backing modified
        ↓
    fb.dirty = 1

Direct EPT/NPT mapping:

    guest write
        ↓
    hardware store directly to backing page

No C function runs.

Therefore fb.dirty would not automatically change.

Possible solutions include:

- second-level write-protect first write and trap it;
- inspect hardware dirty bits;
- mark dirty conservatively after guest execution;
- redesign presentation state around page dirty tracking.

The policy must be explicit.

## RAM writes and instrumentation

The same issue applies to any software instrumentation currently implemented inside chris_phys_write.

A hardware backend bypasses software physical dispatch for directly mapped RAM.

Features such as:

- write tracing;
- watchpoints;
- dirty tracking;
- snapshot copy-on-write;
- access statistics;

must move into hardware page permissions, A/D bits, exits or separate instrumentation.

## Guest page faults versus second-level faults

The most important semantic rule is:

    first-stage fault belongs to guest architecture
    second-stage fault belongs to hypervisor policy

Suppose the guest accesses an unmapped guest virtual address.

Its own page walk fails.

The guest should receive #PF according to x86 rules.

Suppose the guest page walk succeeds and yields GPA 0x40000000, but ChrisHV has no second-level mapping there.

That is an EPT violation or nested page fault.

The VMM decides what the GPA means.

The guest does not automatically receive the same #PF.

## CR2 ownership

Guest #PF updates guest CR2.

A second-level fault should not overwrite guest CR2 merely because it involved a memory address.

This is important for compatibility with the current ChrisCPU exception model.

ChrisHV must update architectural guest state only when the virtual architecture requires it.

## Security permissions

Second-level tables are the primary memory-isolation boundary.

At minimum, ChrisHV must ensure:

- guest RAM maps only to pages owned by that VM;
- hypervisor pages are never mapped;
- VMCS/VMCB/EPT/NPT pages are never guest-accessible;
- host stack/code pages remain inaccessible;
- device model memory is not accidentally exposed;
- stale mappings are invalidated before page reuse.

A use-after-free in second-level mapping can become cross-VM or guest-to-host memory disclosure.

## Mapping lifecycle

A robust lifecycle is:

    allocate host page
        ↓
    assign to VM
        ↓
    create second-level mapping
        ↓
    run guest
        ↓
    remove mapping
        ↓
    invalidate translations
        ↓
    wait for ownership safety
        ↓
    return/reuse host page

Reusing the page before stale translations are invalidated is unsafe.

## Concurrency

Current ChrisVM is single-vCPU.

A future SMP ChrisHV introduces concurrent second-level translation use.

Mapping updates then need synchronization around:

- page-table allocation;
- entry updates;
- TLB shootdown/invalidation;
- vCPU run state;
- page ownership;
- teardown.

The locking design should be established before adding multiple vCPUs.

## Huge pages and fragmentation

Large second-level pages improve translation efficiency but require contiguous/aligned host backing.

Dynamic features can force splitting:

- MMIO holes;
- snapshots;
- copy-on-write;
- page-level protection;
- dirty logging.

A useful allocator should not make large pages a correctness requirement.

They are an optimization.

## Memory types and cacheability

Second-level mappings include or interact with memory-type/cacheability semantics.

RAM, framebuffer and device MMIO must not be treated identically.

Incorrect memory type can cause:

- severe performance loss;
- unexpected ordering;
- incorrect device behavior.

The backend needs an explicit region-type to hardware-memory-type policy.

That policy must be based on Intel/AMD architecture and host ownership, not guessed from virtual addresses.

## Determinism and replay

Second-level translation affects deterministic replay because mapping faults and dirty state can become externally visible monitor events.

A replay architecture should record or deterministically reconstruct:

- memory-map version;
- GPA ownership;
- page-protection changes;
- snapshot/copy-on-write transitions;
- externally timed DMA/device updates.

Pure RAM address translation itself should be deterministic for a fixed mapping.

## Snapshotting

EPT/NPT can become the foundation for efficient snapshots.

A future snapshot design can:

1. mark RAM mappings read-only;
2. on first write, receive a second-level fault;
3. copy the original page or allocate a private version;
4. remap writable;
5. invalidate translation;
6. resume.

This is copy-on-write snapshotting.

It should be added only after baseline mapping/fault semantics are stable.

## Watchpoints

Second-level protection can implement host-side watchpoints.

For example, a page can be mapped read-only to catch writes.

This is coarse at page granularity.

After a violation, the debugger can inspect GPA/RIP and decide whether to emulate, temporarily permit or stop.

This can extend the current ChrisVM debugger without modifying guest debug registers.

## Nested virtualization

If a guest itself attempts to run a hypervisor, EPT/NPT semantics become more complex.

Nested virtualization is outside current ChrisHV scope.

The first backend should explicitly reject or hide virtualization features from guest CPUID rather than accidentally expose partial nested support.

## Host APIs such as KVM

If ChrisHV uses KVM, the host kernel already manages actual EPT/NPT construction.

ChrisVM would still need to define the same conceptual GPA map and memory slots.

Therefore this chapter remains relevant even if raw second-level page-table code is not written in this repository.

The architectural distinction between GVA, GPA and HPA remains.

## Validation strategy

A useful test progression is:

1. map one RAM page and read/write it;
2. prove an unmapped GPA cannot reach host memory;
3. verify read-only second-level protection;
4. verify execute protection where supported;
5. trigger and classify EPT/NPT fault;
6. change mapping and prove invalidation;
7. map multiple noncontiguous host pages into contiguous GPA;
8. test MMIO hole trapping;
9. test framebuffer policy;
10. test mapping teardown and host-page reuse;
11. compare hardware-backend RAM results with ChrisCPU.

## Differential memory test

For a deterministic guest:

    write values to several virtual addresses
    read them back
    touch a large page boundary
    touch framebuffer/MMIO boundary
    halt

Run the same guest on ChrisCPU and ChrisHV.

Compare:

- final RAM digest;
- registers;
- framebuffer;
- exit reason;
- guest exception state.

This tests both first-stage and second-stage integration.

## Current source limitations

At the reviewed revision, ChrisOS contains no:

- EPTP construction;
- EPT entry definitions;
- INVEPT wrapper;
- EPT-violation handler;
- NPT enablement;
- nCR3 ownership;
- nested-page-fault handler;
- ASID allocator for ChrisHV;
- hardware second-level mapping API;
- pinned host-physical RAM provider;
- second-level dirty tracking;
- cross-backend physical-region descriptor.

ChrisCPU's software physical dispatcher remains the only implemented machine-memory backend.

## Implementation priorities

A reasonable order for ChrisHV second-level translation is:

1. define explicit GVA/GPA/HPA types and ownership rules;
2. create one authoritative ChrisMachine physical-region map;
3. build a host-page allocation/pinning abstraction;
4. define generic SLAT map/unmap/protect/flush semantics;
5. implement minimal EPT RAM mapping for VMX;
6. implement minimal NPT RAM mapping for SVM;
7. add fault classification and diagnostics;
8. add required invalidation;
9. add MMIO trapping;
10. define framebuffer dirty policy;
11. add permission changes/watchpoint support;
12. add dirty/access tracking;
13. add large-page optimization;
14. add snapshot/copy-on-write only after baseline correctness;
15. add SMP synchronization and shootdown when multi-vCPU support begins.

## Revision note

At revision e05a17fd76333114a3fb5c2452f38ca747d4ac56, ChrisVM already separates guest virtual translation from machine physical routing conceptually, but both stages are implemented in software by ChrisCPU and ChrisMachine. ChrisHV currently has no EPT or NPT. Adding hardware-assisted execution requires a real second-level translation layer that maps guest physical addresses to owned host/system physical pages, preserves MMIO/device semantics, distinguishes guest page faults from hypervisor mapping faults and provides correct invalidation, isolation and dirty-state behavior.
