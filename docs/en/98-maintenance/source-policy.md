---
id: source-policy
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
  - documentation-schema
  - validation-evidence
  - bibliography
---

# Source and revision policy

## Purpose

This chapter defines how ChrisOS documentation decides what counts as evidence, how implementation claims are tied to source revisions, and how a page remains reviewable as the codebase changes.

The policy exists to prevent three recurring documentation failures:

1. describing roadmap intent as implemented behavior;
2. preserving a technically correct statement after the source that made it true has changed;
3. treating a successful documentation build as evidence that the operating system itself works.

The documentation corpus is revision-aware by design. Every current implementation claim should be traceable to the strongest available evidence for the exact behavior being described.

## Evidence hierarchy

For claims about current ChrisOS behavior, use this order:

1. current ChrisOS source on `main`;
2. reproducible tests and gates on the same revision;
3. current in-repository specifications;
4. revision-bound audits and status records;
5. README prose;
6. roadmap material, explicitly labeled as future work.

The order is intentional.

A README can summarize architecture, but it cannot override source.

A roadmap can explain direction, but it cannot establish implementation.

A test can demonstrate one execution path, but it cannot prove untested hardware, configurations or protocol coverage.

## Current source is the implementation authority

When the question is:

> What does this ChrisOS revision actually do?

the current source tree is the primary authority.

Documentation should therefore distinguish between:

- implementation fact;
- architectural interpretation;
- intended design;
- future work.

An implementation fact must be recoverable from source or executable evidence.

Architectural interpretation may explain why a mechanism exists, but it must not invent behavior absent from the source.

## Revision identity

ChrisOS implementation pages use `reviewed_revision` to record the source revision against which the page was reconciled.

A revision identity is normally a Git commit SHA.

The revision answers:

> At which ChrisOS source state was this page last checked against its declared source dependencies?

It does **not** mean:

> Every statement on this page is permanently valid for all later revisions.

The revision is a review anchor, not a timeless certification.

## Declared source dependencies

The frontmatter `sources` field lists concrete paths in the ChrisOS source checkout.

Example:

    sources:
      - kernel/gfx/gfx3d.c
      - kernel/gfx/gfx3d_virgl.c

These paths are interpreted relative to the source repository root supplied to the documentation build.

`validate_docs.py` rejects a declared source path that does not exist in the checked-out ChrisOS source tree.

This is an important invariant:

> a source dependency is a real repository path, not a prose label.

## What belongs in sources

A path belongs in `sources` when a substantive implementation claim on the page depends on it.

Typical candidates include:

- implementation files;
- public headers;
- on-disk or wire-format readers/writers;
- boot code;
- driver code;
- tests when they define a relevant executable contract;
- build files when build behavior itself is documented.

Do not add every transitive include.

The field should identify the smallest source set that lets a reviewer reconstruct the documented mechanism.

## What does not belong in sources

Do not use `sources` for:

- external standards;
- general textbooks;
- documentation-repository scripts;
- conceptual references that are not ChrisOS source files;
- unrelated files added only to prevent stale detection;
- guessed files based on subsystem names.

External standards belong in the bibliography and chapter prose.

Documentation-maintenance pages such as this one can legitimately use `sources: []` because they describe the documentation system rather than ChrisOS implementation behavior.

## Symbols narrow attention

The optional `symbols` field names identifiers that are especially important inside declared source files.

Example:

    symbols:
      - gfx3d_boot
      - gfx3d_mark_lost

Symbols are not a substitute for source paths.

They are hints used by low-context tooling to extract focused source windows from large files.

A page should list only symbols that materially help reconstruct the documented mechanism.

## reviewed_revision and sources work together

The stale-document workflow uses both fields.

Conceptually:

    page
      |
      +-- reviewed_revision = R
      |
      +-- sources = {s1, s2, ...}
              |
              v
        git diff R..HEAD -- s1 s2 ...

If none of the declared sources changed, the page does not become stale merely because unrelated code changed elsewhere.

If at least one declared source changed, the page enters the generated review queue.

This keeps review cost proportional to dependency changes rather than repository size.

## Empty source sets

A page with `sources: []` is intentionally outside source-diff stale detection.

That is appropriate for pages whose subject is:

- documentation process;
- external standards mapping;
- pure conceptual theory;
- historical interpretation derived from explicitly cited commits;
- navigation or maintenance policy.

An empty source set must not be used to avoid maintenance for an implementation-facing page.

If the page claims current behavior from code, it should declare the code.

## Source changes are not automatically documentation changes

A declared source file can change without invalidating every claim on the page.

The stale queue means:

> reconciliation required.

It does not mean:

> prose definitely wrong.

The reviewer must inspect the relevant diff and decide whether the documented contract, invariant, error path or limitation changed.

## Unavailable baselines are not unchanged baselines

`context_pack.py` records a `diff_status`.

A baseline can be:

- `changed`;
- `unchanged`;
- `unavailable-baseline`;
- not applicable when no source dependency exists.

If the historical `reviewed_revision` cannot be resolved in the source checkout, the tool must not pretend that an empty diff proves stability.

`unavailable-baseline` means the reviewer needs additional Git history or a fresh full reconciliation.

## Updating reviewed_revision

Update `reviewed_revision` only after the page has been reconciled against the current source revision.

A correct sequence is:

1. inspect the current page;
2. inspect declared sources;
3. inspect the diff from the old reviewed revision when available;
4. verify relevant tests/specifications;
5. update prose and limitations;
6. set `reviewed_revision` to the reconciled source commit;
7. run documentation validation.

Do not bump the revision merely to clear a stale queue.

That destroys the meaning of the field.

## Bilingual revision integrity

English and Brazilian Portuguese pages sharing the same `id` must carry equivalent technical metadata.

`validate_docs.py` requires equality for:

- `sources`;
- `depends_on`;
- `reviewed_revision`.

This prevents one language from silently describing a different source baseline or prerequisite graph.

The prose may differ linguistically, but the technical scope must remain equivalent.

## Tests as evidence

Source inspection tells what code exists.

Tests tell what behavior has been exercised.

These are distinct evidence layers.

A useful implementation claim can be modeled as:

[
C = (R,; S,; T,; E)
]

where:

- (R) is the ChrisOS revision;
- (S) is the declared source set;
- (T) is the relevant test/gate set;
- (E) is the execution environment.

A statement such as "the NVMe path works" is weak.

A stronger statement records that the declared NVMe driver source at revision (R) passed a named QEMU gate under a specified virtual controller configuration.

## Host tests are not guest tests

A host unit test proves host-executed logic.

It does not prove:

- boot;
- interrupt delivery;
- DMA behavior in the guest;
- real firmware;
- physical device compatibility.

Host tests are valuable because they are fast and narrow.

Their evidence class should remain explicit.

## QEMU evidence

A QEMU gate proves behavior under a declared virtual-machine configuration.

It can establish integration across more layers than a host test.

It still does not automatically establish:

- physical hardware compatibility;
- firmware diversity;
- timing behavior;
- performance on real devices;
- all protocol variants.

QEMU is a strong controlled integration environment, not a synonym for hardware proof.

## ChrisVM evidence

ChrisVM tests validate behavior in the project-owned emulator/machine model.

They are especially useful for:

- CPU state;
- decoding;
- execution semantics;
- paging;
- exceptions;
- simple virtual devices;
- direct-boot contracts.

They do not prove equivalence with QEMU or physical x86 hardware unless a separate differential or conformance test establishes that relationship.

## Hardware evidence

A physical-hardware claim should identify enough context to make the result reproducible.

At minimum, record when relevant:

- machine/model;
- CPU;
- firmware mode/version;
- storage controller/device;
- GPU/display path;
- network adapter;
- boot medium;
- ChrisOS revision;
- command or image used;
- observed markers;
- failure/recovery behavior.

"Works on hardware" without a hardware profile is weak evidence.

## External specifications

External standards define behavior ChrisOS consumes but does not own.

Examples include:

- x86 architecture manuals;
- UEFI;
- ACPI;
- PCIe;
- VirtIO;
- NVMe;
- USB/xHCI;
- IETF RFCs;
- OpenGL/GLSL.

These references are tracked through the bibliography.

When version differences matter, the implementation chapter should record the relevant edition or protocol revision.

The external specification defines the standard; ChrisOS source defines the implemented subset.

## Internal specifications

Project-owned persistent formats and ABI contracts should have their own specification chapters.

Examples include:

- ChrisO;
- ChrisFS;
- CLVM;
- ChrisVM direct-boot protocol;
- shader/CSIR contracts.

When implementation and internal specification disagree, that disagreement is a defect requiring reconciliation.

Do not silently choose whichever side is more convenient.

## Historical evidence

Historical chapters are allowed to cite old commits because their subject is change over time.

A historical statement should identify the commit or interval in which the claim was true.

Current implementation pages should not rely on an old commit to establish present behavior.

History preserves superseded designs; it does not override current source.

## README and status documents

README files and status snapshots are useful orientation aids.

They are lower in the evidence hierarchy because they can lag behind implementation.

Use them to discover intended boundaries, commands or terminology, then verify current behavior against stronger evidence when the claim is technical.

## Roadmap discipline

Roadmap material must be explicitly future-facing.

Acceptable language:

- planned;
- proposed;
- target;
- future backend;
- not implemented;
- intended direction.

Unacceptable transformation:

    roadmap: add hardware virtualization

into:

    current claim: ChrisHV provides hardware virtualization

The distinction is especially important in experimental systems where planned architecture can be close to implemented architecture in naming.

## Generated source atlas

The generated source atlas is a deterministic mirror/index of source files.

It can provide:

- paths;
- hashes;
- line counts;
- includes;
- detected symbols;
- complete textual source mirrors for indexed files.

It is not authored architectural interpretation.

Generated facts should not be paraphrased as if a model independently verified system behavior.

## Source map

`source_map.py` builds a reverse mapping:

    ChrisOS source path
        -> documentation pages that declare it

This enables impact analysis.

The map is deterministic because it comes from frontmatter metadata rather than semantic similarity.

A source file absent from every page's `sources` field will not appear as a documentation dependency merely because its name looks related.

## Review queue

`stale_docs.py` compares declared sources from `reviewed_revision` to source HEAD and emits a bilingual generated review queue.

The queue is an **attention mechanism**.

It is not a correctness verdict.

A page can be stale but still factually correct.

A page can also be factually wrong even when its declared sources have not changed, for example if the original review was incomplete.

## Documentation build evidence

A successful documentation pipeline establishes properties of the documentation system:

- frontmatter parses;
- bilingual identities are valid;
- declared source paths exist;
- curriculum constraints hold;
- generated artifacts can be produced;
- static site builds;
- reader/SEO checks pass.

It does **not** establish that:

- the kernel boots;
- a driver works;
- a protocol is conformant;
- real hardware is supported.

Documentation CI and ChrisOS runtime validation are separate evidence classes.

## Negative evidence and explicit limitations

A high-quality chapter records what is not proven.

Examples:

- "host-tested only";
- "QEMU path verified; hardware unverified";
- "parser accepts subset X";
- "ChrisHV backend intentionally refused";
- "production ChrisOS kernel not booted by ChrisVM".

Explicit limitations prevent evidence from expanding beyond its actual scope.

## Source-policy checklist

Before marking an implementation page reviewed:

1. confirm the current source revision;
2. verify every declared source path exists;
3. inspect the relevant source, not only previous prose;
4. inspect the diff from the previous reviewed revision when available;
5. verify important symbols;
6. identify the strongest executed tests;
7. record untested environments;
8. separate current behavior from roadmap;
9. preserve limitations;
10. synchronize EN/PT-BR metadata;
11. run the documentation validation pipeline.

## Policy invariant

The central invariant is:

> Every current implementation claim must be attributable to a source revision and must not claim a stronger evidence class than the tests actually executed.

This invariant is more important than keeping revision numbers visually current.

A stale-but-honest page is recoverable.

A page that silently overstates evidence is not.

## Revision note

This policy reflects the documentation tooling and ChrisOS source baseline used by the corpus at revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

Because this page documents documentation policy rather than one ChrisOS subsystem, it intentionally declares an empty ChrisOS `sources` set.
