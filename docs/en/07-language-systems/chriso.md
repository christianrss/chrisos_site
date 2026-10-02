---
id: chriso
lang: en
type: technical-chapter
volume: 07-language-systems
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/chrisld/chriso.h
  - compiler/chrisld/chriso.c
  - compiler/chrisasm/chrisasm.c
  - compiler/chrisld/chrisld.h
  - compiler/chrisld/chrisld.c
  - tools/test_chriso.c
  - tools/test_chrisasm.c
  - tools/test_chrisld.c
symbols:
  - ChrisoSym
  - ChrisoRel
  - ChrisoImage
  - chriso_init
  - chriso_write
  - chriso_read
  - chriso_merge_text
depends_on:
  - native-toolchain
  - data-representation-layout
  - elf-linking
related:
  - chrisasm
  - chrisld
  - kcc
  - chriso-spec
---

# ChrisO object format

## Scope

ChrisO is the compact object representation used between ChrisAsm/KCC and ChrisLd.

It carries the minimum information required by the current native toolchain:

- materialized text bytes;
- read-only data bytes;
- writable data bytes;
- BSS size;
- symbols;
- relocations.

ChrisO is not ELF relocatable object format and is not intended to reproduce every feature of ELF64 ET_REL. It is a project-specific intermediate object contract that is simpler to construct inside ChrisOS and simpler for ChrisLd to consume.

The object has both an in-memory representation, ChrisoImage, and a serialized byte representation written by chriso_write and read by chriso_read.

## Constants and versions

The current format constants are:

| Constant | Value |
| --- | ---: |
| CHRISO_MAGIC | 0x4F524843 |
| current version | 2 |
| legacy accepted version | 1 |
| sections | 4 |
| maximum symbols | 256 |
| maximum relocations | 512 |

Version 2 adds explicit BSS size in the header and stores a 20-byte relocation record that includes relocation type.

Version 1 remains readable for compatibility. When reading a version 1 object, BSS size is treated as zero and legacy symbol records are normalized to local/notype semantics.

Writers always emit the current version.

## In-memory image

ChrisoImage contains:

    uint8_t *sec[4]
    uint32_t sec_size[4]
    ChrisoSym sym[256]
    uint32_t nsym
    ChrisoRel rel[512]
    uint32_t nrel

The four section indices are text, rodata, data and BSS.

For text, rodata and data, sec can point to materialized bytes.

BSS is represented by sec_size only. A BSS byte buffer is unnecessary because the section denotes zero-initialized storage rather than file payload.

The image uses fixed-capacity symbol and relocation arrays, so object construction never dynamically grows those tables.

## Section semantics

The section model is intentionally small.

| Section | Purpose | Serialized payload |
| --- | --- | --- |
| text | executable machine code | yes |
| rodata | read-only constants | yes |
| data | initialized writable data | yes |
| BSS | zero-initialized writable storage | no |

The absence of BSS bytes is important to both file size and linker semantics. A 64 KiB BSS does not add 64 KiB of zero bytes to a ChrisO file; only its size is recorded.

The linker later allocates address space for that logical section.

## Serialized layout

The serialized format begins with a fixed 64-byte header.

The first eight 32-bit words are currently assigned as follows:

| Word | Meaning |
| ---: | --- |
| 0 | magic |
| 1 | version |
| 2 | symbol count |
| 3 | relocation count |
| 4 | text size |
| 5 | rodata size |
| 6 | data size |
| 7 | BSS size in version 2 |

The remainder of the 64-byte header is zeroed by the current writer.

After the header the file is laid out sequentially:

    64-byte header
    text bytes
    rodata bytes
    data bytes
    symbol records
    relocation records

BSS contributes no byte range.

There is no per-section file-offset table because the offsets are derivable from the fixed ordering and section sizes.

## File-size calculation

For version 2, chriso_file_bytes computes:

    total =
        64
        + text_size
        + rodata_size
        + data_size
        + nsym * 80
        + nrel * 20

The writer checks that the supplied destination capacity is at least this computed size.

The return value of chriso_write is the number of bytes written, or -1 on failure.

Because the public API uses uint32_t capacities and the internal size accumulator is also 32-bit, the current implementation is designed for relatively small object images rather than multi-gigabyte object files.

## Symbol record

ChrisoSym has a fixed on-disk size of 80 bytes, enforced by a static assertion.

Its fields are:

| Field | Meaning |
| --- | --- |
| name[64] | fixed-size symbol name storage |
| section | defining section index |
| offset | section-relative offset |
| size | symbol size field |
| binding | local, global or undefined |
| kind | notype, function or object |
| reserved | reserved 16-bit field |

The fixed 64-byte name simplifies serialization because a symbol record has no variable-length string table.

The trade-off is that the object model cannot represent arbitrarily long symbol names without an upstream policy for fitting them into the fixed field.

ChrisAsm already constructs symbols within this representation.

## Bindings

Three bindings are defined:

- CHRISO_BIND_LOCAL;
- CHRISO_BIND_GLOBAL;
- CHRISO_BIND_UNDEF.

An undefined symbol is a linker request rather than a definition. Its final address must be found from another object or an externally supplied linker symbol.

The format does not currently model weak symbols, visibility classes, versioned symbols or ELF-like symbol-table partitions.

## Symbol kinds

Three kinds are defined:

- notype;
- function;
- object.

ChrisAsm uses function for text labels and object for data-like labels.

The kind is descriptive metadata used by the project toolchain; it does not create a full language-level type system.

## Relocation record

ChrisoRel version 2 has a fixed on-disk size of 20 bytes, also enforced by a static assertion.

It stores:

| Field | Meaning |
| --- | --- |
| section | section containing the relocation field |
| offset | offset of the relocation field |
| sym_index | index in the object's symbol table |
| addend | signed addend |
| type | relocation type |

The format uses a subset of x86-64 ELF relocation numeric identifiers:

- R_X86_64_NONE;
- R_X86_64_64;
- R_X86_64_PC32;
- R_X86_64_PLT32;
- R_X86_64_32;
- R_X86_64_32S.

Reusing these numeric relocation meanings allows ChrisAsm and ChrisLd to apply familiar x86-64 relocation formulas without using ELF as the object container.

## PC-relative relocation semantics

ChrisAsm commonly emits PC32 and PLT32 relocations with addend -4.

For a four-byte PC-relative field, the relevant relation is conceptually:

    result = S + A - P

where S is the resolved symbol address, A is the addend and P is the relocation place.

The -4 adjustment matches the convention used by the assembler path for a displacement measured from the address after the encoded four-byte field.

ChrisLd is responsible for applying the final resolved value.

## Initialization

chriso_init zeroes the entire ChrisoImage.

This establishes the initial invariants:

- every section pointer is null;
- every section size is zero;
- no symbols exist;
- no relocations exist.

Callers constructing an object should begin from this state or another fully controlled state.

## Serialization

chriso_write first validates that both image and output buffer are non-null.

It computes the required size, rejects insufficient capacity, then zeroes exactly the serialized output length.

The writer stores header words, copies text/rodata/data bytes when their sizes are nonzero and pointers are present, then copies all symbol and relocation records in array order.

BSS bytes are never copied.

There is no checksum, hash or footer in the current format.

Integrity is therefore established by trusted transport and parser validation, not by an embedded cryptographic mechanism.

## Deserialization and zero-copy section views

chriso_read validates:

- non-null pointers;
- at least a 64-byte input;
- correct magic;
- supported version;
- symbol count no greater than 256;
- relocation count no greater than 512;
- input length at least the computed required serialized size.

After initialization, it assigns text, rodata and data section pointers directly into the supplied input buffer.

This is a zero-copy read for section payloads.

Symbols and relocations are copied into the fixed arrays inside ChrisoImage.

The ownership consequence is important: after chriso_read succeeds, the input byte buffer must remain alive and unchanged for as long as code accesses img.sec for materialized sections.

The reader does not allocate independent copies of those section bytes.

## Version 1 compatibility

Version 1 relocation entries are 16 bytes rather than 20.

The reader selects record size according to version.

For version 1 symbols it forces:

- binding to local;
- kind to notype;
- reserved to zero.

Version 1 has no BSS header word recognized by the current reader, so BSS size becomes zero.

This compatibility path lets older objects be consumed while normalizing them into the current in-memory structure.

## Validation limits of the reader

The reader performs basic structural checks, but it is not a hardened untrusted-object verifier.

For example, the current code does not independently validate every semantic relationship after reading, such as:

- whether each symbol section index is valid for its binding;
- whether each relocation section index is within the section range;
- whether each relocation sym_index is below nsym;
- whether each relocation field fits within its target section;
- whether symbol offsets are inside their defining sections.

Those checks are better understood as linker validation responsibilities in the current architecture.

Also, required-size arithmetic uses 32-bit accumulation. The format is currently intended for bounded project-generated objects, not arbitrary hostile multi-gigabyte inputs.

A future standalone verifier should validate arithmetic overflow and every cross-reference before linker use.

## chriso_merge_text

chriso_merge_text is a specialized composition helper, not a general object linker.

It appends only the source text section to the destination text section.

The function requires:

- non-null source and destination;
- a destination text buffer already present;
- combined text size no greater than 65,536 bytes;
- enough remaining symbol capacity;
- enough remaining relocation capacity.

It copies source text bytes to the current end of destination text.

## Symbol adjustment during text merge

When source symbols are appended, defined symbols in the text section have their offsets increased by the destination's original text size.

Undefined symbols are not offset-adjusted.

Symbols defined in non-text sections are copied without section-content merging. This is one reason chriso_merge_text must not be treated as a complete multi-section linker.

The helper is suitable only where its text-only contract is explicitly intended.

## Relocation adjustment during text merge

Source relocations are appended after destination relocations.

For relocations targeting fields in text, the relocation offset is increased by the original destination text size.

Every copied relocation also has its symbol index shifted by the number of symbols that existed in the destination before the source symbols were appended.

This preserves the relationship between each copied relocation and the copied symbol table entries.

The adjustment is mechanical and bounded by the fixed capacities.

## What merge_text does not do

chriso_merge_text does not:

- merge rodata payloads;
- merge data payloads;
- add BSS sizes;
- coalesce duplicate symbols;
- resolve undefined symbols;
- apply relocations;
- perform section alignment;
- produce ELF;
- enforce general linker symbol-resolution rules.

Those are linker-level concerns.

The function name should therefore be read literally: it merges text under a narrow contract.

## Relationship with ChrisAsm

ChrisAsm constructs ChrisoImage directly.

It fills section bytes, adds symbols and creates relocations while encoding assembly.

At the end of assembly, materialized section buffers are allocated and attached to the image.

ChrisO is therefore the object boundary that lets the assembler avoid knowing final executable addresses.

External calls and RIP-relative references can remain unresolved until ChrisLd sees all participating objects.

## Relationship with ChrisLd

ChrisLd consumes one or more ChrisO images and resolves them into an executable layout.

ChrisO supplies section-relative facts; ChrisLd supplies final placement.

That separation is a central linker invariant:

- assembler offsets are local to sections;
- symbol resolution selects a final definition;
- relocation application converts section-relative object state into executable addresses.

A ChrisO file is therefore not directly executable merely because its text section contains machine code.

## Complexity

Serialization and deserialization are linear in the amount of stored object state.

For object byte size B, symbol count S and relocation count R:

- writing is O(B + S + R);
- reading is O(B + S + R) in validation/copy terms, although section payloads themselves are exposed zero-copy;
- text merging is O(text_bytes + S + R).

The fixed arrays impose constant upper bounds on S and R in the current version.

## Failure behavior

chriso_write returns -1 for null inputs or insufficient output capacity.

chriso_read returns -1 for malformed high-level structure such as wrong magic, unsupported version, excessive counts or truncated input.

chriso_merge_text returns -1 for null inputs, missing destination text storage, text capacity overflow, symbol-capacity overflow or relocation-capacity overflow.

The API does not currently return a detailed error enumeration.

## Validation evidence

tools/test_chriso.c exercises a minimal round trip:

1. initialize an empty image;
2. serialize it into a 64-byte buffer;
3. read it back;
4. verify the magic.

This proves the base header path for an empty current-version object.

Additional evidence comes indirectly from tools/test_chrisasm.c and tools/test_chrisld.c, which construct and consume ChrisO symbols and relocations in non-empty toolchain flows.

The dedicated ChrisO test is currently much narrower than the full format surface. More direct tests are needed for version compatibility, each section, symbol bounds, each relocation type, malformed indices and truncated inputs.

## Current limitations

The current format deliberately trades generality for implementation simplicity.

Important limits include:

- only four fixed section classes;
- fixed 256-symbol capacity;
- fixed 512-relocation capacity;
- 64-byte inline symbol names;
- no string table;
- no weak or visibility-aware binding model;
- no COMDAT/group semantics;
- no debug sections;
- no architecture tag beyond the toolchain convention;
- no checksum or signature;
- basic rather than hardened input validation;
- text-only behavior in chriso_merge_text.

These constraints are acceptable for the current experimental toolchain but must be explicit when discussing self-hosting or compatibility.

## Roadmap boundary

A future ChrisO revision could add:

- explicit file offsets and alignment metadata;
- larger or dynamically sized symbol/relocation tables;
- string tables;
- stricter verifier rules;
- overflow-safe size arithmetic;
- architecture and ABI identifiers;
- debug/source mapping sections;
- richer symbol binding;
- explicit object ownership helpers;
- a general multi-section merge API.

None of these are properties of version 2 today.

## Revision provenance

This chapter documents ChrisO as observed in ChrisOS main revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.

The format authority is compiler/chrisld/chriso.h and compiler/chrisld/chriso.c. Interaction with assembly is evidenced by compiler/chrisasm/chrisasm.c and tools/test_chrisasm.c. Linker-side behavior is represented by compiler/chrisld/chrisld.c and tools/test_chrisld.c.
