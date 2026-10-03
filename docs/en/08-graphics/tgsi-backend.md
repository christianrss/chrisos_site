---
id: tgsi-backend
lang: en
type: technical-chapter
volume: 08-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/shader/sh_tgsi.c
  - kernel/gfx/shader/sh_int.h
  - kernel/gfx/shader/sh_api.c
  - kernel/gfx/shader/sh_src.h
  - kernel/gfx/gfx3d_virgl.c
  - kernel/gfx/virgl_cmd.c
  - tools/test_shader.c
  - tools/test_gfx3d_abi.c
symbols:
  - sh_emit_tgsi
  - sh_program_tgsi
  - sh_program_link
  - virgl_cmd_shader
depends_on:
  - csir
  - virgl-command-stream
related:
  - shaders-csir
  - shader-frontend
  - software-shader
---

# TGSI backend

## Scope

The TGSI backend converts verified Chris Shader IR into the textual TGSI form consumed by the VirGL path.

It does not parse source language, allocate public Gfx3D objects or submit VirtIO requests.

Its boundary is:

```text
verified CSIR
     |
     v
sh_emit_tgsi
     |
     v
TGSI text
     |
     v
VirGL shader object
     |
     v
VirtIO-GPU SUBMIT_3D
```

The software backend executes the same CSIR directly. TGSI is therefore a backend representation, not the semantic source of truth.

## Output budget

TGSI text is written into a fixed buffer:

```text
SH_TGSI_MAX = 3600 bytes
```

The shader API stores one such buffer per compiled shader.

The in-tree shader tests require the larger MVP, lighting and world shaders to remain below roughly 3500 bytes, leaving a small margin below the hard capacity.

If instruction emission approaches the buffer limit, the emitter reports:

```text
TGSI exceeds the VirGL command budget
```

and clears the output.

The budget exists because this text is later packed into a VirGL shader-object command whose own command stream is also bounded.

## Stage header

The first output line is exactly one of:

```text
VERT
FRAG
```

depending on the shader stage.

The backend supports only vertex and fragment stages because those are the only stages the compiler can produce in this revision.

No geometry, tessellation or compute TGSI is emitted.

## Interface high-water marks

Semantic analysis initializes:

```text
attr_hi = -1
var_hi  = -1
uni_hi  = -1
samp_hi = -1
```

and raises each value as interface slots are allocated.

The TGSI emitter uses these high-water marks to decide whether declarations exist.

A shader with no uniforms therefore emits no CONST declaration.

A shader with no samplers emits no SAMP/SVIEW declarations.

## Vertex input declarations

For a vertex shader, every attribute slot from zero through `attr_hi` is declared:

```text
DCL IN[0]
DCL IN[1]
...
```

The declaration model follows the dense high-water range rather than walking only the exact set of source symbols.

Semantic slot allocation normally assigns compact locations unless the user requests explicit locations.

Explicit gaps can therefore cause declarations for intermediate input registers that are not otherwise referenced.

## Vertex outputs

Vertex position is always declared as:

```text
DCL OUT[0], POSITION
```

User varyings begin at TGSI output register one.

For CSIR varying slot N, the corresponding declaration is:

```text
DCL OUT[N+1], GENERIC[N]
```

Position is kept outside the generic-varying namespace.

This matches `IR_STORE_POS` writing OUT[0] and `IR_STORE_VAR` writing OUT[slot+1].

## Fragment varying inputs

Fragment inputs are declared as generic perspective-interpolated values:

```text
DCL IN[S], GENERIC[S], PERSPECTIVE
```

where S is the linked varying slot.

The frontend currently accepts `smooth` but does not provide flat or noperspective alternatives, so the TGSI backend consistently emits PERSPECTIVE for normal varyings.

This is the device-side counterpart to perspective-correct interpolation in the software programmable raster path.

## Varying remap

A fragment shader is initially compiled with stage-local varying slots.

At program link, fragment input names and types are matched against vertex outputs.

The linker builds a remap table.

`sh_emit_tgsi` receives that table when regenerating linked fragment TGSI.

For both declarations and `IR_LOAD_VAR`, a nonnegative remapped slot replaces the original fragment-local slot.

This is why linked TGSI must be regenerated instead of blindly reusing the text emitted during standalone fragment compilation.

## Fragment coordinate

The emitter first scans the IR for `IR_LOAD_FCOORD`.

If found, the fragment header adds:

```text
DCL IN[7], POSITION
```

and the load later becomes:

```text
MOV TEMP[d], IN[7]
```

TGSI input register seven is therefore reserved by this backend convention for `gl_FragCoord`.

This convention is separate from the generic varying declarations.

## Fragment output

The fragment color target is:

```text
DCL OUT[0], COLOR
```

`IR_STORE_COLOR` becomes a MOV into OUT[0].

Because the source-language subset currently allows exactly one fragment output, the TGSI backend has no multiple-render-target output mapping.

## Sampler declarations

For every sampler slot from zero through `samp_hi`, the emitter writes:

```text
DCL SAMP[N]
DCL SVIEW[N], 2D, FLOAT
```

A sampled texture therefore has both sampler and sampler-view declarations in TGSI.

The higher VirGL device layer creates and binds the corresponding sampler state and sampler-view object.

CSIR itself only carries the numeric sampler slot.

## Uniform constants

When `uni_hi >= 0`, the emitter declares one constant-buffer range:

```text
DCL CONST[0][0..uni_hi]
```

The shader subsystem stores vertex and fragment uniforms in stage-specific arrays, but TGSI exposes them through constant buffer zero.

`IR_LOAD_UNI` becomes one MOV per vec4 slot:

```text
MOV TEMP[d+k], CONST[0][base+k]
```

A mat3 therefore expands to three MOV instructions and a mat4 to four.

## Temporary declarations

When at least one CSIR temporary exists, TGSI declares:

```text
DCL TEMP[0]
```

or a range:

```text
DCL TEMP[0..N]
```

The TGSI temporary index is intentionally identical to the CSIR temporary index.

There is no backend register allocator in this revision.

That simple one-to-one mapping keeps the backend auditable but can use more temporary registers than an optimizing compiler would.

## Immediate declarations

Every `IR_CONST` receives its own TGSI IMM index.

The emitter performs a first pass over CSIR to number constant instructions.

It then emits:

```text
IMM[K] FLT32 {x, y, z, w}
```

with unused lanes filled with zero.

Even when two CSIR constants contain identical values, they are not deduplicated by the TGSI backend.

This favors implementation simplicity over textual compactness.

## Float formatting

Immediate floats are converted by the small ChrisOS formatting helper.

The formatter emits six fractional digits and clamps very large finite magnitudes in its textual helper path.

TGSI generation therefore does not use a host libc printf implementation.

The text is intended for the VirGL/TGSI parser, not as an exact decimal round-trip serialization format for arbitrary IEEE-754 values.

## Instruction numbering

Executable TGSI lines are prefixed with an increasing decimal program counter:

```text
  0: MOV ...
  1: ADD ...
  2: ...
```

Declarations and IMM records are not included in this counter.

The final instruction is emitted as:

```text
  N: END
```

The program counter is primarily part of the textual TGSI syntax/debug readability used by this backend.

## MOV and swizzle mapping

`IR_MOV` becomes TGSI MOV.

For partial vectors, the destination uses a write mask.

`IR_SWZ` also becomes MOV, but the source operand receives a swizzle assembled from the CSIR two-bit-per-component mask.

A full identity vec4 mapping omits the explicit suffix where possible.

Thus CSIR keeps a dedicated SWZ opcode while TGSI expresses the operation through operand modifiers.

## SETLANE

`IR_SETLANE` becomes a MOV to a single destination component:

```text
MOV TEMP[d].x, TEMP[a].yyyy
```

with lanes selected from `aux` and `aux2`.

The source scalar is replicated across the textual source swizzle even though only one destination lane is written.

This preserves the non-SSA partial-update semantics of CSIR.

## Basic arithmetic

The direct mappings are:

```text
IR_ADD -> ADD
IR_SUB -> SUB
IR_MUL -> MUL
IR_MIN -> MIN
IR_MAX -> MAX
IR_ABS -> ABS
```

The helper for binary operations applies a destination mask based on `ncomp`.

The source temporaries are read directly.

No additional type conversion is inserted by the TGSI backend; semantic analysis has already validated source-level types.

## Dot products

`IR_DOT` maps to:

- DP4 when `aux == 4`;
- DP3 otherwise.

The result is written to `TEMP[dst].x`.

The current source language uses dot on vector widths handled by semantic lowering, so the backend does not emit a separate DP2 case.

Smaller cases are normalized before this point or use the available mapping strategy.

## Scalar/lane transcendental operations

The following CSIR operations map to same-named TGSI operations:

```text
IR_RSQ   -> RSQ
IR_RCP   -> RCP
IR_SIN   -> SIN
IR_COS   -> COS
IR_TRUNC -> TRUNC
```

For a multi-component CSIR value, the backend emits one TGSI instruction per component.

Each source lane is replicated, and each instruction writes one destination lane.

One CSIR instruction can therefore expand into up to four TGSI instructions.

## POW

`IR_POW` is scalar in the current backend mapping.

It becomes:

```text
POW TEMP[d].x, TEMP[a].xxxx, TEMP[b].xxxx
```

Higher-level vector behavior, when supported by source semantics, must already have been decomposed before this instruction reaches TGSI.

## Comparisons

CSIR comparison codes map as follows:

```text
LT -> SLT(a,b)
GT -> SLT(b,a)
GE -> SGE(a,b)
LE -> SGE(b,a)
EQ -> SEQ(a,b)
NE -> SNE(a,b)
```

The destination is lane X.

Greater-than and less-or-equal are implemented by swapping operands rather than requiring additional TGSI opcodes.

This mirrors the CSIR convention of scalar boolean results represented as 0.0 or 1.0.

## Matrix-vector multiplication

`IR_MULMV` does not map to one matrix opcode.

The helper `mad_col` expands a column-major matrix-vector multiply into:

- one MUL for the first column contribution;
- one MAD for each remaining column.

For a four-column matrix this yields four TGSI arithmetic instructions.

The vector component is replicated with `.xxxx`, `.yyyy`, `.zzzz` or `.wwww`.

Each is multiplied by the corresponding matrix-column temporary.

## Matrix-matrix multiplication

`IR_MULMM` applies the same column expansion once for every destination column.

A 4×4 matrix multiplication therefore expands to sixteen MUL/MAD instructions.

A 3×3 operation expands to nine.

This is a major source of textual TGSI growth and explains why complex matrix-heavy shaders can approach the 3600-byte budget even when CSIR remains well below its 384-instruction limit.

## Texture sampling

`IR_SAMPLE` maps directly to:

```text
TEX TEMP[d], TEMP[coord], SAMP[N], 2D
```

The TGSI instruction names the sampler slot but not the VirGL resource ID.

Sampler/view binding is performed later by the Gfx3D VirGL backend.

This keeps shader text independent of the concrete texture resource used by a particular draw.

## Attribute loads

`IR_LOAD_ATTR` becomes:

```text
MOV TEMP[d], IN[location]
```

The Gfx3D/VirGL draw path separately constructs vertex-element and vertex-buffer state whose locations must match these declarations.

TGSI and vertex-layout compatibility are therefore linked through the program's public attribute metadata.

## Varying loads

`IR_LOAD_VAR` becomes a MOV from the linked input slot.

The same `var_remap` used for fragment declarations is applied here.

Failure to use the same mapping in both places would make declaration and instruction register numbers disagree.

The current emitter keeps them synchronized through one remap parameter.

## Stage stores

Output mappings are simple:

```text
IR_STORE_POS   -> MOV OUT[0], TEMP[a]
IR_STORE_VAR   -> MOV OUT[slot+1], TEMP[a]
IR_STORE_COLOR -> MOV OUT[0], TEMP[a]
```

The meaning of OUT[0] depends on stage: POSITION for vertex, COLOR for fragment.

Generic vertex varyings begin at OUT[1].

## Structured control flow

CSIR's structured markers map directly:

```text
IR_IF    -> IF TEMP[a].x
IR_ELSE  -> ELSE
IR_ENDIF -> ENDIF
```

Because loops and user function calls have already been removed by semantic lowering, the TGSI backend needs no loop, branch-target or subroutine machinery.

It emits only structured conditional flow.

## Discard

`IR_DISCARD` becomes:

```text
KILL
```

The shader tests explicitly require generated fragment TGSI for a discard shader to contain `KILL`.

This is one of the direct test assertions tying a CSIR semantic operation to TGSI text.

## NOP handling

`IR_NOP` produces no TGSI instruction.

The optimizer converts dead pure CSIR instructions to NOP without compacting the IR array.

The TGSI emitter simply skips those entries.

Consequently, backend instruction numbering is dense even when the CSIR array still contains NOP holes.

## Unknown/default behavior

The emitter's switch has a default branch that emits nothing for an unrecognized opcode.

Under the intended pipeline this is protected by `sh_verify`, which rejects opcodes above the defined CSIR range before TGSI emission.

TGSI generation should therefore only see verified IR.

The backend is not meant to sanitize arbitrary unchecked memory by itself.

## Linked-program regeneration

Standalone shader compilation emits preliminary TGSI.

At program link, the shader API rebuilds vertex and fragment TGSI from their retained `ShComp` objects.

The fragment emission receives the linker's varying remap.

The linked `ShProgram` therefore owns the TGSI text that should be passed to Gfx3D/VirGL.

This is also why the shader subsystem retains compiler/IR state after source compilation rather than discarding it immediately.

## Gfx3D integration

`gfx3d_prog_prepare` receives a linked `ShProgram`.

When VirGL is active, Gfx3D retrieves:

```text
sh_program_tgsi(program, SH_STAGE_VERTEX)
sh_program_tgsi(program, SH_STAGE_FRAGMENT)
```

and creates VirGL shader objects from those strings.

The public Gfx3D layer never needs to understand CSIR opcode mappings.

It treats TGSI as backend payload owned by the shader subsystem.

## VirGL shader-command boundary

The VirGL command encoder packages TGSI text into a shader-object command.

That layer:

- accepts only vertex or fragment stage;
- limits text length to 3600 characters;
- includes the terminating NUL;
- packs four text bytes per command dword.

Thus `SH_TGSI_MAX = 3600` in the compiler aligns with the downstream shader-command limit.

The two components share an intentional size contract.

## Failure propagation

If TGSI emission fails during compile, the shader is not marked successful.

If linked-program TGSI regeneration fails, program linking fails.

A failed relink can preserve the previous linked program generation, as documented in the shader/CSIR chapter.

At the Gfx3D layer, failure to create/upload VirGL shader objects can mark the VirGL backend lost and trigger AUTO fallback to software.

There is therefore a complete error path from textual emission to rendering policy.

## Test evidence

`tools/test_shader.c` checks multiple TGSI properties:

- constant vertex TGSI begins with/contains VERT;
- vertex position semantics contain POSITION;
- output ends with END;
- MVP TGSI contains CONST[0] and MUL;
- texture fragment TGSI contains TEX and SAMP[0];
- discard fragment TGSI contains KILL;
- world/MVP/lighting TGSI remains below the configured budget.

These are textual host-side assertions.

## Integration evidence

The VirGL boot proof described in the graphics-device chapter goes further than string inspection.

Shaders generated by this backend are uploaded through the VirGL shader-object command and exercised in triangle, texture, depth, cube and lighting workloads with pixel readback.

That is the relevant evidence that the generated text is accepted by the configured VirGL/virglrenderer environment.

Host string tests alone cannot prove device acceptance.

## Backend-equivalence boundary

Both TGSI and the software interpreter originate from the same verified CSIR, but they need not be bit-identical.

The software backend uses ChrisOS approximations for transcendental functions.

TGSI delegates those operations to the host/VirGL implementation.

Floating-point edge behavior, transcendental precision and texture sampling policy can therefore differ.

Cross-backend tests should focus on defined semantic ranges and tolerances rather than exact bits for all operations.

## Current limitations

The TGSI backend supports only vertex and fragment programs.

There is one fragment color output.

Normal varyings always use PERSPECTIVE interpolation.

There is no register allocation or temporary compaction.

CSIR constants are not deduplicated in TGSI IMM declarations.

Matrix operations expand aggressively into MUL/MAD sequences.

TGSI text is capped at 3600 bytes.

The backend produces textual TGSI specifically for the current VirGL path rather than a reusable binary shader ISA.

## Recommended next tests

Useful additions include golden TGSI outputs for:

- varying remap with deliberately different vertex/fragment slots;
- mat3 and mat4 multiply;
- all comparison operators;
- multi-component SIN/COS/RCP;
- `gl_FragCoord`;
- sampler slots above zero;
- explicit attribute-location gaps.

A boundary test should construct a shader just below the 3600-byte budget and another that deterministically exceeds it.

An integration test should also compare selected software and VirGL results within numeric tolerances for the same linked program.

## Revision note

This chapter was created against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. It documents the TGSI text emitter as a bounded backend translation from verified CSIR to the shader representation consumed by VirGL.
