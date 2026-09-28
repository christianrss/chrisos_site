---
id: testing-validation
lang: en
type: guide
status: maintained
reviewed_revision: 92fb561574bd929522ea005b9fd433138bea3236
sources:
  - docs/development/testing.md
  - scripts/qemu.mk
  - makefile
depends_on:
  - build-run-debug
---

# Testing and validation

ChrisOS uses multiple test classes because no single environment can prove every systems claim. A host-side unit test can validate an algorithm or parser without booting the kernel; a QEMU gate can validate a guest path against an emulated device; ChrisVM can validate the project-owned machine model; only an identified physical system can establish hardware evidence.

The test chosen should match the claim being made.

## Evidence hierarchy

| Evidence class | What it establishes | What it does not establish |
|---|---|---|
| source present | implementation text exists | successful execution |
| host-tested | host-executed logic passed | guest integration or hardware behavior |
| QEMU-tested | declared guest path ran in a named virtual configuration | arbitrary physical compatibility |
| ChrisVM-tested | behavior passed in the project-owned emulator/machine model | QEMU or physical-hardware equivalence |
| hardware-tested | path ran on identified hardware | universal device compatibility |

Use the narrowest class that proves the intended claim, then expand when the change crosses more boundaries.

## Host gates

The broad host-side set is:

~~~bash
make host-gates
~~~

The repository also exposes narrower host targets for filesystem, compiler, runtime, graphics/math and other components. A contributor should prefer the target nearest to the changed code while iterating.

Host gates are especially useful for deterministic data-structure, file-format and compiler/runtime logic. They run faster than a guest boot and make memory errors easier to isolate.

Where available, sanitizers and stress targets add a different kind of evidence:

~~~bash
make host-sanitize
make host-stress
~~~

A sanitizer pass is complementary to functional tests; it does not replace semantic expectations.

## QEMU gates

The broad integration set is:

~~~bash
make qemu-gates
~~~

The maintained QEMU gate configuration uses TCG unless a target explicitly requires another capability. This makes the integration suite portable across developer machines that do not expose KVM.

Individual gates should be used first when a subsystem is known:

~~~bash
make test-qemu-ata
make test-qemu-ahci
make test-qemu-nvme
make test-qemu-vblk
make test-qemu-usb
make test-qemu-gpu
make test-qemu-xhci
make test-qemu-safe
make test-qemu-install
~~~

The gate runner records serial output and checks expected markers. A timeout or missing marker should be diagnosed from the log rather than reduced to a generic "QEMU failed" statement.

## ChrisVM

For the project-owned emulator and machine model:

~~~bash
make chrisvm-test
~~~

When changing ChrisCPU, ChrisVM buses, device models, boot semantics or tracing, this suite is often the first relevant gate.

A ChrisVM pass and a QEMU pass are independent pieces of evidence. Keeping them separate helps identify whether a defect belongs to the guest, the emulator or the virtual-hardware contract.

## VirGL

VirGL depends on host graphics capabilities:

~~~bash
make test-qemu-virgl
~~~

The target may report a capability skip. Record a skip as "not tested on this host", not as a pass. If a pull request changes VirGL-specific code and the author cannot provide a capable host, the missing evidence should be stated explicitly.

## Broad local validation

A broad local sequence is:

~~~bash
make host-gates
make qemu-gates
make chrisvm-test
~~~

The repository also provides:

~~~bash
make full-gates
~~~

Use broad validation before merge for changes with wide impact, but do not wait for the full suite to locate an obvious local regression.

## Physical hardware

Hardware testing needs more context than "works on my PC". Record enough information for the observation to be meaningful:

~~~text
Machine / board:
CPU:
Firmware mode and version:
Storage controller/device:
GPU/display path:
Relevant USB/network devices:
Commit:
Command or boot procedure:
Observed result:
Serial or diagnostic evidence:
~~~

A QEMU driver gate cannot prove compatibility with arbitrary physical implementations of the same standard.

## Negative testing

Systems code should be tested for failure behavior, not only success behavior. Useful negative cases include malformed on-disk metadata, allocation exhaustion, truncated input, invalid descriptors, missing optional devices, failed writes and invalid guest inputs.

If the repository already has a negative or fault-injection target for the changed path, run it. If the change introduces a new boundary whose failure mode matters, adding a focused regression test is usually preferable to documenting an untested assumption.

## Record exact evidence

A pull request should say exactly what ran:

~~~text
Host: Ubuntu 24.xx x86-64 / WSL2 / other
Commit: <sha>
Compiler: gcc <version>
QEMU: <version>
Tests:
  make host-...
  make test-qemu-...
Results:
  PASS / FAIL / SKIP
Not tested:
  VirGL / hardware / RISC-V / other
~~~

Avoid phrases such as "all tests pass" when only one subset was executed.

## CI limitations

Hosted CI exercises a focused subset and should not be assumed to cover every QEMU, graphics, virtualization or hardware path. Local evidence still matters for changes whose relevant environment is not available in CI.

The absence of a CI target is not permission to omit validation. It means the contributor should state the evidence gap and, when possible, provide a deterministic local command that another maintainer can run.

## Regression tests

When fixing a bug, a good regression test should fail for the old behavior and pass for the corrected behavior. Prefer tests close to the failing invariant. A kernel panic reproduced only after a long desktop session may still have a small host-testable cause.

Regression tests also serve documentation: they encode the condition that must remain true after future refactoring.

## Interpreting success

Build success means the toolchain produced artifacts. Host-test success means selected host logic executed correctly. QEMU-gate success means a declared virtual guest path reached expected markers. ChrisVM success means the emulator/machine tests passed. Hardware success means a specific physical configuration was observed.

Keep those statements separate. The project's evidence model is designed to prevent implementation presence or one test environment from being promoted into a broader capability claim than the evidence supports.
