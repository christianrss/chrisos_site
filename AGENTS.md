# AGENTS.md — ChrisOS Documentation

This file is the operational contract for every human or AI agent modifying the ChrisOS documentation repository.

## Primary rule: this is a reference corpus, not a summary site

A technical chapter must not be a condensed overview standing in place of the subject it claims to document. Navigation pages, indexes and abstracts may be concise; authored technical chapters may not use concision as a substitute for coverage.

When a topic spans physics, architecture, operating-system theory, data structures, algorithms, ABI details, source implementation, failure behavior, concurrency or validation, the chapter must carry those layers explicitly. If a subject cannot yet be documented at that depth, keep it visibly incomplete in the coverage report rather than publishing a shallow page as if it were finished.

## Evidence hierarchy

For claims about current ChrisOS behavior, use this order:

1. current source on ChrisOS `main`;
2. reproducible tests and gates on the same revision;
3. current in-repository specifications;
4. revision-bound audits and status records;
5. README prose;
6. roadmap documents, clearly identified as future work.

Never convert roadmap intent into an implementation claim.

## Required chapter model

A substantive page should cover the applicable parts of the following model, in enough detail that a reader can reconstruct the mechanism rather than memorize a description:

- prerequisites and terminology;
- physical or mathematical basis when relevant;
- theory and standard architecture;
- motivation and design constraints;
- ChrisOS architectural decision;
- source files and concrete symbols;
- initialization sequence;
- state and data structures;
- memory layout and ownership;
- control flow and data flow;
- ABI, calling convention or wire/on-disk format when applicable;
- concurrency, CPU context and lock ordering;
- error paths, recovery and fault containment;
- security and privilege boundary;
- performance characteristics and trade-offs;
- validation evidence and tests;
- current limitations;
- roadmap, explicitly separated from current behavior;
- revision notes.

Do not pad chapters to meet a word count. Depth targets are guardrails against accidental summaries; technical completeness is the real criterion.

## Source-level rule

Every implementation claim must be traceable through frontmatter `sources` and, where useful, `symbols`. Explain important code through invariants, ownership, state transitions, interfaces and failure behavior. Do not merely paraphrase individual lines.

The generated Source Atlas is different: it is a deterministic file record. It must reproduce each indexed textual source file completely, with no ellipsis or AI summary. Generated pages are factual indexes and source mirrors, not architectural interpretation.

## Low-context agent workflow

The normal unit of work is one chapter or a tightly related group.

1. Read the target page frontmatter.
2. Read declared `sources`, `symbols`, `depends_on` and `related`.
3. Inspect the Git diff from `reviewed_revision` to current ChrisOS `main` for those sources.
4. Expand context only when a dependency cannot be resolved.
5. Reconcile theory and implementation separately.
6. Run deterministic validation and coverage generation.
7. Update `reviewed_revision` only after source reconciliation.
8. Never manually edit generated files below `docs/*/99-source-atlas/generated/`.

For a page context pack:

```bash
python scripts/context_pack.py docs/en/05-memory/virtual-memory.md --source .source
```

Use `--full` only when symbol-centred extraction is insufficient.

## Translation

English and Brazilian Portuguese are first-class authored trees. Pages sharing the same `id` must be technically equivalent. The pt-BR edition must never be a shortened translation of the English edition.

## Editorial depth accounting

`scripts/coverage.py` distinguishes three states:

- missing chapter;
- authored but below the depth target;
- chapter meeting the depth target.

Existence is not completion. The generated report is intentionally strict so that the site cannot hide unfinished work behind a page count.

## Style

- Formal technical prose.
- No exercises or quizzes.
- No conversational filler.
- Define prerequisites before using them.
- Prefer tables for contracts and layouts.
- Prefer diagrams for state, control flow, memory topology and subsystem boundaries.
- Use equations where they are the clearest representation.
- Prefer primary specifications for external technologies.
- Distinguish observed fact, architectural interpretation and future work.


## Algorithmic documentation rule

Every implementation-facing subsystem chapter must explain the data structures and algorithms that produce the behavior, not only the module responsibilities.

For each important structure or algorithm, record when applicable:

- exact representation and relevant source type or structure;
- invariant maintained by the structure;
- operation sequence or pseudocode;
- worst-case and expected time complexity;
- memory cost and allocation behavior;
- cache/locality implications;
- synchronization and ownership rules;
- failure and saturation behavior;
- why the current design was selected;
- credible alternatives and the trade-off that would justify replacing it;
- validation evidence that exercises the algorithm.

A statement such as "the allocator finds a free page" is incomplete. Documentation must identify the representation used to record page state, the search strategy, cursor/hint behavior, synchronization, complexity, fragmentation implications and the source functions implementing the operation.

Do not assign textbook algorithms to ChrisOS by analogy. Only label a current implementation with an algorithmic name when the source supports that classification.

## Semantic curriculum and build contracts

- `data/documentation-manifest.yml` declares the planned corpus. `data/curriculum.yml` assigns every planned ID exactly once to a level and module. The two must agree; physical chapter URLs remain stable when navigation changes.
- Run `python scripts/curriculum.py` after changing IDs or prerequisites. Unknown prerequisites and dependency cycles fail the build. A planned but unwritten prerequisite is shown as missing, never replaced by an empty published chapter.
- `depends_on` contains prerequisites; `related` may point forward. Do not create reciprocal prerequisites merely because two mechanisms interact.
- Generated routes, figures, coverage reports and source mirrors are build outputs. Edit their scripts and data, not the generated files.
- A word floor is only an editorial signal. It cannot establish technical completeness or justify calling a chapter reviewed. Preserve explicit limitations and distinguish inspected code from executed evidence.
- `context_pack.py` includes dependency outlines and source hashes. Inspect `diff_status`: `unavailable-baseline` requires retrieving the relevant history, not assuming an empty diff proves no change.
- `next_work.py` lists missing and short chapters in curriculum order. Expand an existing weak prerequisite before introducing a dependent chapter that silently assumes it.
- The static search is language-specific. Complete source mirrors are available through the atlas, but excluded from text search payloads; do not duplicate the full source corpus into the search index.

Verification for publication:

```bash
python -m unittest discover -s tests
python scripts/build_all.py --source .source --docs docs
mkdocs build --strict
```

Document any additional source tests actually executed. Do not equate documentation build success with successful kernel boot, desktop operation or hardware support.
