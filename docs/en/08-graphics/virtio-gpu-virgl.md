---
id: virtio-gpu-virgl
lang: en
type: technical-chapter
volume: 08-graphics
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/gfx/hwgate.c
  - kernel/gfx/gfx3d.c
  - kernel/gfx/gfx3d_virgl.c
  - kernel/gfx/virgl_cmd.c
  - kernel/gfx/virgl_obj.c
symbols: []
depends_on:
  - buses-mmio-dma
  - software-3d
related:
  - shaders-csir
---

# VirtIO-GPU and VirGL

## Two related but distinct layers

VirtIO-GPU provides a paravirtual graphics device. Its 2D resource/scanout operations can work without VirGL.

VirGL adds a 3D command-stream contract. The guest submits graphics commands; QEMU's GL-capable VirtIO device passes them to virglrenderer, which uses a host OpenGL implementation.

```text
ChrisOS Gfx3D
    ↓
VirGL command encoder
    ↓
VirtIO-GPU SUBMIT_3D
    ↓
QEMU virtio-vga-gl / virtio-gpu-gl
    ↓
virglrenderer
    ↓
host OpenGL
```

This is **not** a physical Intel/AMD/NVIDIA GPU driver.

## VirtIO negotiation

A VirtIO device advertises feature bits. The guest selects only features it understands, then configures virtqueues and device-specific structures.

Current ChrisOS graphics negotiation can request `VIRTIO_GPU_F_VIRGL` and, when available under the correct contract, context-init support.

## Resources and ownership

VirtIO-GPU resources have identifiers and backing memory. VirGL objects have their own handles. These namespaces are not interchangeable.

A robust lifecycle needs create → attach → use → detach → unref/destroy. Stress tests matter because one successful boot scene does not prove identifiers/backing are reclaimed over repeated cycles.

## Reusable Gfx3D backend

Recent main-branch work extracted reusable context, target, mesh, texture and program objects from the boot proof. `gfx3d_virgl.c` implements the VirGL device side behind the backend-neutral API.

This is architecturally more important than a demo triangle because it creates a boundary where applications/scenes can eventually target different renderers without embedding protocol constants.

## Command buffers

`virgl_cmd.c` constructs dword command streams and checks capacity. Object setup includes surfaces, shaders, blend/depth/rasterizer/sampler state and draw commands.

Command buffer overflow must flush/continue safely rather than writing past allocated memory.

## Readback and scanout

Readback uses `TRANSFER_FROM_HOST_3D` so CPU code can inspect rendered pixels. This is valuable for automated validation.

Presenting a rendered target can instead set scanout and flush. The desktop later restores the primary 2D scanout.

Readback proves rendering but adds a GPU→CPU transfer and is not necessarily the final performance path.

## Current proof scenes

The project's VirGL documentation records gates for context/resource lifecycle, clear, triangle, depth, indexed cube, textured cube and scanout. Those checks inspect pixels rather than accepting a command submission alone as success.

Current Gfx3D documentation also states that Mine Chris still uses the software scene path. A successful VirGL boot proof therefore must not be described as "Mine Chris is GPU accelerated."

## Evidence categories

Host tests can validate object handles, matrices and command-buffer logic without a virtual GPU. QEMU VirGL tests validate the device/virglrenderer path. A host using llvmpipe is still a QEMU VirGL result, not physical-GPU hardware evidence.
