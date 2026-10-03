---
id: depth-buffer
lang: en
type: technical-chapter
volume: 09-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/zbuf.c
  - kernel/gfx/zbuf.h
  - kernel/gfx/gfx_fast.c
  - kernel/gfx/gfx_slot.c
  - kernel/gfx/tri.c
  - kernel/gfx/math3d.c
  - tools/test_zbuf.c
  - tools/test_tri.c
  - tools/test_mesh.c
symbols:
  - zbuf_bind
  - zbuf_set_size
  - zbuf_width
  - zbuf_height
  - zbuf_clear
  - zbuf_test
  - depth_to_z
depends_on:
  - triangle-rasterization
related:
  - software-3d
  - parallel-raster
  - gfx3d-api
---

# Depth buffer

## Scope

The ChrisOS software renderer stores one unsigned 32-bit depth value per pixel.

The low-level API is deliberately compact: bind a storage pointer, set dimensions, clear the active surface and perform a combined compare/update operation.

Its simplicity is useful for bring-up, but the implementation is stateful and global. Correctness depends on both depth arithmetic and lifecycle: which buffer is currently bound, what dimensions are active and whether the surface has been cleared for the current frame.

## Representation

Each depth cell is a `uint32_t`.

The sentinel for a cleared or infinitely far sample is:

```text
ZBUF_FAR = 0xFFFFFFFF
```

Smaller values are considered nearer.

The z-buffer itself never stores floating-point depth.

The software projection path typically converts camera-space Z through `depth_to_z`.

## depth_to_z

For ordinary positive values:

```text
depth = (uint32_t)(z * 65536)
```

Values at or below zero return `ZBUF_FAR`.

Values above 1,000,000 also return `ZBUF_FAR`.

This is a linear fixed-scale representation of positive camera distance. It is not equivalent to the normalized depth distribution of a conventional GPU perspective pipeline.

## Comparison rule

`zbuf_test(x,y,z)` accepts a fragment only when:

```text
z < stored
```

If accepted, the cell is immediately replaced with the incoming value.

If rejected, the stored value is left unchanged.

The effective depth function is therefore fixed LESS.

## Equal depth

Equal depth fails.

If a cell contains 200 and another fragment also arrives with 200, the second fragment returns false.

This gives a first-writer rule for exact coplanar integer depths.

It also interacts with shared raster edges: when two adjacent triangles both cover a sample with identical depth, the first write usually keeps the pixel.

There is no configurable LEQUAL, GREATER, ALWAYS or depth-bias option in this low-level software module.

## Bounds

The test rejects when:

- no depth buffer is bound;
- X is negative;
- Y is negative;
- X is greater than or equal to width;
- Y is greater than or equal to height.

Out-of-range input therefore fails before a memory access.

The triangle rasterizer has its own bounding-box clipping, but the depth module retains this final defensive check.

## Global active buffer

The implementation stores:

```text
static uint32_t *g_zbuf
static int g_w
static int g_h
```

Only one depth surface is active at a time.

`zbuf_bind(external)` changes the active pointer. Passing null restores the built-in static array.

Color surfaces are passed directly into triangle functions, but depth is selected through this global binding. That asymmetry is an important ownership rule.

## Static fallback capacity

The built-in array is:

```text
1024 × 768
```

At four bytes per cell it occupies 3,145,728 bytes.

The public maximum dimensions are larger:

```text
ZBUF_MAX_W = 1920
ZBUF_MAX_H = 1080
```

The fallback therefore cannot support every size accepted by the API.

## zbuf_set_size

The function normalizes dimensions before storing them.

Width and height below one become one.

Width above 1920 becomes 1920.

Height above 1080 becomes 1080.

The normalized dimensions become the active logical size.

Capacity checking of the static array is then performed separately.

## Static overflow protection

If the currently bound pointer is the built-in static array and the configured size cannot fit in that array, `zbuf_set_size` sets:

```text
g_zbuf = 0
```

The module therefore disables depth access instead of indexing beyond static storage.

With no active pointer, clear becomes a no-op and every `zbuf_test` returns false.

This is a safety-oriented failure mode.

## Recovery state

After the static pointer has been replaced by null because of an oversized configuration, merely reducing width/height does not restore the pointer.

The caller needs:

```text
zbuf_bind(0)
```

to bind the fallback array again.

This means logical dimensions and storage binding are independent pieces of state.

A test that only calls `zbuf_set_size` down again would miss this lifecycle edge.

## External buffers

`zbuf_bind` accepts a raw external pointer without a capacity argument.

The caller therefore owns the invariant that the external storage contains at least:

```text
g_w * g_h
```

32-bit cells.

The low-level module cannot determine whether the allocation is large enough.

This contract is safe only when higher layers manage allocation and dimensions together.

## Graphics-slot ownership

`gfx_slot_alloc` is the main higher-level allocator for a 3D software surface.

It allocates both a color buffer and a z-buffer, each with:

```text
width * height * sizeof(uint32_t)
```

The slot API permits up to 1920×1080.

After allocation, all depth cells are initialized to `ZBUF_FAR`, dimensions are configured and the slot's z-buffer is bound.

This is how Full HD depth storage avoids the smaller static fallback.

## Allocation failure

If one of the two allocations fails, any successful partial allocation is freed.

The slot is not marked used.

The caller therefore does not receive a color-only half of a requested 3D slot.

This allocate-before-publish behavior is an important ownership invariant.

## Resize

`gfx_slot_resize` allocates a new color array and a new depth array before releasing the old pair.

The new depth array is initialized entirely to `ZBUF_FAR`.

Old depth is not copied.

A resize therefore begins with a fresh visibility surface rather than preserving earlier occlusion state.

If dimensions are unchanged and a depth allocation already exists, the existing buffers are reused and rebound.

## Converting a slot to 2D

`gfx_slot_resize2d` can replace a graphics slot with color-only storage.

If a depth buffer previously exists, it is freed and the slot depth pointer is set to null.

A graphics slot therefore does not inherently guarantee depth capability.

Higher layers need to know whether a slot is in 2D or 3D allocation mode.

## Free behavior

`gfx_slot_free` releases the color storage and optional depth allocation.

It then executes:

```text
zbuf_bind(0)
zbuf_set_size(320, 200)
```

The low-level depth module is reset to its static fallback at 320×200.

Because binding is global, freeing one slot also changes the active depth target globally.

This coupling is acceptable in simple sequential use but would be problematic for independent concurrent render contexts without synchronization.

## Clear

`zbuf_clear` fills every active cell with `ZBUF_FAR`.

It uses `gfx_fast_fill_u32`.

If no buffer is active, the function returns without writing.

Clear cost is O(width×height).

At 1920×1080 it writes 2,073,600 cells, approximately 8.29 MB of depth storage.

## Frame lifecycle

A correct software frame normally follows:

1. bind/select the intended depth surface;
2. set matching dimensions;
3. clear depth;
4. rasterize projected geometry;
5. run `zbuf_test` for covered fragments.

Some paths, including `mesh_draw`, perform clear explicitly.

A renderer that fails to clear can preserve depth from an older frame and incorrectly hide new geometry.

## Compare-and-update API

`zbuf_test` is not a read-only query.

A successful call changes the cell immediately.

There is no separate "peek depth" operation.

This keeps the fragment interface small but matters for diagnostics: probing visibility through `zbuf_test` can mutate the state being observed.

## Color ordering

In `tri.c`, depth comparison/update occurs before color is written.

For textured paths, texture sampling and lighting also occur after depth acceptance.

This saves shading work for hidden fragments.

In single-threaded rendering the ordering is straightforward.

In concurrent rendering, however, depth update and later color write are separate memory operations and are not one atomic transaction.

## Concurrency risk

`zbuf_test` uses ordinary load, compare and store operations.

There is no per-pixel lock and no atomic compare-and-swap.

Two workers operating on the same cell can both read the same previous depth before either update becomes visible.

They can then race on both depth and framebuffer color.

Spatial partitioning avoids this only if each pixel has exclusive ownership or competing fragments are serialized.

## Precision

Multiplication by 65536 provides fractional resolution relative to integer world units.

The mapping remains linear in camera-space Z.

A perspective GPU depth buffer normally has different precision distribution after projection and homogeneous division.

At large distance, nearby surfaces can quantize to the same integer depth and fall into the equality/first-writer rule.

The current format is therefore a simple software visibility representation, not a claim of GPU-equivalent precision.

## ZBUF_FAR behavior

`ZBUF_FAR` is both the clear sentinel and the value returned by `depth_to_z` for invalid, nonpositive or excessively large depths.

Because the comparison uses strict less-than, a fragment with depth exactly `0xFFFFFFFF` can never pass against a freshly cleared cell.

This is consistent with interpreting the sentinel as "outside useful drawable range."

## Negative interpolated depth

Triangle functions receive signed 32-bit depth values.

If interpolation produces a negative value, `tri.c` clamps it to zero before converting to unsigned.

Zero is the nearest representable depth and will beat every positive stored depth.

Valid projected geometry should normally not depend on this recovery path; earlier clipping/projection should keep depth sane.

## Clipping versus depth

Near-plane clipping determines whether a primitive is geometrically valid for projection.

Depth buffering determines which valid fragment is visible among fragments landing on the same pixel.

A triangle can fail near-plane handling before any depth test exists.

Conversely, two valid projected triangles can only be resolved through depth.

The stages are complementary, not interchangeable.

## Draw-order properties

For unequal depths in sequential rendering, visibility is mostly independent of draw order.

Far then near causes near to replace far.

Near then far causes far to fail.

Equal integer depth is order-sensitive because equality fails.

There is no polygon offset/depth bias facility in this module to separate coplanar overlays.

## Memory cost

Each depth pixel uses four bytes.

| Resolution | Cells | Depth memory |
|---|---:|---:|
| 320×200 | 64,000 | 256,000 bytes |
| 640×480 | 307,200 | 1,228,800 bytes |
| 1024×768 | 786,432 | 3,145,728 bytes |
| 1920×1080 | 2,073,600 | 8,294,400 bytes |

A 3D graphics slot allocates a color buffer of the same four-byte-per-pixel size, so color plus depth approximately doubles these figures before textures and other resources.

## Executable evidence

`tools/test_zbuf.c` directly establishes the core comparison contract.

After clear, depth 500 passes. Depth 800 at the same cell fails. Depth 200 passes and replaces 500. A second 200 fails.

The test also verifies rejection of negative X and Y equal to height.

The repeated 200 check is important because it proves strict LESS rather than leaving equality behavior inferred.

`tools/test_tri.c` provides integration evidence: a nearer green triangle replaces a farther red triangle at a known overlapping sample.

`tools/test_mesh.c` confirms the larger mesh path can render through the same depth infrastructure.

## Validation gaps

The direct test does not cover disabling the static buffer above 1024×768, restoring it through `zbuf_bind(0)`, external binding, incorrect external capacity, Full HD clamping, slot resize/free side effects or concurrent overlapping fragments.

These are high-value future tests because several likely defects are lifecycle/ownership problems rather than arithmetic errors.

## Complexity

`zbuf_test` is O(1).

`zbuf_bind`, width/height queries and `zbuf_set_size` are O(1).

`zbuf_clear` is O(W×H).

Graphics-slot allocation, initialization and resize are also O(W×H) because each depth cell is initialized.

At high resolution, clear and allocation bandwidth can cost more than the depth comparison itself.

## Debugging invariants

If all 3D geometry disappears after a resolution change, verify the active binding first. An oversized request while using the static array may have set `g_zbuf` to null.

If geometry disappears only after the first frame, verify that clear happens each frame.

If coplanar surfaces change with draw order, remember that equality fails.

If corruption appears only under multiple workers, investigate pixel ownership and race behavior before changing the numeric depth formula.

## API design implications

The current API couples logical dimensions and a global storage pointer but does not encapsulate them in one depth-surface object.

A future context-oriented design could carry pointer, capacity, width, height and comparison mode together. That would make mismatched bind/size state harder to express and would also make concurrent contexts more natural.

Such a redesign would need to preserve the current simple host tests while changing ownership, not merely rename functions.

## Current limitations

The module exposes one global active binding, one fixed LESS comparison and no stencil, MSAA depth samples, configurable write mask, depth bias or atomic overlapping-fragment update.

The static fallback is smaller than the public maximum and requires externally allocated storage for larger surfaces.

These are boundaries of the current ChrisOS software renderer rather than limitations of depth buffering in general.

## Revision note

This chapter was created from ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, using implementation and host tests as primary evidence.
