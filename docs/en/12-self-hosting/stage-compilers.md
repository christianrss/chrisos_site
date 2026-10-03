---
id: stage-compilers
lang: en
type: technical-chapter
volume: 12-self-hosting
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/kcc/kcc.c
  - compiler/kcc/kcc.h
  - compiler/chrisasm/chrisasm.c
  - compiler/chrisasm/chrisasm.h
  - compiler/chrisld/chriso.c
  - compiler/chrisld/chriso.h
  - compiler/chrisld/chrisld.c
  - compiler/chrisld/chrisld.h
  - tools/kcc_main.c
  - tools/test_kcc.c
  - tools/test_chrisasm.c
  - tools/test_chrisld.c
  - tools/seed_selfhost.c
  - kernel/tools/shell.c
  - kernel/tools/chrisbuild.c
  - kernel/metal/kcc_job.c
  - makefile
symbols:
  - kcc_compile_source
  - kcc_compile_named
  - chrisasm_assemble
  - chriso_write
  - chriso_read
  - chrisld_link
  - chrisld_link_objects
depends_on:
  - self-hosting-bootstrap
  - selfhost-levels
related:
  - internal-kernel-build
  - reproducible-builds
  - validation-evidence
---

# Compiler staging and convergence

## Scope

Compiler staging answers a narrower question than general self-hosting:

> Can one compiler stage produce the next compiler stage, and can successive stages be compared under a defined equivalence rule?

For ChrisOS, the natural notation is:

```text
KCC0 -> KCC1 -> KCC2
```

where each arrow means that the compiler on the left produced the compiler on the right.

The current repository does not yet implement this complete chain.

It contains the core ingredients needed to begin such a chain, but several concrete source, driver, input-size, header, runtime, and provenance problems still prevent KCC1 from being a demonstrated self-produced compiler.

## Defining KCC0

KCC0 should mean the bootstrap KCC implementation produced by the external host toolchain.

The current make target:

```text
host-kcc
```

builds:

```text
build/host/kcc
```

with `HOST_CC`, currently GCC.

Its source set is:

- `tools/kcc_main.c`;
- `compiler/kcc/kcc.c`;
- `compiler/chrisasm/chrisasm.c`;
- `compiler/chrisld/chriso.c`.

This is a legitimate bootstrap stage.

However, it is a host program, not a self-produced compiler.

## What the host KCC driver actually emits

`tools/kcc_main.c` reads one C source file using host stdio and malloc.

It calls:

```text
kcc_compile_named(...)
```

and serializes the resulting `ChrisoImage` with:

```text
chriso_write(...)
```

The command-line program therefore emits a ChrisO object file, not a final executable compiler binary.

Its usage is effectively:

```text
kcc input.c output.chriso
```

A subsequent linker stage is required to produce ELF.

Thus even the host bootstrap driver is a compile-to-object stage, not the whole compiler executable pipeline.

## KCC0 is host-ABI software

The host driver includes:

- `stdio.h`;
- `stdlib.h`;
- `string.h`.

It uses `FILE`, `fopen`, `fseek`, `ftell`, `fread`, `fwrite`, `malloc`, and `free`.

Therefore `build/host/kcc` is a host-runtime program.

The seed utility copies this file into ChrisFS as:

```text
BIN/KCC.ELF
```

but that filename does not change its provenance or runtime assumptions.

The current guest shell does not execute that file when the user enters `kcc`.

## The guest `kcc` command is an embedded compiler

Inside ChrisOS, the shell command:

```text
kcc path.c
```

allocates a source buffer and directly calls:

```text
kcc_compile_source(...)
```

from the KCC library linked into the running kernel.

The guest therefore has real compiler execution, but this compiler is embedded in the host-built bootstrap kernel.

This is SH1-style evidence, not KCC0 producing KCC1.

## KCC1 must have an explicit artifact definition

Before implementing compiler staging, the project must define what KCC1 actually is.

Possible definitions include:

1. a standalone native ChrisOS ELF executable containing KCC, ChrisAsm, ChrisO, and a guest-native driver;
2. a ChrisO object set later linked into another kernel;
3. a rebuilt compiler library embedded into a new kernel stage.

These are different artifacts with different proof requirements.

The current tree has no target named KCC1 and no gate defining one of these artifacts as canonical.

## Standalone KCC1 needs a guest-native driver

The existing `tools/kcc_main.c` cannot simply become the guest compiler driver without changes because it is written against host libc and file I/O.

A standalone ChrisOS-native KCC1 would need a driver using ChrisOS-native services for:

- file input;
- file output;
- diagnostics;
- allocation;
- process exit status.

The embedded shell command already demonstrates many of these services indirectly, but they are not packaged as a standalone compiler program.

## The current seed does not create KCC1

`tools/seed_selfhost.c` copies:

```text
build/host/kcc
```

into:

```text
BIN/KCC.ELF
```

That operation is bootstrap seeding.

It does not run KCC0 on KCC source.

It does not link KCC1.

It does not execute the result.

Therefore the presence of `BIN/KCC.ELF` must not be described as compiler staging.

## Raw source-size blocker

The current `compiler/kcc/kcc.c` file is approximately 141 KiB.

Guest compilation entry points have much smaller input buffers.

The shell command allocates:

```text
65536 bytes
```

and calls:

```text
fs_read(path, src_buf, 65535)
```

The background KCC job uses the same 64 KiB-class limit.

`chrisbuild_mk_kernel` also defines:

```text
BUILD_SRC_MAX = 65536
```

Therefore the current KCC source cannot even be fully read by these guest compiler entry points.

This is a direct KCC1 blocker before parsing or code generation begins.

## Internal compiler buffers

Inside KCC itself, larger buffers exist:

```text
KCC_PP_MAX  = 256 KiB
KCC_ASM_MAX = 256 KiB
```

The raw KCC source fits under the preprocessor maximum, but only if a caller can first provide the complete source.

It is not yet proven that the preprocessed KCC source or generated assembly stays below those 256 KiB limits.

A stage gate must measure these sizes rather than assume them.

## Header-resolution blocker

`compiler/kcc/kcc.c` includes:

```text
<string.h>
```

KCC's own preprocessor treats only these common headers as built in:

- `stdint.h`;
- `stdbool.h`;
- `stddef.h`;
- `stdarg.h`.

For other includes it searches a fixed set of project directories.

The inspected tree contains `kernel/metal/string.c` and ChrisC-side `LIB/STRING.H`, but no `string.h` file in KCC's include-search directories that satisfies this include.

Therefore a direct self-compilation attempt encounters a header-availability problem.

## Freestanding branch is selected by KCC

KCC initializes predefined macros including:

```text
__x86_64__ = 1
__freestanding__ = 1
__VERSION__ = "KCC"
```

This means compiling KCC with KCC selects the freestanding branch of `kcc.c`.

That branch uses ChrisOS `heap.h` and `fs.h` instead of host stdio/stdlib.

Those directories are already in KCC's include search list.

This is a useful foundation for self-compilation, but the unconditional `string.h` include remains a blocker.

## ChrisAsm and ChrisLd have the same libc-header issue

KCC1 is not only `kcc.c`.

The compiler pipeline also depends on ChrisAsm and ChrisO, and a standalone executable may depend on ChrisLd.

These sources also include `string.h`.

Therefore solving header/runtime independence must cover the entire stage toolchain, not just KCC's parser.

A consistent freestanding string API or KCC builtin-header mapping is required.

## Source-language coverage must be tested against the compiler itself

Even after input-size and header problems are fixed, KCC must be capable of compiling the syntax used by its own implementation.

The current KCC source uses:

- enums;
- typedefs;
- nested structs;
- fixed arrays;
- pointers;
- 64-bit arithmetic;
- conditional preprocessing;
- macros;
- function calls;
- static global state;
- string literals;
- loops and branches.

KCC has explicit support for many of these constructs, but successful tests of individual features do not prove successful compilation of the full compiler source.

The only valid proof is to compile the actual revision of the toolchain.

## KCC's intentional language exclusions

KCC explicitly rejects some language classes.

For example, plain floating-point values are outside the supported subset.

The compiler also has bounded tables and parser limits.

Self-compilation therefore requires the implementation source to remain inside a "KCC-compilable C" profile.

If future compiler development adopts unsupported C constructs, stage convergence can regress even while the host GCC build continues to work.

## A stage-safe source profile

The project should define a machine-checkable source profile for self-hosted toolchain files.

At minimum it should document:

- allowed C syntax;
- allowed preprocessor directives;
- allowed headers;
- maximum include depth;
- maximum source/preprocessed size;
- allowed runtime calls;
- allowed object/relocation features.

CI should reject changes to KCC/ChrisAsm/ChrisLd that leave this profile unless the compiler is extended first.

This prevents accidental bootstrap breakage.

## Building KCC1 as multiple objects

ChrisLd already provides:

```text
chrisld_link_objects(...)
```

with support for multiple ChrisO images.

It can combine TEXT, RODATA, DATA, and BSS across objects and resolve global symbols and relocations.

This is a much better foundation for staging than `chriso_merge_text`.

However, ChrisLd currently caps input objects with:

```text
LD_OBJS = 32
```

A staged compiler build must fit within that object count or raise the limit.

## ChrisO object limits

Each `ChrisoImage` has bounded metadata:

```text
CHRISO_SYM_MAX = 256
CHRISO_REL_MAX = 512
```

These are per-object limits.

A KCC1 build that compiles large monolithic translation units must stay within those limits.

Splitting toolchain source into multiple translation units can reduce pressure per object, but then the multi-object build graph and runtime dependencies must be explicit.

## KCC background jobs are not stages

`kernel/metal/kcc_job.c` can compile a source file asynchronously through the kernel job system and emit:

```text
<source>.CHRISO
```

This is useful infrastructure for parallel native compilation.

It still uses a maximum source buffer of 65536 bytes.

It also compiles one source at a time and does not create a next-stage compiler executable by itself.

Parallel compilation is orthogonal to compiler provenance.

## Defining KCC1 acceptance

A strong KCC1 gate should perform all of the following:

1. start from a declared KCC0 hash;
2. compile the real KCC/ChrisAsm/ChrisO source set;
3. use only declared guest/freestanding headers;
4. link a standalone native KCC1 artifact;
5. validate its ELF;
6. run KCC1 inside ChrisOS;
7. compile a fixed conformance corpus;
8. record KCC1 output hashes and diagnostics.

Only after this should KCC1 be considered an achieved stage.

## Defining KCC2

KCC2 must be produced by KCC1 using the same declared source revision and build rules used for KCC1.

The provenance chain is:

```text
GCC -> KCC0
KCC0 -> KCC1
KCC1 -> KCC2
```

If KCC1 is merely copied or relinked from KCC0 objects, the chain is not valid.

The actual compiler execution producing KCC2 must be KCC1.

## What convergence means

KCC1 and KCC2 do not have to be byte-identical unless the build is deterministic.

But a convergence rule must be declared before comparison.

Possible levels of strength are:

1. both pass the same compiler conformance corpus;
2. both generate semantically equivalent ChrisO objects;
3. their loadable executable sections are identical;
4. the entire compiler ELF is byte-identical.

The strongest practical goal is level 4 after removing nondeterministic metadata.

## Comparing ChrisO output

Because KCC naturally emits ChrisO, object-level convergence is especially useful.

For a fixed corpus, the project can compare:

- section sizes;
- section bytes;
- symbol tables;
- relocation tables.

This can detect compiler-stage drift before introducing ELF/linker differences.

A serializer already exists through `chriso_write`, making hashes straightforward to compute.

## Comparing compiler behavior

Byte equality alone is not sufficient if undefined or unstable build inputs remain.

A useful semantic gate should also compare:

- successful/failed source cases;
- diagnostic locations/messages where contractually relevant;
- generated symbols;
- runtime results of compiled programs.

This is especially important while KCC remains a deliberately limited compiler.

## Bootstrapping ChrisAsm and ChrisLd

A real compiler stage is a toolchain stage, not only a parser/code generator stage.

KCC1 must have compatible ChrisAsm and object/link support.

The stage record should identify hashes for:

```text
KCC
ChrisAsm
ChrisO
ChrisLd
driver/runtime
```

Otherwise a new KCC may silently continue using host-produced support components, weakening the provenance claim.

## Trusting-trust boundary

Compiler staging does not eliminate trust in the original bootstrap compiler.

The classic trusting-trust problem remains: a malicious KCC0 or host compiler could inject behavior not visible in source.

Stage convergence reduces accidental divergence but is not proof of compiler innocence.

Long-term trust reduction can include:

- diverse double compilation;
- building KCC0 with independent compilers;
- comparing stage outputs;
- minimizing the bootstrap implementation;
- publishing artifact hashes and build recipes.

## Current stage status

For revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, a conservative classification is:

```text
KCC0:
  host-built implementation exists and is tested

KCC1:
  not demonstrated as a self-produced compiler artifact

KCC2:
  not demonstrated

convergence:
  not demonstrated
```

The guest's embedded KCC is operationally useful but should not be renamed KCC1 because it was not produced by KCC0.

## Immediate engineering path

The shortest path toward real staging is:

1. provide a freestanding `string.h` contract usable by KCC;
2. remove the 64 KiB guest source-input ceiling;
3. create a guest-native standalone KCC driver;
4. define the exact toolchain source/object manifest;
5. compile toolchain units into ChrisO objects;
6. link them with `chrisld_link_objects`;
7. validate and execute KCC1;
8. use KCC1 to build KCC2;
9. compare KCC1 and KCC2 under a declared rule;
10. make the entire sequence a fail-closed automated gate.

## Revision note

This chapter was created against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. The repository has a valid host bootstrap compiler and real embedded guest compilation, but no current KCC0→KCC1→KCC2 proof. The 64 KiB guest input ceiling, missing freestanding `string.h` resolution, absence of a guest-native standalone KCC driver, and lack of stage-comparison gates are concrete blockers.
