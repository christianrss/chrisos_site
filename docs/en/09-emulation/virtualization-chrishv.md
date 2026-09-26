---
id: virtualization-chrishv
lang: en
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - chrisvm/cpu/hv/vmx/vmx.c
  - chrisvm/cpu/hv/svm/svm.c
  - docs/chrisvm/architecture.md
symbols: []
depends_on:
  - chrisvm-chriscpu
related:
  - x86-64-memory-privilege
---

# Hardware virtualization and the ChrisHV boundary

## Why virtualization differs from interpretation

ChrisCPU fetches and implements guest instructions in software. Hardware virtualization instead configures the physical CPU to execute guest instructions directly until an event causes a controlled exit to the hypervisor.

Intel VT-x and AMD-V/SVM provide different control structures but solve analogous problems.

## Guest and host state

Virtualization hardware maintains a boundary between guest architectural state and host/hypervisor state. Entry loads or activates guest execution context; exit reports a reason and returns control to the monitor.

Typical exit reasons include selected privileged operations, I/O, control-register changes, exceptions or explicitly configured events.

## Second-level translation

A virtualized guest may maintain its own page tables translating guest virtual → guest physical. The hypervisor also needs guest physical → host physical translation, commonly through EPT (Intel) or NPT (AMD).

```text
guest virtual
    ↓ guest page tables
guest physical
    ↓ EPT / NPT
host physical
```

This differs from a simple emulator where the software memory subsystem can directly perform both conceptual stages.

## Device model continuity

Hardware-assisted CPU execution does not eliminate the need for a virtual machine model. Guest I/O still needs emulated/paravirtual devices, interrupts, timers and memory-map policy.

That is why ChrisHV is designed as a backend under ChrisVM rather than as a replacement for ChrisVM.

## Current project state

The current ChrisVM architecture explicitly leaves VMX/SVM implementations unstarted/nonfunctional. Selecting the ChrisHV backend is expected to fail rather than silently fall back to another engine.

This is the correct behavior for a truthful architecture: an unavailable backend should be observable as unavailable.

## Progressive implementation

A future ChrisHV path needs, at minimum:

- host capability detection;
- protected VMX/SVM initialization;
- per-vCPU control structures;
- guest state import/export through `ChrisArchitectureState`;
- memory virtualization;
- exit dispatch;
- interrupt injection;
- device I/O integration;
- teardown on every error path;
- equivalence tests against ChrisCPU where both can run the same guest.

The goal is backend interchangeability at the machine contract, not duplicate virtual platforms.
