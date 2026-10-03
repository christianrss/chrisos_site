---
id: mine-chris
lang: en
type: technical-chapter
volume: 11-desktop
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - GAMES/MINE/MINE.CC
  - GAMES/MINE/MINE.LST
  - GAMES/MINE/STATE.CC
  - GAMES/MINE/PLAY.CC
  - GAMES/MINE/GEN.CC
  - GAMES/MINE/AI.CC
  - GAMES/MINE/SAVE.CC
  - GAMES/MINE/SKY.CC
  - GAMES/MINE/CUBE.CC
  - GAMES/MINE/UI.CC
  - LIB/BODY.CC
  - LIB/CLIP.CC
  - LIB/ANIM.CC
  - LIB/SIM.CC
  - LIB/HIT.CC
  - tools/test_mine_spawn_view.c
symbols:
  - paint_world
  - boot_gfx
  - play_step
  - spawn_player
  - boot_actors
  - shoot
  - break_block
  - place_block
  - ai_step
  - gen_world
  - save_pack
  - save_write
  - save_read
  - respawn
  - clock_h
  - sky_frame
depends_on:
  - input-routing
  - desktop-applications
  - chrisc-clvm
  - software-3d
  - mine-graphics
---

# Mine Chris: a voxel game as a ChrisOS integration workload

Mine Chris is a first-person voxel game implemented in ChrisC and distributed as `GAMES/MINE/MINE.CLV`. In the documentation curriculum it is significant less as a standalone game than as an integration workload: one program exercises the CLVM runtime, input, voxel storage, software 3D, simulation, audio, filesystem persistence, UI and application loop.

The reviewed source is modular at the ChrisC level. `MINE.CC` includes shared simulation/graphics libraries and game-specific state, generation, sky, persistence, AI, play and UI modules. `MINE.LST`, however, contains only `GAMES/MINE/MINE.CC`; the included files are pulled transitively by the source itself.

## Runtime structure

```text
MINE.CLV
   |
   +-- input -------- keyboard + relative/captured mouse
   +-- simulation --- actors + collision + voxel queries
   +-- world -------- voxel generation + block edits
   +-- rendering ---- camera + world + mesh actors + HUD
   +-- environment -- clock + daylight + rain
   +-- audio -------- tone + PCM
   +-- persistence -- MINE.SAV
   +-- UI ----------- menu + pause + inventory + HUD
```

The game is useful as a systems test because these paths must work together frame after frame.

## Main loop and modes

`main()` requests an 800×600 viewport, initializes graphics state and starts with `g_mode = 0`. The loop runs until mode 9.

Mode 0 displays the menu. Gameplay uses mode 1, mode 2 is pause, mode 3 is inventory and mode 5 is used after the tower completion condition. Escape-like and inventory keys switch between these states. During active gameplay, `play_step()` updates the simulation, then `paint_world()` draws the scene and `ui_hud()` overlays game state.

This is a direct state-machine architecture rather than a general scene framework.

## Frame scheduling and subsystem cadence

The outer game loop performs one logical iteration and then calls `wait(1)`. During active gameplay, `play_step` runs before world rendering and HUD painting.

Not every subsystem updates on every iteration. AI is guarded by:

```text
(ticks() / 8) % 2 == 0
```

so AI work is enabled for alternating eight-tick windows rather than being called unconditionally every frame. Projectiles and player simulation, by contrast, are handled directly in `play_step` each active iteration.

This distinction matters when interpreting game behavior as an OS workload. Rendering cadence, player physics and AI cadence are related but not identical clocks.

## State representation

`STATE.CC` defines a compact `Actor` structure with position, velocity, yaw, pitch, kind, state, timer and bit-field flags for ground, water, bow and alive state. The global actor pool contains 16 entries. Entry zero is the player; the remaining slots are reused for world actors, pickups and projectiles.

The game also keeps a 16-entry inventory, resource counters, environmental flags, scene/physics handles, palette and audio buffers, plus a snapshot used for checkpoint-style respawn.

Fixed-size state is a deliberate property of this revision. Mine Chris does not establish an unbounded entity-component system.

## Voxel world generation

`GEN.CC` constructs a bounded authored voxel world. `putb()` rejects coordinates below 1 and above x/z 126 or y 60 before calling `voxel()`. `gen_world()` fills a region with terrain, water, structures, trees and special blocks, then sets `g_built` so generation is performed once for the current game state.

The world is therefore generated procedurally by deterministic placement code, but it is not an infinite procedural terrain generator. The source describes a finite designed play area.

## Player movement and camera

`spawn_player()` searches downward for solid terrain and positions actor zero above it. `play_step()` reads mouse deltas and keyboard state, updates yaw/pitch and applies movement velocity relative to yaw. Pitch is clamped between -50 and +50 degrees.

The current source explicitly documents its convention: positive screen-space mouse Y increases pitch because the 3D forward-vector convention uses negative sine for vertical direction.

Movement is passed through `sim_move()`. Ground state is recomputed with `sim_blocked()`, while water is detected through `voxel_get()` and reduces horizontal velocity.

The game uses mouse capture and relative motion during gameplay, making Mine Chris a practical consumer of the input-routing mechanisms documented earlier in this volume.

## Block interaction

The game can remove and place voxels. `break_block()` samples a point in front of the player at a reach of 2.2 units, validates the target and replaces the voxel with zero. Valid block IDs are credited to the inventory. `place_block()` maps selected hand slots to block IDs, checks inventory quantity and places a block only into an empty target cell.

This path is important architecturally because rendering is not the only consumer of the voxel world: game logic reads and mutates the same world representation.

## Bow and projectiles

`shoot()` converts accumulated charge into a bounded scale between 0.4 and 2.2. It finds a free actor slot, decrements the arrow count and creates a projectile actor with velocity derived from player yaw and pitch. The action also uses tone/PCM output.

A high charge can additionally harvest certain nearby voxel types before the projectile is allocated. If no actor slot is free, no projectile is created.

The fixed actor pool therefore creates a visible resource limit in gameplay and simultaneously exercises bounded runtime state.

## Actor-pool ownership and collision cost

The fixed actor array is also the ownership model. A slot is considered reusable when `kind == 0`. Projectile creation scans slots 1 through 15 for the first free entry. Pickups and mobs use the same storage.

The projectile/mob collision path performs a bounded nested scan: every projectile candidate is compared against actor slots 1 through 7 using `body_hit` or `clip_ray_aabb`. With a 16-entry pool this remains constant-bounded in practice, but the design is structurally quadratic if generalized to a larger homogeneous actor set.

A projectile that collides or times out sets `kind = 0`, returning the slot to the pool. There is no allocator, free list or generational handle protecting against stale references because gameplay code addresses slots directly.

## Actors and AI

`boot_actors()` initializes the 16-slot pool, creates the player and seeds several actors/pickups at fixed world coordinates. `AI.CC` updates non-projectile/non-pickup actors using a small state machine based on actor kind, rain, game phase, distance to the player and a timer.

Movement is deliberately simple. Actors choose small x/z velocity components and perform voxel occupancy checks before movement. This is not pathfinding over a navigation mesh; it is a compact behavior system suitable for exercising simulation primitives.

## Rendering

`paint_world()` sets the camera from actor zero, renders the sky and voxel world, then iterates through the remaining actor slots. Active actors are rendered through `draw_mob()` with state-dependent vertical animation and color selection.

`CUBE.CC` defines eight vertices for a small box-like actor mesh, initializes an identity transform and submits the mesh through `meshf()`. This provides a minimal mesh workload alongside the voxel world renderer.

Mine Chris therefore connects higher-level gameplay state to lower-level geometry and rasterization facilities rather than treating 3D output as a pre-rendered asset.

## Day, night and weather

`SKY.CC` derives an in-game hour from `ticks()` plus `g_bias`. The clock cycles over 24 values. Hours 6 through 17 are treated as day, while rain is enabled from hour 16 through 18.

The sky path changes light parameters and background fill according to day/night/rain state. It also updates a texture offset from the tick counter. `sky_flip()` shifts the time bias to move between day and night ranges.

This is a deterministic environmental model, not a meteorological simulation.

## Menus, HUD and inventory

`UI.CC` implements pointer-tested buttons for the main menu and pause menu. The main menu offers play, continue and exit. Continue initializes the world if needed and then attempts `save_read()`.

The pause UI exposes continue, checkpoint, inventory and exit-from-phase actions. The inventory displays item counts plus arrows, wood and pearls. The HUD displays in-game hour, phase, weather state, transient notifications, crosshair, hand slots and FPS.

The UI is rendered directly with primitives such as `fillrgb()`, `text()`, `line()` and `pixel()` rather than through a large widget toolkit.

## Progression

The reviewed gameplay code has explicit phase transitions. The initial state is phase 1. Collecting enough wood and entering the relevant region advances to phase 2; collecting enough pearls and reaching the far side advances to phase 3. Reaching a designated high block sets mode 5, for which the HUD displays the tower-completed message.

These rules are hard-coded game logic and should not be generalized into a quest engine.

## Save-file byte contract

`save_pack` writes a compact fixed-layout record into `g_sav[48]`, while file I/O writes 40 bytes.

The currently assigned offsets are:

| Offset | Meaning |
|---|---|
| 0 | marker 77 |
| 1 | phase |
| 2–4 | integer-converted player x/y/z |
| 5 | integer-converted yaw |
| 6 | wood |
| 7 | pearls |
| 8 | arrows |
| 9 | currently unassigned by `save_pack` |
| 10–25 | 16 inventory counters |
| 26–39 | currently unassigned by `save_pack` |

The conversion from floating player coordinates/yaw to integer and then byte storage is intentionally lossy. Loading reconstructs floats from those stored byte values, not the original sub-unit positions.

There is also no stored pitch, velocity, actor-pool state, weather bias, voxel mutations or complete environmental state.

## Save and checkpoint model

`SAVE.CC` maintains two different persistence concepts. `g_snap` is an in-memory player snapshot used by `respawn()`. `MINE.SAV` is a filesystem save.

`save_pack()` writes a compact byte representation containing a marker value, phase, integer-converted player position/yaw, resource counts and 16 inventory entries. `save_write()` writes 40 bytes to `MINE.SAV`; `save_read()` reads 40 bytes and accepts the data only when the first byte equals 77.

This format is intentionally small. The reviewed code does not establish versioning, checksums, atomic replacement, schema migration or robust corruption recovery. It also does not persist the complete mutable voxel world or all actor state.

## Input and camera edge handling

`play_step` consumes both absolute pointer coordinates and relative deltas. On the first look iteration it snapshots the pointer position. Relative deltas outside the range -60..60 are discarded as implausible jumps.

The code also retains keyboard-arrow fallback behavior when the absolute pointer lies near screen edges. Pitch is clamped to [-50, +50], while yaw is allowed to accumulate.

This hybrid input path makes the game a useful regression workload for pointer capture because a sign or coordinate-convention bug is immediately visible as inverted or displaced camera motion.

## Audio

Gameplay calls `tone()` for short event feedback and `pcm_write()` when firing. Mine Chris therefore exercises both simple tone generation and a PCM-facing path. The small `g_pcm[64]` buffer is initialized during graphics/game bootstrap.

Audio here is functional integration rather than a full mixer or asset-streaming engine.

## Why Mine Chris belongs in the OS documentation

Mine Chris crosses many ChrisOS subsystem boundaries in one executable:

```text
input -> game state -> simulation -> voxel mutation
                         |
                         v
                 camera / geometry
                         |
                         v
                     graphics

ChrisFS <-> save data        audio <- gameplay events
```

A kernel or runtime feature can appear correct in isolation and still fail when combined with input capture, continuous simulation, filesystem calls, rendering and audio. A game creates sustained cross-subsystem pressure that small unit demonstrations do not.

## Executable evidence

The repository contains `tools/test_mine_spawn_view.c`. It configures the math3d camera at the Mine Chris spawn convention, projects a ground point one step in front and verifies that it lands below the 800×600 horizon. It then projects a high point and verifies that it lands above the horizon.

That test is useful evidence for the camera/view convention that previously produced inverted-looking spawn behavior. It does not execute `MINE.CLV`, generate voxels, run AI, test saves or exercise the desktop input path.

Those remaining contracts still need application-level or QEMU regression gates.

## Algorithmic cost summary

| Operation | Current structure | Cost |
|---|---|---|
| world draw actor loop | 15 non-player slots | O(A) |
| find projectile slot | scan slots 1–15 | O(A) |
| AI update | scan slots 1–15 | O(A) |
| projectile-vs-mob checks | nested bounded scans | O(A²) structurally |
| find ground at spawn | y from 60 downward | O(60) |
| save pack/load inventory | 16 entries | O(16) |
| world generation | fixed authored loops | bounded by fixed region |

The constants are intentionally small in the reviewed game. The table describes algorithm structure, not benchmark timings.

## Current limitations

The reviewed revision uses a fixed 16-actor pool, a finite authored voxel region, small hard-coded AI state machines, direct numeric input bindings, fixed inventory arrays and a compact non-versioned save format. The source does not establish networking, multiplayer, streaming terrain, a general ECS, sophisticated pathfinding or complete persistence of arbitrary world mutations.

These limits are part of what makes Mine Chris useful pedagogically: the complete path from input to simulation to rendering remains small enough to inspect while still exercising a substantial portion of the ChrisOS application stack.
