---
id: architecture-history
lang: en
type: technical-chapter
volume: 16-history
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - docs/STABILITY_AUDIT.md
  - docs/NATIVE_TOOLCHAIN_AUDIT.md
  - docs/CURRENT_GRAPHICS_AUDIT.md
  - docs/chrisvm/architecture.md
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

The ChrisOS repository contains audits tied to older campaign branches as well as current status documents. An older audit may say VirGL is unsupported or KCC accepts only a tiny subset while newer source implements significantly more.

The correct interpretation is not to delete the historical record. It is to label its revision and point current documentation at newer evidence.

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

Early audits documented a very limited KCC/ChrisAsm/ChrisLd sketch. Current KCC status shows compilation of all `kernel/metal` units under the host gate while still recording major blockers to a complete kernel.

Both documents are useful when ordered chronologically.

## Example: ChrisVM

ChrisVM/ChrisCPU introduces a new architectural branch absent from earlier OS-only snapshots. Documentation of emulation must therefore use main-branch source rather than assuming the previous site snapshot remains representative.

## Rule

Current chapters state current behavior. Historical chapters preserve former designs. A current claim should never cite an old audit without checking whether the relevant source has changed.
