---
id: internal-kernel-build
lang: en
type: technical-chapter
volume: 12-self-hosting
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/tools/chrisbuild.c
  - kernel/tools/chrisbuild.h
  - kernel/tools/shell.c
  - kernel/tools/native_link.c
  - compiler/kcc/kcc.c
  - compiler/chrisld/chriso.c
  - compiler/chrisld/chriso.h
  - compiler/chrisld/chrisld.c
  - compiler/chrisld/chrisld.h
  - kernel/metal/linker.ld
  - tools/stamp_kernel.c
  - tools/buildstamp.c
  - tools/seed_selfhost.c
  - makefile
symbols:
  - chrisbuild_mk_kernel
  - chrisbuild_mk_clean
  - chrisbuild_mk_install
  - chriso_merge_text
  - chrisld_link
  - chrisld_link_objects
  - chrisld_validate
depends_on:
  - self-hosting-bootstrap
  - stage-compilers
related:
  - selfhost-levels
  - reproducible-builds
  - validation-evidence
---

# Internally produced kernel

## Scope

ChrisOS contains an in-guest command named:

```text
mk kernel
```

that attempts to compile selected kernel C sources with KCC, combine the resulting ChrisO images, link them with ChrisLd, and write:

```text
BIN/KERNEL.ELF
```

This is a real internal build path.

It is not yet equivalent to the repository's production kernel build.

The difference is structural, not merely one of missing polish.

The host build and the internal build currently consume different artifact graphs, support different language/features, use different linking models, and produce different boot integration semantics.

## User-visible commands

The shell exposes:

```text
mk kernel
mk clean
mk install
```

`mk kernel` calls `chrisbuild_mk_kernel`.

`mk clean` calls `chrisbuild_mk_clean`.

`mk install` calls `chrisbuild_mk_install`.

These commands execute inside the running kernel and operate on ChrisFS.

## Internal manifest

The builder expects:

```text
SYS/BUILD.MK
```

and parses only a small custom subset of make-like syntax.

Recognized controls are:

- `KERNEL_OUT=`;
- `KERNEL_LD=`;
- `C_OBJECTS=`;
- `ASM_OBJECTS=` only as a marker ending C collection.

Default output is:

```text
BIN/KERNEL.ELF
```

and default load address is:

```text
0xffffffff80000000
```

The parser is not GNU Make and does not evaluate variables, rules, dependencies, pattern rules, command recipes, conditional expressions, or generated-file dependencies.

## No dependency graph

The internal builder performs one linear pass over the listed C paths.

It does not compare mtimes, track header dependencies, cache objects, detect unchanged translation units, or rebuild only affected files.

Every `mk kernel` attempt recompiles every manifest entry from source.

That simplifies bootstrap semantics, but it also means the manifest itself is the only build graph.

Any source/header/generated input not represented by the seeded filesystem state is invisible to the build.

## Object-count ceiling

`BuildManifest` can store at most:

```text
BUILD_MAX_OBJ = 48
```

C paths.

The current production makefile expands to approximately:

```text
129 C objects
1 assembly object
130 total kernel objects
```

before considering build-time helper artifacts.

Therefore the internal manifest cannot enumerate the complete current C object set without increasing its capacity.

This is an immediate full-kernel-build blocker.

## Assembly is not built

The production build includes:

```text
kernel/metal/idt_stubs.o
```

assembled by NASM.

The internal manifest parser recognizes the string:

```text
ASM_OBJECTS=
```

only to stop collecting C paths.

It does not parse, assemble, or link an assembly-object list afterward.

Thus the internal builder omits architecture assembly required by the host kernel artifact graph.

## Generated inputs are absent from the model

The production build contains generated dependencies.

For example, shader sources are embedded into:

```text
kernel/gfx/shader/sh_src.h
```

through a Python generator before some graphics objects are compiled.

The internal builder has no dependency graph and no generator execution model.

It assumes the source file named in the manifest already exists in ChrisFS in final form.

A complete internal build must either seed every generated input or reproduce generation inside ChrisOS.

## Per-source input ceiling

Every listed C file is read into:

```text
BUILD_SRC_MAX = 65536
```

bytes.

Files larger than 65535 bytes cannot be consumed completely by this path.

The current KCC implementation source itself is roughly 141 KiB, so the internal builder cannot compile that translation unit as-is.

Any other kernel source crossing the same threshold has the same problem.

## Compilation step

For each C path, the builder:

1. converts the host-like manifest path to a ChrisFS path;
2. reads the source;
3. calls `kcc_compile_source`;
4. receives one `ChrisoImage`;
5. merges it into a combined image.

Compilation stops immediately on the first read or KCC failure.

There is no incremental build cache, dependency tracking, parallel build plan, or per-unit artifact retention in this path.

## Path conversion

A path beginning with:

```text
kernel/
```

is mapped under:

```text
SYS/KERNEL/
```

and characters are uppercased.

This reflects the seeded ChrisFS workspace rather than the host checkout.

The internal build therefore depends on source synchronization between two trees.

A stale source copied into ChrisFS can produce a different kernel even if the host repository is at the expected Git revision.

A strong build record must hash the guest-side source set, not merely record the host Git SHA.

## KCC language mismatch with the current kernel

The production kernel is not compiled under one uniform C feature profile.

The makefile has special flags for graphics code, including SSE2, floating-point XMM execution, and `-ffast-math`.

KCC explicitly rejects ordinary scalar `float` values as outside its current subset.

Therefore the contemporary graphics-heavy kernel object graph contains translation units that the internal KCC cannot be assumed to compile.

The internal builder needs either broader KCC language support or a deliberately reduced bootstrap-kernel configuration.

## Host compiler profile is richer than the internal profile

The host build also controls ABI/code-generation details through flags such as:

```text
-ffreestanding
-fno-stack-protector
-fno-pic
-fno-pie
-mno-red-zone
-mcmodel=kernel
```

with selected graphics units switching to SSE2/XMM modes.

KCC has its own x86-64 code generator rather than translating these GCC flags one-for-one.

Therefore successful source parsing is not sufficient to prove ABI equivalence.

A full internal kernel gate must verify calling convention, relocation model, high-half addressing, red-zone assumptions, and interrupt-safe register behavior against the real kernel ABI.

## The merge algorithm

After each KCC compile, the builder calls:

```text
chriso_merge_text(&merged, &unit)
```

This is the most important implementation constraint in the current internal path.

Despite compiling a full `ChrisoImage`, the build pipeline only combines the TEXT section into one shared 64 KiB text buffer.

## What `chriso_merge_text` preserves

The function:

- appends source TEXT bytes;
- adjusts offsets of defined TEXT symbols;
- copies symbol entries;
- copies relocations;
- adjusts relocation offsets in TEXT.

It does not perform full multi-section object composition.

## What the merge drops

RODATA, DATA, and BSS bytes/sizes from source objects are not accumulated into the combined image.

That means normal C features can be lost, including storage associated with:

- string literals;
- static/global initialized data;
- zero-initialized globals;
- tables;
- constant arrays.

Even if KCC successfully compiles a source unit, merging only its TEXT is insufficient for general kernel semantics.

## Text-size ceiling

The merged TEXT image is explicitly capped at:

```text
65536 bytes
```

through `chriso_merge_text`.

The current production kernel is much larger in source/object complexity than a 64 KiB text-only educational stage.

The internal build path is therefore better understood as a bootstrap subset builder.

## Per-unit memory ownership

KCC returns a `ChrisoImage` whose TEXT storage is dynamically allocated.

After merging each unit, `chrisbuild_mk_kernel` frees only:

```text
unit.sec[CHRISO_SEC_TEXT]
```

and clears that pointer.

The current merge path does not retain the other sections anyway.

This lifetime matches the text-only design, but a future full-object builder must define ownership for RODATA/DATA and any separately allocated object storage before switching to multi-object linking.

## ChrisLd is more capable than the builder feeds it

ChrisLd supports:

```text
chrisld_link_objects(...)
```

which can combine multiple object images while preserving:

- TEXT;
- RODATA;
- DATA;
- BSS;
- global symbols;
- relocations.

That multi-object linker is technically closer to what the internal kernel build needs.

However, `chrisbuild_mk_kernel` does not use it.

It first collapses source objects through `chriso_merge_text`, then calls the single-image:

```text
chrisld_link(...)
```

The broader linker capability is therefore bypassed.

## Multi-object linker capacity

ChrisLd's full object linker itself currently caps input at:

```text
LD_OBJS = 32
```

Even if `chrisbuild` switched directly to `chrisld_link_objects`, the present production kernel's approximately 130-object graph would exceed that limit.

Both the builder and linker object-count limits need redesign for a full current kernel.

## Host linker semantics

The production kernel is linked with:

```text
kernel/metal/linker.ld
```

using GNU ld.

The script explicitly defines:

- entry point `kstart`;
- high-half base `0xffffffff80000000`;
- a dedicated `.limine_requests` load segment;
- aligned `.text`;
- `.rodata`;
- `.data`;
- `.bss`;
- a one-megabyte kernel stack;
- `__kernel_start`, `__stack_bottom`, `__stack_top`, and `__kernel_end`;
- discard rules for unwanted sections.

These semantics are part of the bootable kernel contract.

## ChrisLd does not reproduce the linker script

ChrisLd understands the four ChrisO sections:

```text
TEXT
RODATA
DATA
BSS
```

and creates one RX segment plus an optional RW segment.

It selects `kstart` as entry when present.

It does not implement the host linker's dedicated Limine request section or linker-script-defined stack symbols/layout.

Therefore an internal ELF can be structurally valid as an ELF while still not being equivalent to the Limine-bootable host kernel.

## Limine request preservation

The host linker script uses:

```text
KEEP(*(.limine_requests_start))
KEEP(*(.limine_requests))
KEEP(*(.limine_requests_end))
```

in a dedicated load segment.

The generic ChrisO model has no corresponding section class.

A complete internal bootable kernel needs an explicit design for preserving Limine requests, not just a valid `kstart` symbol.

## Kernel stack contract

The host linker creates a one-megabyte region inside BSS and defines:

```text
__stack_bottom
__stack_top
```

around it.

Those are linker-produced symbols, not ordinary C globals.

ChrisLd does not currently synthesize this contract.

Any internally linked kernel that references those symbols or depends on this layout needs an equivalent mechanism before it can replace the production image.

## Link output ceiling

The internal ELF buffer is:

```text
CHRISLD_ELF_MAX = 1 MiB
```

The final internal kernel must fit inside that fixed buffer.

This may be suitable for a reduced bootstrap kernel, but the limit must be measured against the actual generated artifact before claiming compatibility with the full production image.

## No internal validation call

After linking, `chrisbuild_mk_kernel` writes the ELF directly.

It does not call:

```text
chrisld_validate(...)
```

even though that validator exists.

At minimum, an internally produced kernel should be rejected before write/install if its ELF structure is invalid.

## Production build stamping

The host kernel build runs:

```text
stamp_kernel
```

after GNU ld.

The stamping process finds the `CHRISOSHASH:` slot, zeroes its digest characters, hashes the complete kernel image with SHA-256, and writes the digest back into the image.

This creates a runtime-verifiable image identity.

The internal `mk kernel` path does not perform this stamping step.

## Build provenance mismatch

Because the internal build does not run the same stamping process, its artifact identity does not follow the production provenance path.

For SH5-style reboot proof, this gap matters.

The internally built image needs a build identity tied to its exact bytes before it can be compared with the booted kernel.

## Failure semantics

The internal builder is fail-fast.

Allocation failure, missing manifest, malformed manifest, source read failure, KCC failure, text merge failure, linker failure, or filesystem write failure terminates the build and returns -1.

The three large top-level buffers are freed on both success and the common failure path.

However, the build does not retain a structured diagnostic report describing which language construct, object, relocation, or dependency prevented completion.

Serial messages identify only coarse phases.

A full self-host gate should preserve machine-readable failure evidence.

## Output write

On success, `chrisbuild_mk_kernel` writes the produced bytes to the configured `KERNEL_OUT`, normally:

```text
BIN/KERNEL.ELF
```

A successful write produces:

```text
mk: kernel ok bytes=<n>
```

This means a selected manifest compiled and linked.

It does not mean the production kernel was reproduced.

## `mk clean`

`chrisbuild_mk_clean` removes:

```text
BIN/KERNEL.ELF
```

If the file does not exist, it logs that condition and still returns success.

The command does not clean intermediate objects because the current builder does not persist them.

## `mk install`

The current install function reads:

```text
BIN/KERNEL.ELF
```

into memory and writes the same bytes back to:

```text
BIN/KERNEL.ELF
```

It does not write:

```text
BOOT/KERNEL.ELF
```

It does not update Limine media.

It does not validate the ELF.

It does not record a rollback artifact.

Thus `mk install` currently performs no meaningful promotion into the boot chain.

## Production disk path

The host-side disk population explicitly copies the host-built kernel into:

```text
BOOT/KERNEL.ELF
```

along with:

- `EFI/BOOT/BOOTX64.EFI`;
- `BOOT/LIMINE.CFG`.

That is the boot integration path the internal builder must eventually target.

## Current evidence level

The internal builder is useful evidence that ChrisOS can orchestrate KCC and ChrisLd over source stored in its own filesystem.

It demonstrates a bootstrap architecture.

It does not currently establish a complete SH3 kernel build because:

- source/object count is insufficient;
- assembly is omitted;
- generated dependencies are not modeled;
- KCC cannot compile all current kernel language features;
- object merging discards non-TEXT sections;
- linker-script semantics are not reproduced;
- build stamping is absent;
- validation is not invoked.

## Recommended redesign

A complete internal kernel builder should:

1. version a full manifest;
2. remove the 48-object limit;
3. support C, assembly, and generated inputs;
4. emit one ChrisO per translation unit;
5. link through an expanded `chrisld_link_objects`;
6. preserve all sections and relocations;
7. model Limine request sections and required linker symbols;
8. support the C/SSE/float profile actually used by the kernel or define a reduced bootstrap configuration;
9. validate ELF before write;
10. stamp artifact identity;
11. install atomically into the real boot path;
12. reboot and prove that exact artifact is running.

## Revision note

This chapter was created against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. The current `mk kernel` path is a genuine in-guest bootstrap builder, but it is not equivalent to the 130-object production kernel build. Object-count limits, C-only manifests, text-only merging, missing linker-script semantics, ABI/profile differences, and non-promoting install behavior are explicit blockers.
