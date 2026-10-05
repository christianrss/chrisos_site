---
id: architecture-history
lang: en
type: technical-chapter
volume: 16-history
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - README.md
  - docs/README.md
symbols: []
depends_on: []
related:
  - validation-evidence
---

# Architecture history and superseded evidence

## Why history belongs in technical documentation

Experimental systems change contracts rapidly. A statement can be accurate for one commit and false a week later without either document being dishonest.

Architecture history records when a design existed, why it changed and which newer evidence supersedes it.

## Audit documents as snapshots

The source repository no longer carries the old technical audit corpus. On revision 92fb561574bd929522ea005b9fd433138bea3236 those duplicated technical documents were deliberately retired so that chrisos_site is the canonical documentation surface. Historical audit snapshots remain recoverable from Git history, while current claims must be reconstructed from current source, executable gates and revision-bound documentation here.

The correct interpretation is to preserve historical evidence through version control without keeping stale copies in the live source tree. A historical statement must name the revision or interval in which it was true; current chapters must point at current implementation evidence.

## Change categories

Architectural changes can be classified:

- **extension** — existing contract gains capability;
- **replacement** — one mechanism supersedes another;
- **refactoring** — responsibility moves without intended semantic change;
- **hardening** — failure/ownership/concurrency contracts become stricter;
- **evidence upgrade** — implementation unchanged but a stronger gate proves it.

This vocabulary prevents every commit from being described as a new architecture.

## Example: graphics

The project moved from software rendering and experimental VirtIO scanout toward a reusable Gfx3D/VirGL backend and programmable shader pipeline. Mine Chris remaining on the software path is an important boundary during that transition.

## Example: native toolchain

Early revisions contained a much smaller KCC/ChrisAsm/ChrisLd surface. The current compiler sources and executable gates provide the evidence for present behavior; older audit prose is historical evidence only when recovered at its original Git revision.

The chronology is therefore carried by Git history plus revision-bound site pages, not by duplicated status files in the source repository.

## Example: ChrisVM

ChrisVM/ChrisCPU introduces a new architectural branch absent from earlier OS-only snapshots. Documentation of emulation must therefore use main-branch source rather than assuming the previous site snapshot remains representative.

## Rule

Current chapters state current behavior. Historical chapters preserve former designs. A current claim should never cite an old audit without checking whether the relevant source has changed.
