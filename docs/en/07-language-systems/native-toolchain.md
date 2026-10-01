---
id: native-toolchain
lang: en
type: technical-chapter
volume: 07-language-systems
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/kcc/kcc.h
  - compiler/kcc/kcc.c
  - compiler/chrisasm/chrisasm.h
  - compiler/chrisasm/chrisasm.c
  - compiler/chrisld/chriso.h
  - compiler/chrisld/chriso.c
  - compiler/chrisld/chrisld.h
  - compiler/chrisld/chrisld.c
  - kernel/tools/native_link.h
  - kernel/tools/native_link.c
  - kernel/tools/chrisbuild.c
  - kernel/metal/linker.ld
  - tools/kcc_main.c
  - tools/test_kcc.c
  - tools/test_native_link.c
  - tools/seed_selfhost.c
symbols:
  - kcc_compile_source
  - kcc_compile_named
  - chrisasm_assemble
  - chriso_init
  - chriso_write
  - chriso_read
  - chriso_merge_text
  - chrisld_link
  - chrisld_link_objects
  - chrisld_validate
  - native_link_write_elf
  - chrisbuild_mk_kernel
depends_on:
  - compiler-pipeline
  - native-codegen
  - x86-instruction-encoding
  - elf-linking
related:
  - kcc
  - chrisasm
  - chriso
  - chrisld
  - self-hosting-bootstrap
  - linker-script
---

# Native toolchain: KCC, ChrisAsm, ChrisO and ChrisLd

## Scope

The ChrisOS native toolchain is a complete experimental path from a C-like kernel source subset to native x86-64 executable bytes:

    C source
      -> KCC
      -> textual x86-64 assembly
      -> ChrisAsm
      -> ChrisO object
      -> ChrisLd
      -> ELF64 executable

The project also contains in-kernel build plumbing that can invoke KCC and ChrisLd against files stored in ChrisFS.

That does **not** yet establish full self-hosting of the production kernel. The current implementation proves important compiler, assembler, object and linker mechanisms, but the in-kernel builder is still narrower than the host build and does not yet reproduce the complete production linker-script contract.

![Native toolchain pipeline](../../assets/diagrams/native-toolchain-en.svg)

## Why the toolchain exists

The ordinary ChrisOS build still relies on a host C compiler, assembler/linker ecosystem and build environment for the production kernel.

The native-toolchain line has two goals:

- make compilation and linking mechanisms explicit for teaching and systems research;
- progressively reduce the set of external tools needed to rebuild ChrisOS from inside ChrisOS.

The distinction between those goals matters. A compiler can be useful and technically substantial long before it is capable of rebuilding every translation unit and every boot artifact.

## Architectural boundary

There are four principal contracts.

| Stage | Input | Output | Current implementation |
| --- | --- | --- | --- |
| KCC | kernel-oriented C source | assembly text, then ChrisO | `compiler/kcc/kcc.c` |
| ChrisAsm | textual x86-64 subset | ChrisO | `compiler/chrisasm/chrisasm.c` |
| ChrisO | sections, symbols, relocations | serialized object image | `compiler/chrisld/chriso.c` |
| ChrisLd | one or more ChrisO images | ELF64 ET_EXEC | `compiler/chrisld/chrisld.c` |

KCC deliberately reuses ChrisAsm rather than owning an independent machine-code emitter for every instruction. This keeps one encoding path for compiler-generated assembly and handwritten assembly accepted by ChrisAsm.

## KCC front end and state

KCC is not a thin wrapper around GCC. It implements its own preprocessing, parsing, semantic state and code generation.

Its global fixed-capacity state includes:

    KCC_ASM_MAX     = 256 KiB
    KCC_PP_MAX      = 256 KiB
    KCC_SYM_MAX     = 2048
    KCC_MAC_MAX     = 256
    KCC_STRUCT_MAX  = 80
    KCC_FIELD_MAX   = 32
    KCC_TYPEDEF_MAX = 64
    KCC_ENUM_MAX    = 512
    KCC_PARAM_MAX   = 16

Important internal representations include `Type`, `Field`, `StructDef`, `Sym`, `Macro` and `Val`.

`Val` also carries lvalue category state, allowing the compiler to distinguish locals, globals, address-based lvalues and non-assignable values during lowering.

The compiler is currently implemented around process-global mutable state. It is therefore not reentrant and should not be assumed safe for concurrent independent compilations without external serialization.

## Preprocessor path

KCC has its own bounded preprocessor.

Current mechanisms include:

- object-like macros;
- function-like macros with up to four parameters;
- token pasting with `##`;
- conditional compilation;
- `defined(...)`;
- quoted and system-style includes;
- line markers for diagnostics;
- a built-in subset of standard integer/size macros.

Macro recursive expansion is bounded.

For freestanding execution, included files are read through the ChrisOS filesystem.

For host execution, normal host file reads are used.

The include search path explicitly knows about ChrisOS directories such as `kernel/metal`, `kernel/gfx`, `kernel/fs`, `compiler/chrisld`, `compiler/chrisasm` and the vendored Limine headers.

## Type and language profile

The internal KCC type model represents:

- void/bool/char;
- unsigned 8/16/32/64-bit integers;
- int;
- structs;
- pointers;
- arrays;
- function pointers;
- volatile qualification;
- float as a recognized type category.

Recognition does not imply full implementation.

The current compiler intentionally rejects native floating-point operations outside its supported subset. That is one reason that compiling substantial low-level kernel code is a stronger milestone than compiling the complete graphics stack.

## Native code generation strategy

KCC emits textual assembly into its bounded assembly buffer.

The generated assembly is subsequently consumed by `chrisasm_assemble`.

This architecture provides an inspection point: `kcc_last_asm()` exposes the generated assembly for tests and debugging.

That is used by the host suite to verify semantic properties such as:

- repeated volatile loads/stores not being optimized away;
- non-volatile dead-store reduction;
- structure-field offsets;
- control-flow targets;
- immediate values and `sizeof` results.

## KCC diagnostics

`KccDiag` records:

- source file;
- line;
- column;
- severity;
- textual message.

`kcc_compile_named` preserves a source filename for diagnostics, while `kcc_compile_source` is the simpler unnamed entry point used in several in-kernel paths.

Failures return a nonzero result and can be inspected through `kcc_last_error()`.

## ChrisAsm role

ChrisAsm translates a deliberately bounded assembly language into ChrisO.

It understands the four ChrisO sections:

    .text
    .rodata
    .data
    .bss

It distinguishes BSS size from file-backed bytes: `.zero` or `.skip` in BSS increases the section size without emitting bytes.

The parser also accepts directives including:

- `.extern`;
- `.local`;
- `.global`/global syntax;
- `.byte`;
- `.quad`;
- `.ascii`;
- `.asciz`;
- `.zero` / `.skip`.

A label in text is classified as a function symbol; labels in data-like sections are object symbols.

Local labels and forced-local symbols use local binding.

## Instruction encoding

ChrisAsm contains its own x86-64 encoding logic rather than shelling out to NASM.

The supported subset includes the instruction families required by KCC and selected low-level kernel paths, including ordinary register/memory arithmetic and control flow plus privileged/special instructions exercised by tests.

The host KCC gate checks concrete bytes for operations such as:

- `in` / `out`;
- `hlt`;
- `cli` / `sti`;
- `pause`;
- `lgdt`;
- `iretq`;
- `lock cmpxchg`.

The assembler emits unresolved symbolic references as ChrisO relocations instead of guessing final addresses.

## ChrisO object model

ChrisO version 2 is the intermediate object contract.

It has four sections:

    TEXT
    RODATA
    DATA
    BSS

A `ChrisoImage` contains section pointers/sizes plus fixed symbol and relocation tables.

Limits:

    CHRISO_SYM_MAX = 256
    CHRISO_REL_MAX = 512

A symbol stores:

- up to 64 bytes of name storage;
- section;
- offset;
- size;
- binding;
- kind.

Bindings are local, global or undefined.

Kinds distinguish untyped symbols, functions and objects.

## Relocations

ChrisO currently models these x86-64 relocation IDs:

    R_X86_64_NONE
    R_X86_64_64
    R_X86_64_PC32
    R_X86_64_PLT32
    R_X86_64_32
    R_X86_64_32S

Each v2 relocation stores:

    section
    offset
    sym_index
    addend
    type

The v2 on-disk relocation is 20 bytes. The reader retains compatibility logic for the earlier v1 layout.

This object boundary lets independently compiled units retain unresolved references until final linking.

## Symbol resolution in ChrisLd

`chrisld_link_objects` can link multiple ChrisO images.

Before layout, it rejects duplicate global definitions.

For an undefined reference, resolution searches global defined symbols with the same name across all supplied objects.

A unique match is required.

Unresolved symbols and ambiguous duplicate globals are link failures.

Local defined symbols resolve inside their originating object.

## Section packing

For each of the four sections, ChrisLd places each object's contribution into a combined section.

Contributions after the first nonempty one are aligned to 16 bytes.

The resulting layout logically separates:

    RX: .text + .rodata
    RW: .data + .bss

`.bss` contributes to memory size but not file bytes.

This is an important improvement over emitting a single RWX blob.

## ELF program-header policy

ChrisLd emits ELF64 `ET_EXEC`, machine `EM_X86_64`.

If no writable sections are present, one load segment can be emitted.

When data or BSS exists, it emits two PT_LOAD segments:

- `PF_R | PF_X` for text/rodata;
- `PF_R | PF_W` for data/BSS.

`chrisld_validate` explicitly rejects a PT_LOAD segment that is both writable and executable.

It also checks:

- ELF magic/class/data;
- x86-64 machine ID;
- program-header size/count;
- `filesz <= memsz`;
- non-overlapping load segments;
- entry point contained in an executable segment.

## Entry-point selection

ChrisLd looks first for a defined symbol named:

    kstart

If no such symbol exists, it looks for:

    main

If neither exists, the initialized default remains the supplied load address.

For the production kernel, `kstart` is the relevant native entry convention.

## Relocation application

For every relocation, the linker:

1. validates `sym_index`;
2. resolves the referenced symbol;
3. computes the output file offset and runtime place address;
4. computes the symbol runtime address;
5. applies the relocation according to its type.

For PC-relative relocations, the computed displacement must fit signed 32 bits.

Unsupported relocation types fail the link.

That failure behavior is preferable to silently truncating an address.

## Native user linking

`kernel/tools/native_link.c` provides a simpler in-kernel path for producing an ELF from one ChrisO image.

`native_link_write_elf` allocates an output buffer, calls ChrisLd at `NATIVE_USER_LOAD`, writes the result to ChrisFS and releases the temporary output buffer.

This path is useful for native user-program experiments and is separate from the kernel self-build path.

## In-kernel kernel builder

`chrisbuild_mk_kernel` reads:

    SYS/BUILD.MK

into a small `BuildManifest`.

The manifest tracks:

- output path;
- kernel load address;
- up to 48 C source paths.

For every configured C source, the builder:

1. translates the host-style path to the ChrisFS path;
2. reads up to 64 KiB of source;
3. calls KCC;
4. merges the resulting object into a combined object;
5. finally calls ChrisLd;
6. writes the ELF to the requested output path.

This is real in-kernel compiler/linker plumbing.

## Critical limitation: the builder uses text-only merge

The current builder combines units with:

    chriso_merge_text(&merged, &unit)

and initializes only a 64-KiB merged TEXT buffer.

That helper is not equivalent to `chrisld_link_objects` over the original units.

A production kernel needs more than concatenated text:

- RODATA;
- initialized DATA;
- BSS sizing;
- per-object symbols;
- unresolved relocations across units.

The normal host KCC tests prove ChrisLd can link multiple full objects. The current `chrisbuild_mk_kernel` path, however, still collapses units through the narrower merge operation.

Therefore an apparently successful in-kernel build must not yet be interpreted as semantic reproduction of the production kernel.

## Critical limitation: ASM_OBJECTS are parsed but not built

`BuildManifest` detects the `ASM_OBJECTS=` boundary only to stop collecting C paths.

It does not store or assemble the listed assembly objects.

Consequently handwritten assembly required by the full kernel is not currently part of this builder path.

This is a concrete self-hosting gap, not merely a documentation gap.

## Critical limitation: production linker-script semantics

The host production linker script sets the higher-half base and explicitly retains Limine request sections:

    .limine_requests_start
    .limine_requests
    .limine_requests_end

ChrisLd does not interpret `kernel/metal/linker.ld`.

It owns a simpler fixed layout: packed text/rodata followed by page-aligned writable data/BSS.

KCC tests demonstrate that Limine request marker bytes from `bootinfo.c` can reach initialized data, but preserving the exact production section identity and KEEP ordering is a separate contract.

A native-built kernel is not boot-equivalent until that contract is reproduced or intentionally replaced by another verified layout.

## Critical limitation: object/resource ownership

`native_image_free` currently frees only the TEXT section of a `ChrisoImage`.

The in-kernel build loop likewise explicitly frees only `unit.sec[TEXT]`.

As KCC/ChrisAsm objects can contain rodata/data allocations as well as text, full object lifetime management needs a section-complete ownership API.

This matters more as native compilation expands beyond text-heavy fixtures.

## Current host validation

`tools/test_native_link.c` exercises the basic chain:

    ChrisAsm -> ChrisO -> ChrisLd -> ELF

using a tiny `main` that returns 42.

It verifies ELF magic and the expected entry address.

`tools/test_kcc.c` is substantially deeper.

Among other cases, it checks:

- an initial self-host fixture and undefined-call relocation;
- real `kernel/metal/serial.c`;
- linking serial + klog + assembly stubs;
- BSS objects;
- volatile semantics;
- string/memory routines;
- packed and normal struct layouts;
- control flow;
- preprocessor expansion;
- enums, nested aggregates and initialized data;
- static assertions;
- privileged instruction bytes.

The current test contains an explicit set of 26 real `kernel/metal/*.c` translation units, each compiled with a required symbol check.

This is direct current-source evidence. Older prose claiming a fixed “50 of 112” probe is not a reliable description of this revision and is intentionally not retained here.

## What the existing validation proves

The current gates establish that:

- KCC can compile a nontrivial kernel-oriented C subset;
- ChrisAsm can encode the instruction subset exercised by those cases;
- ChrisO carries code/data/BSS, symbols and relocations;
- ChrisLd can resolve multiple objects and emit W^X-separated ELF program headers;
- important real kernel/metal units pass host compilation through KCC.

They do not establish:

- complete compilation of every production translation unit;
- complete replacement of all handwritten assembly;
- faithful reproduction of the production linker script;
- successful boot of a kernel made solely by the native toolchain;
- installation/reboot into that generated kernel;
- recursive rebuild of the toolchain by itself.

## Capacity and algorithmic trade-offs

The native toolchain intentionally uses bounded arrays and linear searches in many places.

Examples include:

- KCC symbol/macro/struct tables;
- ChrisO symbol and relocation tables;
- ChrisLd cross-object symbol search.

With the current small object counts this keeps implementation transparent.

For N objects with S symbols each, naive global resolution can approach O(N*S) per unresolved symbol, and duplicate-global checks are quadratic across object symbol sets.

Those choices are acceptable for the current experimental scale but should be revisited before large program linking.

## Concurrency

KCC and ChrisAsm use significant global mutable state.

Independent compilations/assemblies are not designed as lock-free concurrent operations.

The current kernel job/build paths should serialize access unless those front ends are refactored around per-compilation context objects.

ChrisLd is more naturally call-scoped, but its inputs and output buffers still require ordinary ownership discipline.

## Failure containment

Each stage fails closed on important structural problems:

- KCC records a diagnostic;
- ChrisAsm rejects unsupported/malformed syntax or capacity overflow;
- ChrisO reader rejects invalid serialized framing;
- ChrisLd rejects duplicate globals, unresolved references, bad relocation indices/types and output overflow;
- ELF validation rejects malformed or W+X segment layouts.

The caller remains responsible for reporting errors and releasing temporary section buffers.

## Self-hosting boundary

A useful hierarchy is:

    tool exists
      < tool compiles fixtures
      < tool compiles real kernel units
      < full kernel objects are produced
      < full kernel is linked with boot-equivalent layout
      < generated kernel boots
      < generated kernel is installed and rebooted
      < generated system rebuilds itself

ChrisOS is currently in the middle of this hierarchy.

The source contains genuine in-kernel compile/link infrastructure, but the complete production-kernel bootstrap remains unproven.

## Required next steps

For the native path to become a credible complete kernel builder:

1. replace text-only object merging with full multi-object linking;
2. ingest and assemble the manifest's ASM_OBJECTS;
3. preserve all ChrisO section allocations and ownership correctly;
4. model the required Limine/linker-script section contract;
5. compile every production translation unit required by the selected kernel configuration;
6. link without unresolved symbols;
7. validate ELF structure against the production contract;
8. boot it under QEMU;
9. install it to the target boot medium;
10. reboot into the generated image;
11. only then advance the corresponding self-host evidence level.

## Source map and revision

`compiler/kcc/kcc.c` is the native C-subset compiler and assembly generator.

`compiler/chrisasm/chrisasm.c` encodes assembly into ChrisO sections, symbols and relocations.

`compiler/chrisld/chriso.c` serializes/deserializes the project object format.

`compiler/chrisld/chrisld.c` performs section layout, symbol resolution, relocation and ELF64 generation.

`kernel/tools/native_link.c` is the simple in-kernel ELF writer for one native object.

`kernel/tools/chrisbuild.c` is the current in-kernel kernel-build orchestrator.

`tools/test_kcc.c` and `tools/test_native_link.c` are the principal host validation evidence for this chapter.

All current-behavior claims were reconciled against ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.
