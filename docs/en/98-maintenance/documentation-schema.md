---
id: documentation-schema
lang: en
type: technical-chapter
volume: 98-maintenance
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources: []
symbols: []
depends_on:
  - agent-workflow
related:
  - source-policy
  - contribution-workflow
---

# Documentation schema and templates

## Purpose

This chapter defines the structural contract for authored ChrisOS documentation.

The schema is not merely formatting convention. It drives:

- bilingual identity;
- curriculum placement;
- dependency validation;
- source-impact analysis;
- stale detection;
- coverage accounting;
- generated navigation;
- context-pack creation;
- static-site routes;
- review queues.

A page that looks correct in Markdown but violates this metadata model can break the documentation system or silently disappear from coverage.

## Canonical identity is the frontmatter id

The most important rule is:

> A chapter's canonical identity is its frontmatter `id`, not its filename.

For example, a page can live at:

    docs/en/17-developer-guide/linux-development-environment.md

while its canonical chapter ID is:

    development-environment-linux

Coverage, curriculum and bilingual pairing operate on the ID.

The filename controls the route and repository location; it does not define the chapter identity.

This distinction is deliberate and must be preserved.

## Why filename-based counting is wrong

A filename-based inventory can produce false "missing" chapters when a route name differs from the manifest ID.

The correct structural check is:

    manifest chapter id
          |
          v
    frontmatter id in EN
          +
    frontmatter id in PT-BR

If both authored pages exist with the same planned ID, the chapter is structurally present even when neither filename equals the ID.

This rule prevents accidental duplicate pages created only to satisfy a path-based count.

## Frontmatter boundary

Authored Markdown pages begin with YAML frontmatter:

    ---
    id: example-chapter
    lang: en
    type: technical-chapter
    volume: 04-kernel
    status: maintained
    reviewed_revision: <git-sha>
    sources:
      - kernel/example.c
    symbols:
      - example_init
    depends_on:
      - prerequisite-id
    related:
      - adjacent-topic
    ---

The body begins after the closing delimiter.

The tooling reads frontmatter deterministically; metadata is not inferred from prose headings.

## Required fields

`validate_docs.py` requires:

- `id`;
- `lang`;
- `type`.

Pages missing any required field fail validation.

Other fields are required by policy for substantive implementation pages even when the generic parser does not require them syntactically.

## id

The `id` is the stable semantic identity of a chapter.

Rules:

- use a short lowercase kebab-case identifier;
- keep it stable across file moves;
- use the same ID in EN and PT-BR;
- do not reuse an ID for a different concept;
- do not encode language into the ID;
- do not change an ID only to improve a URL.

An ID change is a curriculum/schema migration, not a cosmetic edit.

## lang

Authored trees use:

    en
    pt-br

The directory also carries language identity.

`frontmatter.py` can normalize a missing `lang` from the path for compatibility, but authored pages should still declare it explicitly.

Explicit metadata makes review and standalone processing clearer.

## type

The `type` classifies the page for coverage and generation behavior.

Common authored types include:

- `concept`;
- `technical-chapter`;
- `subsystem`;
- `specification`;
- `source-commentary`;
- `guide`;
- `volume-index`;
- `landing`.

Generated pages use types beginning with `generated`.

Type selection affects editorial depth accounting.

It should describe the actual role of the page rather than being chosen to obtain an easier word target.

## volume

The `volume` field records the physical/semantic volume.

Example:

    volume: 08-graphics

For planned technical pages it should match the manifest organization.

Volume indexes have their own index identity and are excluded from normal chapter coverage.

## status

The corpus commonly uses:

    status: maintained

Generated pages typically use:

    status: generated

Status should describe lifecycle state, not technical correctness.

A maintained page can still require review because its declared sources changed.

## reviewed_revision

`reviewed_revision` records the ChrisOS source commit against which an implementation-facing page was reconciled.

It must match between EN and PT-BR for the same ID.

The field should not be advanced merely to silence stale detection.

Pages with no ChrisOS source dependency may still record the project baseline used while authoring, while declaring `sources: []`.

## sources

`sources` is a YAML list of paths relative to the ChrisOS source repository.

Example:

    sources:
      - kernel/mm/pmm.c
      - kernel/mm/vmm.c

`validate_docs.py` checks these paths against the source checkout supplied to the build.

Use an empty list when the page does not document ChrisOS implementation source.

Do not put documentation-repository files in this field, because the field is validated against the ChrisOS source tree.

## symbols

`symbols` contains important source identifiers used by context-pack tooling.

Example:

    symbols:
      - pmm_alloc
      - vmm_map_page

Symbols are hints, not independent dependencies.

A symbol without a declared source path does not create a source dependency.

## depends_on

`depends_on` defines prerequisite edges in the learning DAG.

Example:

    depends_on:
      - paging
      - physical-memory-manager

A prerequisite means the target chapter assumes concepts or contracts defined by the dependency.

Rules:

- every prerequisite ID must be planned in the manifest;
- dependencies must not form cycles;
- EN/PT-BR metadata must match;
- do not use reciprocal dependencies merely because two subsystems interact.

A prerequisite is directional.

## related

`related` records useful non-prerequisite relationships.

Examples:

- implementation/specification pair;
- adjacent subsystem;
- validation chapter;
- historical chapter;
- alternative backend.

`related` may point forward because it does not participate in the prerequisite DAG.

It should not be used to hide a real prerequisite.

## Bilingual identity invariant

For authored non-generated pages, `validate_docs.py` requires every ID to have both:

    en
    pt-br

A single-language authored page fails the pipeline.

This is why intermediate commits that add only EN can fail before the PT-BR pair is committed.

The final bilingual commit is the meaningful validation target.

## Duplicate identity is forbidden

Within one language, two pages cannot share the same `id`.

The validator reports:

    duplicate id/lang

This means creating:

    docs/en/17-developer-guide/index.md
    docs/en/17-developer-guide/developer-guide.md

with the same `id: developer-guide` would be invalid.

A missing-by-filename report must never be "fixed" by creating a duplicate canonical identity.

## Bilingual metadata equality

For a paired ID, the validator requires exact equality of:

- `sources`;
- `depends_on`;
- `reviewed_revision`.

This makes the two language trees technically equivalent at the metadata level.

The prose can be idiomatic in each language, but the source scope and prerequisite graph must not diverge.

## Manifest contract

`data/documentation-manifest.yml` defines the planned corpus.

Each planned chapter has:

- ID;
- title;
- volume;
- priority.

The manifest answers:

> What chapters are supposed to exist?

It does not determine file paths.

Coverage joins the manifest with authored pages by frontmatter ID.

## Curriculum contract

`data/curriculum.yml` assigns every planned manifest ID exactly once to the learning path.

`curriculum.py` enforces an exact partition:

- no planned ID omitted;
- no unknown ID added;
- no duplicate curriculum assignment.

This keeps navigation and prerequisites tied to the same semantic identities used by coverage.

## Physical path versus semantic identity

The documentation system deliberately separates:

    physical path
    semantic ID
    curriculum position

These can change independently within constraints.

A page may move to a better directory without changing its ID.

A chapter may move to a different curriculum module without changing its file path.

This reduces unnecessary link/identity churn.

## Route stability

Although ID is canonical for the data model, file path still matters for URLs.

Moving an authored file changes its static-site route unless redirect handling exists.

Therefore:

- do not rename files casually;
- prefer stable routes;
- change ID only for semantic reasons;
- treat path moves and ID migrations as separate operations.

## Coverage model

`coverage.py` loads every authored page and builds a map keyed by:

    (id, lang)

It excludes:

- generated types;
- `volume-index`;
- `landing`.

Then it joins that map against the manifest.

Structural presence is therefore based on canonical ID, not filename.

## Structural coverage

For each language:

[
C_s = rac{N_{present}}{N_{planned}}
]

where:

- (N_{present}) is the number of manifest IDs with an authored page;
- (N_{planned}) is the number of manifest chapters.

Structural coverage answers only:

> Does an authored page with this canonical ID exist?

It does not establish technical completeness.

## Editorial depth floors

`coverage.py` also computes a word-floor signal.

Current type-specific targets are:

| Type | Minimum words |
|---|---:|
| `concept` | 1800 |
| `technical-chapter` | 1800 |
| `subsystem` | 2200 |
| `specification` | 1600 |
| `source-commentary` | 1200 |
| other authored technical page | 900 |

These floors are guardrails.

They are not evidence that a chapter is correct, complete or well reviewed.

## Why word count is not completion

A 3,000-word chapter can still be technically incomplete if it omits:

- ownership;
- concurrency;
- error paths;
- source evidence;
- validation;
- limitations.

A 1,500-word specification can also be complete for a genuinely small contract.

The floor detects suspiciously short pages; it does not replace technical review.

## Generated pages

Generated pages are build outputs, not authored sources of truth.

Examples include:

- coverage;
- learning path;
- review queue;
- source atlas;
- generated metadata indexes.

Do not manually edit generated files when a script/data source owns them.

Fix the generator or input data instead.

## Source atlas exception

The generated source atlas is intentionally a deterministic mirror/index.

It may reproduce source text completely.

It is not subject to the same authored-prose role as technical chapters.

The atlas must not be manually summarized to reduce size because exact source reproduction is part of its purpose.

## Frontmatter parser behavior

`frontmatter.py`:

1. verifies the page starts with a YAML delimiter;
2. finds the closing delimiter;
3. parses YAML;
4. normalizes language from path if omitted;
5. returns metadata and body separately.

Malformed or absent frontmatter eventually fails higher-level validation when required fields are missing.

## Page discovery

`iter_pages()` recursively discovers Markdown under `docs/`.

It skips generated source-atlas files under:

    /99-source-atlas/generated/

because those files are managed separately and can be extremely numerous.

Other generated pages still participate in validation according to their generated type.

## Validation contract

`validate_docs.py` performs several important checks:

- required metadata exists;
- duplicate `id/lang` pairs do not exist;
- declared ChrisOS source paths exist;
- authored pages do not contain placeholder tokens;
- bilingual authored identities exist;
- paired metadata matches for key technical fields.

Validation errors stop publication.

## Placeholder protection

Authored pages cannot contain unresolved tokens such as:

- `TODO`;
- `TBD`;
- `REPLACE_ID`;
- `REPLACE_SOURCE`;
- `REPLACE_REVISION`;
- `lorem ipsum`.

This prevents scaffolding markers from being published as finished prose.

If future work must be documented, write it explicitly as roadmap/limitation prose instead of leaving a placeholder token.

## Short-body warning

The validator warns when an authored non-index page has a very small body.

Coverage performs the more precise word-floor classification.

A warning does not always fail CI, but it signals that the page may be too shallow for the role it claims.

## Curriculum DAG

Prerequisites form a directed acyclic graph.

For each page:

    depends_on:
      - prerequisite-a
      - prerequisite-b

means both prerequisites conceptually precede the page.

`curriculum.py` traverses dependencies and rejects cycles.

A cycle means the corpus has not defined a usable learning order for those concepts.

## Dependency semantics

Use `depends_on` when a reader genuinely needs the referenced concept first.

Use `related` when the connection is useful but not prerequisite.

Bad pattern:

    A depends_on B
    B depends_on A

because they interact.

Better:

    A depends_on foundational-C
    B depends_on foundational-C
    A related B
    B related A

when neither logically precedes the other.

## Source-impact graph

`source_map.py` creates a deterministic reverse graph from `sources`.

For each authored page it records:

- ID;
- language;
- path;
- type;
- reviewed revision;
- sources;
- symbols;
- dependencies;
- related pages.

Then it builds:

    source path -> affected documentation paths

This is the basis for low-context maintenance.

## Stale detection schema

A page participates in source-diff stale detection when it has:

- a non-empty `sources` list;
- a `reviewed_revision`.

`stale_docs.py` computes changed paths between that revision and source HEAD.

The generated review queue lists only pages whose declared source dependencies changed.

## Context-pack schema

`context_pack.py` uses frontmatter to build a bounded maintenance package.

It can include:

- target page;
- full or symbol-centered declared source;
- Git diff;
- source hashes;
- dependency headings;
- metadata;
- instructions.

This is why accurate frontmatter materially reduces maintenance cost.

Bad metadata creates bad context.

## File templates

A new substantive implementation chapter should normally begin from this model:

    ---
    id: stable-id
    lang: en
    type: technical-chapter
    volume: NN-volume
    status: maintained
    reviewed_revision: <source-commit>
    sources:
      - real/source/path.c
    symbols:
      - important_symbol
    depends_on:
      - prerequisite-id
    related:
      - adjacent-id
    ---

The PT-BR page uses the same technical metadata except:

    lang: pt-br

The body should be independently well written in Brazilian Portuguese, not mechanically shortened.

## Concept template

A theory-first page may use:

    type: concept
    sources: []

when it does not make ChrisOS implementation claims.

If it later crosses into implementation, declare the relevant ChrisOS paths.

A concept page still needs evidence and bibliography for external technical claims even when `sources` is empty.

## Specification template

A project-owned contract can use:

    type: specification

and should explicitly define:

- scope/version;
- binary or logical layout;
- invariants;
- state transitions;
- validity constraints;
- error behavior;
- compatibility;
- implementation bindings;
- test evidence.

Specifications should distinguish normative project contract from implementation notes.

## Guide template

Operational developer documentation can use:

    type: guide

A guide prioritizes reproducible commands, environment assumptions, failure classification and workflow.

It should not pretend that procedural instructions are an architecture specification.

## Volume-index template

A volume index uses:

    type: volume-index

Its purpose is navigation and scope.

It is excluded from planned chapter coverage and may be concise.

A volume index should not carry a planned chapter ID unless that is intentionally the same canonical authored guide and tooling behavior has been reviewed carefully.

In the existing developer guide, the index itself is the planned `developer-guide` page because its type is `guide`, not `volume-index`.

## Landing template

A landing page uses:

    type: landing

It is excluded from ordinary planned chapter depth/coverage accounting.

Landing pages organize entry points; they are not substitutes for technical chapters.

## ID migration procedure

Changing an existing ID requires coordinated edits.

At minimum:

1. update the manifest;
2. update the curriculum;
3. update EN/PT-BR frontmatter;
4. update `depends_on` references;
5. update `related` references where appropriate;
6. update generated-data inputs;
7. run curriculum validation;
8. run the full documentation build;
9. consider route compatibility separately.

Do not perform partial ID migrations.

## File move procedure

Moving a file without changing its ID is simpler, but still affects links/routes.

Steps:

1. move both language files coherently;
2. preserve IDs;
3. update authored relative links;
4. verify generated navigation;
5. run reader-navigation tests;
6. run `mkdocs build --strict`;
7. consider redirects if public URLs changed.

## Adding a planned chapter

To introduce a genuinely new planned chapter:

1. add a stable ID to `documentation-manifest.yml`;
2. assign it exactly once in `curriculum.yml`;
3. decide prerequisites;
4. create EN and PT-BR authored pages;
5. use equivalent technical metadata;
6. add real source dependencies when implementation-facing;
7. run the complete publication pipeline.

A one-language intermediate commit can fail by design.

## Removing a planned chapter

Removal is a schema change.

Before removing:

- verify it is genuinely obsolete rather than merely incomplete;
- update manifest and curriculum;
- remove/redirect dependencies;
- preserve historical material when appropriate;
- consider URL compatibility;
- remove both language versions coherently.

Coverage should never be improved by deleting planned work merely because it is unfinished.

## Generated versus authored ownership

Every file should have a clear owner.

| File class | Owner |
|---|---|
| technical prose | human/agent authored |
| manifest/curriculum | curated data |
| coverage/review queue | generator |
| source atlas | generator |
| static site output | build |
| source code | ChrisOS repository |

Editing the wrong layer creates drift.

## Publication pipeline

The core deterministic publication sequence is:

    python -m unittest discover -s tests
    python scripts/build_all.py --source .source --docs docs
    mkdocs build --strict

The hosted workflow adds additional validators, SEO checks, reader smoke tests and Pages artifact creation.

A final content commit should be considered validated only when the complete pipeline for that commit succeeds.

## Concurrency and intermediate commits

The repository CI can cancel or fail intermediate commits while a bilingual pair is being published.

Common sequence:

    EN commit
      -> validator sees missing PT-BR pair
      -> fails

    PT-BR commit
      -> pair complete
      -> final workflow succeeds

The final paired commit is the one that establishes publishable state.

Intermediate failure caused solely by an incomplete bilingual pair is not a content regression.

## Schema anti-patterns

Avoid:

- counting filenames instead of IDs;
- creating duplicate IDs to satisfy a path-based report;
- changing IDs for aesthetic URLs;
- putting documentation-repository scripts in ChrisOS `sources`;
- bumping reviewed revisions without reconciliation;
- using `related` to replace a real prerequisite;
- leaving generated files manually edited;
- making PT-BR shorter in technical scope;
- marking roadmap behavior as implemented;
- using word count as proof of completeness.

## Canonical chapter-presence algorithm

A correct structural inventory is equivalent to:

    planned = IDs from documentation-manifest.yml

    authored[(id, lang)] =
        every non-generated,
        non-volume-index,
        non-landing page
        indexed by frontmatter id

    present(id) =
        authored[(id, en)] exists
        and
        authored[(id, pt-br)] exists

Filename matching is not part of this algorithm.

This is the rule that should be used in audits, dashboards and completion reports.

## Schema invariant

The central invariant is:

> Semantic identity, language pairing, curriculum placement, source dependencies and revision metadata are explicit data; none should be inferred from filename similarity or prose.

This is what allows a corpus of hundreds of chapters to remain machine-verifiable.

## Revision note

This schema chapter reflects the documentation tooling and ChrisOS baseline used by the corpus at revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

Because the page documents documentation-repository behavior rather than ChrisOS implementation internals, it intentionally declares `sources: []`.
