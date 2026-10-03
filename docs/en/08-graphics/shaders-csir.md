---
id: shaders-csir
lang: en
type: technical-chapter
volume: 08-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/shader/sh_pub.h
  - kernel/gfx/shader/sh_int.h
  - kernel/gfx/shader/sh_src.h
  - kernel/gfx/shader/sh_lex.c
  - kernel/gfx/shader/sh_parse.c
  - kernel/gfx/shader/sh_sem.c
  - kernel/gfx/shader/sh_ir.c
  - kernel/gfx/shader/sh_tgsi.c
  - kernel/gfx/shader/sh_exec.c
  - kernel/gfx/shader/sh_api.c
  - tools/test_shader.c
  - tools/test_gfx3d_abi.c
symbols:
  - sh_compile
  - sh_program_create
  - sh_program_attach
  - sh_program_link
  - sh_uniform_set
  - sh_soft_vs
  - sh_soft_fs
  - sh_soft_triangle
  - sh_shader_save_csi
  - sh_shader_load_csi
depends_on:
  - compiler-pipeline
  - software-3d
  - virtio-gpu-virgl
related:
  - shader-frontend
  - csir
  - tgsi-backend
  - software-shader
---

# Programmable shaders and Chris Shader IR

## Scope

ChrisOS contains a small shader compiler and runtime designed specifically for its graphics stack.

It is not a full GLSL 3.30 implementation. The public header states this explicitly.

The implemented architecture is:

```text
ChrisOS GLSL subset
        |
        v
lexer
        |
        v
recursive-descent parser / AST
        |
        v
semantic analysis + lowering
        |
        v
Chris Shader IR (CSIR)
       / \
      /   \
     v     v
TGSI text  software interpreter
     |             |
     v             v
VirGL          CPU rendering
```

The important property is that the language frontend and shader semantics do not depend directly on the VirGL command encoder.

## Supported stages

The public API defines numeric values for vertex, fragment, geometry and compute stages, but the compiler accepts only:

- vertex;
- fragment.

`sh_compile` explicitly rejects geometry, tessellation and compute shader requests.

The extra stage constants therefore describe namespace/future direction, not current compiler support.

## Source-size and compiler limits

The implementation deliberately uses fixed-capacity structures.

Important limits are:

```text
SH_SRC_MAX   = 4096 bytes
SH_TOK_MAX   = 768 tokens
SH_AST_MAX   = 512 nodes
SH_SYM_MAX   = 64 symbols
SH_IR_MAX    = 384 IR instructions
SH_IMM_MAX   = 160 float immediates
SH_TEMP_MAX  = 96 temporaries
SH_NEST_MAX  = 32 parser nesting levels
SH_SCOPE_MAX = 48 scopes
SH_ERR_MAX   = 8 reported errors
SH_TGSI_MAX  = 3600 bytes
SH_LOG_MAX   = 1536 bytes
```

These capacities are part of the current compiler contract. Exceeding them should fail rather than allocate unbounded compiler state.

## Compilation entry point

`sh_compile(stage,name,src)` allocates a `ShShader` and a full `ShComp`.

The name is truncated into a fixed 64-byte compiler name buffer.

The source length must be greater than zero and strictly less than 4096 bytes.

A valid uncached compilation measures individual phases with `RDTSC`:

1. lexing;
2. parsing;
3. semantic analysis/lowering;
4. IR optimization and verification;
5. TGSI emission.

The timings can be queried through `sh_shader_cycles`.

## Compile cache

ChrisOS keeps a small global cache of eight `ShComp` objects.

The cache key combines stage, compiler version and source bytes with an FNV-style 32-bit hash.

A hit still checks:

- hash;
- stage;
- exact source length;
- exact source bytes.

The first eight successful shaders fill cache slots. Later successful compilations replace the slot selected by `hash & 7`.

Cached entries copy the complete compiler state into a new shader object.

The cache is global and has no general locking protocol, so it should not be treated as a concurrent compilation cache.

## Preprocessor policy

The lexer supports a narrow `#version` directive only when it appears at the start of a line.

Accepted numeric versions are 110 through 330.

Other preprocessor directives are rejected with `unsupported preprocessor directive`.

An extension directive such as `#extension` therefore fails explicitly.

The version number is recorded, but accepting `#version 330` does not mean that all GLSL 3.30 syntax or semantics exist.

## Lexical language

Recognized keywords include:

- `in`, `out`, `uniform`, `const`, `layout`, `smooth`;
- scalar, vector, integer-vector and matrix types;
- `sampler2D`;
- `if`, `else`, `for`, `return`, `discard`;
- boolean literals.

Several familiar GLSL qualifiers are explicitly classified as unsupported, including legacy `attribute`/`varying`, precision qualifiers, `flat`, `noperspective`, `invariant`, storage-memory qualifiers and others.

Comments and source line/column tracking are implemented in the lexer.

## Diagnostics

Errors contain shader name, line and column, followed by:

- an error message;
- the relevant source line;
- a caret under the approximate column.

At most eight errors are retained in the fixed diagnostic log before later failures are effectively collapsed by capacity.

This makes compiler failures useful to applications without requiring a host compiler.

## Parser

The parser is recursive descent and writes into the fixed AST pool.

AST node kinds include declarations, functions, blocks, return, if, for, assignment, discard, literals, identifiers, unary/binary expressions, calls, swizzles, indexing and constructors.

Parser recursion is protected by `SH_NEST_MAX = 32`.

Going beyond this bound reports `nesting limit exceeded`.

The AST can be exported in human-readable form with `sh_shader_ast`.

## Types

The internal type system includes:

- void;
- bool;
- int;
- float;
- vec2/vec3/vec4;
- ivec2/ivec3/ivec4;
- mat3/mat4;
- sampler2D.

Matrices are represented as multiple vector temporaries and follow the shader system's column-major multiplication semantics.

This is why CPU matrices passed through Gfx3D require a defined conversion into shader/GLSL ordering.

## Symbol table

A symbol records name, kind, type, declared location, assigned slot, scope, temporary, function body/parameters, const state and limited compile-time value information.

Symbol kinds distinguish:

- stage inputs;
- stage outputs;
- uniforms;
- locals;
- functions;
- `gl_Position`;
- `gl_FragCoord`.

The table is limited to 64 entries.

Scopes have a separate fixed parent table.

## Interface slot assignment

Vertex attributes and varyings support up to eight locations.

Explicit `layout(location=...)` values are honored when valid and non-conflicting.

Unspecified attribute/varying slots are assigned from the next free position.

Conflicting or excessive locations produce errors.

Non-sampler uniforms consume vec4-style constant slots.

A mat4 consumes four slots and a mat3 consumes three.

The compiler limits this storage to 32 vec4 slots.

Sampler uniforms use a separate namespace limited to four samplers.

## Fragment-output restriction

The fragment stage currently supports exactly one user output.

That output must be `vec4`.

More than one fragment output or a different type is rejected.

Multiple render targets are therefore not part of the present shader-language contract.

## Built-in stage values

`gl_Position` is available only in the vertex stage and must be assigned a vec4.

`gl_FragCoord` is available only in the fragment stage.

The linker requires the vertex shader to have written `gl_Position`.

It also requires at least one fragment output.

These are semantic/link conditions, not merely syntax checks.

## Loop semantics

The parser recognizes `for`, but loops are not dynamic runtime loops in CSIR.

Semantic lowering requires:

- an integer declaration as the loop initializer;
- a compile-time evaluable initial value;
- a supported integer comparison;
- a statically understandable increment/decrement or assignment step;
- no assignment to the loop variable inside the body.

The body is unrolled during compilation.

The unroll guard is eight iterations.

If the condition would still be true after the eighth attempted iteration, compilation reports `loop bound exceeds the unroll limit`.

This creates bounded IR growth and removes runtime loop control from the current CSIR.

## User functions

User-defined functions are lowered by semantic expansion rather than retained as callable CSIR procedures.

Arguments are copied into new local temporaries and the function body is semantically processed at the call site.

Recursion is rejected.

A function-call stack tracks at most eight nested calls.

A function used as a value must return a value, and the current semantic rules require returns to appear as the final statement of the function-level body.

This is effectively bounded compile-time inlining.

## Built-in functions

The semantic layer recognizes a useful but intentionally small set, including:

- `texture`;
- `dot`;
- `cross`;
- `length`;
- `normalize`;
- `abs`;
- `sin`;
- `cos`;
- `min`;
- `max`;
- `clamp`;
- `mix`;
- `pow`;
- `reflect`.

Several built-ins lower into combinations of simpler CSIR operations.

For example, normalize is built from dot, reciprocal square root and multiply.

Unknown functions fail explicitly unless they resolve to a user function.

## Other expression restrictions

Array/vector indexing currently requires a constant integer index.

The percent operator is supported only when both operands are compile-time constant integers.

Standalone increment/decrement expressions are rejected; increment/decrement is supported as part of the restricted loop-step form.

Assignments to uniforms and stage inputs are rejected.

Sampler values are not ordinary assignable variables.

These restrictions make lowering deterministic and bounded.

## CSIR representation

The IR instruction is a compact fixed record containing:

- opcode;
- type;
- component count;
- destination temporary;
- up to three source temporaries;
- two auxiliary fields.

The instruction set includes arithmetic, swizzle/lane operations, comparisons, matrix operations, sampling, attribute/varying/uniform loads, stage stores, conditionals and discard.

Representative operations include:

```text
CONST MOV SWZ SETLANE
ADD SUB MUL MIN MAX ABS
DOT RSQ RCP SIN COS POW TRUNC CMP
MULMV MULMM SAMPLE
LOAD_ATTR LOAD_VAR LOAD_UNI LOAD_FCOORD
STORE_POS STORE_VAR STORE_COLOR
IF ELSE ENDIF DISCARD
```

There is no runtime loop opcode in the current IR.

## Temporary and immediate pools

Scalar/vector values use temporary registers indexed in a 96-entry pool.

Matrices consume consecutive temporaries by column.

Constant literal data is stored in a separate float immediate pool limited to 160 entries.

IR CONST instructions reference slices of this pool.

These fixed pools are verified before a shader is accepted.

## Optimization

`sh_opt` currently performs a compact dead-result elimination pass.

It repeats four times.

For selected pure operations, if the destination temporary has no use, the instruction is changed to `IR_NOP`.

The optimization is intentionally conservative.

Stores, sampling, control flow and other side-effecting/semantic operations are not removed by this rule.

This is not a general SSA optimizer.

## IR verification

`sh_verify` validates structural invariants after optimization.

Checks include:

- valid stage;
- temp and IR counts inside limits;
- valid opcode range;
- balanced IF/ELSE/ENDIF nesting;
- `STORE_POS` only in vertex shaders;
- `STORE_COLOR` and DISCARD only in fragment shaders;
- sampler, attribute and varying ranges;
- uniform-load destination ranges;
- matrix-multiply shape;
- constant/immediate bounds;
- source/destination temporary validity.

An unbalanced or structurally invalid IR is rejected before backend emission.

## Linker

A program consists of one compiled vertex shader and one compiled fragment shader.

At link time, fragment inputs are matched to vertex outputs by name.

Their types must match.

The linker builds a remap from fragment varying slots to vertex varying slots.

It also collects up to eight vertex attributes, up to eight varyings, up to 32 public uniform records and sampler metadata.

Linking then regenerates TGSI for both stages, applying the varying remap to the fragment shader.

## Failed relink behavior

A linked `ShProgram` has a generation counter.

Successful link increments the generation and skips zero on wrap.

If a program was previously linked and a later relink fails, the old linked program is kept.

The program log records `kept previous program`.

Gfx3D uses the generation to know when VirGL shader objects must be refreshed.

This gives shader hot-reload behavior a defined failure mode: a bad replacement does not automatically destroy the last known-good program.

## Uniform storage

Program uniform values are stored separately for vertex and fragment stages in fixed float arrays.

Matrices occupy consecutive vec4 slots.

`sh_uniform_set` finds every uniform with the same public name in both stages and updates both stage stores.

Mat4 consumes 16 floats directly.

Mat3 values are expanded into three vec4 slots with the fourth lane zero.

Scalar/vector values use up to four lanes.

Gfx3D later uploads these words into VirGL constant buffers.

## Samplers

Sampler2D symbols do not consume the ordinary uniform vec4 slots.

They receive sampler slots from zero to three.

`sh_sampler_find` searches fragment uniforms first, then vertex uniforms.

The current higher-level Gfx3D API effectively binds one texture, so the language can describe more sampler slots than the current public rendering API conveniently binds.

## TGSI backend

A successful shader emits TGSI text into a fixed 3600-byte buffer.

The public shader can expose this text directly.

At program link, TGSI is regenerated so fragment varying slots can be remapped to the linked vertex interface.

VirGL receives this TGSI text through the shader-object command described in the command-stream chapter.

TGSI is therefore a backend artifact, not the source language.

## Software interpreter

`sh_exec_ir` interprets the same CSIR.

It allocates a fixed `SH_TEMP_MAX × 4` temporary array on the execution stack and walks instructions sequentially.

IF/ELSE/ENDIF are implemented with a 32-level skip stack.

DISCARD ends fragment execution and marks the fragment discarded.

The interpreter implements the same arithmetic, matrix, load/store and sample operations used by the TGSI backend.

## Software math approximations

The interpreter contains its own compact approximations for sine, cosine, exponential, logarithm and power.

Inputs are deliberately bounded in several helpers.

These routines are not the system libm and should not be assumed bit-identical to host/GPU implementations.

Cross-backend shader tests should therefore use tolerances for transcendental results rather than requiring exact bit equality.

## Software texture sampling

The CSIR interpreter's sampler is distinct from the older procedural-texture module.

It accepts a CPU BGRA-like byte buffer, clamps U and V into 0..1 and performs nearest lookup.

It converts bytes into normalized float RGBA output.

This software shader texture behavior should not be conflated with `tex_sample`, whose older renderer uses repeat addressing over a fixed procedural atlas.

## Software triangle proof path

`sh_soft_triangle` is a small programmable-pipeline proof renderer.

It is limited to surfaces no larger than 128×128.

It runs the CSIR vertex shader for three vertices, performs perspective divide, rasterizes a bounding box, performs float depth testing and interpolates varyings using reciprocal W.

The fragment shader is then interpreted per accepted pixel.

This path demonstrates shader semantics independently of VirGL.

It is not the main general-purpose CPU rasterizer.

## CSI serialization

A successful shader can be serialized through `sh_shader_save_csi`.

The blob begins with eight 32-bit header words.

The current header contains:

- magic `0x52495343` ("CSIR" in little-endian bytes);
- format version 1;
- stage;
- IR instruction count;
- immediate count;
- temporary count;
- additive checksum;
- reserved word.

IR records follow the 32-byte header, then immediate floats.

## CSI validation limitation

The saved checksum is the sum of bytes in the IR records only.

Immediate-pool bytes are not included.

A corrupted immediate value can therefore leave the checksum unchanged.

Loading still checks the overall size and runs `sh_verify`, but structural verification does not authenticate literal values.

A stronger format should checksum the complete payload.

## CSI interface-metadata limitation

The serialized form does not preserve the original symbol table, attribute/varying/uniform high-water marks or linker interface metadata.

`sh_shader_load_csi` reconstructs only stage, IR, immediates and temporary count, names the shader `csi`, verifies it and attempts TGSI emission.

The current test serializes a constant vertex shader, which does not stress complex interface metadata.

CSI should therefore be considered an experimental IR persistence format rather than a complete general shader-cache format in this revision.

## Guest shader API

The guest-facing registry supports:

```text
16 shader objects
8 program objects
```

Each slot records an owner.

Foreign-owner lookup/drop fails.

The API supports compile, shader status/log, program create/attach/link/status/log, uniform lookup/update, sampler lookup and owner-wide cleanup.

`sh_guest_drop_owner` frees every shader and program belonging to the specified owner.

This integrates shader lifetime with CLVM/application teardown.

## Executable evidence

`tools/test_shader.c` exercises the subsystem extensively.

It covers:

- constant shaders;
- diagnostics and invalid swizzles;
- rejection of unsupported preprocessor directives;
- rejection of geometry shaders;
- MVP matrices and column-major semantics;
- texture sampling;
- diffuse lighting;
- the world shader pair;
- varying type mismatch at link;
- IF/ELSE;
- four-iteration loop unrolling;
- a user function calling clamp;
- discard;
- sine;
- software triangle rasterization;
- CSI save/load and corruption;
- 1000 compile/free cycles;
- malformed-source fuzz cases;
- guest ownership and cleanup.

The test requires live-object count to return to its initial value.

## Gfx3D evidence

`tools/test_gfx3d_abi.c` independently compares CPU matrix transforms against shader vertex execution for identity, translation, rotations, scale, camera transforms, perspective and orthographic matrices.

It also verifies that a failed shader relink keeps the previous program generation alive.

This ties shader semantics to the public Gfx3D contract.

## Current limitations

The language is a deliberate subset.

Only vertex and fragment stages compile.

No dynamic loops exist.

Recursion is unsupported.

Only one fragment color output exists.

Attributes/varyings are limited to eight, samplers to four and uniform storage to 32 vec4 slots per shader compiler state.

Source and IR capacities are fixed.

The compile cache and guest registries are global and not generally thread-safe.

CSI persistence is incomplete for rich interfaces.

TGSI output is bounded to 3600 bytes.

These limits make the compiler small and inspectable, but they are not desktop-GLSL compatibility.

## Revision note

This chapter was reconciled against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. It treats CSIR as the central semantic representation shared by the TGSI/VirGL backend and the software interpreter, with explicit compiler, linker and persistence boundaries.
