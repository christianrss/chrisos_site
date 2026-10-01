# ChrisOS Documentation — Operational State Memory

Snapshot date: 2026-09-30  
Current reconciled ChrisOS source revision: `e05a17fd76333114a3fb5c2452f38ca747d4ac56`  
Baseline documentation commit: `a70dfc8e62149aae5e22374e6d8a4059a7f709fb`

This file is the persistent handoff memory for humans and AI agents working on the ChrisOS documentation corpus. It records what is already implemented, what is incomplete, and the completion rules. It is a snapshot, not the canonical coverage calculator: always regenerate coverage before updating the numbers below.

## Canonical sources of truth

1. `data/documentation-manifest.yml` — planned chapter corpus.
2. `data/curriculum.yml` — semantic order, levels, modules and chapter placement.
3. `docs/*/98-maintenance/coverage.md` — generated structural/depth coverage.
4. `scripts/next_work.py` — next missing/thin work in curriculum order.
5. ChrisOS `main` source — authority for current implementation claims. Technical/reference prose removed from the source repository is not a fallback authority; `chrisos_site` is the canonical documentation corpus.
6. `AGENTS.md` — authoring, evidence and validation contract.

Never treat this memory file as stronger evidence than those sources.

## Current corpus state

Planned chapters: **221**.

Authored chapters:
- EN: **141 present**
- PT-BR: **141 present**
- structurally bilingual authored pairs: **141**
- structural coverage: **63.8%**
- missing chapters in both languages: **80**

Depth-floor state:
- EN: **122** chapters above the text floor; **19** present but below the floor.
- PT-BR: **116** chapters above the text floor; **25** present but below the floor.
- chapters above the floor in **both** languages: **116**.
- chapters needing expansion in at least one language: **25**.
- three kernel chapters meet the EN floor but still need PT-BR expansion: `process-lifecycle`, `user-copy`, `user-mode-entry`.

The word floor is only a length guardrail. A chapter is not technically complete merely because it crosses the floor.

## Chapters currently above the depth floor in both languages

`ac-signals-frequency-impedance`, `acpi-platform`, `address-spaces`, `ahci`, `algorithmic-complexity`, `arithmetic-circuits`, `arrays-lists-stacks-queues`, `ata`, `atom-semiconductor`, `atomics-memory-model`, `bitmaps-rings-free-lists`, `block-storage`, `boolean-algebra`, `boot-information`, `branch-prediction-speculation`, `buses-mmio-dma`, `cache-hierarchy`, `calling-conventions`, `capacitance-inductance`, `clock-timing`, `chrisfs`, `chrisfs-cache`, `chrisfs-directories`, `chrisfs-fsck`, `chrisfs-inodes`, `chrisfs-journal`, `chrisfs-superblock`, `chrisc-clvm`, `clvm-bytecode`, `clvm-interpreter`, `clvm-memory`, `clvm-syscalls`, `cmos-switching-power`, `coherence`, `combinational-logic`, `compiler-pipeline`, `cpu-datapath-isa`, `crystal-bands-doping`, `data-representation-layout`, `data-structures`, `discrete-math-sets-relations-functions`, `electric-charge-field-potential`, `electromagnetic-induction-transformers`, `elf-linking`, `emulator-theory`, `gdt-tss`, `graph-algorithms`, `graphs-union-find`, `hash-tables`, `heap-ownership`, `hhdm`, `higher-half-kernel`, `idt-exceptions`, `intermediate-representation`, `interrupts-smp`, `jit-memory`, `kernel-jobs-kthreads`, `kernel-model`, `latches-flipflops`, `lexical-analysis`, `limine`, `linker-script`, `logic-levels-noise-margins`, `logic-sequential`, `machine-code`, `memory-controller-dram-organization`, `microarchitecture-pipeline`, `mos-capacitor`, `native-codegen`, `noise-grounding-signal-integrity`, `number-systems-binary-arithmetic`, `nvme`, `ohm-kirchhoff-circuits`, `out-of-order-renaming-retirement`, `page-faults`, `parsing`, `page-table-layout`, `panic-logging`, `partitions-gpt`, `pci-pcie`, `physical-memory`, `pic-apic-ioapic`, `pipeline-hazards-forwarding`, `pixels-framebuffer`, `pmm-algorithms`, `pn-junction`, `power-delivery-regulation`, `power-on-kstart`, `privilege-rings`, `proof-invariants-induction`, `rc-rlc-transients`, `recursion-recurrences-amortization`, `registers-counters`, `reset-firmware`, `resource-lifetime`, `semantic-analysis`, `sorting-searching`, `spinlocks`, `sram-dram`, `string-parsing-algorithms`, `systems-algorithms`, `timers`, `tlb`, `tlb-shootdown`, `transistor-cmos`, `transmission-lines-differential-signals`, `trees-heaps-tries`, `uefi`, `usb-storage`, `vectors-complex-numbers-systems`, `virtio-block`, `virtual-memory`, `voltage-current-resistance-power`, `x86-64-memory-privilege`, `x86-instruction-encoding`, `x86-registers-flags`.

## Authored chapters that still require expansion

`agent-workflow`, `architecture-history`, `build-run-debug`, `chrisvm-chriscpu`, `contribution-workflow`, `desktop-applications`, `developer-guide`, `development-environment-linux`, `development-environment-windows`, `development-troubleshooting`, `installation-real-hardware`, `native-toolchain`, `network-stack`, `process-lifecycle`, `processes-syscalls`, `self-hosting-bootstrap`, `shaders-csir`, `software-3d`, `specifications-policy`, `testing-validation`, `user-copy`, `user-mode-entry`, `validation-evidence`, `virtio-gpu-virgl`, `virtualization-chrishv`.

## Missing chapters by volume

| Volume | Missing |
|---|---:|
| 01-foundations | 0 |
| 02-computer-architecture | 0 |
| 03-boot | 0 |
| 04-kernel | 0 |
| 05-memory | 0 |
| 06-storage | 0 |
| 07-language-systems | 7 |
| 08-graphics | 17 |
| 09-emulation | 16 |
| 10-networking | 6 |
| 11-desktop | 7 |
| 12-self-hosting | 4 |
| 13-real-hardware | 5 |
| 14-validation | 6 |
| 15-specifications | 7 |
| 16-history | 3 |
| 17-developer-guide | 0 |
| 98-maintenance | 2 |
| **Total** | **80** |

For the exact ordered list, run:

```bash
python scripts/next_work.py --lang en --limit 221
python scripts/next_work.py --lang pt-br --limit 221
```

## Reader / UX / deployment state

Implemented and merged:
- custom MkDocs book-style reader;
- responsive sidebar/drawer and mobile reading controls;
- semantic level/module/chapter navigation;
- chapter TOC and sequential previous/next navigation;
- direct language-specific search index loading without a Web Worker dependency;
- search ranking across title, page title, path and body text;
- search-result deduplication;
- cache-busting of `site.css` and `site.js` by deployment SHA;
- search JSON loaded with deployment version and no stale-cache reuse;
- adaptive bounded page/section search excerpts preserve all searchable titles/anchors while keeping the direct client-side reader payload below its mobile size budget as the corpus grows;
- post-build reader smoke tests;
- GitHub Pages build and deploy pipeline.
- CI explicitly runs `python -m unittest discover -s tests` before generated build and publication gates.

Last known successful reader/deploy baseline: `a70dfc8e62149aae5e22374e6d8a4059a7f709fb`.

Still required for the reader:
- continued real-browser QA across Android/mobile, desktop and narrow tablet widths;
- fix any runtime defect found in the deployed site before adding cosmetic features;
- keep search and navigation runtime contracts covered by smoke tests.

## Content completion order

Work in curriculum order and preserve prerequisites.

1. Expand any weak prerequisite that blocks the next chapter.
2. Finish the remaining foundations.
3. Continue architecture/platform prerequisites.
4. Complete kernel/memory/storage.
5. Complete language systems/toolchain.
6. Complete graphics/desktop/networking.
7. Complete emulation/virtualization.
8. Complete self-hosting, hardware, validation and specifications.
9. Finish history and maintenance pages.
10. Run a final bilingual equivalence and technical-completeness pass over all 221 IDs.

Do not create a shallow placeholder merely to reduce the missing count.

## Required model for every substantive chapter

Apply the full chapter contract from `AGENTS.md`: prerequisites, theory, mathematical/physical basis where relevant, architecture, ChrisOS design, source files and symbols, initialization, state/data structures, algorithms and complexity, memory/ownership, control/data flow, ABI/format, concurrency, failure/recovery, privilege/security, performance/trade-offs, validation evidence, current limitations, roadmap separated from current behavior, and revision provenance.

English and PT-BR must remain technically equivalent. PT-BR may not be a shortened translation.

## Per-run completion workflow

A content-producing agent should:

1. Read this file and `AGENTS.md`.
2. Pull current `chrisos_site/main` and ChrisOS `main`.
3. Run `scripts/next_work.py` in both languages.
4. Select at most two tightly related chapters; use one when source reconciliation is substantial.
5. Read prerequisites and current source before writing.
6. Author/expand EN and PT-BR to equivalent technical depth.
7. Add diagrams/tables/equations where they materially improve understanding.
8. Update frontmatter source dependencies and revision evidence.
9. Run unit tests, `scripts/build_all.py`, reader JavaScript checks and `mkdocs build --strict`.
10. Commit only a validated atomic batch.
11. Recompute coverage after the commit.
12. Update this memory snapshot only when the validated counts or major implementation state changed.

## Definition of corpus completion

The temporary completion campaign ends only when all conditions hold:

- 221/221 planned IDs authored in EN and PT-BR;
- zero missing chapters;
- zero chapters below the configured depth floor in either language;
- prerequisite DAG valid;
- no conversational/template filler;
- source/revision metadata reconciled against current ChrisOS `main`;
- bilingual technical equivalence reviewed;
- diagrams/tables/code references render correctly;
- search/navigation smoke tests pass;
- `python -m unittest discover -s tests` passes;
- `python scripts/build_all.py --source .source --docs docs` passes;
- `mkdocs build --strict` passes;
- GitHub Pages deployment succeeds.

Crossing the word floor alone is not completion.
