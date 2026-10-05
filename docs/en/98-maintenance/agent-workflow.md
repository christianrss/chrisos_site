---
id: agent-workflow
lang: en
type: technical-chapter
volume: 98-maintenance
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources: []
symbols: []
depends_on: []
related:
  - validation-evidence
  - documentation-schema
  - source-policy
---

# Low-context documentation maintenance

## Purpose

The documentation corpus is designed to scale beyond the amount of material that a human reviewer or an AI agent should load for one ordinary maintenance task.

The strategy is not to compress the entire project into one summary. It is to make each authored page declare enough dependency information that a narrow, reproducible context can be assembled automatically.

The operating model is:

1. identify one documentation page or one source change;
2. resolve the declared dependency set;
3. inspect only the affected source/diff;
4. reconcile the authored interpretation;
5. run deterministic repository-wide validation;
6. publish only after the global contracts still pass.

This keeps local reasoning bounded while preserving global consistency.

## Two repositories, two kinds of authority

The maintenance workflow spans two repositories.

The ChrisOS source repository is authoritative for implementation behavior, build targets, executable gates and source history.

The documentation repository is authoritative for the long-form bilingual technical corpus, curriculum, specifications, architecture history, validation interpretation and generated source atlas.

The documentation pipeline checks out both repositories during CI.

This split means a documentation agent must distinguish:

- implementation evidence from ChrisOS;
- documentation-tool behavior from chrisos_site;
- generated facts from authored interpretation.

The `sources` frontmatter field refers to files in the ChrisOS source checkout. Maintenance pages about the documentation machinery itself may intentionally have no ChrisOS `sources`.

## Page identity

Every authored page has an `id` and `lang`.

The pair:

    (id, lang)

is the page identity used by validation.

For authored bilingual material, the same `id` must exist in:

- `en`;
- `pt-br`.

The validator rejects an authored identity that exists in only one language.

This avoids a common failure mode in which English evolves while Portuguese silently disappears from the maintained corpus.

## Frontmatter as dependency metadata

Frontmatter is not decorative metadata. It drives maintenance automation.

Important fields include:

- `id` — stable conceptual page identity;
- `lang` — language identity;
- `type` — editorial/depth class;
- `reviewed_revision` — ChrisOS revision used for source reconciliation;
- `sources` — concrete ChrisOS files that materially support the page;
- `symbols` — high-value identifiers inside large source files;
- `depends_on` — prerequisite documentation identities;
- `related` — non-prerequisite conceptual links.

The metadata creates a graph from source files to authored interpretation and from authored pages to conceptual dependencies.

## Bilingual metadata invariants

`validate_docs.py` checks selected bilingual metadata for equality.

For one page identity, English and Portuguese must agree on:

- `sources`;
- `depends_on`;
- `reviewed_revision`.

This is important because two translations should not claim to describe different source revisions or different prerequisite graphs.

Language-specific prose can differ in sentence structure, but the evidence boundary must remain shared.

## Stable IDs matter more than filenames

A page may be renamed or moved while preserving its conceptual identity.

The stable `id` lets curriculum and dependency tooling refer to the concept rather than to an incidental path.

This reduces coupling between navigation layout and documentation semantics.

Changing an ID is therefore more significant than changing a filename. It can affect:

- curriculum entries;
- `depends_on`;
- `related`;
- generated metadata;
- cross-page navigation.

ID changes should be treated as schema migrations, not cosmetic edits.

## Stale detection

`scripts/stale_docs.py` compares each authored page against the current ChrisOS HEAD.

For pages that declare `sources` and a `reviewed_revision`, the script asks Git which declared source files changed between:

    reviewed_revision .. HEAD

Only those declared files are considered.

If none changed, the page is not marked stale merely because unrelated source changed elsewhere.

If at least one changed, the page is added to the generated review queue with:

- page path;
- reviewed revision;
- changed source paths.

This is the core low-context mechanism.

## Invalid revision handling

Stale detection also verifies that `reviewed_revision` resolves to a commit in the source checkout.

If it does not, the page is reported separately as having an invalid revision.

An invalid baseline must not be interpreted as "unchanged."

Without a valid baseline, the system cannot prove that the declared sources were reconciled.

## Source reconciliation

A stale page should not be updated by mechanically replacing the revision hash.

The maintenance task is:

1. inspect the source diff;
2. determine whether the documented contract actually changed;
3. update prose if necessary;
4. preserve historical statements when they remain historical;
5. advance `reviewed_revision` only after reconciliation.

Sometimes the correct result is a prose change.

Sometimes the source changed in a way that does not alter the documented contract, and only the reviewed revision needs advancement.

The distinction requires technical review.

## Context packs

`scripts/context_pack.py` creates a bounded working directory for one page.

The pack contains:

- a copy of the target page;
- declared source material;
- the Git diff from the page baseline to current source HEAD;
- metadata;
- source hashes;
- dependency summaries;
- maintenance instructions.

This is intended to be the normal unit of context for an agent working on one page.

## Large-source handling

Context packs do not always copy every large source file in full.

The current implementation uses a full-file threshold of 24,000 characters.

For larger files, declared `symbols` can be used to extract context around relevant identifiers.

The extractor keeps bounded regions around symbol hits and merges overlapping regions.

This reduces context cost while still showing the code most likely to support the page.

If the excerpt is insufficient, the maintainer can explicitly request a full pack.

The important rule is that truncation is visible, not silent.

## Dependency summaries

A context pack does not recursively copy the entire documentation graph.

For `depends_on` and `related`, it records compact same-language summaries containing page identity, path, reviewed revision and headings.

This prevents one page from pulling an unbounded transitive closure of the corpus into every task.

If a dependency is missing, the pack records that state explicitly.

## Diff status

The context pack records whether the source diff is:

- changed;
- unchanged;
- unavailable because no valid baseline exists;
- not applicable when no source dependencies are declared.

An unavailable baseline is not equivalent to unchanged source.

This distinction prevents a missing Git ancestor or invalid revision from creating false confidence.

## Source hashes

Each packed source file receives a SHA-256 value in the pack metadata.

The hash identifies the exact bytes inspected.

This is useful when the same logical file path changes repeatedly or when a review artifact is retained outside the live checkout.

The Git revision remains the project-wide identity; the content hash provides file-level identity.

## Generated source inventory

`scripts/inventory.py` scans textual ChrisOS source files and builds the source atlas.

The scanner skips generated or non-source working directories such as:

- `.git`;
- `build`;
- `site`;
- virtual environments;
- Python cache directories.

For textual candidates it records:

- path;
- line count;
- byte count;
- SHA-256;
- detected includes;
- detected C-like function definitions;
- complete textual content.

This output is deterministic repository evidence, not authored architectural interpretation.

## Source atlas role

The generated source atlas guarantees traceability from documentation to exact source content.

It is intentionally verbose because generated material does not consume authoring effort the way hand-written prose does.

The atlas should answer:

> What exactly was in this file at the indexed revision?

It should not answer:

> What architectural role does this file play?

Ownership, invariants, concurrency, failure behavior and rationale belong in authored chapters.

## Generated facts versus authored interpretation

This separation is central.

Automation is good at producing:

- file inventories;
- hashes;
- counts;
- dependency tables;
- symbol lists;
- navigation structures;
- stale lists;
- coverage statistics.

Authored pages remain responsible for:

- architectural boundaries;
- ownership;
- memory/lifetime rules;
- concurrency;
- algorithms;
- complexity;
- security;
- failure/recovery;
- validation meaning;
- limitations;
- roadmap separation.

Generating facts prevents agents from spending tokens repeatedly rediscovering mechanical information.

Authored interpretation prevents the site from becoming a source-code dump with no technical model.

## Structural coverage

`scripts/coverage.py` compares the authored corpus with the planned chapter manifest.

Structural coverage asks whether each planned chapter identity exists.

It does not claim technical completeness.

A file with a title and a few sentences can satisfy structural presence while still failing the editorial depth target.

That is why the project tracks structural and text-floor coverage separately.

## Text-depth floors

The coverage script currently defines minimum word signals by page type.

Examples include:

- concept: 1,800 words;
- technical chapter: 1,800 words;
- subsystem: 2,200 words;
- specification: 1,600 words;
- source commentary: 1,200 words;
- other authored technical pages: 900 words.

The word count excludes fenced code and HTML markup.

These thresholds are editorial signals only.

Crossing the floor does not prove technical correctness or completeness.

## Why code blocks do not count toward depth

A documentation page should not meet its prose target by pasting large source files or command transcripts.

The word counter removes fenced code before measuring depth.

This creates the desired incentive:

- generated source belongs in the atlas;
- focused code excerpts can support explanation;
- prose depth must come from actual technical reasoning.

A page can therefore contain extensive code while still being classified as thin if its explanatory model is insufficient.

## Curriculum graph

`scripts/curriculum.py` validates the planned learning path.

The curriculum must partition the manifest exactly:

- every planned chapter appears;
- no unknown chapter appears;
- no duplicate chapter identity appears.

The script also validates prerequisite relationships and detects dependency cycles.

This makes `depends_on` more than a hyperlink field: it participates in an executable learning DAG.

## Reading state

The generated learning path distinguishes:

- missing chapter;
- present but requiring expansion;
- text floor met, technical review still required.

This wording is deliberate.

A page that reaches the word floor is not labeled "complete."

The system preserves the difference between editorial length and technical review.

## Documentation validation

`scripts/validate_docs.py` enforces repository contracts.

It checks:

- required frontmatter fields;
- duplicate `id/lang` identities;
- declared ChrisOS source paths;
- placeholder tokens;
- bilingual presence;
- bilingual metadata alignment.

It also emits warnings for very short authored technical bodies.

These checks prevent several classes of silent documentation corruption before MkDocs runs.

## Source-to-doc reverse map

`scripts/source_map.py` emits a machine-readable reverse index from ChrisOS source paths to documentation pages.

This supports impact analysis in the opposite direction.

Instead of asking:

> Which source files support this page?

the reverse map answers:

> Which pages declare that they depend on this source file?

That map is useful for code-review automation and future change-triggered maintenance.

## Build orchestration

`scripts/build_all.py` is the central documentation generation entry point.

Its sequence includes:

- documentation unit tests;
- diagram generation;
- figure generation;
- source inventory;
- coverage;
- curriculum;
- reader-navigation checks;
- stale detection;
- documentation validation;
- editorial-style checks;
- source-map generation.

A local or CI pass is meaningful because these steps run together against one checked-out documentation state.

## CI as global consistency check

The GitHub Pages workflow runs on:

- pushes to `main`;
- pull requests targeting `main`;
- manual dispatch;
- a weekly schedule.

It checks out both documentation and ChrisOS main, installs dependencies, runs the documentation pipeline and then executes many specialized verification scripts.

After those checks it performs:

- JavaScript syntax validation;
- strict MkDocs build;
- SEO/discovery checks;
- generated-reader smoke tests;
- Pages artifact upload;
- deployment for non-pull-request runs.

This is the global safety net after local low-context editing.

## Concurrency behavior

The Pages workflow uses a shared concurrency group with cancellation enabled.

When several commits are pushed rapidly, an older in-progress workflow may be cancelled by a newer one.

That cancellation is not automatically a content failure.

The authoritative validation result is the newest workflow for the final repository state.

Maintenance reports should therefore identify the final commit SHA and final workflow conclusion rather than treating every intermediate cancellation as an error.

## Local reasoning, global validation

Low-context maintenance is safe only because local editing is followed by global deterministic checks.

The workflow intentionally combines:

    narrow context for reasoning
    +
    repository-wide automated contracts

Using narrow context without global validation risks hidden cross-page breakage.

Loading the whole corpus into every task wastes resources and makes source reconciliation less precise.

The combination provides both scalability and integrity.

## Update algorithm

A practical update cycle is:

1. identify changed ChrisOS revision;
2. run stale detection;
3. select the highest-priority stale or thin page;
4. create or emulate its context pack;
5. inspect source diff and declared dependencies;
6. update both languages;
7. validate source paths and metadata;
8. run the documentation pipeline;
9. inspect the final workflow;
10. publish only after the latest state is green.

If no page is stale, move to planned missing chapters or below-floor chapters.

If structural coverage is complete, maintenance becomes reconciliation and depth work rather than creation.

## Thin-page workflow

A thin page is present but below its type-specific text floor.

Expansion should not consist of filler.

A useful expansion should add one or more of:

- prerequisites;
- formal model;
- source-backed implementation detail;
- data structures;
- algorithm steps;
- complexity;
- ownership/lifetime;
- concurrency;
- failure behavior;
- security;
- performance;
- validation;
- limitations;
- historical context;
- roadmap.

The best additions reduce ambiguity for a reader who needs to implement, debug or review the subsystem.

## Stale-page workflow

A stale page requires source reconciliation, not automatic rewriting.

The diff should be classified:

### No contract change

Implementation changed internally but the documented behavior remains accurate. Advance the review revision after checking both languages.

### Contract extension

Existing behavior remains while new capability appears. Add the new contract and evidence.

### Contract change

An existing rule changed. Update normative/current prose and any dependent pages.

### Historical-only effect

Current source changed, but the page is a history chapter describing a past revision. Preserve the historical statement and update only the framing needed to prevent it from being read as current behavior.

This classification prevents revision updates from erasing valid history.

## Bilingual workflow

English and Portuguese should be maintained as one conceptual transaction.

A safe sequence is:

1. reconcile evidence once;
2. update English;
3. update Portuguese with equivalent technical claims;
4. compare frontmatter;
5. run bilingual validation;
6. treat the final second-language commit as the state that must pass CI.

Intermediate one-language commits may fail or be cancelled because the repository intentionally rejects missing bilingual pairs.

That is expected during a tightly controlled sequential update, but the final state must always restore equivalence.

## Avoiding duplicated research

Once a page has a valid reviewed revision and unchanged declared sources, do not repeatedly re-research it during unrelated updates.

Reuse the dependency graph.

This is the main cost-control rule of the project.

Research should be reopened when:

- a declared source changes;
- a dependency changes in a way that alters interpretation;
- a validation failure contradicts the page;
- the page is intentionally being deepened;
- an external standard claim requires refreshed verification.

Otherwise, the last reconciled state remains usable.

## Scope control

A maintenance agent should not fix unrelated source or documentation merely because it notices it.

Record the issue and keep the current patch aligned with one reviewable claim unless the discovered defect blocks validation.

Scope control makes failures attributable and prevents a simple documentation update from turning into an unreviewable refactor.

For broader campaigns, group pages by one coherent source area or editorial objective and validate after each meaningful batch.

## Failure handling

If CI fails, classify the failure before editing.

Typical classes include:

- malformed frontmatter;
- bilingual metadata mismatch;
- missing source path;
- curriculum/DAG error;
- generated navigation error;
- specialized contract-check failure;
- JavaScript syntax error;
- MkDocs strict-build failure;
- discovery/reader smoke failure;
- deployment/infrastructure failure.

Do not change prose to fix an infrastructure outage.

Do not dismiss a source-contract verifier as "documentation only" if the page made the claim being checked.

## Generated files

Generated outputs should be regenerated, not manually curated.

Examples include:

- source inventory;
- source atlas pages;
- coverage status;
- learning path;
- review queue;
- source map;
- diagrams/figures produced by scripts.

Hand-editing generated output creates drift because the next build will overwrite it.

Changes belong in:

- source data;
- generation script;
- authored page;

depending on what is actually wrong.

## Evidence retention

For important maintenance batches, retain at least:

- final documentation commit;
- ChrisOS source revision;
- final workflow run ID;
- build/deploy conclusion;
- structural coverage count;
- stale count;
- remaining thin-page count.

This compact record is enough to continue a later session without replaying the entire campaign.

It also prevents an agent from relying on conversational memory when repository state can provide authoritative facts.

## Completion criteria

A documentation campaign is not complete merely because files were edited.

A strong completion condition is:

- planned structural coverage is satisfied;
- no unexpected stale pages remain;
- no invalid reviewed revisions remain;
- intended thin pages meet their depth floor;
- bilingual contracts pass;
- generated curriculum and navigation pass;
- strict site build succeeds;
- discovery and reader smoke tests succeed;
- the final Pages deployment succeeds.

The corpus can still improve after those conditions.

They define a stable maintenance checkpoint, not the end of technical documentation.

## Revision note

This workflow describes the documentation-maintenance architecture at the current site implementation while using ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56` as the shared source baseline for authored technical pages.

The central principle is simple: **read narrowly, declare dependencies explicitly, generate mechanical facts deterministically, preserve bilingual evidence boundaries and validate the entire corpus before publication.**
