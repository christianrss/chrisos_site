---
id: chriso-spec
lang: en
type: specification
volume: 15-specifications
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/chrisld/chriso.h
  - compiler/chrisld/chriso.c
  - compiler/chrisasm/chrisasm.c
  - compiler/chrisld/chrisld.c
  - compiler/chrisld/chrisld.h
  - kernel/tools/native_link.c
  - kernel/tools/native_link.h
symbols:
  - chriso_init
  - chriso_write
  - chriso_read
  - chriso_merge_text
  - chrisld_link
  - chrisld_link_objects
  - chrisld_validate
depends_on:
  - specifications-policy
  - object-files
  - linker
related:
  - elf-linking
  - chrisasm
  - chrisld
  - native-toolchain
---

# ChrisO object format

## Status

ChrisO is the native object format used by the ChrisOS toolchain between assembly/compilation and final ELF linking.

This specification describes ChrisO **version 2** as implemented at ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

The reader also accepts version 1 objects with compatibility rules described below.

ChrisO is intentionally smaller than ELF relocatable objects. It carries only the sections, symbols and relocations required by the current ChrisAsm/ChrisLd pipeline.

## Magic and version

The format constants are:

    CHRISO_MAGIC   = 0x4F524843
    CHRISO_VERSION = 2

On the little-endian x86-64 systems for which the implementation is written, the magic appears in the file as the four ASCII bytes:

    C H R O

Version 1 is identified by:

    CHRISO_VERSION_V1 = 1

The current writer always emits version 2.

## Byte-order contract

The current writer stores 32-bit header words through native `uint32_t` writes and copies the symbol/relocation structs directly into the byte stream.

The current project environment is little-endian x86-64.

Therefore the practical ChrisO v2 contract is **little-endian with the exact field sizes specified here**.

The implementation is not currently an endian-neutral serializer.

A future portable implementation should encode every integer field explicitly rather than relying on native struct representation.

## File layout

A ChrisO v2 file is laid out as:

    64-byte header
    .text payload
    .rodata payload
    .data payload
    symbol table
    relocation table

The BSS section has a declared size but contributes no bytes to the file payload.

Formally:

[
file_size =
64 +
text_size +
rodata_size +
data_size +
80 cdot nsym +
20 cdot nrel
]

for version 2.

## Header

The header is exactly 64 bytes.

The first eight 32-bit words are:

| Offset | Size | Field |
|---:|---:|---|
| 0 | 4 | magic |
| 4 | 4 | version |
| 8 | 4 | symbol count |
| 12 | 4 | relocation count |
| 16 | 4 | text size |
| 20 | 4 | rodata size |
| 24 | 4 | data size |
| 28 | 4 | BSS size |

Bytes 32 through 63 are currently zeroed by the writer and reserved.

Readers must not infer additional meaning from those bytes at version 2.

## Section identifiers

ChrisO defines four logical sections:

    CHRISO_SEC_TEXT   = 0
    CHRISO_SEC_RODATA = 1
    CHRISO_SEC_DATA   = 2
    CHRISO_SEC_BSS    = 3

The maximum section count is therefore four.

There is no arbitrary section-name table.

There is no section-header table.

The format is purpose-built around these four semantic classes.

## Section payload ordering

Payload bytes appear in fixed order:

1. text;
2. rodata;
3. data.

BSS has no serialized payload.

The sizes in the header are sufficient to locate each payload by accumulation from byte 64.

A zero-sized section contributes no bytes.

## Section-size limits

The ChrisO container itself stores section sizes as 32-bit values.

However, the current ChrisAsm implementation uses 64 KiB static buffers for emitted text/rodata/data sections.

`chriso_merge_text` also rejects text growth beyond:

    65536 bytes

Therefore practical producer limits can be smaller than the theoretical 32-bit format field.

A consumer must distinguish the serialized field width from toolchain implementation limits.

## Symbol table

Each version-2 symbol record is exactly 80 bytes.

The source enforces:

    sizeof(ChrisoSym) == 80

The layout is:

| Offset | Size | Field |
|---:|---:|---|
| 0 | 64 | name |
| 64 | 4 | section |
| 68 | 4 | offset |
| 72 | 4 | size |
| 76 | 1 | binding |
| 77 | 1 | kind |
| 78 | 2 | reserved |

Symbol names are stored in a fixed 64-byte field.

Current producers zero-initialize records and copy names with room for a terminating NUL.

Consumers should not assume arbitrary external objects are safely NUL-terminated unless validated.

## Symbol-count limit

The in-memory format model allows:

    CHRISO_SYM_MAX = 256

The reader rejects files declaring more than 256 symbols.

The writer operates on the fixed-size `ChrisoImage.sym` array, so callers must respect the same bound before serialization.

## Symbol bindings

Bindings are:

    CHRISO_BIND_LOCAL  = 0
    CHRISO_BIND_GLOBAL = 1
    CHRISO_BIND_UNDEF  = 2

A symbol with `UNDEF` binding represents a reference that must be resolved by the linker.

A defined non-global symbol resolves inside its own object.

A global symbol participates in cross-object resolution.

## Symbol kinds

Kinds are:

    CHRISO_KIND_NOTYPE = 0
    CHRISO_KIND_FUNC   = 1
    CHRISO_KIND_OBJECT = 2

Kinds are descriptive metadata used by the current toolchain.

They do not create separate namespaces.

Name and binding remain central to resolution.

## Symbol section and offset

For a defined symbol:

    section

identifies one of the four ChrisO sections, and:

    offset

is relative to the start of that object section.

The final linker converts this section-relative location into the final ELF virtual address after packing all objects.

For undefined symbols, current producers may use placeholder section/offset values because final resolution is name-based.

## Local assembler labels

ChrisAsm deliberately handles same-section labels beginning with `.L` internally.

They are patched before the ChrisO object is finalized and are not necessarily emitted as ChrisO symbols.

This avoids exhausting the 256-symbol object-table limit with temporary local labels.

Therefore absence of a local branch label from the symbol table is normal.

## Relocation table

Each version-2 relocation is exactly 20 bytes.

The source enforces:

    sizeof(ChrisoRel) == 20

Layout:

| Offset | Size | Field |
|---:|---:|---|
| 0 | 4 | section |
| 4 | 4 | offset |
| 8 | 4 | symbol index |
| 12 | 4 | signed addend |
| 16 | 4 | relocation type |

The addend is a signed 32-bit integer.

## Relocation-count limit

The in-memory format supports:

    CHRISO_REL_MAX = 512

The reader rejects a larger declared relocation count.

ChrisAsm also checks this bound when adding relocations.

## Supported relocation identifiers

ChrisO uses the numeric values of selected x86-64 ELF relocation types:

    R_X86_64_NONE  = 0
    R_X86_64_64    = 1
    R_X86_64_PC32  = 2
    R_X86_64_PLT32 = 4
    R_X86_64_32    = 10
    R_X86_64_32S   = 11

The final ChrisLd linker implements these selected forms.

Other relocation values are not part of the current supported contract.

## Relocation target

A relocation record identifies:

- the section containing the patch site;
- the byte offset within that section;
- the symbol-table index;
- the addend;
- the relocation calculation type.

The linker rejects a relocation whose symbol index is outside the source object's symbol table.

The current final linker supports relocation sites in text, rodata and data.

BSS has no serialized bytes to patch.

## PC-relative relocation

For PC-relative types, ChrisLd computes conceptually:

[
value = S + A - P
]

where:

- (S) is the resolved symbol address;
- (A) is the signed ChrisO addend;
- (P) is the place address.

The result must fit the signed 32-bit displacement accepted by the linker.

ChrisAsm commonly records an addend of (-4) for rel32 instruction fields because the architectural displacement is relative to the address after the four-byte field.

## Absolute relocation

For `R_X86_64_64`, ChrisLd writes a full 64-bit:

[
S + A
]

For the 32-bit relocation forms it emits a 32-bit value after the implementation's range checks.

Objects requiring relocation semantics outside these supported formulas are not currently linkable by ChrisLd.

## Version-1 compatibility

The reader accepts version 1.

Version 1 differs in two important ways.

First, BSS size is treated as zero even if header word 7 contains data.

Second, a version-1 relocation record is:

    16 bytes

instead of 20.

The v1 record therefore has no serialized relocation-type field in the current compatibility reader.

Before copying, the v2 in-memory record is zeroed, so the missing type becomes:

    R_X86_64_NONE

Version-1 compatibility is consequently limited and should not be used as the basis for new object generation.

## Version-1 symbols

Version-1 symbols are still read as 80-byte records, but the reader overrides the fields introduced for richer v2 semantics:

    binding = LOCAL
    kind = NOTYPE
    reserved = 0

This preserves old objects without pretending they carry v2 binding/kind metadata.

## Reader validation

`chriso_read` rejects:

- input shorter than 64 bytes;
- wrong magic;
- versions other than 1 or 2;
- symbol count above 256;
- relocation count above 512;
- truncated section/symbol/relocation data.

The size check computes the complete required byte count before the parser walks payload records.

## Reader ownership model

For section bytes, `chriso_read` stores pointers directly into the caller-provided input buffer.

It does not allocate copies of text/rodata/data.

Symbol and relocation records are copied into the `ChrisoImage` arrays.

Therefore:

> the source byte buffer must remain alive while the parsed section pointers are in use.

This lifetime rule is part of the practical API contract.

## Writer behavior

`chriso_write`:

1. computes required size;
2. rejects insufficient destination capacity;
3. zeroes the full output;
4. writes the eight header words;
5. copies text/rodata/data payloads;
6. copies symbols;
7. copies v2 relocation records;
8. returns the number of bytes written.

The writer always emits version 2.

## Merge helper

`chriso_merge_text` is a narrow helper, not a general object linker.

It appends only the source object's text payload to destination text.

It then copies source symbols and relocations while adjusting:

- defined text-symbol offsets;
- text relocation offsets;
- relocation symbol indices.

It rejects text growth above 64 KiB or table overflow.

Other sections are not merged by this helper.

## Multi-object final linking

The final ChrisLd path is more general than `chriso_merge_text`.

`chrisld_link_objects` accepts up to:

    32 objects

It packs each logical section from each object.

Per-object contributions are aligned to 16-byte boundaries when necessary.

Global definitions are resolved by name.

Duplicate global definitions cause failure.

Unresolved references cause failure.

## Global resolution

For a local defined symbol, resolution remains in the originating object.

For a global or undefined symbol, the linker scans objects for a matching defined global.

More than one matching global is an error.

No matching definition for an undefined reference is also an error.

This is a deliberately simple static-link model.

There are no weak symbols or dynamic-symbol scopes in ChrisO v2.

## Final ELF mapping

ChrisLd emits ELF64 x86-64 executable output.

Text and rodata are packed into an RX load segment.

When data or BSS exists, a second RW segment is emitted.

BSS expands the memory size of the RW segment but contributes no file bytes.

This preserves the same "size without payload" model used inside ChrisO.

## Entry-point selection

ChrisLd chooses entry in this order:

1. first defined symbol named `kstart`;
2. otherwise first defined symbol named `main`;
3. otherwise the provided load address.

This rule is linker behavior rather than a field stored in ChrisO.

ChrisO itself contains no dedicated entry-point header field.

## Native user linking

The in-kernel native linker uses:

    NATIVE_USER_LOAD = 0x400000

and writes final `.ELF` files through ChrisLd.

This demonstrates the intended format pipeline:

    source
      -> ChrisAsm / compiler
      -> ChrisO
      -> ChrisLd
      -> ELF64 executable

ChrisO is an intermediate object format, not the normal runtime executable container.

## Format limitations

ChrisO v2 currently has no:

- arbitrary named sections;
- section attributes;
- alignment field per section;
- COMDAT;
- weak binding;
- visibility;
- TLS model;
- DWARF/debug sections;
- relocation-section names;
- endian marker;
- architecture field;
- checksum;
- build ID;
- string table;
- dynamic linking metadata.

These omissions are deliberate simplifications but limit interoperability.

## Stability requirements

Because ChrisO files can cross independently built assembler/compiler/linker stages, incompatible changes require explicit versioning.

The following must not change silently inside version 2:

- 64-byte header;
- magic;
- section identifiers;
- symbol record size/layout;
- relocation record size/layout;
- binding numeric values;
- kind numeric values;
- supported relocation-number meanings;
- payload ordering.

A version bump is required if compatibility cannot be preserved.

## Recommended future v3 work

A future revision should consider:

1. explicit little-endian encode/decode helpers;
2. explicit architecture/ABI identifier;
3. per-section alignment and flags;
4. stronger validation of section/symbol offsets;
5. explicit undefined-section sentinel;
6. checksum or content hash;
7. source/build provenance;
8. optional debug records;
9. relocation semantics independent of host C struct layout;
10. a documented migration strategy from v2.

## Conformance summary

A conforming ChrisO v2 reader must understand:

- `CHRO` magic;
- 64-byte header;
- fixed text/rodata/data/BSS section IDs;
- no serialized BSS payload;
- 80-byte symbol records;
- 20-byte relocation records;
- 256-symbol limit;
- 512-relocation limit;
- the listed bindings, kinds and relocation types.

A conforming writer for the current toolchain emits version 2 and preserves those byte-level contracts.

## Revision note

This specification was reconciled against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

ChrisO is currently a compact, project-specific static object format. Its strongest compatibility risk is that serialization still depends partly on native little-endian C representation; that behavior is documented here rather than hidden.
