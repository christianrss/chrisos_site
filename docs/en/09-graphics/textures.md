---
id: textures
lang: en
type: technical-chapter
volume: 09-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/tex.c
  - kernel/gfx/tex.h
  - kernel/gfx/tri.c
  - kernel/gfx/voxel.c
  - kernel/gfx/mesh.c
  - kernel/gfx/gfx3d_ctx.c
  - kernel/gfx/gfx3d_ctx.h
  - tools/test_chunk_mesh.c
  - tools/test_cube_mesh_f.c
symbols:
  - tex_init
  - tex_set_slot
  - tex_slot
  - tex_ofs
  - tex_sample
  - tex_state_save
  - tex_state_load
depends_on:
  - triangle-rasterization
related:
  - software-3d
  - shaders-csir
  - mine-graphics
---

# Textures

## Scope

ChrisOS currently implements a compact software texture subsystem rather than a general asset system. The implementation in `kernel/gfx/tex.c` owns a fixed procedural atlas with sixteen slots, each containing a 16×16 RGB texture.

There is no image decoder, texture upload API, filesystem-backed asset object or GPU texture resource in this path. That simplicity is intentional: texture sampling can be exercised before the rest of the asset pipeline exists.

The cost is equally explicit. Applications cannot currently load arbitrary images through this module, and texture resolution, filtering and addressing behavior are all fixed by code.

## Atlas layout

The atlas is declared as `g_atlas[TEX_SLOTS][TEX_SIZE * TEX_SIZE]` with `TEX_SLOTS = 16` and `TEX_SIZE = 16`.

Each texel is a 32-bit word containing 24 meaningful RGB bits in 0xRRGGBB form. One slot contains 256 texels, or 1,024 bytes. All sixteen slots occupy 16,384 bytes.

The atlas is static storage and does not allocate per texture.

## Lazy initialization

`tex_init` fills the atlas the first time texture functionality is used. The `g_ready` flag makes later calls return immediately.

Slots 0 through 7 have explicit base colors and variation amplitudes. Remaining slots derive their base color partly from the slot index. Every slot is generated through `fill_noise`.

No filesystem operation is required.

## Procedural generator

`fill_noise` uses a deterministic integer pseudo-random sequence. The initial seed is derived from the slot:

```text
slot * 1103515245 + 12345
```

Each texel advances `s = s * 1664525 + 1013904223`. A bounded signed variation is derived with modulo arithmetic and added to the base R/G/B components.

The `rgb` helper clamps all channels to 0..255 before packing. The same code revision therefore produces the same atlas every boot.

## Why deterministic textures are useful

A deterministic atlas makes graphics regressions easier to diagnose. A different image is not caused by an external asset version or random seed.

It also makes early renderer tests independent of filesystem initialization and image decoders.

The tradeoff is that material appearance is code-defined. There is no authoring workflow for importing user-provided images into these slots.

## Initialization concurrency

Lazy initialization is controlled by a plain integer flag. There is no lock around the first `tex_init`.

In the current controlled rendering model this is acceptable, but simultaneous first-use from multiple workers is not a documented thread-safe initialization protocol.

A future concurrent texture system should either initialize before worker startup or use explicit once/synchronization semantics.

## Global state

The module keeps `g_slot`, `g_ofs_u`, `g_ofs_v` and `g_ready`.

`tex_set_slot` initializes the atlas and clamps the requested slot into 0..15. Negative values become 0 and values >=16 become 15.

`tex_slot` returns the selected value.

## Invalid explicit sample slot

`tex_sample` has a different invalid-ID contract.

If its explicit slot is outside 0..15, the function uses the current global `g_slot`. It does not clamp the explicit argument and does not return an error.

Therefore, if the current selected slot is 3, `tex_sample(100,u,v)` samples slot 3.

This fallback behavior matters when texture IDs are derived indirectly from other API values.

## UV repeat wrapping

U and V are normalized to `0 <= coordinate < 1`. The implementation repeatedly adds one while a coordinate is negative and repeatedly subtracts one while it is at least one.

Examples are 1.25 -> 0.25, -0.25 -> 0.75 and 2.0 -> 0.0.

This is repeat addressing. There is no clamp-to-edge or mirrored-repeat mode.

## Wrapping cost

The loop-based implementation is simple but not constant time for extreme coordinates.

A coordinate of 100000 requires many subtractions before sampling. Ordinary raster UV values remain near the normalized interval, so this is normally insignificant.

Still, the function should not be treated as hardened against arbitrarily large user-controlled floats.

## Nearest-neighbor lookup

After wrapping, `x = int(u * 16)` and `y = int(v * 16)`. The code defensively clamps X/Y into 0..15.

The texel is returned from `g_atlas[slot][y * 16 + x]`.

There is no interpolation between neighboring texels, no mipmaps and no anisotropic filtering. The sampling rule is nearest-neighbor.

## Seam behavior

Exactly U=1 or V=1 wraps to zero before integer conversion. A value immediately below one addresses the final row or column.

That discontinuity is correct for repeat addressing. A test suite should pin it because seam handling differs among APIs.

## Animated slot 5

`tex_ofs(du,dv)` stores global UV offsets. They are applied only when the sampled slot is 5.

Other slots ignore the offsets. Slot 5 can therefore behave as a simple scrolling texture while geometry keeps fixed UV values.

The offset is added before repeat wrapping, so scrolling crosses the seam continuously.

## Texture state snapshot

`TexState` stores the selected slot and both offsets. `tex_state_save` copies global state into a caller object and `tex_state_load` restores it.

Null pointers are ignored. The procedural atlas itself is not copied because its contents are global and deterministic.

## Context integration

`Gfx3DCtx` contains a `TexState` alongside view and shading state. The context code saves the legacy globals into a context and later reloads them.

This is a compatibility bridge from global renderer state toward per-context graphics state. It does not make concurrent accesses automatically independent; a context still needs to be loaded before calls that use the globals.

## Voxel material mapping

`voxel_set` clamps block IDs to 0..15. ID zero means empty space and generates no faces.

Visible blocks therefore normally map IDs 1..15 to texture slots 1..15.

A voxel face has UV coordinates (0,1), (1,1), (1,0), (0,0) and is triangulated as two triangles.

When near clipping creates new vertices, U/V values are interpolated at the generated intersections.

## Mesh texture encoding

`mesh_draw_f` overloads its `color` argument. For `color < 16`, it uses a palette color. For `color >= 16`, `texid = color - 16` and the textured raster path is selected.

Thus 16..31 naturally encode texture slots 0..15.

## Encoded IDs above the atlas

A color value above 31 produces `texid > 15`. That ID eventually reaches `tex_sample`.

Because an invalid explicit ID falls back to `g_slot`, the renderer silently uses the currently selected texture rather than failing or clamping to slot 15.

This behavior is deterministic but surprising. A future API should validate encoded texture IDs before rasterization.

## Mesh UV limitation

The current CLVM mesh ABI stores positions and triangle indices, not per-vertex UV data.

When the textured float path is used, every triangle receives the same canonical UV assignment: (0,0), (1,0), (0,1).

That demonstrates texture mapping but cannot represent a real authored unwrap. A richer vertex format is required for that.

## Raster interpolation

`tri_fill_lit` and `tri_fill_tex` interpolate U/V using screen-space barycentric weights. The interpolation is affine.

The renderer does not carry reciprocal W and does not reconstruct attributes using U/W, V/W and 1/W.

Strong depth variation can therefore produce texture warping. The sampler itself simply consumes the U/V it receives; the perspective limitation is in raster interpolation.

## Depth-before-sample ordering

The triangle paths run `zbuf_test` before `tex_sample`. A hidden fragment does not perform a texture lookup.

This is a simple early-rejection optimization and reduces sampling cost under overdraw.

Texture state affects visible color, not depth acceptance.

## Lighting interaction

`tri_fill_tex` computes lighting once from a face normal and multiplies that lighting into every sampled texel.

`tri_fill_lit` interpolates normals and calls `shade_phong` on each visible fragment.

The same texture system therefore participates in both face-level and per-fragment shading.

There is no normal map, roughness map, metallic channel or material descriptor associated with a texture slot.

## No alpha contract

Texels contain RGB only. The texture sampler does not produce an alpha channel and does not implement transparency testing.

The software triangle path writes resulting RGB directly. Blending is outside this module.

Applications should not assume a zero high byte represents meaningful alpha.

## State-transition invariants

A caller that wants deterministic material selection should make the texture state explicit before drawing.

The safest sequence is to load or set the desired context, select the slot if fallback sampling is possible, configure slot-5 offsets when needed and only then issue raster work.

Saving a context after another subsystem has modified `g_slot` captures that modified value. Restoring the context later restores exactly that value.

Because invalid sample IDs use `g_slot`, a stale selected slot can become visible even if the normal rendering path usually supplies valid IDs. This is why fallback state is not merely cosmetic.

## API error model

Most texture operations do not return status codes.

Invalid selection is normalized. Invalid sampling ID falls back. Extreme UV values are wrapped. Null state pointers are ignored.

This makes the sampler resilient for normal rendering but can hide upstream bugs that would be easier to diagnose with strict validation.

A future debug build could add assertions or counters for invalid explicit texture IDs while retaining permissive release behavior.

## Memory locality

The complete atlas fits in a small amount of memory. A 16×16 slot occupies only 1 KiB and the complete atlas is 16 KiB.

This size is favorable for cache locality compared with large external textures.

Nearest-neighbor sampling performs one indexed load and no neighboring fetches.

As the system evolves toward larger images, cache behavior and mip selection will become materially different from this current fixed atlas.

## Security boundary

The current atlas contains no pointers supplied by an application. Sampling indexes only statically allocated storage after slot and coordinate normalization.

That gives the software sampler a small attack surface.

If future APIs permit application-owned texture buffers, they will need capacity validation, ownership/lifetime rules and possibly per-context resource permissions analogous to graphics-slot memory.

## Ownership and thread safety

The atlas and texture selection state are global. No lock protects `g_slot` or offsets.

Concurrent mutation of texture state while another worker samples can produce context leakage.

The intended model is explicit state ownership: load the proper context, render, then save or restore as needed.

A future per-context sampler object would remove this implicit dependency.

## Complexity

Initialization writes exactly 4,096 texels.

Normal sampling is O(1) when UV is near the expected range. Extreme UV values make wrapping proportional to the number of repeated periods.

Nearest lookup itself is a few arithmetic operations plus one array load.

The subsystem is small enough that rasterized pixel count dominates texture-management cost.

## Executable evidence

The inspected tree has no dedicated `tools/test_tex.c` or `tools/test_shade.c`.

Texture behavior is exercised indirectly by `tools/test_chunk_mesh.c`.

The test creates voxel blocks with different IDs, renders the world and requires more than eight distinct nonzero framebuffer colors. That path reaches `tri_fill_tex` and `tex_sample`.

This is useful integration evidence, but it does not independently prove exact wrap behavior, invalid-ID fallback, slot-5 animation or exact procedural texel values.

`tools/test_cube_mesh_f.c` validates the float mesh path but currently uses a palette color, so it is not direct texture evidence.

## Recommended validation

A dedicated texture test should verify deterministic generation, selected-slot clamping, invalid explicit-ID fallback, negative wrapping, >1 wrapping, U/V=1 seam behavior, slot-5 offsets, no offsets for other slots and `TexState` roundtrip.

It should also test very large coordinates to document current loop cost or establish an input bound.

A raster integration test should pin known texel selection at selected pixels and explicitly distinguish affine interpolation from perspective-correct output.

## Debugging invariants

If every textured mesh suddenly uses the same material, inspect the encoded ID and `g_slot`: an out-of-range ID can fall back to the global slot.

If a texture appears to slide only for one material, verify whether that material is slot 5.

If seams occur exactly at integer UV boundaries, remember the sampler uses repeat semantics.

If distortion grows with depth, inspect affine raster interpolation rather than atlas generation.

## Current limitations

The system has sixteen fixed 16×16 procedural textures, nearest-neighbor filtering, repeat-only addressing, no mipmaps, no alpha and no image-loading path.

Texture state is global underneath context save/load.

Mesh UV support is synthetic rather than authored.

These restrictions keep the subsystem deterministic and inspectable but do not form a production texture architecture.

## Revision note

This chapter was created from ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, using `tex.c`, its consumers and available integration tests as the primary evidence.
