---
id: gfx3d-api
lang: en
type: technical-chapter
volume: 08-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/gfx3d.c
  - kernel/gfx/gfx3d.h
  - kernel/gfx/gfx3d_dev.h
  - kernel/gfx/gfx3d_virgl.c
  - kernel/gfx/gfx3d_batch.c
  - kernel/gfx/gfx3d_batch.h
  - kernel/gfx/gfx3d_ctx.c
  - kernel/gfx/gfx3d_ctx.h
  - kernel/gfx/shader/sh_pub.h
  - tools/test_gfx3d_abi.c
  - tools/test_gfx3d_ctx.c
symbols:
  - gfx3d_boot
  - gfx3d_context_create
  - gfx3d_target_create
  - gfx3d_mesh_create
  - gfx3d_mesh_upload
  - gfx3d_tex_create
  - gfx3d_prog_prepare
  - gfx3d_begin
  - gfx3d_draw
  - gfx3d_end
  - gfx3d_present_scanout
  - gfx3d_drop_owner
depends_on:
  - software-3d
  - virtio-gpu-transport
related:
  - virtio-gpu-virgl
  - virgl-command-stream
  - shaders-csir
---

# Gfx3D backend-neutral API

## Scope

Gfx3D is the public 3D abstraction that sits above the ChrisOS software renderer and the VirtIO-GPU/VirGL device backend.

Its main design rule is stated directly in `gfx3d.h`: public handles are ChrisOS handles, while VirtIO resource IDs and VirGL object handles do not cross this boundary.

The API therefore has two responsibilities at once:

1. present one mostly stable object/frame interface to callers;
2. translate that interface either into CPU rendering or into device-side VirGL work.

This chapter documents that contract rather than the lower transport or the VirGL packet format.

## Backends

Four boot modes exist:

```text
GFX3D_AUTO
GFX3D_SOFTWARE
GFX3D_VIRGL
GFX3D_MOCK
```

SOFTWARE always selects the CPU backend.

VIRGL requires `gfx3d_dev_available()`. If unavailable, boot returns failure, records `virgl unavailable`, and leaves the visible backend name as `virgl-lost`.

AUTO chooses VirGL when the device backend is available; otherwise it chooses software.

MOCK does not render pixels. It records high-level API operations into a log for ABI/ordering tests.

## Device-lost policy

`gfx3d_mark_lost` marks the VirGL path unusable.

If the caller forced VirGL, Gfx3D keeps the VirGL selection and reports the lost state instead of silently changing policy.

If AUTO selected VirGL, Gfx3D switches to SOFTWARE and marks statistics as degraded.

This difference is important for diagnostics: AUTO prioritizes continuity, while forced VirGL prioritizes exposing the backend failure.

## Public handle format

A public handle packs:

```text
high 16 bits : generation
low 16 bits  : slot index + 1
```

Zero is never valid.

Each object slot owns a generation counter. Reusing a freed slot increments the generation, wrapping through 1..65535 and skipping zero.

A stale handle therefore fails when its stored generation no longer matches the live slot.

This is stronger than exposing a raw table index and prevents many use-after-destroy mistakes from accidentally targeting a new object.

## Owner isolation

Every context, target, mesh, texture and program instance stores an integer owner.

Lookup helpers accept an expected owner and reject objects owned by another caller.

`GFX3D_OWNER_KERNEL` is owner zero, but the API supports other integer owners for applications/subsystems.

Ownership is software bookkeeping, not an MMU/IOMMU security boundary, but it prevents accidental cross-owner destroy/bind operations through normal calls.

## Fixed object tables

Current capacities are:

```text
contexts : 8
targets  : 8
meshes   : 48
textures : 24
programs : 16
```

The tables are static global arrays.

Creation scans for a free slot.

When a table is full, creation returns handle zero and records an error string.

The fixed tables keep allocation/lookup simple, but they also make capacity a visible API limit.

## Context state

A context stores:

- owner and generation;
- optional backend device context;
- active-frame flag;
- bound target;
- bound program;
- bound texture;
- depth enable;
- cull enable;
- viewport width/height;
- model/view/projection matrices;
- camera parameters.

A new context defaults to depth enabled, FOV 60 degrees, near 0.1 and far 200.

Model, view and projection start as identity matrices.

When VirGL is active, context creation also attempts to create a backend device context.

## Context creation failure and fallback

If device-context creation fails under forced VirGL, public context creation fails and returns zero.

If AUTO was using VirGL, the same device failure calls `gfx3d_mark_lost`, degrades to software and still returns the public context.

The public object can therefore survive a backend transition in AUTO mode.

This fallback policy appears repeatedly in target/resource operations.

## Context destruction

Destroying a context first destroys targets and program instances associated with that exact public context.

Then it destroys the backend device context when present.

Meshes and textures are owner-scoped rather than directly context-scoped, so they are not automatically destroyed solely because one context disappears.

Full owner cleanup is handled separately by `gfx3d_drop_owner`.

## Render targets

A target belongs to one context and accepts dimensions from 1×1 through 1920×1080.

Every target allocates CPU storage for:

- 32-bit color pixels;
- float depth values.

This CPU storage exists even when VirGL is active.

When the device backend is available, target creation additionally allocates device color/depth resources and associated DMA through `gfx3d_dev_target`.

The public target is therefore a cross-backend object, not merely a thin GPU resource handle.

## Target memory cost

For W×H pixels, CPU target storage is approximately:

```text
color = W * H * 4
depth = W * H * sizeof(float)
```

At Full HD, that is roughly 8.29 MB for color plus another 8.29 MB for float depth, before device backing.

Gfx3D statistics track target and depth bytes separately.

VirGL device backing is queried through the device layer.

## Resize semantics

A no-op resize returns success immediately.

A real resize destroys VirGL target resources first when present, frees CPU color/depth arrays, allocates new CPU arrays, and then recreates device resources when VirGL remains active.

If VirGL recreation fails in AUTO mode, Gfx3D marks VirGL lost and keeps the CPU target.

Forced VirGL returns failure instead.

Previous pixel/depth contents are not preserved by resize.

## Readback

`gfx3d_target_read` requires destination capacity for the complete target.

In software mode, it copies the CPU color array.

In VirGL mode, it first asks the device backend to transfer/read the color resource into the target's CPU color array, increments the readback statistic, and then copies to the caller.

This makes readback semantics consistent at the public boundary even though cost differs greatly by backend.

## Mesh table and usage hint

Meshes accept:

```text
STATIC
DYNAMIC
STREAM
```

usage values.

An invalid usage value is normalized to STATIC.

The current implementation stores the usage field, but upload behavior is not yet a sophisticated backend-specific streaming policy.

Callers should treat it as an API intent hint rather than a full resource residency contract.

## Vertex layouts

`Gfx3DLayout` contains:

- byte stride;
- element count up to eight;
- location for each element;
- component count;
- byte offset.

The shader program exposes required attributes.

`gfx3d_layout_ok` verifies that every required shader attribute location is present and that the supplied element has at least the required number of components.

It does not, by itself, prove that every offset and component range fits inside stride.

Mesh upload performs only broader structural checks such as positive stride and element-count range.

A future validator should make byte-range validation stricter.

## Mesh upload ownership

`gfx3d_mesh_upload` copies vertex bytes into Gfx3D-owned CPU memory.

Optional indices are copied into a `uint16_t` array.

The source pointers can therefore be released by the caller after upload returns.

The statistics account for CPU mesh bytes.

When VirGL is active, the implementation searches for a live device context belonging to the same owner and uploads VBO/IBO resources there.

The mesh records the device context used for those buffers.

## Mesh device-context caveat

Mesh upload is owner-scoped, not explicitly context-scoped.

The code chooses the first live owner context with a device context.

That is convenient for current workloads but is not a general multi-device-context residency model.

If an owner creates several independent VirGL contexts, mesh/device ownership semantics are weaker than the public API shape may suggest.

A future design should make resource-context affinity explicit or support backend sharing deliberately.

## Incremental mesh builder

Besides raw upload, Gfx3D provides `gfx3d_mesh_vert`.

It accumulates up to:

```text
ACC_MAX = 8192
```

vertices.

Each accumulated vertex contains position, normal and UV: eight floats.

The temporary array begins at capacity 64 and doubles as needed up to the cap.

`gfx3d_mesh_finish` converts the accumulator into a 40-byte vertex format.

## Canonical finished layout

The generated 40-byte layout contains:

- location 0: four position components at offset 0;
- location 1: four normal-related components at offset 16;
- location 2: two UV components at offset 32.

The W position is set to 1.

The fourth normal slot remains zero because the accumulator supplies XYZ normal only.

After raw upload succeeds, the temporary conversion buffer is freed.

## Textures

Public Gfx3D textures support dimensions 1..1024 in both axes.

Creation allocates a CPU `uint32_t` pixel array.

Upload requires dimensions to match exactly.

Every uploaded pixel is ORed with:

```text
0xFF000000
```

so public texture upload currently forces opaque alpha.

When VirGL is active, a device texture and sampler view are created for the first suitable owner device context.

## One effective texture binding

`gfx3d_bind_tex(owner,ctx,unit,tex)` currently ignores the `unit` argument.

The context stores one texture handle.

This means the public signature anticipates texture units, but the present implementation effectively supports a single bound texture.

Documentation and applications must not infer working multi-texture support merely from the parameter.

## Solid texture helper

`gfx3d_tex_solid` creates a 1×1 texture, forces opaque alpha and uploads one pixel.

On upload failure it destroys the newly created texture before returning.

This is useful for materials that want the same shader path with a constant sampled color.

## Shader program instances

Gfx3D does not compile source itself.

It receives a linked `ShProgram` from the shader subsystem.

`gfx3d_prog_prepare` verifies that the program is linked and creates a public program instance tied to a specific Gfx3D context.

In VirGL mode, TGSI text for vertex and fragment stages is retrieved from the shader program and uploaded as VirGL shader objects.

## Program generation and hot refresh

A prepared program stores the shader program's generation stamp.

Before use/draw, Gfx3D compares the current `sh_program_gen` against the stored stamp.

If the program was successfully relinked and generation changed, the VirGL shaders are destroyed/reuploaded.

The shader subsystem can therefore update a program without requiring the caller to allocate a completely new Gfx3D instance.

## Frame lifecycle

A normal explicit frame is:

```text
gfx3d_begin
  -> clear / state / uniforms
  -> use program
  -> bind texture
  -> draw...
gfx3d_end
```

`gfx3d_begin` verifies that target and context have the same owner/context relationship.

It marks the context in-frame, binds the target and initializes viewport width/height to target dimensions.

In VirGL mode it starts a device batch.

## Forced-backend gate at frame begin

If the user explicitly forced VirGL and the backend is lost or no longer VirGL, `gfx3d_begin` fails immediately with `forced virgl unavailable`.

AUTO mode may already have degraded to software and can continue through the same public calls.

This makes backend policy observable at the frame boundary.

## Clear semantics

`gfx3d_clear` always clears the CPU target color and float-depth arrays.

Color components below zero are clamped to zero, but values above one are not explicitly clamped before integer conversion.

Depth cells are set to 1.0.

The `depth` argument causes depth testing to become enabled when nonzero; passing zero does not disable an already-enabled context.

Disabling depth is the job of `gfx3d_depth(ctx,0)`.

In VirGL mode a matching device clear is also emitted.

## Viewport limitation

`gfx3d_viewport` validates positive width/height and stores them.

The current implementation ignores X and Y completely.

More importantly, the software raster path uses target width/height directly rather than the stored viewport width/height.

The VirGL device path also builds draw state from target dimensions in the inspected revision.

Therefore the current viewport API is not yet a complete viewport implementation.

## Depth and cull backend mismatch

`gfx3d_depth` and `gfx3d_cull` store state in the context.

VirGL draw descriptors receive both flags.

The current software `soft_tri` path, however, always performs its float depth comparison/update and does not consult `cull`.

Thus these public controls are not semantically equivalent across backends in this revision.

This is an explicit compatibility gap that should be covered by cross-backend tests.

## Camera and matrix state

`gfx3d_camera` updates the global math3d camera, computes a context view matrix, computes perspective projection from target aspect ratio and stores FOV/near/far.

If a program is already bound, uniforms named `view` and `projection` are updated when those names exist.

`gfx3d_model` stores the model matrix and updates `model`.

If a `normalMatrix` uniform exists, a 3×3 normal matrix is computed from the model and uploaded.

## Uniform API

`gfx3d_uniform_mat4` converts ChrisOS matrix layout to GLSL ordering before storing the uniform.

`gfx3d_uniform_f` writes an arbitrary float vector/count accepted by the shader subsystem.

Both operate on the currently bound public program instance.

No program bound means failure.

Uniform values live in the `ShProgram`; VirGL draw code later serializes the needed constants.

## Draw preconditions

`gfx3d_draw` requires:

- an active frame;
- uploaded mesh;
- bound linked program;
- active target;
- vertex layout compatible with the program;
- at least one triangle.

Indexed meshes use groups of three `uint16_t` indices.

Non-indexed meshes use sequential groups of three vertices.

Out-of-range indices cause failure rather than undefined memory access.

## Software backend

The software backend runs the shader subsystem's software vertex and fragment execution.

Vertex outputs are divided by W to produce screen coordinates.

Varyings are interpolated perspective-correctly using reciprocal W.

Depth is stored as float in the public target.

Fragments with depth greater than or equal to the stored value are rejected.

If a public texture is bound, its CPU pixel buffer is passed to the software fragment shader.

This path is separate from the older `tri.c` rasterizer documented in the software-3D chapter.

## VirGL backend

For VirGL, Gfx3D builds a `Gfx3DDevDraw` containing shader handles, VBO/IBO IDs, stride, count, index mode, depth/cull flags, optional texture resource/view, layout offsets/formats and color/depth target resources.

Component count two maps to one VirGL format code and other current element sizes map to another code.

The backend converts this descriptor into VirGL state and draw commands.

Public callers never receive those device IDs.

## Mock backend

MOCK records strings such as:

```text
begin
clear
use
tex
draw
end
```

It is used to test API sequencing and object ownership without requiring pixel rendering or a device.

The mock log is bounded by a 1024-byte global array.

This backend is a validation tool, not a renderer.

## End of frame

`gfx3d_end` requires an active frame.

In VirGL mode it flushes/submits the device frame.

It then samples cumulative device submission/dword counters and adds deltas into public statistics.

Device backing bytes and VirGL live/peak object counts are also refreshed.

Finally, the context's frame flag is cleared.

Calling end without begin fails.

## Presentation

Two explicit presentation paths exist.

`gfx3d_present_scanout` requires an active VirGL target with a device color resource and asks the backend to make that resource the scanout.

`gfx3d_scanout_primary` restores the primary VirtIO-GPU 2D scanout.

These functions are meaningful only in freestanding/device operation.

Host builds return failure for direct scanout functions.

## Cleanup by owner

`gfx3d_drop_owner` destroys, in order:

- meshes;
- textures;
- program instances;
- targets;
- contexts

belonging to an owner.

It also cancels implicit-frame ownership for that owner.

This is the bulk-cleanup mechanism applications should use during teardown to avoid leaking table slots and backend resources.

## Statistics

`Gfx3DStats` exposes:

- submits and VirGL dwords;
- draws and triangles;
- uploads and uploaded bytes;
- readbacks;
- CPU mesh bytes;
- GPU backing bytes;
- target/depth bytes;
- live object counts;
- VirGL object live/peak counts;
- backend, forced mode and degraded flag.

Some fields such as `frame_cycles`, `visible_chunks` and `chunk_rebuilds` exist in the public structure but are not updated by the inspected `gfx3d.c` path.

They should not be treated as complete telemetry yet.

## Statistics reset

`gfx3d_stats_reset` clears event counters but preserves current live-object counts and persistent CPU memory totals for meshes, targets and depth.

This avoids reporting that resources vanished merely because counters were reset.

GPU backing and some device-derived values are refreshed when stats are queried under VirGL.

## Host tests

`tools/test_gfx3d_abi.c` provides broad API evidence.

It verifies matrix agreement between CPU math and shader execution, VirGL object handle exhaustion/release, batch rollover, linked-shader layout validation, MOCK sequencing, owner rejection, software rendering, target resizing, handle generation after destroy/recreate and 1000 mesh/texture create-destroy cycles.

At the end, `gfx3d_drop_owner` must return live counts to zero.

## Context-state test

`tools/test_gfx3d_ctx.c` tests an older/lower state-snapshot layer that saves camera, light and procedural texture state between `Gfx3DCtx` values.

It verifies that first load initializes defaults instead of importing foreign globals, then verifies isolation between two saved contexts.

It also tests voxel-world ownership.

That test complements, but is not identical to, the public handle-based `gfx3d.c` API.

## Current limitations

The API is global-table based and not generally thread-safe.

Tables are fixed-size.

Mesh device residency is only loosely associated with the first owner device context.

Texture `unit` is ignored.

Viewport X/Y are ignored and viewport dimensions are not fully honored by all paths.

Software depth/cull semantics are not identical to VirGL.

Public textures are limited to 1024×1024 and force opaque alpha.

These are concrete current boundaries, not intended final graphics semantics.

## Revision note

This chapter was created from ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. It treats Gfx3D as an ownership/handle/frame abstraction above both CPU shader execution and the VirGL device backend, without leaking VirtIO or VirGL IDs through the public interface.
