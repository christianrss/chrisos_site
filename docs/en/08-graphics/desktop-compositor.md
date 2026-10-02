---
id: desktop-compositor
lang: en
type: technical-chapter
volume: 08-graphics
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/wm/desktop.c
  - kernel/wm/main.c
  - kernel/wm/task.h
  - kernel/wm/task.c
  - kernel/wm/ui.h
  - kernel/wm/ui.c
  - kernel/tools/app_window.c
  - kernel/gfx/graphics.h
  - kernel/gfx/graphics.c
  - kernel/lang/clvm_sys.c
  - compiler/lang_pipeline.h
  - compiler/lang_pipeline.c
  - APPS/DESKTOP/DESKTOP.CC
  - APPS/TASKBAR/TASKBAR.CC
  - tools/test_task_window.c
  - tools/test_graphics_present.c
symbols:
  - desktop_frame
  - desktop_run
  - task_run_all
  - task_raise
  - task_move
  - task_resize
  - app_window_open
  - app_run
  - lang_slot_pixels
  - lang_slot_publish
  - clvm_sys_blit_to
  - clvm_sys_blit_scaled
  - ui_draw_cursor
  - ui_undraw_cursor
  - gfx_mark_dirty
  - gfx_present
depends_on:
  - pixels-framebuffer
  - color-formats
  - gfx2d
related:
  - desktop-applications
  - window-manager
  - input-routing
  - chrisc-clvm
---

# Desktop composition

## Scope

The ChrisOS desktop is composited in software into the global graphics backbuffer and then copied to the front framebuffer through the damage-tracked presentation path.

The current composition chain is roughly:

    application/CLVM surface
        -> published slot surface
        -> Task ordered by z
        -> app/window rendering
        -> global graphics backbuffer
        -> dirty rectangles
        -> gfx_present()
        -> front framebuffer / device flush

This is a real compositor in the broad sense that multiple independently rendered surfaces are ordered and combined into one visible image.

It is not a modern GPU compositor with per-window GPU textures, asynchronous surface transactions, occlusion regions, page-flipped scanout planes or hardware composition.

The distinction is important because the current architecture's correctness, performance and synchronization properties follow from software redraw and copy semantics.

## Composition versus presentation

Two separate operations must not be confused.

Composition decides what pixels should appear in the desktop backbuffer.

Presentation transfers changed portions of that backbuffer into the front framebuffer and, on freestanding builds, asks the GPU/device path to flush the affected region.

The desktop loop performs both in order.

desktop_run repeatedly executes:

    net_poll()
    clvm_sys_frame(...)
    lang_tick(...)
    desktop_frame(...)
    gfx_present()

The compositor therefore updates the software image before gfx_present copies the dirty regions.

A successful composition does not by itself prove that the display device completed scanout.

Likewise, a correct framebuffer presentation path does not prove that windows were ordered correctly before presentation.

## The global destination surface

The final software destination is g_gfx.back from the general graphics subsystem.

This backbuffer is tightly packed by logical width.

The front framebuffer can have a different pitch.

Rendering code writes the backbuffer.

gfx_present later copies only the recorded dirty rectangles to g_gfx.front, accounting for front-buffer pitch row by row.

This means desktop composition itself can use simple x/y addressing without carrying hardware pitch through every UI operation.

The hardware-specific stride is confined to the presentation boundary.

## Application surfaces are separate from the desktop backbuffer

CLVM applications do not normally draw directly into g_gfx.back.

Each language slot has a graphics context containing its own pixel surface.

Functions such as fillrgb, text, glyph and the lower-level 2D/3D builtins modify that slot-owned surface.

The compositor later obtains a pointer through:

    lang_slot_pixels(slot)

This creates a useful separation:

- application rendering changes an application surface;
- desktop composition copies that surface into the desktop backbuffer;
- presentation copies the desktop backbuffer to the front framebuffer.

The separation reduces direct coupling between application drawing and physical framebuffer layout.

## Published front surfaces

The language runtime has an additional surface-publication mechanism.

lang_slot_publish copies the slot's active graphics pixels into front_pixels.

If the published allocation does not exist or no longer matches the slot dimensions, it reallocates a buffer of:

    width * height * sizeof(uint32_t)

and copies the current surface with gfx_fast_copy_u32.

lang_slot_pixels prefers this published front surface when its dimensions match.

Otherwise it falls back to the live graphics surface.

In the CLVM syscall path, the wait builtin publishes the slot before putting the VM to sleep.

This gives the compositor a snapshot-like surface for ordinary frame-yielding applications.

It is not an atomic multi-buffer transaction system: allocation, copying and task composition are ordinary software operations.

But it does reduce the likelihood that the compositor reads the same buffer while the guest is in the middle of drawing the next frame.

## Surface ownership and lifetime

A language slot owns its graphics state and optional published copy.

A Task of type TASK_APP stores the associated language slot ID.

app_window_open binds the two objects using:

    task->state.app.lang_slot = slot
    lang_bind_task(slot, task_id)

The task is therefore the desktop-visible lifecycle object, while the language slot owns the application execution and pixels.

If app_run discovers that the slot is no longer used, it closes the Task.

Conversely, window-close paths request that the language slot be closed.

This bidirectional association is critical: otherwise a dead VM could leave a stale window or a closed window could leave an invisible VM consuming resources.

## Task table and z-order

The window/task layer uses a fixed array of at most 32 tasks.

Each active task has a monotonically assigned z value.

task_raise assigns:

    task->z = g_next_z++

and makes that task focused.

The implementation does not normalize z values after every raise.

For the current lifetime and uint32_t counter this is simple, but a theoretical wraparound is not explicitly handled.

The important composition rule is implemented by task_run_all.

## Bottom-to-top rendering

task_run_all does not iterate the array directly.

Instead it repeatedly finds the active, non-minimized task with the smallest z value greater than the z value emitted previously.

That means tasks run in increasing z order:

    lower z first
    higher z later

Because later rendering overwrites earlier pixels in the common desktop backbuffer, higher-z tasks appear on top.

For at most 32 tasks, this selection-based traversal is bounded and simple.

Its worst-case metadata work is O(T^2), where T is the number of task slots.

With T <= 32, this cost is negligible relative to large pixel copies.

A larger compositor would normally maintain an explicit ordered list or tree.

## No general occlusion elimination

The current compositor renders active tasks in z order even if a higher opaque window completely covers a lower one.

There is no general visible-region subtraction phase.

As a result, work may be performed for pixels that are immediately overwritten by later tasks.

This is correct but not optimal.

A production desktop compositor often computes occlusion or uses retained GPU surfaces so that fully hidden regions need not be redrawn.

ChrisOS currently favors directness and testability.

## Window types and two rendering modes

app_run distinguishes game-like surfaces from ordinary UI application surfaces.

For game-like surfaces:

- the kernel draws window chrome;
- the application image is scaled into the content area;
- the application surface can remain at its own resolution.

For ordinary UI applications:

- the surface is copied 1:1;
- its Task frame is forced to match the slot dimensions;
- the kernel then paints title/borders around or over the application frame.

This is a hybrid composition model.

The application owns its content surface, while the kernel owns important desktop chrome.

## Game-like surfaces

app_is_game classifies a surface partly by dimensions.

HD game sizes between 640x480 and 1024x768 are accepted, and smaller game-oriented sizes near the CLVM default game dimensions are also recognized.

app_game_chrome draws:

- title bar;
- minimize button;
- maximize/restore button;
- close button;
- resize handle.

The content rectangle begins below the chrome.

clvm_sys_blit_scaled delegates to gfx_blit_scaled, so game content can be scaled to the current window size.

The scaler is nearest-neighbor.

This keeps the guest rendering resolution independent of the displayed window rectangle.

## Ordinary UI surfaces

Non-game CLVM applications are composed with clvm_sys_blit_to.

That function performs a 1:1 copy of the top-left overlapping region only.

It does not scale.

It clips against the desktop bounds, marks the copied rectangle dirty and performs row copies with gfx_fast_copy_u32.

After the surface copy, app_run normally paints a kernel title strip and borders.

Therefore the final pixels of an ordinary application are a combination of guest-owned content and kernel-owned chrome.

## Desktop and taskbar special cases

Two CLVM applications receive special compositor treatment.

APPS/DESKTOP/DESKTOP.CC creates a screen-sized surface and requests placement at the origin.

APPS/TASKBAR/TASKBAR.CC creates a full-width short surface placed along the bottom.

app_run recognizes these geometries after copying their slot pixels.

For a full-screen origin task it calls:

    ui_paint_desktop()

For a taskbar-like surface it calls:

    ui_paint_taskbar_strip(...)

These kernel UI functions repaint the desktop or taskbar after the CLVM surface was copied.

That means the current implementation contains duplicated/overlapping ownership: CLVM desktop/taskbar programs render their own visual content, while the kernel compositor has special-case code that paints corresponding desktop/taskbar visuals again.

The resulting behavior should not be described as a pure application-owned shell.

It is a transitional hybrid architecture.

## Why the special cases matter

The special cases have several consequences.

First, the visible desktop can differ from the pixels produced by DESKTOP.CC because the kernel repaint occurs later.

Second, changing the CLVM desktop source alone may not change every visible element.

Third, the same conceptual taskbar policy exists in both application code and kernel UI code.

This duplication increases maintenance risk.

A future architecture should choose a clearer authority:

- shell surfaces fully owned by applications; or
- shell visuals fully owned by the kernel/window manager.

Both can work, but mixed ownership requires careful reconciliation.

## Moving and resizing windows

Task geometry changes are damage-producing operations.

task_move:

1. records the old frame;
2. erases that frame using the desktop color;
3. changes x/y;
4. marks the new frame dirty.

task_resize follows a similar pattern.

This approach is simple but does not reconstruct arbitrary lower windows in the erased old region immediately.

Correct recovery depends on the normal frame pass redrawing tasks again in z order.

Therefore movement is not an isolated bitmap move.

It is a state change followed by compositor reconstruction.

## Closing and minimizing

task_close erases the task frame, clears its task slot and drops focus if necessary.

task_minimize erases the frame, changes mode, disables dragging and removes focus when the minimized task owned it.

task_run_all skips minimized tasks.

Again, erasing to the desktop color is only an intermediate state.

Lower windows that were previously covered must redraw during the frame to restore their content.

The compositor model is therefore redraw-based rather than backing-store restoration of the exact hidden pixels.

## Maximization and restoration

A maximized task stores its previous frame in WindowState.restore.

task_maximize erases the old frame, saves restore geometry when appropriate, installs the new bounds and marks the new frame dirty.

task_restore erases the current frame, restores the saved bounds when leaving maximized mode and marks the resulting frame.

The window state machine therefore separates logical geometry from rendered pixels.

The compositor is responsible for producing the new image from state every frame.

## Damage tracking

Most graphics primitives call gfx_mark_dirty.

Surface blits also mark their affected destination rectangle.

Window movement and resizing explicitly mark affected regions.

gfx_mark_dirty clips rectangles to the display and merges touching damage regions.

The global list holds at most 32 regions.

If the list overflows, it falls back to one full-screen dirty rectangle.

This ensures that the presentation stage never loses correctness merely because damage metadata capacity was exhausted.

The trade-off is potentially copying more pixels.

## Composition and damage are related but separate

Rendering into the desktop backbuffer changes pixels.

Damage tracking records which changed pixels must be copied to the front framebuffer.

A compositor bug can produce the wrong backbuffer even with perfect dirty tracking.

A dirty-tracking bug can leave the front framebuffer stale even when composition is correct.

This is why the two mechanisms are tested separately in the source tree.

## Cursor composition

The mouse cursor is software-composited into the same backbuffer.

desktop_frame performs:

    ui_undraw_cursor()
    task_run_all(ticks)
    ui_draw_cursor()

ui_draw_cursor first saves the 12x12 pixels currently under the pointer into a static buffer.

It then draws the cursor shape.

On the next frame, ui_undraw_cursor restores those saved pixels before tasks are rendered again.

This is a classic save-under cursor strategy.

It is separate from application z-order: the cursor is drawn after all tasks, so it appears above them.

## Why the cursor is software drawn

The source comments explain that the virtio-gpu cursor sprite path is accepted in the tested QEMU configuration but not visibly shown as expected.

The code still calls vgpu_cursor_move when the virtual GPU cursor is active, but it always paints a software pointer into the framebuffer so that the pointer remains visible.

This is a compatibility workaround based on observed backend behavior.

It should not be generalized into a requirement that hardware cursors are unusable.

## Cursor correctness boundaries

The save-under strategy assumes disciplined sequencing.

The old cursor must be removed before tasks repaint.

The new underlying pixels must be saved only after the desktop has been composited.

The cursor region is marked dirty both when restored and when drawn.

If unrelated code modified the backbuffer under the cursor between save and restore without participating in this sequence, restoring g_cur_under could reintroduce stale pixels.

The current single desktop frame pipeline avoids that by centralizing the cursor operations.

## Frame cadence

desktop_run waits for the global tick to advance after every frame.

While waiting, the CPU polls TLB work and executes hlt.

The frame cadence is therefore tied to the system timer rather than a display-vblank event.

There is no explicit compositor/display synchronization protocol that guarantees tear-free presentation.

A software backbuffer reduces direct drawing into scanout memory, but gfx_present still copies pixels while display hardware may be reading the front buffer.

The current architecture should therefore not be described as vsync-synchronized.

## Input and composition ordering

desktop_frame polls pointer devices before choosing focus.

A left press can raise/focus the task under the pointer.

Then queued key/text events are forwarded to the focused application slot.

Only after input routing does the frame remove the cursor, run tasks in z order and redraw the cursor.

This ordering means a click can affect z-order in the same frame in which rendering occurs.

The next task_run_all traversal sees the updated z values.

## Focus and wallpaper behavior

task_focus_at normally raises the selected task.

There is a special wallpaper test for a task covering the full framebuffer from the origin.

Such a task can become focused without being raised.

This avoids letting a desktop-background task jump above normal windows merely because the user clicked empty desktop space.

Similarly, the surf_raise CLVM operation refuses to raise a full-screen wallpaper-like task.

These policies are small but important compositor invariants.

## Memory bandwidth

Software composition can copy the same pixel several times in one frame.

A lower application may write into the desktop backbuffer, then an overlapping higher application overwrites the same region, and gfx_present finally copies the result to the front framebuffer.

Published CLVM surfaces add another possible full-surface copy when an application yields.

For a surface of W by H pixels, one full 32-bit copy moves:

    4 * W * H bytes

in each direction from the perspective of source reads and destination writes.

At desktop resolutions, redundant full-window copies can dominate CPU and memory bandwidth.

The damage system limits the final front-buffer copy, but it does not eliminate overdraw during composition.

## Concurrency model

The desktop composition path is primarily serialized by the frame loop.

task_run_all and the global backbuffer are not protected here by a compositor lock.

Published application front surfaces help separate guest rendering from compositor reads, but the architecture is not a general multi-threaded transactional compositor.

Global structures also include:

- task table;
- focused task ID;
- z counter;
- damage rectangles;
- cursor save-under state.

Code introducing concurrent rendering must define ownership and synchronization around these objects.

## Complexity

Let T be the number of active task slots and P_i the number of pixels drawn/copy-composited by task i.

The current task ordering costs at most O(T^2).

Pixel work is approximately:

    O(sum(P_i))

plus the final dirty-region presentation cost.

There is no general occlusion culling, so P_i can include fully covered regions.

Damage merging has a bounded cost because the dirty array is capped at 32 entries.

For the current small task count, pixel bandwidth is usually more significant than ordering metadata.

## Validation evidence

tools/test_task_window.c verifies several compositor-adjacent state contracts:

- minimized tasks are not run;
- raising restores a minimized task to normal rendering;
- maximize and restore preserve geometry;
- move and resize record damage;
- hit testing chooses the higher-z overlapping task;
- repeated open/close cycles reuse slots without leaking live tasks.

The stress test opens and closes 1000 tasks while checking the live task count.

tools/test_graphics_present.c verifies the presentation side:

- front-buffer pitch is honored;
- partial dirty rectangles copy only the intended area;
- unmarked backbuffer changes are not presented;
- dirty-list saturation falls back to a full-screen copy.

Together these tests cover important state ordering and presentation invariants.

## Validation gaps

There is not a dedicated host test that reconstructs a multi-window image and compares the complete composited result.

Current tests also do not fully exercise:

- overlapping semi-transparent windows;
- desktop/taskbar special-case visual equivalence;
- cursor save-under under every movement pattern;
- z-counter wraparound;
- compositor behavior under concurrent writers;
- occlusion performance;
- actual vsync/scanout timing;
- physical GPU completion.

These remain separate validation targets.

## Failure behavior

Most composition APIs are defensive but not diagnostic-rich.

A missing application pixel surface makes app_run return without drawing.

If an application's language slot disappears, the Task is closed.

If app_window_open cannot allocate a Task slot, it kills the application slot.

Surface publication allocation failure causes lang_slot_publish to clear its published dimensions and return; lang_slot_pixels can subsequently fall back to the active graphics surface.

This preserves some functionality at the cost of weaker snapshot isolation.

The compositor does not expose a structured per-frame error report.

## Security and isolation boundaries

Desktop composition is not itself a security boundary for arbitrary native memory.

The window manager trusts kernel-owned Task structures and pointers obtained from the language runtime.

CLVM drawing operations write their slot surfaces rather than arbitrary desktop addresses under the intended runtime model.

Input focus determines which application receives keyboard/text events.

This makes focus state part of the desktop's isolation contract.

However, the current documentation should not claim that the graphical architecture alone provides process-grade isolation; that depends on CLVM/process memory, syscall validation and task lifecycle mechanisms documented elsewhere.

## Current limitations

The current compositor has several explicit boundaries:

- software composition into one global backbuffer;
- maximum 32 tasks;
- O(T^2) z-order traversal;
- no general occlusion culling;
- no per-window GPU textures or hardware planes;
- no atomic surface transaction protocol;
- no explicit vblank synchronization;
- no tear-free guarantee;
- hybrid ownership between CLVM desktop/taskbar and kernel repaint code;
- nearest-neighbor scaling for game windows;
- save-under software cursor;
- fixed-capacity damage list;
- limited structured diagnostics;
- no dedicated end-to-end pixel-composition regression test.

These are current architectural properties, not requirements for future ChrisOS graphics.

## Roadmap boundary

Natural future extensions include:

- one authoritative desktop/taskbar owner;
- retained window surfaces with explicit format metadata;
- occlusion-region calculation;
- dirty regions per surface;
- generation-numbered or atomic surface publication;
- compositor-local ordered task structures;
- optional GPU texture composition;
- hardware cursor use where reliable;
- frame pacing tied to display synchronization;
- explicit presentation fences;
- end-to-end screenshot regression tests;
- measured overdraw and bandwidth telemetry.

Those features should be treated as future work until source and tests demonstrate them.

## Revision provenance

This chapter documents desktop composition as observed in ChrisOS main revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.

kernel/tools/app_window.c is the main bridge between language-slot surfaces and window Tasks. compiler/lang_pipeline.c defines surface publication and slot ownership. kernel/wm/task.c defines task ordering and window state. kernel/wm/ui.c defines desktop chrome and cursor composition. kernel/gfx/graphics.c defines dirty tracking and final presentation. kernel/wm/main.c establishes the frame order. tools/test_task_window.c and tools/test_graphics_present.c provide direct executable evidence for the state and presentation contracts described above.
