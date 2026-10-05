---
id: developer-guide
lang: en
type: guide
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - CONTRIBUTING.md
  - docs/README.md
  - docs/getting-started/environment.md
  - docs/getting-started/build-and-run.md
  - docs/development/workflow.md
  - docs/development/testing.md
depends_on: []
---

# Developer Guide

This guide is the canonical entry point for building, running, testing and contributing to ChrisOS. It treats the development environment as a reproducible engineering system rather than a package checklist. The host toolchain produces a freestanding x86-64 kernel and host utilities, QEMU supplies controlled machine models for integration tests, ChrisVM supplies the project-owned machine/emulation path, and Git plus the test gates define how a change becomes reviewable evidence.

Operational commands that can change with the source tree remain close to the code in the ChrisOS repository. This guide explains how those commands fit together, which host configurations are reference paths, how to classify failures, and what evidence a contributor should produce before opening a pull request.

## Reference host model

The lowest-friction host is a recent x86-64 Debian or Ubuntu Linux system. Windows contributors should use WSL2 with an Ubuntu distribution for the GNU-oriented build. Native Windows shells are not currently the reference build environment because the top-level build assumes GNU Make, GCC/binutils, NASM, shell utilities, xorriso and Linux-oriented QEMU workflows.

The distinction matters. A platform can compile source files without reproducing the complete ChrisOS workflow. Development also includes ISO construction, disk-image manipulation, host-side tests, QEMU device models, optional KVM acceleration, OVMF-based UEFI tests and optional graphics paths such as VirGL.

| Host configuration | Build | Host tests | Headless QEMU gates | Interactive QEMU | Status |
|---|---:|---:|---:|---:|---|
| Debian/Ubuntu x86-64 | yes | yes | yes | yes | reference |
| Windows + WSL2 Ubuntu | yes | yes | yes with QEMU installed | host-dependent | supported development path |
| Native Windows shell | not canonical | not canonical | not canonical | helper-specific | not the reference workflow |
| Other Linux distributions | usually possible | usually possible | package-dependent | package-dependent | contributor-maintained |

## Development flow

A normal contribution should move through a narrow-to-broad sequence:

~~~text
clone
  ↓
verify host tools
  ↓
build the narrow target
  ↓
run the narrowest relevant test
  ↓
inspect serial/test evidence
  ↓
run broader gates
  ↓
update canonical documentation when behavior changes
  ↓
open a focused pull request
~~~

The first environment check is:

~~~bash
./scripts/check-dev-env.sh
~~~

It verifies the required commands git, make, gcc, ld, nasm, xorriso, qemu-system-x86_64 and python3. It also reports optional capabilities such as RISC-V QEMU, Clang/LLD, SDL and access to /dev/kvm.

A basic system build is:

~~~bash
make
~~~

The default target produces build/os.iso. A persistent ChrisFS workspace image can be produced with:

~~~bash
make disk.img
~~~

The interactive path is:

~~~bash
make run
~~~

At the reviewed source revision, the interactive recipe requests KVM. A machine without usable /dev/kvm should not interpret that acceleration failure as a kernel failure. The maintained headless integration gates use TCG and are the portable validation path:

~~~bash
make test-qemu-ata
make qemu-gates
~~~

## What to read next

Use [Linux development environment](linux-development-environment.md) for a native Linux workstation and [Windows and WSL2 development environment](windows-wsl-development-environment.md) for Windows. After the host is ready, [Build, run and debug](build-run-debug.md) explains the artifact graph, execution modes, serial diagnostics and the difference between a host failure and a guest failure.

[Testing and validation](testing-validation.md) defines the evidence hierarchy and the progression from narrow host tests to QEMU or ChrisVM gates. [Contribution workflow](contribution-workflow.md) defines branches, scope, documentation ownership and pull-request evidence. [Development troubleshooting](troubleshooting.md) maps common failures to the layer that should be investigated first.

## Repository and documentation ownership

ChrisOS separates operational source-tree documentation from the canonical technical corpus.

The ChrisOS repository owns instructions that must remain synchronized with exact command names: setup commands, build and run mechanics, test target names, contribution mechanics and security reporting. The chrisos_site repository owns architecture, subsystem behavior, interfaces, validation interpretation, research context, educational material and this developer guide.

A code change that alters a command should update repository-local operational documentation. A code change that alters architecture or behavior should update the canonical site. Non-trivial changes may require both.

## Evidence before convenience

The project uses several execution environments and each establishes a different class of evidence. A host test proves host-executed logic. A QEMU gate proves a declared guest path under a particular virtual machine configuration. ChrisVM tests prove behavior in the project-owned emulator and machine model. Hardware evidence requires an identified physical machine and device profile.

Do not collapse these into one "works" label. A useful contribution record contains:

~~~text
Commit:
Host:
Compiler/tool versions:
Command:
Result:
Relevant serial/test marker:
Not tested:
~~~

For physical hardware, also record firmware mode and relevant device identities.

## Generated output

The build/ tree is disposable. It contains object files, boot images, host binaries, test logs, user binaries and ChrisVM artifacts. Generated ISO images, disk images, object files and transient logs do not belong in source-control commits.

Use:

~~~bash
make clean
~~~

when a stale artifact is a plausible cause of a failure.

## Baseline before modification

Before changing a subsystem, record a known-good baseline for the narrowest relevant gate. This separates a pre-existing failure from a regression introduced by the patch.

A useful baseline note includes the source revision, command and result. If the target already fails, preserve that evidence and do not describe the later patch as the cause until the failure is reproduced against both revisions.

## Scope discipline

ChrisOS spans a kernel, memory manager, storage stack, filesystem, language/runtime components, graphics, desktop, networking, native tools and machine emulation. A contributor should identify the owning subsystem before changing code and avoid crossing architectural boundaries only to make a local symptom disappear.

A useful patch is narrow enough that its claim can be tested. A VirtIO-GPU change should prefer the GPU-specific gate before the entire QEMU suite; a ChrisFS path-resolution change should prefer the relevant host filesystem test before a full guest boot. Broad gates are confirmation, not a substitute for locating the invariant being modified.

The development environment is therefore part of the engineering method: it exists to make each claim reproducible, reviewable and attributable to a specific source revision.
