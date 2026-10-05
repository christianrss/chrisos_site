# ChrisOS Documentation — Operational State Memory

Snapshot date: 2026-10-04  
Current reconciled ChrisOS source revision: `e05a17fd76333114a3fb5c2452f38ca747d4ac56`  
Baseline documentation commit: `7b03fb1c9fa75472bded8acf1739f2a1876ea3f0`

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
- EN: **221 present**
- PT-BR: **221 present**
- structurally bilingual authored pairs: **221**
- structural coverage: **100.0%**
- missing chapters in both languages: **0**

The structural count above is computed by the same canonical identity rule used by `scripts/coverage.py`: planned chapter IDs from `data/documentation-manifest.yml` are joined to authored pages by frontmatter `id` and `lang`. Filenames are not chapter identities.

A previous snapshot incorrectly treated four Volume 17 route filenames as if they were canonical IDs. The pages already existed:
- `docs/*/17-developer-guide/index.md` carries `id: developer-guide`;
- `linux-development-environment.md` carries `id: development-environment-linux`;
- `windows-wsl-development-environment.md` carries `id: development-environment-windows`;
- `troubleshooting.md` carries `id: development-troubleshooting`.

The 2026-10-05 completion pass added the final genuinely missing IDs, `source-policy` and `documentation-schema`. The validated content commit `7b03fb1c9fa75472bded8acf1739f2a1876ea3f0` produced `coverage planned=221 authored_pairs=442` and passed the complete documentation workflow through Pages.

Structural completeness does **not** mean every page is technically final. Depth-floor state and source-review state remain separate generated signals. Use the generated coverage report and review queue after `scripts/build_all.py`; word floors are editorial guardrails, and stale-source entries require reconciliation rather than automatic prose changes.

## Missing chapters by volume

| Volume | Missing |
|---|---:|
| 01-foundations | 0 |
| 02-computer-architecture | 0 |
| 03-boot | 0 |
| 04-kernel | 0 |
| 05-memory | 0 |
| 06-storage | 0 |
| 07-language-systems | 0 |
| 08-graphics | 0 |
| 09-emulation | 0 |
| 10-networking | 0 |
| 11-desktop | 0 |
| 12-self-hosting | 0 |
| 13-real-hardware | 0 |
| 14-validation | 0 |
| 15-specifications | 0 |
| 16-history | 0 |
| 17-developer-guide | 0 |
| 98-maintenance | 0 |
| **Total** | **0** |

The 2026-10-04/05 completion campaign structurally closed the remaining validation, specification, history and maintenance gaps, including `driver-compatibility`, `host-tests`, `qemu-gates`, `hardware-gates`, `fault-injection`, `fuzzing`, `performance-measurement`, `chrisvm-spec`, `chrisvm-boot-spec`, `chriso-spec`, `chrisfs-spec`, `clvm-spec`, `shader-spec`, `bibliography`, `graphics-history`, `toolchain-history`, `chrisvm-history`, `source-policy` and `documentation-schema`.

There is no remaining structural chapter gap. The next maintenance work should be selected from generated **Needs expansion** and **review queue** entries, not by creating new manifest chapters.

For the current curriculum state, run:

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

Last known successful reader/deploy baseline for the validated content snapshot: `7b03fb1c9fa75472bded8acf1739f2a1876ea3f0`.

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
