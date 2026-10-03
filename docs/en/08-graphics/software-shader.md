---
id: software-shader
lang: en
type: technical-chapter
volume: 08-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/shader/sh_exec.c
  - kernel/gfx/shader/sh_api.c
  - kernel/gfx/shader/sh_int.h
  - kernel/gfx/gfx3d.c
  - kernel/gfx/gfx3d.h
  - tools/test_shader.c
  - tools/test_gfx3d_abi.c
symbols:
  - sh_exec_ir
  - sh_soft_vs
  - sh_soft_fs
  - sh_soft_triangle
  - gfx3d_draw
depends_on:
  - csir
  - gfx3d-api
related:
  - tgsi-backend
  - software-3d
  - triangle-rasterization
---

# Software shader backend

## Scope

The programmable software path executes the same verified CSIR that feeds the TGSI/VirGL backend.

It has two layers: `sh_exec_ir`, the scalar CSIR interpreter, and CPU rasterizers that invoke vertex and fragment shaders around triangle interpolation.

There are two triangle paths:

- `sh_soft_triangle`, a compact proof renderer limited to 128×128;
- `soft_tri` in `gfx3d.c`, the software backend used by public Gfx3D targets up to 1920×1080.

Both are separate from the older `tri.c` renderer.

## Interpreter state

Every `sh_exec_ir` call creates a stack-local temporary file of 96 vec4-like registers and two 32-entry control-flow stacks.

The temporary file is zeroed for every invocation. Scalars, vectors, integer-like values and booleans all share float storage, matching CSIR.

Before execution, fragment color is zeroed, discard is cleared, and vertex position defaults to `(0,0,0,1)` when those outputs are present.

This per-call state means the interpreter itself does not retain temporary register values between vertices or fragments.

## Structured control flow

`IR_IF` tests lane X. Zero is false; nonzero is true.

The two fixed stacks track whether a branch is skipped and whether ELSE has already changed branch state. A false parent keeps nested branches skipped. ELSE toggles only a branch whose parent is active. ENDIF pops one level.

Malformed ELSE/ENDIF or runtime nesting beyond 32 returns an error defensively, although verified CSIR should already satisfy those invariants.

`IR_DISCARD` sets the discard flag and immediately returns from fragment execution.

## Data movement

CONST copies values from the compiler immediate pool and zeroes unused lanes.

MOV copies the selected number of lanes.

SWZ first copies all four source lanes to a local scratch value before writing the destination. This makes same-register swizzles safe.

SETLANE modifies only one destination lane and leaves the others untouched, preserving the non-SSA semantics documented in the CSIR chapter.

## Arithmetic

ADD, SUB, MUL, MIN, MAX and ABS operate component-wise.

DOT accumulates three or four source lanes according to its width field and writes lane X.

Comparisons LT, GT, LE, GE, EQ and NE read scalar X lanes and write 1.0 or 0.0.

TRUNC converts through a C integer cast and stores the resulting value back as float.

The backend therefore implements semantic integer behavior through the float temporary file rather than through a separate integer register bank.

## Reciprocal and square root behavior

RCP is component-wise. A zero input produces zero instead of infinity.

RSQ returns zero unless the input is strictly positive. Positive values use the local power approximation with exponent 0.5 and then reciprocal.

These are concrete software semantics and can differ from TGSI/VirGL behavior for zeros, negative inputs, infinities and NaNs.

Cross-backend tests should avoid assuming IEEE edge equivalence unless that behavior is explicitly standardized by ChrisOS.

## Trigonometric approximation

The software backend avoids host libm.

Sine first wraps toward the interval around ±π. Each wrap loop has a guard of 16 iterations. It then evaluates six series correction terms.

Cosine calls the same sine implementation with a π/2 offset.

For ordinary shader inputs this is sufficient for the current tests, but it is intentionally a compact approximation rather than a high-accuracy math library.

## Exponential, logarithm and power

POW has a special path for nonnegative integer exponents below 16, evaluated by repeated multiplication.

Negative bases are accepted only through that small integral-exponent path. A negative base with non-integral exponent returns zero.

The general positive-base implementation uses an approximate exponential of exponent multiplied by an approximate logarithm.

Exponential inputs are clamped to [-10,10] and evaluated with 16 terms. Logarithm rescales the input with bounded loops and uses a 20-term alternating series.

These choices explain why CPU and VirGL results should be compared with tolerances.

## Matrix execution

IR_MULMV and IR_MULMM use consecutive temporaries as matrix columns.

Matrix-vector multiplication scales each matrix column by the corresponding vector lane and accumulates it.

Matrix-matrix multiplication repeats the operation for every output column.

The interpreter follows shader column-major semantics. Gfx3D converts CPU `Mat4f` values into shader ordering before setting uniforms, so the same program can run in software or TGSI.

## Attribute input

IR_LOAD_ATTR treats input as eight vec4 locations.

The Gfx3D software draw path converts a raw vertex into a 32-float dense attribute array. `load_attr` zeroes the array, then copies up to four float components from every layout element into `location*4`.

Locations outside 0..7 and negative offsets are skipped.

The software loader assumes float elements at those byte offsets. It does not decode normalized integers, half floats or packed vertex formats.

## Uniform input

IR_LOAD_UNI reads stage-specific `ShProgram` word arrays, four floats per slot.

Mat3 and mat4 occupy consecutive slots.

`sh_soft_vs` passes vertex-stage words and `sh_soft_fs` passes fragment-stage words.

The public uniform API updates every matching same-name uniform across the attached stages, so the CPU backend sees the same logical program state used to build VirGL constant buffers.

## Varyings and remap

IR_STORE_VAR writes one of eight vec4 varying slots.

IR_LOAD_VAR reads a fragment input slot and applies the linked program's varying-remap table before access.

This mirrors linked TGSI generation.

The same cross-stage name/type link result therefore drives both CPU execution and device execution.

## Fragment coordinate

IR_LOAD_FCOORD reads a rasterizer-supplied vec4.

The software triangle paths construct:

```text
x = pixel-center X
y = pixel-center Y
z = software depth value
w = 1 / interpolated reciprocal-W
```

Thus the fourth component exposed as `gl_FragCoord.w` corresponds to the recovered W-like value from the current interpolation convention.

## CPU texture sampling

IR_SAMPLE uses a small nearest/clamp sampler.

U and V are independently clamped to [0,1].

Coordinates are rounded to the nearest texel with:

```text
x = int(u * (width  - 1) + 0.5)
y = int(v * (height - 1) + 0.5)
```

The sampler then clamps the integer result defensively.

No bilinear filtering, mipmapping, anisotropy, repeat or mirrored-repeat modes are implemented.

## Texture byte order

The CPU sampler reads four bytes per texel and returns normalized RGBA:

```text
R = byte2 / 255
G = byte1 / 255
B = byte0 / 255
A = byte3 / 255
```

This matches little-endian memory for the public 32-bit BGRA-like pixel values used by Gfx3D textures.

This sampler is unrelated to the older procedural-atlas `tex_sample`, which uses different wrapping semantics.

## Vertex wrapper

`sh_soft_vs` requires a linked program, an attribute array and an output position.

It calls `sh_exec_ir` with vertex uniforms, no varying input, no fragment coordinate and no texture.

The caller provides the varying-output array.

The wrapper contains no projection or viewport logic; those transformations come from the shader program and later rasterization.

## Fragment wrapper

`sh_soft_fs` calls the same interpreter with fragment uniforms, linked varyings, optional `fragcoord`, optional texture bytes and the program's varying remap.

It returns color plus discard status.

Depth testing, pixel coverage and conversion to packed pixels happen outside this wrapper.

## Proof renderer

`sh_soft_triangle` is the compact end-to-end proof renderer used by shader tests.

The output surface must be at most 128×128.

It receives three separate vertex attribute pointers. `attr_stride` must be at least four, but the current helper otherwise ignores the stride because each vertex has already been separated by the caller.

A float depth buffer is allocated for the entire surface on every call.

## Vertex projection

The vertex shader runs three times.

If any W lies within approximately ±0.0001, the proof renderer returns an error.

Otherwise it computes reciprocal W and full-surface coordinates:

```text
x = (X/W * 0.5 + 0.5) * width
y = (1 - (Y/W * 0.5 + 0.5)) * height
```

There is no homogeneous clipping stage and no clipping against six canonical clip planes.

## Bounding box and sampling

Projected minima/maxima form an integer bounding box, clipped to surface bounds.

Samples are evaluated at `pixel + 0.5`.

The signed edge denominator is recomputed inside the pixel loop. Magnitudes below about 0.0001 are treated as degenerate.

Barycentric weights are edge values divided by the signed denominator.

A sample is outside when any weight is below -0.001.

Because sign is normalized by the denominator, both windings can pass. There is no back-face culling or top-left shared-edge ownership rule.

## Perspective-correct varying interpolation

The rasterizer computes:

```text
iw = b0/w0 + b1/w1 + b2/w2
```

and each varying component as:

```text
(b0*v0/w0 + b1*v1/w1 + b2*v2/w2) / iw
```

All eight varying slots and four components are interpolated in fixed loops, regardless of how many are used by the linked fragment shader.

This is perspective-correct interpolation, unlike the affine UV interpolation in the older `tri.c` path.

## Current depth formula

The software programmable paths compute depth as:

```text
z =
 (b0*z0/w0 + b1*z1/w1 + b2*z2/w2)
 / iw
```

A fragment is rejected when `z >= stored_depth`.

Smaller values win and equal values lose.

The expression above is the literal implementation. It should not be described as necessarily identical to conventional hardware post-projection depth interpolation without a dedicated cross-backend depth test.

## Proof-renderer depth lifetime

The proof renderer initializes its newly allocated depth buffer to 1.0 and frees it at the end of the call.

Separate calls therefore do not share depth and cannot occlude one another.

This helper is for validating one triangle and shader pipeline, not for building a multi-triangle scene.

Discarded fragments do not update color or depth.

## Proof-renderer color packing

After fragment shading, RGBA floats are multiplied by 255, rounded, explicitly clamped to 0..255 and packed into a 32-bit BGRA-like pixel.

That clamping makes the proof helper deterministic even when a test shader outputs a value outside the nominal normalized range.

The Gfx3D production software path behaves differently.

## Gfx3D software renderer

The public backend uses `soft_tri` in `gfx3d.c`.

It runs the same `sh_soft_vs` and `sh_soft_fs` wrappers and nearly the same raster equations, but renders into persistent CPU target arrays.

Targets may be 1×1 through 1920×1080.

This is the software fallback used by Gfx3D AUTO after VirGL loss and by explicit SOFTWARE mode.

## Target lifecycle

`gfx3d_target_create` allocates one 32-bit color array and one float depth array.

`alloc_target_cpu` does not initialize either allocation.

`gfx3d_clear` fills color and sets every depth cell to 1.0.

Resize frees both arrays and creates new uninitialized storage.

Therefore a newly created or resized software target should be cleared before deterministic rendering.

The current API does not automatically clear it at creation.

## Clear behavior

`gfx3d_clear` clamps negative RGBA inputs to zero but does not explicitly clamp values above 1.0 before integer packing.

It always clears the CPU depth array to 1.0.

If its `depth` argument is nonzero, it enables the context depth flag; a zero argument does not disable a previously enabled flag.

Disabling public depth state requires `gfx3d_depth(ctx,0)`.

The software raster path, however, has a further mismatch described below.

## Persistent depth semantics

Gfx3D `soft_tri` always compares and updates target depth.

It does so regardless of `c->depth_on`.

Thus `gfx3d_depth(...,0)` affects VirGL state but does not currently disable depth testing in the software rasterizer.

This is a concrete cross-backend incompatibility.

The depth write happens only after fragment execution succeeds and the fragment is not discarded.

## Culling and viewport gaps

The public context stores a cull flag and viewport dimensions.

`soft_tri` ignores the cull flag.

It maps clip-space output to the entire target width/height rather than the stored viewport rectangle.

Viewport X and Y are already ignored at the Gfx3D API layer, and software rendering also ignores stored viewport width/height during coordinate mapping.

These state gaps should remain explicit until fixed.

## W and clipping behavior

Gfx3D software rendering silently skips an entire triangle when any vertex W is approximately within ±1e-5.

The proof helper instead returns an error around ±0.0001.

Neither path performs homogeneous clipping.

Triangles crossing the near plane, far plane, side planes or W=0 are not processed like a full GPU clipper.

Bounding-box clipping only limits raster writes to the target.

## Production color packing

Gfx3D `soft_tri` multiplies shader color channels by 255 and packs them directly.

Unlike `sh_soft_triangle`, it does not explicitly clamp the float output first.

Applications should keep production software fragment outputs inside the expected [0,1] range if deterministic packed channels are required.

The difference between proof and production paths is testable and should not be hidden.

## Indexed and non-indexed drawing

`gfx3d_draw` accepts either `uint16_t` index triplets or consecutive groups of three vertices.

Indices are range-checked against the vertex count before attribute loading.

Each triangle is then processed independently through `soft_tri`.

All triangles share the target's persistent depth array, unlike separate calls to the proof renderer.

## Complexity

Interpreter execution is O(CSIR instructions) per shader invocation.

A triangle runs three vertex invocations and one fragment invocation per accepted pixel.

Raster work is O(clipped bounding-box area), not merely O(covered pixels).

The current code recomputes the edge denominator inside the pixel loop and interpolates all eight vec4 varying slots for every covered sample.

There is no SIMD quad execution, JIT compilation, tiling or worker scheduling in this programmable software path.

## Concurrency

The interpreter's temporary/control arrays are local to a call, so independent calls do not share its register file.

However, `ShProgram` uniform arrays and Gfx3D target buffers are mutable shared objects without a general lock protocol.

Concurrent uniform updates or overlapping draws into the same target require external serialization.

The software backend is therefore not generally thread-safe even though its inner interpreter is mostly local-state based.

## Test evidence

`tools/test_shader.c` executes software shaders for constant output, MVP transforms, texture sampling, diffuse lighting, IF/ELSE, statically unrolled loops, user functions, discard and sine.

Its 32×32 proof-triangle test requires more than 20 red pixels.

It also checks different lighting orientations and exercises the same linked shader interface used by TGSI.

`tools/test_gfx3d_abi.c` separately boots Gfx3D in SOFTWARE mode, creates a 32×32 target, clears it, renders a triangle, reads it back and requires more than ten red pixels.

It then exercises several target resizes and repeated object lifecycle operations.

## Cross-backend role

Because both backends originate from the same verified CSIR, software execution is useful as a semantic reference.

It is not a universal bit-exact oracle for VirGL.

Known differences include transcendental approximations, texture sampling behavior, depth-enable handling, culling, viewport semantics and potentially depth representation.

Differential tests should isolate those gaps and use numerical tolerances where appropriate.

## Current limitations

The interpreter is scalar and non-JIT.

Sampling is nearest/clamp only.

The proof renderer is limited to 128×128 and creates fresh depth per call.

The public software renderer lacks full homogeneous clipping, culling-state support and working viewport semantics, and it ignores the depth-disable flag.

There is no multisampling, stencil, blending, derivative support or mipmapping.

Production color packing does not clamp fragment output.

These are concrete limits of revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

## Recommended tests

Useful additions include RCP/RSQ zero cases, software/VirGL SIN-COS-POW tolerance tests, sampler endpoint/out-of-range tests, discard preserving old depth, equal-depth rejection, several triangles sharing one target, depth-disabled/culling/viewport differential tests, W=0 and near-plane crossing cases, colors outside [0,1], and deterministic behavior after target creation before clear.

A dedicated depth test should also establish the intended relationship between the current software depth formula and VirGL depth.

## Revision note

This chapter was created against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. It documents the CSIR interpreter and both programmable CPU triangle paths while keeping them distinct from the legacy `tri.c` renderer.
