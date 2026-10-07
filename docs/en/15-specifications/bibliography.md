---
id: bibliography
lang: en
type: reference-chapter
volume: 15-specifications
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources: []
symbols: []
depends_on:
  - specifications-policy
related:
  - source-policy
  - validation-evidence
---

# Primary bibliography and standards map

## Purpose

This chapter defines the primary external references used to interpret ChrisOS architecture, interfaces, protocols and implementation claims.

It is not a generic reading list. Its purpose is to answer three engineering questions:

1. which authority defines a behavior that ChrisOS does not own;
2. which document should be consulted before changing an externally visible contract;
3. how external specifications, ChrisOS source and validation evidence are reconciled when they appear to disagree.

The canonical machine-readable catalogue is maintained in `data/bibliography.yml`. This chapter explains how that catalogue is used and how each reference family maps to the operating system.

## Authority model

ChrisOS documentation separates four kinds of authority.

| Authority | Role |
|---|---|
| ChrisOS `main` source | defines current ChrisOS implementation behavior |
| ChrisOS persisted/internal specification | defines project-owned formats and compatibility contracts |
| External primary specification | defines standards ChrisOS consumes but does not own |
| Test or hardware evidence | demonstrates that one implementation path behaves as claimed |

These authorities answer different questions.

For example, the VirtIO specification defines the device protocol. ChrisOS source defines which portion of VirtIO is implemented. QEMU or physical-device evidence shows whether the implemented subset actually interoperates in a tested environment.

None of those three can replace the other two.


## Source-scope boundary for this bibliography

This chapter intentionally declares `sources: []` because its subject is the external-reference catalogue and the rules for using it, not the implementation state of a ChrisOS subsystem.

That boundary has a concrete consequence: this page must not freeze revision-specific statements such as "ChrisOS currently uses feature X" or "the current driver supports Y" unless the page also declares and maintains the relevant source dependencies. Implementation state belongs in the subsystem chapter, specification, generated source map or validation record that is revision-bound to the corresponding code.

The bibliography may still explain how an external standard relates to ChrisOS. Such wording must remain conditional or methodological: it can state which authority should be consulted, what evidence an implementation chapter must provide, and how subset compliance should be described. The existence of a standard in this catalogue is never evidence that ChrisOS implements that standard or any particular feature within it.

## Primary-source rule

When an external technology has a normative specification, the primary bibliography must prefer that specification over:

- tutorials;
- blog posts;
- forum answers;
- vendor summaries;
- generated AI explanations;
- secondary textbooks;
- source code from unrelated operating systems.

Secondary sources can be useful for explanation, but they are not the final authority for bit layouts, reserved values, state transitions, timing requirements or ABI rules.

## Revision pinning

External standards evolve independently of the ChrisOS Git history.

A rigorous engineering note should therefore carry two identities where relevant:

    ChrisOS source revision
    external specification revision

A statement such as "the driver follows VirtIO" is incomplete if protocol behavior differs across revisions.

When a standards revision matters, the documentation or test record should name it explicitly.

The bibliography catalogue intentionally uses family-level titles for standards that continue to evolve. Individual implementation chapters should pin the exact edition used when the edition materially affects behavior.

## x86 architecture references

### Intel Software Developer's Manual

**Intel 64 and IA-32 Architectures Software Developer's Manual**

Organization: Intel.

Use this family as a primary reference for Intel-defined x86 behavior including:

- instruction semantics;
- control registers;
- segmentation;
- paging;
- exceptions and interrupts;
- APIC behavior;
- memory ordering;
- cache-control mechanisms;
- system instructions;
- VMX when relevant.

ChrisOS chapters about long mode, page tables, exceptions, interrupt control, SMP and CPU feature detection should distinguish architectural guarantees from implementation choices made by the kernel.

### AMD64 Architecture Programmer's Manual

**AMD64 Architecture Programmer's Manual**

Organization: AMD.

This is the corresponding primary architecture family for AMD64-specific behavior.

It is particularly relevant when documentation discusses:

- long-mode architectural state;
- page translation;
- SYSCALL/SYSRET behavior;
- model-specific registers;
- exception semantics;
- AMD-specific feature bits;
- SVM-related behavior.

When Intel and AMD manuals describe common x86-64 behavior differently in presentation, ChrisOS documentation should avoid assuming that wording from one vendor automatically defines the other vendor's implementation detail.

## RISC-V architecture references

### RISC-V unprivileged architecture

**The RISC-V Instruction Set Manual, Volume I — Unprivileged Architecture**

Organization: RISC-V International.

Use it for:

- base instruction semantics;
- integer register model;
- memory operations;
- control-flow instructions;
- ISA extension behavior.

### RISC-V privileged architecture

**The RISC-V Instruction Set Manual, Volume II — Privileged Architecture**

Organization: RISC-V International.

Use it for:

- privilege modes;
- CSRs;
- traps;
- interrupt delegation;
- address translation;
- `satp`;
- Sv39 and related virtual-memory rules.

When ChrisOS documents RISC-V bring-up, these manuals define the architectural contract. The corresponding implementation chapter must state the execution surface actually implemented and the evidence for it; a standard-defined RISC-V feature is not evidence that ChrisOS implements that feature.

## Firmware and boot references

### UEFI

**Unified Extensible Firmware Interface Specification**

Organization: UEFI Forum.

Use UEFI as the primary reference for firmware services, boot services, runtime services, system tables, memory maps and executable loading conventions defined by the firmware interface.

UEFI is not the same thing as the ChrisOS boot protocol.

The firmware may load a bootloader, while the bootloader then hands control to ChrisOS using another contract.

### ACPI

**Advanced Configuration and Power Interface Specification**

Organization: UEFI Forum.

Use ACPI for the structures and semantics of:

- RSDP;
- RSDT/XSDT;
- MADT/APIC topology;
- FADT/FACP;
- MCFG;
- AML-described platform configuration where implemented.

A ChrisOS ACPI probe that discovers a table is not equivalent to implementing all ACPI semantics.

Documentation should state exactly which tables or fields the current kernel consumes.

### Limine boot protocol

**Limine Boot Protocol**

Organization: Limine project.

The ChrisOS boot chapters use the Limine specification to distinguish bootloader-defined responses from kernel-owned handling. The implementation chapter, rather than this bibliography, is responsible for stating which Limine requests and responses are used at a particular source revision.

Use the Limine protocol reference for the contract around requests and responses such as:

- framebuffer;
- memory map;
- higher-half direct map;
- multiprocessor information;
- kernel command line.

The ChrisOS boot code remains the authority for which Limine features are actually requested and how missing responses are handled.

## Executable, ABI and debug references

### ELF

**System V Application Binary Interface — Executable and Linking Format**

Use ELF as the primary format reference for:

- ELF headers;
- program headers;
- section headers where relevant;
- symbol tables;
- relocation records;
- executable and object-file structure.

ChrisOS-specific loaders may implement only a subset.

A valid ELF feature in the standard is not automatically a supported ChrisOS loader feature.

### AMD64 System V ABI

**System V Application Binary Interface — AMD64 Architecture Processor Supplement**

Use it for the conventional x86-64 ABI surrounding:

- register argument passing;
- return values;
- stack alignment;
- caller/callee-saved registers;
- data layout;
- relocation and linking conventions.

ChrisOS internal kernel conventions may intentionally differ from user-space System V ABI conventions. Those differences must be documented as ChrisOS choices.

### DWARF

**DWARF Debugging Information Format**

Organization: DWARF Standards Committee.

Use DWARF for debug-information encodings when compiler/debugger tooling emits or consumes them.

A source-level debugger can support only a subset of DWARF while remaining useful; the implemented subset should be stated explicitly.

### ISO C

**ISO/IEC 9899 — Programming Languages — C**

Organization: ISO/IEC JTC 1/SC 22/WG 14.

Use the C language standard for language-level semantics.

This matters in kernel and compiler work because hardware-facing C frequently approaches boundaries involving:

- integer conversion;
- signed overflow;
- aliasing;
- volatile access;
- object lifetime;
- alignment;
- implementation-defined behavior.

A hardware manual does not override the C abstract machine, and the C standard does not define device-register side effects. Correct low-level code must satisfy both layers.

## PCI and device-interface references

### PCI Express

**PCI Express Base Specification**

Organization: PCI-SIG.

Use it for PCIe configuration-space semantics, capability structures, BARs, bus/device/function addressing, transaction-level requirements and MSI/MSI-X-related concepts.

A ChrisOS PCI implementation may be narrower than the complete PCIe model. A bus-0-only helper, for example, would be an implementation limitation rather than a property of PCIe.

### VirtIO

**Virtual I/O Device (VIRTIO) Specification**

Organization: OASIS.

VirtIO is central to multiple virtual-device paths.

Use the specification for:

- feature negotiation;
- device status;
- virtqueue layout;
- descriptors;
- avail/used rings;
- MMIO or PCI transport behavior;
- device-specific configuration.

For any ChrisOS VirtIO driver, the implementation chapter must identify its transport and negotiated feature subset. The presence of VirtIO in this bibliography does not establish that a particular device path exists in the current source.

## Storage references

### NVMe

**NVM Express Base Specification**

Organization: NVM Express.

Use it for:

- controller registers;
- submission/completion queues;
- command formats;
- namespaces;
- doorbells;
- status codes;
- queue lifecycle.

A QEMU NVMe success marker establishes interoperability with a tested virtual controller, not universal NVMe hardware compatibility.

### AHCI

**Serial ATA Advanced Host Controller Interface**

Organization: Intel.

Use AHCI for:

- host bus adapter registers;
- ports;
- command list structures;
- command tables;
- FIS receive areas;
- port state.

AHCI defines the host-controller interface. ATA commands carried through it are governed by ATA command-set specifications.

### ATA/ATAPI

**ATA/ATAPI Command Set**

Organization: INCITS Technical Committee T13.

Use the ATA command set for command semantics such as IDENTIFY and sector I/O.

PIO register programming and AHCI transport differ operationally even when they eventually issue related ATA commands.

Documentation should not collapse transport and command-set semantics into one layer.

## USB references

### USB specification

**Universal Serial Bus Specification**

Organization: USB Implementers Forum.

Use it for device concepts such as:

- descriptors;
- endpoints;
- transfer types;
- device configuration;
- class-independent enumeration behavior.

Class specifications may define additional behavior beyond the base USB specification.

### xHCI

**eXtensible Host Controller Interface for Universal Serial Bus**

Organization: Intel.

Use xHCI for host-controller behavior including:

- capability and operational registers;
- device contexts;
- transfer rings;
- event rings;
- command rings;
- TRBs;
- doorbells.

USB device protocol and xHCI host-controller mechanics are distinct standards layers.

## Internet protocol references

The RFC Editor publications in the catalogue are primary protocol references for the network stack.

### ARP — RFC 826

Use for IPv4-to-link-layer address resolution on Ethernet-like networks.

### UDP — RFC 768

Use for UDP header layout and core datagram semantics.

### IPv4 — RFC 791

Use as the historic base IPv4 protocol reference.

Later RFCs update and refine parts of IPv4 behavior; implementation chapters should identify any later document that materially changes the rule being discussed.

### IPv6 — RFC 8200

Use as the primary IPv6 base specification.

### TCP — RFC 9293

Use RFC 9293 as the current consolidated TCP specification rather than relying only on the original RFC 793 text.

### DNS — RFC 1035

Use for DNS message formats, labels and resolver/server protocol foundations.

### DHCP — RFC 2131

Use for DHCP state and message exchange.

## Network-standard interpretation

An RFC can be:

- original protocol definition;
- standards-track update;
- clarification;
- extension;
- deprecation.

Therefore citing an RFC number is not enough when later RFCs update the exact behavior.

For protocol implementation work, the engineer should check the "Updates" and "Obsoletes" relationships of the relevant RFC family before treating an old document as complete.

## Graphics references

### OpenGL

**OpenGL Specification**

Organization: Khronos Group.

Use OpenGL specifications for concepts that ChrisOS intentionally models after OpenGL-style graphics pipelines.

The ChrisOS graphics stack is not itself an OpenGL implementation unless a specific compatibility layer states that it is.

### GLSL

**The OpenGL Shading Language Specification**

Organization: Khronos Group.

Use GLSL as the external language reference when comparing syntax or semantics with the ChrisOS shader frontend.

When a ChrisOS shader frontend accepts GLSL-like syntax, the shader specification and revision-bound implementation chapter must define the supported subset.

A source beginning with `#version 330` does not make ChrisOS a conforming GLSL 3.30 implementation.

The `shader-spec` chapter defines the actual ChrisOS contract.

### TGSI

**TGSI — Tungsten Graphics Shader Infrastructure**

Organization: Mesa.

Use TGSI documentation for the intermediate representation expected by any Mesa/VirGL path in which a ChrisOS implementation emits TGSI text.

TGSI is an external graphics IR, not the same representation as ChrisOS CSIR.

### virglrenderer

**virglrenderer protocol and command definitions**

Organization: Mesa / virglrenderer project.

Use the virglrenderer source/protocol definitions to interpret the host-facing virtual 3D command path.

VirtIO-GPU transport, VirGL commands, TGSI and ChrisOS's own graphics API are separate layers and should remain separate in documentation.

## University reference material

The primary bibliography also contains two MIT OpenCourseWare collections.

These are deliberately classified as **university lecture notes**, not normative specifications.

### MIT 6.012 — Microelectronic Devices and Circuits

Use this material for foundational explanations of semiconductor and transistor behavior.

It is useful in chapters that connect:

- MOS electrostatics;
- transistor switching;
- capacitance;
- delay;
- power;
- physical implementation

to digital systems.

### MIT 6.004 — Computation Structures

Use this material for foundational explanations of:

- combinational logic;
- sequential logic;
- finite-state machines;
- processors;
- pipelining;
- memory hierarchy;
- computer organization.

These notes are explanatory references. They do not define x86, RISC-V or ChrisOS behavior.

## Reference class taxonomy

The catalogue currently uses classes such as:

- `architecture-manual`;
- `architecture-specification`;
- `firmware-specification`;
- `boot-protocol-specification`;
- `abi-specification`;
- `debug-format-specification`;
- `language-standard`;
- `bus-specification`;
- `device-specification`;
- `storage-specification`;
- `internet-standard`;
- `graphics-api-specification`;
- `graphics-language-specification`;
- `graphics-protocol-reference`;
- `graphics-ir-reference`;
- `university-lecture-notes`.

The class communicates the kind of authority a source has.

A university note should not be cited as if it were a hardware standard.

A vendor architecture manual should not be cited as if it defined ChrisOS-specific policy.

## Mapping standards to ChrisOS evidence

A useful implementation claim can be represented as:

[
C = (S_e,; R_e,; S_c,; T)
]

where:

- (S_e) is the external specification family;
- (R_e) is the external revision when material;
- (S_c) is the ChrisOS source revision;
- (T) is validation evidence.

For example:

    VirtIO specification
      + selected protocol revision
      + ChrisOS driver commit
      + QEMU/device test evidence

is a much stronger compatibility statement than "VirtIO supported".

## Standards compliance versus subset implementation

ChrisOS implementation chapters may deliberately define small subsets of larger external standards.

Documentation must distinguish at least four statements:

1. **format recognized** — a parser identifies the structure;
2. **subset implemented** — selected required operations work;
3. **tested interoperability** — a specific peer/device configuration passed;
4. **standards conformance** — all requirements for a claimed profile are satisfied.

The first three do not automatically establish the fourth.

This distinction is particularly important for ELF, ACPI, USB, VirtIO, GLSL and network protocols.

## Conflict resolution

When sources appear to conflict, use the following decision sequence.

### External behavior

If the question is "what does PCIe/UEFI/TCP require?", the external normative source wins.

ChrisOS source may then be identified as conforming, incomplete or incorrect.

### ChrisOS behavior

If the question is "what does this ChrisOS revision actually do?", current ChrisOS source wins.

A documentation page that describes intended standard behavior but contradicts the code must be corrected or clearly marked as roadmap.

### Persisted ChrisOS formats

For project-owned serialized formats such as ChrisFS, ChrisO, CLVM and CSIR, the project specification and current readers/writers must be reconciled.

If implementation and specification disagree, that is a compatibility defect, not an invitation to silently choose one.

## Paywalled or access-controlled standards

Some primary specifications are distributed under access or licensing conditions.

The bibliography may therefore contain a title and issuing organization without mirroring the document or embedding a direct downloadable copy.

Do not copy large sections of proprietary standards into the documentation corpus.

Instead:

- cite the standard;
- explain the subset ChrisOS uses;
- record field names and behavior necessary to understand the implementation;
- link to public issuing-organization material when permitted.

## Stable links versus titles

URLs change more frequently than standard names.

For that reason, the catalogue treats the title, organization and class as the stable identity.

A URL is helpful metadata when an authoritative public landing page is known, but the absence of a URL does not reduce the authority of the identified standard.

Broken URLs should be repaired without renaming the reference key unless the underlying source identity changed.

## Bibliography keys

Reference keys such as:

    intel-sdm
    amd-apm
    virtio
    rfc-9293
    glsl

are stable project identifiers.

They should remain short, lowercase and semantically durable.

A key should not embed a standards revision unless two revisions must coexist in the corpus simultaneously.

## Adding a reference

A new bibliography entry should be added when at least one substantive chapter depends on an external authority not already represented.

Before adding it:

1. identify the original standards body, vendor or project;
2. prefer the normative document over a secondary explanation;
3. choose a stable key;
4. record title and organization;
5. assign an authority class;
6. add an official landing URL when confidently known and useful;
7. cite the exact revision inside implementation chapters when revision-dependent.

Do not create duplicate entries for mirrors of the same source.

## Removing a reference

A reference should not be removed merely because the current code no longer touches it.

Historical chapters may still rely on it.

Removal is appropriate when:

- the entry was incorrect;
- it duplicates another key;
- the underlying source was misidentified;
- no authored or historical chapter uses the source and no compatibility record depends on it.

## Validation and bibliography

Documentation build success verifies catalogue syntax and site integration; it does not validate the external standard itself.

Protocol or hardware claims need separate evidence.

Examples include:

- host tests for parser behavior;
- QEMU gates for virtual devices;
- physical hardware records;
- differential execution tests;
- packet traces;
- filesystem image checks.

The bibliography tells the project what behavior to compare against. Tests determine whether the implementation matches the selected contract.

## Current catalogue coverage

At this revision the bibliography catalogue covers the principal external authorities needed by the existing ChrisOS corpus:

- x86 and RISC-V ISA architecture;
- UEFI, ACPI and Limine boot handoff;
- ELF, AMD64 ABI, DWARF and C;
- PCIe and VirtIO;
- NVMe, AHCI and ATA;
- USB and xHCI;
- core IPv4/IPv6, ARP, UDP, TCP, DNS and DHCP references;
- OpenGL, GLSL, TGSI and VirGL;
- university material for device physics and computation structures.

This is intentionally not an exhaustive bibliography of computer science.

The catalogue grows when the source tree or curriculum introduces a concrete dependency.

## Revision note

This chapter was reconciled against the ChrisOS source baseline `e05a17fd76333114a3fb5c2452f38ca747d4ac56` and the bibliography catalogue maintained in the documentation repository.

External standards remain independently versioned. Future chapter revisions should pin exact external editions where interoperability or binary compatibility depends on them.
