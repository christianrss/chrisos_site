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
  - source-policy
  - documentation-schema
---

# Low-context documentation maintenance

## Objective

The ChrisOS documentation corpus is designed to grow far beyond what one maintenance task should read into context.

The maintenance model therefore does **not** assume that an agent scans every chapter, every source file or the complete repository before making one update.

Instead, the corpus stores machine-readable dependencies in frontmatter and generates repository facts deterministically.

The normal maintenance unit is:

    one authored page
    + its declared ChrisOS sources
    + relevant source diff
    + a small dependency summary
    + explicit validation commands

This keeps maintenance cost proportional to the changed boundary rather than to total corpus size.

## Core principle

The workflow is based on one rule:

> Context should be selected by declared dependency and revision evidence, not by broad semantic search over the entire corpus.

Semantic search can still help when a dependency is genuinely unknown.

It should not be the default when frontmatter already identifies the relevant source contract.

This reduces both token cost and the risk of mixing unrelated subsystem assumptions into a focused update.

## Canonical page identity

The maintenance tools use frontmatter `id` and `lang` as canonical document identity.

Filename similarity is not enough.

For example:

    linux-development-environment.md

can represent:

    id: development-environment-linux

The same rule applies to source mapping, curriculum, coverage and bilingual pairing.

Agents must therefore read frontmatter before assuming that a missing filename implies a missing chapter.

## Frontmatter dependency graph

The key fields are:

- `sources`;
- `symbols`;
- `depends_on`;
- `related`;
- `reviewed_revision`.

They answer different questions.

### sources

Concrete ChrisOS repository paths whose implementation materially supports the page.

### symbols

Important identifiers inside declared sources. They help context extraction focus large files.

### depends_on

Conceptual prerequisites in the curriculum DAG.

### related

Useful adjacent pages that are not prerequisites.

### reviewed_revision

The ChrisOS source commit against which the page was last reconciled.

Together, these fields form a bounded maintenance graph.

## Reverse source map

`scripts/source_map.py` reads every authored page and builds two deterministic structures:

    page path -> metadata
    source path -> affected pages

The reverse map makes impact analysis cheap.

If:

    kernel/mm/pmm.c

changes, the tool can identify pages that explicitly declare that source without asking a language model to guess which chapter names "sound related."

This is more reliable than filename similarity because one source file can affect pages in different volumes and one page can depend on several source files.

## Why explicit dependencies matter

Without declared dependencies, the maintenance choices are poor:

1. scan the entire documentation corpus after every source change; or
2. rely on semantic guesses that can miss indirect but important pages.

Explicit dependency metadata allows the project to choose a third option:

> review exactly the pages that declared the changed contract.

This does not guarantee that the metadata is perfect.

It makes dependency quality inspectable and correctable.

## Stale detection

`scripts/stale_docs.py` compares each source-backed page against current ChrisOS HEAD.

Conceptually:

    reviewed revision R
        |
        +-- declared source A
        +-- declared source B
        |
        v
    git diff R..HEAD -- A B

If no declared source changed, the page is not marked stale merely because unrelated repository code changed.

If at least one declared source changed, the page enters the generated review queue.

This is the main mechanism that prevents a large corpus from requiring full rereads after every commit.

## Stale does not mean wrong

A stale page means:

> one of the source dependencies changed after the page's reviewed revision.

It does not mean:

> the prose is definitely incorrect.

A refactor may alter lines without changing the documented contract.

A bug fix may strengthen implementation without requiring prose changes.

A major interface change may require extensive rewriting.

The agent must inspect the actual diff before deciding.

## Unavailable baseline

Stale detection and context packing require the old `reviewed_revision` to exist in the source checkout.

If that commit cannot be resolved, the correct state is not "unchanged."

It is:

    unavailable-baseline

An unavailable baseline means the agent cannot use a normal bounded diff to prove what changed.

Possible responses include:

- fetch deeper Git history;
- inspect the full current declared source set;
- perform a fresh reconciliation;
- reset the reviewed revision only after that reconciliation.

Never advance the revision merely because the old commit is inconvenient to retrieve.

## Invalid revision queue

`stale_docs.py` separately tracks pages whose reviewed revision cannot be resolved.

This distinction matters because:

    stale
    !=
    invalid baseline

A stale page has a known old point and a known diff.

An invalid baseline lacks the historical anchor needed to construct that diff.

Maintenance reports should keep those cases separate.

## Context packs

`scripts/context_pack.py` creates a bounded directory for one page.

The pack contains:

- the target `PAGE.md`;
- declared source material;
- `DIFF.patch`;
- `META.json`;
- `DEPENDENCIES.json`;
- `INSTRUCTIONS.md`.

This package is the preferred input for a focused maintenance agent.

The goal is to make the context sufficient without copying unrelated repository areas.

## Context-pack metadata

`META.json` records fields such as:

- page path;
- page ID;
- old reviewed revision;
- source HEAD;
- declared sources;
- declared symbols;
- source hashes;
- dependency IDs;
- related IDs;
- diff status;
- packing mode for each source.

This lets an agent reason about provenance before reading prose.

A good first step is always to inspect `diff_status`.

## Full source versus symbol-centered source

Large source files can exceed a useful context budget.

The context pack therefore uses a threshold.

When a declared source is small enough, the full file is copied.

When it is large and symbols are available, `context_pack.py` extracts bounded line windows around important symbols.

The current implementation uses approximately 100 lines of context around each matched symbol and merges overlapping windows.

This reduces context while preserving implementation locality.

## When symbol-centered context is enough

Symbol extraction is usually sufficient when the documentation claim concerns a narrow function or data structure, such as:

- one initializer;
- one parser;
- one state transition;
- one error path;
- one resource lifecycle function.

If the claim depends on global file invariants, macros, tables or interactions not visible near the symbol, the agent should request the full source.

The bounded pack is an optimization, not a prohibition against reading necessary context.

## The --full escape hatch

`context_pack.py --full` forces complete declared source files into the pack.

Use it when:

- symbol windows omit a required helper;
- file-level invariants matter;
- macro definitions outside the window affect semantics;
- global tables define behavior;
- an unresolved contradiction remains after narrow inspection.

Do not use `--full` automatically for every page.

That would defeat the bounded-context architecture.

## Dependency summaries

The context pack does not recursively copy every prerequisite and related page.

Instead it records small summaries including:

- dependency ID;
- path;
- reviewed revision;
- headings.

This is intentional.

A maintenance task should not recursively explode into the full curriculum unless the changed contract genuinely requires it.

If a dependency heading shows that a specific prerequisite definition matters, read that page explicitly.

## Generated source atlas

`scripts/inventory.py` scans textual ChrisOS files and generates the source atlas.

For each indexed file it records:

- repository path;
- line count;
- byte count;
- SHA-256;
- detected includes;
- detected C-like function symbols;
- complete textual source.

The atlas is deterministic source evidence.

It is not authored architecture.

## Why the atlas reproduces complete source

Normal authored documentation should summarize and interpret.

The source atlas has a different job: exact traceability.

Its generated file pages intentionally preserve the full textual source at a known revision.

This makes it possible to inspect the source through the documentation site without pretending the generated page is a human-authored explanation.

Do not manually rewrite generated atlas pages.

Change the generator or source instead.

## Generated facts versus authored interpretation

Automation is good at facts such as:

- file exists;
- path;
- hash;
- size;
- include list;
- detected symbol position;
- manifest membership;
- word count;
- source-diff status.

Automation cannot infer every architectural meaning safely.

Authored chapters remain responsible for:

- invariants;
- ownership;
- concurrency;
- ABI meaning;
- failure semantics;
- security interpretation;
- performance implications;
- subsystem boundaries;
- evidence limitations;
- roadmap separation.

This division of labor is deliberate.

## Coverage generation

`scripts/coverage.py` measures two different things.

### Structural coverage

Does an authored page with the planned frontmatter ID exist in the language?

### Text-floor coverage

Does the page meet the editorial word floor for its type?

The second metric is a length signal only.

It does not prove technical completeness.

The current type-specific floors include:

- concept: 1800 words;
- technical-chapter: 1800;
- subsystem: 2200;
- specification: 1600;
- source-commentary: 1200;
- other authored technical pages: 900.

## Why word floors exist

Very short pages in a technical corpus often omit important dimensions such as:

- ownership;
- error paths;
- validation;
- limitations;
- performance;
- concurrency.

The floor is therefore a useful review trigger.

It must never be optimized mechanically by adding empty prose.

When a page is below its floor, expand the missing technical dimensions.

If the topic is genuinely smaller than the floor, that may indicate the page type or manifest design deserves review.

## next_work selection

`scripts/next_work.py` walks the curriculum in order and reports pages that are missing or below their type-specific depth target.

This keeps work selection deterministic.

It avoids repeatedly choosing visually prominent pages while leaving earlier thin chapters untouched.

The script reports the total remaining count after applying optional language and volume filters.

## Curriculum order versus source urgency

Curriculum order is useful for general expansion work.

Stale-source work can be more urgent.

A practical priority model is:

1. invalid reviewed revision;
2. stale page caused by changed implementation contract;
3. missing planned page;
4. below-floor page in curriculum order;
5. optional editorial refinement.

This prevents a purely editorial expansion from delaying correction of a page whose underlying source contract changed.

## Bilingual maintenance

Authored technical identities require EN and PT-BR counterparts.

When source-backed metadata changes, paired pages should remain technically equivalent.

Important paired fields include:

- `sources`;
- `depends_on`;
- `reviewed_revision`.

The prose should be idiomatic in each language, not a mechanically shortened translation.

An agent should therefore treat the bilingual pair as one technical maintenance unit even if repository commits temporarily land one language first.

## Intermediate CI behavior

The validator can fail an intermediate EN-only commit because the PT-BR pair is temporarily incomplete.

Repository workflow concurrency can also cancel earlier runs when a later commit arrives.

These states should not be mistaken for final content failure.

The meaningful validation target is the newest commit containing the complete bilingual pair.

If that final run fails, inspect the actual failure.

## Build-all pipeline

`scripts/build_all.py` runs the deterministic documentation generation and validation chain.

It includes:

- unit tests;
- diagrams;
- figures;
- source inventory;
- coverage;
- curriculum generation;
- reader navigation checks;
- stale detection;
- documentation validation;
- editorial-style checks;
- source map generation.

Hosted CI adds additional checks and static-site publication stages.

A page is not fully published merely because Markdown was committed.

## Validation before revision bump

A source-backed page should move its `reviewed_revision` only after reconciliation.

Correct sequence:

1. inspect page metadata;
2. inspect source diff;
3. inspect current source;
4. decide whether prose changes;
5. verify tests/specifications relevant to the claim;
6. update page;
7. update reviewed revision;
8. run documentation validation;
9. verify final bilingual workflow.

Blindly bumping the SHA destroys stale-detection value.

## Source hashes and caching

The context pack records SHA-256 for declared source files.

Git itself also provides content identity.

These identities allow maintenance systems to reuse analysis for unchanged source rather than rereading it.

A long-term cache can key technical source summaries by content hash.

If a file's content identity is unchanged, re-analysis should normally be unnecessary.

## Token-cost model

Let:

- (D) = total documentation size;
- (S) = total source size;
- (k) = number of declared source dependencies for the target page;
- (d) = size of the relevant source diff.

A naive workflow tends toward reading a large fraction of (D + S).

The low-context workflow aims for work proportional to:

    page + k bounded sources + d + small dependency metadata

As the corpus grows, this difference becomes increasingly important.

## Avoiding context explosion

Common causes of unnecessary context growth include:

- recursively reading every related page;
- copying every include transitively;
- requesting complete large files before checking symbols;
- scanning the full repository for terms already represented in frontmatter;
- regenerating unaffected prose.

The maintenance tools are designed to prevent these patterns.

An agent should preserve that discipline.

## When semantic search is appropriate

Explicit metadata cannot solve every case.

Semantic or broader search is justified when:

- a page clearly depends on implementation not declared in `sources`;
- a source move broke metadata;
- a new subsystem has no established documentation mapping;
- the diff reveals a previously hidden cross-subsystem dependency;
- a concept needs external primary references;
- the current frontmatter is known to be incomplete.

When broader discovery identifies a durable dependency, add it to metadata so future updates become cheaper.

## Failure mode: stale metadata

The most dangerous maintenance failure is often not stale prose but stale dependency metadata.

If a chapter depends on file B but declares only file A, changes to B will never place the page in the review queue.

Reviewers should therefore ask during substantive reconciliation:

> Are these still the smallest complete source dependencies for the claims on this page?

Metadata is part of the technical contract.

## Failure mode: oversized source sets

The opposite failure is declaring an entire subsystem directory through many unrelated paths.

That causes every minor code change to mark the page stale and makes context packs unnecessarily large.

Prefer the smallest source set that reconstructs the documented mechanism.

Use multiple focused pages rather than one giant page when contracts are independent.

## Failure mode: generated/authored ownership confusion

Generated files should not be edited as if they were source prose.

Examples include:

- coverage reports;
- review queues;
- source atlas;
- generated source map;
- generated learning path.

If a generated result is wrong, fix:

- source metadata;
- manifest/curriculum data;
- generator logic;
- underlying ChrisOS source.

Manual patching will be overwritten on the next build.

## Agent decision record

For nontrivial maintenance, an agent should be able to state:

- why the page was selected;
- which revision changed;
- which declared source changed;
- what contract difference was observed;
- whether prose changed;
- which limitations remain;
- which validation passed.

This record can be concise.

Its purpose is traceability, not narration of hidden reasoning.

## Review queue zero is not finality

A generated queue with zero stale pages means:

> every source-backed page is reconciled against its declared dependencies at the current source revision.

It does not mean:

- every dependency declaration is perfect;
- every page is above depth floor;
- every technical claim is complete;
- hardware support is fully validated;
- no editorial improvements remain.

The maintenance metrics are independent.

## Recommended maintenance loop

A normal source-driven loop is:

    update ChrisOS source
        |
        v
    run build_all
        |
        v
    inspect review queue
        |
        v
    choose one stale page
        |
        v
    build context pack
        |
        v
    reconcile against diff/source
        |
        v
    update bilingual pair
        |
        v
    run validation
        |
        v
    repeat until stale queue is empty

After the stale queue reaches zero, use `next_work.py` for thin or missing curriculum work.

## Recommended expansion loop

For corpus-depth work:

1. run `next_work.py`;
2. select the first useful thin page;
3. inspect its current frontmatter and body;
4. reconcile declared sources before expanding;
5. add missing technical dimensions, not filler;
6. update both languages;
7. measure with the same canonical word counter;
8. run the full documentation pipeline;
9. continue in curriculum order.

This prevents word-count work from drifting away from source truth.

## Cost-control invariants

The maintenance architecture follows several practical rules:

1. reuse unchanged source analysis by content identity;
2. work from Git diffs whenever a valid baseline exists;
3. do not regenerate unaffected authored prose;
4. generate indexes and source facts deterministically;
5. read full large files only when bounded context is insufficient;
6. keep dependency metadata explicit;
7. validate the bilingual pair as one technical unit;
8. distinguish structural coverage, text depth and source freshness.

These rules let the site grow while ordinary maintenance remains bounded.

## Revision note

This chapter describes the current low-context documentation tooling in `chrisos_site` and uses ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56` as the reviewed project baseline.

Because the page documents the documentation-maintenance system rather than a ChrisOS implementation subsystem, it intentionally declares `sources: []`. The relevant tooling is owned by the documentation repository and is validated by its own CI pipeline.
