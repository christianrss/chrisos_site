---
id: fault-injection
lang: en
type: technical-chapter
volume: 14-validation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - makefile
  - tools/test_cfs_host.c
  - tools/test_elf_malformed.c
  - tools/test_fuzz_elf.c
  - user/fault.asm
  - tools/qemu_gate.py
  - scripts/qemu.mk
  - kernel/metal/panic.c
  - kernel/fs/storage.c
symbols:
  - panic
  - panic_exception
  - storage_format_if_empty
depends_on:
  - host-tests
  - qemu-gates
  - hardware-gates
related:
  - fuzzing
  - performance-measurement
  - process-isolation
  - chrisfs
---

# Negative testing and fault injection

## Scope

Fault injection asks a different question from ordinary success-path testing:

> What does ChrisOS do when an expected resource, input, device, allocation, or invariant fails?

At revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, ChrisOS already contains several useful negative-test mechanisms, but it does not yet have a general fault-injection framework shared across the kernel.

The current mechanisms are local and deterministic:

- block-I/O failure at a selected LBA;
- constrained allocation budgets while loading ELF images;
- deliberately malformed executable images;
- a deliberately faulting userspace ELF;
- negative QEMU topologies such as boot without the normal ATA root path;
- fatal-marker detection in integrated QEMU runs.

This is enough to test important failure paths, but not enough to claim systematic kernel-wide fault coverage.

## Fault model

A useful fault model separates failures by boundary:

| Boundary | Example fault | Current evidence |
|---|---|---|
| Storage | read/write returns I/O error | host ChrisFS test |
| Memory allocation | page allocation becomes unavailable | malformed/fuzz ELF tests |
| Executable format | invalid offsets, sizes, flags, overlap | malformed ELF test |
| Privilege boundary | userspace touches invalid address | fault ELF fixture |
| Device topology | expected device absent | QEMU no-ATA gate |
| Kernel safety | panic/exception/corruption marker | QEMU fatal scan |

The point is not to create arbitrary failure. The point is to violate one assumption at a time and verify that the subsystem preserves its contract.

## Determinism

The strongest current negative tests are deterministic.

Given the same revision and test input, they fail the same operation at the same point.

This property is essential because a failure that cannot be replayed is expensive to debug.

A useful fault-injection experiment is therefore:

[
F = (R, S, P, E)
]

where:

- (R) is the revision;
- (S) is the injected stimulus;
- (P) is the exact injection point;
- (E) is the expected externally observable result.

A future randomized injector should always print the seed and the chosen injection schedule so the run can be reproduced exactly.

## ChrisFS I/O injection

`tools/test_cfs_host.c` contains the clearest current fault-injection mechanism.

The fake block device uses:

    g_fail_lba

Both `fake_read` and `fake_write` return `BD_EIO` when the requested range contains that selected LBA.

The test can therefore force a storage failure without changing the ChrisFS implementation.

This separation is important: the production filesystem receives an ordinary block-device error through its normal interface.

## Mount failure

The host test formats a valid device and then sets:

    g_fail_lba = CFS_SUPER_LBA

Mount is expected to return:

    CFS_EIO

The test then clears the fault and verifies that mount succeeds.

This proves two properties:

1. the failure is propagated instead of being misclassified as a filesystem format error;
2. the failure does not permanently poison subsequent mount state.

## Write-path failure

The same test injects a failure at:

    CFS_BITMAP_LBA

A write of `Z.TXT` is expected to return:

    CFS_EIO

This exercises an error below the filesystem allocation/update path.

The current test is valuable but narrow: it injects a single LBA failure, not every possible write in a multi-step transaction.

## Unknown-media negative test

ChrisFS also tests a different failure class without simulated I/O loss.

The first bytes of the fake disk are filled with `0xFF`.

The prepare path must return:

    CFS_EFORMAT

and must not modify the unknown media.

This is a critical safety invariant:

> unrecognized media is not equivalent to blank media.

The test verifies that invalid/unknown content is rejected rather than silently formatted.

## Resource exhaustion

The filesystem host suite also creates many files until the data structure approaches capacity and checks maximum file-size/name constraints.

These are negative boundary tests rather than synthetic faults.

They verify that finite-resource conditions return defined errors rather than corrupting metadata.

Fault injection and boundary exhaustion belong in the same validation family because both force uncommon control-flow edges.

## ELF malformed-input testing

`tools/test_elf_malformed.c` constructs precise invalid ELF64 images.

The cases include:

- truncated file;
- invalid ELF magic;
- overflowing program-header offset;
- `filesz > memsz`;
- virtual-address overflow;
- file-offset overflow;
- zero-sized load segment;
- segment outside the allowed user range;
- overlapping load segments;
- unsupported program-header type;
- writable + executable segment;
- non-executable entry point.

These are structured negative tests.

They are stronger than random bytes for known invariants because each input has a named expected rejection reason.

## Allocation-failure injection

The malformed ELF test also contains a page-allocation budget.

`pmm_alloc` returns zero when the test budget is exhausted.

For the `oom mid` case the test sets:

    g_budget = 1

while loading an image that needs more memory.

The expected behavior is rejection with no leaked pages and no stale current process.

The important invariant is:

[
Delta pages = 0
]

after a failed load.

This converts out-of-memory handling from an assumption into executable evidence.

## ELF fuzz allocation pressure

`tools/test_fuzz_elf.c` reuses the allocation-budget idea during pseudo-random ELF inputs.

Each iteration records the current allocated-page count, constrains the budget, calls the real ELF loader and then checks failure cleanup.

This combines two stress dimensions:

- malformed binary data;
- partial resource availability.

That combination is particularly useful because cleanup bugs often appear only after some allocations have already succeeded.

## Deliberately faulting userspace image

`user/fault.asm` builds a valid ELF whose entry point executes an invalid memory access:

    mov rax, [0]

The image then contains a normal exit sequence that should never be reached if isolation and fault delivery work as intended.

This fixture is useful for validating privilege/fault handling on the real kernel path.

It is not, by itself, an automated host fault-injection test.

The evidence depends on how the image is launched and what the kernel records.

## Kernel fatal diagnostics

When a fatal kernel condition occurs, the current panic layer prints revision-bound architectural context.

`panic` records:

- CPU;
- CR3;
- RSP;
- Build ID;
- Git revision;
- kernel SHA-256.

`panic_exception` additionally records:

- exception vector;
- error code;
- RIP;
- CR2.

A fault-injection system should preserve this output verbatim because it links the injected stimulus to the exact failing instruction context.

## QEMU fatal-marker rejection

`tools/qemu_gate.py` rejects integrated runs containing fatal strings such as:

    PANIC:
    EXCEPTION vector=
    double fault
    general protection
    heap corruption
    PMM corruption

This is not fault injection by itself.

It is the oracle that prevents an injected or naturally occurring failure from being hidden after an earlier positive marker.

Negative experiments need both a stimulus and a reliable oracle.

## Negative topology as fault stimulus

`test-qemu-noata` deliberately removes the normal ATA root path.

The run must observe:

    ata missing

and still reach AHCI root, ChrisFS mount and the desktop.

This is better described as **negative topology testing** than device fault injection.

No ATA command is failed mid-flight; instead the expected device is absent from the machine configuration.

The distinction matters when reasoning about coverage.

## Safe mode as recovery experiment

The safe-mode QEMU gate is another negative-path tool.

It verifies that ChrisOS can boot with several optional capabilities disabled.

Safe mode is not an injected fault, but it provides a recovery/control experiment after failures involving SMP, APIC, audio, networking or JIT-related behavior.

A good fault campaign should always include a known reduced configuration to help localize the failing subsystem.

## Missing fault classes

The current repository does not yet provide a general mechanism for systematically injecting:

- every allocation failure point;
- short reads/writes;
- partial DMA completion;
- controller timeout;
- dropped interrupt;
- duplicate interrupt;
- delayed interrupt;
- MMIO read/write failure;
- corrupted PCI configuration;
- network packet loss/reordering/corruption;
- power loss during filesystem update;
- CPU stop/start anomalies;
- scheduler preemption at chosen instruction boundaries;
- random kernel API failures.

These remain roadmap areas.

## Crash consistency

The most important missing storage experiment is controlled crash/power-loss testing.

A filesystem may correctly propagate synchronous `EIO` while still corrupting state if execution stops between metadata updates.

A future crash-consistency harness should:

1. begin from a known image;
2. execute one filesystem operation;
3. terminate the guest at controlled write/flush boundaries;
4. reboot from the resulting image;
5. run fsck;
6. verify allowed old/new states;
7. reject impossible intermediate states.

This is a different problem from returning `BD_EIO`.

## Injection-point coverage

A useful future metric is not only line coverage but fault-point coverage.

For (N) explicit injection points:

[
C_f = rac{N_{exercised}}{N}
]

Each point should have:

- stable ID;
- subsystem;
- operation;
- default disabled state;
- deterministic activation condition;
- expected result;
- cleanup invariant.

Without stable IDs, fault campaigns become difficult to compare across revisions.

## Proposed kernel fault API

A future test-only facility could expose calls conceptually similar to:

    fault_point("pmm.alloc")
    fault_point("bdev.read")
    fault_point("bdev.write")
    fault_point("irq.delivery")
    fault_point("net.rx")

The production-disabled implementation would have near-zero semantic impact.

The test build could select:

- fail on the Nth call;
- fail in a count range;
- fail for a named device;
- delay rather than fail;
- corrupt a controlled field.

The selection state must never silently ship enabled in normal artifacts.

## Safety requirements

Fault injection can be destructive.

Physical storage injection must use disposable or cloned media.

Kernel builds with test-only failure hooks must be clearly identified.

A gate must distinguish:

    expected injected failure
    unexpected kernel failure
    test infrastructure failure

Treating all three as the same status destroys diagnostic value.

## Relationship to fuzzing

Fault injection and fuzzing overlap but are not identical.

Fault injection controls **environmental or resource failure**.

Fuzzing mutates **input space**.

A malformed ELF plus OOM budget uses both techniques at once.

Keeping the concepts separate helps answer whether a bug is caused by parser input, resource pressure or their interaction.

## Current coverage summary

At revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, ChrisOS has credible negative evidence for:

- ChrisFS I/O propagation;
- rejection of unknown media;
- filesystem capacity boundaries;
- ELF structural validation;
- ELF cleanup under allocation failure;
- malformed/random ELF cleanup;
- an explicit userspace page-fault fixture;
- negative ATA topology;
- fatal-marker rejection in QEMU.

It does not yet have kernel-wide injection scheduling or power-failure consistency testing.

## Highest-value next steps

The next fault-injection work should prioritize:

1. generic deterministic Nth-call allocation failure;
2. block-device short/error/flush-failure injection;
3. crash-consistency testing for ChrisFS;
4. QEMU reset at controlled storage checkpoints;
5. interrupt drop/delay hooks in virtual-hardware test builds;
6. structured injection IDs in logs;
7. automatic sweep over every registered fault point;
8. sanitizer execution of fuzz/fault cases where practical;
9. artifact retention for first failing seed/point;
10. eventual physical fault experiments only with dedicated hardware/media.

## Deterministic activation and failure artifacts

A fault campaign is most useful when the same source revision and activation rule reproduce the same failing transition.

Prefer deterministic controls such as:

    fail operation X on call N
    fail block request for LBA range R
    exhaust allocation budget after K successful pages

over unrecorded random failure.

When randomization is valuable, the seed and generated case must be retained.

The first failing run should preserve enough state to reproduce the experiment:

- source revision;
- injection-point identity;
- activation count or seed;
- machine/test configuration;
- serial or host log;
- mutated disk/image when relevant;
- expected oracle;
- observed exit status.

Without this artifact bundle, a rare injected failure can become impossible to distinguish from unrelated test infrastructure noise.

Determinism also makes regression repair measurable: after a fix, the exact previously failing point should pass before broader randomized exploration resumes.

## Revision note

This chapter was reconciled against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

The current project already exercises meaningful negative paths, especially ChrisFS I/O failure and ELF rejection/cleanup. The principal limitation is architectural: the mechanisms are local tests, not yet one systematic fault-injection framework spanning the kernel.
