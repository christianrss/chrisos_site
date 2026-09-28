---
id: home
lang: en
type: landing
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - README.md
  - kernel/metal/start.c
  - chrisvm/chrisvm.h
---

# ChrisOS Research Project

<div class="record">
<span>Source branch: <b>main</b></span>
<span>Documentation baseline: <code>da3df29cb397</code></span>
<span>Publication model: static / revision-bound</span>
</div>

<div class="abstract">
<b>Abstract.</b> ChrisOS is an experimental systems ecosystem containing an x86-64 kernel, ChrisC and CLVM, native compiler/assembler/linker components, ChrisFS, graphics and desktop subsystems, networking, and the ChrisVM/ChrisCPU machine-emulation stack. The documentation is organized as a dependency-ordered technical corpus from physical foundations to operating-system research.
</div>

<div class="author-signature" role="group" aria-label="Project authorship">
<span class="author-signature-kicker">A computing system by</span>
<strong>Christian Rafael de Souza Silva</strong>
<span class="author-signature-role">Creator &amp; Lead Developer of ChrisOS</span>
<span class="author-credentials">Data Science Technologist · Specialist in Electronic Engineering &amp; Robotics</span>
<span class="author-studies">Current undergraduate studies: Mathematics · Economics · Electrical Engineering · Mechanical Engineering</span>
</div>

## Canonical organization

The documentation has two independent organizational layers:

| Layer | Purpose | Authority |
|---|---|---|
| learning curriculum | establishes prerequisite order and conceptual progression | data/curriculum.yml |
| repository collections | provides stable paths and subject-oriented archival grouping | docs/en/* and docs/pt-br/* |

The learning curriculum is authoritative for reading order. Directory numbering is retained for URL stability and repository maintenance; it does not override prerequisite order.

[Learning path and current gaps](learning-path.md)

## Dependency chain

<figure class="figure">
<img src="../assets/diagrams/system-layers.svg" alt="Computing layers">
<figcaption>Each layer is defined only after the mechanisms required by the preceding layers have been established.</figcaption>
</figure>

The principal dependency chain is:

~~~text
matter and physical models
    ↓
mathematical tools required by the physical model
    ↓
electric fields, circuits and electromagnetic behavior
    ↓
semiconductor devices and CMOS
    ↓
Boolean and sequential logic
    ↓
representation, data structures and algorithms
    ↓
CPU architecture and platform interfaces
    ↓
firmware and boot
    ↓
kernel, memory, concurrency and processes
    ↓
language systems and persistent storage
    ↓
graphics, networking and desktop
    ↓
emulation, virtualization and self-hosting
    ↓
real hardware, validation and formal specifications
~~~

Missing chapters remain visible in the curriculum and are not bypassed by the canonical previous/next sequence.

## Curriculum levels

| Level | Technical scope |
|---|---|
| 01 · Matter, mathematical tools, electricity, devices and logic | matter, electrostatics, circuits, semiconductor devices, CMOS, Boolean logic, arithmetic circuits, state and memory cells |
| 02 · Representation and algorithms | discrete mathematics, binary representation, complexity, data structures and systems algorithms |
| 03 · Instruction execution and platform | datapaths, microarchitecture, ISA, x86-64, memory hierarchy, PCIe, MMIO, DMA and ACPI |
| 04 · Reset to kernel entry | processor reset, firmware, UEFI, Limine, ELF, linking and higher-half entry |
| 05 · Kernel, memory and execution contexts | trust boundaries, exceptions, PMM, paging, TLBs, concurrency, user mode and process lifecycle |
| 06 · Languages, compilers and runtimes | compiler construction, ChrisC, CLVM, JIT and the native toolchain |
| 07 · Persistent state and filesystems | block storage, ATA/AHCI/NVMe/VirtIO and ChrisFS structures/recovery |
| 08 · Bytes to desktop | framebuffer, 2D graphics, composition, input, windows and applications |
| 09 · Geometry, rasterization and GPUs | transformations, rasterization, VirtIO-GPU, VirGL and programmable shading |
| 10 · Networks and protocol state | Ethernet, IPv4, UDP, TCP, VirtIO-net and sockets |
| 11 · Emulation and virtualization | x86 emulation, ChrisVM/ChrisCPU, VMX/SVM and second-level translation |
| 12 · Bootstrap, validation and research | self-hosting, real hardware, validation, specifications, history and corpus maintenance |

## Document structure

Technical chapters separate the following evidence classes:

1. physical or mathematical theory;
2. general systems architecture;
3. current ChrisOS/ChrisCPU implementation;
4. executable validation or source-derived evidence;
5. known limitations;
6. future architecture explicitly identified as future work.

A source symbol is not sufficient evidence for feature completeness. Implementation claims are revision-bound.

## Navigation semantics

Each curriculum chapter exposes:

- curriculum level and module;
- absolute position in the canonical sequence;
- previous and next planned chapters;
- technical prerequisites declared by the chapter;
- authored chapters that depend on it;
- language pair;
- source revision and source files.

An absent previous or next chapter is rendered as an explicit curriculum gap rather than silently skipped.

## Repository collections

The stable repository collections remain available for reference navigation:

| Collection | Subject |
|---|---|
| [Foundations](01-foundations/index.md) | physical, electrical, digital, mathematical and algorithmic prerequisites |
| [Computer architecture](02-computer-architecture/index.md) | CPU, x86-64, memory hierarchy and platform |
| [Boot](03-boot/index.md) | firmware, executable layout and kernel entry |
| [Kernel](04-kernel/index.md) | privileged execution, interrupts, processes and kernel model |
| [Memory](05-memory/index.md) | physical/virtual memory, TLBs, allocation and lifetime |
| [Storage](06-storage/index.md) | block devices and filesystems |
| [Language systems](07-language-systems/index.md) | compilers, runtimes and native toolchain |
| [Graphics](08-graphics/index.md) | framebuffer, 2D/3D graphics and GPU interfaces |
| [Emulation](09-emulation/index.md) | ChrisVM, ChrisCPU and virtualization |
| [Networking](10-networking/index.md) | network protocols and devices |
| [Desktop](11-desktop/index.md) | windows, input and applications |
| [Self-hosting](12-self-hosting/index.md) | bootstrap and internal rebuild |
| [Real hardware](13-real-hardware/index.md) | installation, bring-up and compatibility |
| [Validation](14-validation/index.md) | tests, gates, faults and measurements |
| [Specifications](15-specifications/index.md) | project formats, ABIs and protocol contracts |
| [Architecture history](16-history/index.md) | revision-bound architectural history |

## Evidence policy

1. Current source on main.
2. Reproducible checks and gates against the same revision.
3. Current in-repository specifications.
4. Historical material explicitly bound to its source revision.
5. Future work explicitly separated from implemented behavior.
