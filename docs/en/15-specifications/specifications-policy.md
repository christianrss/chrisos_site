---
id: specifications-policy
lang: en
type: technical-chapter
volume: 15-specifications
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/fs/cfs_format.h
symbols: []
depends_on: []
related:
  - validation-evidence
---

# Specifications, formats and revision policy

## Specification versus implementation

A specification describes a contract independently enough that an implementation can be tested against it. Source code alone can define behavior de facto, but extracting an explicit specification makes compatibility and alternative implementations possible.

ChrisOS has several specification-like surfaces:

- ChrisVM machine/boot contracts;
- ChrisO object format;
- ChrisFS on-disk encoding;
- CLVM image/syscall contracts;
- shader language subset and CSIR/TGSI interface;
- executable/kernel boot layout.

## Stable external state

Anything persisted or consumed across independently built components behaves like an ABI:

- disk structures;
- bytecode images;
- executable files;
- syscall numbers;
- device protocols;
- serialized shader blobs.

Changing a C struct without versioning such data can silently break existing artifacts.

## Versioning

A format version should answer:

1. how a reader identifies the version;
2. which fields exist and their byte order/width;
3. whether older versions remain readable;
4. whether migration is required;
5. which writer emits the new version.

Compatibility must be deliberate rather than accidental.

## Normative and explanatory text

A specification benefits from distinguishing requirements from explanation.

Normative: "The loader MUST reject an ELF segment overlapping reserved page-table memory."

Explanatory: why the overlap would corrupt the machine state.

The documentation corpus may teach both, but machine contracts should make mandatory behavior unambiguous.

## External standards

ChrisOS depends on specifications it does not own: x86-64, UEFI, ELF, PCI, VirtIO and network protocols.

The project documentation should explain the subset it uses and link to the primary specification rather than copying large standard texts or implying custom behavior is standard.

## Revision binding

Implementation commentary is tied to a ChrisOS commit. Protocol specifications may have their own version independent of Git.

Both identities are useful:

```text
document revision → which source was inspected
protocol version  → which external/persistent contract is described
```
