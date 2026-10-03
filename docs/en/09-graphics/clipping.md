---
id: clipping
lang: en
type: technical-chapter
volume: 09-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/voxel.c
  - kernel/gfx/math3d.c
  - kernel/gfx/mesh.c
  - kernel/gfx/tri.c
  - kernel/gfx/tri.h
  - kernel/gfx/scene.c
  - kernel/gfx/gfx3d.c
  - LIB/CLIP.CC
  - tools/test_math3d.c
  - tools/test_scene.c
  - tools/test_chunk_mesh.c
symbols:
  - clip_near_tri
  - draw_clipped
  - project_view
  - project_vertex
  - tri_fill_clip
  - tri_fill_u32
  - scene_in_frustum
  - scene_visible
  - clip_aabb
  - clip_ray_aabb
depends_on:
  - matrix-transformations
related:
  - triangle-rasterization
  - depth-buffer
  - software-3d
  - mine-graphics
---

# Clipping, rejection and visibility boundaries

## Scope

"Clipping" refers to several different operations in the current ChrisOS tree. They should not be collapsed into one concept.

The voxel renderer performs true geometric clipping of triangles against a near plane. The generic software mesh path mostly rejects triangles when any projected vertex is behind the camera. The rasterizer restricts pixel iteration to a screen/scissor rectangle. The scene subsystem performs coarse frustum culling before drawing. A separate `LIB/CLIP.CC` contains gameplay collision helpers whose name includes "clip" but which are not polygon clipping.

This chapter separates those mechanisms and documents where each one applies.

## Why clipping is necessary

Perspective projection contains division by depth.

A vertex approaching camera-space Z=0 can produce extremely large projected X/Y values. A vertex behind the camera has a sign that no longer represents a point visible through the forward camera.

Simply projecting every vertex is therefore unsafe as a complete polygon pipeline.

For a triangle crossing the camera plane, the desired behavior is normally to preserve the visible part, introduce intersection vertices and discard only the portion outside the visible half-space.

That is different from dropping the entire triangle.

## Near-plane convention in the voxel renderer

`voxel.c` transforms each face vertex into camera space.

The voxel-specific clipper uses:

```text
near = 0.08
inside ⇔ z >= near
```

The value is a software-renderer near plane, not the `znear` parameter stored by the newer `gfx3d` camera context.

A voxel face is first split into two triangles. Each triangle is clipped independently before projection.

## ClipV attributes

The clipping vertex structure contains:

```text
x, y, z
u, v
```

This is important because clipping geometry without interpolating texture coordinates would create discontinuities along the generated edge.

Normals are not stored per clipped vertex in this path. A transformed face normal is computed separately and passed as one face-level normal to the textured rasterizer.

## clip_near_tri algorithm

`clip_near_tri` is a one-plane polygon clipper specialized to a triangle.

It iterates the three directed edges:

```text
a = input[i]
b = input[(i+1) mod 3]
```

For each edge it classifies both endpoints against `z >= 0.08`.

The cases are:

| a | b | output |
|---|---|---|
| inside | inside | b |
| inside | outside | intersection |
| outside | inside | intersection, then b |
| outside | outside | nothing |

The intersection factor is:

```text
t = (near - a.z) / (b.z - a.z)
```

X, Y, U and V are linearly interpolated with the same `t`, and the generated Z is set exactly to `near`.

This is equivalent to the edge-processing principle used by Sutherland-Hodgman clipping, specialized to one plane and at most three input vertices.

## Output cardinality

A triangle clipped against one half-space can produce:

- 0 vertices: fully outside;
- 3 vertices: fully inside or one surviving corner plus two intersections;
- 4 vertices: two original inside vertices plus two intersections.

The output buffer is therefore exactly four `ClipV` entries.

No dynamic allocation is required.

## Re-triangulation

`draw_clipped` ignores results with fewer than three vertices.

For three vertices it emits one triangle:

```text
0, 1, 2
```

For four vertices it emits two:

```text
0, 1, 2
0, 2, 3
```

Every output vertex is then passed to `project_view`.

Because generated vertices are fixed at Z=0.08 and original retained vertices are at or beyond that plane, the projection helper should not encounter non-positive Z for a correctly clipped polygon.

## Texture-coordinate interpolation

Generated intersections interpolate U/V linearly in camera-space edge parameter `t`.

That preserves continuity at the clipping boundary before the resulting triangles enter `tri_fill_tex`.

The rasterizer itself currently performs affine interpolation of U/V from screen-space barycentric weights. It does not implement perspective-correct texture interpolation with U/W and V/W.

Near-plane geometric clipping and perspective-correct sampling are separate issues.

## Voxel face flow

The full path is:

```text
voxel face
   ↓
four world-space corners
   ↓
view transform
   ↓
two camera-space triangles
   ↓
clip_near_tri(z >= 0.08)
   ↓
3/4-vertex polygon
   ↓
project_view()
   ↓
tri_fill_tex()
```

This is currently the clearest true polygon-clipping implementation in the software graphics stack.

## Legacy mesh behavior is rejection, not clipping

`mesh_draw` and `mesh_draw_f` call `project_vertex` independently for every vertex.

`project_vertex` returns false when transformed Z <= 0.

During triangle collection, if any of the three referenced vertices has `g_vis == 0`, the complete triangle is skipped.

Therefore a triangle crossing the camera plane can disappear instead of being cut at the boundary.

This is a simpler bring-up strategy, but it can create visible popping when geometry approaches the camera.

Documentation should call this vertex/triangle rejection, not near-plane clipping.

## The near values are not unified

There are multiple depth thresholds in the graphics stack.

The voxel clipper uses 0.08. The `gfx3d` context defaults its camera near plane to 0.1 and accepts caller-provided `znear`. The legacy `project_view` merely requires Z>0.

These values belong to different pipelines.

A future consolidation should define whether software voxel, software mesh and shader/GPU paths share a common camera projection contract.

## Screen-space clipping in the triangle rasterizer

After projection, `tri_fill_u32`, `tri_fill_lit` and `tri_fill_tex` compute a triangle bounding box.

`clip_box` intersects that box with:

- the supplied clip rectangle;
- framebuffer X range;
- framebuffer Y range.

If the resulting rectangle is empty, rasterization returns immediately.

Otherwise the rasterizer iterates only pixels inside that clipped bounding rectangle and performs barycentric inside tests there.

This is screen-space work reduction and memory-safety bounding. It does not create new polygon vertices.

## tri_fill_clip as a scissor-like boundary

`tri_fill_clip` is a wrapper that converts a palette index to RGB and calls `tri_fill_u32` with an explicit rectangle:

```text
clip_x0, clip_y0, clip_x1, clip_y1
```

The ordinary `tri_fill` function simply uses the whole framebuffer as that rectangle.

The scene renderer uses the explicit form to divide work into horizontal bands. In that case clipping prevents each band worker from writing outside its assigned Y interval.

Thus the rectangle has both rendering and parallel-work ownership significance.

## Coarse scene frustum culling

`scene_in_frustum` is not exact homogeneous frustum clipping.

It calculates integer `fwd` and `side` values using one of four yaw quadrants.

An object is rejected when:

```text
fwd + radius < 8
```

or when lateral magnitude exceeds roughly:

```text
fwd + radius
```

This forms a coarse forward wedge.

`scene_visible` scans the fixed scene array and records nodes passing that test.

The purpose is to avoid drawing obviously irrelevant scene nodes, not to compute exact polygon intersections with six clip planes.

## Culling versus clipping

Culling decides that an entire primitive/object can be skipped.

Clipping preserves part of a primitive by generating new boundaries.

Examples in ChrisOS:

- `scene_in_frustum`: object culling;
- `project_vertex(z<=0)` + triangle skip: primitive rejection;
- `clip_near_tri`: geometric clipping;
- `clip_box`: pixel-work bounding/scissor.

Using precise terminology matters when debugging disappearing geometry.

## gfx3d software backend

The newer software `gfx3d` path executes the vertex shader and receives four-component clip positions.

`soft_tri` rejects a triangle only if a vertex has `w` extremely close to zero, then computes:

```text
ndc_x = x / w
ndc_y = y / w
```

and maps the result to target pixels.

Its raster bounding box is clamped to the target dimensions.

The inspected routine does not implement a full canonical clip-volume polygon stage for ±X, ±Y, near and far planes before the perspective divide.

This is an important limitation of the current software shader backend.

## Hardware/VirGL path

The `gfx3d` API can also target a VirGL/device backend. In that path, standard graphics-pipeline clipping can be performed by the graphics backend rather than the legacy software helpers described here.

The host-side API still constructs conventional projection matrices and shader clip positions.

The existence of a hardware path does not imply that the software fallback has identical clipping behavior in every edge case.

## Depth is not clipping

The z-buffer answers a different question: among fragments that survive geometry/raster bounds, which one is nearer at a pixel?

A fragment being hidden by depth is not the same as the triangle being outside the viewing volume.

This distinction becomes important when debugging missing geometry. Near-plane errors occur before normal z-buffer visibility resolution.

## LIB/CLIP.CC is gameplay collision

`LIB/CLIP.CC` contains `clip_aabb` and `clip_ray_aabb` and is used by Mine Chris/physics-oriented ChrisC code.

`clip_aabb` checks overlap between two axis-aligned cubes described by position plus a single size.

Despite its name, `clip_ray_aabb` is not a general graphics polygon clipper and not a robust three-axis slab ray/AABB test. In the nonzero-X case it derives `t` only from the X direction and X box interval.

It belongs to gameplay collision helpers and should not be cited as the implementation of view-frustum clipping.

## Correctness edge cases

For `clip_near_tri`, the denominator `b.z - a.z` is guarded by `b.z != a.z` before intersection.

An edge with both endpoints exactly on the near plane is classified inside/inside and retains the endpoint.

An edge parallel to the plane with both points on the same side does not require an intersection.

The use of a fixed Z for generated vertices avoids tiny negative depth caused by interpolation around the boundary.

## Attribute scope

The voxel near clipper preserves position and UV.

It does not interpolate a per-vertex normal, color, tangent or arbitrary shader varying because that renderer does not carry those attributes in `ClipV`.

A generalized clipper for the programmable pipeline would need to preserve every varying that must remain continuous after clipping.

## Complexity

For a single triangle and one plane, `clip_near_tri` performs exactly three edge classifications: O(1).

Re-triangulation produces at most two triangles.

The rasterizer bounding-box clipping is also O(1), while the later pixel iteration cost depends on the intersected screen-space area.

`scene_visible` is O(N) in scene nodes.

The benefit of culling/clipping is not the cost of the operation itself but the raster/fragment work avoided afterward.

## Executable evidence

`tools/test_math3d.c` verifies that a point with negative Z is rejected by the legacy projector. That is evidence for the rejection rule, not polygon clipping.

`tools/test_scene.c` verifies representative frustum decisions: an object in front is accepted, one behind is rejected and a far lateral object is rejected. It therefore covers the coarse scene culling contract.

`tools/test_chunk_mesh.c` builds voxel data, renders it twice and checks that substantial pixels are produced while unchanged chunks do not rebuild on the second frame. Because the voxel renderer includes `clip_near_tri`, this is integration coverage of the path.

However, no dedicated test in the inspected tree directly exercises all `clip_near_tri` classifications such as one-inside/two-outside and two-inside/one-outside.

## Recommended validation gaps

A focused near-plane unit test should expose or factor the clipper so it can verify:

- triangle fully inside;
- triangle fully outside;
- one vertex inside;
- two vertices inside;
- vertex exactly on Z=0.08;
- UV interpolation at both generated intersections;
- winding/order after output;
- continuity across the two triangles generated from a clipped quad.

The software `gfx3d` path also needs canonical clip-space edge tests if parity with GPU clipping is a goal.

## Pipeline-order invariant

Clipping must occur in the coordinate space for which its plane equation is defined.

The voxel near plane is defined directly in camera-space Z, so the renderer transforms world vertices into camera space first, clips there, and only then divides by Z during projection.

The homogeneous pipeline is different. Conventional clip-volume tests operate on four-component clip coordinates before division by W. Performing those tests only after mapping to pixels loses information and can produce incorrect edges around the camera/near boundary.

This ordering is one reason ChrisOS cannot simply reuse `clip_near_tri` unchanged as the complete clipping stage for arbitrary programmable shaders.

## Current limitations

Near-plane polygon clipping exists only in selected software rendering code, most clearly the voxel path. Legacy mesh rendering drops partially visible triangles. The software shader backend lacks a complete canonical clip-volume polygon stage. Raster clipping is rectangle/bounds based rather than geometry generation. Coarse scene frustum logic is intentionally approximate.

The code therefore has multiple visibility mechanisms optimized for different stages of project development rather than one unified clipping subsystem.

## Revision note

This chapter was created against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. It distinguishes geometric clipping, primitive rejection, object culling, raster scissoring and gameplay collision according to the current source rather than treating every function named "clip" as equivalent.
