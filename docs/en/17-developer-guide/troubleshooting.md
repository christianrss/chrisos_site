---
id: development-troubleshooting
lang: en
type: guide
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - docs/getting-started/environment.md
  - docs/getting-started/build-and-run.md
  - docs/development/testing.md
  - scripts/check-dev-env.sh
  - scripts/qemu.mk
  - makefile
depends_on:
  - build-run-debug
---

# Development troubleshooting

Troubleshooting ChrisOS is easier when failures are classified by layer before code is changed. A failed command can originate in the host environment, compiler, linker, image builder, QEMU process, boot path, kernel, device driver, filesystem, emulator or test expectation.

The first task is therefore to locate the earliest layer that stopped behaving as expected.

## Start with the environment checker

Run:

~~~bash
./scripts/check-dev-env.sh
~~~

If a required command is missing, resolve that before investigating guest code.

Capture tool versions when the failure may be host-specific:

~~~bash
gcc --version
ld --version | head -n 1
nasm -v
qemu-system-x86_64 --version | head -n 1
git rev-parse HEAD
~~~

The source revision and tool versions are part of the bug report.

## Command not found

A missing gcc, ld, nasm, xorriso, qemu-system-x86_64 or python3 is a host setup failure. Use the package instructions from the Linux or WSL2 setup chapter.

Do not modify the Makefile merely to bypass a missing required dependency unless the goal is an intentional portability change.

## Compiler warnings promoted to errors

The build uses strict warnings in important host components. If a newer compiler diagnoses something that an older compiler did not, preserve the exact diagnostic.

Check whether the warning identifies a real bug before attempting a compiler-version workaround. The cloud-agent bootstrap records GCC 11 as a known-good configuration for one warning-sensitive path, but global warning suppression is not an acceptable fix.

## Linker errors

Undefined symbols generally indicate one of four classes of problem:

- missing object in the link set;
- declaration/definition mismatch;
- conditional build logic excluded a required source;
- an architectural layer now depends on a symbol it should not own.

Inspect the first undefined symbol and its intended owner before adding libraries or objects indiscriminately.

## xorriso or ISO failures

If compilation succeeds but ISO construction fails, the kernel may be correct. Check xorriso availability, Limine assets and the staged ISO tree.

Classify image-construction errors separately from guest boot errors.

## make run fails immediately

If no ChrisOS serial output appears, inspect host QEMU startup first.

Common host causes include:

- /dev/kvm absent or inaccessible;
- unsupported QEMU display backend;
- missing or stale build image;
- host QEMU lacking an optional device;
- graphics/GL capability missing.

Use a headless TCG gate to separate host interactive configuration from guest functionality:

~~~bash
make test-qemu-ata
~~~

If that passes while make run fails before serial output, the investigation belongs primarily to the interactive host configuration.

## KVM unavailable

KVM is optional for the maintained TCG gates. If /dev/kvm is unavailable:

~~~bash
make test-qemu-ata
make qemu-gates
~~~

remain valid portable paths.

Do not run QEMU as root simply to obtain /dev/kvm access without understanding the host permission problem.

## QEMU gate timeout

Open build/qemu-test.txt and identify the last successful marker. A timeout is often more informative when expressed as "boot reached X but never reached Y".

Rerun the narrow target before changing code. If the timeout is deterministic, instrument the transition between the final observed marker and the missing one.

## Panic after serial startup

Once ChrisOS serial output begins, the guest is running. Preserve the panic and the preceding initialization messages.

Map the last completed subsystem to the owning source area. Avoid broad refactoring until the failure can be reproduced with the smallest relevant configuration.

Safe mode can help distinguish optional subsystem initialization from lower-level boot behavior.

## VirGL skip

A VirGL skip is usually a host capability result. Check QEMU device availability, EGL/GTK support, display variables and render-node availability.

Do not change guest shader or VirtIO-GPU code to solve a host that cannot create the required GL device.

## WSL2 GUI failure

A successful WSL2 build plus a passing headless QEMU gate already proves that the basic build and guest smoke path work. If only the GUI fails, investigate WSLg, QEMU display backend and acceleration separately.

Keep the repository in the WSL filesystem and ensure the QEMU binary being invoked is the Linux one installed in WSL.

## Stale build behavior

When the result seems inconsistent with source:

~~~bash
make clean
make
~~~

If a clean build fixes an incremental build repeatedly, the project may have a dependency-graph defect. Do not normalize a required clean build if the dependency should be expressible correctly.

## Disk image appears corrupted

Stop all QEMU instances using the image before host-side modification. Confirm that the operation is targeting build/disk.img or another disposable test image, not a physical device.

Use the project's supported image manipulation targets instead of unrelated filesystem tools that do not understand ChrisFS.

## ChrisVM-only failure

If QEMU passes but ChrisVM fails, isolate the emulator/machine contract. Run:

~~~bash
make chrisvm-test
~~~

and use the smallest failing fixture. Do not assume the guest is correct merely because QEMU accepted it; emulator work often exposes implicit assumptions.

## QEMU-only failure

If host tests and ChrisVM pass but a QEMU gate fails, compare the virtual device or boot contract specific to QEMU. The difference may be in guest driver behavior, machine configuration or assumptions made by the project-owned emulator.

## Test passes locally but CI fails

Record local compiler and tool versions, then compare the CI environment and the exact failing command. Avoid adding timing sleeps or disabling strict diagnostics before understanding the environmental difference.

A deterministic test should be repaired at the invariant that differs, not made less precise until it becomes green.

## Minimal issue report

Provide:

~~~text
Host:
WSL2/native Linux/other:
Commit:
gcc:
ld:
nasm:
QEMU:
Command:
First relevant error:
Last serial marker:
Reproducible after make clean: yes/no
Relevant log attached:
~~~

For hardware problems, add machine, firmware and device identities.

## Troubleshooting rule

Always preserve the first meaningful failure. The final error line often reflects only propagation. In systems development, the earliest incorrect transition is usually closer to the defect than the largest visible symptom.
