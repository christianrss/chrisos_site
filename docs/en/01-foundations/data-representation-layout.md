---
id: data-representation-layout
lang: en
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
- chrisvm/chris_arch.h
- compiler/chrisld/chriso.h
- kernel/fs/cfs_format.h
- kernel/gfx/virtq.c
- kernel/gfx/virtq.h
symbols:
- ChrisArchitectureState
- ChrisoImage
- virtq_set
- virtq_bytes
- virtq_publish
- cfs_get16
- cfs_get32
- cfs_put16
- cfs_put32
depends_on:
- clock-timing
related:
- data-structures
- cpu-datapath-isa
---

# Data representation, memory layout and pointers

<div class="abstract">
Software never manipulates abstract “data” directly. It manipulates bit patterns placed at addresses according to representation rules. Integer width, signedness, endianness, alignment, structure layout, pointer interpretation and serialization determine how the same bits acquire meaning. This chapter establishes those rules before data structures and algorithms are introduced, because an algorithm over an array, tree, page table or file format is only correct if the underlying representation is well defined.
</div>

## Bits acquire meaning through a contract

A sequence such as <code>11111111</code> has no intrinsic software meaning. Under one contract it is the unsigned integer 255; under another it is the signed two's-complement integer -1; under another it is a byte of an instruction, a color component, a bit mask or part of an encoded structure.

Representation therefore has two layers:

1. the physical or architectural bit pattern;
2. the interpretation imposed by a type, protocol or format.

Operating systems constantly cross representation boundaries. A physical address is stored in an integer field, a page-table entry combines an address with flags, an ELF header interprets consecutive bytes as typed fields, a network packet places multi-byte values in a specified byte order, and an emulator reconstructs machine operands from instruction bytes.

Correct systems code makes these contracts explicit.

## Width

An n-bit unsigned integer has 2^n possible patterns and represents values from 0 through 2^n-1. An n-bit two's-complement signed integer uses the same patterns but maps them to -2^(n-1) through 2^(n-1)-1.

Width affects:

- overflow and wraparound;
- shifts;
- masks;
- pointer truncation;
- ABI layout;
- on-disk compatibility;
- instruction encoding;
- atomic access guarantees.

A conversion from 64 bits to 32 bits is not a cosmetic type change. It discards information unless the value is already known to fit. Kernel and compiler bugs often originate when an address-sized value is narrowed accidentally.

## Bit fields and masks

Systems software frequently packs several logical fields into one machine word.

If bits 0-11 are flags and bits 12-51 contain a page-frame address, the representation can be conceptualized as:

    63                              12 11             0
    +--------------------------------+----------------+
    | address / implementation bits  |     flags      |
    +--------------------------------+----------------+

Extraction uses masks and shifts:

    flags   = entry & FLAG_MASK
    address = entry & ADDRESS_MASK

Modification must preserve unrelated bits:

    entry = (entry & ~TARGET_MASK) | new_bits

The central invariant is not merely the C expression. It is the declaration of which bit positions belong to which semantic field.

## Endianness

Endianness defines byte order for multi-byte values.

For the 32-bit value 0x12345678 stored at increasing addresses:

| Address offset | Little-endian byte | Big-endian byte |
|---:|---:|---:|
| +0 | 0x78 | 0x12 |
| +1 | 0x56 | 0x34 |
| +2 | 0x34 | 0x56 |
| +3 | 0x12 | 0x78 |

x86-64 is little-endian for ordinary integer memory representation. A software format can nevertheless define a different byte order. Network protocols traditionally use big-endian network byte order, while many executable and filesystem formats explicitly state their encoding.

Endianness becomes observable whenever raw bytes cross an abstraction boundary.

## Alignment

An object is aligned when its address satisfies a divisibility requirement. A 16-byte-aligned object begins at an address divisible by 16.

Alignment can exist for several reasons:

- the ISA may require it for particular instructions;
- aligned access may be faster;
- atomicity may depend on natural alignment;
- DMA hardware may impose boundaries;
- page tables require page alignment;
- vector operations may prefer wider alignment;
- object formats and ABIs impose layout rules.

Alignment creates padding. A structure containing a byte followed by a 64-bit integer may occupy more than nine bytes because the larger field is placed at a suitably aligned offset.

## Structure layout

A source-language structure is an ordered set of fields plus layout rules.

A compiler decides field offsets according to ABI and alignment unless the program or format explicitly requests packed representation. Therefore an in-memory C structure should not automatically be treated as an on-disk or wire-format structure.

Stable formats should define:

- exact field widths;
- exact offsets;
- byte order;
- version;
- alignment or packing;
- reserved fields;
- checksum coverage;
- bounds and maximum counts.

ChrisO, ChrisFS and executable formats are examples where representation must remain stable across producer and consumer code.

## Padding

Padding bytes are not semantically owned by ordinary source fields. Copying a structure as opaque bytes can therefore expose uninitialized padding or produce incompatible persistent data if compiler layout changes.

For persistent and external formats, explicit encode/decode functions are often safer than direct structure dumps.

The distinction is:

    logical structure
        ↓
    language layout
        ↓
    encoded external representation

Those three may intentionally differ.

## Pointers

A pointer is a value interpreted as locating an object in an address space. It is not merely “an integer containing an address,” although machine implementations often encode pointers numerically.

Pointer validity depends on context:

- which address space;
- required access permissions;
- alignment;
- object lifetime;
- provenance rules of the language;
- current page-table mapping;
- privilege level.

The same numeric value may refer to valid memory in one process and be unmapped in another.

## Physical and virtual addresses

A physical address identifies a location in the machine's physical address space. A virtual address is interpreted through translation structures associated with an address space.

The relationship is not generally one-to-one:

    virtual address
        ↓
    page-table walk
        ↓
    physical frame + page offset

Different virtual addresses can map the same physical frame. The same virtual number in two processes can map different frames. Some virtual ranges may be unmapped entirely.

Algorithms that manipulate addresses must state which representation they receive.

## Offset versus pointer

Persistent formats usually store offsets or identifiers rather than raw host pointers. A pointer is meaningful only while a particular address space and allocation remain valid. An offset can be reconstructed relative to a known base.

This distinction is essential for filesystems, object files and shared-memory protocols.

A relocation entry is effectively a rule for transforming symbolic or relative representation into a final address representation.

## Arrays

An array stores equal-sized elements contiguously.

If base is the first element address and each element occupies S bytes:

address(i) = base + i × S

This formula provides constant-time indexed access because no preceding element must be traversed.

Contiguity also provides spatial locality. Hardware cache lines fetch neighboring bytes, so sequential array traversal often uses memory bandwidth efficiently.

The trade-off is resizing and insertion. If an array is tightly packed, inserting in the middle may require moving many following elements.

## Strings

A string is not one universal representation.

Common models include:

- zero-terminated byte strings;
- explicit length plus bytes;
- fixed-capacity buffers;
- length-prefixed encoded strings;
- Unicode code-unit sequences.

A zero-terminated string makes length discovery O(n) unless cached. A length-prefixed string makes length retrieval O(1) but still needs capacity and encoding rules.

Kernel code must also treat untrusted strings as bounded data. Searching indefinitely for a terminator across invalid memory is not acceptable at a privilege boundary.

## Tagged and untagged unions

Sometimes one storage location can contain values of several kinds. A tagged representation stores an explicit discriminator:

    kind = INTEGER
    payload = 42

Without a tag, interpretation must come from an external invariant.

Tagged representations cost space but make illegal interpretations easier to detect. Untagged representations can be compact and fast when the controlling invariant is strong.

Instruction decoders, AST nodes, device messages and variant records often use one of these patterns.

## Handles and indices

A kernel can expose an integer handle instead of a direct pointer. The handle indexes a protected table that contains the actual object reference and metadata.

Advantages include:

- preventing direct mutation of kernel pointers;
- validating ownership;
- allowing revocation;
- decoupling external ABI from internal addresses;
- making object lifetime explicit.

The cost is a lookup and the need to manage handle reuse safely.

## Serialization

Serialization converts an in-memory model into a byte sequence with explicit rules. Deserialization performs the inverse operation while validating input.

A safe decoder treats every length, offset and count as untrusted until bounds are proven.

For a region starting at offset O with length L inside an N-byte buffer, the robust question is not merely whether O + L <= N, because O + L can overflow. A safer form checks:

    O <= N
    L <= N - O

This pattern appears repeatedly in executable loaders and filesystem parsers.

## Integer overflow as representation failure

When a calculation determines an allocation size, file span or address range, overflow can transform a large invalid value into a small apparently valid one.

For count elements of size S:

    bytes = count × S

must be checked before multiplication or with a checked-arithmetic primitive. Bounds validation is an algorithm over finite-width integers, not over mathematical integers.

This is one reason representation theory belongs before algorithms.

## Ownership metadata

A pointer or index alone says where an object is; it does not say who is responsible for releasing it.

Systems code therefore often associates data with ownership state:

- static lifetime;
- stack lifetime;
- process-owned allocation;
- kernel-global allocation;
- device-owned DMA buffer;
- reference counted object;
- borrowed pointer;
- transferred ownership.

The representation of ownership may be explicit in a field or implicit in API contracts. Documentation must make it explicit even when the code does not encode it in the type system.

## Layout and cache locality

Two logically equivalent representations can have very different performance.

An array of structures stores complete records together:

    [A0 B0 C0][A1 B1 C1][A2 B2 C2]

A structure of arrays stores each field separately:

    [A0 A1 A2] [B0 B1 B2] [C0 C1 C2]

If an algorithm scans only field A, the second layout may use cache lines more efficiently. If it consumes complete records, the first can be better.

Data structure selection is therefore also data-layout selection.

## ChrisOS examples

The current ChrisOS tree demonstrates several representation classes:

| Source | Representation role |
|---|---|
| <code>chrisvm/chris_arch.h</code> | architectural CPU state represented as explicit fixed-width fields |
| <code>compiler/chrisld/chriso.h</code> | object sections, symbols and relocations with bounded arrays and fixed field widths |
| <code>kernel/fs/cfs_format.h</code> | filesystem format contracts |
| page-table code | addresses combined with permission/status bits |
| VirtIO drivers | descriptor structures shared with a device |
| graphics | pixel, vertex, matrix and command-buffer representations |

The representation is part of the algorithm. A page allocator using one bit per frame behaves differently from an allocator storing full objects per frame; a ring buffer depends on modular indices; a parser depends on token representation.

The next chapters therefore move from representation to cost models and then to structured organizations of data.

## A descriptor reconstructed byte by byte

`virtq_set` supplies a concrete serialization example. Each descriptor occupies sixteen bytes in a shared buffer. The function computes its start as descriptor-base offset plus sixteen times the index. It then writes the address, length, flags and next index using explicit little-endian helpers. This layout is independent of whether a host C compiler would insert padding into an equivalent structure.

| Byte offsets within descriptor | Width | Meaning | Example bytes, lowest address first |
|---|---|---|---|
| 0–7 | 64 bits | Device-visible buffer address | `88 77 66 55 44 33 22 11` |
| 8–11 | 32 bits | Length, here 4096 | `00 10 00 00` |
| 12–13 | 16 bits | Flags, here NEXT | `01 00` |
| 14–15 | 16 bits | Next descriptor, here 7 | `07 00` |

The address example encodes `0x1122334455667788`. This is an illustrative address value, not a valid allocation or DMA mapping supplied by the project. Byte order says how a number is represented; it says nothing about whether the device is permitted to access that address. Address translation, lifetime and ownership require additional contracts.

For an eight-entry queue, descriptor storage is 8 × 16 = 128 bytes. The available area consumes 4 + 2 × 8 + 2 = 22 bytes. The implementation aligns the following used area to four bytes, so it begins at offset 152 rather than 150. That area occupies 4 + 8 × 8 + 2 = 70 bytes, giving a total of 222. The two padding bytes are a layout consequence, not additional entries. These calculations follow `virtq_bytes`; choosing an arbitrary packed structure would not explain them.

## An in-memory object is not its serialized image

`ChrisoImage` holds section pointers, section sizes and bounded arrays of symbols and relocations. A section pointer belongs to the host process's address space. Writing the structure's raw bytes to a file would preserve meaningless addresses for a later process. In contrast, `ChrisoSym` and `ChrisoRel` have explicit size assertions of 80 and 20 bytes in the inspected header. Those assertions constrain size, but do not by themselves prove byte order, valid indices or the complete file grammar.

The distinction also appears in CFS. `CfsSuper` and `CfsInode` are useful in-memory representations, while `cfs_get16`, `cfs_get32`, `cfs_put16` and `cfs_put32` explicitly assemble or scatter bytes. A cast from an arbitrary byte pointer to a multi-byte integer pointer can add alignment and aliasing assumptions. Explicit byte operations make the represented order visible and avoid assuming that every external buffer is aligned as a native object.

## Bounds, lifetime and publication are separate proofs

Before accessing a field of length L at offset O in a buffer of size N, first prove O ≤ N and then L ≤ N − O. The subtraction form avoids overflow in O + L. For arrays, prove the index bound and that stride multiplication is representable before forming the address. After those arithmetic checks, the backing allocation must still be alive and owned by a party permitted to access it.

Finally, shared-memory publication needs ordering: a consumer must not observe a new index before the corresponding bytes are ready. `virtq_publish` places barriers around index publication, but the descriptor serializer itself does not lock the queue or validate a device mapping. Correct bytes, valid bounds, stable lifetime and correct synchronization are four distinct obligations. Passing a serialization example proves only the first unless the others are tested explicitly.
