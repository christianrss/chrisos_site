---
id: software-3d
lang: en
type: technical-chapter
volume: 08-graphics
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/gfx/math3d.c
  - kernel/gfx/tri.c
  - kernel/gfx/scene.c
  - kernel/gfx/gfx3d_ctx.c
  - docs/GFX3D.md
symbols: []
depends_on:
  - pixels-framebuffer
related:
  - virtio-gpu-virgl
  - shaders-csir
---

# Software 3D: transforms, clipping, rasterization and depth

## Geometry pipeline

A basic 3D renderer transforms model vertices through coordinate spaces, projects them to the screen, rasterizes triangles and resolves visibility.

```text
model space
   ↓ model transform
world space
   ↓ view transform
camera space
   ↓ projection
clip space
   ↓ divide / viewport
screen space
   ↓ rasterization
fragments / pixels
```

## Homogeneous coordinates

Using four-component vectors permits translation and perspective projection to be represented in matrix form. After projection, perspective division converts homogeneous coordinates to normalized device coordinates.

Care around `w` is essential; clipping must occur in the correct space to avoid invalid divisions and geometry artifacts.

## Triangle rasterization

A triangle covers a set of pixel sample positions. Edge equations or barycentric coordinates determine whether a sample lies inside and provide interpolation weights.

Barycentric coordinates `λ0, λ1, λ2` satisfy:

```text
λ0 + λ1 + λ2 = 1
P = λ0 V0 + λ1 V1 + λ2 V2
```

Attributes such as depth or color can be interpolated. Texture/varying interpolation under perspective requires perspective-correct treatment rather than simple screen-linear interpolation.

## Depth buffer

A depth buffer stores the nearest accepted depth per pixel. A new fragment compares its depth to the stored value according to the depth function. If it passes, color/depth are updated.

Color and depth writes for one tile must obey ownership rules under parallel rasterization. Two workers writing the same pixel without coordination can race.

## ChrisOS software renderer

Current source retains software 3D as the reference/fallback path. `math3d.c` handles matrices, `tri.c` and related units rasterize geometry, `scene.c` organizes scene operations and per-context state lives under graphics context code.

Mine Chris still uses this software scene path at the documented revision.

## Matrix convention

The current graphics documentation states that `Mat4f` uses row-major storage while multiplying column vectors. Translation components and multiplication order therefore follow a specific convention.

The VirGL/shader path uses GLSL-style column-major matrices, so `mat4f_to_glsl` transposes the representation for upload.

Matrix convention errors are notoriously subtle because a transpose can produce plausible but wrong motion. Host ABI tests compare CPU and shader-side transforms.

## Software rendering as oracle

A software renderer is useful even after GPU acceleration exists because it provides:

- a hardware-independent reference;
- deterministic small-scene tests;
- fallback when VirGL is unavailable;
- a way to test shader IR or scene semantics without the virtual GPU transport.

Performance and reference correctness are different roles.
