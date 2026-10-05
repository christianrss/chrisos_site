---
id: validation-evidence
lang: en
type: technical-chapter
volume: 14-validation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - makefile
  - scripts/qemu.mk
  - tools/qemu_gate.py
  - tools/check_test_gates.py
  - chrisvm/tests/test_chrisvm.c
  - tools/test_elf_malformed.c
  - tools/test_fuzz_elf.c
symbols: []
depends_on:
  - kernel-model
related:
  - host-tests
  - qemu-gates
  - hardware-gates
  - fault-injection
  - fuzzing
  - performance-measurement
  - self-hosting-bootstrap
  - installation-real-hardware
---

# Validation, evidence classes and reliability

## Purpose

ChrisOS treats validation as a set of evidence classes, not as one Boolean label called "working."

Source code proves that an implementation exists. A successful build proves that one selected source path compiled and linked. A host test proves behavior inside a host process. A QEMU gate proves an integrated guest path under a declared virtual machine configuration. ChrisVM tests prove behavior inside the project-owned emulator. A physical-hardware record proves the identified physical configuration.

Those statements are not interchangeable.

The purpose of the validation model is to prevent implementation claims from becoming stronger than the evidence that actually produced them.

## Evidence record

A useful validation record needs six elements:

| Element | Meaning |
|---|---|
| Revision | exact ChrisOS commit tested |
| Command | gate, test or build command |
| Environment | host, machine and relevant device configuration |
| Oracle | exact rule deciding pass or fail |
| Artifact | log, marker set, image, counter or state comparison |
| Limitations | configurations or properties not established |

"Passed on my machine" omits almost all of this information.

A reproducible claim should let another developer reconstruct both the workload and the pass/fail rule.

## Revision identity

A gate result belongs to the source revision it executed.

If revision R1 passes and the repository later moves to R2, the old result becomes historical evidence. It does not automatically prove R2.

This is why authored documentation records `reviewed_revision` and why serious test reports should identify the tested commit.

Revision binding also prevents a label such as "QEMU-tested" from surviving indefinitely after the relevant source changes.

## Evidence is property-specific

One command can establish several properties, but it never establishes every property of the subsystem it touches.

For example, a gate that reaches:

    root ata
    cfs mounted

shows that the tested boot selected ATA as root and mounted ChrisFS.

It does not prove every ATA command, every filesystem path, every concurrency interleaving or every physical controller.

Evidence must therefore be read at the same granularity as its oracle.

## Layer 0: build evidence

The first executable layer is compilation and linking.

Build evidence can detect:

- missing declarations;
- type errors;
- unresolved symbols;
- warnings promoted to errors;
- incompatible object formats;
- linker-script failures;
- image-construction errors.

A successful build does not prove boot or runtime behavior.

It establishes that the selected artifact graph could be constructed under the declared toolchain.

## Layer 1: narrow host tests

Host tests execute ChrisOS algorithms as ordinary host programs.

They are valuable because they are generally:

- fast;
- deterministic;
- isolated;
- easy to repeat;
- easy to inspect;
- compatible with host sanitizers.

The root `host-gates` target aggregates tests for filesystems, JIT, native toolchain components, graphics, queues, memory-management protocols, synchronization, ELF handling, sockets, fuzzers and editor/debugger behavior.

This provides broad algorithmic coverage without booting the kernel for every assertion.

## Host-test fidelity boundary

A host test runs with the host ABI, host virtual memory and host scheduler.

It does not automatically reproduce:

- guest page tables;
- real kernel privilege transitions;
- hardware interrupt entry;
- DMA;
- firmware;
- PCI enumeration;
- QEMU device behavior;
- physical device timing.

A parser or allocator may be strongly host-tested and still require guest integration evidence.

The correct phrase is therefore "host-tested," not "hardware-tested."

## Gate reachability audit

ChrisOS includes `tools/check_test_gates.py`.

The script parses the makefile dependency graph from the `host-gates` root and reports test-like targets that are not reachable from the aggregate.

This protects against a subtle false sense of coverage:

> a test can exist in source but never execute when the project runs its advertised aggregate gate.

The audit proves reachability, not the quality of the tests themselves.

## Aggregate host gates

The current `host-gates` dependency list spans many independent families, including:

- ChrisFS operations and fsck;
- indirect/journal/chmod/max-write paths;
- JIT encoding, VM, native and benchmark tests;
- ChrisO, ChrisAsm, ChrisLd and KCC;
- graphics and shader paths;
- VirtIO queue/resource logic;
- PMM/heap SMP behavior;
- kthread/job saturation;
- TLB protocol;
- build metadata;
- CLVM synchronization;
- malformed ELF;
- ownership and write paths;
- deterministic fuzzers;
- editor/debugger model tests.

The exact list is revision-bound.

The important architectural property is that the aggregate is explicit and auditable.

## Layer 2: sanitizer evidence

The `host-sanitize` target compiles selected host tests with AddressSanitizer and UndefinedBehaviorSanitizer.

The current instrumented set includes selected PMM/heap SMP, kthread, job-saturation and key-state paths.

Sanitizers improve detection of classes such as:

- invalid host memory access;
- some lifetime errors;
- buffer misuse;
- undefined C behavior detectable by UBSan.

They do not prove the absence of all memory bugs.

They also do not instrument every host gate.

A sanitizer result must remain scoped to the targets actually built with instrumentation.

## Stability aggregation

The root `stability` target depends on:

    host-gates
    host-sanitize

When `qemu-system-x86_64` is available, it also runs:

    qemu-stress

When QEMU is unavailable, the makefile explicitly reports that only host gates were executed.

Therefore "stability passed" is incomplete unless the environment record says whether the QEMU branch actually ran.

## Stress evidence

Stress tests apply repeated pressure to state transitions and resource limits.

The current host-stress family includes examples around:

- PMM/heap SMP;
- kthreads;
- job saturation;
- TLB protocol;
- logging;
- PMM cycles;
- filesystem locking;
- fuzz workloads;
- task/window behavior.

Passing repeated iterations increases confidence in the exercised transitions.

It does not mathematically prove race freedom for every possible schedule.

## Layer 3: QEMU integration

The maintained QEMU x86 gate base uses a declared machine configuration including:

    pc machine
    2048 MiB RAM
    configurable SMP count
    qemu64 CPU
    TCG acceleration
    headless display
    serial log file

TCG is used for the portable headless validation path.

KVM is therefore not required for the main QEMU gate suite.

This makes the test environment more reproducible across machines that cannot expose hardware virtualization.

## QEMU gate oracle

`tools/qemu_gate.py` is the common serial-marker oracle.

A QEMU process may exit normally or remain alive until its timeout.

Timeout code 124 is acceptable only when:

- every expected marker is present;
- no fatal marker is present;
- QEMU did not exit with another error code.

The current fatal-marker set includes categories such as:

- kernel panic;
- explicit exception-vector report;
- double fault;
- general protection;
- heap corruption;
- PMM corruption.

This prevents "QEMU stayed running" from being mistaken for success.

## Expected markers

Expected markers should correspond to the invariant or milestone under test.

For example, the ATA gate expects:

- the configured CPU-online count;
- ATA selected as root;
- ChrisFS mounted.

The NVMe gate instead expects NVMe discovery and a successful block-device read/write marker.

A marker emitted too early creates a weak oracle.

A good gate places the marker after the operation whose success it represents.

## QEMU device matrix

The base `qemu-gates` aggregate currently includes dedicated paths for:

- ATA;
- AHCI;
- NVMe;
- VirtIO block;
- USB mass storage;
- VirtIO GPU;
- RISC-V;
- no-ATA fallback;
- installation;
- safe mode;
- xHCI HID.

The one-vCPU variant is added by `full-gates`, not by base `qemu-gates`.

VirGL is a separate conditional gate because it depends on host graphics capability.

A report should preserve these distinctions instead of saying only "QEMU tests passed."

## Negative topology testing

The no-ATA gate demonstrates negative topology testing.

It expects ATA to be absent, AHCI to become the root path, ChrisFS to mount and later boot milestones to continue.

That establishes fallback selection when one device class is missing.

It is not equivalent to injecting an I/O error into an already initialized disk.

Topology variation and mid-flight fault injection test different recovery properties.

## Installer gate

The installer gate crosses several layers:

1. prepare source and target images;
2. boot the automatic installer;
3. require installer progress markers;
4. validate the produced disk image structurally;
5. boot the installed image with OVMF/UEFI;
6. require filesystem and desktop milestones.

This is stronger than checking only that installer code exists.

It still does not prove installation on arbitrary physical firmware and storage controllers.

## VirGL skip semantics

The VirGL gate first checks whether the host QEMU and display stack can provide a GL-capable VirtIO GPU environment.

If the required capability is absent, the test reports a skip.

A skip is neither a guest pass nor a guest failure.

It means the requested test environment could not be created.

Reports should preserve this third state so unavailable host capability is not converted into a false green feature claim.

## Layer 4: ChrisVM evidence

`make chrisvm-test` executes the project-owned emulator suite.

The current suite includes named tests for:

- arithmetic flags;
- interpreted ADD;
- memory and CALL/RET;
- serial and port I/O;
- faults;
- CPUID/MSR behavior;
- multiply/divide;
- ELF acceptance and rejection;
- decoder fuzzing;
- real MMIO callbacks;
- STOS and framebuffer splash.

These tests provide evidence about ChrisCPU and ChrisVM semantics.

They do not by themselves prove equivalence with physical x86.

## Differential emulator evidence

A strong future emulator validation technique is differential execution.

Start two environments from equivalent architectural state, run a bounded instruction sequence, then compare:

- registers;
- flags;
- memory;
- exception vector;
- exit reason;
- device-visible effects.

Agreement with an independent reference gives stronger evidence than tests that use only the project's own expected values.

Timing fields may require normalization.

## Layer 5: physical hardware

Physical hardware introduces variability that QEMU deliberately regularizes:

- firmware implementation;
- chipset details;
- storage-controller revisions;
- DMA behavior;
- interrupt routing;
- device timing;
- boot-media behavior;
- display and GPU paths.

A physical result should identify the tested profile.

At minimum, record relevant machine, CPU, firmware mode/version, device identities, boot medium and source revision.

The repository currently has no generic automated physical-hardware gate equivalent to `qemu-gates`.

Manual hardware reports must not be described as continuously reproduced CI evidence.

## Fault injection

Fault injection deliberately perturbs an otherwise valid path.

Current project examples include:

- ChrisFS block-device I/O failures;
- malformed executable data;
- constrained allocation budgets;
- deliberate process-fault fixtures;
- missing-device topologies.

The question changes from:

> does the normal path succeed?

to:

> when a dependency fails, are ownership and consistency invariants preserved?

This distinction is essential for reliability work.

## Fuzzing

Current fuzzers are deterministic pseudo-random or structured adversarial tests rather than continuous coverage-guided infrastructure.

Existing fuzz targets exercise areas including:

- ChrisFS operation sequences;
- ELF loading;
- ChrisC source;
- CLVM images;
- ChrisVM instruction decoding.

Fixed seeds make failures reproducible.

The trade-off is limited exploration unless the corpus or seed strategy expands.

A fuzzer becomes much stronger when it has a semantic oracle such as no leaked pages, a successful filesystem check or a bounded valid decoder result.

## Negative tests

A reliable suite contains inputs whose correct result is rejection.

Examples include:

- malformed ELF;
- invalid relocation;
- unsupported compiler input;
- corrupt metadata;
- invalid owner/handle relationships;
- missing devices;
- exhausted allocators.

Expected rejection is a successful negative test.

The important property is that the system rejects the input at the intended boundary without corrupting unrelated state.

## Invariant-oriented testing

An invariant is a property that must remain true across valid state transitions.

Examples relevant to ChrisOS include:

- unrelated allocators do not own the same physical frame;
- filesystem allocation state remains consistent after an error;
- failed ELF loading does not leak pages;
- a resource handle does not cross its owner boundary;
- page faults retain the faulting virtual address in CR2;
- backend fallback does not change public resource identity.

Tests that target invariants generally provide stronger evidence than tests that only search for a final success string.

## Oracle quality

A validation result is only as strong as its oracle.

A weak oracle is:

    process exited with code 0

Stronger oracles include:

- exact state comparison;
- structural image validation;
- expected markers present;
- forbidden markers absent;
- ownership counters returned to baseline;
- round-trip encode/decode equality;
- filesystem consistency checks.

The oracle should be as close as practical to the property being claimed.

## False positives

A false positive occurs when a gate passes while the intended property is broken.

Common causes include:

- success marker emitted before the operation completes;
- a test target exists but is not reachable from the aggregate;
- a timeout is accepted without progress markers;
- an unsupported feature silently falls back to another implementation;
- only one field of a larger state is compared;
- stale build artifacts satisfy the oracle.

Gate design should explicitly defend against these cases.

## False negatives

A false negative occurs when the target behavior is correct but the test environment fails for an unrelated reason.

Examples include:

- host QEMU lacks VirGL;
- required QEMU binary is absent;
- interactive KVM is unavailable;
- a host tool version changes diagnostics;
- graphics display infrastructure is unavailable.

Environment failure, guest failure and infrastructure failure should be reported separately.

## Performance evidence

A benchmark is not a correctness gate.

Performance evidence should record:

- workload;
- build configuration;
- host;
- timing source;
- warmup;
- repetitions;
- statistic;
- revision.

A faster result cannot compensate for a failed correctness invariant.

Regression thresholds should be introduced only after measurement noise and environment sensitivity are understood.

## Evidence matrix

| Evidence class | Establishes | Does not establish |
|---|---|---|
| build | selected source compiles/links | runtime correctness |
| host unit | host-executed logic | guest or physical integration |
| sanitizer | selected instrumented host paths | absence of every memory/UB defect |
| stress | repeated exercised transitions | every possible interleaving |
| QEMU gate | integrated guest path on declared virtual hardware | arbitrary physical hardware |
| ChrisVM test | project-owned emulator behavior | physical x86 equivalence |
| fault injection | selected failure behavior | every failure class |
| fuzzing | tested generated/adversarial corpus | exhaustive input space |
| hardware run | one identified physical profile | universal compatibility |
| benchmark | measured workload performance | correctness or portability |

## Claim promotion

A capability claim should become broader only when evidence crosses the required boundary.

A typical progression is:

    source exists
      -> narrow host test
      -> aggregate host gate
      -> guest integration
      -> topology/configuration variants
      -> identified physical hardware
      -> broader compatibility matrix

Not every feature requires every step.

The required level depends on the exact claim.

## Failure records

A failed run is useful evidence when it is localized.

A useful record includes:

- source revision;
- command;
- environment;
- first meaningful error;
- last successful marker;
- retained log or artifact;
- clean-build reproducibility;
- classification as host, guest or infrastructure.

Discarding failed runs because they are not green throws away diagnostic information.

## Reproducibility

A reproducible gate minimizes hidden state.

Useful practices include:

- deterministic disk images;
- fixed fuzz seeds;
- explicit QEMU device configuration;
- clean artifact boundaries;
- versioned source revisions;
- machine-readable markers;
- bounded timeouts.

Reproducibility does not require identical wall-clock timing on every host.

It requires that the semantic pass/fail condition can be reconstructed.

## Reliability is cumulative

No individual gate proves that an operating system is reliable.

Confidence increases when independent classes exercise overlapping invariants through different mechanisms:

    host tests
      + sanitizers
      + guest integration
      + fault injection
      + fuzzing
      + identified hardware

These classes are complementary because their blind spots differ.

## Current evidence boundary

At revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, ChrisOS has broad deterministic host gates, selected sanitizer paths, structured QEMU gates, ChrisVM tests, fault injection and deterministic fuzzing.

Physical-hardware validation remains less automated and configuration-specific.

Documentation should therefore use precise phrases such as:

- host-tested;
- QEMU-gated;
- ChrisVM-tested;
- tested on identified hardware;
- unverified on physical hardware.

Avoid the unqualified label "fully tested."

## Revision note

This chapter was reconciled against ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

The central rule is: **every validation claim should name its execution class, revision and oracle, and must not claim more than the environment actually demonstrated.**
