---
id: validation-evidence
lang: en
type: technical-chapter
volume: 14-validation
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - makefile
  - tests
symbols: []
depends_on:
  - kernel-model
related:
  - self-hosting-bootstrap
  - installation-real-hardware
---

# Validation, evidence classes and reliability

## Presence of code is not proof

A source file demonstrates that an implementation exists. It does not demonstrate that every path compiles, boots, survives concurrency or works on physical hardware.

ChrisOS documentation therefore separates implementation state from evidence state.

## Test layers

### Unit and host tests

Host tests isolate algorithms without booting the OS. They are fast and useful for parsers, filesystems, allocation protocols and compiler internals.

Their limitation is environmental fidelity: host memory, threads and stubs are not identical to kernel page tables, IRQ state or real DMA.

### QEMU gates

A QEMU gate exercises the built kernel against declared virtual hardware. It can validate boot order, actual interrupt entry, virtual devices and integrated subsystems.

QEMU still controls hardware behavior and does not prove physical compatibility.

### Physical hardware

Hardware testing adds firmware/device/timing variation. A result should identify the machine/device profile and exact kernel revision.

## Negative testing

Reliability work must include invalid input and failure paths:

- malformed ELF;
- corrupted filesystem metadata;
- invalid user pointers;
- allocator exhaustion;
- unsupported device features;
- timeouts;
- duplicate/invalid handles.

A success-only test suite proves little about fault containment.

## Invariants

An invariant is a property that must remain true across all allowed state transitions.

Examples:

- one physical frame is not simultaneously allocated to unrelated owners;
- a process cannot map a user page above the permitted boundary;
- a freed JIT frame is not reused while a remote TLB translation remains;
- a shader handle cannot be destroyed by another language slot.

Tests become stronger when they target invariants rather than merely checking one expected output string.

## Gates and revision identity

A gate result is meaningful only for the code revision it tested. Documentation that says "QEMU-tested" without tying the statement to a commit can become false after later changes.

This site therefore stores `reviewed_revision` on authored pages and generates a review queue when declared source dependencies change.

## Historical audits

The ChrisOS source repository contains audits written at earlier branches/revisions. They are valuable records of bugs and design decisions but cannot override newer code.

The documentation pipeline treats current source as primary and historical audits as contextual evidence.

## Reproducible commands

A good gate records a command that another developer or agent can execute, exit status semantics and observable marker/artifact.

"Looked correct on screen" can supplement evidence but is weaker than deterministic pixel readback, structural validation or machine-readable counters.

## No false equivalence

Different evidence classes should not be collapsed into a single "working" label. A host-tested matrix function, QEMU-tested VirGL draw and hardware-tested NVMe path establish different facts.
