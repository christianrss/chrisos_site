---
id: graphics-history
lang: en
type: technical-chapter
volume: 16-history
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/graphics.c
  - kernel/gfx/gfx2d.c
  - kernel/gfx/tri.c
  - kernel/gfx/zbuf.c
  - kernel/gfx/tex.c
  - kernel/gfx/voxel.c
  - kernel/gfx/gfx3d.c
  - kernel/gfx/gfx3d_virgl.c
  - kernel/gfx/vgpu.c
  - kernel/gfx/virgl_cmd.c
  - kernel/gfx/virgl_demo.c
  - kernel/gfx/shader/sh_api.c
  - kernel/gfx/shader/sh_ir.c
  - kernel/wm/desktop.c
  - kernel/wm/ui.c
symbols:
  - gfx_present
  - gfx3d_boot
  - gfx3d_mark_lost
  - vgpu_boot
  - sh_compile
  - sh_program_link
depends_on:
  - architecture-history
related:
  - pixels-framebuffer
  - gfx2d
  - triangle-rasterization
  - virtio-gpu-virgl
  - gfx3d-api
  - shader-spec
  - mine-graphics
---

# Graphics architecture history

## Scope

This chapter reconstructs how the ChrisOS graphics stack reached its current architecture.

It is intentionally revision-bound. It does not present every graphics commit as a separate architecture. Instead it identifies transitions that changed a subsystem boundary, ownership model, execution backend or evidence level.

The history is reconstructed from Git commits together with the current source at revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

## Reading the timeline correctly

The first graphics milestone described here, 18 September 2026, is **not** the absolute birth of graphics in ChrisOS.

Commit `13b8aa216065b85f7f50a9b1fe1bd758c7caaab8` moved or renamed several already existing files such as `graphics.c`, `font.c`, `input.c`, `desktop.c` and other window-manager files while adding the new `kernel/gfx` organization and `gfx2d.c`.

Therefore 18 September is best interpreted as the point where the current graphics/window-manager directory structure became recognizable, not as proof that no framebuffer or desktop code existed before it.

This distinction matters in historical documentation: a rename commit is architectural evidence, but not necessarily an origin commit.

## Phase model

The graphics evolution can be divided into six phases:

1. consolidation of framebuffer, 2D and desktop code;
2. expansion into a software 3D renderer;
3. application pressure and framebuffer/scanout integration;
4. VirtIO-GPU and VirGL proof of hardware-assisted rendering;
5. programmable shader pipeline;
6. extraction of a reusable backend with software fallback.

These phases overlap in dates because the project evolved rapidly.

## 18 September 2026 — current graphics layout consolidates

Commit:

    13b8aa216065b85f7f50a9b1fe1bd758c7caaab8

Message:

    feat:PASSO W01 — pastas do kernel e Makefile

The commit added `kernel/gfx/gfx2d.c` and `gfx2d.h`, while moving or renaming existing font, graphics, input and desktop components into the current source hierarchy.

The resulting separation established a pattern that remains visible today:

    kernel/gfx/
        low-level drawing and rendering

    kernel/wm/
        desktop/window/task interaction

That boundary was important because the desktop could evolve as a consumer of graphics primitives instead of being the graphics implementation itself.

## 18 September — desktop interaction grows around the 2D layer

Several commits on the same day extended the user interface:

- `0a790e6b59a4f0ddaf2a32f4f47404791f6e2b2b` — taskbar, text, clock and windows;
- `641c23af9d70e14d5333823f457d24693daa456a` — desktop icons;
- `2032cb8f5cb70419fb8ea088a8f66cd02a5a5a20` — explorer with folders;
- `6fd3e42b27c8eadabb49a6bd5300720467096539` — task manager.

These commits are significant to graphics history even though they are primarily UI work.

They turned the framebuffer and 2D primitives into a desktop platform with multiple independently painted applications.

The historical lesson is that ChrisOS graphics did not begin with a GPU abstraction. It first matured as a software-rendered desktop surface.

## The 2D architecture that survived

The current `graphics.c` still reflects that lineage.

ChrisOS renders into a back buffer, records dirty rectangles, copies changed regions to the front buffer in `gfx_present()`, and then, in the freestanding build, calls the hardware flush path for the union of dirty areas.

Conceptually:

    application/window paint
          |
          v
      software back buffer
          |
          v
       dirty regions
          |
          v
      front framebuffer
          |
          v
    optional hardware scanout flush

This is not a GPU-composited desktop architecture.

The CPU-owned 2D path remains a first-class rendering path even after VirtIO-GPU and VirGL were introduced.

## 20 September 2026 — software 3D appears

The major 3D expansion arrived in:

    89e3587422ab34eceb1054abf14de06717f93db6

with message:

    feat: JIT, 3D, Float, etc.

The graphics additions were broad:

- `math3d.c`;
- `mesh.c`;
- `shade.c`;
- `tex.c`;
- `tile.c`;
- `tri.c`;
- `tri_bin.c`;
- `voxel.c`;
- `zbuf.c`;
- SSE initialization;
- graphics benchmark support;
- slot/resource support.

This was not merely "draw a triangle".

It created most of the conceptual components of a CPU 3D pipeline.

## Software rasterization model

The current `tri.c` still contains the direct descendant of that renderer.

Triangle coverage is evaluated through edge functions.

A simplified inside test for a consistently oriented triangle is:

[
w_0 ge 0 land w_1 ge 0 land w_2 ge 0
]

Depth is interpolated from barycentric weights and tested against the z-buffer before the color is stored.

Later paths add texture coordinates, normals and lighting.

This design has two historical consequences.

First, ChrisOS had a useful 3D path before a virtual GPU backend existed.

Second, when VirGL arrived, it did not need to replace every graphics algorithm immediately; software remained a valid reference and fallback backend.

## 20 September — immediate optimization

Only minutes later, commit:

    158d0c7a13c3986a4a13e743c19b00533baec1a2

with message:

    feat: gfx optimization

changed fast-copy, mesh, shade and triangle code.

This is evidence that the software 3D implementation immediately encountered the normal cost centers of CPU rasterization:

- framebuffer memory bandwidth;
- per-pixel triangle work;
- shading work;
- mesh traversal;
- clipping and UI redraw interactions.

The architecture therefore evolved under performance pressure before GPU offload was introduced.

## Software 3D becomes more than a demo

The software renderer was connected to mesh and voxel systems rather than being kept as an isolated test.

The current tree still contains:

- chunked voxel state;
- dirty-chunk rebuild tracking;
- dynamically allocated face lists;
- texture support;
- z-buffered triangles;
- lighting paths.

This is important when interpreting later VirGL work.

The project did not move from "no 3D" to "VirGL 3D". It moved from an existing software 3D stack toward an additional accelerated backend.

## 22 September — Doom increases graphics integration pressure

Commit:

    9e26685723513e7145231b5a301dd833c74eb0c1

was the large "Porting Doom" change.

Graphics-related modifications included `gfx_slot`, input, mesh and desktop integration.

The historical significance is not that Doom created a new graphics architecture.

Instead, it increased pressure on the existing architecture to behave like a platform:

- application-visible surfaces;
- responsive input;
- desktop integration;
- framebuffer update behavior;
- compatibility with a substantial external codebase.

This is an example of an **integration milestone**, not a backend replacement.

## 23 September — desktop scanout becomes explicit

Commit:

    794dec7a1ae8c5a34cc61690a45f3e1a39ab7eb3

has the message:

    feat: scan out the desktop, install real disks, and boot RISC-V

The graphics changes modified `graphics.c` and hardware-gate code.

This stage strengthened the boundary between:

    software composition

and:

    device scanout/presentation

That distinction remains in the current `gfx_present()` path.

The desktop can continue painting through CPU graphics even if the physical/virtual presentation mechanism changes.

## Why scanout and 3D acceleration are separate problems

A graphics device can be useful in at least two independent ways:

1. showing a framebuffer on a display;
2. executing or accelerating 3D rendering commands.

ChrisOS encountered those as separate stages.

The desktop scanout work did not automatically provide VirGL 3D.

Conversely, a VirGL proof scene did not automatically make every desktop surface GPU-composited.

This separation is still useful in the architecture today.

## 25 September — VirtIO-GPU and VirGL proof

The decisive virtual-GPU milestone was:

    a894bf7de6ef6dcfaa8fe217ce003f32914f99aa

Message:

    Drive VirtIO-GPU and a native VirGL proof scene.

The commit added the large `vgpu.c` implementation and `virgl_demo.c`.

Its commit record states that the boot path:

- negotiated VirtIO version 1 and VirGL;
- discovered capsets;
- issued real `SUBMIT_3D`;
- rendered clear, triangle, depth, cube and textured cube cases;
- performed readback;
- fell back to software 3D on failure.

This was the first major transition from "software renderer plus scanout" toward "graphics device as a rendering backend".

## Why this was still a proof

The first VirGL code was concentrated in a proof/demo path.

That matters architecturally.

A proof can answer:

> can ChrisOS negotiate the device and submit a real 3D workload?

It does not yet answer:

> can ordinary applications create reusable contexts, targets, meshes, textures and programs without depending on boot-demo internals?

The next day's refactoring addressed exactly that problem.

## Command encoding becomes its own concern

The VirGL path introduced another layer beneath the graphics API:

    high-level draw intent
          |
          v
      VirGL command encoding
          |
          v
    VirtIO-GPU submission
          |
          v
        host renderer

This layer must manage bounds, object identifiers, command-buffer capacity and protocol details.

That is why later source separates files such as `virgl_cmd.c`, `virgl_obj.c`, `gfx3d_batch.c` and `gfx3d_virgl.c`.

The device backend is not merely a call to "GPU draw".

## 25 September — shader compiler arrives

Commit:

    4f911d18fc366815fc39b5849680b03afd3f38bb

added the ChrisOS shader compiler.

The commit message describes the intended pipeline:

    GLSL subset
        -> AST
        -> CSIR
        -> verification
        -> TGSI or CPU interpretation

The change added lexer, parser, semantic analysis, IR, execution, TGSI generation, public API and host tests.

This was a major architectural shift.

Before this point, 3D rendering could exist without a project-owned programmable-language frontend.

After this point, ChrisOS had its own shader-language boundary.

## Why the shader compiler matters historically

The shader compiler did more than make examples prettier.

It created a backend-independent representation.

The same source-level intent could feed:

- the software shader executor;
- TGSI for the VirGL path.

That made software rendering valuable not only as a fallback, but also as a semantic reference for programmable graphics.

The later `shader-spec` formalizes this boundary.

## Same day — compiled shaders drive the VirGL proof

Commit:

    90e0176830b47fafd81377df33ddaba006c54ccd

connected compiled shader source to the VirGL proof scene.

The commit record states that:

- triangle;
- depth;
- cube;
- texture;
- varyings;
- lighting

used TGSI produced by the ChrisOS compiler.

It also states that Mine Chris world shaders were linked during the same boot, **without drawing the voxels through VirGL**.

That sentence is historically important.

It records a boundary that can easily be lost in later summaries:

> shader compilation integration advanced faster than full application migration to the accelerated backend.

## 26 September — proof becomes reusable Gfx3D

The key architectural refactoring was:

    011dfb25e41ac37db483216c0364923292035d39

Message:

    gfx3d: reusable VirGL backend behind the boot proof (#20)

This commit introduced:

- `gfx3d.c`;
- `gfx3d.h`;
- `gfx3d_dev.h`;
- `gfx3d_virgl.c`;
- batching;
- VirGL object management;
- shared context/target/mesh/texture/program abstractions.

This is the point where the accelerated path stopped being only a boot demonstration and became a reusable graphics subsystem.

## Public handles and device handles become separate

The refactoring explicitly separated multiple identifier domains:

- ChrisOS public Gfx3D handles;
- VirtIO resource IDs;
- VirGL object handles.

That separation is a maturity step.

Without it, application-visible identity can accidentally become coupled to device-protocol identity, making recovery, cleanup and fallback difficult.

The current `gfx3d.c` still tracks project-level objects independently from device objects.

## Resource ownership becomes explicit

The reusable backend introduced bounded tables for contexts, targets, meshes, textures and programs.

Objects track ownership and generation.

The VirGL side separately tracks DMA-backed resources and object handles.

This evolved graphics from "issue a proof command stream" to a resource-lifetime architecture.

That change also made host tests for creation/destruction meaningful.

## DMA strategy becomes part of the backend

Current `gfx3d_virgl.c` documents a persistent DMA slab for buffers and textures, with dedicated backing for some render targets.

The backend tracks slices, device resources, ownership and submitted work.

This is a later-stage graphics concern absent from the initial software renderer:

    software renderer:
        CPU memory is directly the rendering medium

    VirGL backend:
        guest objects must be mapped onto device resources,
        command objects and DMA ownership

The historical shift is therefore also a memory-ownership shift.

## Software fallback becomes policy

The current `gfx3d_boot()` supports:

- forced mock;
- forced software;
- forced VirGL;
- automatic mode.

In automatic mode:

- if the device is available, use VirGL;
- otherwise use software.

If VirGL is later marked lost and the mode was not forced, the backend degrades to software.

This behavior is the architectural descendant of the 25 September proof's "failure falls back to software 3D" policy.

The fallback was not discarded when the backend became reusable.

## Software rendering was retained deliberately

It would be incorrect to describe software graphics as merely obsolete pre-GPU code.

It still provides:

- fallback when VirGL is unavailable;
- host-testable behavior;
- semantic reference for shaders;
- simple rendering for components not migrated to Gfx3D;
- a path independent of virtual-GPU protocol complexity.

The architecture became multi-backend rather than GPU-only.

## Cursor integration exposed scanout edge cases

After reusable VirGL landed, cursor behavior exposed integration bugs.

Commit:

    7c1937f70d0be58ba7f0ad66653f3bf384dbfe29

attempted to ensure the VirtIO-GPU cursor resource was copied into host-visible backing before display.

Later the same day, commit:

    40c69bb2c9c5466e4ef81dbe8dcfe59b0427ee0b

changed the approach again, with the message:

    Draw the pointer in the scanout and keep it under the QEMU cursor.

The commit record explains that input/DMA constraints and cursor visibility required software painting behavior.

This is a useful historical example because it shows that "hardware cursor support" is not a binary capability.

It depends on:

- resource format;
- DMA visibility;
- scanout transitions;
- input-device behavior;
- hypervisor implementation.

## Current 2D presentation path

At revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, the desktop still paints through the software graphics layer.

`gfx_present()`:

1. iterates dirty regions;
2. copies changed lines from back buffer to front buffer;
3. combines the dirty region for hardware notification;
4. calls `hw_gpu_flush_rect()` in the freestanding build;
5. clears the dirty list.

That is the surviving desktop architecture after the VirGL work.

VirGL did not replace the basic 2D desktop compositor.

## Current Gfx3D model

The reusable 3D layer now presents a separate abstraction.

It owns bounded pools for:

- contexts;
- targets;
- meshes;
- textures;
- programs.

The selected backend can be:

    software
    VirGL
    mock

This separation means the high-level API is not forced to know how each backend represents GPU resources.

It also makes backend loss and test substitution possible.

## Current VirGL device model

The current VirGL backend tracks device contexts, surfaces, resources, DMA slices, object pools and command batches.

The source explicitly distinguishes:

- VirtIO resource IDs;
- VirGL object handles;
- ChrisOS public handles.

Submissions are synchronous in the current design.

A frame fence is recorded, but staging memory is not reused before the submit returns.

This is a much stronger ownership model than the initial proof scene.

## Current shader model

The shader pipeline remains split between:

    source frontend
        |
        v
      ChrisOS IR
       /      \
      v        v
 software     TGSI
 executor     VirGL

The compiler cache, verifier, program linker and serialized CSIR support grew around this model.

Historically, that means the project chose an internal semantic layer instead of making application code emit TGSI directly.

TGSI remains a backend format.

## Mine Chris as a transition boundary

Mine Chris is especially useful for understanding the transition.

The software voxel renderer predates the VirGL backend.

When compiled shaders were connected to the VirGL proof, the historical commit explicitly noted that Mine Chris world shaders linked but voxel drawing had not moved through VirGL.

The current tree still retains the software voxel/triangle stack alongside Gfx3D.

Therefore Mine Chris should not be used as evidence that the whole graphics stack became hardware accelerated on 25–26 September.

It represents a mixed-era application boundary.

## The architecture did not evolve linearly

A simplified narrative would be:

    framebuffer -> software 3D -> GPU -> shaders

The real history is more complex:

    framebuffer/desktop
          |
          +---- software 3D ------+
          |                       |
          +---- scanout ----------+---- current system
                                  |
                           VirtIO-GPU/VirGL
                                  |
                            shader compiler
                                  |
                          reusable Gfx3D API

Software paths were retained while accelerated paths were added.

Some application integration lagged behind lower-level capabilities.

This is normal for an experimental operating system and should be represented explicitly rather than hidden.

## Evidence quality also evolved

The graphics history is not only a feature history.

It is an evidence history.

Early work was primarily demonstrated by visible desktop behavior.

Later stages gained:

- host-testable shader compilation;
- IR verification;
- VirGL command tests;
- resource-lifetime checks;
- matrix ABI comparisons;
- backend fallback logic;
- QEMU graphics gates;
- current documentation specifications.

A capability becomes substantially easier to trust when its behavior can be tested without relying only on visual inspection.

## Historical milestones

| Date | Commit | Architectural meaning |
|---|---|---|
| 2026-09-18 | `13b8aa2` | current gfx/wm layout consolidates; Gfx2D added |
| 2026-09-18 | multiple W03–W09 commits | desktop becomes a richer consumer of 2D graphics |
| 2026-09-20 | `89e3587` | broad software 3D/voxel/z-buffer pipeline added |
| 2026-09-20 | `158d0c7` | immediate graphics optimization pass |
| 2026-09-22 | `9e26685` | Doom port increases integration pressure |
| 2026-09-23 | `794dec7` | desktop scanout path strengthened |
| 2026-09-25 | `a894bf7` | VirtIO-GPU/VirGL proof with real 3D submits |
| 2026-09-25 | `4f911d1` | ChrisOS GLSL-subset compiler and CSIR added |
| 2026-09-25 | `90e0176` | compiler-generated TGSI drives proof scenes |
| 2026-09-26 | `011dfb2` | reusable Gfx3D/VirGL backend extracted |
| 2026-09-26 | `7c1937f`, `40c69bb` | cursor/scanout integration corrected |

The table is a map, not a substitute for the individual commit diffs.

## Architectural lessons

### Preserve a software reference path

The software renderer made it possible to develop 3D semantics before the accelerated backend existed and remains useful after it.

### Separate presentation from rendering

Framebuffer scanout and 3D acceleration evolved independently.

That separation reduced coupling.

### Hide transport-specific formats behind a backend

Applications target Gfx3D and shader programs, not raw VirtIO descriptors or TGSI command text.

### Make ownership explicit before scaling objects

The reusable backend introduced clear object domains only after the proof established feasibility.

That order is rational for experimentation, but the proof architecture should not become the permanent API accidentally.

### Tests change the maturity level of a subsystem

Host-testable shader compilation and VirGL object/resource tests made later claims stronger than visually successful demos alone.

## Superseded assumptions

Historical snapshots can now be misleading if read without revision context.

The following statements were true only for earlier stages or were incomplete:

- ChrisOS graphics are software-only;
- VirtIO-GPU is only scanout;
- VirGL exists only as a boot demo;
- shaders are hard-coded backend strings;
- Gfx3D has no backend fallback;
- a hardware cursor is always the visible pointer;
- Mine Chris using shaders implies voxel rendering uses VirGL.

Current documentation must use current sources, while this chapter preserves when those earlier interpretations were valid.

## Current architecture summary

At revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, the graphics stack is best described as layered and multi-backend:

    desktop/apps
        |
        +--> software 2D compositor
        |       |
        |       +--> framebuffer/scanout flush
        |
        +--> Gfx3D
                |
                +--> software backend
                |
                +--> VirGL backend
                        |
                        +--> VirtIO-GPU

    shader source
        |
        v
    ChrisOS shader IR
       /       \
      v         v
 software      TGSI -> VirGL

This is the endpoint of the history described here, not the architecture that existed at every earlier commit.

## Revision note

This chapter was reconciled against current ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56` and the graphics-history milestones listed above.

Future graphics changes should extend this timeline only when they change a real architectural boundary: backend ownership, rendering/presentation split, shader contract, resource model, recovery policy or validation evidence.
