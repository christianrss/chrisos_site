---
id: volume-03-boot
lang: en
type: volume-index
volume: 03-boot
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
---

# Boot and executable formats

<div class="abstract">Power-on state, firmware, UEFI, Limine, ELF loading, linker layout and the transition into the ChrisOS entry point.</div>

## Scope

This volume defines the terminology and relationships required before implementation detail. General concepts remain separate from ChrisOS-specific decisions; when a chapter crosses into implementation, its source revision and relevant files are declared in frontmatter.

## Core chapters

- Power-on to kstart
- ELF and kernel linking

## Reading rule

Lower-layer details need not be memorized, but terms used by higher layers are defined before their first technical use. Diagrams show flow and responsibility; tables record contracts, layouts and states.
