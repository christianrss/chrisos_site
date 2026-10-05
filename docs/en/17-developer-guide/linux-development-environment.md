---
id: development-environment-linux
lang: en
type: guide
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - docs/getting-started/environment.md
  - scripts/check-dev-env.sh
  - .cursor/install.sh
  - makefile
depends_on:
  - developer-guide
---

# Linux development environment

The reference ChrisOS development host is a recent x86-64 Debian or Ubuntu installation. This is the environment against which the repository-local setup instructions are written and the path with the fewest differences between the documented command line and the actual build system.

The build combines freestanding kernel compilation, host-side utilities, ISO creation, disk-image manipulation and QEMU-based validation. Installing only GCC is therefore insufficient.

## Baseline packages

On Debian or Ubuntu:

~~~bash
sudo apt update
sudo apt install   build-essential   binutils   nasm   xorriso   qemu-system-x86   qemu-utils   python3   git
~~~

The installer integration gate additionally expects OVMF:

~~~bash
sudo apt install ovmf
~~~

These packages supply the core tools checked by scripts/check-dev-env.sh: Git, GNU Make, GCC, GNU ld, NASM, xorriso, x86-64 QEMU and Python 3.

After installation:

~~~bash
git clone https://github.com/christianrss/ChrisOS.git
cd ChrisOS
./scripts/check-dev-env.sh
~~~

Do not continue by guessing if the checker reports a required command as missing. Resolve the host dependency first. A missing host executable is not evidence about ChrisOS itself.

## Compiler selection

The general environment contract currently requires GCC rather than one globally mandated version. The cloud-agent bootstrap in .cursor/install.sh selects GCC 11 because newer GCC versions have produced a warning promoted to an error in a ChrisC host build at that automation baseline. This is a known-good automation configuration, not a reason to rewrite a developer workstation's global compiler selection unnecessarily.

Start with the distribution compiler:

~~~bash
gcc --version
make
~~~

If the build fails specifically because a compiler-version-dependent warning is promoted by the warnings-as-errors policy, preserve the diagnostic, record the compiler version and compare with the known-good GCC 11 path. Do not suppress warnings globally merely to obtain a green build.

## Optional capabilities

The environment checker reports optional tools independently from required build tools.

RISC-V bring-up uses Clang/LLD for the cross target and needs qemu-system-riscv64 to run the guest. Package names vary by distribution.

ChrisVM can use SDL when sdl2-config is present, although headless tests do not require SDL.

VirGL requires more than a package named QEMU. The host QEMU build must expose an appropriate GL-capable VirtIO GPU device and the host must provide a usable display/GL path. The maintained test-qemu-virgl target detects missing host support and reports a skip rather than converting host incapability into a guest failure.

## KVM

The environment checker tests /dev/kvm separately:

~~~bash
test -r /dev/kvm -a -w /dev/kvm   && echo "KVM usable"   || echo "KVM unavailable"
~~~

KVM is an acceleration capability, not a prerequisite for all ChrisOS testing. The interactive make run path currently requests KVM, but the headless QEMU gates in scripts/qemu.mk use TCG. This distinction allows integration tests on machines where hardware virtualization is absent, disabled or inaccessible.

If /dev/kvm exists but is not writable, investigate host virtualization configuration and device permissions. Do not use elevated QEMU execution as a routine workaround; running a development VM as root changes the risk profile of file access, network forwarding and device handling.

## Repository checkout and artifact boundaries

Use a normal checkout:

~~~bash
git clone https://github.com/christianrss/ChrisOS.git
cd ChrisOS
git status
~~~

The generated tree includes:

| Path | Role |
|---|---|
| build/obj/ | kernel/compiler object files |
| build/iso/ | staged ISO filesystem |
| build/os.iso | bootable ChrisOS image |
| build/disk.img | ChrisFS workspace disk |
| build/host/ | host utilities and tests |
| build/user/ | user-mode test binaries |
| build/chrisvm/ | ChrisVM executable and fixtures |

All are reproducible artifacts and should remain outside commits.

## First build

A useful first validation sequence is:

~~~bash
./scripts/check-dev-env.sh
make
make disk.img
make test-qemu-ata
~~~

This proves progressively different things: host tool presence, source compilation and image generation, workspace-disk production, and a TCG-based guest smoke path with serial expectations.

Only after the baseline works should an interactive session be treated as a useful debugging environment:

~~~bash
make run
~~~

## Distribution differences

Other Linux distributions can host ChrisOS, but the project does not currently maintain package-manager recipes for all of them. Translate capabilities rather than package names. The required contract is the command set reported by check-dev-env.sh; OVMF, SDL, GL/VirGL support and RISC-V tools are additional capabilities.

When reporting a problem on a non-Debian host, include:

~~~bash
./scripts/check-dev-env.sh
gcc --version
ld --version | head -n 1
nasm -v
qemu-system-x86_64 --version | head -n 1
git rev-parse HEAD
~~~

Also include the exact make target and the first relevant error. The final make exit line usually contains less information than the first compiler, linker, image-construction or QEMU failure.

## Tool identity and PATH discipline

When several compiler, QEMU or Python installations coexist, record which executable is actually selected by the shell.

Useful checks include:

~~~bash
command -v gcc
command -v ld
command -v qemu-system-x86_64
command -v python3
~~~

Do not assume that installing a package changed the executable used by the current terminal. PATH differences can explain why two developers with apparently identical packages observe different compiler diagnostics, QEMU capabilities or Python behavior.

## Environment snapshot for bug reports

For environment-sensitive failures, capture the host state before changing packages or PATH. A minimal snapshot should include the selected compiler, linker, QEMU and Python executables, their versions, the source revision and the exact failing target.

This preserves the evidence needed to distinguish a project defect from a host-only configuration difference. If a package reinstall changes the result, keep both snapshots. The before/after comparison is usually more useful than a final statement that reinstalling "fixed" the issue.

## Host reproducibility

Avoid silently changing flags or tools to obtain a local pass. The repository intentionally uses warnings as errors in important host builds and deterministic test targets for many subsystems. If a local host requires a change, determine whether it is a configuration issue or a portability defect worth fixing in the project.

A useful environment is not one that makes every command succeed at any cost. It is one whose differences are visible enough that another contributor can reproduce the same result.
