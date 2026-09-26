---
id: volume-04-kernel
lang: en
type: volume-index
volume: 04-kernel
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
---

# Kernel architecture

<div class="abstract">Privilege boundaries, monolithic modular organization, exceptions, interrupts, SMP, processes, ELF user execution and system calls.</div>

## Scope

This volume defines the terminology and relationships required before implementation detail. General concepts remain separate from ChrisOS-specific decisions; when a chapter crosses into implementation, its source revision and relevant files are declared in frontmatter.

## Core chapters

- Kernel model and trust boundaries
- Interrupts and SMP
- Processes and system calls

## Reading rule

Lower-layer details need not be memorized, but terms used by higher layers are defined before their first technical use. Diagrams show flow and responsibility; tables record contracts, layouts and states.
