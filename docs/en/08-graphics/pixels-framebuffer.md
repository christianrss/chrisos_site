---
id: pixels-framebuffer
lang: en
type: technical-chapter
volume: 08-graphics
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/gfx/graphics.c
  - kernel/gfx/gfx2d.c
  - kernel/wm/ui.c
symbols: []
depends_on:
  - buses-mmio-dma
related:
  - software-3d
  - virtio-gpu-virgl
---

# Pixels, framebuffers, scanout and composition

## Pixel representation

A display pixel is a sample of color at a location. Software commonly represents color as integer channels such as red, green and blue, often with an alpha component.

A 32-bit framebuffer stores one fixed-width pixel per location. Channel ordering is a format contract; ARGB, RGBA and XRGB are not interchangeable names.

## Linear framebuffer

A linear framebuffer is memory whose addresses correspond to screen rows and columns.

```text
address(x,y) = base + y * pitch + x * bytes_per_pixel
```

**Pitch** is the byte distance between row starts. It is not safe to assume `pitch = width × bytes_per_pixel` because hardware may pad rows.

ChrisOS `gfx_init` receives address, width, height and pitch from boot information.

## Backbuffers

Drawing directly into the displayed buffer can expose partially rendered frames. A backbuffer lets software render into off-screen memory and copy/present a coherent image afterward.

Double buffering separates construction from visibility.

## Dirty rectangles

If only one window changes, copying the entire framebuffer wastes memory bandwidth. Dirty tracking records changed regions and limits presentation work.

Correct dirty tracking must union overlapping updates and remain conservative: missing a changed pixel produces visible stale content; copying a little extra merely costs performance.

## Scanout

Scanout is the display engine reading a buffer and generating display output. With a firmware framebuffer, the mapped framebuffer itself can be the scanout target. With VirtIO-GPU, software can create resources and tell the virtual device which resource is attached to scanout.

Drawing API and scanout mechanism should remain separate. Applications should not know VirtIO descriptor formats just to draw a rectangle.

## Composition

A desktop compositor combines background, windows, decorations, cursor and other surfaces into the final image.

Current ChrisOS window paths still paint through a common screen-oriented model rather than a fully independent per-window GPU surface graph. This is an implementation fact, not a limitation of the general concept.

## Input relationship

Mouse position is conceptually independent from graphics, but cursor presentation couples the two. Current work includes VirtIO-GPU cursor/scanout behavior and software cursor fallback. Correctness requires agreement between input coordinates and the resource currently displayed.

## Why 2D remains important with 3D

Even with a VirGL backend, the desktop needs a robust fallback and reference path. Boot diagnostics, window chrome, text and recovery should not depend on a complex 3D stack if the simpler framebuffer path is sufficient.
