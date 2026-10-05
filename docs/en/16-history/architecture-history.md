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
  - graphics-history
  - toolchain-history
  - chrisvm-history
  - source-policy
---

# Architecture history and superseded evidence

## Purpose

Architecture history records **when an architectural statement was true**, why it changed and which later evidence superseded it.

ChrisOS changes quickly enough that an old statement can be perfectly accurate for its original revision and still be wrong for current `main`.

The correct response is not to erase history.

It is to bind every historical claim to a revision or interval and to keep current implementation claims anchored to current source.

## Current evidence rule

For present behavior, use current ChrisOS source and reproducible gates.

For historical behavior, use:

- Git commits;
- commit diffs;
- revision-bound audit records;
- old test results with known revision;
- archived documentation at that revision.

An old audit never overrides newer source.

A new source file also does not invalidate the historical fact that the subsystem did not exist in an earlier commit.

History and current documentation answer different questions.

## Architecture is not the same as repository shape

A file move can look large in Git while changing no intended behavior.

Conversely, a small change to ownership, synchronization or ABI may be architecturally important.

History should therefore classify changes by semantic effect rather than by line count.

Useful categories are:

- **extension** — an existing contract gains capability;
- **replacement** — a new mechanism supersedes an older one;
- **refactoring** — responsibility moves without intended behavior change;
- **hardening** — failure, synchronization or ownership rules become stricter;
- **evidence upgrade** — behavior remains but stronger validation is added;
- **boundary extraction** — an experiment becomes a reusable subsystem/API;
- **canonicalization** — authority moves from duplicated prose to one maintained source.

These categories help avoid describing every commit as a new architecture.

## Revision snapshots

A useful historical snapshot contains at least:

| Field | Purpose |
|---|---|
| commit | exact implementation identity |
| date | ordering |
| subsystem | affected architecture |
| prior contract | what existed before |
| new contract | semantic change |
| evidence | tests/gates available at the time |
| superseded by | later revision if applicable |

This makes history auditable rather than narrative-only.

## Early desktop and subsystem consolidation

On 18 September 2026, the current `kernel/gfx` and `kernel/wm` structure became recognizable through a reorganization that also introduced the Gfx2D layer.

That event is best classified as a mixture of refactoring and extension.

Some graphics/desktop files already existed and were moved into clearer ownership boundaries.

The important architectural change was not "graphics suddenly appeared"; it was that low-level graphics and window-manager responsibilities became more explicit.

The dedicated graphics history chapter preserves the detailed sequence.

## Software 3D as an independent execution path

By 20 September, ChrisOS had expanded into a substantial software-rendered 3D path with triangle rasterization, z-buffering, texturing, mesh and voxel support.

This is important historically because later GPU work did not replace an empty space.

VirGL arrived after a CPU rendering architecture already existed.

That earlier software path later became:

- a fallback;
- a host-testable reference;
- a useful semantic comparison path for shader work.

A simplistic timeline saying "2D then GPU 3D" would therefore erase a major intermediate architecture.

## Integration pressure changes architecture

Large applications and workloads can force architecture to become explicit even when they do not introduce a new subsystem.

The Doom port, desktop applications and Mine Chris increased pressure on:

- framebuffer presentation;
- input;
- resource ownership;
- process/application lifetime;
- filesystem access;
- compiler/runtime behavior.

Such commits are often best classified as integration milestones.

They reveal contracts that small unit-like demos can avoid.

## 24 September 2026 — stability becomes a named architecture concern

A major cluster on 24 September made reliability mechanisms explicit.

The stability campaign included changes around:

- ChrisFS serialization/locking;
- graphics context ownership;
- driver timeout behavior;
- QEMU gates;
- parser fuzzing;
- install/SMP behavior;
- TLB shootdown acknowledgement.

One important correction changed QEMU validation so a timeout was no longer treated as an unconditional pass.

This is an **evidence upgrade** and a reliability architecture change at the same time.

The kernel may execute the same successful boot path, but the project becomes less likely to certify a broken run.

## Failure behavior is architecture

Changes such as:

- returning storage timeout instead of waiting forever;
- fencing a CPU before reusing TLB-sensitive frames;
- preserving volatile MMIO accesses in KCC output;
- serializing ChrisFS access with explicit locking

are not merely bug fixes.

They define what the system does when assumptions fail.

An architecture history that records only new features misses some of the most important maturity transitions.

## TLB ownership hardening

The 24–25 September sequence around TLB shootdown is an example.

The project evolved from basic invalidation coordination toward stronger acknowledgement/fencing before frames could be safely reused.

The semantic invariant is more important than the individual implementation steps:

> a physical frame must not be reused while another CPU can still access the old translation.

This kind of change belongs in architectural history because it changes the ownership/reclamation contract between CPUs.

## Developer-tool boundary matures

On 24 September the developer-tool campaign added or hardened:

- editor path bounds;
- text model behavior;
- debug sessions;
- stepping;
- host gates.

At the same time, the native toolchain audit made KCC fail closed outside its supported subset.

These changes are related by a general maturity principle:

> unsupported or invalid development operations should fail explicitly rather than produce ambiguous success.

This principle later appears in ChrisHV, where unavailable hardware virtualization is also refused rather than silently substituted.

## Toolchain progression

The native toolchain history records a rapid progression from limited KCC/ChrisAsm/ChrisLd support toward compilation of real kernel translation units.

Important milestones on 25 September included:

- compiling kernel logging infrastructure;
- preserving volatile MMIO;
- expanding C and assembler forms;
- covering fourteen `kernel/metal` files;
- eventually host-compiling every C file in `kernel/metal`.

This was a major extension of the self-hosting boundary.

It did **not** mean the complete production kernel had become self-hosted.

The explicit limitation remained part of the architecture.

## Why partial self-hosting is a real stage

Self-hosting is not one binary transition.

Distinct stages include:

1. in-system editing;
2. in-system application compilation;
3. project-owned object/link formats;
4. native linking;
5. compiler capable of real kernel subsets;
6. complete kernel artifact construction;
7. boot of that artifact;
8. reproducible self-hosted rebuild.

History should preserve which stage was reached at each revision.

Calling stage 5 "fully self-hosted" would destroy the usefulness of the chronology.

## 25 September — VirGL and programmable graphics

A major graphics branch landed on 25 September.

The sequence introduced:

- explicit VirtIO queue/resource handling;
- bounded VirGL command encoding;
- VirtIO-GPU/VirGL proof rendering;
- QEMU VirGL targets;
- a ChrisOS GLSL-like subset compiler;
- project-owned shader IR;
- TGSI generation;
- compiled shaders driving VirGL proof scenes.

This is more than a feature addition.

It changed the rendering boundary from only fixed project code to a programmable shader pipeline with a backend-independent internal representation.

## Proof versus reusable subsystem

The first VirGL work was a proof scene.

The next architectural milestone was commit:

    011dfb25e41ac37db483216c0364923292035d39

which extracted a reusable Gfx3D backend behind the proof.

That is a **boundary extraction**.

A proof answers "can this mechanism work?"

A reusable subsystem answers "can ordinary callers use this mechanism through stable ownership and resource abstractions?"

History should not collapse those milestones into one.

## Cursor corrections as integration evidence

The later cursor/scanout fixes on 26 September are useful historical evidence because they show the gap between protocol support and polished integration.

A device capability can exist and still interact badly with:

- scanout;
- DMA visibility;
- input behavior;
- hypervisor display logic.

Architecture matures when these cross-layer contracts become explicit.

## 25 September — ChrisVM opens a new architecture branch

Commit:

    86f08da720c24ec6ee0b0179d6a97b3dbf0ca0f6

introduced the ChrisVM machine foundation and ChrisCPU interpreter.

Less than an hour later:

    be4307a28afb9b923549243d0f85a7358fcbf1b2

added framebuffer/splash support.

ChrisVM did not replace QEMU.

It created a project-owned path for:

- CPU state;
- decoding;
- execution;
- paging;
- exceptions;
- simple I/O/MMIO devices;
- deterministic host tests.

The QEMU production-kernel path explicitly remained.

This is best understood as **parallel architecture**, not replacement.

## Backend seam before acceleration

ChrisVM also introduced the ChrisHV backend identity while deliberately leaving it non-functional.

This is a useful architectural pattern:

- define the interface boundary;
- keep unsupported backend selection explicit;
- implement the reference/software backend first;
- add acceleration only after shared state semantics are clear.

History should preserve the fact that ChrisHV was a reserved seam, not infer hardware virtualization from the existence of the name.

## Evidence architecture evolves alongside implementation

The 24–26 September period also strengthened the validation system itself:

- host aggregate gates;
- orphan-test audit;
- fuzz-style tests;
- sanitizer paths;
- structured QEMU markers;
- device-specific QEMU gates;
- installer boot validation;
- safe-mode testing;
- ChrisVM host tests.

This matters because project maturity is partly the ability to make reliable claims.

A subsystem with a strong gate has a different evidence status from one demonstrated only visually.

## 26 September baseline

Commit:

    da3df29cb397932c43d32373871fb9380e688ade

became an important documentation baseline.

Many authored pages were reviewed against that source state.

Later source changes did not invalidate all of those pages equally; only pages declaring changed dependencies entered the stale review queue.

This led to the low-context, revision-bound documentation maintenance model now used by the site.

## 28 September — documentation authority changes

Commit:

    92fb561574bd929522ea005b9fd433138bea3236

made `chrisos_site` the canonical technical documentation source.

The source repository stopped carrying duplicated technical documentation as if it were equally authoritative.

This is a **canonicalization** change.

It affects engineering workflow even though it does not alter kernel execution.

The repository continues to own operational instructions close to exact commands, while the site owns architecture, contracts, history and the long-form technical corpus.

## Developer Guide canonicalization

Commit:

    e05a17fd76333114a3fb5c2452f38ca747d4ac56

linked the canonical Developer Guide from the source repository and is the source baseline reviewed by the current completion campaign.

At this point the documentation model has a clear authority split:

    ChrisOS repository
        -> source
        -> build/run/test mechanics
        -> contribution/security operational files

    chrisos_site
        -> canonical architecture
        -> specifications
        -> history
        -> validation interpretation
        -> developer guide

This reduces duplicated prose that would otherwise drift.

## Superseded evidence

Evidence becomes superseded when a stronger or newer fact replaces its relevance for current claims.

Examples:

- an old audit saying VirGL is absent is superseded for current behavior by later VirGL source and gates;
- an early KCC limitation remains historically true, but cannot describe the later kernel/metal gate;
- a pre-ChrisVM architecture overview cannot be treated as complete after ChrisVM appears;
- old duplicated source-repository docs remain historical artifacts after the site becomes canonical.

Superseded does not mean useless.

It means "do not use this as the primary source for present behavior."

## Historical conflict resolution

When two documents conflict, ask four questions:

1. What revision does each describe?
2. Which source paths were current at that revision?
3. Is one statement roadmap while the other is implementation?
4. Which evidence class supports each statement?

Many apparent contradictions disappear once revision identity is restored.

## Architecture epochs

A useful high-level view of the current history is:

### Desktop/software epoch

Framebuffer, 2D desktop and software graphics become usable development surfaces.

### Systems expansion epoch

Storage, filesystem, language/runtime, applications and software 3D increase cross-subsystem integration pressure.

### Hardening epoch

Locking, timeout, TLB, parser, installer and validation contracts become stricter.

### Native-toolchain expansion epoch

KCC/ChrisAsm/ChrisLd progress from limited bootstrap tools toward real kernel-source coverage.

### Accelerated-graphics epoch

VirtIO-GPU/VirGL and programmable shaders create a second 3D backend.

### Project-owned emulation epoch

ChrisVM/ChrisCPU introduce a controlled x86-64-subset machine alongside QEMU.

### Canonical-documentation epoch

Technical authority moves into a revision-bound bilingual corpus with generated source impact and stale detection.

These epochs overlap; they are explanatory groupings, not formal release numbers.

## Why histories remain separate

The top-level history should not duplicate every subsystem chronology.

Detailed histories exist for:

- graphics;
- native toolchain;
- ChrisVM.

This chapter instead records how those lines interact and how evidence/authority changed around them.

Subsystem chapters are the correct place for implementation-specific commit-by-commit detail.

## Nonlinear development

ChrisOS did not evolve as one ordered ladder.

Several lines advanced in parallel:

    kernel hardening
    graphics
    compiler/runtime
    self-hosting
    installation
    validation
    emulation
    documentation

A commit in one line can expose assumptions in another.

For example, compiler progress can reveal volatile-MMIO requirements; new graphics paths can expose DMA/ownership constraints; installation tests can expose storage/filesystem assumptions.

History should therefore preserve causal interactions, not just dates.

## What should enter architecture history

A future commit belongs in architecture history when it changes at least one durable boundary:

- ownership;
- ABI/format;
- privilege;
- concurrency;
- boot contract;
- device model;
- backend architecture;
- recovery semantics;
- validation/evidence class;
- documentation authority.

Routine code cleanup, typo fixes and isolated implementation optimizations usually do not need a top-level historical milestone.

## Commit messages are indexes, not proof

Commit messages are useful entry points into history, but the message alone is not the architectural evidence.

A message such as "add", "fix" or "support" must be checked against:

- the changed files;
- the actual source diff;
- tests added or modified in the same change;
- limitations preserved in code or prose;
- later corrections that may narrow the original claim.

This is especially important in a fast-moving experimental repository, where a concise commit title can describe the intended goal more broadly than the final implemented subset.

Architecture history should therefore use commit messages to locate milestones and diffs/tests to define what the milestone actually established.

## Current architecture statement

At reviewed revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, current behavior must be reconstructed from current source and current specifications.

Historical commits explain how the project arrived there.

The present documentation model therefore follows this rule:

> current chapters describe the current contract; history chapters preserve earlier contracts and transition evidence; neither should impersonate the other.

## Revision note

This chapter was reconciled against ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56` and the current Git history.

The main historical lesson is that ChrisOS maturity has come from three kinds of change at once: adding capabilities, making failure/ownership boundaries stricter, and upgrading the evidence used to justify claims.
