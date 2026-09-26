---
id: elf-linking
lang: en
type: technical-chapter
volume: 03-boot
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/linker.ld
  - kernel/metal/elf.c
  - compiler/chrisld/chrisld.c
  - compiler/chrisld/chriso.h
symbols: []
depends_on:
  - cpu-datapath-isa
related:
  - power-on-kstart
  - native-toolchain
  - processes-syscalls
---

# ELF, object files and kernel linking

## Translation units are not executables

Compiling a C source file normally produces an object containing machine code, data, symbols and relocation information. Addresses of external functions or final section positions may not yet be known.

The linker combines objects, resolves symbols, applies relocations and creates an executable layout.

```text
C / assembly sources
       │
       ▼
   compiler / assembler
       │
       ▼
   relocatable objects
       │
       ▼
      linker
       │
       ▼
       ELF
```

## Sections and segments

ELF distinguishes link-time organization from load-time organization.

**Sections** organize content for linking and tooling: text, read-only data, writable data, BSS, symbols and relocations.

**Program headers/segments** tell a loader what ranges must be mapped into memory and with what properties.

A kernel linker script therefore controls both symbol addresses and memory protection intent.

## Relocations

Suppose one object contains a call to a function defined in another object. The assembler cannot always encode the final displacement because the target's final address is unknown. It emits a relocation describing what must be patched after layout is known.

Different relocation types encode different mathematical operations: absolute addresses, PC-relative displacements, width-limited forms and architecture-specific semantics.

A linker that "concatenates text bytes" without correctly resolving relocation types is not equivalent to a production linker.

## Symbols

Symbols name code or data locations and carry binding/visibility/type information in mature object formats. Linkers must detect undefined references and often duplicate global definitions.

The ChrisOS native toolchain uses its own ChrisO object representation on the path toward an internally controlled toolchain. Its semantics must eventually be rich enough for the actual kernel, not merely a trivial executable.

## Kernel linker script

`kernel/metal/linker.ld` is part of the kernel architecture. It fixes the higher-half address model, entry point and output segments. Changing it can invalidate assumptions in boot, virtual memory and the bootloader protocol even if no C source changes.

A linker script is therefore executable architecture policy.

## User ELF loading

`kernel/metal/elf.c` addresses the inverse operation: consuming an executable. A secure loader must validate ranges before mapping them:

- ELF identity and machine;
- program-header bounds;
- file-size versus memory-size relationships;
- integer overflow;
- virtual-address policy;
- overlapping mappings;
- entry-point validity;
- writable/executable combinations where prohibited.

The loader then allocates physical pages, maps them into the process address space, copies file-backed bytes and zero-initializes BSS ranges.

## W^X

Writable and executable memory simultaneously increases exploitation opportunities. A loader can enforce a W^X policy by refusing segments that request both permissions or by constructing stricter mappings.

The exact policy is an operating-system choice constrained by the executable format and hardware page-table permission bits.

## ChrisLd and bootstrap maturity

ChrisLd exists because self-hosting eventually requires the project to control its own final executable production. The important milestone is not "the output starts with the ELF magic." It is semantic equivalence for the requirements of the target image:

- all required objects included;
- symbols resolved;
- relocations applied;
- section/segment alignment correct;
- kernel entry exact;
- Limine-visible structures preserved;
- stack and BSS represented correctly;
- permissions appropriate.

This is why toolchain validation must compare structure and behavior, not only file signatures.
