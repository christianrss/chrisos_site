---
id: shaders-csir
lang: en
type: technical-chapter
volume: 08-graphics
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/gfx/shader/sh_lex.c
  - kernel/gfx/shader/sh_parse.c
  - kernel/gfx/shader/sh_sem.c
  - kernel/gfx/shader/sh_ir.c
  - kernel/gfx/shader/sh_tgsi.c
  - kernel/gfx/shader/sh_exec.c
  - kernel/gfx/shader/sh_api.c
  - docs/SHADER_ARCHITECTURE.md
symbols: []
depends_on:
  - compiler-pipeline
  - software-3d
  - virtio-gpu-virgl
related:
  - chrisc-clvm
---

# Programmable shaders, GLSL subset and CSIR

## Fixed and programmable pipelines

A fixed-function renderer exposes predefined lighting/transform operations. A programmable pipeline lets applications provide programs for stages such as vertex and fragment processing.

ChrisOS implements a defined GLSL subset rather than claiming full desktop GLSL compatibility.

## Frontend

The shader compiler has lexer, recursive-descent parser, AST and semantic analysis. This mirrors the general compiler pipeline but targets shader-specific types, stage interfaces, builtins and execution constraints.

Errors include source location, which is necessary for usable shader tooling.

## CSIR

Chris Shader IR is a typed representation independent of the final VirGL/TGSI transport.

```text
GLSL subset
  ↓
AST / semantic analysis
  ↓
CSIR
  ├── TGSI emitter → VirGL
  └── interpreter → software backend
```

Backend independence is the key property: language semantics should not be hard-coded as strings inside one graphics driver.

## Types and interfaces

Shader programs need stage inputs/outputs, uniforms, samplers and temporary values. Link-time matching verifies that fragment inputs correspond to compatible vertex outputs.

Matrices use GLSL column-major semantics in the shader system. CPU-side matrix representations must be converted consistently.

## Control flow constraints

A small shader compiler can deliberately restrict dynamic complexity. Current documentation records bounded compile-time unrolling for certain `for` loops and inlining rules for user functions. Unsupported constructs should fail explicitly rather than silently generate wrong shaders.

## TGSI backend

VirGL in the current project consumes TGSI text generated from verified CSIR. TGSI is transport/backend representation, not the public shader API exposed to ChrisC.

This separation prevents applications from depending directly on virglrenderer-specific details.

## Software backend

`sh_exec.c` interprets the same CSIR. The small software triangle path can exercise vertex/fragment programs with perspective-correct varyings.

Cross-backend tests are valuable because both backends consume the same IR. Differences reveal either backend bugs or underspecified semantics.

## ChrisC API

The language-facing functions create/drop shaders and programs, attach/link, query diagnostics and set uniforms/samplers. Handles belong to the owning language slot and are destroyed on slot teardown.

Resource ownership is therefore integrated with shader API design.

## Mine Chris boundary

The world shader pair is compiled and used by a VirGL proof draw, but the Mine Chris voxel renderer still follows the software scene path at the documented revision. Shader readiness and game migration are separate milestones.
