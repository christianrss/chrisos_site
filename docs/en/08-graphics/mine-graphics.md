---
id: mine-graphics
lang: en
type: technical-chapter
volume: 08-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - GAMES/MINE/MINE.CC
  - GAMES/MINE/GEN.CC
  - GAMES/MINE/PLAY.CC
  - GAMES/MINE/CUBE.CC
  - GAMES/MINE/SKY.CC
  - GAMES/MINE/UI.CC
  - kernel/gfx/voxel.c
  - kernel/gfx/voxel.h
  - kernel/lang/clvm_sys.c
  - tools/test_chunk_mesh.c
  - tools/test_mine_spawn_view.c
symbols:
  - paint_world
  - boot_gfx
  - gen_world
  - voxel_world_draw
  - voxel_set
  - draw_mob
depends_on:
  - textures
  - clipping
  - software-3d
related:
  - mine-chris
  - depth-buffer
  - triangle-rasterization
---

# Mine Chris graphics pipeline

## Scope

Mine Chris is an integration workload for the original ChrisOS software 3D stack. The game does not render its voxel world through the later programmable Gfx3D/VirGL API. Instead, its ChrisC/CLVM code drives camera state, the global voxel world, the procedural texture atlas, fixed-function lighting, float meshes, the z-buffer, and 2D UI through graphics syscalls.

A gameplay frame is organized approximately as:

    player/actor state
        -> cam(...)
        -> sky_frame()
        -> world()
        -> draw_mob(...) for actors
        -> ui_hud()

This chapter documents that composition boundary. The voxel data structure, clipping algorithm, texture sampler, and triangle rasterizer are described in their own chapters; here the focus is how Mine Chris combines them into one game frame.

## Logical viewport

The game calls `viewport(800, 600)` at startup.

Menu rectangles, HUD positions, inventory panels, and the crosshair are authored directly in this logical coordinate system. The crosshair is centered around (400,300), and the horizon regression test also assumes a vertical midpoint of 300.

The CLVM viewport syscall attempts to configure the requested dimensions and falls back to the game default if the operation fails. Width and height are then exposed to guest code through adjacent graphics syscalls.

## Frame ordering

`paint_world` first updates the camera from actor zero, the player.

It places the camera at the player's X/Z and at player Y + 1.5, then uses the player's yaw and pitch.

After camera setup it calls `sky_frame`, then `world`, then draws non-player actors.

HUD composition happens after `paint_world`.

This ordering is significant:

1. sky/background color is established first;
2. lighting and animated texture offsets are updated;
3. the voxel world renders and establishes depth;
4. actor meshes render against that depth;
5. HUD and menus draw as 2D overlays.

Changing this order can alter occlusion or overwrite previously rendered layers.

## Camera convention

The player spawns near X=72, Z=80 and is placed at the detected ground height plus approximately 1.15.

The camera is another 1.5 units above the actor origin.

Movement and look conventions are encoded directly in `PLAY.CC`.

Forward motion uses:

    vx += sin(yaw) * speed
    vz -= cos(yaw) * speed

At yaw zero, forward therefore points toward negative Z.

The source explicitly notes that positive pitch looks downward because the math3d forward-vector convention uses a negative sine for Y. Mouse screen-space positive Y is downward as well, so positive mouse delta Y increases pitch.

Pitch is clamped to -50..50 degrees.

## Camera regression evidence

`tools/test_mine_spawn_view.c` locks down a previous source of sign errors.

It configures an 800×600 screen, camera position (72,11,80), yaw zero, and pitch zero.

A ground point one step forward along negative Z must project successfully below Y=300.

A point high above the same forward location must project successfully above Y=300.

The test does not validate the entire game camera, but it establishes the intended horizon orientation and forward direction.

## Sky model

Mine Chris does not render a geometric skybox.

`sky_frame` derives an in-game hour from ticks plus a bias, then fills the whole 800×600 background with a flat color.

Hours 6 through 17 are treated as day.

Hours 16 through 18 enable the rain state.

Day, rain, and night use different background colors.

This sky pass is therefore a cheap 2D backdrop behind the depth-tested 3D world.

## Dynamic lighting

The light source also changes with time.

The game computes a sun-like direction from sine/cosine of hour×15 degrees.

During daytime it uses a brighter warm light and a higher Y position.

At night it uses a dimmer cooler light and a lower position.

The values are sent through the CLVM light syscall into the fixed-function shading state used by textured world faces and float meshes.

Because the light is updated before world rendering, every visible voxel face in that frame sees the new light state.

## Animated texture state

`sky_frame` also computes:

    wave = ticks % 100
    tex_ofs(wave / 100, 0.04)

The texture subsystem applies this global offset only to the texture slot designated as animated by the low-level texture implementation.

Mine Chris therefore gets a moving-material effect without regenerating voxel geometry or UVs.

The mechanism is global state, so it is part of frame setup rather than per-face material data.

## World dimensions

The engine voxel world uses:

    CHUNK_N = 16
    WORLD_CX = 8
    WORLD_CY = 4
    WORLD_CZ = 8

The full world is therefore 128×64×128 voxels split into 256 chunks.

Each block is stored as one byte.

Block IDs are clamped by the engine to 0..15, with zero meaning empty.

## Game-authored region

`gen_world` creates a handcrafted subset rather than filling the complete engine volume.

Most generated terrain lies around X 48..102 and Z 52..99, with structures extending vertically into the teens.

The game-side `putb` helper further restricts writes to X/Z 1..126 and Y 1..60.

That intentionally leaves an inner margin relative to the engine's 0..127/0..63 ranges.

Terrain, water, bridges, trees, tower structures, pickups, and objective markers are all built by repeated voxel writes.

## Chunk invalidation

Every `voxel_set` writes the block and marks the owning chunk dirty.

When an edited voxel lies on a chunk boundary, the adjacent chunk is also dirtied.

This is essential because a face stored in one chunk can become visible or hidden when a neighboring block in a different chunk changes.

Gameplay block breaking and placement therefore need no explicit mesh API: changing voxel data automatically schedules the appropriate chunk rebuilds.

## Chunk mesh representation

A chunk mesh is a list of exposed block faces, not a conventional indexed triangle buffer.

Each `MeshFace` stores local X, Y, Z, face number, and block ID.

Rebuilding scans all 16³ cells in the chunk.

For every non-empty block, it checks the six neighboring positions.

A face is stored only when the neighbor in that direction is empty.

Internal faces between adjacent solid blocks are omitted.

This reduces geometry substantially compared with blindly emitting all six faces per block.

## Face-list capacity

Chunk face storage starts at capacity 64 and doubles when required.

Growth stops at:

    FACE_CAP_MAX = 8192

If the list is already at the maximum, further faces cannot be appended and rebuilding returns early.

The current interface does not expose a rich diagnostic for this condition.

A pathological high-surface-area chunk can therefore be truncated rather than represented completely.

## Lazy rebuild

Chunks begin dirty after voxel initialization.

`voxel_world_draw` only calls `rebuild_chunk` for chunks that are both in the coarse camera region and currently dirty.

Once rebuilt, the chunk remains cached until a later voxel edit invalidates it.

`tools/test_chunk_mesh.c` verifies this behavior: after the first render it records `voxel_mesh_rebuilds()`, renders the unchanged scene again, and requires the rebuild count to stay constant.

## Coarse visibility selection

The renderer does not perform true chunk-frustum culling.

It constructs an axis-aligned camera-centered region approximately:

    X = camera ±48
    Y = camera ±32
    Z = camera ±48

and clamps it to world bounds.

A chunk completely outside this box is skipped.

A chunk inside the box is processed even if it lies behind the camera or outside the projected view.

The system trades culling precision for simple bounded iteration.

## Quad reconstruction

Stored faces do not contain precomputed vertex arrays.

For every visible `MeshFace`, `face_verts` reconstructs four world-space corners based on block position and one of six face orientations.

Normals come from the same ±X/±Y/±Z face table.

The face normal is transformed through the view matrix as a direction and normalized.

UV corners are fixed as:

    (0,1)
    (1,1)
    (1,0)
    (0,0)

The quad is then split into two source triangles.

## Camera-space conversion

Each of the four world-space corners is transformed through the current view matrix.

The resulting camera-space position is stored with its U/V coordinate in a small `ClipV` structure.

This makes the clipping step operate on geometry and texture coordinates together.

Lighting uses the transformed face normal, while projection uses the transformed positions.

## Near-plane clipping

Each source triangle is clipped against:

    camera-space z = 0.08

using a specialized polygon clipper.

A vertex is inside when Z >= 0.08.

When an edge crosses the plane, the code linearly interpolates X, Y, Z, U, and V at the intersection.

The result can contain zero, three, or four vertices.

A three-vertex result produces one raster triangle.

A four-vertex result is split into two triangles.

This is true geometric near clipping for voxel faces, unlike older mesh paths that simply reject a triangle when one vertex is not projectable.

## Projection and raster submission

Every clipped polygon vertex goes through `project_view`.

If any resulting vertex cannot be projected, that clipped polygon is abandoned.

Successful screen positions, software depth values, UVs, block ID, and transformed face normal are passed to `tri_fill_tex`.

The low-level textured triangle routine then performs z testing, texture lookup, and lighting.

## Material mapping

For voxel rendering, block ID is passed directly as the texture slot.

The game generates only IDs that fit the engine's 0..15 block range.

Thus a block's stored byte acts simultaneously as gameplay material identity and texture/material selection for world rendering.

Actor meshes use a different convention: `meshf` interprets values 16 and above as texture IDs offset by 16, while smaller values follow palette/fixed-color paths.

## Z-buffer lifecycle

`voxel_world_draw` calls:

    math3d_set_screen(w,h)
    zbuf_set_size(w,h)
    zbuf_clear()

before rendering chunks.

Every call to `world()` therefore starts a fresh voxel depth pass.

The CLVM world syscall also prepares the graphics z-buffer for the current guest context before invoking the voxel renderer.

The renderer's own clear remains the decisive reset for the world pass.

## Actor occlusion

Mine actors are drawn after `world()` with `meshf`.

The float-mesh path sets z-buffer dimensions but does not clear the global z-buffer internally.

Consequently, actor triangles are tested against the depth left by the voxel world.

This ordering allows terrain to occlude actors and projectiles.

A new rendering path inserted between world and actors must not clear the z-buffer if the same composition is expected.

## Actor geometry

`CUBE.CC` defines eight vertices forming a small box approximately 0.8 units wide and 0.8 units tall.

`draw_mob` renders that geometry as twelve triangles through `meshf`.

Different actor kinds reuse this same mesh with different translation, yaw, and color/material codes.

The geometry model is intentionally simple; most visual distinction comes from material selection and movement rather than separate meshes.

## Actor animation

Some actor kinds add vertical bobbing with `anim_eval1`.

The animation changes the Y coordinate passed to `draw_mob`; it does not deform vertices.

Other state transitions can add a larger vertical displacement.

This keeps animation independent of the chunk renderer and avoids skeletal or per-vertex animation costs.

## Player interactions and graphics invalidation

Block breaking, block placement, and some high-charge actions query or modify voxel state directly.

Breaking sets the selected voxel to zero.

Placement writes a material ID.

Because `voxel_set` dirties chunk meshes, the next visible world render rebuilds the affected geometry automatically.

The graphics representation therefore stays synchronized with gameplay through the voxel API.

## Rain rendering

Rain is deliberately not 3D world geometry.

When rain is active, `ui_hud` draws 24 2D line streaks.

Their X positions depend on the loop index and current ticks.

They are rendered after the world and do not use depth.

This is inexpensive but means rain does not disappear behind roofs or terrain.

## HUD and overlays

The HUD displays time, phase, notifications, crosshair, hotbar selection, FPS, and rain streaks.

The crosshair consists of two short lines plus a center pixel at approximately (400,300).

Pause and inventory screens are rectangles/text drawn in the same 2D coordinate system.

These overlays do not participate in the 3D projection or z-buffer.

## CLVM ownership boundary

Mine Chris runs through CLVM.

Kernel graphics syscalls expose light state, texture state, voxel writes/reads, world rendering, viewport control, math helpers, and mesh operations.

Before voxel operations, the syscall layer calls `voxel_for(ctx)`, which ultimately uses the global voxel ownership mechanism.

Only one application slot can own the voxel world at a time unless it is the already owning slot.

This prevents unrelated guest applications from simultaneously controlling the single global voxel state.

## World syscall

The world-render syscall prepares the per-context z-buffer and then checks voxel ownership.

If ownership succeeds, it calls `voxel_world_draw` with the guest graphics pixel buffer and current logical dimensions.

Failure in ownership or rendering propagates as a syscall error.

The guest-level `world()` function therefore hides a substantial kernel-side pipeline behind one call.

## Test evidence

`test_chunk_mesh.c` creates a 24×24 floor plus additional blocks, renders at 320×200, and requires more than 500 nonzero pixels.

It also requires more than eight unique nonzero colors, providing indirect evidence of textured/lit variation.

It requires at least one chunk rebuild on the first draw and no additional rebuild on the unchanged second draw.

`test_mine_spawn_view.c` independently validates the camera orientation at the game's 800×600 viewpoint.

Together these tests cover both local voxel rendering and Mine-specific view conventions.

## Current limitations

The Mine world path is software-rendered in this revision.

Chunk visibility is AABB-based rather than frustum-based.

There is no occlusion culling and no greedy meshing.

Stored chunk geometry is one record per exposed block face.

UV interpolation inside the old textured triangle rasterizer remains affine after the near-clipping stage.

Only the near plane receives polygon clipping.

Pathological chunks can hit the 8192-face cap.

Rain is a 2D overlay.

Actor meshes are simple boxes.

The voxel world is global rather than per-scene/per-context.

## Performance consequences

World generation is largely a one-time gameplay cost.

Steady-state frame cost is dominated by visible-region chunk traversal, lazy rebuilds, per-face reconstruction, view transformation, near clipping, projection, and textured triangle rasterization.

Block edits usually invalidate one chunk, but an edit on a chunk boundary can invalidate two or more.

The largest architectural optimization opportunities are tighter frustum culling, greedy meshing, batching exposed faces, and eventually moving the world path onto the newer programmable GPU-capable renderer.

## Revision note

This chapter was created against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. Mine Chris is documented as an integration workload over camera, voxel, clipping, texture, shading, z-buffer, mesh, CLVM, and 2D UI subsystems rather than as a separate rendering engine.
