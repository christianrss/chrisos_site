---
id: chrisld
lang: en
type: technical-chapter
volume: 07-language-systems
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/chrisld/chrisld.h
  - compiler/chrisld/chrisld.c
  - compiler/chrisld/chriso.h
  - compiler/chrisld/chriso.c
  - compiler/chrisasm/chrisasm.c
  - kernel/tools/native_link.c
  - kernel/tools/chrisbuild.c
  - tools/test_chrisld.c
symbols:
  - chrisld_link
  - chrisld_link_objects
  - chrisld_validate
  - resolve_sym
  - duplicate_globals
  - LdMap
  - sym_addr
  - reloc_site
  - apply_one
  - pack_sec
  - wr_phdr
depends_on:
  - native-toolchain
  - chriso
  - chrisasm
  - elf-linking
  - calling-conventions
related:
  - kcc
  - self-hosting-bootstrap
  - linker-script
  - internal-kernel-build
---

# ChrisLd

## Scope

ChrisLd is the native linker in the experimental ChrisOS toolchain. It consumes one or more ChrisO object images, resolves symbols and relocations, lays out their sections, and emits an ELF64 executable for x86-64.

The current path is:

    ChrisO objects
        -> duplicate-global check
        -> per-section packing
        -> symbol resolution
        -> relocation application
        -> ELF64 ET_EXEC layout
        -> structural validation

ChrisLd is not a wrapper around GNU ld, lld, mold or the host linker. The ELF image is written directly by project code in compiler/chrisld/chrisld.c.

Its current goal is narrower than a production ELF linker. It implements the contracts needed by the ChrisOS native-toolchain experiments while keeping the linker small enough to run in a freestanding environment.

## Public interface

compiler/chrisld/chrisld.h exposes three entry points:

    int chrisld_link(const ChrisoImage *img, uint64_t load_addr,
                     void *out, uint32_t cap, uint64_t *entry_out);

    int chrisld_link_objects(const ChrisoImage *const *imgs, uint32_t n,
                             uint64_t load_addr, void *out, uint32_t cap,
                             uint64_t *entry_out);

    int chrisld_validate(const void *elf, uint32_t n);

chrisld_link is a convenience wrapper for one object.

chrisld_link_objects is the actual multi-object linker. It accepts up to 32 object pointers because the internal mapping structure has a fixed object dimension.

chrisld_validate checks important structural properties of a produced ELF image. It is a validation helper, not a complete hostile-input ELF verifier.

The header also defines CHRISLD_ELF_MAX as one MiB. That constant is used by current in-kernel integration as an output-buffer policy. The core linker still obeys the cap supplied by the caller.

## Input object contract

ChrisLd consumes ChrisoImage objects.

Each object can provide four logical sections:

- text;
- rodata;
- data;
- BSS.

It also carries a symbol table and relocation table.

ChrisLd does not parse assembly or C. By the time execution reaches this layer, instruction bytes already exist and unresolved references are represented as ChrisO relocations.

This separation is important: ChrisAsm determines instruction encoding, while ChrisLd determines final placement.

## Fixed object-count boundary

The internal LdMap contains:

    at[4][32]

so one link invocation accepts at most 32 ChrisO images.

The function rejects:

- a null image array;
- zero objects;
- more than 32 objects;
- a null output pointer;
- a null entry output pointer;
- any null element inside the object array.

This is a deliberate fixed-capacity implementation boundary.

The in-kernel build manifest can list more C paths than this current linker accepts directly, which is one reason the current kernel builder uses an intermediate text-only merge path instead of passing every compilation unit directly to chrisld_link_objects.

## Duplicate global definitions

Before section layout, ChrisLd calls duplicate_globals.

The algorithm examines every defined global symbol in every object and compares it against global symbols in later objects.

If the same global name is defined by more than one object, the link fails.

For N objects and symbol counts S_i, the implementation is conceptually quadratic in the total number of global definitions because it performs nested scans.

That is acceptable for the current fixed and small object sets, but it is not a scalable symbol-table strategy for a large production linker.

A hash-based global definition table would reduce lookup and duplicate-detection costs.

## Symbol resolution rules

resolve_sym implements the current resolution model.

If the referenced symbol is already defined and is not global, it resolves within its originating object.

Otherwise, ChrisLd scans all objects for a defined global symbol with the same name.

A unique global definition is required.

If a second matching global definition is found, resolution fails.

If an undefined symbol has no global definition, resolution fails.

There is no weak-symbol precedence model, symbol versioning, visibility policy, archive extraction or dynamic symbol resolution.

The model is intentionally strict:

- local definitions stay local;
- global definitions must be unique;
- undefined references must find exactly one global definition.

## Section packing

Before copying bytes, pack_sec computes where each object's contribution begins inside each combined section.

For every section, object contributions are concatenated in input order.

After the first nonempty contribution, the next nonempty contribution is aligned to 16 bytes.

For an object i and section s, LdMap.at[s][i] stores that object's offset inside the combined section.

LdMap.total[s] stores the final combined size.

The four section families are packed independently.

This produces stable object-relative offsets before final virtual and file addresses are assigned.

## Read-execute region

Text and rodata are combined into the executable/read-only side of the output.

If rodata exists, its combined region begins after text aligned to 16 bytes:

    ro_off = align_up(total_text, 16)

The combined RX file size is therefore:

    rx_filesz = text_total + optional alignment + rodata_total

Text starts at load_addr in virtual memory.

Rodata follows text at load_addr + ro_off.

This is a simpler policy than a full linker script, but it preserves a meaningful execution/data permission boundary.

## Writable region

If either data or BSS is nonempty, ChrisLd emits a separate writable load segment.

The RX memory size is rounded up to a 4 KiB page boundary.

The writable virtual address becomes:

    rw_vaddr = load_addr + rx_memsz

Within the writable address range:

- initialized data comes first;
- BSS follows data.

A BSS symbol address is calculated as:

    rw_vaddr
      + total_data
      + object_bss_offset
      + symbol_offset

BSS contributes to memory size but not file size.

This is the standard high-level idea of zero-filled memory beyond file-backed initialized data, implemented in the project's compact layout.

## One-segment and two-segment outputs

ChrisLd has two layout modes.

For a text/rodata-only program, it writes one PT_LOAD segment with read and execute permissions.

For an image containing data or BSS, it writes two PT_LOAD segments:

| Segment | Contents | Flags |
| --- | --- | --- |
| RX | text + rodata | PF_R | PF_X |
| RW | data + BSS | PF_R | PF_W |

It never intentionally emits a writable-executable PT_LOAD.

chrisld_validate explicitly rejects a load segment whose flags contain both W and X.

This W^X split is one of the most important security properties of the current linker design.

## ELF header policy

The output is ELF64, little-endian, System V ABI, ET_EXEC, EM_X86_64.

ChrisLd writes the ELF header fields directly.

Current constants include:

- ELF header size: 64 bytes;
- program-header size: 56 bytes;
- one or two program headers;
- page alignment: 4096 bytes.

No section-header table is emitted.

The output is therefore a loader-oriented executable rather than a richly described ELF file intended for generic post-link tooling.

This is sufficient for an executable image whose loader primarily needs program headers.

## File placement

For a one-segment output, the RX bytes begin after the ELF header and one program header, rounded to a 16-byte boundary.

With writable state present, the implementation places the RX payload at a page-oriented file offset derived from the load address's page offset.

The RW file data, when present, follows after the RX memory-size span.

BSS receives no file bytes.

The mapping is designed so the PT_LOAD entries describe coherent virtual ranges with distinct permissions.

## Entry-point selection

ChrisLd searches all defined symbols for an entry point.

The priority is:

1. kstart;
2. main;
3. the supplied load address if neither symbol exists.

The first defined kstart found wins.

Only if no kstart exists does the linker scan for main.

This reflects the distinction between the kernel-native entry convention and simpler user/test programs.

The linker does not currently require that an explicit kstart or main symbol exist. A caller can therefore receive an ELF whose entry defaults to the base load address.

chrisld_validate subsequently requires the selected entry address to fall inside an executable PT_LOAD range.

## Runtime symbol addresses

sym_addr converts an object-relative ChrisO symbol into its final virtual address.

Text symbols are based at load_addr plus the object's packed text offset.

Rodata symbols add ro_off.

Data symbols use rw_vaddr plus the object's packed data offset.

BSS symbols use rw_vaddr plus total data size plus the object's packed BSS offset.

This function is central to relocation evaluation because every relocation ultimately needs the resolved symbol's runtime address.

## Relocation-site mapping

reloc_site converts a ChrisO relocation location into two coordinates:

- file_at: where the relocation field resides in the output file buffer;
- place: the runtime virtual address of that relocation field.

Text, rodata and data relocation sites are currently supported.

A relocation whose target field is in BSS is rejected because BSS has no file-backed bytes to patch.

This distinction follows directly from the BSS model.

## Relocation formulas

apply_one implements the supported relocation types.

For R_X86_64_64:

    result = S + A

and eight bytes are written.

For R_X86_64_PC32 and R_X86_64_PLT32:

    result = S + A - P

where S is the symbol address, A the signed addend and P the runtime address of the relocation field.

The result must fit signed 32 bits.

For R_X86_64_32 and R_X86_64_32S, the implementation currently computes S + A and requires the resulting unsigned value not to exceed 0xffffffff.

This means the current R_X86_64_32S handling does not independently enforce the signed-32-bit range normally associated with that ELF relocation name. It shares the same upper-bound test as R_X86_64_32.

That behavior should be treated as the current ChrisLd contract, not generalized to full ELF semantics.

Unsupported relocation types fail the link.

## Relocation safety checks

For each relocation, ChrisLd first verifies that sym_index is within the originating object's symbol table.

It then resolves the symbol, maps the relocation site and checks the write width against the generated file length.

PC-relative displacement overflow is rejected.

These checks prevent several classes of silent truncation.

However, the linker trusts other parts of the ChrisoImage more than a hardened object parser would. For example, it does not perform a complete standalone validation pass over every symbol section index and every section-relative symbol offset before layout.

Current ChrisO objects are expected to come from project-controlled tooling.

## ELF validator

chrisld_validate checks:

- non-null input;
- at least a 64-byte ELF header;
- ELF magic;
- 64-bit class;
- little-endian data encoding;
- x86-64 machine ID;
- expected program-header entry size;
- at least one program header;
- every inspected program header fits inside the supplied input;
- PT_LOAD filesz is not greater than memsz;
- no PT_LOAD is simultaneously writable and executable;
- PT_LOAD virtual ranges do not overlap;
- the entry point lies within an executable PT_LOAD.

This is useful executable evidence for the linker output contract.

## Validator limitations

chrisld_validate is intentionally incomplete as a generic ELF verifier.

The current implementation does not fully validate, among other things:

- ET_EXEC type;
- ELF version and OSABI fields;
- p_offset plus p_filesz staying inside the supplied file;
- p_align consistency;
- congruence between file offsets and virtual addresses;
- integer-overflow-safe range arithmetic for every malformed input;
- section headers, because the linker does not emit them.

It also narrows e_phoff to a 32-bit local offset when walking program headers.

The function should therefore be used as a project output sanity check, not as a security boundary for arbitrary untrusted ELF files.

## Validation evidence

tools/test_chrisld.c exercises several meaningful contracts.

The first test assembles a single main function, links it at a high-half address, verifies ELF magic, verifies that a text-only image has one PT_LOAD, and runs chrisld_validate.

The multi-object test creates a caller with call foo and a separate object defining foo.

It verifies that:

- multi-object linking succeeds;
- the external call relocation is resolved to the expected displacement;
- linking the caller alone fails because foo is undefined;
- two global foo definitions are rejected.

A section-layout test creates text, rodata and BSS.

It verifies that:

- rodata and BSS survive assembly;
- the linked ELF has two PT_LOAD entries;
- the second segment is read/write rather than executable;
- writable memory begins at the expected page boundary;
- a RIP-relative reference to BSS is relocated correctly;
- rodata bytes appear at the expected output location.

These tests provide concrete evidence for symbol resolution, relocation, section layout and W^X segmentation.

They do not prove all supported relocation types or all malformed-input paths.

## In-kernel integration

kernel/tools/native_link.c allocates a one-MiB temporary buffer, calls chrisld_link at NATIVE_USER_LOAD, writes the resulting ELF into ChrisFS and frees the buffer.

That path is a real in-kernel consumer of the linker.

kernel/tools/chrisbuild.c also calls ChrisLd while experimenting with an internal kernel build.

Its current object-combination stage is more limited than ChrisLd itself because the builder merges compilation units using chriso_merge_text before final linking.

That helper only merges text and related tables under a narrow contract.

Consequently, the existence of chrisld_link_objects must not be used to claim that the current internal kernel builder already reproduces the full production link.

## Relationship with the production linker script

ChrisLd uses a hard-coded compact layout policy.

The ordinary production kernel build has a richer linker-script contract covering the kernel's actual section placement and boot expectations.

The experimental native linker therefore proves executable linking mechanisms, symbol resolution and permission-separated load segments, but it is not yet a drop-in replacement for every production-link detail.

This distinction is especially important for self-hosting claims.

## Complexity

Let O be the number of objects, S the total symbol count, R the total relocation count and B the total copied section bytes.

Section packing and section copying are approximately O(O + B).

Relocation iteration is O(R), but each global symbol resolution can scan symbols across all objects, making the current worst-case lookup cost proportional to S per unresolved/global reference.

Duplicate-global detection is also based on nested scans.

The implementation is suitable for small fixed object sets.

A larger linker would normally build indexed symbol maps and perform validation in explicit phases.

## Failure behavior

The linker returns -1 for structural or semantic failures, including:

- invalid arguments;
- more than 32 objects;
- duplicate global definitions;
- no linkable content;
- insufficient output capacity;
- invalid relocation symbol index;
- unresolved or ambiguous symbol;
- unsupported relocation section;
- unsupported relocation type;
- relocation write outside the generated file;
- PC-relative range overflow.

There is no detailed public linker diagnostic structure yet.

Callers receive success length or failure.

## Current limitations

Major current boundaries include:

- maximum 32 objects per direct multi-object link;
- fixed ChrisO symbol and relocation capacities;
- simple O(S) symbol resolution;
- quadratic duplicate-global detection;
- no weak symbols;
- no archives or lazy extraction;
- no dynamic linking;
- no GOT/PLT construction beyond applying the project's PLT32 relocation;
- no TLS;
- no section-header output;
- no arbitrary linker script;
- no dead-section elimination;
- no identical-code folding;
- no link-time optimization;
- incomplete hardened validation of hostile object/ELF input;
- simplified R_X86_64_32S range semantics;
- no rich diagnostics.

These constraints define the experimental linker profile.

## Roadmap boundary

Future work can improve ChrisLd without changing the educational value of the current implementation.

Natural extensions include:

- indexed global symbol tables;
- an explicit validation phase for every ChrisO field;
- structured diagnostics;
- stronger overflow checking;
- exact signed semantics for R_X86_64_32S;
- general section alignment metadata;
- production-compatible linker-script concepts;
- more relocation families;
- larger or dynamic object sets;
- debug metadata;
- deterministic link maps;
- stronger reproducibility evidence.

Those are future directions, not current guarantees.

## Revision provenance

This chapter documents ChrisLd as observed in ChrisOS main revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.

The implementation authority is compiler/chrisld/chrisld.c and compiler/chrisld/chrisld.h. The input-object contract comes from compiler/chrisld/chriso.h. tools/test_chrisld.c supplies direct executable host evidence. kernel/tools/native_link.c and kernel/tools/chrisbuild.c show the current in-kernel integration boundaries.
