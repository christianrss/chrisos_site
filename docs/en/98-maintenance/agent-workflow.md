---
id: agent-workflow
lang: en
type: technical-chapter
volume: 98-maintenance
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on: []
related:
  - validation-evidence
---

# Low-context documentation maintenance

## Objective

The documentation may grow to hundreds or thousands of pages while an agent should normally read only one page and a small source set.

This is achieved by storing dependency metadata in each page and generating repository facts deterministically.

## Frontmatter dependency graph

`sources` lists concrete ChrisOS files. `symbols` narrows important identifiers. `depends_on` and `related` link conceptual pages.

A source change can therefore be mapped to affected documents without semantic search across the entire corpus.

## Stale detection

`stale_docs.py` compares each page's `reviewed_revision` to current ChrisOS HEAD for only its declared source paths.

If none changed, the page does not require source reconciliation merely because unrelated code changed.

If one changed, the generated review queue lists the page and changed files.

## Context packs

`context_pack.py` copies:

- target page;
- declared source files;
- Git diff since reviewed revision;
- metadata;
- concise instructions.

This pack is the normal input to an AI agent.

## Generated facts

`inventory.py` produces file references, hashes, line counts, includes and detected C-like symbols. An agent should not spend tokens rewriting this information.

The generated atlas is rebuilt from the source checkout during GitHub Actions.

## Authored interpretation

Automation cannot infer all architectural meaning from syntax. Authored pages remain responsible for:

- invariants;
- ownership;
- concurrency;
- rationale;
- failure modes;
- subsystem boundaries;
- validation interpretation.

## Cost control

The practical token budget is reduced by four rules:

1. cache unchanged source by Git content identity;
2. work from Git diffs;
3. never regenerate unaffected prose;
4. generate indexes and file facts without a model.

The site can therefore become much larger than the context required for any ordinary update.
