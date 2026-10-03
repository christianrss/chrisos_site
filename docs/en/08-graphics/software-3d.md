---
id: software-3d
lang: en
type: technical-chapter
volume: 08-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/math3d.c
  - kernel/gfx/mesh.c
  - kernel/gfx/mesh.h
  - kernel/gfx/voxel.c
  - kernel/gfx/voxel.h
  - kernel/gfx/tri.c
  - kernel/gfx/zbuf.c
  - kernel/gfx/tex.c
  - kernel/gfx/shade.c
  - kernel/gfx/scene.c
  - kernel/gfx/tile.c
  - kernel/gfx/gfx3d_ctx.c
  - kernel/lang/clvm_sys.c
  - tools/test_mesh.c
  - tools/test_cube_mesh.c
  - tools/test_cube_mesh_f.c
  - tools/test_chunk_mesh.c
  - tools/test_scene.c
symbols:
  - mesh_draw
  - mesh_draw_f
  - mesh_transform
  - voxel_world_draw
  - voxel_set
  - voxel_get
  - voxel_claim
  - voxel_release
  - scene_visible
  - scene_draw
depends_on:
  - textures
  - depth-buffer
related:
  - parallel-raster
  - gfx3d-api
  - mine-graphics
---

# Software 3D renderer

## Scope

ChrisOS does not have one monolithic software 3D renderer. It has several rendering paths built from common math, rasterization, depth, texture and shading modules.

The important paths are the legacy CLVM-backed integer mesh renderer, the float mesh renderer, the chunked voxel renderer and the lightweight scene/node renderer.

They share infrastructure but do not share every semantic. Near clipping, depth-clear ownership, geometry format and parallelization differ among them.

## Common pipeline

A useful conceptual pipeline is:

```text
geometry
  -> model transform
  -> view transform
  -> visibility / clipping
  -> projection
  -> triangle rasterization
  -> depth test
  -> texture / lighting
  -> framebuffer
```

This sequence describes the architecture, not a single function.

The legacy mesh path skips some clipping work. The voxel path implements a stronger near-plane stage. The scene path is a simplified projected representation rather than a full arbitrary-mesh scene graph.

## Global versus contextual state

Several legacy modules maintain global state:

- camera and screen dimensions in math3d;
- active z-buffer and dimensions;
- light state;
- selected texture slot and offsets.

Newer `Gfx3DCtx` stores snapshots of camera, shading and texture state.

Loading a context copies its values into those globals before rendering.

This gives a migration path toward per-context behavior without rewriting every low-level function at once.

It does not make the low-level renderer naturally reentrant.

## CLVM mesh ABI

`mesh_draw` reads geometry from CLVM VM memory.

The memory layout is:

```text
V vertices:
  int32 x
  int32 y
  int32 z

T triangles:
  int32 i0
  int32 i1
  int32 i2
```

Each vertex uses 12 bytes and each triangle triplet uses 12 bytes.

The integer coordinates are converted with `MODEL_SCALE` before projection.

## Mesh validation

`mesh_ok` requires a non-null VM, non-null framebuffer, at least three vertices and at least one triangle.

It enforces:

```text
MESH_MAX_V = 2048
MESH_MAX_T = 4096
```

The base address must be nonnegative and the complete vertex-plus-index region must fit inside VM memory.

Triangle indices are validated individually before use.

Invalid geometry returns -1 instead of reading outside the VM.

## Global mesh staging arrays

Projected X/Y/depth, visibility flags, world positions and filtered triangle indices are stored in fixed global arrays.

This avoids allocation inside each draw.

It also means two simultaneous mesh draws would reuse the same staging memory.

The current renderer therefore assumes serialization or higher-level exclusion around these routines.

## mesh_draw transformation

`mesh_draw` sets the software screen size, configures z-buffer dimensions and clears depth.

It builds a view matrix from the current camera and a Y rotation from the supplied integer degree angle.

The effective matrix is:

```text
view * rotation
```

Each model vertex is converted to float and passed through `project_vertex`.

## Legacy visibility rule

If `project_vertex` receives a point whose transformed Z is <=0, it reports that point as invisible.

During triangle assembly, if any of the three referenced vertices is invisible, the whole triangle is skipped.

This is primitive rejection.

It is not geometric clipping.

A triangle crossing the camera plane can disappear abruptly rather than being cut at the boundary.

## Depth clear in mesh_draw

`mesh_draw` calls `zbuf_clear` internally.

That makes one invocation behave like a fresh depth frame.

This is convenient for a standalone demo mesh but has an important compositing consequence: calling `mesh_draw` for object B after object A clears the depth written by A.

The function is therefore not a natural multi-object scene primitive unless its depth lifecycle is changed or wrapped differently.

## Automatic tile threshold

In freestanding builds, `mesh_draw` chooses the tiled path when:

```text
w * h >= 640 * 400
```

Larger targets call `tile_mesh_raster`.

Smaller ones loop over accepted triangles and call `tri_fill`.

The threshold is an implementation policy, not an exposed tuning parameter.

## Float mesh ABI

`mesh_draw_f` uses the same broad memory structure, but vertex components are interpreted as 32-bit IEEE-754 floats rather than scaled integers.

Triangle indices remain integer triplets after the vertex array.

The function also receives model translation and yaw explicitly.

## Float transform composition

The function constructs:

```text
model = translation * rotation_y
mvp   = view * model
```

Each source vertex is transformed through `model` to record world-space coordinates.

Projection is performed using the combined view/model transform.

The separate world-space position is needed for triangle normals.

## mesh_draw_f does not clear depth

A critical difference is that `mesh_draw_f` configures z-buffer size but does not call `zbuf_clear`.

That allows multiple float meshes to participate in one shared depth frame, provided the caller cleared and bound the intended buffer beforehand.

The difference between `mesh_draw` and `mesh_draw_f` is therefore semantic, not merely numeric vertex format.

Documentation and callers must not assume all mesh entry points have the same frame ownership.

## Face normal generation

For every accepted float triangle:

```text
e0 = world[b] - world[a]
e1 = world[c] - world[a]
normal = normalize(cross(e0,e1))
```

The renderer computes one geometric normal per triangle.

There are no stored authored vertex normals in the mesh ABI.

Smooth shading across shared vertices is therefore not represented by this format.

## Palette and texture mode

When `color < 16`, the float path gets an RGB value from the palette and shades it with the triangle normal.

When `color >= 16`:

```text
texid = color - 16
```

and `tri_fill_lit` is called.

The triangle receives canonical UV coordinates:

```text
(0,0)
(1,0)
(0,1)
```

rather than UVs loaded from VM memory.

## Material encoding edge

Values 16..31 map naturally to the sixteen texture slots.

A larger color value produces an invalid explicit texture ID.

The texture sampler then falls back to the currently selected global texture slot.

So malformed material encoding can depend on renderer state rather than producing an explicit error.

This should be considered an API hardening target.

## mesh_transform

`mesh_transform` is a separate geometry mutation helper.

It reads a 4×4 float matrix from VM memory and applies it in place to a sequence of vertices.

The vertex representation used by this helper is the scaled integer representation.

Matrix and vertex memory ranges are validated before modification.

It does not rasterize or perform visibility tests.

## Voxel world dimensions

The voxel subsystem uses chunks with:

```text
CHUNK_N = 16
```

The world has 8 chunks in X, 4 in Y and 8 in Z.

Logical block dimensions are therefore:

```text
128 × 64 × 128
```

The block array is allocated lazily on first use.

## Voxel ownership

The subsystem includes `voxel_claim(slot)` and `voxel_release(slot)`.

Only one slot can own the voxel world at a time unless the same slot reclaims it.

This is a coarse ownership mechanism around global world data.

It prevents two independent CLVM applications from casually mutating the same voxel world through the intended API.

## Block IDs

`voxel_set` validates world coordinates.

Block ID values below zero become zero.

Values above 15 become 15.

ID zero means empty space.

Nonzero IDs also act as texture IDs when faces are rendered.

## Dirty chunk propagation

Editing a voxel marks its own chunk dirty.

If the voxel lies on a chunk boundary, the adjacent chunk is also marked dirty for that axis.

This is necessary because changing one boundary block can expose or hide the neighbor chunk's face.

The dirty flag defers mesh rebuilding until rendering needs that chunk.

## Chunk face extraction

`rebuild_chunk` scans all 16³ cells.

For every nonzero block it checks six neighboring directions.

A face is stored only when the neighbor is empty or outside the world.

Internal faces between two solid blocks are therefore removed before rasterization.

The face array grows from an initial capacity of 64 up to:

```text
FACE_CAP_MAX = 8192
```

## Chunk allocation behavior

When face capacity must grow, a new array is allocated, old faces are copied and the old allocation is freed.

If allocation fails, or the chunk already reached the maximum capacity, `mesh_push` fails and chunk rebuild stops early.

The current rebuild function does not expose a detailed error to the eventual caller.

A saturated/failed chunk can therefore have incomplete face output without a rich diagnostic channel.

## Camera-local voxel render window

`voxel_world_draw` does not scan every face in the world blindly.

It builds a camera-centered region roughly:

- X: camera ±48;
- Y: camera ±32;
- Z: camera ±48.

Chunks outside this region are skipped.

This is a coarse spatial culling layer before dirty rebuild and per-face rendering.

## Voxel face pipeline

Each stored face is reconstructed as four world-space corners.

A face normal is transformed into view space.

The corners are transformed into camera space and receive the fixed quad UV layout.

The quad is split into two triangles.

Each triangle passes through near clipping before projection.

The resulting polygon is then rasterized as one or two textured triangles.

## Near clipping difference

The voxel path uses an explicit near plane:

```text
z >= 0.08
```

Edges crossing the plane generate interpolated position and UV values.

This is stronger behavior than legacy mesh rejection and avoids simply dropping a face that partially crosses the camera.

## Voxel depth lifecycle

`voxel_world_draw` configures z-buffer dimensions and clears depth internally.

Like `mesh_draw`, it assumes ownership of a fresh depth frame.

Mixing voxel output with previously rendered float meshes can therefore erase earlier depth unless the calling architecture deliberately orders and refactors these operations.

## Voxel texture mapping

Visible block IDs 1..15 are passed directly to `tri_fill_tex`.

The procedural atlas therefore doubles as a material table.

Each face covers a complete 0..1 texture square.

There is no block-specific UV scale, atlas sub-rectangle or external material descriptor.

## Software lighting model

`shade_phong` implements a compact Phong-like model.

It normalizes the supplied normal.

Ambient, diffuse and specular coefficients are:

```text
ka = 0.22
kd = 0.70
ks = 0.28
```

Specular response uses a fixed exponent-16 approximation implemented as repeated squaring.

This is a demonstration lighting model, not physically based shading.

## Light and view cache

The module caches normalized light/view directions.

The cache is invalidated when light state changes or when camera position changes.

The view vector is derived from camera position rather than yaw/pitch, so pure camera rotation does not trigger the same cache invalidation.

This reflects the simplified lighting assumptions of the current renderer.

## Scene subsystem

`scene.c` provides a small higher-level layer with:

```text
SCENE_MAX = 32
```

Each node stores used flag, mesh ID, integer position, yaw and color.

The freestanding draw path currently renders each visible node as a simple projected triangle.

It does not dispatch the node's mesh ID through `mesh_draw_f`.

Therefore this is not yet a fully general mesh scene graph.

## Scene culling

`scene_in_frustum` approximates camera orientation with four yaw quadrants.

It computes forward and side distances.

Nodes behind the camera or sufficiently outside a forward wedge are rejected.

This is object culling, not canonical six-plane frustum clipping.

`scene_visible` linearly scans the fixed node array.

## Scene band parallelism

Freestanding `scene_draw` splits the image into up to four horizontal bands.

Each band becomes a job.

Every job loops through visible nodes, but `tri_fill_clip` limits writes to that band's Y range.

This gives each band disjoint pixel ownership and avoids the same-pixel competition possible in arbitrary triangle/tile scheduling.

## Animation

The scene layer also owns sixteen animation key slots.

`anim_sample` searches for the closest key at/before time and at/after time.

Position and yaw are linearly interpolated with integer arithmetic.

The animation applies node transforms only; there is no skeletal animation or vertex skinning.

## Error and fault containment

Mesh functions return -1 on invalid VM memory layouts or illegal triangle indices.

Voxel initialization returns failure if block storage cannot be allocated.

Voxel face growth can stop on allocation failure or capacity limit.

The low-level triangle rasterizer itself mostly uses silent no-draw behavior rather than rich errors.

Diagnosing a missing frame therefore requires understanding which layer owns the failure signal.

## Performance structure

The major costs are separable:

- vertex transformation/projection: O(V);
- triangle validation/filtering: O(T);
- rasterization: proportional to clipped screen-space bounding area;
- one chunk rebuild: O(16³ * 6 neighbor checks);
- scene visibility: O(32);
- animation sampling: O(16);
- ordinary texture sampling: O(1).

After coarse culling, pixel work and visible face count are usually the dominant factors.

## Executable evidence

`tools/test_mesh.c` verifies that a simple CLVM-backed triangle renders at least one pixel.

`tools/test_cube_mesh.c` builds an eight-vertex, twelve-triangle integer cube, rotates it and requires more than 2,000 painted pixels.

`tools/test_cube_mesh_f.c` builds the float version, uses `mesh_draw_f` and requires both more than 2,000 painted pixels and broad horizontal coverage.

`tools/test_chunk_mesh.c` creates voxel blocks, renders more than 500 pixels with multiple colors and verifies that a second unchanged render does not increase the chunk rebuild count.

`tools/test_scene.c` covers scene visibility decisions and keyframe interpolation.

## What the tests do not prove

The current tests do not directly verify multi-mesh shared-depth composition, the clear difference between `mesh_draw` and `mesh_draw_f`, all near-plane clipping cases, chunk-face capacity exhaustion, texture fallback IDs or concurrent renderer state isolation.

They establish meaningful bring-up evidence, but not a complete graphics conformance suite.

## Recommended regression layers

A stronger test hierarchy would include pure math tests, isolated raster/depth tests, deterministic texture/shade tests, single-mesh image checksums, multi-mesh depth composition, voxel near-plane edge cases and QEMU integration images.

Failure-path tests should also deliberately supply invalid VM addresses, invalid triangle indices and chunk allocation pressure.

## Debugging order

When a mesh disappears, first distinguish input validation from visibility rejection.

Then check camera-space Z and whether the path performs clipping or whole-triangle rejection.

Next inspect screen coordinates, raster coverage and z-buffer state.

Only after a visible fragment is confirmed should texture and lighting be investigated.

For voxel defects, check dirty-chunk rebuild count before blaming rasterization.

## Current limitations

The renderer combines global state with context save/load, has a minimal mesh vertex format, uses affine texturing and simple Phong-like lighting, and has inconsistent depth-clear ownership between entry points.

Legacy mesh uses primitive rejection instead of near clipping.

The scene layer is simplified.

Despite these constraints, the system is a substantial executable CPU renderer integrated with CLVM and ChrisOS graphics state.

## Revision note

This chapter was created from ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, documenting mesh, voxel and scene as separate paths with shared infrastructure rather than pretending they are one uniform renderer.
