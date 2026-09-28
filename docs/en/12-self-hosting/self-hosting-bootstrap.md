---
id: self-hosting-bootstrap
lang: en
type: technical-chapter
volume: 12-self-hosting
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/tools/chrisbuild.c
  - tools/seed_selfhost.c
symbols: []
depends_on:
  - native-toolchain
  - desktop-applications
related:
  - installation-real-hardware
  - validation-evidence
---

# Self-hosting, bootstrapping and reproducibility

## Definition

A system is self-hosting when it can build meaningful parts of itself using tools that run within or are produced by the system, according to a stated criterion.

The term is ambiguous unless levels are defined. Compiling one application inside the OS is a different claim from rebuilding the kernel, and rebuilding the kernel is different from producing complete installation media without a host toolchain.

## Bootstrap chain

Any compiler starts from something. An early compiler may be built by GCC on the host. Later, the new compiler can compile a successor of itself.

```text
host toolchain
    ↓
stage 0 compiler
    ↓
stage 1 built by stage 0
    ↓
stage 2 built by stage 1
    ↓
convergence / behavior checks
```

The bootstrap chain is a provenance graph.

## ChrisOS levels

The project's self-host audit defines SH0–SH6 and explicitly marks current higher stages as unproven. At the documented revision:

- host GCC/ld remains the kernel build path;
- KCC host gates cover substantial `kernel/metal` behavior;
- the whole kernel is not yet compiled by KCC;
- ChrisLd has not produced the booted `BIN/KERNEL.ELF`;
- no internally built kernel has been installed and rebooted as SH5 evidence;
- full media/system reproduction still requires host tooling.

## Why a source compiler is not enough

A self-hosted kernel build requires the entire artifact graph:

```text
C units
assembly units
generated assets
linker semantics
boot protocol structures
        ↓
kernel ELF
        ↓
installation / boot
        ↓
observable identity of the new kernel
```

If one stage still silently invokes host ld or NASM, the dependency remains.

## Reproducibility

Self-hosting and reproducible builds are related but different.

Self-hosting asks **who/what can build the artifact**. Reproducibility asks whether defined equivalent inputs produce an artifact or behavior matching a reproducibility criterion.

Timestamps, build IDs and environmental paths can make byte-for-byte identity differ even when semantics are equivalent.

## Trust

Compiler bootstrapping has a classic trust problem: source review does not by itself prove the binary corresponds to source if the compiler is malicious. Diverse double compilation is one advanced technique for investigating this class of issue.

ChrisOS does not need to solve every formal trust problem before self-hosting is useful, but documentation should distinguish compiler provenance from source-level intent.

## Practical proof

A strong ChrisOS self-host milestone would record:

1. exact starting revision;
2. compiler/tool binaries used;
3. internally produced kernel hash;
4. ELF validation;
5. installation of that exact kernel;
6. reboot without substituting the host-built image;
7. serial/build identity proving the running kernel;
8. repeatable gate command.

That turns "self-hosted" from a narrative label into reproducible evidence.
