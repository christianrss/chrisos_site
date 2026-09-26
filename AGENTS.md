# AGENTS.md — ChrisOS Documentation

This file is the operational contract for any AI agent or human automation modifying this repository.

## Primary rule

**Do not scan the entire ChrisOS repository for a normal page update.**

The unit of work is one page or one tightly related group of pages.

## Required workflow

1. Read the target page frontmatter.
2. Read only the declared `sources`, `symbols`, `depends_on` and `related` entries.
3. Inspect the Git diff from `reviewed_revision` to the current ChrisOS `main` branch for those sources.
4. Expand context only when a dependency cannot be resolved.
5. Modify only sections affected by evidence.
6. Run deterministic validation.
7. Update `reviewed_revision` only after reconciling the page with source.
8. Never edit generated files under `docs/*/99-source-atlas/generated/`.
9. Never manually maintain current commit hashes, repository inventories or stale queues.
10. Never convert roadmap intent into an implementation claim.

## Content model

Every substantive technical page must distinguish, when applicable:

- **Theory** — general computing mechanism.
- **Architecture** — intended ChrisOS design and contracts.
- **Implementation** — what current `main` source actually does.
- **Validation** — tests or gates that establish observed behavior.
- **Limitations** — missing or unproven behavior.
- **Roadmap** — future work, never phrased as current capability.

## Style

- Formal technical prose.
- No exercises, quizzes or conversational teaching phrases.
- Define prerequisites before using them.
- Explain why a mechanism exists, how it works, and how ChrisOS implements it.
- Explain important code by invariants, ownership, dataflow, concurrency and failure behavior; do not merely paraphrase individual lines.
- Use diagrams and tables when they reduce ambiguity.
- Prefer primary specifications for external technology.

## Frontmatter

Typical page:

```yaml
---
id: virtual-memory
lang: en
type: concept
volume: "05-memory"
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/mm.c
  - kernel/metal/mm.h
  - kernel/metal/pmm.c
symbols:
  - mm_map_cr3
  - mm_switch
depends_on:
  - physical-memory
  - x86-64-addressing
related:
  - tlb-shootdown
  - process-address-spaces
---
```

## Context packs

Generate before asking an agent to update a page:

```bash
python scripts/context_pack.py docs/en/05-memory/virtual-memory.md --source .source
```

## Generated source atlas

`scripts/inventory.py` scans the ChrisOS checkout and generates repository inventory, per-file source-reference pages, includes, C-like function definitions, hashes, line counts and source revision.

Generated pages are factual indexes, not architectural interpretation.

## Translation

English and pt-BR pages are independent authored pages with the same `id` plus language. Technical content must remain equivalent. Do not reduce the pt-BR page to a summary.

## Evidence priority

For current implementation claims:

1. Current source on ChrisOS `main`.
2. Reproducible tests/gates on the same revision.
3. Current specifications maintained in source.
4. Historical audit documents.
5. README prose.
6. Roadmap documents.
