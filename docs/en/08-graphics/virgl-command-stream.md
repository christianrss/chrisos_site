---
id: virgl-command-stream
lang: en
type: technical-chapter
volume: 08-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/virgl_proto.h
  - kernel/gfx/virgl_cmd.c
  - kernel/gfx/virgl_cmd.h
  - kernel/gfx/virgl_obj.c
  - kernel/gfx/virgl_obj.h
  - kernel/gfx/gfx3d_batch.c
  - kernel/gfx/gfx3d_batch.h
  - kernel/gfx/gfx3d_virgl.c
  - kernel/gfx/gfx3d_dev.h
  - kernel/gfx/virtgpu_enc.c
  - tools/test_virgl_cmd.c
  - tools/test_gfx3d_abi.c
symbols:
  - virgl_cmd_init
  - virgl_cmd_begin
  - virgl_cmd_u32
  - virgl_cmd_end
  - virgl_cmd_shader
  - virgl_cmd_link
  - virgl_cmd_draw
  - virgl_cmd_consts
  - gfx3d_batch_open
  - gfx3d_batch_reserve
  - gfx3d_batch_flush
depends_on:
  - gfx3d-api
  - virtio-gpu-transport
related:
  - virtio-gpu-virgl
  - shaders-csir
  - tgsi-backend
---

# VirGL command stream

## Scope

ChrisOS does not send high-level Gfx3D calls directly to VirtIO-GPU. The VirGL backend converts them into a stream of 32-bit Gallium/VirGL command words, then wraps that stream in a VirtIO-GPU `SUBMIT_3D` request.

This chapter covers the command-stream layer itself:

```text
Gfx3D state/draw
     |
     v
gfx3d_virgl.c
     |
     v
VirglCmd dword encoder
     |
     v
Gfx3DBatch
     |
     v
VirtIO-GPU SUBMIT_3D
```

The transport chapter covers how `SUBMIT_3D` reaches the device. The shader chapters cover how GLSL-like source becomes TGSI text. Here the focus is how state, shaders, resources and draws are encoded into VirGL dwords.

## Protocol subset

`virgl_proto.h` intentionally defines a subset of the VirGL command stream corresponding to the protocol used by the current renderer.

The source notes that the command numbering and `VIRGL_CMD0` layout follow the VirGL renderer protocol subset used by this implementation.

Implemented command opcodes include:

- create, bind and destroy object;
- viewport state;
- framebuffer state;
- vertex buffers;
- clear;
- draw VBO;
- sampler views;
- index buffer;
- constant buffer;
- sampler-state binding;
- shader binding;
- shader link.

This is not a complete Gallium command implementation.

## Command header layout

Every structured VirGL command begins with one 32-bit header produced by:

```text
VIRGL_CMD0(cmd, obj, len)
```

The packing is:

```text
bits  7..0  : command opcode
bits 15..8  : object type
bits 31..16 : payload length in dwords
```

The length excludes the header itself.

A command with payload length eight therefore occupies nine dwords in the stream.

## VirglCmd state

`VirglCmd` stores:

- pointer to output dwords;
- total capacity in dwords;
- current dword count;
- expected end of the currently open command;
- sticky error state;
- VirGL context ID.

The context ID is metadata for the surrounding submission path. It is not automatically inserted into every command header.

## Initialization

`virgl_cmd_init` requires:

- non-null command object;
- non-null buffer;
- capacity greater than zero;
- nonzero context ID.

A valid initialization resets count, expected-command end and error state.

Invalid initialization places the object into error state when possible.

This means reinitialization is the explicit recovery boundary after an encoder failure.

## Sticky error model

Once `c->err` becomes nonzero, subsequent command writes fail.

The individual encoder does not attempt to repair a partially written command.

This is deliberate. A stream whose structural invariants are uncertain should be discarded or reinitialized rather than submitted.

`virgl_cmd_ok` requires both:

```text
err == 0
n > 0
```

An empty but otherwise valid builder is therefore not considered a submit-ready command stream.

## begin/write/end discipline

`virgl_cmd_begin` validates that:

- no prior error exists;
- payload length is nonzero;
- header plus complete payload fits in capacity;
- any previously open command ended exactly where expected.

It writes the command header, then stores the exact expected dword position after the payload.

`virgl_cmd_u32` refuses writes beyond total capacity and refuses writes beyond the current open command's declared payload.

`virgl_cmd_end` succeeds only when the current count equals the expected position exactly.

The encoder therefore detects both underfilled and overfilled structured commands.

## Raw dword capability

When no command is open, `virgl_cmd_u32` can still append raw dwords because `expect == 0`.

The batch unit test uses this behavior to fill a buffer artificially and force rollover.

Consequently, `VirglCmd` is a low-level stream builder, not a formal parser that proves every dword belongs to a valid VirGL command.

Production backend code normally uses the structured helpers.

## Maximum command buffer

The public encoder defines:

```text
VIRGL_CMD_MAX = 1024 dwords
```

At four bytes per dword, one Gfx3D command batch has 4096 bytes of VirGL stream storage.

This is smaller than the maximum dword count accepted by the lower VirtIO `SUBMIT_3D` encoder.

The stricter Gfx3D limit bounds per-batch stack/static storage and makes rollover predictable.

## Clear command

`virgl_cmd_clear` emits opcode CLEAR with eight payload dwords:

- buffer mask;
- four color words;
- low/high halves of a 64-bit depth representation;
- stencil value.

The current Gfx3D VirGL clear uses the COLOR0 bit and optionally the low depth/stencil clear bit used by this backend.

Color floats are bit-cast to `uint32_t`.

The depth value used by the device clear path is encoded as the 64-bit bit pattern for 1.0.

## Surface objects

`virgl_cmd_surface` creates a SURFACE object.

It rejects zero object handles and zero VirtIO resource IDs.

The payload contains:

- VirGL surface handle;
- backing VirtIO resource ID;
- format;
- two zero fields for the currently unused surface range parameters.

The backend creates B8G8R8A8 surfaces for color resources and Z32_FLOAT surfaces for depth resources.

This is one place where the VirGL object namespace references the separate VirtIO resource namespace.

## Framebuffer state

`virgl_cmd_framebuffer` currently supports exactly one color buffer.

It requires:

```text
nr == 1
color != 0
```

The depth/stencil surface handle may be zero when depth is disabled.

The payload is color-count, depth/stencil surface, then color surface.

The backend caches color/depth surface objects and recreates them when the target resources change.

## Viewport encoding

The viewport helper emits seven payload words.

The current device backend supplies:

```text
scale x = width / 2
scale y = height / 2
scale z = 0.5
translate x = width / 2
translate y = height / 2
translate z = 0.5
```

These floats are passed as raw IEEE-754 bits.

The backend caches the last width/height and avoids re-emitting viewport state when dimensions are unchanged.

This command stream therefore currently reflects full-target viewport dimensions, matching the limitation documented in the public Gfx3D API.

## Object handles

VirGL object handles are not public Gfx3D handles and are not VirtIO resource IDs.

Each device context has a `VirglObjPool` with:

```text
VIRGL_OBJ_POOL_MAX = 256
```

entries.

The pool stores handle, object type and live state.

Allocation avoids zero and avoids a currently live handle.

Peak/live object counts are exposed to Gfx3D statistics.

## Object creation families

The current object types include:

- blend;
- rasterizer;
- depth/stencil/alpha state;
- shader;
- vertex elements;
- sampler view;
- sampler state;
- surface.

Creation helpers encode the exact payload required by the subset.

Bindings are emitted separately where the protocol uses bindable state objects.

## Destroy semantics

`virgl_cmd_destroy` emits DESTROY_OBJECT with one payload word containing the handle.

Unlike several create/bind helpers, this low-level helper does not itself reject handle zero.

Higher backend code normally filters zero before calling it.

That asymmetry means validation is partly split between the generic encoder and its callers.

A future hardening pass could make handle validation more uniform.

## Opaque blend state

`virgl_cmd_blend_opaque` creates a fixed blend object.

The current payload configures the renderer for opaque color writes rather than exposing arbitrary blend equations through Gfx3D.

The object is created once per device context in `ensure_pipe` and then rebound during draws.

This makes the present pipeline intentionally narrower than a general OpenGL-style blending API.

## Depth/stencil state

`virgl_cmd_dsa` creates a DSA object.

A nonzero handle and comparison function <=7 are required.

When depth is enabled, the state word enables depth test, depth write, and encodes the comparison function.

The VirGL backend creates two variants during pipeline initialization:

- depth-enabled state;
- depth-disabled state.

Draws bind one of them based on the public context's depth flag.

## Rasterizer state

`virgl_cmd_raster` accepts cull mode values 0..3.

The command writes a fixed set of rasterizer bits plus the selected cull field.

The backend creates one no-cull object and one culling object during pipeline setup.

Again, Gfx3D exposes only a small policy switch rather than the full rasterizer state space.

## Vertex elements

`virgl_cmd_velems` accepts from one to eight elements.

Each element contributes four payload dwords:

```text
source offset
0
0
format
```

The object header is preceded by its VirGL handle.

The backend caches vertex-element objects by element count, offsets and formats.

If a matching cached object exists, no new object needs to be encoded.

## Vertex buffer state

`virgl_cmd_vbuffers` requires nonzero stride and nonzero resource ID.

It emits:

- stride;
- byte offset;
- VirtIO buffer resource ID.

The Gfx3D backend currently binds one vertex buffer with offset zero per draw.

Resource creation and DMA backing are handled below this layer.

## Index buffer state

`virgl_cmd_ib` requires a nonzero resource and index size of exactly two or four bytes.

The public Gfx3D mesh representation currently uses `uint16_t` indices, so the VirGL path sends index size two.

The command also writes a zero offset.

Non-indexed draws simply omit index-buffer setup.

## Draw command

`virgl_cmd_draw` rejects a zero vertex/index count.

The current payload selects:

```text
primitive = TRIANGLES
instance count = 1
```

and supplies start, count, indexed flag, min index and max index plus fixed zero fields.

Indexed Gfx3D draws currently pass max index 65535.

Non-indexed draws pass the vertex count as the max field.

The current abstraction therefore targets ordinary triangle draws rather than arbitrary primitive topologies or instancing.

## Shader object encoding

`virgl_cmd_shader` creates a shader object from text.

It accepts only vertex or fragment stages.

The text length is scanned explicitly and rejected if more than 3600 non-NUL characters are encountered.

The terminating NUL is included in the encoded length.

The byte count is rounded up to dwords:

```text
shader_dwords = ceil(length_with_NUL / 4)
```

The payload size is five metadata words plus packed text words.

## Shader text packing

Four source bytes are packed into each dword in increasing byte significance.

Conceptually:

```text
word =
  byte0
  | byte1 << 8
  | byte2 << 16
  | byte3 << 24
```

Bytes beyond the final NUL remain zero.

This makes command construction explicit and independent of host pointer alignment.

The text supplied by the current backend is TGSI generated by the shader subsystem, not GLSL source.

## Shader metadata

The shader payload includes handle, stage, exact text length, an additional length-derived metadata word and a zero word before text data.

That fourth metadata word is at least 128 and at most 2048 under the current encoder.

The documentation should not reinterpret it as a general-purpose Gfx3D setting; it is part of this VirGL shader encoding.

## Binding and linking shaders

`virgl_cmd_link` is a three-command sequence, not one packet.

It emits:

1. BIND_SHADER for the vertex handle;
2. BIND_SHADER for the fragment handle;
3. LINK_SHADER carrying both handles and four zero words.

Both handles must be nonzero.

The backend invokes this sequence during draw setup.

Shader objects themselves may have been created earlier through immediate submissions.

## Program generation interaction

The public Gfx3D layer tracks the generation of `ShProgram`.

When a linked program changes, the VirGL backend destroys/recreates the stage shader objects.

The command-stream layer does not know about generations.

It sees only object handles and TGSI text.

This separation keeps program-version policy above the packet encoder.

## Constant buffers

`virgl_cmd_consts` accepts between one and 64 dwords.

It writes:

- shader stage;
- constant-buffer slot zero;
- supplied words.

The helper does not independently validate the stage value.

The backend passes only vertex or fragment stage and converts shader uniform floats to raw bits before encoding.

A 64-dword limit corresponds to at most sixteen vec4 values in one emitted constant-buffer command.

## Sampler state

`virgl_cmd_sampler` creates a fixed sampler-state object.

The state word encodes the addressing/filter policy chosen by ChrisOS.

The remaining payload includes fixed zero values and a fixed maximum-LOD bit pattern.

This API does not currently expose arbitrary min/mag filters or address modes to Gfx3D callers.

The device context creates one sampler state and reuses it.

## Sampler views

`virgl_cmd_sview` creates a sampler-view object for a resource and format.

It rejects zero handle or resource.

The swizzle word maps channels in the natural 0,1,2,3 order.

A Gfx3D texture therefore involves both a VirtIO 3D resource and a VirGL sampler-view handle.

Those identifiers remain separate.

## Binding sampled textures

Textured draws emit:

- BIND_SAMPLER_STATES for fragment stage;
- SET_SAMPLER_VIEWS for fragment stage.

Both low-level helpers reject a zero handle but do not independently validate the supplied stage.

The backend supplies `VIRGL_SHADER_FRAGMENT`.

The public API currently exposes one effective texture binding, so only one sampler/view is configured.

## Immediate submissions

Not every VirGL command waits for the end of a frame.

The device backend has an `emit_now` path that builds a temporary `VIRGL_CMD_MAX` buffer, runs a fill callback, checks `virgl_cmd_ok`, and submits immediately.

Pipeline objects and shader/object creation can use this path.

This is useful when a later batch depends on the object already existing remotely.

## Frame batches

Ordinary frame state and draws use `Gfx3DBatch`.

A batch owns:

- 1024-dword storage;
- one `VirglCmd`;
- context ID;
- submit callback;
- submission/dword counters;
- sticky batch error.

`gfx3d_batch_open` initializes both the batch and its command builder.

## Reservation and rollover

Before adding a group of commands, backend code calls `gfx3d_batch_reserve(need)`.

If the requested group would exceed remaining space, the current batch is flushed.

The command builder is then reinitialized on the same storage.

If `need > 1024`, reserve fails and marks the batch erroneous.

Thus a logical backend operation can trigger a `SUBMIT_3D` boundary when it does not fit in the current batch.

## Flush invariant

`gfx3d_batch_flush` returns success immediately for an empty stream.

A nonempty stream is rejected if:

- the batch is already in error;
- a command is still open (`expect != 0`);
- `virgl_cmd_ok` is false;
- the submit callback fails.

Only a structurally closed stream is passed to `SUBMIT_3D`.

After successful submit, the batch counts the submission and dwords and reinitializes the command builder.

## Draw assembly order

A current VirGL draw broadly assembles:

1. ensure pipeline objects;
2. ensure framebuffer surfaces;
3. ensure viewport;
4. bind blend;
5. bind depth state;
6. bind rasterizer;
7. bind/link vertex and fragment shaders;
8. upload vertex/fragment constants;
9. bind sampler/view if textured;
10. ensure and bind vertex-element object;
11. set vertex buffer;
12. set index buffer if indexed;
13. emit DRAW_VBO.

This ordering is the concrete device-state contract implemented by `gfx3d_virgl.c`.

## Object caches

The backend caches some state objects rather than recreating them every draw.

Framebuffer surfaces track current color/depth resources.

Viewport tracks current dimensions.

Vertex-element layouts are cached by offsets and formats.

The base blend/DSA/rasterizer/sampler objects are created once per device context.

Caching reduces command volume but introduces lifecycle complexity when resources are destroyed or targets change.

## Context destruction

Device-context destruction first flushes pending batched work.

It then walks live VirGL objects and emits DESTROY_OBJECT commands into temporary command buffers.

When the temporary buffer approaches its capacity, it submits the accumulated destroys and reinitializes the builder.

After object cleanup it releases tracked resources and destroys the VirtIO GPU context.

This path demonstrates that command batching is also used for teardown, not only rendering.

## Test evidence

`tools/test_virgl_cmd.c` validates several exact encoder properties.

It confirms:

- zero-capacity initialization fails;
- a tiny command buffer detects CLEAR overflow;
- CLEAR produces the expected `VIRGL_CMD0` header and nine total dwords;
- surface creation rejects zero handle;
- VirtIO 3D resource/context/SUBMIT encoders produce expected fields;
- DESTROY_OBJECT produces the expected header and handle.

This is byte/dword-level host evidence.

## Batch test evidence

`tools/test_gfx3d_abi.c` fills almost an entire 1024-dword command buffer, then reserves a larger block.

The reserve must trigger exactly one fake submit and reset command length to zero.

It also verifies that reserving more than the full batch capacity fails.

This pins rollover behavior independently of a VirtIO device.

## What host tests do not prove

Host encoder tests do not prove that virglrenderer accepts every emitted state combination.

They do not validate the visual meaning of shader metadata, rasterizer bits, sampler bits or framebuffer state.

That evidence comes from the QEMU/VirGL boot gate and pixel readbacks documented in the VirtIO-GPU/VirGL chapter.

Protocol shape and rendered correctness are separate validation layers.

## Error containment

The command layer prefers fail-closed behavior.

A bad handle, capacity failure, illegal index size, oversized shader text or wrong structured payload length poisons the current command builder.

The batch then refuses to submit it.

Higher device code propagates failure to Gfx3D, which can mark VirGL lost and degrade to software when policy permits.

This avoids knowingly submitting a partially encoded command stream.

## Current limitations

The protocol subset is narrow.

Only triangles are emitted for draw topology.

Only vertex and fragment shader stages are supported.

Constant buffers use slot zero and at most 64 dwords per stage submission.

Sampler configuration is fixed.

Framebuffer encoding supports one color target.

Vertex elements are limited to eight.

The command builder is not a semantic validator for arbitrary raw dwords.

There is no decoder/disassembler in the current tree to inspect streams after construction.

## Recommended next tests

Useful additions include golden-word tests for viewport, framebuffer, DSA, rasterizer, vertex elements, indexed draw, sampler/view and shader text packing.

Tests should deliberately underfill a begun command, overfill it, attempt a second command before ending the first and verify that sticky error blocks submission.

An integration test should capture a complete simple triangle batch and compare its command sequence against a reviewed golden stream before sending it to QEMU.

## Revision note

This chapter was created against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. It documents the VirGL dword encoder and batch semantics as the protocol layer between backend-neutral Gfx3D state and VirtIO-GPU `SUBMIT_3D`.
