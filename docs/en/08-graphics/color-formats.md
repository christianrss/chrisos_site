---
id: color-formats
lang: en
type: technical-chapter
volume: 08-graphics
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/graphics.h
  - kernel/gfx/graphics.c
  - kernel/gfx/gfx2d.h
  - kernel/gfx/gfx2d.c
  - tools/test_graphics_present.c
  - tools/test_gfx2d.c
symbols:
  - gfx_rgb
  - gfx_blit_rgba
  - gfx2d_palette
  - gfx2d_color
  - gfx2d_put
  - gfx2d_layer
depends_on:
  - pixels-framebuffer
  - data-representation-layout
related:
  - gfx2d
  - desktop-compositor
  - textures
  - software-3d
---

# Color formats and alpha

## Scope

A color value is not meaningful until its bit layout, channel interpretation, transfer assumptions and alpha convention are known.

ChrisOS currently uses several related but distinct 32-bit pixel contracts:

- ordinary framebuffer and UI colors are stored as 0x00RRGGBB integers;
- gfx_blit_rgba accepts source pixels as 0xAARRGGBB;
- the 2D palette stores 24-bit RGB values inside uint32_t words;
- gfx2d_layer interprets the upper byte of its source pixels as a presence/opacity gate, but does not perform partial-alpha blending.

These contracts are close enough to be confused and different enough that such confusion causes visible defects.

This chapter separates integer representation, memory byte order, alpha semantics and current ChrisOS behavior.

## A pixel format is a data contract

A 32-bit integer can encode many things.

For graphics, a format definition must answer at least:

- which bits represent red, green and blue;
- whether an alpha channel exists;
- whether alpha is straight or premultiplied;
- how the integer is stored in memory;
- whether the channels are linear-light values or encoded display values;
- whether every consumer uses the same convention.

The type uint32_t alone answers none of these questions.

ChrisOS relies on conventions at subsystem boundaries, so documenting those conventions is part of correctness.

## The primary ChrisOS RGB convention

gfx_rgb accepts three 8-bit channels and returns:

    (red << 16) | (green << 8) | blue

The resulting integer is:

    0x00RRGGBB

Bits 31 through 24 are zero.

Bits 23 through 16 contain red.

Bits 15 through 8 contain green.

Bits 7 through 0 contain blue.

For example:

    red   = 0x12
    green = 0x34
    blue  = 0x56

produces:

    0x00123456

This representation is also visible in the constant UI palette in graphics.h.

Values such as CHRIS_DESKTOP_COLOR and CHRIS_TEXT_COLOR are ordinary 0x00RRGGBB integers.

## Integer layout is not memory byte order

x86-64 is little-endian.

Therefore the 32-bit integer:

    0x00123456

occupies increasing memory addresses as:

    56 34 12 00

The logical channel order described by the integer remains red=0x12, green=0x34 and blue=0x56.

The byte sequence in memory is a consequence of integer endianness.

This distinction prevents a common documentation error: naming the in-memory bytes “RGBA” merely because four bytes exist.

If a device defines channel fields by memory byte position rather than by the CPU integer interpretation, the format contract must reconcile the two explicitly.

The current software graphics path assumes the integer representation used by the boot/device path is compatible with these stores.

## Framebuffer format assumptions

The boot path verifies that the framebuffer is 32 bits per pixel before initializing the software graphics layer.

However, a 32-bpp framebuffer is not automatically equivalent to 0x00RRGGBB.

A generic boot framebuffer description can also include channel masks or shifts.

The current graphics initialization API receives:

- address;
- width;
- height;
- pitch in bytes.

It does not receive red, green and blue bit masks.

Therefore the present ChrisOS software path assumes a compatible channel layout rather than dynamically adapting to arbitrary 32-bpp formats.

That is a current implementation boundary.

A future physical-hardware path should validate the supplied channel masks or convert through a defined canonical format.

## Palette colors in gfx2d

gfx2d exposes a fixed 16-color palette.

The entries are uint32_t values such as:

    0x000000
    0x000080
    0x008000
    ...
    0xFFFFFF

These are again RGB values with no meaningful stored alpha byte.

gfx2d_color returns the indexed palette value.

An out-of-range palette index returns palette entry zero.

gfx2d_put is stricter: if the requested color index is outside the 0 through 15 range, it performs no write.

This difference matters when reasoning about error behavior.

gfx2d_color has a fallback color; gfx2d_put rejects the invalid drawing request.

## Indexed sprite representation

gfx2d_sprite does not receive 32-bit pixels.

Its source is an array of uint8_t palette indices.

For every sprite cell, the byte is interpreted as an index into gfx2d_palette.

The optional key value identifies one palette index to skip.

This is color-key transparency rather than alpha blending.

If key is zero, source cells containing palette index zero are transparent to the destination.

Other entries overwrite the destination with the selected RGB palette value.

Color-key transparency has constant metadata cost and is appropriate for small retro-style indexed sprites, but it cannot express partial transparency.

## 0xAARRGGBB input in gfx_blit_rgba

The general graphics layer has a distinct input contract for gfx_blit_rgba.

graphics.h states that source pixels are:

    0xAARRGGBB

The alpha channel occupies bits 31 through 24.

Red, green and blue occupy the same lower channel positions as the ordinary RGB convention.

This arrangement lets code extract channels using shifts and masks without changing the RGB field locations.

The destination backbuffer remains RGB-like: the blending path writes only the lower 24 color bits.

It does not maintain destination alpha as a persistent compositing channel.

## Transparent and opaque fast paths

gfx_blit_rgba extracts:

    a = pixel >> 24

For alpha zero, the source pixel is skipped.

For alpha 255, the source RGB value replaces the destination directly:

    destination = pixel & 0x00FFFFFF

These two cases avoid the arithmetic required for partial opacity.

The result also makes the destination's upper byte zero in the fully opaque source case.

## Straight-alpha blending

For intermediate alpha, ChrisOS computes each output channel as:

    out = (src * alpha + dst * (255 - alpha)) / 255

This is a straight-alpha source-over-like RGB calculation for a destination treated as fully present.

The source RGB channels have not been premultiplied by alpha in storage.

If alpha is 128, approximately half of the source and half of the destination contribute.

Integer division truncates toward zero.

The calculation is performed independently for red, green and blue.

No destination alpha is computed.

## Straight versus premultiplied alpha

In straight-alpha storage, RGB values describe the unattenuated source color and alpha is applied during composition.

In premultiplied-alpha storage, RGB channels have already been multiplied by alpha.

The two forms are not interchangeable.

Feeding premultiplied input into gfx_blit_rgba would multiply the source contribution by alpha again, darkening translucent colors.

Feeding straight-alpha input into a premultiplied compositor without conversion can produce bright fringes.

The current gfx_blit_rgba contract is straight alpha.

## Gamma and linear-light limitation

The current blend equation operates directly on stored 8-bit channel values.

There is no conversion to a linear-light color space before interpolation.

For typical display-encoded RGB values, arithmetic interpolation in encoded space does not equal physical interpolation of light intensity.

This can make translucent gradients or antialiased edges differ from a color-managed renderer.

ChrisOS currently prioritizes a compact integer software path over color-managed compositing.

That is a rendering-quality trade-off, not an address or memory-safety issue.

## Alpha in gfx2d_layer is different

gfx2d_layer copies from a uint32_t source surface to a uint32_t destination.

For each source pixel it checks:

    if ((c >> 24) == 0)
        continue;

If the upper byte is nonzero, it copies the entire 32-bit word directly.

There is no intermediate-alpha blend.

Therefore alpha in gfx2d_layer behaves as a binary presence test:

- alpha 0: skip;
- alpha 1 through 255: copy.

A source with alpha 1 and one with alpha 255 are equally opaque from this function's perspective.

This is a materially different contract from gfx_blit_rgba.

## Interaction between RGB-only and layer pixels

The fixed gfx2d palette contains values whose upper byte is zero.

If such an RGB-only palette value is placed into a buffer and that buffer is later consumed by gfx2d_layer, the layer function sees alpha zero and treats the pixel as transparent.

That means a buffer intended for gfx2d_layer needs source pixels with a nonzero upper byte if visibility is required.

The ordinary palette drawing API itself writes 0x00RRGGBB values and does not automatically set alpha.

Subsystems must therefore know whether a buffer is:

- a final RGB surface;
- an indexed palette destination;
- or an ARGB-like source layer.

The same uint32_t type is used across these roles, so the distinction is semantic rather than enforced by C's type system.

## Loss of format information at API boundaries

Several current APIs accept a raw uint32_t color rather than a tagged format-specific type.

That keeps low-level routines simple and fast.

The cost is that incompatible values can be passed without compiler diagnostics.

For example, a 0xAARRGGBB source value used as an ordinary framebuffer color preserves its alpha byte in memory even though many consumers conceptually treat the upper byte as unused.

Likewise, a 0x00RRGGBB pixel passed into a layer path can disappear because the layer path interprets the upper byte.

A richer future API could use explicit pixel-format structures or naming conventions that make these boundaries harder to misuse.

## Scaling does not change the format

gfx_blit_scaled performs nearest-neighbor scaling.

It selects source coordinates using integer ratios and copies the selected uint32_t value directly.

No channel conversion or alpha interpretation occurs.

The operation preserves the source word exactly.

Therefore the meaning of those copied bits is inherited from the caller's format contract.

This is distinct from gfx_blit_rgba, which interprets alpha and writes RGB output.

## Dirty tracking is format-independent

The framebuffer damage system tracks rectangles, not pixel semantics.

gfx_mark_dirty does not inspect colors or alpha.

Whether a pixel changed from blue to red, opaque to transparent, or one binary representation to another is irrelevant to damage tracking.

The only contract is that callers mark the region whose backbuffer bytes changed and need presentation.

This separation is useful: presentation bandwidth policy does not need to understand color science.

## Arithmetic and precision

All current channels are eight bits.

A channel therefore has 256 possible integer values.

For alpha blending, products such as:

    255 * 255

fit easily in 32-bit arithmetic.

The maximum sum of the two weighted terms is also bounded safely.

Division by 255 maps the weighted sum back into the 0 through 255 range.

The implementation does not use floating point.

This is appropriate for the low-level kernel path and deterministic across the supported integer environment.

## Validation evidence

tools/test_graphics_present.c verifies concrete RGB values written through the general graphics path.

It checks, among other things:

- full clear values such as 0x00112233;
- rectangular writes such as 0x00445566;
- scaled copies preserving exact source uint32_t values.

tools/test_gfx2d.c verifies palette semantics.

It confirms that:

- palette index 1 maps to 0x000080;
- index 12 maps to 0xFF0000;
- invalid indexed writes do not alter the destination;
- keyed sprite cells are skipped;
- tilemap palette indices produce the expected RGB words.

These tests establish current numeric conventions for the tested functions.

The present tests do not directly cover partial-alpha gfx_blit_rgba blending or gfx2d_layer's binary upper-byte behavior.

Those remain useful targets for dedicated regression tests.

## Performance characteristics

Ordinary RGB writes are simple 32-bit stores.

Opaque blits can also use direct copies.

Partial-alpha composition is more expensive because every destination pixel requires:

- source load;
- destination load;
- alpha extraction;
- six channel multiplications;
- additions;
- divisions by 255;
- channel repacking;
- destination store.

The current implementation performs this scalar work per pixel.

A future SIMD implementation could process multiple pixels at once, but it would need to preserve exact rounding and clipping behavior or explicitly define the new numerical contract.

## Security and robustness

Pixel-format interpretation is usually a visual-correctness concern, but dimensions and buffer ownership remain memory-safety concerns.

The graphics functions validate several geometry cases, but the raw format is not self-describing.

An external file, network image or untrusted application must not be allowed to choose arbitrary dimensions, strides or format assumptions without boundary validation.

The kernel should convert untrusted image data into a validated internal representation before drawing.

Current documented code primarily operates on trusted project-controlled buffers.

## Current limitations

The current color-format layer has several explicit boundaries:

- framebuffer initialization assumes a compatible 32-bpp channel layout;
- no runtime channel-mask conversion;
- no color-profile handling;
- no linear-light blending;
- no HDR or channels wider than eight bits;
- no persistent destination alpha in the main framebuffer;
- gfx2d_layer uses binary alpha gating rather than partial blending;
- palette values do not automatically gain an opaque alpha byte;
- raw uint32_t APIs do not encode the pixel format in the C type;
- dedicated regression coverage for partial alpha is limited.

These are properties of the current implementation, not requirements of graphics systems generally.

## Roadmap boundary

A future color subsystem could introduce:

- explicit pixel-format descriptors;
- boot-framebuffer mask validation;
- conversion between canonical RGB and device-native formats;
- a clearly typed ARGB surface abstraction;
- premultiplied-alpha compositing where beneficial;
- SIMD blend kernels;
- color-space metadata;
- linear-light composition for higher-quality paths;
- tests covering all alpha values and layer semantics.

None of those features should be inferred from the current source.

## Revision provenance

This chapter documents color representation as observed in ChrisOS main revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.

The primary implementation authority is kernel/gfx/graphics.c and graphics.h for RGB and ARGB behavior, plus kernel/gfx/gfx2d.c and gfx2d.h for palette and layer semantics. tools/test_graphics_present.c and tools/test_gfx2d.c provide executable evidence for the numeric conventions they exercise.
