---
id: triangle-rasterization
lang: en
type: technical-chapter
volume: 09-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/tri.c
  - kernel/gfx/tri.h
  - kernel/gfx/zbuf.c
  - kernel/gfx/tile.c
  - kernel/gfx/tri_bin.c
  - kernel/gfx/mesh.c
  - kernel/gfx/voxel.c
  - tools/test_tri.c
  - tools/test_mesh.c
  - tools/test_chunk_mesh.c
  - tools/test_tile.c
  - tools/test_tile_bin.c
symbols:
  - edge
  - clip_box
  - tri_fill
  - tri_fill_clip
  - tri_fill_u32
  - tri_fill_lit
  - tri_fill_tex
  - tile_mesh_raster
  - tri_bin_add
depends_on:
  - clipping
related:
  - depth-buffer
  - textures
  - software-3d
  - parallel-raster
---

# Triangle rasterization

## Scope

ChrisOS rasterizes projected software triangles in `kernel/gfx/tri.c`. Inputs are already screen-space X/Y plus integer depth; textured variants add UV and, in one path, normals. Camera transforms, projection and near-plane clipping have already happened.

The rasterizer decides pixel coverage, interpolates attributes, runs the depth test and writes visible color. Its deliberately small surface makes the complete hot path inspectable and useful as a teaching implementation.

## Entry points

`tri_fill` draws a palette triangle over the framebuffer. `tri_fill_clip` adds a caller rectangle. `tri_fill_u32` accepts direct RGB. `tri_fill_lit` interpolates UV and normals and can sample a texture. `tri_fill_tex` uses UV plus one face-level normal.

All variants share the same edge-function coverage model.

## Edge function

Coverage uses:

```text
edge(A,B,P) =
    (Px-Ax)(By-Ay) -
    (Py-Ay)(Bx-Ax)
```

The products are evaluated in `int64_t`. This widens the practical coordinate range versus 32-bit intermediate multiplication.

The signed triangle area is the same function evaluated at the third vertex.

## Degenerate triangles

Area zero means the three projected points are collinear. The function returns immediately and does not reinterpret the primitive as a line or point.

Triangle fill therefore requires nonzero screen-space area.

## Winding normalization

If area is negative, vertices 1 and 2 are swapped. Associated depth, UV and normal attributes are swapped with them. Area is then negated.

Coverage can consequently use the same condition for both input orientations:

```text
w0 >= 0 && w1 >= 0 && w2 >= 0
```

Callers do not need to pre-normalize clockwise/counter-clockwise winding merely to obtain fill.

## Bounding box

The rasterizer computes min/max X/Y from the vertices and intersects that box with the explicit clip rectangle and framebuffer boundaries.

Upper clip coordinates are exclusive. `clip_x1` and `clip_y1` become maximum valid coordinates one less than the endpoint.

An empty intersection exits before pixel loops. This is both a performance optimization and a memory-safety boundary.

## Incremental edge evaluation

At each row start, the three edge values are evaluated at the first candidate pixel. Moving one pixel in X changes each value by a constant.

The code precomputes:

```text
col_step0 = y2 - y1
col_step1 = y0 - y2
col_step2 = y1 - y0
```

The horizontal loop then uses additions instead of recomputing full products. Row-start values are recalculated for each Y.

## Sample location

Coverage is evaluated at integer `(x,y)`. There is no +0.5 pixel-center offset.

That convention can differ from modern API reference rasterizers. Pixel-exact comparisons must account for it.

## Shared-edge ownership

Every edge uses `>= 0`. No explicit top-left rule assigns a shared edge exclusively to one adjacent triangle.

Two coplanar triangles can both classify a shared-edge sample as covered. The strict depth test usually lets the first equal-depth write remain and rejects the second.

This avoids a second equal-depth color write but means exact shared-edge ownership is partly draw-order dependent. The current tests do not define a formal top-left contract.

## Flat-color path

`tri_fill_u32` interpolates depth:

```text
z = (w0*z0 + w1*z1 + w2*z2) / area
```

Negative interpolated Z is clamped to zero.

Only a successful `zbuf_test` causes the RGB value to be written. Coverage alone is not enough to update the framebuffer.

`tri_fill_clip` maps a palette index through `gfx2d_color` and delegates to this function. `tri_fill` delegates again with the whole framebuffer as clip rectangle.

## Barycentric coefficients

The lit/textured paths convert edge weights to floating coefficients:

```text
bw0 = w0 / area
bw1 = w1 / area
bw2 = w2 / area
```

They are reused for UV and, when present, normal interpolation. Within the triangle they sum approximately to one, subject to float conversion.

## Affine interpolation

UV coordinates are interpolated directly with screen-space barycentric coefficients. This is affine interpolation.

The rasterizer does not carry reciprocal W and does not reconstruct U/V from U/W, V/W and 1/W. Triangles with large depth variation can therefore show texture distortion relative to a perspective-correct pipeline.

Normals in `tri_fill_lit` are likewise interpolated affinely.

## Depth interpolation

Depth is also interpolated linearly in screen space. The incoming software depth normally derives from positive camera-space Z scaled by 65536.

This is internally consistent with the current renderer but is not the same depth interpolation produced by a conventional homogeneous GPU pipeline.

## tri_fill_lit

`tri_fill_lit` obtains a base color from the palette or uses gray fallback. It interpolates U/V and XYZ normal components for every covered fragment.

If `texid >= 0`, `tex_sample` supplies source color; otherwise base color is used. Color and the interpolated normal are passed to `shade_phong`.

The routine does not explicitly renormalize the interpolated normal before that call. Lighting therefore depends on both the inputs and shade-layer behavior.

## tri_fill_tex

The voxel-oriented path interpolates UV but receives one normal for the whole triangle.

Lighting is computed once before the loops using white as the base. Each sampled texel is multiplied channel-by-channel by that lighting result.

This is cheaper than evaluating Phong lighting per fragment and matches a voxel face that has a constant normal.

## Depth-before-texture order

The depth test occurs before texture sampling and final shading/modulation.

Fragments already hidden by nearer geometry therefore avoid texture work. This is a useful early-rejection property.

## Clip rectangles

All core routines accept explicit bounds. Besides framebuffer safety, those bounds let higher layers partition work.

The scene renderer can use horizontal bands. The tile renderer can invoke a triangle once per overlapping 64×64 region while constraining each invocation to that tile.

The scalar coverage algorithm does not change; only its writable rectangle changes.

## Tile rasterization

`tile_mesh_raster` computes each triangle's screen bounding box and calls `tri_bin_add`.

The bin expands a triangle into one packed entry for every overlapping 64×64 tile. Entries encode triangle ID, tile Y and tile X.

A job is submitted for each triangle/tile pair, and that job calls `tri_fill_clip` with the tile rectangle.

Tile rasterization is therefore a scheduling layer around the scalar rasterizer rather than a second coverage algorithm.

## Bin capacity

`TriBin` stores at most 4096 entries. The cap applies to triangle/tile overlaps, not source triangles.

A large triangle can consume many entries. Once the fixed array is full, `tri_bin_add` stops adding later overlaps.

The current bin does not dynamically grow or return detailed overflow information.

## Parallel ownership caveat

Different triangles overlapping the same tile create distinct jobs that can target the same pixels.

Framebuffer stores and z-buffer updates are ordinary memory operations, not one atomic fragment transaction.

The clip rectangle alone does not guarantee deterministic overlapping-fragment results if the scheduler executes competing jobs simultaneously. The parallel-raster chapter treats that ownership problem separately.

## Complexity

For clipped bounding area A, the base loop is O(A). Area, winding and box clipping are O(1).

Flat fill performs coverage, depth interpolation and z-test. Textured/lit paths add floating interpolation, texture lookup and lighting.

Projected pixel area and shading mode can matter more than raw triangle count.

Tile binning adds work proportional to triangle/tile overlaps.

## Executable evidence

`tools/test_tri.c` directly tests flat rasterization. A red triangle must paint a known interior pixel and more than 80 pixels overall. A nearer green triangle then replaces the red value at an overlapping sample. A larger triangle must cover more than 400 pixels and several columns.

`tools/test_mesh.c` supplies one triangle through CLVM mesh memory and requires `mesh_draw` to change at least one framebuffer pixel.

`tools/test_chunk_mesh.c` provides higher-level voxel/textured integration.

`tools/test_tile.c` compares parallel clear with one and two workers. `tools/test_tile_bin.c` verifies basic tile-bin generation. Neither proves deterministic rendering for overlapping triangle jobs.

## Validation gaps

The inspected tests do not directly fix exact shared-edge ownership, byte-identical CW/CCW output, all off-screen boundary cases, affine UV values at selected pixels, normal interpolation, 4096-entry overflow or overlapping parallel determinism.

Useful future tests include adjacent triangle pairs, near-degenerate geometry, one-pixel triangles, exact clip-boundary alignment and golden images for textured perspective distortion.

Property tests can permute vertices and compare normalized coverage.

## Raster precision and overflow reasoning

Although edge products are 64-bit, screen coordinates still arrive as `int`, and raster bounds ultimately become framebuffer indices. Correct callers should keep projected coordinates in a reasonable range before rasterization.

The bounding-box clip protects framebuffer access, but it does not make arbitrary extreme integer arithmetic semantically meaningful. Projection and clipping remain responsible for keeping geometry sane.

Depth interpolation multiplies edge weights by signed 32-bit depth values. This is practical for current display sizes and depth ranges, but the renderer is an engineering implementation rather than an arbitrary-precision geometry system.

## Attribute continuity across clipped triangles

Near-plane clipping in the voxel path can turn one source triangle into a quad and then two raster triangles. The generated U/V coordinates are shared consistently at the newly created vertices.

Once those triangles reach `tri_fill_tex`, each is rasterized independently. Because interpolation is affine and shared-edge ownership is not top-left specified, exact texel/color ownership on the diagonal between the two generated triangles can still depend on integer sampling and depth equality.

This is another reason geometry clipping correctness and raster edge rules must be validated separately.

## Interaction with depth equality

Shared-edge coverage and depth comparison are coupled.

Changing the depth function from LESS to LEQUAL could alter which adjacent primitive writes duplicated shared-edge samples even if the edge equations remained unchanged.

A future formal raster specification should define coverage, sample position and depth comparison together.

## State dependencies

The rasterizer receives the color buffer explicitly but obtains depth through the globally bound z-buffer module.

Therefore two invocations using different color targets are not automatically independent unless the intended depth target is also rebound correctly.

This asymmetry is easy to miss: color ownership is explicit in the function arguments while depth ownership is implicit global state.

Higher-level graphics contexts must establish both before drawing.

## Failure modes

A null color pointer, nonpositive width or nonpositive height causes an immediate return.

Invalid palette indices are rejected by `tri_fill_clip`.

A zero-area triangle is ignored.

An empty clipped box is ignored.

A fragment rejected by depth does not update color.

These are silent no-draw conditions rather than error returns because the API is `void`.

Diagnostics therefore need to inspect inputs or use higher-level tests; the rasterizer itself does not emit detailed fault codes.

## Performance interpretation

The bounding rectangle may contain many pixels that are outside the triangle, so O(A) measures candidate area rather than actual covered samples.

Skinny diagonal triangles can have large bounding boxes relative to their true area and therefore poor efficiency.

Tile/scissor partitioning can reduce unrelated pixel ranges but does not eliminate the fundamental bounding-box scan inside each clipped region.

Future SIMD or hierarchical edge rejection could improve this while preserving the same coverage contract.

## Debugging invariants

When a primitive paints nothing, first confirm nonzero area. Then inspect the clipped bounding box. If the box is valid, inspect edge signs. If coverage exists but color is absent, inspect depth.

For textured geometry, a visible fragment with wrong color points toward UV, texture or lighting rather than coverage.

This stage-by-stage approach separates raster defects from earlier camera, projection and clipping defects.

## Current limitations

The software rasterizer uses integer sample locations, no explicit top-left rule, affine attributes and a simple screen-space depth model.

It is intentionally small and useful for ChrisOS bring-up and experimentation, not a pixel-exact reproduction of a modern GPU specification.

## Revision note

This chapter was created from ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, using source and host tests as primary evidence.
