---
id: virtio-gpu-virgl
lang: en
type: technical-chapter
volume: 08-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/vgpu.c
  - kernel/gfx/vgpu.h
  - kernel/gfx/virtgpu_enc.c
  - kernel/gfx/virtgpu_enc.h
  - kernel/gfx/gpures.c
  - kernel/gfx/gpures.h
  - kernel/gfx/gfx3d.c
  - kernel/gfx/gfx3d.h
  - kernel/gfx/gfx3d_virgl.c
  - kernel/gfx/gfx3d_dev.h
  - kernel/gfx/gfx3d_batch.c
  - kernel/gfx/gfx3d_batch.h
  - kernel/gfx/virgl_cmd.c
  - kernel/gfx/virgl_cmd.h
  - kernel/gfx/virgl_obj.c
  - kernel/gfx/virgl_obj.h
  - kernel/gfx/virgl_demo.c
  - kernel/gfx/hwgate.c
  - tools/test_virgl_cmd.c
  - tools/test_gpures.c
  - tools/test_gfx3d_abi.c
  - tools/test_gfx3d_ctx.c
symbols:
  - vgpu_boot
  - vgpu_submit3d
  - vgpu_res_create_2d
  - vgpu_res_create_3d
  - vgpu_ctx_create
  - gfx3d_boot
  - gfx3d_mark_lost
  - gfx3d_dev_available
  - virgl_cmd_begin
  - virgl_cmd_end
  - virgl_demo_run
depends_on:
  - buses-mmio-dma
  - software-3d
related:
  - virtio-gpu-transport
  - gfx3d-api
  - virgl-command-stream
  - shaders-csir
---

# VirtIO-GPU and VirGL

## Scope

ChrisOS uses VirtIO-GPU as a paravirtual graphics device and VirGL as an optional 3D command-stream layer above it.

The two layers must be kept distinct.

VirtIO-GPU can provide a working 2D scanout, framebuffer transfer and hardware cursor without VirGL. VirGL requires additional feature negotiation, capability sets, 3D contexts, resources and command submission.

The current stack is therefore layered as:

```text
applications / Gfx3D
        |
        v
backend-neutral Gfx3D API
        |
        +--> software backend
        |
        +--> VirGL backend
                 |
                 v
          VirGL command stream
                 |
                 v
          VirtIO-GPU SUBMIT_3D
                 |
                 v
        virtual device / host renderer
```

This path is not a physical Intel, AMD or NVIDIA GPU driver.

## Device discovery

`vgpu_boot` scans PCI buses 0 through 7 and devices 0 through 31, function zero.

The current device match is:

```text
vendor = 0x1AF4
device = 0x1050
```

which identifies the modern VirtIO GPU PCI function expected by this implementation.

The scan is intentionally narrow. It does not enumerate every PCI bus/function topology or every possible VirtIO transport.

After finding the device, ChrisOS enables PCI memory-space and bus-master bits before parsing VirtIO PCI capabilities.

## VirtIO PCI capabilities

The driver walks the PCI capability list and looks for vendor-specific capability ID 9.

It records windows for:

- common configuration;
- notification configuration;
- ISR status;
- device-specific configuration.

The common and notify regions are mandatory for this path.

The ISR and device-specific regions are used when present.

MMIO BARs are mapped through the generic hardware gate, which establishes the connection to the PCI/MMIO/DMA layer documented earlier in the book.

## Feature negotiation

Negotiation begins by resetting device status and moving through ACKNOWLEDGE and DRIVER.

The driver reads both 32-bit feature words.

The high-word bit zero is required, corresponding to modern VirtIO feature bit 32.

If that bit is absent, negotiation fails.

The low feature word can request:

```text
VGPU_F_VIRGL
VGPU_F_CONTEXT_INIT
```

VirGL is requested only when the boot configuration allows 3D and the device advertises it.

CONTEXT_INIT is requested only when VirGL was requested and the device also advertises the context-init feature.

## FEATURES_OK fallback

ChrisOS writes the selected guest feature words and sets FEATURES_OK.

If the device does not keep the FEATURES_OK status bit, the driver retries with only the mandatory modern VirtIO feature and no low-word graphics features.

This means a rejected VirGL feature set can still leave a usable non-VirGL VirtIO-GPU path.

If the second negotiation also fails, device initialization stops.

## Queue setup

The graphics device uses control queue index 0.

Cursor queue index 1 is configured when the common configuration reports at least two queues.

The driver initially asks for:

```text
VGPU_QSZ = 16
```

descriptors.

If the device exposes fewer, the chosen size is reduced to one of:

```text
16, 8, 4, 2
```

A queue smaller than two descriptors is rejected.

Each queue is placed in one 4 KiB DMA page.

Descriptor, available and used addresses are written into the VirtIO common configuration, and the queue is then enabled.

## Notification address

The notify offset is calculated from the queue notification index and the device notification multiplier.

This is a transport-level property, independent of the VirGL command format.

VirGL commands do not write the PCI notify BAR directly; they eventually travel through the same control virtqueue submission machinery.

## DMA allocations

Boot allocates dedicated DMA for:

- command staging;
- response staging;
- the primary scanout backing.

Command and response staging each use four pages.

The scanout DMA size is derived from:

```text
width * height * 4
```

and rounded to pages.

The current VirtIO-GPU boot path clamps width to 1920 and height to 1080.

## Base 2D resource

After queue initialization, the driver creates a VirtIO-GPU 2D resource in B8G8R8A8 format.

That resource is backed by the framebuffer DMA and becomes scanout zero.

This is important architecturally: a functioning VirtIO-GPU desktop does not prove that VirGL is active.

The 2D scanout exists before VirGL capability discovery and before the 3D boot proof.

## 2D flush path

`vgpu_flush_rect` clips a requested rectangle against both the VirtIO framebuffer and ChrisOS front-buffer dimensions.

The selected pixels are copied from the software front buffer into DMA backing memory.

Alpha is forced opaque.

The driver then sends:

```text
TRANSFER_TO_HOST_2D
RESOURCE_FLUSH
```

for the affected rectangle.

The implementation records counts for rectangles, pixels, bytes, full updates and partial updates.

## Hardware cursor

When queue 1 is available, the driver can create a dedicated cursor resource.

The implementation uses a 64×64 cursor because the QEMU path expects that size.

The resource is transferred to the host before UPDATE_CURSOR.

Changing scanout resources increments a generation so the cursor image can be resent, because the host-side cursor sprite may be dropped when the scanout changes.

If hardware cursor movement is unavailable, higher layers can fall back to the software cursor.

## Command submission serialization

The VirtIO-GPU transport is not currently a multi-command concurrent engine from the guest perspective.

A global `g_busy` flag serializes submissions.

Command bytes are copied into shared command DMA, a fence number is allocated, and the request is sent through the control virtqueue.

This design simplifies DMA lifetime because one command/response staging pair is reused.

The cost is that independent graphics callers cannot simultaneously fill the transport with several outstanding control commands.

## Descriptor structure

A normal control submission allocates two virtqueue descriptors:

1. command buffer, device-readable;
2. response buffer, device-writable.

The head descriptor chains to the response descriptor.

After publishing the head, the driver notifies the device and waits for a used-ring completion.

Descriptor reclamation happens after completion.

A failure to allocate the two-descriptor chain is treated as a serious queue problem.

## Fences

The transport maintains a monotonically increasing `g_fence_seq`.

When a command uses a fence, fence flag and 64-bit sequence are written into the command header.

On completion, the response fence is checked.

A mismatched fence is treated as an error rather than silently accepting the response.

The public low-level submission wrapper currently relies on this internal sequence management.

## Completion waiting

Although an IRQ handler records device interrupts and acknowledges ISR status, normal command completion is waited for by polling the VirtIO used ring.

The polling loop has both iteration limits and TSC-based time budgets.

A fast and a slow budget exist; operations such as 3D resource creation, context operations and SUBMIT_3D use the slower path.

If completion times out, the driver marks the device dead, clears live/online state and reports the error.

This is fail-stop behavior for the current graphics transport.

## Response validation

Responses are checked for:

- expected used descriptor identity;
- fence equality when fenced;
- nonzero response type;
- absence of VirtIO-GPU error response codes;
- command-specific expected response type.

Examples include OK_NODATA, OK_DISPLAY_INFO, OK_CAPSET_INFO and OK_CAPSET.

Successful submission is therefore more than "the descriptor moved to used."

## Resource namespace

VirtIO GPU resource IDs are managed by `GpuPool`.

The current limits are:

```text
GPU_RES_MAX = 96
GPU_CTX_MAX = 16
```

A resource tracks ID, owner, 2D/3D type, state, dimensions, format, bind flags, DMA backing and context-attachment count.

Context records track owner, capset ID and live state.

Ownership checks prevent one owner from releasing another owner's object through the intended API.

## Resource lifecycle

A typical backed resource follows:

```text
allocate ID
  -> RESOURCE_CREATE_2D / RESOURCE_CREATE_3D
  -> RESOURCE_ATTACH_BACKING
  -> optionally CTX_ATTACH_RESOURCE
  -> transfer / draw / scanout
  -> CTX_DETACH_RESOURCE
  -> RESOURCE_DETACH_BACKING when applicable
  -> RESOURCE_UNREF
  -> release local pool entry
```

The exact sequence differs by resource role, but create and local allocation are deliberately not treated as the same event.

## 3D resource creation

`vgpu_res_create_3d` constructs a VirtIO-GPU RESOURCE_CREATE_3D command from target, format, bind flags, dimensions and other fields.

The resource obtains a local VirtIO resource ID from the pool.

Backing can then be attached from DMA.

`vgpu_res_create_3d_off` supports a resource whose backing begins at an offset inside a shared DMA slab.

This is useful for persistent or cached geometry allocations.

## Context creation

`vgpu_ctx_create` allocates a local context ID and emits CTX_CREATE.

If CONTEXT_INIT was negotiated and the caller requests it, the low eight bits of the chosen capset ID are placed into the context-init field.

The debug name is "chrisos".

Context destroy sends CTX_DESTROY before releasing the local pool entry.

## Context/resource attachment

A 3D resource can be attached to a context through CTX_ATTACH_RESOURCE.

The driver verifies that both objects exist and have the same owner.

Successful attachment increments a local attachment count.

Detach emits CTX_DETACH_RESOURCE and decrements the count when positive.

The resource namespace and the context namespace remain separate.

## Capability sets

VirGL is considered usable only when the feature was negotiated and at least one acceptable capability set was read.

The driver reads the device-reported number of capsets.

Values greater than sixteen are treated defensively as invalid for this path.

Only:

```text
VGPU_CAPSET_VIRGL
VGPU_CAPSET_VIRGL2
```

are retained.

The local cache stores at most four capsets, each up to 8192 bytes.

## Capset version policy

A capset with size above 8192 or version zero is rejected.

When requesting the capset body, the driver asks for at most version 2 even if the device reports a higher version.

This deliberately narrows the protocol surface to versions the current implementation expects.

`vgpu_virgl_on` requires both the negotiated feature and a nonzero cached capset count.

## VirGL object handles

VirGL object handles form another namespace.

They are not VirtIO resource IDs and are not public Gfx3D handles.

`VirglObjPool` tracks up to:

```text
VIRGL_OBJ_POOL_MAX = 256
```

live handles.

Types include surfaces, shaders, blend state, depth/stencil state, rasterizer state, vertex elements, sampler state and sampler views.

The allocator avoids zero and avoids a handle that is still live.

## Command stream builder

`VirglCmd` writes a dword stream into caller-supplied storage.

A command header packs:

- command opcode;
- object type;
- payload length.

`virgl_cmd_begin` reserves the expected command extent.

`virgl_cmd_u32` refuses to write beyond capacity or beyond the currently declared command length.

`virgl_cmd_end` verifies that the exact expected number of dwords was produced.

Malformed length accounting therefore poisons the command builder instead of writing beyond its buffer.

## Supported command families

The current builder includes support for:

- object create/destroy/bind;
- framebuffer state;
- viewport;
- clear;
- blend;
- depth/stencil/alpha state;
- rasterizer state;
- vertex elements and vertex buffers;
- index buffer;
- draw VBO;
- shader creation/binding/link;
- constant buffers;
- sampler state and sampler views.

This is a deliberately selected subset of the VirGL/Gallium protocol, not a complete Gallium command implementation.

## Batch rollover

A single VirGL batch is limited to:

```text
VIRGL_CMD_MAX = 1024 dwords
```

`Gfx3DBatch` uses the same limit.

Before adding a command that would exceed the remaining capacity, the batch layer can flush the current command stream through SUBMIT_3D and reopen an empty buffer.

A request larger than the complete batch capacity is rejected.

This prevents command-buffer overflow while permitting a frame to require multiple submissions.

## SUBMIT_3D

`vgpu_submit3d` wraps a dword command stream in the VirtIO-GPU SUBMIT_3D command.

It requires:

- nonzero context ID;
- non-null dword array;
- online device;
- transport not already busy.

The command uses a slow completion budget and a fence.

The expected response is OK_NODATA.

Unexpected response or timeout causes an error instead of being treated as a successful draw.

## Gfx3D abstraction

`gfx3d.c` provides the backend-neutral API above software and VirGL implementations.

The backends include:

```text
GFX3D_SOFTWARE
GFX3D_VIRGL
GFX3D_MOCK
GFX3D_AUTO
```

AUTO chooses VirGL only when `gfx3d_dev_available` succeeds.

The device availability check requires:

- VirtIO-GPU ready;
- VirGL feature/capsets active;
- an acceptable capset.

Otherwise AUTO uses the software backend.

## Lost-device recovery

`gfx3d_mark_lost` marks VirGL unavailable and sets a diagnostic string.

If VirGL was not explicitly forced, Gfx3D switches to the software backend and increments degraded-state statistics.

If the user explicitly forced VirGL, the backend remains in the virgl-lost state instead of silently changing the requested policy.

This distinction lets automatic operation recover while keeping forced diagnostic modes honest.

## VirGL device backend

`gfx3d_virgl.c` translates backend-neutral Gfx3D operations into VirtIO/VirGL objects.

It manages device contexts, color/depth targets, buffers, textures, shader objects and per-frame command batches.

Targets use separate VirtIO 3D resources for color and depth.

Buffers can use shared backing allocations.

Textures have both a resource and a sampler-view object.

## Readback

For CPU-visible validation, the device backend uses TRANSFER_FROM_HOST_3D on the rendered color resource.

The resulting backing memory can then be copied into a CPU destination.

Readback is expensive compared with leaving the result on the host/GPU path, but it is essential for boot-time gates and deterministic pixel inspection.

A successful command submission without correct pixels is not considered sufficient evidence.

## Scanout presentation

Presentation can instead bind the rendered color resource directly to scanout zero through SET_SCANOUT and then issue RESOURCE_FLUSH.

This avoids making readback the final presentation mechanism.

Changing scanout may require cursor state to be re-established, which the lower layer tracks with its cursor generation.

The desktop can later restore its primary 2D resource.

## Boot policy

`vgpu_boot` always establishes the 2D device first.

It then performs a 2D resource lifecycle stress test.

With the stress boot flag disabled, this runs four cycles; with stress enabled, 1000 cycles are used.

If VirGL was not negotiated or software 3D was requested, the system keeps the 2D VirtIO device and selects the software 3D backend.

## VirGL boot gate

When VirGL is allowed, boot reads capsets, starts Gfx3D and runs `virgl_demo_run`.

The demo is not merely decorative.

It is a boot-time validation gate that performs context/resource cycles, creates persistent Gfx3D objects, compiles/links shader programs and inspects rendered pixels.

A failure marks VirGL lost and causes automatic fallback to software.

## Proof workloads

The VirGL gate currently covers, among other paths:

- context create/destroy cycles;
- 3D resource attach/detach/unref cycles;
- clear;
- triangle rendering;
- depth behavior;
- indexed cube;
- textured cube;
- varying interpolation;
- lighting;
- shader/program switching;
- persistent mesh behavior;
- lit textured mesh;
- scanout presentation.

When the stress flag is active, context and resource lifecycle cycle counts are increased.

These checks are stronger than accepting protocol responses alone because pixel predicates are evaluated after readback.

## Host tests

`tools/test_virgl_cmd.c` tests command and transport encoders without a virtual GPU.

It checks command-buffer overflow, exact clear command words, invalid surface handles, 3D resource encoding, context creation, context-resource attach encoding, SUBMIT_3D capacity and object destroy encoding.

`tools/test_gpures.c` tests ownership and repeated resource/context allocation/free cycles.

`tools/test_gfx3d_abi.c` tests public handle generations, VirGL object pool exhaustion/release, batch rollover, shader/matrix ABI, software fallback behavior and repeated Gfx3D resource lifecycle.

These are host-side protocol/ABI tests, not proof that QEMU and virglrenderer executed 3D commands.

## QEMU evidence boundary

The boot VirGL gate runs only when the virtual device and its VirGL path are present.

That validates ChrisOS -> VirtIO-GPU -> VirGL/virglrenderer behavior in the configured virtual environment.

If the host OpenGL implementation is software such as llvmpipe, the evidence still proves the virtual VirGL path but does not prove execution on a physical GPU.

The documentation must preserve this distinction.

## Current limitations

The PCI scan is narrow.

Control submissions are globally serialized through one command/response staging pair.

Completion is polled even though interrupt bookkeeping exists.

Only a limited VirGL command subset and capset-version range are used.

Pool capacities are fixed.

The implementation targets the virtual VirtIO-GPU/VirGL environment, not physical vendor GPUs.

Mine Chris must not be described as GPU accelerated merely because the VirGL boot proof succeeds unless its actual rendering path is routed through Gfx3D/VirGL.

## Debugging order

When 2D graphics fail, debug PCI capabilities, feature negotiation, queue setup, DMA backing and scanout before investigating VirGL.

When 2D works but 3D falls back, inspect VIRGL negotiation, capset discovery and the VirGL boot gate.

When command submissions succeed but pixels are wrong, inspect resource attachments, framebuffer/depth objects, shaders, uniforms, viewport and readback rather than treating OK_NODATA as rendering proof.

When the transport times out, treat the device as lost and inspect the last logged operation, context, resource, fence and response.

## Revision note

This chapter was reconciled against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. It documents VirtIO-GPU 2D transport and VirGL 3D as separate layers, with the Gfx3D API and boot-time validation gate above them.
