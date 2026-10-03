---
id: desktop-applications
lang: en
type: technical-chapter
volume: 11-desktop
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/wm/desktop.c
  - kernel/wm/task.c
  - kernel/wm/task.h
  - kernel/wm/ui.c
  - kernel/tools/app_window.c
  - compiler/lang_pipeline.c
  - compiler/lang_pipeline.h
  - kernel/lang/clvm_sys.c
  - APPS/DESKTOP/DESKTOP.CC
  - APPS/TASKBAR/TASKBAR.CC
  - APPS/EDITOR/EDITOR.CC
  - APPS/SHELL/SHELL.CC
  - APPS/EXPLORER/EXPLORER.CC
  - LIB/WIN.CC
  - LIB/UI.CC
  - LIB/APP.CC
  - tools/test_task_window.c
symbols:
  - desktop_init
  - desktop_boot_apps
  - desktop_frame
  - task_spawn
  - task_close
  - task_raise
  - task_run_all
  - task_focus_at
  - app_window_open
  - lang_bind_task
  - lang_slot_push_key
  - lang_slot_push_text
  - lang_slot_request_close
depends_on:
  - pixels-framebuffer
  - chrisc-clvm
related:
  - window-manager
  - input-routing
  - chrisfs
  - chriseditor
  - chrisshell
  - file-manager
---

# Desktop, windows and applications

## Scope

The ChrisOS desktop is not one monolithic GUI function. It is a hybrid of kernel-owned window/task infrastructure and CLVM applications that implement visible desktop components and first-party programs.

The kernel owns the authoritative task table, z-order, focus, device polling, keyboard/text routing, window placement and final blitting into the system graphics path. CLVM programs own application logic and their own drawing surfaces. The desktop background/launcher and taskbar are themselves CLVM programs started during desktop boot, while kernel UI code still supplies window chrome, fallback painting and common presentation primitives.

This division is central to understanding failure and ownership. Closing a window record is not identical to terminating a CLVM slot. Drawing into an application surface is not identical to presenting pixels on the physical framebuffer. Keyboard/text events are queued to the focused application slot, while pointer state is primarily polled by application/window code.

## Architectural layers

A simplified path is:

```text
USB tablet / xHCI HID / PS/2
          |
          v
      input subsystem
          |
          v
   desktop_frame()
          |
          +--> task focus / z-order
          +--> key/text -> CLVM slot queues
          |
          v
     Task table (32)
          |
          v
 application runner / surface
          |
          v
 kernel blit + window chrome
          |
          v
 graphics dirty/present path
```

At the application side:

```text
ChrisC source
   -> compiler / CLVM image
   -> LangSlot
   -> CLVM graphics context
   -> front/back pixels
   -> TASK_APP binding
   -> desktop blit
```

The window manager chapter focuses on window mechanics; this chapter focuses on how those mechanics combine with the application runtime.

## Desktop initialization

`desktop_init` resets the task system, initializes input with the current framebuffer dimensions, selects absolute pointer mode when the USB tablet is available and clears the graphics target to the desktop color.

This means task identity and focus begin from a known state. `task_system_init` clears every task slot, resets the z-order counter and sets the focused task ID to -1.

The desktop loop therefore does not inherit stale windows across an initialization boundary.

## Booting desktop applications

`desktop_boot_apps` first attempts to load `LIB/WIN.CLS`, then starts the CLVM desktop and taskbar:

- `APPS/DESKTOP/DESKTOP.CLV`;
- `APPS/TASKBAR/TASKBAR.CLV`.

The helper `boot_one` first probes the compiled CLV file. If it exists, the runtime attempts to execute it. If the image is missing or unusable, the kernel compiles the corresponding `.LST` and then runs the generated CLV.

This is an important self-hosting-oriented behavior: desktop startup can consume already-built applications but also has a compile-and-run fallback.

Optional smoke flags in ChrisFS can request Doom or World startup. Those paths are validation hooks and should not be confused with mandatory desktop components.

## Desktop and taskbar as CLVM programs

`APPS/DESKTOP/DESKTOP.CC` creates a display-sized surface, positions it at the origin and continuously draws the background and launcher icons. The current launcher exposes Shell, Files, Edit, Tasks, Ball, Doom, Preferences and Mine Chris.

A click edge launches the corresponding CLV through `app_launch`, which is a thin library wrapper over `app_spawn`.

`APPS/TASKBAR/TASKBAR.CC` similarly creates a 40-pixel-high surface at the bottom of the display. It provides launch buttons and a simple MM:SS clock derived from system ticks.

These components being CLVM applications is architecturally significant: the visible shell is not only privileged C drawing. The application runtime participates in building the desktop itself.

## Task representation

The kernel task layer defines `TASK_MAX = 32`. A `Task` stores:

- numeric ID and active flag;
- z value;
- task type;
- rectangle;
- `WindowState`;
- runner callback;
- 24-character title buffer;
- type-specific state in a union.

The current types include Shell, Ball, Editor, Explorer, Task Manager and generic `TASK_APP`.

A CLVM graphical program normally appears to the task system as `TASK_APP`, with its language-runtime slot stored in `task->state.app.lang_slot`.

## Task creation and slot reuse

`task_spawn` rejects invalid types, null runners and non-positive geometry. It then linearly scans for the first inactive slot.

The selected slot is completely cleared before reuse. The function sets normal window mode, remembers the restore rectangle, assigns the runner, obtains a new z value and initializes type-specific state.

The new task becomes focused.

This clearing rule is important. A reused slot must not inherit dragging state, an old language slot, stale title text or another task's union state.

## CLVM slot to task binding

When a language program starts, the language pipeline initializes a `LangSlot` and calls `app_window_open`.

`app_window_open` first checks whether the same language slot already owns a task. If it does, the existing task is retitled and raised rather than duplicated.

For a new window, it reads the slot's graphics dimensions, chooses placement and size, creates a `TASK_APP`, stores the language slot in the task and calls `lang_bind_task(slot, task_id)`.

If task creation fails, the language slot is killed rather than leaving an active application with no desktop owner.

This establishes a bidirectional relationship:

```text
Task.state.app.lang_slot  <-->  LangSlot.task_id
```

The relationship is explicit rather than inferred from window position or title.

## Z-order

Each raised or newly created task receives an increasing `z`.

`task_id_at(x,y)` scans all active, non-minimized tasks containing the point and selects the task with the largest z value.

`task_run_all` presents tasks from back to front. It repeatedly scans for the smallest z greater than the previously emitted value and invokes that task's runner.

With at most 32 tasks this simple algorithm is bounded, but its worst-case scan cost is quadratic in the task count: up to O(TASK_MAX²) comparisons per frame.

The design favors straightforward state over maintaining a separate sorted list.

## Focus

A left-button press causes `desktop_frame` to call `task_focus_at`.

For ordinary windows, focus raises the task, assigning a new z. A full-display wallpaper-style task is focused without being raised in the same way, preventing the desktop surface from unnecessarily jumping above ordinary windows.

Closing or minimizing the focused task resets the focused ID.

Focus is therefore both an input-routing property and a stacking property.

## Window modes

Window state can be Normal, Minimized or Maximized.

Minimize erases the old frame, records minimized mode, cancels dragging and drops focus if necessary. Minimized tasks are skipped by `task_run_all`.

Raise restores a minimized task to Normal and marks the frame dirty.

Maximize stores the prior rectangle in `window.restore` before replacing the frame with the supplied bounds. Restore reinstates that saved rectangle.

Move and resize erase the old region, update geometry and mark the new region for redraw.

The graphics damage model is therefore coupled to window lifecycle.

## Desktop frame loop

`desktop_frame(ticks)` performs one integration cycle:

1. poll USB tablet;
2. poll xHCI HID;
3. poll PS/2 mouse;
4. snapshot pointer state;
5. update focus on a left-button edge;
6. determine the focused application slot;
7. drain input events;
8. queue key/text events to that slot;
9. undraw the software cursor;
10. run visible tasks in z order;
11. redraw the cursor.

The ordering avoids drawing application content over a stale cursor image and centralizes keyboard/text routing before task execution.

## Keyboard and text event queues

The language runtime has separate key and text rings for each slot. `LANG_VM_SLOTS = 16` and the internal event capacity is `LANG_EVQ = 8`.

`lang_slot_push_key` and `lang_slot_push_text` compute the insertion index from read index plus count modulo the queue size. Taking an event advances the read index modulo the same capacity.

When a queue already contains eight events, a new event is discarded.

This is real backpressure behavior. A slow application can lose input; the current implementation does not block the desktop, grow the queue or overwrite the oldest entry.

## Routing restrictions

Keyboard/text events are routed only when the focused task is a `TASK_APP` and the window is not currently dragging or resizing.

If no eligible slot exists, `desktop_frame` still drains the global input event queue but does not forward those events to an application.

Pointer input follows a different model. CLVM applications query pointer position/button state through their system interface and the window library performs local hit testing and drag/resize logic.

Documentation must therefore avoid describing one universal event queue for all input types.

## Application surfaces

Each active language slot owns a graphics context. Applications draw into that context rather than writing directly into the system framebuffer.

The runtime can publish a front buffer. `lang_slot_publish` allocates or resizes a kernel front-pixel buffer and copies the slot graphics pixels into it. `lang_slot_pixels` prefers the published front buffer when its dimensions match, otherwise it returns the current graphics pixels.

The task runner then performs the system-facing blit.

This creates an explicit boundary between application drawing memory and desktop presentation.

## UI applications versus game surfaces

`app_run` distinguishes game-like surfaces from ordinary UI applications.

Game surfaces can be scaled into a client rectangle below kernel-managed chrome. This is used for programs whose internal resolution should not necessarily equal their on-screen window size.

Ordinary UI application surfaces are kept one-to-one with their task frame. The resulting surface is blitted at the task position and the kernel then restores common title/border presentation where applicable.

Fullscreen desktop-sized and taskbar-like surfaces receive special treatment so the kernel can preserve desktop/taskbar presentation conventions.

The model is simpler than a GPU scene compositor but already separates logical application resolution from physical placement.

## Closing applications

Window closure spans two ownership systems.

A task record belongs to the window manager. A CLVM slot belongs to the language runtime.

For application-window close paths, the code closes the task and requests closure of the corresponding language slot with `lang_slot_request_close`. That request marks the slot as dying so the runtime can complete its own teardown.

Conversely, if `app_run` discovers that its language slot is no longer used, it closes the remaining task.

A CLVM surface-close syscall also connects both paths.

This symmetry prevents a dead VM from leaving a permanent window and prevents a closed window from silently leaving a live program without presentation.

## Failure containment

Failure containment depends on the execution model.

A CLVM application fault belongs primarily to the VM/runtime slot. Native process faults follow the native process containment path described in the kernel chapters. The desktop task table is not itself the universal process table.

The task runner checks language-slot liveness before blitting. This is one example of the UI refusing to assume that a window implies a valid execution context.

A complete desktop failure model therefore requires reasoning across task lifetime, language-slot lifetime, process lifetime and graphics resources.

## Algorithmic cost summary

| Operation | Representation | Cost |
|---|---|---|
| spawn task | linear scan of 32 slots | O(TASK_MAX) |
| hit-test top task | scan all tasks | O(TASK_MAX) |
| count tasks | scan all tasks | O(TASK_MAX) |
| iterate nth active task | scan slots | O(TASK_MAX) |
| render tasks in z order | repeated selection scans | O(TASK_MAX²) worst case |
| push/take key or text | fixed ring | O(1) |
| close task | indexed task + full structure clear | O(sizeof(Task)) |
| launch icon lookup | fixed launcher list | O(1) at current size |

These choices are appropriate to current fixed limits but would need revision for hundreds or thousands of windows.

## Security and trust boundaries

The kernel owns focus and task-to-slot binding. CLVM programs do not directly mutate the kernel task array.

CLVM system calls mediate surface placement, resize, close and application launch operations. Driver-capability flags exist in the language runtime for privileged device-facing applications, while ordinary desktop applications use the normal application interface.

The current desktop is still experimental. The existence of CLVM isolation should not be described as equivalent to a hardened multi-user GUI security model.

Important open boundaries include event flooding, global pointer visibility, resource quotas and richer capability policy.

## Responsiveness

The desktop frame path is cooperative across several subsystems. Long-running CLVM execution, expensive filesystem work or excessive rendering can become visible as input/frame latency even if the kernel remains alive.

The runtime defines different instruction budgets for ordinary, UI and game workloads, but end-to-end responsiveness still depends on work performed per frame and on where blocking operations occur.

Performance evaluation should therefore include frame percentiles, input-to-paint latency and repeated application lifecycle stress rather than only raw drawing throughput.

## Applications as integration workloads

First-party programs exercise different parts of the stack:

- Shell: command dispatch, app launch and filesystem/runtime services;
- Explorer: directory enumeration, path construction and application handoff;
- ChrisEditor: filesystem, text input, compile/run/debug integration;
- Task Manager: task/runtime introspection and termination paths;
- Ball: basic animation and frame timing;
- Doom and Mine Chris: larger rendering/input workloads.

No one application proves the correctness of every layer. Together they create realistic cross-subsystem pressure.

## Executable evidence

`tools/test_task_window.c` is a focused host regression test for the kernel task/window layer.

It verifies:

- successful task spawn and initial Normal mode;
- minimized tasks are not run;
- raising a minimized task restores execution;
- maximize and restore preserve geometry;
- move/resize update geometry and record graphics damage;
- hit testing selects the higher-z overlapping task;
- 1,000 spawn/close cycles reuse slots without increasing the live-task count.

The test is meaningful evidence for task lifecycle and z/window mechanics. It does not execute the full CLVM desktop, HID path, application event queues or final display presentation.

Those integration paths still require QEMU/hardware-level tests.

## Current limitations

The task table is fixed at 32 entries and the CLVM runtime at 16 slots. Event queues hold eight key events and eight text events per slot. Overflow drops new events.

Task rendering uses repeated linear scans. Z values monotonically increase without a separate compact ordering structure. The desktop/taskbar launcher layout is largely fixed. The architecture does not implement a modern per-surface GPU compositor, multi-seat input model or hardened multi-user desktop security policy.

These are implementation boundaries of the current ChrisOS desktop, not limitations of graphical operating systems in general.

## Revision reconciliation

This page was reconciled to ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. The implementation files described by the chapter are unchanged relative to the previous reviewed process/window baseline; the revision update records source reconciliation rather than an inferred feature change.

## Source map

Kernel desktop integration is in `kernel/wm/desktop.c`. Task/window state is defined in `kernel/wm/task.c` and `task.h`. Common kernel UI drawing is in `kernel/wm/ui.c`. CLVM application windows are connected by `kernel/tools/app_window.c`, `compiler/lang_pipeline.c` and `kernel/lang/clvm_sys.c`.

The visible CLVM desktop and taskbar live in `APPS/DESKTOP/DESKTOP.CC` and `APPS/TASKBAR/TASKBAR.CC`. Application-side window/UI/launch helpers live under `LIB/`. The Source Atlas preserves the referenced source files for the reviewed revision.
