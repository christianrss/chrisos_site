---
id: window-manager
lang: en
type: technical-chapter
volume: 11-desktop
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/wm/task.h
  - kernel/wm/task.c
  - kernel/wm/ui.h
  - kernel/wm/ui.c
  - kernel/wm/desktop.c
  - kernel/tools/app_window.h
  - kernel/tools/app_window.c
  - compiler/lang_pipeline.c
  - kernel/lang/clvm_sys.c
  - LIB/WIN.CC
  - APPS/TASKBAR/TASKBAR.CC
  - tools/test_chrisc_apps.c
symbols:
  - task_system_init
  - task_spawn
  - task_close
  - task_raise
  - task_move
  - task_resize
  - task_minimize
  - task_maximize
  - task_restore
  - task_id_at
  - task_focus_at
  - task_focused_id
  - task_run_all
  - app_window_open
  - desktop_frame
depends_on:
  - desktop-applications
  - gfx2d
  - desktop-compositor
related:
  - input-routing
  - chriseditor
  - chrisshell
  - file-manager
  - clvm-syscalls
---

# Window manager and task model

## Scope

ChrisOS uses a compact in-kernel task/window model for desktop composition.

The implementation is not a separate privileged window-server process. Window metadata, focus, z-order, native task runners and CLVM application surfaces are coordinated inside the kernel and language runtime.

The system is split across two layers:

1. **kernel window/task state** in `kernel/wm/task.c`;
2. **application-side/window-chrome behavior** in `kernel/tools/app_window.c` and `LIB/WIN.CC`.

That distinction is essential.

The kernel owns task identity, active state, frame geometry, focus, z-order, minimize/maximize mode and execution ordering. ChrisC applications can draw their own chrome and request surface operations through CLVM syscalls.

![Window manager data flow](../../assets/diagrams/window-manager-en.svg)

## Task table

The kernel keeps a fixed global table:

    Task g_tasks[TASK_MAX]

with:

    TASK_MAX = 32

A Task contains:

- integer task ID;
- active flag;
- 32-bit z value;
- TaskType;
- TaskRect;
- WindowState;
- runner callback;
- bounded title;
- type-specific state union.

The task ID is the table index.

IDs are therefore stable while an entry is active but can be reused after close.

There is no dynamically allocated task object per window.

## Geometry

TaskRect contains:

    x
    y
    width
    body_height

The name `body_height` is historical.

For application windows several code paths use the value as the total surface/window height, including chrome.

For game-style kernel chrome, the client area begins below:

    APP_CHROME_H = 20

and its height is computed as:

    frame.body_height - APP_CHROME_H

Code working with TaskRect must therefore follow the owning path's convention rather than assume `body_height` always excludes title chrome.

## Window state

WindowState stores interaction and lifecycle data:

    dragging
    drag_offset_x
    drag_offset_y
    resizing
    resize_mouse_x
    resize_mouse_y
    resize_start
    mode
    restore

The mode is one of:

    TASK_WINDOW_NORMAL
    TASK_WINDOW_MINIMIZED
    TASK_WINDOW_MAXIMIZED

`restore` remembers the previous frame used when returning from maximized mode.

Drag and resize state is per task.

## Initialization

`task_system_init` clears all 32 task entries.

It then initializes:

    g_next_z = 1
    g_focused_id = -1

`desktop_init` calls task-system initialization before input setup and initial desktop clear.

Desktop applications are booted separately by `desktop_boot_apps`.

The standard boot path starts at least:

- the desktop CLVM application;
- the taskbar CLVM application.

Optional smoke/game workloads can also be launched.

## Spawning

`task_spawn` requires:

- a nonzero TaskType;
- a non-null TaskRunner;
- positive width;
- positive body_height.

It scans for the first inactive slot.

If all 32 entries are active, spawn fails with -1.

A successful spawn:

1. clears the chosen task entry;
2. marks it active;
3. installs type/frame/runner;
4. initializes normal window mode;
5. stores the frame as the restore frame;
6. assigns a new z value;
7. initializes type-specific defaults;
8. sets the new task as focused.

Therefore newly spawned windows come to the front logically.

## Z-order

The z-order source is:

    static uint32_t g_next_z

Each spawn and raise performs:

    task->z = g_next_z++

A larger z value is visually above a smaller one.

There is no linked z-list.

Finding the top task at a coordinate scans the entire task table and selects the matching task with largest z.

Rendering works in the opposite direction: `task_run_all` repeatedly finds the smallest z greater than the previously emitted z.

This produces back-to-front drawing.

## Rendering complexity

With at most 32 tasks, `task_run_all` uses repeated full-table searches.

In the worst case:

    O(TASK_MAX^2)

per frame for task ordering.

Because TASK_MAX is fixed at 32, the practical upper bound is small.

A larger desktop model would normally use an ordered list/tree or a precomputed z-sorted array.

## Z-counter overflow

The current z sequence is a monotonically increasing uint32_t.

There is no renormalization when `g_next_z` approaches UINT32_MAX.

After wraparound, a newly raised task can receive a low z and no longer sort as the top window.

This requires an extremely large number of raises in normal use, but it is still a correctness boundary.

A robust implementation can renormalize active tasks while preserving order before overflow.

## Focus

Global focus is represented by one integer:

    g_focused_id

Only one task is focused at a time.

`task_is_focused` requires:

- non-null task;
- active task;
- task ID equal to g_focused_id.

A spawn focuses the new task.

A normal raise also focuses it.

Focus is therefore strongly coupled to z-order.

## Hit testing

`task_id_at(x, y)` scans all tasks.

A task participates only when:

- active;
- not minimized;
- point lies inside its frame.

Among all matches, the greatest z wins.

The geometry check is half-open:

    x >= left
    x < left + width
    y >= top
    y < top + height

This avoids two adjacent windows claiming the exact same right/bottom boundary pixel.

## Focus on pointer press

At each desktop frame, `desktop_frame` snapshots pointer state.

When a new left press is detected, it calls:

    task_focus_at(mouse.x, mouse.y)

The function selects the highest-z window at that coordinate.

Ordinary windows are raised when focused.

A window recognized as full-screen wallpaper is focused without being raised.

If no task is hit:

    g_focused_id = -1

The input-routing chapter documents how keyboard/text events are then delivered.

## Wallpaper special case

`task_focus_at` identifies a wallpaper-like task when its frame begins at or above the origin and covers at least the full graphics width/height.

That task can receive focus without consuming a new highest z value.

The same full-screen geometry concept is also used by the `surf_raise` syscall to avoid raising a desktop-like surface.

This is a heuristic based on geometry, not a dedicated “desktop” task class.

A full-screen non-desktop application can therefore resemble wallpaper to this policy depending on its frame.

## Raise semantics

`task_raise`:

- ignores invalid IDs;
- restores a minimized task to NORMAL;
- marks its frame dirty when restoring from minimized;
- assigns a new z;
- focuses it.

It does not restore a maximized task to normal.

Thus “raise” and “restore from maximized” are distinct operations.

## Closing

`task_close`:

1. finds the active task;
2. paints over its old frame with desktop color;
3. clears its Task entry;
4. if it was focused, sets focus to -1.

It does not automatically select the next highest-z visible task as the new focus.

That means keyboard focus can become temporarily empty after the front window closes.

The next pointer focus action or explicit raise selects a new target.

## Focus fallback limitation

Both close and minimize can remove the focused task.

Neither operation performs:

    focus = highest remaining visible task

This is a user-visible policy difference from conventional desktop window managers.

It is simple and deterministic but leaves focus gaps.

A future focus policy should probably centralize close/minimize/raise transitions and pick a deterministic fallback.

## Move

`task_move` saves the old frame, erases it with desktop color, updates x/y and marks the new frame dirty.

Moving a maximized task changes its mode back to NORMAL.

The function itself does not clamp coordinates to screen bounds.

Clamping is done by higher layers such as `app_game_chrome` and `LIB/WIN.CC`.

The CLVM `surf_move` syscall only clamps y to zero; x can remain negative.

Therefore geometry policy is distributed between caller and kernel primitive.

## Resize

`task_resize` rejects non-positive dimensions.

It erases the old frame, updates width/body_height, exits maximized mode if needed, and marks the new frame dirty.

As with move, the primitive does not enforce desktop bounds.

Higher-level chrome code chooses minimum sizes and clips dimensions against display/taskbar limits.

## Minimize

`task_minimize`:

- erases the frame;
- sets mode MINIMIZED;
- cancels dragging;
- clears focus if the minimized task was focused.

The frame is retained.

A later raise can return the task to NORMAL with the same geometry.

Minimized tasks are excluded from hit testing and `task_run_all`.

## Maximize

`task_maximize` accepts an explicit bounds rectangle.

If the window was not already maximized, its old frame is saved in `window.restore`.

The task then receives the supplied bounds and mode MAXIMIZED.

Dragging is cancelled.

The kernel primitive does not itself compute the desktop/taskbar usable area.

Callers decide those bounds.

For kernel game chrome, the maximized area is approximately:

    x = 0
    y = 0
    width = display width
    height = display height - UI_TASKBAR_HEIGHT

## Restore

`task_restore` returns the window to NORMAL.

If the task was MAXIMIZED it restores the saved frame.

If the task was only MINIMIZED, its current frame is retained.

The primitive marks the resulting frame dirty.

## Two chrome models

ChrisOS currently has two major window-chrome paths.

### Kernel game chrome

`kernel/tools/app_window.c` draws title chrome for game-style CLVM applications.

It implements:

- close button;
- maximize/restore button;
- minimize button;
- title dragging;
- lower-right resize handle;
- display-bound clamping;
- scaled blit of game framebuffer into client area.

### ChrisC library chrome

Normal UI-style ChrisC applications can use `LIB/WIN.CC`.

The library draws title/body/button pixels into the application's own surface.

It then calls syscalls such as:

    surf_place
    surf_move
    surf_raise
    surf_close
    surf_resize
    surf_minimize
    surf_maximize
    surf_restore

This creates a hybrid architecture: visual chrome is partly application-side, while authoritative task geometry and z/focus state remain kernel-side.

## Why the split exists

The split lets ChrisC applications implement UI behavior without adding a new kernel function for every widget or visual style.

It also allows the kernel to retain ownership of:

- task table entries;
- execution lifetime;
- focus;
- z-order;
- surface placement;
- application close requests.

The trade-off is duplicated interaction logic between `app_window.c` and `LIB/WIN.CC`.

Minimum sizes, edge-resize rules and button handling are not defined from one shared state machine.

## CLVM surface ABI

ChrisC exposes task/window operations through numeric CLVM syscalls.

Important IDs include:

| ID | Builtin | Kernel effect |
|---:|---|---|
| 88 | surf_place(x,y,w,h) | move then resize current task |
| 89 | surf_move(x,y) | move current task |
| 90 | surf_raise() | raise current task unless full-screen wallpaper heuristic |
| 91 | surf_close() | close task, request language-slot close, halt VM |
| 113 | surf_resize(w,h) | resize viewport then task |
| 114 | surf_minimize() | minimize task |
| 115 | surf_maximize(x,y,w,h) | resize viewport and maximize task |
| 116 | surf_restore(x,y,w,h) | resize viewport, restore, move and resize |

The current CLVM task is located indirectly from the syscall graphics context.

An application cannot supply an arbitrary task ID to these surface operations.

That is an ownership property: the operation targets the task associated with its runtime context.

## Close lifecycle

Closing a CLVM application window is more than clearing pixels.

The syscall path:

1. closes the Task entry;
2. asks the language slot to close;
3. places the VM in HALTED state.

Kernel game chrome follows a similar two-part path:

    task_close(task->id)
    lang_slot_request_close(slot)

The language runtime later releases the VM/JIT/process/graphics resources associated with the slot.

This separation prevents the window table from directly owning all runtime memory.

## Task versus language slot

A TASK_APP stores:

    state.app.lang_slot

The Task object owns desktop identity and geometry.

The LangSlot owns execution/runtime resources such as:

- ClvmVm;
- code/image state;
- process ID;
- pixel buffer/graphics context;
- JIT code;
- guest memory;
- debug state.

The association must remain valid in both directions.

If `app_run` finds that the language slot is no longer used, it closes the task automatically.

## Application rendering

`app_run` distinguishes game-like viewports from ordinary UI apps.

For a game:

- kernel chrome is drawn;
- client dimensions are derived from task frame;
- the guest framebuffer is scaled to that client rectangle.

For an ordinary UI app:

- the guest draws its own chrome;
- the Task frame is synchronized to the guest viewport dimensions;
- guest pixels are blitted 1:1 at the task x/y position.

This difference is why window behavior cannot be understood only from task.c.

## Dirty-region interaction

Window movement and resizing call:

    erase_task_frame(old)
    mark_task_frame(new)

The old rectangle is immediately painted with desktop color.

The new rectangle is marked dirty through graphics infrastructure.

Subsequent back-to-front task rendering reconstructs visible windows.

This is a simple compositor strategy rather than retained per-window damage history.

The exact framebuffer/dirty-region mechanism is documented in the compositor chapter.

## Input ownership

Focus affects input delivery.

`desktop_frame` determines the focused task.

Only a focused TASK_APP that is not currently dragging or resizing gets keyboard/text events forwarded to its language slot.

This prevents application input from competing with window manipulation.

Native kernel tools similarly check `task_is_focused` before draining input events.

Pointer state itself is globally readable by some UI paths, which is why focus/press consumption rules remain important.

## Draw order and focus are separate concepts

Normally task_raise modifies both z and focus.

However, they are not identical fields.

Examples:

- wallpaper can become focused without being raised;
- closing focused task sets focus to -1 while z values of other windows remain unchanged;
- task_run_all only cares about z/mode, not focus.

This separation is useful because keyboard focus and visual stacking are conceptually different.

The current API still couples them in most ordinary actions.

## Taskbar interaction

The taskbar exists as a regular CLVM application in the boot sequence.

Kernel UI definitions reserve:

    UI_TASKBAR_HEIGHT = 40

Window chrome uses that value when constraining bottom-edge movement and maximization.

The taskbar can enumerate/raise applications through task-related syscall services.

Thus it is not the owner of the task table; it is a client of kernel task/runtime information.

## Fixed capacities and ownership

The task model avoids dynamic task metadata allocation.

Advantages:

- bounded metadata memory;
- stable task-array storage;
- simple IDs;
- no allocator failure after table slot selection.

Trade-off:

- at most 32 active task entries;
- IDs are recycled;
- external code must not treat a task ID as globally unique across time.

Task-specific resources outside the Task table need independent cleanup.

For CLVM apps, language-slot teardown performs that cleanup.

## Concurrency model

The task table has no internal lock.

The normal desktop model mutates it from the kernel UI/runtime execution path.

There are no atomic operations around:

    g_tasks
    g_next_z
    g_focused_id

If future SMP workers manipulate tasks concurrently, explicit locking or serialized message delivery will be required.

Current correctness therefore depends on window-manager operations being effectively serialized.

## Failure behavior

The API favors safe no-op behavior for invalid task IDs.

Examples:

- task_get returns null;
- move/resize/raise/close return without action;
- invalid spawn returns -1.

There is no separate window-manager error object.

Syscall wrappers may translate invalid argument conditions into CLVM syscall failure while “no associated task” is sometimes treated as successful no-op.

That distinction should remain explicit at ABI boundaries.

## Geometry overflow considerations

Task coordinates and dimensions are signed int.

Several hit-test calculations use expressions such as:

    frame.x + frame.width

without overflow-safe widening.

Normal desktop geometry is far below INT_MAX.

However, raw internal callers supplying extreme values could overflow signed arithmetic.

The CLVM surface ABI partially validates positive sizes, but not every move coordinate is constrained.

A hardened window boundary should use checked geometry arithmetic and central screen-bound normalization.

## Validation evidence

Current evidence includes:

- host compilation of the desktop/application ChrisC lists in `tools/test_chrisc_apps.c`;
- runtime task/window code exercised in the QEMU desktop path;
- application chrome logic used by normal UI applications through `LIB/WIN.CC`;
- game-window lifecycle exercised through application launch and game smoke paths;
- CLVM syscall integration for surface placement/resize/close.

The inspected source set does not contain a dedicated host-side `test_task.c` covering task state transitions.

That is a notable validation gap.

## High-value missing tests

A focused task/window test suite should cover:

- spawn capacity at 32 tasks;
- z-order selection for overlapping windows;
- raise and focus;
- minimize exclusion from hit testing;
- maximize/restore frame preservation;
- close of focused task;
- deterministic focus fallback policy;
- z-counter renormalization/wrap behavior;
- task_run_all back-to-front order;
- wallpaper special-case focus;
- extreme geometry values;
- CLVM surface syscall ownership;
- close synchronization between Task and LangSlot;
- drag/resize input capture and edge cases.

## Current limitations

At the documented revision:

- task metadata uses a fixed 32-entry table;
- z-order is a monotonically increasing uint32 without overflow renormalization;
- closing/minimizing the focused task does not automatically focus the next visible task;
- hit testing and render ordering scan the fixed table rather than using an ordered structure;
- geometry clamping is distributed across callers instead of centralized in task.c;
- signed coordinate arithmetic is not overflow hardened;
- the desktop/wallpaper exception is geometry-based rather than represented by an explicit role;
- kernel game chrome and ChrisC `LIB/WIN.CC` duplicate parts of drag/resize/button policy;
- there is no internal locking around task/focus/z global state;
- no dedicated host unit-test suite for the core Task state machine is evident;
- task IDs are reusable and are not generation-tagged handles.

## Roadmap boundary

A stronger window manager could add:

- generation-tagged task/window handles;
- z-order renormalization;
- explicit desktop/taskbar/window roles;
- centralized geometry constraints;
- deterministic focus fallback;
- one shared chrome/window-state policy;
- per-window damage tracking;
- lock/message-based mutation for SMP;
- explicit pointer capture ownership during drag/resize;
- a compositor-facing ordered window list;
- a dedicated task/window host test suite.

Those are future changes until implemented in source and tests.

## Source map and revision

`kernel/wm/task.h` defines Task, TaskRect, WindowState, task modes and the public task API.

`kernel/wm/task.c` owns the task table, z-order, focus, geometry state and back-to-front runner ordering.

`kernel/wm/desktop.c` initializes the desktop, chooses focus on pointer press, forwards focused application input and runs all tasks each frame.

`kernel/tools/app_window.c` implements kernel-side chrome and scaled game-window presentation.

`LIB/WIN.CC` implements ChrisC-side UI window chrome and surface manipulation.

`kernel/lang/clvm_sys.c` maps surface builtins to authoritative Task operations.

`compiler/lang_pipeline.c` owns the CLVM language slots associated with TASK_APP windows.

All current-behavior claims in this chapter were reconciled against ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.
