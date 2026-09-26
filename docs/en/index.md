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
<b>Abstract.</b> ChrisOS is an experimental operating-system ecosystem combining an x86-64 higher-half kernel, ChrisC and CLVM, a native compiler/assembler/linker path, ChrisFS, a graphical desktop, software and paravirtual graphics, and the ChrisVM/ChrisCPU emulator. This documentation builds the prerequisites from the physical foundations of computing and connects them to the concrete implementation in main.
</div>

<figure class="figure">
<img src="../assets/diagrams/system-layers.svg" alt="Computing layers">
<figcaption>The conceptual sequence runs from matter to applications; each layer introduces mechanisms grounded in preceding layers.</figcaption>
</figure>

## Learning path

[Start the 12-level sequence](learning-path.md): matter, representation, architecture, boot, kernel, languages, storage, pixels, graphics, networks, virtual machines and research. The catalogue exposes each chapter’s prerequisites and remaining gaps.

## Structure of the corpus

The corpus separates theory, architecture, implementation, validation, limitations and roadmap. A capability is not treated as proven merely because source exists. The Source Atlas is mechanical; authored chapters explain meaning, invariants, ownership, concurrency, failure modes and subsystem relationships.

<figure class="figure">
<img src="../assets/diagrams/chrisos-overview.svg" alt="ChrisOS overview">
<figcaption>High-level organization of the current ecosystem.</figcaption>
</figure>

## Collections

| Volume | Scope |
|---|---|
| [01-foundations — Physical and digital foundations](01-foundations/index.md) | Matter, electrical charge, semiconductor devices, MOSFETs, CMOS logic, Boolean algebra, combinational and sequential circuits. |
| [02-computer-architecture — Computer architecture](02-computer-architecture/index.md) | Datapaths, control, instruction sets, x86-64 execution, privilege, caches, memory hierarchy, buses, MMIO and DMA. |
| [03-boot — Boot and executable formats](03-boot/index.md) | Power-on state, firmware, UEFI, Limine, ELF loading, linker layout and the transition into the ChrisOS entry point. |
| [04-kernel — Kernel architecture](04-kernel/index.md) | Privilege boundaries, monolithic modular organization, exceptions, interrupts, SMP, processes, ELF user execution and system calls. |
| [05-memory — Memory systems](05-memory/index.md) | Physical memory allocation, virtual addressing, four-level paging, CR3, TLBs, heaps, ownership and multiprocessor invalidation. |
| [06-storage — Storage and filesystems](06-storage/index.md) | Block devices, ATA/AHCI/NVMe/VirtIO concepts, sectors, DMA, filesystem structures, journaling, ChrisFS and installation. |
| [07-language-systems — Languages and toolchains](07-language-systems/index.md) | Lexing, parsing, semantic analysis, intermediate forms, bytecode, JIT compilation and the ChrisC/native toolchain paths. |
| [08-graphics — Graphics systems](08-graphics/index.md) | Pixels, color, framebuffers, scanout, composition, rasterization, depth, VirtIO-GPU, VirGL and programmable shaders. |
| [09-emulation — Machine emulation and virtualization](09-emulation/index.md) | Instruction interpretation, architectural state, buses and devices, ChrisVM/ChrisCPU and the boundary to future hardware virtualization. |
| [10-networking — Networking](10-networking/index.md) | Network interface devices, packet movement, Ethernet/IP/UDP/TCP concepts and the current VirtIO networking paths. |
| [11-desktop — Desktop and applications](11-desktop/index.md) | Window management, composition, input routing, built-in ChrisC applications and system workloads. |
| [12-self-hosting — Self-hosting and bootstrap](12-self-hosting/index.md) | Compiler bootstrapping, internally produced objects and executables, kernel rebuild milestones and dependency reduction. |
| [13-real-hardware — Installation and real hardware](13-real-hardware/index.md) | GPT, ESP, UEFI boot media, hardware profiles, driver evidence and the distinction between emulation and physical-machine support. |
| [14-validation — Validation and reliability](14-validation/index.md) | Host tests, QEMU gates, physical-hardware evidence, invariants, fault containment, stability auditing and reproducibility. |
| [15-specifications — Specifications and formats](15-specifications/index.md) | ChrisVM contracts, ChrisO, boot protocols, filesystem formats, ABIs, graphics protocols and externally defined specifications. |
| [16-history — Architecture history](16-history/index.md) | Revision-bound history of architectural changes, superseded designs and the reasons interfaces moved. |

## Evidence policy

1. Current source on main.
2. Reproducible tests and gates on the same revision.
3. Current in-repository specifications.
4. Historical audits, identified by their revision.
5. Roadmap explicitly marked as future work.
