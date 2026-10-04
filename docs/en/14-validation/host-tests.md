---
id: host-tests
lang: en
type: technical-chapter
volume: 14-validation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - makefile
  - tools/check_test_gates.py
  - tools/test_cfs_host.c
  - tools/test_pmm_cycle.c
  - tools/test_tlb_proto.c
  - tools/test_klog.c
  - tools/test_elf_malformed.c
  - tools/test_fuzz_cfs.c
  - tools/test_jit_bench.c
  - tools/host_metal/metal_stub.c
symbols: []
depends_on:
  - validation-evidence
related:
  - qemu-gates
  - fault-injection
  - fuzzing
  - performance-measurement
---

# Host-test architecture

## Scope

ChrisOS uses a large host-side test layer to exercise production algorithms without booting the kernel.

The principal aggregate target is:

    make host-gates

The target builds and executes tests for filesystems, memory protocols, concurrency helpers, language/runtime components, graphics algorithms, compiler/toolchain stages, malformed inputs, fuzz workloads and selected performance contracts.

Host tests are evidence about code semantics under a controlled process environment. They are not evidence that privileged CPU state, interrupt routing, DMA or physical hardware behave correctly.

## Host build model

The top-level makefile defines:

    HOST_CC := gcc
    HOST_CFLAGS := -std=c11 -Wall -Wextra -Werror ...

Most host tests compile the production C module under test directly into a normal userspace executable.

This architecture has two advantages:

1. the test executes the same algorithmic implementation used by the kernel instead of a separately reimplemented model;
2. failures are cheap to reproduce under ordinary debugging tools.

The main risk is environmental substitution. Kernel dependencies that cannot execute in userspace are replaced by stubs, synthetic memory, fake devices or host synchronization primitives.

A host result therefore proves the code reachable through that harness, not the complete kernel integration path.

## Aggregate gate graph

The `host-gates` target is a dependency graph rather than one monolithic executable.

Its prerequisites currently include families such as:

- ChrisFS format, mount, paths, indirect blocks, journal, chmod, locking and fsck;
- JIT, VM, native-code generation and benchmark checks;
- ChrisO, ChrisAsm, ChrisLd and KCC;
- graphics, shader, VirtIO queue and resource helpers;
- PMM/heap/SMP models;
- kernel-thread and job scheduling helpers;
- TLB protocol;
- klog/build identity/memory information;
- malformed ELF handling;
- socket ownership;
- fuzz tests;
- editor/debugger/runtime regressions;
- stability gates.

This layout isolates failure domains. A failed executable identifies a narrower subsystem than a whole-system boot failure.

## Gate reachability audit

A test target can exist in a makefile and still never run in continuous validation.

ChrisOS addresses this with:

    tools/check_test_gates.py

The script parses make rules, starts from the root target `host-gates`, follows prerequisite edges and reports test-like rules that are unreachable.

The relevant invariant is:

    every declared host test target intended for the suite
    must be reachable from host-gates

This checks orchestration, not test quality.

It prevents silent loss of coverage when a developer adds a test executable but forgets to wire it into the aggregate gate.

## Filesystem tests as fake-device tests

`tools/test_cfs_host.c` constructs a memory-backed `BlockDevice`.

Its fake read/write callbacks copy sectors between the filesystem and a host memory buffer.

The harness can inject I/O failure at a chosen LBA and can reset the complete synthetic disk between scenarios.

This makes several classes of behavior cheap to test:

- format and mount;
- persistence across remount;
- cache counters;
- directory growth;
- disk-full handling;
- read/write failure propagation;
- metadata invariants.

The useful design pattern is dependency substitution at the narrowest interface.

ChrisFS still sees the real block-device API. Only the controller/media layer is replaced.

## What a fake block device does not prove

A memory-backed disk cannot reproduce:

- real controller queue behavior;
- DMA ordering;
- volatile write caches;
- partial hardware completion;
- power loss between writes;
- firmware/controller reset;
- media error timing.

Therefore a passing host filesystem test is strong evidence for on-disk algorithms and error propagation through the abstract interface, but weak evidence for storage-controller integration.

## Memory allocator cycle tests

`tools/test_pmm_cycle.c` verifies allocator accounting across a large allocate/free cycle.

It records the initial number of free pages, allocates 1000 pages, checks the decrement, frees them and verifies:

    free_after == free_before

and:

    used + free == usable

This is an invariant-oriented test.

It does not merely confirm that one allocation returns nonzero; it checks conservation of allocator state over a complete cycle.

The complexity of the test itself is (O(n)) for (n) allocations and frees.

Its diagnostic value is high because a leaked or double-counted frame appears as an accounting mismatch at the end of the cycle.

## Host models for SMP-sensitive protocols

Some concurrency mechanisms are split so their state machine can run without real privileged instructions.

The TLB shootdown protocol is a strong example.

`tools/test_tlb_proto.c` exercises:

- publication of a new invalidation generation;
- acknowledgements from remote CPUs;
- timeout/fencing of a silent CPU;
- reuse blocking until required CPUs acknowledge;
- holes in the online CPU set;
- halted/fenced CPU transitions;
- heartbeat behavior.

These tests prove the protocol state machine.

They do not prove that:

- real IPIs are delivered;
- `invlpg` executed on the intended core;
- APIC ordering is correct;
- hardware memory ordering matches assumptions.

Those properties require QEMU or physical-hardware evidence.

## Host-metal substitution

Some kernel modules are compiled with:

    -DCHRIS_HOST_METAL

and linked with:

    tools/host_metal/metal_stub.c

This exposes a host-compatible model for low-level services.

The purpose is not to emulate x86-64 completely.

It is to make algorithmic state transitions testable while excluding privileged machine operations from the executable.

A test that uses host-metal stubs must document which boundary was substituted; otherwise a host pass can be mistaken for architectural integration evidence.

## Sanitizer layer

The makefile contains a `host-sanitize` target.

Selected tests are rebuilt with:

    -fsanitize=address,undefined

including memory/concurrency-oriented cases such as PMM/heap/SMP and kernel-thread/job paths.

AddressSanitizer and UndefinedBehaviorSanitizer add a different evidence class from ordinary assertions.

They can expose:

- out-of-bounds accesses;
- use-after-free in host-visible allocations;
- invalid shifts and arithmetic UB;
- some lifetime/aliasing faults.

They still operate under the host ABI and cannot detect violations that only occur in the freestanding kernel memory map or privileged execution path.

## Negative parser and loader tests

`tools/test_elf_malformed.c` deliberately constructs invalid ELF inputs.

Cases include malformed or inconsistent:

- magic;
- program-header offsets;
- segment sizes;
- virtual-address ranges;
- file offsets;
- unsupported segment types;
- overlapping mappings.

The harness also tracks resource state around rejected loads.

A failed parse is only correct when rejection does not leak process-owned frames or leave process state inconsistent.

This is stronger than checking only an error code.

## Deterministic fuzz-style tests

ChrisOS also uses bounded pseudo-random tests.

`tools/test_fuzz_cfs.c` begins from a fixed PRNG seed and generates a series of path mutations and filesystem operations before running fsck.

The fixed seed makes the workload reproducible.

This is not coverage-guided fuzzing. It is a deterministic adversarial workload.

Its value is regression detection over unusual inputs while retaining a stable reproduction path.

A later fuzzing layer can add corpus mutation and coverage guidance without replacing this deterministic gate.

## Kernel log tests

`tools/test_klog.c` verifies both ordinary copying and ring-wrap behavior.

The critical capacity invariant is:

    klog retained bytes <= 8192

After more than one ring capacity is written, the test checks that the copied length is exactly 8192 bytes and that the newest byte is retained.

This isolates ring-buffer semantics from serial hardware and filesystem persistence.

Serial transmission and persistence of `SYS/BOOT.LOG` remain integration concerns.

## Compiler and runtime tests

A large fraction of the host suite covers the ChrisC/CLVM/native-toolchain stack.

Host tests are particularly effective here because parsing, semantic analysis, bytecode generation, object generation, linking and much of JIT code generation are ordinary deterministic transformations.

Useful invariants include:

- malformed input is rejected;
- generated object metadata is internally consistent;
- relocation/link results preserve symbol semantics;
- VM and JIT executions agree on observable results;
- pointer-width behavior remains stable;
- debugger/source mapping does not regress.

This layer catches many errors before a kernel boot is necessary.

## JIT performance gate

`tools/test_jit_bench.c` is not only a functional test.

It runs an interpreted workload and a JIT-compiled form and requires:

    speedup >= 5.0x

for the host benchmark configuration.

The benchmark uses a monotonic host clock and repeated rounds.

This is a performance regression guard, not an absolute ChrisOS hardware performance result.

Its result depends on:

- host CPU;
- host compiler;
- optimization flags;
- thermal/frequency state;
- operating-system scheduling;
- architecture.

A threshold gate is useful when the environment is reasonably controlled, but benchmark numbers should not be compared across unrelated machines as if they described kernel performance.

## Graphics host tests

Graphics algorithms are good host-test candidates because many operations are pure memory transformations.

The suite covers components such as:

- 2D drawing;
- matrix/vector math;
- depth buffering;
- triangles and meshes;
- tile/bin processing;
- shader and IR behavior;
- VirtIO queue/resource command construction.

A host framebuffer array can validate exact pixel or depth results.

It cannot prove the boot framebuffer mapping, VirtIO-GPU transport, VirGL host stack or a physical GPU.

## Concurrency caveat

Host threading is useful but not identical to the kernel execution model.

Differences include:

- scheduler policy;
- signal/interrupt behavior;
- privilege level;
- APIC delivery;
- TLB semantics;
- page-table ownership;
- cache topology;
- compiler and libc environment.

A host race test can reveal a synchronization defect.

A host pass cannot prove absence of races under SMP kernel execution.

## Failure semantics

Host tests conventionally communicate through process exit status:

    0  success
    !=0 failure

They also print a subsystem-specific diagnostic before failing.

This creates a simple CI contract.

The diagnostic should identify the violated invariant rather than only print a generic "failed" message.

## Reproducibility contract

A useful host test should be:

- deterministic unless randomness is explicitly part of the subject;
- self-contained or explicit about fixtures;
- independent of developer-local state;
- bounded in runtime;
- noninteractive;
- strict about return code;
- explicit about the invariant checked.

When pseudo-random input is used, the seed should be fixed or emitted.

## What host tests are best at

Host tests provide the strongest cost/feedback ratio for:

- parsers;
- compilers;
- filesystems over abstract block devices;
- allocators and accounting;
- protocol state machines;
- pure graphics/math;
- serialization and object formats;
- deterministic runtime semantics;
- negative-input handling.

They are weaker for:

- boot;
- interrupts;
- privileged transitions;
- DMA;
- MMIO timing;
- actual SMP/TLB invalidation;
- firmware contracts;
- physical devices.

## Evidence promotion

A feature should progress through evidence layers rather than replacing one with another:

    host invariant test
        -> QEMU integration gate
        -> physical observation
        -> repeatable hardware gate

A QEMU gate does not make the host test redundant.

The host test remains the cheaper failure-localization layer.

Likewise, a physical pass does not make deterministic algorithm tests unnecessary.

## Current host validation command

The canonical aggregate command in the reviewed source is:

    make host-gates

A broader stability run includes sanitizer coverage and, when QEMU is installed, can extend into QEMU stress gates through the `stability` target.

Documentation should record the exact target used when citing evidence.

## Revision note

This chapter was reconciled against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

At this revision, the host suite is a substantial first validation layer with explicit aggregation, an orphan-test audit, deterministic negative testing, sanitizer variants, fuzz-style workloads and performance guards. Its results must remain classified as host evidence until the corresponding integrated behavior is exercised under QEMU or physical hardware.
