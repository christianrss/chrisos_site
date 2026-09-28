---
id: development-environment-windows
lang: en
type: guide
status: maintained
reviewed_revision: 92fb561574bd929522ea005b9fd433138bea3236
sources:
  - docs/getting-started/environment.md
  - docs/getting-started/build-and-run.md
  - scripts/check-dev-env.sh
  - run.bat
  - makefile
depends_on:
  - developer-guide
---

# Windows and WSL2 development environment

The recommended Windows development path is Windows with WSL2 and an Ubuntu distribution. The ChrisOS build system is GNU-oriented and documented against Linux tools; WSL2 lets a Windows workstation execute that environment with fewer translation layers than a native PowerShell, MSYS2 or MinGW reconstruction.

Compilation, headless integration testing and interactive accelerated virtualization are separate capabilities. WSL2 can be suitable for the first two even when KVM or graphics support is not available for the third.

## Install the Linux toolchain inside WSL2

After installing WSL2 and an Ubuntu distribution through the supported Windows WSL setup flow, open the Ubuntu shell and install the same baseline packages used by native Debian/Ubuntu development:

~~~bash
sudo apt update
sudo apt install   build-essential   binutils   nasm   xorriso   qemu-system-x86   qemu-utils   python3   git   ovmf
~~~

Then clone and validate the environment from inside WSL:

~~~bash
git clone https://github.com/christianrss/ChrisOS.git
cd ChrisOS
./scripts/check-dev-env.sh
~~~

The checker is the project-level authority for required command availability and separately reports optional capabilities.

## Keep the working tree in the Linux filesystem

For this build, prefer a working tree below the WSL Linux home directory instead of building from a Windows-mounted directory:

~~~bash
cd ~
git clone https://github.com/christianrss/ChrisOS.git
~~~

This preserves Linux executable bits, permissions, path semantics and shell behavior and avoids unnecessary cross-filesystem overhead during large builds.

A Windows editor can still open the WSL workspace through its WSL integration. The important boundary is that Git, Make, GCC, xorriso, Python and QEMU acting on the repository are the Linux versions.

## The role of run.bat

The repository contains run.bat, but it is intentionally tiny:

~~~text
@echo off
REM Boot ChrisOS via make (build/os.iso + build/disk.img)
make run
~~~

This file does not implement a native Windows toolchain. It delegates to Make. A Windows shell that lacks the GNU-oriented build dependencies still lacks the environment required by the project.

The canonical Windows development path is therefore WSL2, not run.bat by itself.

## Build and smoke-test under WSL2

Start with the same sequence used on native Linux:

~~~bash
./scripts/check-dev-env.sh
make
make disk.img
make test-qemu-ata
~~~

The last command is especially useful because the maintained QEMU gate uses TCG. TCG is software CPU emulation and does not require /dev/kvm.

A passing gate establishes more than a successful compile: ChrisOS artifacts were constructed, QEMU started under the declared headless configuration, the guest executed, and required serial markers were observed.

## KVM under WSL2

The interactive make run recipe at the reviewed revision requests KVM. Whether /dev/kvm exists and is usable in WSL depends on the Windows and WSL virtualization environment and must be detected rather than assumed.

Check:

~~~bash
./scripts/check-dev-env.sh
ls -l /dev/kvm 2>/dev/null || true
~~~

If KVM is unavailable, an acceleration error from make run is a host capability issue, not a ChrisOS kernel regression. Use the TCG-based test targets for portable validation.

A contributor can derive a local TCG QEMU command for interactive investigation, but an ad-hoc command is not the same as a maintained project target. If the project changes the canonical run recipe, update the repository-local build documentation with it.

## Display backends and WSLg

Interactive QEMU also needs a usable display backend. The makefile uses a GTK-oriented default and contains an SDL-oriented note for Windows environments without GTK.

WSLg can make Linux GUI applications available on Windows, but the actual QEMU display and OpenGL capabilities still depend on the installed QEMU build and the Windows graphics stack. Treat display support independently from compilation and headless guest execution.

For kernel, memory, filesystem, networking and most driver work, headless gates should be the first validation path.

## VirGL

VirGL adds a second host graphics requirement. The maintained gate checks that QEMU exposes a GL-capable VirtIO GPU and that a usable EGL or GTK path exists. A skipped VirGL test means the host cannot provide the test environment. It is neither a guest pass nor a guest failure.

Do not spend time making VirGL work before validating an unrelated storage or kernel change.

## Recommended Windows architecture

~~~text
Windows
├─ browser and GitHub
├─ editor / IDE
└─ WSL integration
      ↓
WSL2 Ubuntu
├─ git
├─ make
├─ gcc / ld
├─ nasm
├─ xorriso
├─ python3
└─ qemu-system-x86_64
      ↓
ChrisOS build artifacts and test logs
~~~

This preserves Windows desktop convenience while keeping the build and test semantics aligned with Linux.

## Line endings and executable permissions

Do not convert shell scripts to CRLF as part of unrelated edits. Do not remove executable permissions from repository scripts. If a shell reports an interpreter error for an existing script, inspect line endings and file mode before changing its logic.

The same rule applies to generated patches: avoid broad editor-driven formatting changes that obscure the actual contribution.

## Native Windows status

A complete native-Windows development path would require an intentionally maintained contract for compiler/linker tools, Make or an alternative build runner, shell scripts, xorriso-equivalent image tooling, Python invocation, QEMU device and display configuration, path semantics and tests.

Until such a path is maintained and tested, native Windows parity should not be claimed.

Portability contributions are useful when they preserve the reference Linux path and include reproducible evidence for the additional host.

## Windows contributor readiness

A WSL2 environment is ready for ordinary source contributions when this sequence succeeds:

~~~bash
./scripts/check-dev-env.sh
make
make test-qemu-ata
make host-gates
~~~

For ChrisVM changes also run:

~~~bash
make chrisvm
make chrisvm-test
~~~

KVM, VirGL, RISC-V and physical-hardware workflows are additional capabilities and are not prerequisites for every contribution.
