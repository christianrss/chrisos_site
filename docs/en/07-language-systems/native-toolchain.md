---
id: native-toolchain
lang: en
type: technical-chapter
volume: 07-language-systems
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - compiler/kcc/kcc.c
  - compiler/chrisasm/chrisasm.c
  - compiler/chrisld/chriso.h
  - compiler/chrisld/chrisld.c
  - docs/KCC_STATUS.md
  - docs/CURRENT_SELFHOST_AUDIT.md
symbols:
  - kcc_compile_source
depends_on:
  - compiler-pipeline
  - elf-linking
related:
  - self-hosting-bootstrap
---

# KCC, ChrisAsm, ChrisO and ChrisLd

## Purpose

The native toolchain exists to reduce dependence on host GCC/NASM/ld for software that must execute as native x86-64, ultimately including the kernel.

Its conceptual path is:

```text
kernel-oriented C subset
        ↓
       KCC
        ↓
   native assembly/object representation
        ↓
    ChrisAsm / ChrisO
        ↓
      ChrisLd
        ↓
       ELF64
```

## Current KCC evidence

The current `docs/KCC_STATUS.md` is substantially more advanced than older audit text. Its host gate compiles every `kernel/metal/*.c` unit and checks selected exported symbols and machine-code properties.

It also validates volatile access behavior, structure layout, selected control flow, inline-assembly templates and atomic builtins used by current kernel code.

This is meaningful compiler progress, but the same status document records that a probe still compiles only 50 of 112 makefile C units.

## Why compiling one directory is not SH4

A bootable kernel requires all required translation units plus assembly stubs and correct final linking. Remaining blockers include language constructs and graphics code outside the current subset, NASM-dependent interrupt stubs, linker placement of Limine request structures and lack of a completed internally linked kernel ELF.

Therefore:

```text
"compiles kernel/metal" ≠ "builds the kernel"
"produces ELF"          ≠ "produces equivalent kernel ELF"
"host test passes"      ≠ "self-hosted boot proven"
```

## ChrisAsm

An assembler maps textual/symbolic instructions to exact machine bytes and records symbols/relocations when final addresses are unknown.

For kernel use it must cover privileged instructions, operand sizes, addressing modes, sections and relocation forms actually emitted by KCC or handwritten low-level source.

## ChrisO

ChrisO is the project's object format. An object format sits between compilation and final linking. It needs section payloads, symbol identity/binding and relocation information rich enough to combine independently compiled units.

A custom object format is useful educationally and architecturally because it makes linking semantics explicit rather than outsourcing every intermediate contract to ELF.

## ChrisLd

The linker must merge objects, lay out sections, resolve symbols, apply relocations and produce ELF program headers compatible with Limine and the kernel linker contract.

The target is not byte-for-byte equality with GNU ld unless the project explicitly chooses that criterion. The target is semantic equivalence for boot, memory layout, permissions and symbols required by the kernel.

## Differential validation

A strong validation strategy compares a host-toolchain build and native-toolchain build at several levels:

- exported symbol set;
- relocation resolution;
- ELF headers/program headers;
- section addresses/alignment;
- required Limine markers;
- entry point;
- executable behavior under QEMU;
- eventually self-produced rebuild identity.

This is more informative than checking only whether both files exist.

## Self-hosting boundary

Current self-host audit marks SH4, SH5 and SH6 unproven. Documentation must preserve this status until a gate demonstrates a complete internally built kernel, installation/reboot of that kernel and finally broader media/system reproduction according to the project's defined levels.
