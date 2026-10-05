---
id: build-run-debug
lang: en
type: guide
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - docs/getting-started/build-and-run.md
  - makefile
  - scripts/qemu.mk
  - scripts/check-dev-env.sh
depends_on:
  - developer-guide
---

# Build, run and debug

ChrisOS has multiple build and execution paths. Selecting the narrowest path that exercises the modified subsystem reduces iteration time and makes failures easier to classify.

## Core artifacts

From the repository root:

~~~bash
make
~~~

The default target produces build/os.iso. The kernel can be built separately:

~~~bash
make kernel
~~~

The persistent ChrisFS workspace disk is:

~~~bash
make disk.img
~~~

These commands establish different facts. Kernel compilation does not prove ISO construction; ISO construction does not prove boot; a boot does not prove a specific device or filesystem path.

## Interactive QEMU

The standard interactive target is:

~~~bash
make run
~~~

At the reviewed revision, this target prepares the required artifacts, starts x86-64 QEMU with the project's normal virtual-device set, routes the guest serial stream to the terminal and requests KVM acceleration.

If make run fails before any ChrisOS serial output appears, first determine whether QEMU started successfully. Missing KVM access, an unavailable display backend, an invalid host QEMU option or an absent artifact is a host-side failure.

A guest failure begins only after the virtual machine is actually executing ChrisOS.

## Portable headless execution

For reproducible integration work, prefer maintained gates. The common smoke path is:

~~~bash
make test-qemu-ata
~~~

The gate uses TCG, writes serial output to build/qemu-test.txt and checks explicit progress markers.

Broader sets are:

~~~bash
make host-gates
make qemu-gates
make full-gates
~~~

Run the narrow test first. A large suite is confirmation after the relevant invariant is stable, not the best first diagnostic.

## Device-specific QEMU gates

scripts/qemu.mk defines separate paths for major device and boot configurations. Examples include:

~~~bash
make test-qemu-ahci
make test-qemu-nvme
make test-qemu-vblk
make test-qemu-usb
make test-qemu-gpu
make test-qemu-xhci
make test-qemu-safe
make test-qemu-install
~~~

These gates provide QEMU-model evidence. They do not prove physical-device compatibility.

## ChrisVM

The project-owned emulation path has separate targets:

~~~bash
make chrisvm
make chrisvm-test
~~~

Keep ChrisVM failures conceptually separate from QEMU failures. A change can break the emulator without breaking the guest under QEMU, or ChrisVM can expose a guest assumption that a QEMU model happens to tolerate.

## RISC-V bring-up

The RISC-V path is:

~~~bash
make riscv
make run-riscv
~~~

This is a bring-up target, not feature parity with the x86-64 system. Its results should be described as architecture-specific evidence.

## Serial-first debugging

The serial stream is the primary early diagnostic path. Interactive make run sends it to the terminal; headless gates capture it into a build log.

When a gate fails:

1. preserve the first failing log;
2. identify the last successful marker;
3. rerun the narrowest gate;
4. classify the failure as host-side or guest-side;
5. instrument the smallest relevant path;
6. turn useful temporary diagnostics into intentional logging or remove them before merge.

Avoid replacing a deterministic check with visual observation of the desktop.

## GDB status

The repository does not currently define GDB as a maintained first-class validation target. QEMU can expose a remote GDB stub in generic configurations, and a contributor may use that facility locally, but an ad-hoc QEMU command line is a debugging technique rather than a project test result.

Do not report a local GDB session as equivalent to a maintained gate. If a stable project-level GDB workflow is added later, it should have a reproducible target and documentation close to the build system.

## Safe mode

The QEMU test suite includes a safe-mode image path. Safe mode is useful when optional subsystems obscure a lower-level boot problem.

If a normal configuration fails while the safe-mode gate succeeds, compare the initialization paths that safe mode disables instead of reopening reset, bootloader and basic memory assumptions from scratch.

## VirGL

The graphics integration gate is:

~~~bash
make test-qemu-virgl
~~~

It first checks host capabilities and may skip when the QEMU binary or host display/GL stack cannot provide the required environment.

Treat outcomes distinctly:

| Result | Meaning |
|---|---|
| pass | declared guest expectations were observed |
| fail | the test ran but an expectation failed |
| skip | the host could not supply the VirGL test environment |

A skip is not a pass.

## Clean versus incremental builds

Generated artifacts can make a failure look inconsistent with source changes. When stale output is plausible:

~~~bash
make clean
make
~~~

However, clean builds should not hide missing dependency declarations. If an incremental build fails to rebuild a file that should have changed, the build graph itself needs correction.

## Disk-image discipline

build/disk.img and the temporary images created by QEMU gates are disposable developer artifacts. Physical-disk installation is a separate operation and should never be substituted casually for ordinary build testing.

Stop QEMU before performing offline modifications to the workspace image. Use the repository-provided host or live transfer mechanisms according to the current build guide.

## Preserve the first failing artifact

When a run fails, keep the first log or image that demonstrates the failure before repeatedly changing flags or rebuilding.

A later rerun may change timing, regenerate a disk image or overwrite the serial log. Preserving the first artifact makes it possible to compare the last successful marker, the first failing marker and the source revision that produced them.

If the failure disappears after `make clean`, record that fact. It may indicate stale generated state or an incomplete build dependency rather than a guest logic defect.

## Re-run discipline

After changing source in response to a failure, rerun the same narrow gate first. Do not jump directly to a broader suite, because a broad pass can hide whether the original failure condition was actually exercised.

A useful debug sequence is:

1. reproduce the original failure;
2. preserve its artifact;
3. apply the smallest change;
4. rerun the identical command;
5. confirm the previous failure point is now crossed;
6. only then run wider regression gates.

This keeps the causal link between defect and fix visible.

## Debugging from the last known milestone

When serial output stops, do not restart analysis from reset unless the evidence points there. Use the last confirmed milestone to bound the search interval.

For example, if memory initialization, storage discovery and filesystem mount markers are present but the desktop marker is absent, investigate the code executed after mount first. This narrows the candidate set and prevents unrelated early-boot subsystems from consuming debugging time.

After adding temporary instrumentation, keep marker names specific to the state being proven and remove or formalize them before merge.

## Failure classification

| Symptom | First layer to inspect |
|---|---|
| command not found | host environment |
| compiler or linker diagnostic | toolchain/build |
| xorriso error | image construction |
| QEMU exits before serial | host QEMU, display or acceleration |
| serial begins then panic | guest kernel/subsystem |
| timeout with partial markers | guest progress or test expectation |
| VirGL skip | host graphics capability |
| host test failure | host-executed algorithm or format logic |
| ChrisVM-only failure | emulator or machine model |

This classification avoids a common systems-development error: debugging guest code for a problem that happened before the guest executed.
