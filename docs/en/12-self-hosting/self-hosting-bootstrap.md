---
id: self-hosting-bootstrap
lang: en
type: technical-chapter
volume: 12-self-hosting
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/tools/chrisbuild.c
  - kernel/tools/chrisbuild.h
  - kernel/tools/shell.c
  - kernel/metal/start.c
  - tools/seed_selfhost.c
  - tools/kcc_main.c
  - compiler/kcc/kcc.c
  - compiler/kcc/kcc.h
  - compiler/chrisasm/chrisasm.c
  - compiler/chrisasm/chrisasm.h
  - compiler/chrisld/chriso.c
  - compiler/chrisld/chriso.h
  - compiler/chrisld/chrisld.c
  - compiler/chrisld/chrisld.h
  - tools/test_kcc.c
  - tools/test_chrisasm.c
  - tools/test_chrisld.c
  - makefile
symbols:
  - chrisbuild_mk_kernel
  - chrisbuild_mk_clean
  - chrisbuild_mk_install
  - kcc_compile_source
  - kcc_compile_named
  - chrisasm_assemble
  - chriso_merge_text
  - chrisld_link
depends_on:
  - native-toolchain
  - desktop-applications
related:
  - selfhost-levels
  - stage-compilers
  - internal-kernel-build
  - reproducible-builds
  - validation-evidence
---

# Self-hosting and bootstrap

## Scope

ChrisOS contains a real in-guest native compilation path, but the current repository does not yet prove full self-hosting.

The important distinction is between three different claims:

1. the running kernel contains compiler, assembler, object-format, and linker code that can produce native ELF files;
2. the guest can attempt to compile selected kernel C sources into `BIN/KERNEL.ELF`;
3. the system can rebuild, install, boot, and verify its complete current kernel without relying on a host toolchain.

The current source strongly supports the first claim and partially implements the second. It does not yet establish the third.

This chapter treats self-hosting as an evidence problem rather than a label.

## Host bootstrap remains the root

The normal repository build still starts with the host toolchain.

The makefile defines:

```text
CC      = gcc
LD      = ld
HOST_CC = gcc
```

The production kernel objects are compiled by host GCC and linked by host `ld`.

Assembly and boot-media preparation also depend on host-side tools such as NASM, xorriso, Limine tooling, Python scripts, and filesystem utilities.

Therefore the normal `make iso` path is not self-hosted.

It is the bootstrap root from which the in-guest tools are built and embedded.

## Native toolchain components

The emerging native path is composed of:

```text
KCC
  -> ChrisAsm textual assembly
  -> ChrisO object image
  -> ChrisLd
  -> ELF64 executable
```

KCC is a C-subset compiler.

It emits assembly text into an internal buffer and then calls `chrisasm_assemble`.

ChrisAsm produces a `ChrisoImage`.

ChrisO represents sections, symbols, and relocations.

ChrisLd resolves those objects and emits an ELF64 x86-64 executable.

These components are compiled into the ChrisOS kernel and can therefore execute inside the guest.

## KCC is not GCC

KCC must not be described as a complete C compiler.

It implements a project-specific C subset targeted at the code patterns needed by ChrisOS experiments.

The source has explicit fixed limits for preprocessed text, assembly output, symbols, macros, structs, fields, typedefs, enums, initializers, and parameters.

Its diagnostics and tests are substantial, but language coverage is not equivalent to GCC or Clang.

A kernel source file compiling under host GCC does not automatically imply that KCC can compile it.

## Host KCC executable

The makefile also builds:

```text
build/host/kcc
```

through the `host-kcc` target.

That binary is compiled by `HOST_CC` from:

- `tools/kcc_main.c`;
- KCC;
- ChrisAsm;
- ChrisO support.

Its purpose is to exercise the same compiler path from the host and to create a bootstrap tool artifact.

This host executable is not itself evidence that KCC has compiled KCC.

It is still produced by host GCC.

## Host tool tests

There are separate host tests for the emerging native toolchain:

- `host-chrisasm-test`;
- `host-chrisld-test`;
- `host-kcc-test`;
- `host-chriso-test`.

These tests prove concrete pieces of functionality such as instruction encoding, malformed assembly rejection, ELF generation, relocations, section layout, KCC language features, and compiler diagnostics.

They are useful bootstrap evidence because they validate the tools before using them inside the guest.

They are not a proof that the entire kernel can be rebuilt by those tools.

## The misleading level-zero target

The makefile defines:

```text
host-kcc-kernel-l0: host-kcc-test
```

This target currently aliases the general KCC test rather than compiling a complete kernel stage.

There is a source fixture named `tools/kcc_fixtures/level0.c`, but its own comment explicitly says it is not `kernel/metal/serial.c` and that it represents a deliberately tiny subset.

Thus "kernel-l0" is a bootstrap experiment, not a full kernel build level.

## In-guest KCC command

The shell command:

```text
kcc <path>
```

does not launch `BIN/KCC.ELF`.

It directly calls the KCC library already linked into the running kernel:

```text
kcc_compile_source(...)
```

The resulting ChrisO image is passed through the native linker helper to produce an ELF file.

This is meaningful in-guest compilation, but the compiler executing is part of the host-built kernel image.

That is an important provenance distinction.

## In-guest assembler command

The shell also provides:

```text
as <path>
```

for `.S` or `.ASM` sources.

It reads source from ChrisFS, runs `chrisasm_assemble`, and links the resulting ChrisO image into a native ELF.

Like the KCC command, the assembler code is embedded in the currently running host-built kernel.

This proves the guest can perform native assembly/linking work without invoking host NASM at that moment.

It does not eliminate NASM from the bootstrap of the running kernel.

## The `mk kernel` path

The central self-build function is:

```text
chrisbuild_mk_kernel()
```

The shell exposes it as:

```text
mk kernel
```

The function reads:

```text
SYS/BUILD.MK
```

from ChrisFS and parses a small custom manifest.

The defaults are:

```text
KERNEL_OUT = BIN/KERNEL.ELF
KERNEL_LD  = 0xffffffff80000000
```

The manifest may list C source paths under `C_OBJECTS`.

## Manifest parser limits

The internal builder supports at most:

```text
BUILD_MAX_OBJ = 48
```

C source units.

The source buffer is:

```text
BUILD_SRC_MAX = 65536
```

bytes.

The final ELF buffer is bounded by:

```text
CHRISLD_ELF_MAX = 1 MiB
```

These are hard implementation limits, not merely documentation recommendations.

## C-only internal build list

The parser recognizes the start of `C_OBJECTS`.

When it encounters `ASM_OBJECTS=`, it stops collecting C paths.

It does not subsequently parse and assemble an assembly-object list.

Therefore the current `chrisbuild_mk_kernel` pipeline is not a complete replacement for the repository kernel build, which includes assembly units and generated assets.

This alone prevents a full-kernel self-host claim.

## Path translation

Manifest paths are converted into ChrisFS paths.

For example, a host-style path beginning with:

```text
kernel/
```

is translated beneath:

```text
SYS/KERNEL/
```

and letters are uppercased.

This allows the guest builder to consume seeded source files from the ChrisFS workspace.

The self-host workspace is therefore a second source tree representation, not direct access to the host checkout.

## Per-unit compilation

For every manifest C source, the builder:

1. reads the source into the 64 KiB buffer;
2. invokes `kcc_compile_source`;
3. obtains one `ChrisoImage`;
4. merges that image into a combined object.

Compilation failure aborts the build immediately.

The serial log identifies the file currently being compiled with an `mk: kcc` prefix.

## Text-only merge limitation

The merge operation is:

```text
chriso_merge_text(&merged, &unit)
```

Its behavior is narrower than its name might suggest.

It appends the TEXT section and adjusts TEXT symbols and relocations.

It does not merge RODATA, DATA, or BSS payloads from each source unit into the combined image.

The combined text buffer is also capped at 65536 bytes.

Consequently, the current internal kernel builder can only correctly combine a restricted class of units.

A general current ChrisOS kernel containing globals, static data, BSS, strings, generated tables, and other sections cannot be assumed to survive this merge path.

## Link stage

After all selected C units are merged, the builder calls:

```text
chrisld_link(&merged, kernel_ld, ...)
```

ChrisLd emits ELF64 for x86-64.

Its general linker implementation supports TEXT, RODATA, DATA, and BSS, symbol resolution, multiple relocation types, RX/RW load segments, and entry selection.

However, the `mk kernel` builder currently feeds it one already-merged image produced by the text-only merge path.

The linker's broader capabilities therefore do not remove the builder's earlier information loss.

## Kernel output

On success, the generated ELF is written to the path selected by the manifest, normally:

```text
BIN/KERNEL.ELF
```

The serial console prints:

```text
mk: kernel ok bytes=...
```

This is useful evidence that selected units compiled and linked.

It is not evidence that the resulting binary has booted.

## `mk clean`

The shell command:

```text
mk clean
```

deletes:

```text
BIN/KERNEL.ELF
```

when present.

This part of the lifecycle is simple and deterministic.

## `mk install` is not a boot install

The function named `chrisbuild_mk_install` currently:

1. reads `BIN/KERNEL.ELF`;
2. writes the same bytes back to `BIN/KERNEL.ELF`;
3. prints `mk: install ok`.

It does not copy that file to:

```text
BOOT/KERNEL.ELF
```

and it does not update the EFI System Partition or the ISO boot tree.

Therefore `mk install` does not currently establish that the next boot will execute the internally built kernel.

Its name overstates the current effect.

## Boot artifact used elsewhere

The normal host-side disk population copies the host-built kernel into:

```text
BOOT/KERNEL.ELF
```

along with Limine configuration and EFI files.

This is a separate path from `BIN/KERNEL.ELF`.

Until the internally built ELF is deliberately promoted into the actual boot path and verified after reboot, self-hosted boot is unproven.

## Seed workflow

The repository defines:

```text
make seed-selfhost
```

which depends on:

- ISO construction;
- disk image;
- host KCC;
- host seed utility.

The seed program mounts the ChrisFS disk and attempts to populate:

- `SYS/BUILD.MK`;
- selected kernel source files;
- `BIN/KCC.ELF`.

This is intended to create the guest-side build workspace.

## Broken seed dependency in this revision

The seed program tries to read:

```text
learn/fase16-selfhost64/stubs/SYS_BUILD.MK
```

from the host repository.

That path does not exist in the inspected source tree at revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

Because `put_file` treats failure to read that file as fatal, the current seed workflow cannot be considered complete/reproducible from the checked-in tree.

This is a concrete bootstrap break, not a theoretical limitation.

## What `BIN/KCC.ELF` means

The seed utility copies:

```text
build/host/kcc
```

to:

```text
BIN/KCC.ELF
```

inside ChrisFS.

That source binary was produced by the host compiler.

The guest shell's `kcc` command does not execute this file; it calls the embedded KCC library.

Therefore presence of `BIN/KCC.ELF` should not be used as proof that ChrisOS runs a self-produced compiler binary.

The provenance chain remains host-rooted.

## Boot log marker

Early in `kstart`, the kernel prints:

```text
ChrisOS selfhost=1
```

unconditionally.

This string does not test which compiler produced the running kernel.

It does not hash the booted image or compare it with `BIN/KERNEL.ELF`.

It is therefore a descriptive marker, not self-hosting evidence.

A real self-host proof must bind runtime identity to a specific internally generated artifact.

## Self-host evidence levels

A practical evidence model for ChrisOS should separate milestones.

A useful progression is:

```text
SH0  host-built KCC/ChrisAsm/ChrisLd pass host tests
SH1  embedded guest tools compile/link native programs
SH2  guest compiles selected real kernel units
SH3  guest builds a structurally complete kernel ELF
SH4  internally built ELF passes validation and boot packaging
SH5  machine reboots into that exact internally built ELF
SH6  repeated stage build demonstrates defined convergence/reproducibility
```

These names are documentation criteria, not claims that all stages are achieved.

## Current evidence classification

At the inspected revision, strong evidence exists for SH0 and meaningful parts of SH1.

There is implementation toward SH2 through `chrisbuild_mk_kernel`, but the missing seed manifest and builder limitations prevent treating the whole workflow as a clean reproduced gate.

SH3 and higher are not established by the inspected source.

In particular, no checked source path proves that the complete current kernel is built by KCC and then booted.

## Reproducibility versus self-hosting

Self-hosting asks what toolchain produces the artifact.

Reproducibility asks whether equivalent declared inputs produce equivalent outputs under a defined criterion.

The two properties are independent.

A host-built kernel can be reproducible.

A self-hosted kernel can be non-reproducible.

ChrisOS build IDs include Git revision and build date, so byte-for-byte convergence needs a policy for timestamps and metadata before identical hashes can be expected.

## Required proof for a full claim

A strong future gate should record:

1. source Git revision;
2. exact bootstrap binary hashes;
3. source-manifest hash;
4. KCC/ChrisAsm/ChrisLd versions or hashes;
5. generated `BIN/KERNEL.ELF` hash;
6. `chrisld_validate` result;
7. exact promotion to the boot path;
8. reboot;
9. runtime build identity from the booted kernel;
10. comparison showing runtime identity matches the internally produced artifact.

Without steps 7–10, "built a kernel ELF" is not the same as "self-hosted the running kernel."

## Architectural next steps

The most important engineering work is:

1. restore/check in the missing `SYS_BUILD.MK` seed source;
2. make the manifest represent the complete kernel artifact graph;
3. support assembly units and generated inputs;
4. replace text-only object merging with full multi-object linking;
5. raise or remove the 64 KiB merged-text bottleneck;
6. validate the generated ELF with `chrisld_validate`;
7. make install copy to the actual boot target atomically;
8. add a reboot gate proving the exact artifact is running;
9. make the compiler itself buildable by a previous KCC stage;
10. define convergence and reproducibility criteria.

## Revision note

This chapter was reconciled against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. The current tree contains genuine in-guest native compilation infrastructure, but it does not yet prove complete kernel self-hosting. The missing seed manifest, C-only manifest handling, text-only merge, and non-installing `mk install` are explicit blockers in the inspected revision.
