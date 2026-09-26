---
id: volume-06-storage
lang: en
type: volume-index
volume: 06-storage
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
---

# Storage and filesystems

<div class="abstract">Block devices, ATA/AHCI/NVMe/VirtIO concepts, sectors, DMA, filesystem structures, journaling, ChrisFS and installation.</div>

## Scope

This volume defines the terminology and relationships required before implementation detail. General concepts remain separate from ChrisOS-specific decisions; when a chapter crosses into implementation, its source revision and relevant files are declared in frontmatter.

## Core chapters

- Block storage stack
- ChrisFS

## Reading rule

Lower-layer details need not be memorized, but terms used by higher layers are defined before their first technical use. Diagrams show flow and responsibility; tables record contracts, layouts and states.
