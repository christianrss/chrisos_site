---
id: shader-spec
lang: en
type: specification
volume: 15-specifications
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/shader/sh_pub.h
  - kernel/gfx/shader/sh_int.h
  - kernel/gfx/shader/sh_lex.c
  - kernel/gfx/shader/sh_parse.c
  - kernel/gfx/shader/sh_sem.c
  - kernel/gfx/shader/sh_ir.c
  - kernel/gfx/shader/sh_api.c
  - kernel/gfx/shader/sh_src.h
  - kernel/gfx/gfx3d.c
  - kernel/gfx/gfx3d_dev.h
  - tools/cshader.c
  - tools/test_shader.c
symbols:
  - sh_compile
  - sh_shader_ok
  - sh_program_create
  - sh_program_attach
  - sh_program_link
  - sh_uniform_set
  - sh_soft_vs
  - sh_soft_fs
  - sh_soft_triangle
  - sh_shader_save_csi
  - sh_shader_load_csi
  - sh_guest_compile
depends_on:
  - specifications-policy
  - shader-frontend
  - shaders-csir
  - gfx3d-api
related:
  - virtio-gpu-virgl
  - virgl-command-stream
  - software-shader
  - triangle-rasterization
---

# ChrisOS shader language and CSIR specification

## Status

ChrisOS contains a small shader compiler and runtime designed for the operating system's own graphics stack.

The source itself is explicit:

> this is a ChrisOS GLSL subset, not a GLSL 3.30 implementation.

This specification describes that subset, its compiler pipeline, program-link model, intermediate representation, software execution path, TGSI output, serialized CSIR form and guest ownership model as implemented at ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

## Scope

The shader subsystem has five distinct layers:

1. GLSL-like source text;
2. lexer/parser/semantic frontend;
3. ChrisOS shader IR;
4. either software IR execution or TGSI generation;
5. program integration with the software/VirGL graphics backends.

A source file that begins with `#version 330` is **not** evidence of full GLSL 3.30 support.

The version directive is accepted syntax inside a deliberately restricted language.

## Supported stages

The public API defines numeric stage values for:

    vertex   = 0
    fragment = 1
    geometry = 2
    compute  = 3

However `sh_compile()` currently accepts only:

- vertex;
- fragment.

Geometry, tessellation and compute-style compilation are rejected.

The extra constants reserve vocabulary; they do not imply implementation.

## Source-size limit

Shader source must satisfy:

    0 < source_length < 4096

because:

    SH_SRC_MAX = 4096

A source of 4096 bytes is already too large.

This bound includes all source text presented to the compiler.

## Compiler version

The public compiler version constant is:

    SH_COMPILER_VERSION = 1

This version describes the ChrisOS compiler implementation family.

It is not a GLSL language-version claim.

## Version directive

The lexer recognizes a line-start directive:

    #version N

with:

    110 <= N <= 330

The accepted number is recorded in compiler state.

Other preprocessor directives are rejected.

For example, `#extension` is not currently supported.

The accepted numeric version does not expand the syntax/semantic feature set to the complete Khronos language corresponding to that number.

## Comments

The lexer accepts:

- `//` line comments;
- `/* ... */` block comments.

An unterminated block comment is a compile error.

## Identifier limit

Internal names use:

    SH_NAME_MAX = 40

Identifiers whose length reaches the limit are rejected.

Public reflection structures also expose names through fixed 40-byte fields.

## Token limit

The compiler has:

    SH_TOK_MAX = 768

tokens.

Exceeding this bound is a compile error.

This is an implementation/resource limit rather than a general GLSL property.

## AST and nesting limits

The frontend uses:

    SH_AST_MAX  = 512
    SH_NEST_MAX = 32

AST-node exhaustion and excessive syntactic nesting are compile errors.

The semantic scope table has:

    SH_SCOPE_MAX = 48

entries.

## Symbol and temporary limits

The compiler has:

    SH_SYM_MAX  = 64
    SH_TEMP_MAX = 96

symbols and IR temporaries respectively.

These are hard bounds of the current implementation.

## Error budget

At most the first:

    SH_ERR_MAX = 8

errors are retained before later compilation stages stop making useful progress.

Diagnostics contain shader name, line, column, a source line and a caret where possible.

## Supported scalar and aggregate types

Type IDs cover:

- `void`;
- `bool`;
- `int`;
- `float`;
- `vec2`, `vec3`, `vec4`;
- `ivec2`, `ivec3`, `ivec4`;
- `mat3`, `mat4`;
- `sampler2D`.

No double-precision type, unsigned vector family, opaque image type, SSBO type or user-defined struct type is part of the current subset.

## Supported storage/qualifier vocabulary

Recognized qualifier-like keywords include:

    in
    out
    uniform
    const
    layout
    smooth

The compiler explicitly rejects several GLSL qualifiers, including:

    attribute
    varying
    highp
    mediump
    lowp
    inout
    centroid
    flat
    noperspective
    invariant
    precise
    readonly
    writeonly
    coherent
    volatile
    restrict
    shared
    patch
    sample

Therefore portability must be judged against this subset rather than desktop GLSL source in general.

## Global-scope restriction

`in`, `out` and `uniform` declarations are valid only at global scope.

Using those qualifiers on local declarations is rejected.

A `sampler2D` must be a uniform.

## Layout locations

The frontend supports explicit location syntax used by sources such as:

    layout(location = 0) in vec4 position;

Vertex attributes and stage interface variables can receive explicit locations.

Current resource binding allows at most eight attribute locations and eight varying/interface slots.

Location conflicts are rejected.

## Vertex inputs

A vertex shader can expose at most:

    8 attributes

through the current program/reflection model.

Locations may be explicit or automatically assigned to the next free slot.

The public reflection API reports name, type, location and component count.

## Varyings

Vertex outputs and fragment inputs are linked by **name** and then checked for type compatibility.

The linker builds a remap from fragment-input slot to vertex-output slot.

A fragment input with no matching vertex output fails link.

A same-name varying with a different type also fails link.

At most eight varying slots are supported.

## Fragment outputs

A fragment shader must provide at least one output for a program to link.

Current semantic binding further requires:

- exactly one fragment output;
- that output must be `vec4`.

Multiple render targets are not part of this subset.

## Built-in variables

The semantic layer introduces:

    gl_Position : vec4
    gl_FragCoord : vec4

`gl_Position` is available only where appropriate to the vertex stage.

`gl_FragCoord` is available only to the fragment stage.

A linkable vertex shader must write `gl_Position`.

## Statements

The parser/semantic layer supports a restricted set of statements including:

- declarations;
- assignments;
- expression statements;
- blocks;
- `if` / `else`;
- restricted `for`;
- `return`;
- fragment `discard`;
- empty statements.

Unsupported statement forms are compile errors.

## If/else

Conditions must be scalar-compatible.

The IR represents structured control flow with:

    IR_IF
    IR_ELSE
    IR_ENDIF

The verifier checks nesting and balance.

There are no arbitrary branch labels in the shader IR.

## For loops are compile-time unrolled

The current `for` implementation is deliberately restricted.

The loop initializer must declare an integer induction variable with a compile-time evaluable initial value.

The condition must be statically evaluable from that induction variable.

The step must match one of the supported compile-time integer-step forms.

The body is then semantically emitted repeatedly.

The implementation guard is:

    8 iterations

If the condition would still be true beyond the unroll bound, compilation fails with:

    loop bound exceeds the unroll limit

The loop variable may not be assigned inside the body.

Thus the language has no general dynamic loop in current IR.

## Increment/decrement

Pre/post increment syntax is not a general expression feature.

It is accepted only in the restricted loop-step context.

Using increment as an ordinary expression is rejected.

## Functions

User-defined functions are supported with important restrictions.

The current compiler allows at most four parameters per function.

A non-void function must produce a return value.

The return must be the last statement in the function according to current semantic rules.

## Function calls are inlined semantically

User-function calls are expanded through semantic processing rather than represented as a runtime call instruction in the final IR.

The compiler tracks a maximum semantic call depth of:

    8

and rejects recursion.

There is therefore no recursive shader execution in the current language.

## Scalar/vector arithmetic

Supported operators include arithmetic and comparisons used by the frontend:

    + - * /
    < > <= >= == !=
    && ||
    unary - and !

Vector/scalar compatibility follows the semantic helpers rather than full GLSL overload resolution.

Some operations are lowered to simpler IR identities.

## Modulo restriction

The `%` operator is currently supported only when both operands can be resolved as constant integers and the divisor is nonzero.

General runtime integer remainder is not emitted by the shader IR.

## Indexing restriction

Vector indexing currently requires a compile-time constant integer index.

Dynamic indexing is rejected.

The index must lie inside the vector's component count.

## Swizzles

Vector swizzles are parsed and semantically checked.

Invalid component selection is rejected.

Tests explicitly verify that selecting a nonexistent component such as `z` from a `vec2` produces a diagnostic.

## Matrix operations

The subset supports:

- `mat3`;
- `mat4`;
- matrix × vector;
- matrix × matrix.

Matrix × scalar is rejected.

The uniform path stores matrices in column-oriented vec4 slots.

The test suite validates the effective matrix convention with MVP execution.

## Constructors

Scalar, vector and matrix constructors are supported only in forms recognized by the semantic layer.

Component count is checked.

A scalar may be broadcast in supported constructor contexts.

Arbitrary GLSL constructor conversion behavior should not be assumed.

## Built-in functions

The implemented built-in function set at this revision is:

    texture
    dot
    cross
    length
    normalize
    abs
    sin
    cos
    min
    max
    clamp
    mix
    pow
    reflect

Calls outside the built-in list can resolve to supported user functions.

An unresolved function name is a compile error.

## texture()

`texture()` requires:

- a `sampler2D`;
- a vector coordinate with at least two components.

It lowers to:

    IR_SAMPLE

and returns `vec4`.

The current compiler permits sampling in vertex or fragment stage, subject to the rest of the backend path.

## Sampler limit

At most:

    4 samplers

are assigned by the semantic binder.

Sampler slots are distinct from ordinary uniform vec4 slots.

## Uniform slots

Non-sampler uniforms consume an array of vec4-like constant slots.

The semantic limit is:

    32 uniform vectors per stage

A `mat4` consumes four slots.

A `mat3` consumes three.

Scalar/vector values consume one.

## Program-level uniform reflection

The linked program exposes at most 32 reflected uniform entries.

Same-name uniforms appearing in both stages are represented as one logical program uniform when their types match.

Setting that program uniform updates the corresponding storage in both stages.

A type mismatch for a same-name uniform causes link failure.

## Uniform layout

The linked program keeps:

    128 floats for vertex uniforms
    128 floats for fragment uniforms

which corresponds to 32 vec4 slots per stage.

`mat4` occupies 16 consecutive floats.

`mat3` is expanded into three four-float slots with padding in the fourth lane of each column.

## Compiler pipeline

For uncached source, `sh_compile()` executes:

    lex
      -> parse
      -> semantic analysis
      -> IR optimization
      -> IR verification
      -> TGSI emission

Each major stage records a cycle counter.

The public API can return timing for lex, parse, semantic, IR and TGSI phases.

## Compiler cache

Successful compiler state is cached by:

- source hash;
- shader stage;
- exact source bytes.

The current cache has eight effective entries.

After the initial fill, a hashed slot may be replaced.

The cache stores the compiler representation, not a driver/GPU binary.

## AST and IR diagnostics

The API can expose textual dumps of:

- AST;
- IR;
- generated TGSI;
- compiler log.

These are diagnostics and development interfaces, not stable serialized ABIs unless separately versioned.

## ChrisOS shader IR

The current IR instruction classes are:

    NOP
    CONST
    MOV
    SWZ
    SETLANE
    ADD
    SUB
    MUL
    MAX
    MIN
    ABS
    DOT
    RSQ
    RCP
    SIN
    COS
    POW
    TRUNC
    CMP
    MULMV
    MULMM
    SAMPLE
    LOAD_ATTR
    LOAD_VAR
    LOAD_UNI
    LOAD_FCOORD
    STORE_POS
    STORE_VAR
    STORE_COLOR
    IF
    ELSE
    ENDIF
    DISCARD

The IR is small and structured around exactly the subset the frontend can produce.

## IR limits

The compiler permits:

    SH_IR_MAX  = 384 instructions
    SH_IMM_MAX = 160 float immediates
    SH_TEMP_MAX = 96 temporaries

An IR program beyond these limits is invalid.

## IR verifier

The verifier checks, among other invariants:

- legal stage;
- legal opcode;
- temporary indexes;
- constant ranges;
- balanced structured control flow;
- no duplicate `else`;
- `STORE_POS` only in vertex shaders;
- `STORE_COLOR` only in fragment shaders;
- `DISCARD` only in fragment shaders;
- sampler indexes;
- attribute indexes;
- varying indexes;
- uniform-load ranges;
- matrix multiply dimensions.

The verifier is used both after frontend compilation and while loading serialized CSIR.

## IR optimization

The optimizer currently performs four passes of simple dead-result elimination for pure temporary-producing operations.

It replaces unused pure instructions with `IR_NOP`.

This is not a general SSA optimizer.

No global value numbering, loop optimization or register allocation framework is present.

## TGSI output

A successfully compiled shader is translated from ChrisOS IR to TGSI text.

The maximum output buffer is:

    SH_TGSI_MAX = 3600

The TGSI is then suitable for the VirGL device path.

The compiler does not emit native NVIDIA/AMD/Intel machine code.

## Program linking

A `ShProgram` normally contains one vertex shader and one fragment shader.

Link requires:

- both attached shaders compiled successfully;
- vertex shader writes `gl_Position`;
- fragment shader has a valid output;
- fragment inputs match vertex outputs;
- varying types match;
- uniform conflicts are absent;
- TGSI can be emitted for both stages.

Successful link increments a program generation counter.

## Failed relink behavior

If a program was already linked successfully and a later relink fails, the implementation keeps the previous linked program active and records:

    kept previous program

This provides a useful hot-development failure mode: a bad edit need not destroy the last working program.

## Software execution

The same IR has a CPU execution path.

The public API exposes:

    sh_soft_vs()
    sh_soft_fs()
    sh_soft_triangle()

The software vertex and fragment functions execute IR directly.

This creates an important reference path independent of VirGL.

## Software triangle rasterizer

`sh_soft_triangle()` combines:

- software vertex execution;
- clipping/projection-related raster setup;
- varying interpolation;
- fragment execution;
- depth buffer;
- color packing.

The helper is deliberately small and currently restricts render target dimensions to:

    width  <= 128
    height <= 128

It is primarily a correctness/reference facility, not the full desktop renderer.

## Software and VirGL parity

For a shader subset feature to be considered portable across ChrisOS graphics backends, both of these paths matter:

    IR -> software executor
    IR -> TGSI -> VirGL

A shader compiling to TGSI does not by itself prove software-path parity, and the reverse is also true.

Host shader tests exercise both IR semantics and TGSI generation.

## VirGL integration

The device graphics API accepts:

    gfx3d_dev_shader(ctx, stage, tgsi, &handle)

The graphics layer can operate with software, mock or VirGL backends.

When VirGL is unavailable and the mode is not explicitly forced, the higher graphics layer can degrade to software.

Thus the shader compiler is designed around backend-independent source/IR with backend-specific execution below it.

## Predefined shader sources

The tree includes embedded source examples for:

- simple triangle color;
- varying color;
- MVP transform;
- texturing;
- lighting;
- world transform/normal/texturing.

These examples often use:

    #version 330

but still target the ChrisOS subset.

They serve as regression inputs, not as a conformance suite for GLSL 330.

## Serialized CSIR format

A compiled shader can be saved using:

    sh_shader_save_csi()

and loaded with:

    sh_shader_load_csi()

This serialized form stores verified ChrisOS IR and immediates rather than original GLSL source.

## CSIR header

The serialized record starts with eight 32-bit words, 32 bytes total.

Current fields are:

| Word | Meaning |
|---:|---|
| 0 | magic = `0x52495343` |
| 1 | format version = 1 |
| 2 | stage |
| 3 | IR instruction count |
| 4 | immediate-float count |
| 5 | temporary count |
| 6 | additive checksum over raw IR bytes |
| 7 | reserved/zero |

On little-endian ChrisOS hosts the magic appears as bytes:

    C S I R

## CSIR payload

After the 32-byte header:

    raw Ir[nir]
    raw float[nimm]

are copied directly.

The size must be exactly:

[
32 + nir cdot sizeof(Ir) + nimm cdot sizeof(float)
]

No trailing data is accepted by the loader.

## CSIR portability warning

CSIR v1 currently copies:

- native `uint32_t` header words;
- native `Ir` structs;
- native C `float` arrays.

It is therefore a **ChrisOS implementation artifact**, not a portable architecture-neutral interchange format.

Current little-endian C layout is part of practical compatibility.

A future portable format should encode fields explicitly.

## CSIR checksum

The stored checksum is a simple 32-bit sum of every raw byte in the serialized IR array.

Immediate-float bytes are not included in that checksum.

This is corruption detection, not a cryptographic integrity mechanism.

## CSIR loading

The loader validates:

- minimum size;
- magic;
- format version 1;
- stage is vertex or fragment;
- IR count <= 384;
- immediate count <= 160;
- temp count <= 96;
- exact file size;
- raw-IR checksum;
- IR verifier.

Then it regenerates TGSI from the loaded IR.

Tests deliberately corrupt a serialized image and require rejection.

## Guest-owned shader objects

The guest API maintains bounded handle tables:

    16 guest shaders
    8 guest programs

Each handle is associated with an owner.

Operations from a different owner are rejected.

Dropping an owner releases all of that owner's shader/program objects.

This ownership boundary is important when shader compilation is exposed to CLVM/user applications.

## Resource lifetime

Shader and program objects are heap-backed.

The implementation tracks a live-object count.

Tests repeatedly compile/free shaders and verify that the live count returns to its original value.

This gives direct host evidence against simple lifecycle leaks.

## Security and robustness

Shader source is treated as untrusted enough to be bounded and verified.

Important defensive properties include:

- fixed source/token/AST/symbol/IR/temp limits;
- bounded diagnostic buffer;
- bounded recursion/call expansion;
- static loop-unroll limit;
- stage-specific verifier checks;
- exact CSIR size validation;
- owner checks on guest handles.

These checks reduce attack surface but do not make the compiler a formally verified sandbox.

## Known non-GLSL semantics

Several behaviors differ materially from general desktop GLSL expectations:

- only vertex/fragment stages;
- no full preprocessor;
- no dynamic loops;
- recursion forbidden;
- max four function parameters;
- constant-only vector indexing;
- constant-only integer modulo;
- restricted qualifiers;
- one fragment color output;
- only four samplers;
- small fixed interface/resource limits;
- fixed compiler storage;
- no full standard-library built-in set.

Applications must target the ChrisOS subset intentionally.

## Compatibility requirements

The following should not change silently for already persisted or generated shader assets:

- CSIR magic/version/layout;
- IR opcode meanings;
- type IDs used in serialized IR;
- stage numeric values;
- uniform/varying/attribute slot interpretation;
- matrix packing convention;
- TGSI semantic mapping where persisted driver objects depend on it.

Source-language extensions can usually be additive, but changing existing expression semantics can break both software and VirGL execution.

## Recommended future work

Future versions should consider:

1. an explicit language-profile/version declaration independent of `#version`;
2. architecture-neutral CSIR encoding;
3. stronger CSIR checksum/hash;
4. machine-readable grammar and built-in catalogue;
5. explicit resource-limit query API;
6. broader loop/control-flow support through verified IR;
7. more complete integer semantics;
8. differential software-vs-VirGL shader tests;
9. fuzzing of lexer/parser/CSIR loader;
10. a compatibility suite that distinguishes ChrisOS-subset behavior from GLSL behavior.

## Conformance summary

A conforming implementation of the current ChrisOS shader subsystem must preserve:

- source limit below 4096 bytes;
- only vertex and fragment stages;
- the documented type/resource limits;
- restricted loop/function semantics;
- name/type-based stage linking;
- required vertex `gl_Position`;
- one `vec4` fragment output;
- verified ChrisOS IR;
- the listed IR opcode meanings;
- software execution semantics;
- TGSI generation for the VirGL path;
- CSIR v1 serialization/loading rules when that format is used.

## Revision note

This specification was reconciled against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

The correct compatibility statement is not "ChrisOS supports GLSL 3.30". It is: **ChrisOS implements a bounded GLSL-like subset, lowers it to its own verified IR, and executes that IR either in software or through TGSI/VirGL.**
