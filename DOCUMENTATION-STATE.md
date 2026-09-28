# ChrisOS Documentation — Operational State Memory

Snapshot date: 2026-09-28  
Baseline documentation commit: `ec9b3eba87ac66b938ed57d12d8133a766a6813e`

This file is the persistent handoff memory for humans and AI agents working on the ChrisOS documentation corpus. It records what is already implemented, what is incomplete, and the completion rules. It is a snapshot, not the canonical coverage calculator: always regenerate coverage before updating the numbers below.

## Canonical sources of truth

1. `data/documentation-manifest.yml` — planned chapter corpus.
2. `data/curriculum.yml` — semantic order, levels, modules and chapter placement.
3. `docs/*/98-maintenance/coverage.md` — generated structural/depth coverage.
4. `scripts/next_work.py` — next missing/thin work in curriculum order.
5. ChrisOS `main` source — authority for current implementation claims.
6. `AGENTS.md` — authoring, evidence and validation contract.

Never treat this memory file as stronger evidence than those sources.

## Current corpus state

Planned chapters: **214**.

Authored chapters:
- EN: **89 present**
- PT-BR: **89 present**
- structurally bilingual authored pairs: **89**
- structural coverage: **41.6%**
- missing chapters in both languages: **125**

Depth-floor state:
- EN: **64** chapters above the text floor; **25** present but below the floor.
- PT-BR: **58** chapters above the text floor; **31** present but below the floor.
- chapters above the floor in **both** languages: **58**.
- chapters needing expansion in at least one language: **31**.
- six kernel chapters meet the EN floor but still need PT-BR expansion: `idt-exceptions`, `interrupts-smp`, `pic-apic-ioapic`, `process-lifecycle`, `user-copy`, `user-mode-entry`.

The word floor is only a length guardrail. A chapter is not technically complete merely because it crosses the floor.

## Chapters currently above the depth floor in both languages

`ac-signals-frequency-impedance`, `acpi-platform`, `algorithmic-complexity`, `arithmetic-circuits`, `atom-semiconductor`, `atomics-memory-model`, `boolean-algebra`, `boot-information`, `buses-mmio-dma`, `cache-hierarchy`, `capacitance-inductance`, `clock-timing`, `coherence`, `combinational-logic`, `cpu-datapath-isa`, `crystal-bands-doping`, `data-representation-layout`, `data-structures`, `electric-charge-field-potential`, `cmos-switching-power`, `logic-levels-noise-margins`, `number-systems-binary-arithmetic`, `proof-invariants-induction`, `discrete-math-sets-relations-functions`, `electromagnetic-induction-transformers`, `mos-capacitor`, `noise-grounding-signal-integrity`, `power-delivery-regulation`, `transmission-lines-differential-signals`, `elf-linking`, `emulator-theory`, `gdt-tss`, `higher-half-kernel`, `kernel-jobs-kthreads`, `kernel-model`, `latches-flipflops`, `limine`, `linker-script`, `logic-sequential`, `machine-code`, `ohm-kirchhoff-circuits`, `pci-pcie`, `pixels-framebuffer`, `pn-junction`, `power-on-kstart`, `privilege-rings`, `rc-rlc-transients`, `registers-counters`, `reset-firmware`, `sram-dram`, `systems-algorithms`, `transistor-cmos`, `uefi`, `vectors-complex-numbers-systems`, `voltage-current-resistance-power`, `x86-64-memory-privilege`, `x86-instruction-encoding`, `x86-registers-flags`.

## Authored chapters that still require expansion

`agent-workflow`, `architecture-history`, `block-storage`, `chrisc-clvm`, `chrisfs`, `chrisvm-chriscpu`, `compiler-pipeline`, `desktop-applications`, `heap-ownership`, `idt-exceptions`, `installation-real-hardware`, `interrupts-smp`, `native-toolchain`, `network-stack`, `panic-logging`, `physical-memory`, `pic-apic-ioapic`, `process-lifecycle`, `processes-syscalls`, `self-hosting-bootstrap`, `shaders-csir`, `software-3d`, `specifications-policy`, `timers`, `tlb-shootdown`, `user-copy`, `user-mode-entry`, `validation-evidence`, `virtio-gpu-virgl`, `virtual-memory`, `virtualization-chrishv`.

## Missing chapters by volume

| Volume | Missing |
|---|---:|
| 01-foundations | 9 |
| 02-computer-architecture | 5 |
| 03-boot | 0 |
| 04-kernel | 0 |
| 05-memory | 9 |
| 06-storage | 12 |
| 07-language-systems | 17 |
| 08-graphics | 17 |
| 09-emulation | 16 |
| 10-networking | 6 |
| 11-desktop | 7 |
| 12-self-hosting | 4 |
| 13-real-hardware | 5 |
| 14-validation | 6 |
| 15-specifications | 7 |
| 16-history | 3 |
| 98-maintenance | 2 |
| **Total** | **125** |

For the exact ordered list, run:

```bash
python scripts/next_work.py --lang en --limit 214
python scripts/next_work.py --lang pt-br --limit 214
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
- bounded page/section search text prevents duplicated MkDocs records from exceeding the reader payload budget as the corpus grows;
- post-build reader smoke tests;
- GitHub Pages build and deploy pipeline.
- CI explicitly runs `python -m unittest discover -s tests` before generated build and publication gates.

Last known successful reader/deploy baseline: `286a966073835e9e6b84acb7e149d18fa62bc930`.

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
10. Run a final bilingual equivalence and technical-completeness pass over all 214 IDs.

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

- 214/214 planned IDs authored in EN and PT-BR;
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
