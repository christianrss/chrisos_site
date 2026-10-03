---
id: selfhost-levels
lang: en
type: technical-chapter
volume: 12-self-hosting
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/tools/chrisbuild.c
  - kernel/tools/shell.c
  - kernel/metal/start.c
  - tools/seed_selfhost.c
  - tools/kcc_main.c
  - tools/test_kcc.c
  - tools/test_chrisasm.c
  - tools/test_chrisld.c
  - compiler/kcc/kcc.c
  - compiler/chrisasm/chrisasm.c
  - compiler/chrisld/chrisld.c
  - compiler/chrisld/chriso.c
  - makefile
symbols:
  - chrisbuild_mk_kernel
  - chrisbuild_mk_install
  - kcc_compile_source
  - chrisasm_assemble
  - chrisld_link
  - chrisld_validate
depends_on:
  - self-hosting-bootstrap
related:
  - stage-compilers
  - internal-kernel-build
  - reproducible-builds
  - validation-evidence
---

# SH0-SH6 self-host evidence model

## Purpose

"Self-hosted" is too broad to be useful as a binary label.

ChrisOS has enough native toolchain infrastructure that several different statements can sound similar while describing very different engineering milestones.

For example:

- a compiler library executes inside the guest;
- that compiler can compile one native program;
- it can compile selected kernel files;
- it can create a complete kernel ELF;
- that ELF becomes the next boot image;
- the booted kernel can rebuild the compiler and itself again.

These are not equivalent achievements.

The SH0-SH6 model defines a monotonic evidence ladder so documentation can state exactly what has been proved.

## Evidence principle

A level is achieved only when the required artifact and execution evidence exist.

Source code that appears capable of performing a step is weaker evidence than a repeatable gate that actually performs the step.

A log string is weaker than a hash tied to a produced artifact.

A produced ELF is weaker than proof that the machine booted that exact ELF.

Each level therefore requires:

1. declared inputs;
2. a producing toolchain;
3. an artifact;
4. validation of that artifact;
5. where applicable, execution evidence;
6. provenance connecting the previous level to the next.

## Historical versus reproducible evidence

The project should distinguish "this level was achieved once" from "this level is reproducible from the current revision."

A historical log, screenshot, or old artifact can establish that an event occurred, but it does not prove that the present repository can repeat the event.

For current-status documentation, a level should be marked reproducible only when all required sources, manifests, tools, scripts, and gates are present in the checked revision and can be invoked without hidden local files.

This distinction matters in the current self-host path because the seed utility references a manifest path that is absent from the tree.

## Transition rule

Promotion from SHn to SHn+1 requires new evidence that closes the specific gap between those levels.

Passing more tests at the same level does not automatically promote the system.

For example, adding more KCC language tests strengthens SH0 but does not establish SH1 until the compiler actually runs in the guest.

Likewise, generating more partial kernel objects at SH2 does not establish SH3 until the required kernel artifact graph is complete.

The documentation should therefore record both breadth of evidence within a level and the explicit transition criterion for the next level.

## Monotonicity

Higher levels include the requirements of lower levels.

If SH4 is achieved but later a required bootstrap input disappears from the repository, reproducibility of the claim is broken even if an old artifact once worked.

The project should therefore record both:

- historical achievement;
- current reproducibility from the checked revision.

This chapter classifies the inspected revision only.

## SH0 — host-built native toolchain is validated

SH0 means the ChrisOS-native toolchain components exist as source and their host-built forms pass dedicated tests.

Required components include:

- KCC;
- ChrisAsm;
- ChrisO serialization/object model;
- ChrisLd.

The host compiler may still be GCC.

The goal is not self-hosting yet. The goal is to establish that the project's own compiler/linker logic is functional enough to become a bootstrap stage.

## SH0 evidence

The current repository provides:

```text
host-chrisasm-test
host-chrisld-test
host-kcc-test
host-chriso-test
```

The tests exercise real implementation code.

KCC tests compile supported source constructs.

ChrisAsm tests instruction encoding and rejection behavior.

ChrisLd tests executable generation, section handling, symbols and relocations.

ChrisO tests the project's native object representation.

This is valid SH0 evidence.

## SH0 non-claims

SH0 does not mean:

- KCC compiled itself;
- ChrisOS built its own running kernel;
- host GCC has been removed;
- the guest can boot an internally built artifact.

The producing compiler for SH0 tools may still be the host toolchain.

## SH1 — native tools execute inside ChrisOS

SH1 requires that native toolchain logic execute inside the running guest and produce useful native artifacts without invoking host compiler processes during that operation.

The current shell provides:

```text
kcc <source>
as <source>
```

The implementations call KCC and ChrisAsm libraries linked into the kernel.

They then use ChrisLd through the native linker helper to emit ELF files.

This is genuine guest-side compilation and assembly.

## SH1 provenance limitation

The code executing inside the guest was embedded in a kernel built by host GCC.

Thus SH1 demonstrates operational independence for the compilation action, not independent provenance of the compiler binary.

This distinction is essential.

A compiler running inside ChrisOS is not automatically a compiler produced by ChrisOS.

## SH1 acceptance evidence

A strong SH1 gate should:

1. boot a known ChrisOS image;
2. create or load a test C source in ChrisFS;
3. run guest `kcc`;
4. produce an ELF;
5. validate the ELF;
6. execute it;
7. assert deterministic observable output.

Equivalent evidence should exist for guest ChrisAsm.

The source supports this architecture, but dedicated end-to-end SH1 gates should be recorded explicitly.

## SH2 — selected real kernel units compile in the guest

SH2 moves beyond toy programs.

It requires KCC running in the guest to compile source files taken from the real kernel tree.

The current `chrisbuild_mk_kernel` function is aimed at this stage.

It reads a guest-side `SYS/BUILD.MK`, resolves selected C paths under `SYS/KERNEL`, and calls `kcc_compile_source` for each unit.

This is the correct direction for SH2.

## SH2 artifact

The output for a successful selected-unit build is normally:

```text
BIN/KERNEL.ELF
```

However, the artifact name alone does not prove that it contains the full kernel.

At SH2 the artifact may be deliberately partial.

The evidence must record exactly which real source units were included.

## SH2 blocker in the current tree

The seed utility expects:

```text
learn/fase16-selfhost64/stubs/SYS_BUILD.MK
```

but that path is absent from the inspected revision.

Therefore the repository does not currently contain the complete declared input required to reproduce the intended seeded SH2 workflow.

This makes the current SH2 gate incomplete even though the builder code exists.

## SH2 compiler-coverage requirement

A proper SH2 report should list, per source file:

- compiled successfully;
- unsupported language feature;
- unresolved external;
- section/link limitation;
- runtime gate if executable.

"Substantial kernel support" is not a measurable criterion unless the exact source set is versioned.

A manifest hash is therefore part of strong SH2 evidence.

## SH3 — structurally complete kernel ELF is built internally

SH3 requires that the guest toolchain produce a kernel ELF representing the complete required kernel artifact graph.

This is substantially stronger than compiling selected units.

The build must account for:

- all required C translation units;
- assembly units;
- generated source/assets;
- required symbols;
- TEXT/RODATA/DATA/BSS;
- relocations;
- link address;
- valid entry point.

## Current SH3 blockers

The current internal builder has several blockers.

First, its manifest parser collects only C objects.

Encountering `ASM_OBJECTS=` stops C collection but does not assemble those objects.

Second, the merge path uses:

```text
chriso_merge_text
```

which merges TEXT but not full RODATA/DATA/BSS content from each unit.

Third, the combined text buffer is limited to 65536 bytes.

These constraints mean the current `mk kernel` path cannot be assumed to represent the complete contemporary kernel.

## SH3 validation

A produced ELF should pass `chrisld_validate`.

The validator checks important structural properties such as:

- ELF64 little-endian identity;
- x86-64 machine;
- program-header shape;
- filesz <= memsz;
- no W+X load segment;
- non-overlapping load segments;
- entry point inside executable memory.

A future SH3 gate should make this validation mandatory.

## SH4 — internally built kernel is installed as boot artifact

SH4 requires promotion from "kernel file exists" to "the next boot path contains that exact file."

For the current disk layout, the distinction between:

```text
BIN/KERNEL.ELF
```

and:

```text
BOOT/KERNEL.ELF
```

is critical.

The host-side disk build populates `BOOT/KERNEL.ELF`.

The internal builder writes `BIN/KERNEL.ELF`.

## Current SH4 blocker

`chrisbuild_mk_install` does not copy the internal ELF to the boot path.

It reads `BIN/KERNEL.ELF` and writes it back to the same path.

No bootloader configuration is updated and no boot artifact is replaced.

Therefore the current `mk install` implementation does not establish SH4.

## SH4 atomicity requirement

A robust install stage should avoid corrupting the only bootable kernel.

A stronger design would:

1. validate the new ELF;
2. write a temporary boot artifact;
3. sync storage;
4. rename or switch atomically;
5. retain a rollback image;
6. record the expected hash for next boot.

This turns install into a controlled state transition rather than a copy operation.

## SH5 — reboot proves the internally built kernel is running

SH5 is the first level at which "the running ChrisOS kernel is self-built" becomes a defensible statement.

The machine must reboot after SH4 and provide evidence that the running image is exactly the internally produced artifact.

A fixed string such as:

```text
ChrisOS selfhost=1
```

is not sufficient.

The current kernel prints that string unconditionally.

## SH5 identity evidence

Strong SH5 evidence should include an identifier embedded into the generated kernel and known before reboot.

Examples include:

- full artifact SHA-256;
- build manifest hash;
- source revision plus stage ID;
- signed or structured build record.

After reboot, the kernel should report that identity.

The gate must compare the runtime identity with the pre-reboot internally produced artifact.

## SH5 negative controls

A strong gate should also ensure that a host-built kernel was not silently restored.

Useful negative controls include:

- remove/rename alternate boot images;
- verify boot-path hash immediately before reboot;
- assert an internally generated nonce/build ID after reboot;
- fail if the identity matches the bootstrap kernel instead.

Without such controls, a successful reboot may prove only that some bootable kernel exists.

## SH6 — stage convergence and reproducibility

SH6 is a compiler/bootstrap convergence level.

The self-built system must be able to produce a subsequent stage under a defined equivalence rule.

A conceptual sequence is:

```text
host bootstrap
    -> stage A toolchain/kernel
    -> stage B built by A
    -> stage C built by B
```

The project then compares B and C.

## Byte identity versus semantic convergence

ChrisOS embeds Git revision and build date in normal build identity.

Therefore byte-for-byte equality cannot be assumed unless nondeterministic metadata is normalized.

SH6 must state its equivalence rule explicitly.

Possible rules are:

- identical bytes after deterministic-build changes;
- identical loadable sections;
- identical compiler output on a test corpus;
- equivalent execution under defined gates.

The strongest long-term target is deterministic byte identity for controlled inputs.

## Compiler self-production

A complete SH6 story should include the compiler itself.

It is not enough for KCC to build the kernel while KCC forever originates from GCC.

A stronger chain is:

```text
GCC-built KCC0
   -> KCC0 builds KCC1
   -> KCC1 builds KCC2
   -> compare KCC1/KCC2
```

Then KCC1 or KCC2 should build the kernel.

The current inspected source does not provide evidence that this chain has been completed.

## Current revision classification

The inspected revision can be classified conservatively as:

```text
SH0  supported by direct host tests
SH1  implementation exists and guest commands are real
SH2  partial implementation; reproducible seeded gate is currently broken
SH3  not established
SH4  not established
SH5  not established
SH6  not established
```

This classification is intentionally stricter than marketing language.

It is based on artifact provenance and executable transitions.

## Why strict classification matters

Self-hosting claims are easy to inflate accidentally.

For example:

- embedding compiler source in the kernel is not self-compilation;
- producing an ELF is not booting it;
- printing "selfhost=1" is not provenance;
- copying a host-built compiler into ChrisFS is not compiler self-production;
- compiling a fixture is not compiling the current kernel;
- booting once is not reproducibility.

The SH ladder prevents these category errors.

## Required evidence record

Every future SH milestone should preserve:

```text
source revision
bootstrap tool hashes
input manifest hash
tool versions/hashes
command or automated gate
artifact hash
validation result
runtime result
logs
date/environment
```

For SH4+, boot-path hashes are mandatory.

For SH5+, post-reboot runtime identity is mandatory.

For SH6, stage comparison criteria and results are mandatory.

## Failure semantics

A failed higher level does not invalidate lower levels.

For example, an install failure after a valid internal ELF may leave SH3 evidence intact while SH4 fails.

Likewise, nondeterministic stage output may preserve SH5 while SH6 remains unproved.

This separation makes debugging and reporting much clearer.

## Recommended automated gates

The repository should eventually provide explicit targets such as:

```text
selfhost-sh0
selfhost-sh1
selfhost-sh2
selfhost-sh3
selfhost-sh4
selfhost-sh5
selfhost-sh6
```

Each target should depend on the preceding level and emit a machine-readable result.

A gate should fail closed: missing manifest, skipped validation, unavailable artifact, or identity mismatch must produce failure, not a warning.

## Revision note

This evidence model was written against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. It deliberately distinguishes existing guest-native tooling from unproved full self-hosting and provides concrete criteria for promoting future claims from SH0 through SH6.
