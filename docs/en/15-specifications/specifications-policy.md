---
id: specifications-policy
lang: en
type: technical-chapter
volume: 15-specifications
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/fs/cfs_format.h
  - compiler/chrisld/chriso.h
  - compiler/clvm/clvm_format.c
  - kernel/gfx/shader/sh_pub.h
symbols:
  - cfs_super_encode
  - cfs_super_decode
  - chriso_write
  - chriso_read
  - clvm_parse
  - clvm_write_image_v2
  - sh_shader_save_csi
  - sh_shader_load_csi
depends_on: []
related:
  - validation-evidence
  - bibliography
  - chrisfs-spec
  - chriso-spec
  - clvm-spec
  - shader-spec
---

# Specifications, formats and revision policy

## Purpose

A specification is a contract that is explicit enough for implementations, readers, writers and tests to agree without depending on one particular source function.

ChrisOS contains several project-owned interfaces that behave as compatibility boundaries:

- ChrisFS on-disk structures;
- ChrisO object files;
- CLVM executable images and VM-visible contracts;
- ChrisVM direct-boot behavior;
- shader/CSIR serialization;
- public syscall and resource interfaces.

This chapter defines how those contracts should be written, versioned and changed.

## Specification versus implementation

Source code answers:

> What does this revision currently do?

A specification answers:

> What behavior is part of the contract that compatible producers and consumers are expected to preserve?

The two can be identical at first, but they serve different purposes.

Implementation can contain:

- optimization details;
- private helper functions;
- temporary internal structures;
- caching policy;
- debug counters.

Those details should not automatically become compatibility requirements.

A specification should expose only behavior that another component must know to interoperate correctly.

## De facto behavior is not automatically normative

A reader may observe that one implementation happens to initialize a reserved field to zero.

That does not necessarily mean future readers must reject nonzero values.

Turning every observed implementation detail into normative behavior freezes accidental choices.

Before declaring behavior normative, ask:

1. does another independently built component depend on it?
2. is the behavior serialized, transmitted or exposed through an ABI?
3. would changing it break an existing valid artifact?
4. is a test already treating it as required?

If the answer is no, it may be an implementation detail rather than part of the contract.

## Normative language

Specifications should distinguish requirements from explanation.

Useful normative terms include:

- MUST / MUST NOT;
- SHALL / SHALL NOT;
- SHOULD / SHOULD NOT;
- MAY.

The prose should then explain why the requirement exists.

Example:

> A ChrisFS reader MUST validate the superblock checksum before trusting geometry fields.

Explanation can then describe the corruption risk.

The requirement is the compatibility rule; the explanation is rationale.

## Contract surface

A complete binary-format specification normally defines:

- magic/signature;
- version field;
- byte order;
- integer widths;
- record sizes;
- field offsets;
- alignment;
- reserved fields;
- checksums;
- validity rules;
- maximum sizes;
- error behavior;
- compatibility rules;
- upgrade/migration path.

An API/ABI specification instead emphasizes:

- symbol or syscall identity;
- argument types;
- ownership;
- lifetime;
- caller/callee responsibilities;
- failure codes;
- concurrency;
- side effects;
- compatibility across versions.

## Persisted state behaves like an ABI

Anything written to disk or exchanged between independently built components is externally observable state.

Examples include:

- filesystem sectors;
- object files;
- executable/bytecode images;
- serialized shaders;
- network or device protocol messages.

Changing a C struct in memory is easy.

Changing a byte layout already stored on disk can invalidate existing data.

Persistent formats therefore require explicit encoding and compatibility policy.

## Do not serialize native structs accidentally

A common unsafe pattern is:

    write(fd, &native_struct, sizeof native_struct)

unless the format explicitly defines that exact native representation.

Native structs can vary because of:

- padding;
- alignment;
- compiler choices;
- architecture endianness;
- field-width assumptions.

ChrisFS demonstrates the safer approach: its format helpers explicitly write 16- and 32-bit values in little-endian byte order and define exact offsets.

The on-disk representation is therefore not dependent on the in-memory layout of `CfsSuper`.

## ChrisFS example: explicit encoding

`cfs_super_encode()` constructs a 512-byte superblock explicitly.

It writes:

- magic;
- version;
- sector size;
- geometry fields;
- root inode;
- clean/generation state;
- journal geometry;
- checksum.

`cfs_super_decode()` validates magic, version, sector size, checksum and geometry constraints before accepting the record.

This is specification-friendly implementation because field positions and validation are visible independently from C struct padding.

## ChrisFS compatibility example

The current ChrisFS decoder recognizes the current version plus explicitly named legacy/compat versions.

Legacy versions are interpreted through known fixed geometry.

Current format geometry is decoded from the serialized fields and validated.

This demonstrates a useful rule:

> compatibility is implemented by an explicit reader branch, not by hoping an old layout still resembles the new struct.

When an old format is no longer supported, the specification should say so directly.

## Checksums and integrity scope

A checksum specification must define exactly what bytes participate.

ChrisFS computes a checksum over a defined prefix of serialized records and stores the result at a fixed offset.

A phrase such as "the record is checksummed" is insufficient.

A specification should state:

- algorithm;
- initial value if relevant;
- byte range;
- location of stored checksum;
- whether the checksum field itself is excluded;
- required reader behavior on mismatch.

Checksums detect accidental corruption; they should not be described as cryptographic authenticity unless the construction provides that property.

## ChrisO example: versioned object contract

ChrisO declares:

    CHRISO_MAGIC
    CHRISO_VERSION = 2
    CHRISO_VERSION_V1 = 1

and defines bounded sections, symbols and relocations.

The header also uses compile-time assertions for important record sizes:

    sizeof(ChrisoSym) == 80
    sizeof(ChrisoRel) == 20

That protects the current implementation against an accidental compiler/layout change.

The normative ChrisO specification must still state the serialized representation directly rather than requiring readers to infer it from the C compiler used to build ChrisLd.

## Version field semantics

A version number should answer more than "newer or older."

For each version, define:

- which reader accepts it;
- which writer emits it;
- whether migration occurs;
- whether conversion is lossless;
- whether a newer reader can preserve unknown fields;
- whether an older reader must reject it.

A writer normally emits one current version.

A reader may support multiple versions.

That asymmetry is normal.

## Reader compatibility matrix

A useful format document can include a matrix:

| Reader | Input v1 | Input v2 | Writes |
|---|---|---|---|
| current | supported | supported | v2 |
| legacy | supported | rejected | v1 |

The actual table must reflect implementation evidence.

The point is to make compatibility directional.

"Backward compatible" without identifying reader and writer direction is ambiguous.

## CLVM example: two image versions

The current CLVM parser explicitly recognizes v1 and v2.

The versions have different header behavior:

- v1 uses a smaller header and a 16-bit entry field;
- v2 uses the expanded header with a 32-bit entry and memory hint.

Both versions validate:

- magic;
- known flags;
- code size;
- entry range;
- bytecode checksum.

The writer functions are also explicit: one emits v1, another emits v2.

This is a clear example of contract evolution with deliberate reader behavior.

## Compatibility is not the same as permissiveness

A parser should not accept arbitrary future fields merely to appear compatible.

Unknown flags, impossible sizes and unsupported versions can change semantics.

CLVM rejects unknown flags and unsupported versions.

That fail-closed policy is preferable when the implementation cannot safely interpret the new contract.

Forward compatibility should be designed, not guessed.

## Bounds are part of the specification

Maximum sizes are observable behavior when a producer can exceed them or a reader can reject them.

Examples include:

- maximum bytecode size;
- maximum symbol count;
- maximum relocation count;
- maximum serialized source size;
- maximum resource slots.

If the bound is a stable contract, document it normatively.

If it is only a current implementation capacity expected to grow without compatibility impact, identify it as an implementation limit.

That distinction prevents temporary table sizes from becoming accidental ABI forever.

## Shader example: external language versus project subset

`sh_pub.h` explicitly says:

> ChrisOS GLSL subset. This is not a GLSL 3.30 implementation.

That sentence captures an important specification rule.

Using familiar external syntax does not automatically import the full external standard.

The ChrisOS shader specification must define:

- supported stages;
- types;
- built-ins;
- qualifiers;
- resource limits;
- linking rules;
- IR behavior;
- serialization.

A source line such as `#version 330` cannot widen the implementation beyond the documented subset.

## Internal format versus backend format

The shader system also illustrates layered contracts.

ChrisOS has its own source subset and internal IR/serialized CSIR behavior, while TGSI is used for the VirGL backend.

Those are separate compatibility surfaces.

An internal serialized shader should not be called TGSI merely because TGSI is generated later.

Specifications should name every boundary precisely so implementation layers do not collapse into one ambiguous "shader format."

## External standards

ChrisOS consumes standards it does not own, including x86-64, ELF, UEFI, ACPI, PCIe, VirtIO, NVMe, USB and network protocols.

The project should not redefine those standards.

Documentation should instead state:

1. which external specification family is authoritative;
2. which revision/profile matters when relevant;
3. which subset ChrisOS implements;
4. where ChrisOS intentionally differs or remains incomplete;
5. what tests establish interoperability.

The primary bibliography tracks those external authorities.

## External conformance versus subset support

Four claims must remain distinct:

1. format recognized;
2. subset implemented;
3. interoperability tested;
4. standards conformance established.

A loader recognizing ELF headers is not automatically a conforming implementation of every ELF feature.

A VirtIO driver working under one QEMU device model does not prove every transport/profile.

A GLSL-like parser does not imply GLSL conformance.

The specification should use the weakest accurate claim.

## ABI stability

An ABI includes more than binary layout.

It may include:

- numeric syscall IDs;
- calling convention;
- register usage;
- pointer width;
- error-code meanings;
- resource-handle ownership;
- lifetime;
- alignment;
- synchronization expectations.

Changing any of these can break independently built code even if the function name remains unchanged.

ABI changes therefore need the same discipline as disk-format changes.

## Reserved fields

Reserved fields should have explicit semantics.

Typical policies are:

- writer MUST write zero;
- reader MUST ignore;
- reader MUST reject nonzero;
- field reserved for a named future extension.

The choice determines forward compatibility.

Leaving the policy unstated makes different implementations behave differently.

## Unknown enum values

Enumerations used across persistent/ABI boundaries need an unknown-value policy.

Possible choices include:

- reject;
- ignore;
- preserve and round-trip;
- map to a generic unknown state.

The correct policy depends on whether the unknown value changes interpretation of later data.

A specification should never leave this to accidental switch-statement defaults.

## Migration

Format evolution may require explicit migration.

A migration contract should define:

- accepted source versions;
- target version;
- in-place versus copy migration;
- rollback behavior;
- crash behavior;
- data that cannot be preserved;
- how success is verified.

Migration itself becomes a compatibility surface and should have tests.

## Atomicity and crash behavior

For persistent formats, logical compatibility is not enough.

The specification may also need to define valid states during interrupted updates.

A journaled filesystem, for example, needs rules for:

- transaction boundaries;
- committed versus uncommitted state;
- recovery;
- generation numbers;
- clean/dirty state.

Crash consistency belongs in the format contract when readers can encounter partially completed updates.

## Security and malformed input

Every parser boundary is also a security boundary.

Specification validity rules should let the implementation reject:

- integer overflow;
- offset overflow;
- overlapping regions;
- impossible lengths;
- invalid ownership;
- unsupported flags;
- invalid checksums;
- version mismatches.

"Undefined behavior" should not be used as a convenient response to malformed untrusted serialized input.

## Normative test vectors

A strong specification should eventually include machine-readable test vectors.

Useful vectors include:

- smallest valid object;
- representative valid object;
- old-version object;
- each important rejection class;
- checksum mismatch;
- maximum-size boundary;
- round-trip encode/decode case.

These vectors help alternative implementations agree on semantics without copying the original source.

## Implementation binding

A project specification should identify the current readers and writers that implement it.

For example:

    specification
       |
       +-- writer implementation
       +-- reader implementation
       +-- validation tests

This makes drift visible.

If the writer changes without the specification or tests changing, review should ask whether the contract changed or only internal implementation changed.

## Revision versus protocol version

Git revision and protocol version are independent axes.

Example:

    Git revision R42
    implements CLVM format v2

A later Git revision may still implement v2 after refactoring.

Conversely, one Git revision may contain readers for v1 and v2 simultaneously.

Documentation must therefore preserve both identities.

## Specification-change classification

Changes can be classified as:

### Editorial

Clarifies wording without changing valid inputs or outputs.

### Compatible extension

Adds behavior that old valid artifacts retain, under explicit compatibility rules.

### Breaking change

Changes interpretation, layout, required fields, ABI behavior or validity such that old producer/consumer pairs can fail.

### Implementation-only

Changes internal code while preserving the specified observable contract.

This classification helps reviewers decide whether version numbers and migration are required.

## Breaking-change procedure

A breaking persistent-format or ABI change should not be merged as a casual struct edit.

A disciplined sequence is:

1. define the new contract;
2. decide version identity;
3. define reader compatibility;
4. define migration if needed;
5. update writer;
6. update reader;
7. add old/new fixtures;
8. add rejection tests;
9. update specification;
10. record compatibility limitations.

The version field should change because the contract changed, not merely because code was refactored.

## Evidence for a specification

A specification is strongest when tested from more than one direction.

Useful evidence includes:

- writer output parsed by reader;
- hand-built fixture parsed by reader;
- malformed fixture rejected;
- round-trip equality;
- old-version fixture accepted when promised;
- unknown-version fixture rejected when required;
- independent implementation interoperability.

The validation chapter defines how those evidence classes should be reported.

## Current project policy

For ChrisOS-owned externally visible formats:

- use explicit magic/version where appropriate;
- define byte order and widths;
- bound variable-size data;
- validate before trusting offsets/sizes;
- separate current writer version from accepted reader versions;
- reject unsupported semantics explicitly;
- keep current implementation and specification revision-bound;
- add migration rather than silently reinterpreting old data;
- distinguish implementation limit from normative limit.

## Review checklist

Before changing a format or ABI, ask:

1. Is the changed state persisted or consumed independently?
2. Does a reader from another revision need to understand it?
3. Is the field byte order explicit?
4. Can size/offset arithmetic overflow?
5. Is version behavior explicit?
6. Are unknown flags/values defined?
7. Does the writer still emit old or new version?
8. Is migration needed?
9. Do old fixtures exist?
10. Do tests exercise rejection and compatibility?
11. Does the specification need a revision?
12. Are roadmap ideas clearly separated from current contract?

## Revision note

This policy was reconciled against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

The current source demonstrates explicit versioned contracts in ChrisFS, ChrisO and CLVM, while the shader API explicitly constrains its external-language claim. These examples define the project direction: compatibility should be encoded and tested deliberately, never inferred from accidental C layout or familiar external terminology.
