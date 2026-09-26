---
id: volume-05-memory
lang: en
type: volume-index
volume: 05-memory
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
---

# Memory systems

<div class="abstract">Physical memory allocation, virtual addressing, four-level paging, CR3, TLBs, heaps, ownership and multiprocessor invalidation.</div>

## Scope

This volume defines the terminology and relationships required before implementation detail. General concepts remain separate from ChrisOS-specific decisions; when a chapter crosses into implementation, its source revision and relevant files are declared in frontmatter.

## Core chapters

- Physical memory
- Virtual memory
- Heap and ownership
- TLB shootdown

## Reading rule

Lower-layer details need not be memorized, but terms used by higher layers are defined before their first technical use. Diagrams show flow and responsibility; tables record contracts, layouts and states.
