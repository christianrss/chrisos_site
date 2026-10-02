---
id: gfx2d
lang: en
type: technical-chapter
volume: 08-graphics
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/gfx2d.h
  - kernel/gfx/gfx2d.c
  - kernel/gfx/gfx_fast.h
  - kernel/gfx/gfx_fast.c
  - kernel/gfx/zbuf.h
  - kernel/gfx/zbuf.c
  - kernel/gfx/tile.h
  - kernel/gfx/tile.c
  - tools/test_gfx2d.c
symbols:
  - gfx2d_palette
  - gfx2d_color
  - gfx2d_clear
  - gfx2d_put
  - gfx2d_fill
  - gfx2d_line
  - gfx2d_sprite
  - gfx2d_tilemap
  - gfx2d_layer
  - gfx_fast_fill_u32
  - tile_parallel_clear
depends_on:
  - pixels-framebuffer
  - color-formats
  - algorithmic-complexity
related:
  - desktop-compositor
  - software-3d
  - parallel-raster
---

# 2D primitives and composition

## Scope

kernel/gfx/gfx2d.c implements a compact software 2D drawing layer used by ChrisOS experiments and test workloads.

Its public operations cover:

- indexed palette lookup;
- pixel writes;
- full-surface clear;
- filled rectangles;
- integer line rasterization;
- indexed sprites with color-key transparency;
- tilemaps using a fixed atlas layout;
- camera-window layer copies.

The implementation operates on caller-owned uint32_t pixel buffers rather than the global GfxFramebuffer abstraction in graphics.c.

This distinction matters: gfx2d is primarily a rendering library over memory, while graphics.c owns the backbuffer/frontbuffer presentation path.

## Surface model

Most gfx2d functions accept:

    uint32_t *pixels
    int width
    int height

The expected memory layout is tightly packed row-major pixels:

    index = y * width + x

No pitch parameter is provided.

Therefore each logical row is assumed to begin immediately after the previous row.

A padded hardware framebuffer should not be passed directly unless its physical pitch equals width * 4 bytes.

The normal pattern is to render into a tightly packed software surface and use a presentation/conversion layer when necessary.

## Fixed 16-color palette

gfx2d defines a 16-entry palette inspired by traditional low-color interfaces.

Each entry is a 24-bit RGB value stored in uint32_t.

The public gfx2d_color helper maps an integer index to the corresponding RGB value.

For an invalid index, it returns palette entry zero.

Drawing functions that accept a palette index usually reject invalid values instead of silently clamping.

This gives the API two distinct behaviors:

- lookup can fall back;
- mutation can refuse the request.

The distinction is visible in the unit tests.

## Geometry guardrail

area_ok is used for operations whose source or rectangle dimensions can create large nested loops.

It rejects:

- nonpositive width or height;
- either dimension above 4096;
- area above 4096 * 4096.

The multiplication is explicitly promoted to int64_t before comparison.

This avoids signed 32-bit overflow in the area check itself.

The limit is an algorithmic and robustness guardrail, not a statement that every destination surface can actually be 4096 by 4096.

Destination dimensions are still supplied separately and clipping determines visible writes.

## Single-pixel operation

gfx2d_put performs the basic clipped indexed write.

It checks:

- destination pointer;
- positive destination dimensions;
- x and y inside the surface;
- color index inside the palette.

Only then does it write:

    pixels[y * w + x] = palette[color]

Out-of-range coordinates are simply ignored.

This makes gfx2d_put convenient as a safe leaf primitive for algorithms such as line drawing and sprite rendering.

The trade-off is repeated bounds and palette checks for every pixel.

Higher-level routines sometimes write directly for performance when their clipping already guarantees validity.

## Full-surface clear

gfx2d_clear validates the surface and palette index, resolves the RGB value and clears every row.

In ordinary builds it uses gfx_fast_fill_u32 per row.

gfx_fast_fill_u32 uses SSE2 128-bit stores to write four uint32_t pixels at a time, followed by scalar remainder stores.

The clear therefore separates geometry iteration from the lower-level vectorized fill kernel.

After clearing color pixels, gfx2d_clear also resets the global depth-buffer dimensions and clears the z-buffer.

This is an important cross-subsystem side effect: a 2D clear also establishes depth-buffer state for later 3D rasterization.

## Parallel clear path

In a freestanding build, a sufficiently large surface can take a different path.

The condition is:

    width * height >= 512 * 512
    and at least two CPUs online

In that case gfx2d_clear calls tile_parallel_clear.

tile_parallel_clear divides the surface into 64 by 64 tiles.

Each tile becomes a job containing:

- destination pointer;
- full surface geometry;
- tile coordinates;
- color.

Workers fill independent rectangular regions with gfx_fast_fill_u32.

Because tiles do not overlap, the color stores themselves do not require a per-pixel lock.

The function waits for queued work to become idle before returning, so the clear has completion semantics from the caller's perspective.

## Job queue batching

tile_parallel_clear uses a static array of TileClearArg sized to JOB_QUEUE_CAP.

When all argument slots have been consumed, it waits for the job system to become idle and starts reusing the array from slot zero.

This prevents overwriting an argument structure that a queued worker may still read.

At the end, it waits again for the final batch.

The algorithm therefore bounds temporary metadata without allocating one object per tile.

## Parallel-clear caveats

The parallel path depends on global scheduler/job-system state and cpu_online_count.

It exists only in freestanding builds.

Host unit tests of gfx2d do not exercise that path.

Correctness relies on the job system honoring job_wait_idle as a completion barrier for submitted clear jobs.

The tiles are disjoint, but the destination surface itself still must not be concurrently modified by unrelated renderers during the clear unless a higher-level ownership rule permits it.

The static argument buffer also means two simultaneous tile_parallel_clear calls would share argument storage and are not independently reentrant.

## Filled rectangles

gfx2d_fill accepts an origin, rectangle width/height and palette index.

It first validates area and color.

Then it computes:

    x0 = x
    y0 = y
    x1 = x + rw
    y1 = y + rh

and clips those endpoints to the destination.

Only the visible intersection is written.

The nested loops visit every surviving pixel.

For a visible rectangle of width W and height H, time complexity is O(W * H).

Memory overhead is O(1).

## Rectangle clipping behavior

Negative origins are allowed.

For example, a rectangle beginning at (-2,-2) with size 4 by 4 is clipped to the 2 by 2 visible corner.

tools/test_gfx2d.c verifies exactly this kind of case.

Clipping prevents ordinary out-of-bounds writes.

As with many C geometry APIs, extremely large signed coordinate values can still make additions such as x + rw a potential integer-overflow concern before clipping.

The current callers are expected to provide bounded project-controlled coordinates.

## Line rasterization

gfx2d_line implements an integer incremental line algorithm equivalent to the common symmetric Bresenham family.

It computes:

- absolute dx and dy;
- x and y step directions;
- an accumulated error term.

At each iteration it calls gfx2d_put and then updates x and/or y according to twice the error.

No floating point is used.

The algorithm handles horizontal, vertical, diagonal and general slopes through the same state machine.

## Line complexity

For endpoints (x0,y0) and (x1,y1), the number of iterations is proportional to:

    max(abs(x1 - x0), abs(y1 - y0))

Thus time complexity is O(max(dx,dy)) and auxiliary memory is O(1).

Because each step calls gfx2d_put, off-screen portions are computed but discarded by per-pixel clipping rather than by a line-clipping phase.

For very long mostly off-screen lines, a geometric clipping algorithm before rasterization would reduce unnecessary work.

## Sprite representation

gfx2d_sprite uses an 8-bit indexed source.

The source is laid out row-major with dimensions sw by sh.

Each byte is interpreted as a palette index.

If the index equals key, the destination is unchanged.

Otherwise the function calls gfx2d_put.

This combines:

- palette conversion;
- destination clipping;
- color-key transparency.

The key can be -1 to disable effective transparency because uint8_t source indices range from 0 through 255 and therefore never equal -1 after integer conversion.

## Sprite complexity

A sprite always scans all sw * sh source cells after validation.

Its complexity is O(sw * sh), even when the sprite lies almost completely outside the destination.

Per-pixel clipping keeps writes safe but does not skip invisible source rows/columns at a coarse level.

An optimized implementation could compute source clipping once and iterate only the visible source rectangle.

The current form prioritizes simplicity.

## Tilemap binary layout

gfx2d_tilemap expects a compact combined data buffer.

The beginning contains an atlas of exactly 16 tiles:

    atlas_bytes = 16 * tile_width * tile_height

Immediately after the atlas is the map:

    map_bytes = map_width * map_height

Each map byte selects one of the 16 atlas tiles.

There is no separate structure describing offsets; the layout is derived from dimensions.

This is a small fixed format rather than a general map-file parser.

## Tilemap constraints

The function rejects:

- null pointers;
- nonpositive dimensions;
- map dimensions above 512 by 512;
- tile dimensions above 256 by 256;
- tile area rejected by area_ok.

It computes atlas and map sizes as int.

Given the explicit dimensional caps, the expected products remain within normal signed-int range.

Each valid map cell selects its tile source and calls gfx2d_sprite.

Invalid tile values at or above the 16-entry atlas count are skipped.

## Tilemap complexity

For a map containing M = mapw * maph cells and tiles containing T = tw * th pixels, the straightforward rendering cost is:

    O(M * T)

because every map tile invokes a full sprite scan.

There is no viewport culling based on the destination before choosing tiles.

Therefore a large map rendered with an offset still scans tiles that may end completely off-screen.

A future camera-aware tile renderer could first calculate which tile coordinates intersect the viewport.

## Layer operation

gfx2d_layer copies a camera-sized view from a source uint32_t surface to a destination surface.

For each destination coordinate:

    source_x = x + camx
    source_y = y + camy

Coordinates outside the source are skipped.

The source pixel's upper byte is then inspected.

If that byte is zero, the pixel is treated as transparent.

Any nonzero upper byte causes the entire 32-bit source word to overwrite the destination.

This is binary alpha gating, not partial blending.

## Layer complexity

The function loops across every destination pixel:

    O(destination_width * destination_height)

The camera offset affects which source positions are read but does not reduce loop bounds.

For small viewports over larger worlds, this is predictable.

For sparse layers, a representation containing dirty rectangles, runs or tiles could reduce work, but at the cost of more metadata and complexity.

## Difference between gfx2d and graphics.c

gfx2d and the general graphics layer overlap in capability but serve different contracts.

gfx2d:

- renders to caller-provided tightly packed buffers;
- often uses palette indices;
- exposes line, sprite, tilemap and layer operations;
- does not maintain dirty rectangles for presentation.

graphics.c:

- owns a global backbuffer/frontbuffer pair;
- accepts raw RGB colors;
- tracks dirty rectangles;
- performs scaling, RGBA blending, text and presentation.

A caller may use both layers, but should not assume they share pitch, alpha or ownership semantics automatically.

## Fast fill implementation

gfx_fast_fill_u32 broadcasts the 32-bit color into an SSE2 register and writes four pixels per iteration with unaligned 128-bit stores.

The remainder loop handles one to three trailing pixels.

The use of _mm_storeu_si128 means the destination does not need 16-byte alignment.

However, the CPU must have the required SSE2 execution state enabled in the environment where the function runs.

The broader ChrisOS startup path initializes SSE support before relying on graphics fast paths.

## Z-buffer coupling

gfx2d_clear calls:

    zbuf_set_size(w, h)
    zbuf_clear()

The z-buffer stores one uint32_t depth value per cell.

ZBUF_FAR is 0xFFFFFFFF.

zbuf_test accepts a new depth only when:

    new_z < stored_z

and updates the stored value.

Thus a color clear also resets depth tests to the far value.

This coupling makes sense for a frame-oriented software renderer, but it also means gfx2d_clear is not purely a color-buffer operation.

Any future separation of 2D and 3D surfaces should make that side effect explicit or move frame reset to a higher-level frame API.

## Static z-buffer capacity

The built-in static z-buffer is 1024 by 768.

zbuf_set_size allows logical sizes up to 1920 by 1080, but if the active buffer is still the static array and the requested dimensions exceed its capacity, it sets the z-buffer pointer to null.

An external depth buffer can be installed with zbuf_bind.

After a null depth-buffer state, zbuf_clear becomes a no-op and zbuf_test rejects all samples.

This behavior is an important limitation when a large gfx2d_clear is followed by software 3D rendering without an externally bound depth surface.

## Ownership and reentrancy

Most gfx2d routines do not allocate memory.

They mutate caller-provided buffers.

This gives simple ownership rules for the color surface itself.

However, the subsystem also touches global/shared state:

- the global z-buffer;
- cpu_online_count in freestanding clear selection;
- the global job queue;
- static tile clear argument storage.

The API therefore cannot be described as globally reentrant merely because most functions accept explicit destination pointers.

Independent simple fills on unrelated buffers may be mechanically independent, but clear's depth-buffer side effect and parallel path introduce shared state.

## Validation evidence

tools/test_gfx2d.c provides host evidence for the core scalar path.

It verifies:

- full clear to palette index 1;
- clipped single-pixel writes;
- rejection of invalid palette indices;
- filled rectangles;
- clipping of a partially off-screen rectangle;
- horizontal lines;
- diagonal lines;
- keyed sprite transparency;
- tilemap atlas addressing.

The test checks exact output values, not just return codes.

This is strong evidence for those particular algorithms and palette mappings.

## Validation gaps

The current dedicated test does not directly exercise:

- gfx2d_layer;
- very large geometry rejection;
- the parallel clear path;
- job batching;
- z-buffer side effects;
- every line octant;
- tilemap clipping with large camera offsets;
- concurrent use.

These are appropriate targets for future test expansion.

The documentation should not imply they are covered simply because the functions exist.

## Failure behavior

Most gfx2d APIs return void.

Invalid inputs normally cause an early return rather than a diagnostic.

Examples include:

- null surface;
- invalid geometry;
- invalid color index;
- invalid tile dimensions;
- out-of-range coordinates.

This style makes rendering calls easy to compose but loses information about why nothing was drawn.

For kernel-internal trusted call sites that may be acceptable.

For an application ABI or debug-oriented API, structured errors or validation counters would improve observability.

## Performance characteristics

The dominant costs are proportional to pixels visited.

- put: O(1);
- fill: O(visible area);
- line: O(max(dx,dy));
- sprite: O(sw * sh);
- tilemap: O(map cells * tile pixels);
- layer: O(destination area);
- clear: O(w * h), with optional parallel execution.

The subsystem uses simple contiguous row-major memory, which is favorable for cache locality during fills and horizontal scans.

Sprite and tilemap accesses are also sequential inside individual source rows.

Layer copy scans destination and source rows in lockstep when camera coordinates are in range.

## Current limitations

Major current boundaries include:

- fixed 16-color indexed palette;
- tightly packed destination surfaces only;
- no pitch argument;
- no vector shapes beyond line/rect primitives;
- no line clipping before rasterization;
- no coarse sprite clipping;
- no tilemap viewport culling;
- tilemap atlas fixed to 16 entries;
- binary layer alpha rather than partial blending;
- global z-buffer side effects from clear;
- static tile-job argument storage;
- parallel clear not covered by the host unit test;
- no explicit thread-safety contract;
- void APIs with limited diagnostics.

These constraints are consistent with a compact experimental software renderer.

## Roadmap boundary

A more complete 2D subsystem could add:

- explicit surface descriptors including pitch and pixel format;
- viewport-aware sprite and tile culling;
- arbitrary atlas sizes;
- clipped line algorithms;
- alpha-aware layer composition;
- transformed sprites;
- dirty-region tracking at the surface level;
- explicit frame/depth reset APIs;
- per-operation contexts instead of shared state;
- SIMD sprite/layer kernels;
- broader property and fuzz tests for clipping.

These are future directions, not current behavior.

## Revision provenance

This chapter documents the 2D path as observed in ChrisOS main revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.

The primary sources are kernel/gfx/gfx2d.c and gfx2d.h. gfx_fast.c defines the SIMD fill primitive, tile.c defines the freestanding parallel-clear path, zbuf.c defines the depth-buffer side effect, and tools/test_gfx2d.c supplies executable evidence for the scalar rendering contract.
