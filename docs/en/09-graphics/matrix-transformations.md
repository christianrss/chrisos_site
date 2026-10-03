---
id: matrix-transformations
lang: en
type: technical-chapter
volume: 09-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/math3d.h
  - kernel/gfx/math3d.c
  - kernel/gfx/mesh.c
  - kernel/gfx/gfx3d.c
  - kernel/gfx/gfx3d_ctx.h
  - kernel/gfx/shader/glsl/mvp.vert
  - tools/test_math3d.c
  - tools/test_math3d_view.c
  - tools/test_gfx3d_abi.c
  - tools/test_mine_spawn_view.c
symbols:
  - vec3f_set
  - vec3f_dot
  - vec3f_cross
  - vec3f_norm
  - mat4f_identity
  - mat4f_mul
  - mat4f_rotate_x
  - mat4f_rotate_y
  - mat4f_rotate_z
  - mat4f_scale
  - mat4f_translate
  - mat4f_perspective
  - mat4f_ortho
  - mat4f_transform
  - mat4f_transform4
  - mat4f_to_glsl
  - mat4f_normal3
  - math3d_view
  - project_view
  - project_vertex
depends_on:
  - gfx2d
related:
  - clipping
  - triangle-rasterization
  - software-3d
  - gfx3d-api
  - shaders-csir
---

# Matrix transformations and coordinate spaces

## Scope

ChrisOS has a compact 3D mathematics layer in `kernel/gfx/math3d.c`. It supplies vector operations, 4×4 matrices, camera/view construction, projection helpers and conversion between the CPU matrix representation and the GLSL-facing representation used by the newer `gfx3d` path.

The important architectural fact is that ChrisOS currently has two related but distinct transformation pipelines.

The older software mesh/voxel path transforms vertices into camera space and then performs a direct divide by positive camera-space `z`. The newer `gfx3d`/shader path supports a conventional homogeneous model-view-projection chain and carries a four-component position through `mat4f_transform4`.

Treating those paths as identical would hide real implementation differences.

## Coordinate convention

The view convention is stated directly in `math3d_view`:

- yaw 0 looks toward world -Z;
- +X is camera right at yaw 0;
- positive pitch looks downward;
- there is no roll component in the camera state.

The forward vector is constructed as:

```text
f.x = sin(yaw) * cos(pitch)
f.y = -sin(pitch)
f.z = -cos(yaw) * cos(pitch)
```

The right vector remains horizontal:

```text
r = (cos(yaw), 0, sin(yaw))
```

The up vector is derived from `r × f` and normalized.

This convention explains why a positive screen-space mouse delta can legitimately increase pitch while making the player look downward.

## Vector operations

`Vec3f` stores three floats. The layer provides addition, subtraction, dot product, cross product, length and normalization.

`vec3f_norm` has an explicit degenerate-vector policy. If the vector length is at most `1e-8`, it does not leave the vector unchanged and does not return an error; it replaces the value with:

```text
(0, 1, 0)
```

Callers that need a zero-vector-preserving normalization contract must therefore implement a different policy.

For ordinary nonzero vectors, normalization divides every component by the Euclidean length obtained from `__builtin_sqrtf(dot(v,v))`.

## Matrix representation

`Mat4f` is an array of 16 floats stored in row-major order.

The transform routines interpret vectors as mathematical column vectors. Translation is therefore stored in the final column of the first three rows:

```text
m[3]   -> translation X
m[7]   -> translation Y
m[11]  -> translation Z
```

For a position `(x,y,z,1)`, `mat4f_transform` computes the first three rows only.

`mat4f_transform4` evaluates all four rows and accepts an explicit input `w`. It is the appropriate primitive when homogeneous coordinates matter.

## Matrix multiplication

`mat4f_mul(o,a,b)` computes the mathematical product:

```text
o = a × b
```

using three fixed loops over rows, columns and the four inner terms.

A temporary `Mat4f t` holds the result before assignment to `*o`. That makes calls such as multiplication into one of the input objects safe from partial overwrite.

The operation always performs the fixed 4×4 workload, so its cost is constant: 64 multiply-add contributions plus loop/control overhead.

Order matters. If a point is a column vector and a model matrix should rotate and then translate it, a common composition is:

```text
model = translation × rotation
world = model × local
```

This is the ordering used in `mesh_draw_f`.

## Identity, scale and translation

`mat4f_identity` zeroes all sixteen elements and sets the main diagonal to one.

`mat4f_scale` starts from identity and replaces diagonal X/Y/Z components.

`mat4f_translate` starts from identity and writes translation into indices 3, 7 and 11.

These constructors do not mutate an existing transform incrementally. They create a complete matrix, after which composition is explicit through `mat4f_mul`.

## Rotation matrices

ChrisOS provides separate X, Y and Z rotation constructors.

Angles are expressed in degrees. The trigonometric functions are not host `sinf/cosf`; they use a lookup table for 0..90 degrees plus quadrant reflection.

A significant precision detail is that `gfx_sinf` converts the wrapped degree value to an integer before indexing the table. There is no interpolation between adjacent entries. Fractional-degree input is therefore effectively quantized to the integer LUT step.

For interactive camera movement this can be acceptable, but it is a real numerical property of the current renderer.

## Degree wrapping cost

`wrap_deg` normalizes angles by repeatedly adding or subtracting 360.

For normal camera angles the cost is trivial. For extremely large-magnitude inputs, however, the operation is proportional to the number of 360-degree intervals rather than using a constant-time remainder operation.

The public contract should therefore be understood as optimized for ordinary rendering angles, not arbitrary unbounded numeric input.

## Building the view matrix

`math3d_cam_set` stores global camera position, yaw and pitch.

`math3d_view` derives forward, right and up vectors, normalizes the relevant basis vectors and builds a row-major view transform.

Each basis row receives a translation term equal to the negative dot product between the basis vector and camera position. Conceptually:

```text
view(world) =
[
 right · (world - camera),
 up    · (world - camera),
 fwd   · (world - camera)
]
```

Objects in front of the camera therefore produce positive camera-space Z in the legacy software path.

## Global state versus copied context state

The low-level math module stores camera and screen dimensions in globals.

`math3d_state_save` and `math3d_state_load` allow those values to be copied to and from a `Gfx3DView`.

The newer `gfx3d_camera` calls the global camera setter, builds a view matrix and stores that resulting matrix inside the graphics context.

This means the source is transitioning from global software-renderer state toward per-context 3D state, but the matrix helper layer itself is not a purely context-free camera object API.

Concurrent callers must not assume that independent calls to the global camera setters are automatically isolated.

## Legacy software projection

`project_view` accepts a point already in camera space.

If `z <= 0`, projection fails and returns screen coordinates -1/-1 plus maximum depth.

Otherwise:

```text
sx = width/2  + x * (width/2)  / z
sy = height/2 - y * (height/2) / z
```

Depth is generated from positive camera-space Z using `depth_to_z`.

This is a compact pinhole projection. It has no explicit FOV parameter. The apparent scale follows directly from half the target width/height.

## Legacy project_vertex

`project_vertex` first calls `mat4f_transform` and then applies the same camera-space divide.

Despite its parameter being named `mvp` in some callers, this helper does not perform a homogeneous four-component perspective divide. It transforms only X/Y/Z and then divides screen X/Y by the resulting Z.

In `mesh.c`, the matrix supplied to it is normally:

```text
view × model
```

rather than a full perspective projection matrix.

This is the correct mental model for the legacy software mesh path.

## Homogeneous projection matrices

`mat4f_perspective` builds a conventional four-component perspective matrix.

It sanitizes inputs:

- aspect close to zero becomes 1;
- near below `1e-4` becomes 0.1;
- far not greater than near becomes `near + 1`.

The FOV scale is computed as cosine/sine of half FOV, which is equivalent to cotangent for the LUT-backed angle representation.

The matrix writes `-1` into the fourth row Z term and zero into the fourth-row W term, making homogeneous `w` relevant.

That matrix belongs naturally to `mat4f_transform4` and shader execution, not the legacy three-component projector.

## Orthographic projection

`mat4f_ortho` creates an orthographic transform from left/right, bottom/top and near/far bounds.

Degenerate spans near zero are replaced with 1.0 to avoid division by an almost-zero value.

Unlike perspective projection, orthographic projection does not use distance to shrink X/Y.

## CPU and shader matrix ABI

CPU matrices are row-major, while GLSL conventionally consumes column-major matrix words.

`mat4f_to_glsl` transposes the storage order:

```text
out[col * 4 + row] = m[row * 4 + col]
```

The mathematical matrix remains the same; only serialized memory order changes.

`tools/test_gfx3d_abi.c` explicitly checks this boundary by evaluating model/view/projection on the CPU with `mat4f_transform4` and comparing the result against the software vertex-shader implementation.

This is stronger evidence than merely checking that both code paths compile.

## Normal matrix limitation

`mat4f_normal3` currently copies the upper-left 3×3 model transform after conversion to GLSL storage.

It does not compute the inverse-transpose matrix.

That is sufficient for pure rotations and some uniform-scale cases, but normals under general non-uniform scaling mathematically require inverse-transpose handling.

A future chapter on lighting/shaders should therefore not describe `mat4f_normal3` as a complete general normal-matrix implementation.

## Projection and depth

`depth_to_z` converts positive floating depth to a 16.16-like integer scale:

```text
uint32 depth = clip_z * 65536
```

Depth at or below zero and values above one million map to `0xFFFFFFFF`.

This representation is consumed by the software z-buffer path. It is not the same coordinate representation as GPU normalized device depth.

## Numerical behavior and ABI constraints

The matrix layer uses single-precision `float` throughout. Repeated composition can therefore accumulate rounding error, especially when many transforms are multiplied incrementally rather than rebuilt from canonical object state.

The current camera path largely rebuilds its basis from position/yaw/pitch each time, which avoids accumulating an orientation matrix frame after frame. By contrast, application code that repeatedly multiplies an existing model transform should expect ordinary floating-point drift.

The degree LUT introduces another form of quantization independent of IEEE-754 rounding. A caller may store a fractional yaw, but `gfx_sinf/gfx_cosf` evaluate it at the integer degree selected by truncation. Therefore the stored camera angle and the effective rendered basis are not necessarily numerically identical at sub-degree resolution.

The shader ABI adds a storage-layout boundary. CPU code must not upload the raw row-major `m[16]` array directly where the shader contract expects column-major words. `mat4f_to_glsl` is the canonical conversion point in the reviewed code.

## Model, view and projection ownership

The three transform categories have different ownership in the newer API.

Model state belongs to the drawable/context and is set through `gfx3d_model`. Camera position/orientation is converted into a view matrix by `gfx3d_camera`. The same call builds projection using the target aspect ratio and requested FOV/near/far values.

When a program is active, those matrices can be uploaded to named uniforms such as `model`, `view` and `projection`.

This separation matters because changing camera state should not rewrite object-local geometry, and changing one object's model matrix should not mutate the camera transform.

## Source consumers

The matrix layer is used by several different subsystems:

- `mesh.c` for model/view transforms and software projection;
- `voxel.c` for camera-space face positions and transformed normals;
- `gfx3d.c` for context view/projection state;
- software shaders for model-view-projection;
- Mine Chris for its camera convention;
- graphics ABI tests to compare CPU and shader transforms.

This breadth makes matrix behavior an ABI-like contract rather than a private math utility.

## Executable evidence

`tools/test_math3d.c` checks basic projection, rejection of a point behind the camera, a 90-degree Y rotation and representative trigonometric values.

`tools/test_math3d_view.c` checks four yaw directions across three pitches. It verifies that points above aim project above center, points below project below center and camera-right remains screen-right. It also explicitly checks the positive-pitch-is-down convention.

`tools/test_mine_spawn_view.c` uses the Mine Chris spawn orientation and verifies ground/sky ordering around the screen horizon.

`tools/test_gfx3d_abi.c` compares CPU and software-shader matrix results for identity, translation, all rotation axes, scale, camera, yaw, pitch, perspective and orthographic transforms.

Together these tests provide meaningful coverage of both the legacy camera path and the newer shader ABI.

## Complexity summary

| Operation | Cost |
|---|---:|
| vector add/sub/dot/cross | O(1) |
| vector normalization | O(1) plus sqrt |
| matrix constructor | O(1) |
| 4×4 matrix multiplication | fixed O(4³) |
| transform 3D position | fixed O(1) |
| transform homogeneous position | fixed O(1) |
| project point | O(1) |
| build view | O(1) |
| angle wrap | O(number of 360° wraps) |

In a renderer the expensive factor is usually how many vertices invoke these constant-size operations.

## Current limitations

The legacy software projector has an implicit projection scale rather than configurable FOV. It rejects non-positive camera Z without polygon clipping. Trigonometry is quantized to integer degrees. Camera/screen state still exists globally in `math3d.c`. General inverse-transpose normal matrices are not implemented.

The homogeneous `gfx3d` path is more conventional, but it coexists with the simpler software path rather than replacing it everywhere.

## Revision note

This chapter was created from ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56` and describes behavior observed in the current source and executable host tests. It intentionally distinguishes the camera-space software pipeline from the homogeneous shader pipeline.
