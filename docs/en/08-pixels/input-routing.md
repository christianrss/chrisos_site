---
id: input-routing
lang: en
type: technical-chapter
volume: 08-pixels
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/input.h
  - kernel/gfx/input.c
  - kernel/wm/task.h
  - kernel/wm/task.c
  - kernel/wm/desktop.c
  - kernel/wm/ui.c
  - kernel/tools/editor_window.c
  - kernel/tools/explorer.c
  - kernel/tools/taskmgr.c
  - compiler/lang_pipeline.c
  - compiler/lang_pipeline.h
  - kernel/lang/clvm_sys.c
  - compiler/chrisc/chrisc.c
  - tools/test_input.c
  - tools/test_keystate.c
symbols:
  - input_init
  - input_keyboard_irq
  - input_mouse_irq_byte
  - input_pointer_absolute
  - input_next_event
  - input_mouse_snapshot
  - input_key_down
  - input_capture_set
  - input_capture_release_task
  - input_mouse_axis
  - task_focus_at
  - task_focused_id
  - task_is_focused
  - lang_slot_push_key
  - lang_slot_push_text
  - lang_slot_take_key
  - lang_slot_take_text
depends_on:
  - pixels-framebuffer
  - desktop-compositor
  - window-manager
related:
  - desktop-applications
  - chriseditor
  - chrisshell
  - mine-chris
  - clvm-syscalls
---

# Input routing, focus and capture

## Scope

ChrisOS input is not a single queue delivered directly from hardware to applications.

The implemented path has several layers:

    keyboard / mouse hardware
        -> IRQ or USB report decoding
        -> global input state + global event queue
        -> window/task focus selection
        -> desktop routing
        -> native task consumers or per-CLVM queues
        -> application APIs

Keyboard input has two parallel representations:

- **key state**, used for polling whether a scan-code identity is currently down;
- **event stream**, used for discrete key/text events.

Pointer input has three representations:

- absolute screen position/buttons;
- accumulated relative deltas;
- left-press sequence state for edge detection.

CLVM applications add another queueing layer for `ev_key()` and `ev_text()`.

This chapter describes those contracts and the current routing limitations.

![ChrisOS input-routing layers](../../assets/diagrams/input-routing-en.svg)

## Input event types

The core event queue carries only:

    INPUT_EVENT_TEXT
    INPUT_EVENT_KEY

`InputEvent` contains:

    type
    key
    character

Special/navigation keys are represented by `InputKey`, including:

- Backspace;
- Tab;
- Enter;
- Escape;
- arrows;
- Home/End/Delete;
- selected function keys.

Printable characters use TEXT events instead of KEY events.

This separation lets an editor distinguish semantic navigation keys from layout-dependent character input.

## Global event queue

The core queue has:

    INPUT_QUEUE_CAPACITY = 64

It is a ring with global head/tail indexes.

IRQ-side producers append events through `queue_push`.

If the next head would equal tail, the new event is dropped and:

    g_lost_events++

is incremented.

The queue does not overwrite the oldest event.

`input_lost_events()` exposes the cumulative loss count.

There is currently no per-task event queue at this lowest layer.

## IRQ-to-main-loop synchronization

The event queue and mouse state are shared between interrupt/device paths and the desktop/main execution path.

The implementation uses volatile fields and compiler barriers rather than a general lock.

For the event ring, producer writes the event payload before publishing the new head.

Consumer observes head/tail, copies the event, then advances tail.

This is a bounded single-global-queue design.

It should not be generalized as a fully lock-free MPMC queue: the implementation assumes the current interrupt/main-loop producer-consumer pattern.

## Keyboard scan-code identity

ChrisOS preserves raw Set-1 identity for polling.

Ordinary make code N maps to index N.

E0-prefixed extended make code N maps to:

    128 + N

This avoids collisions between keypad keys and navigation keys.

For example:

    Up    = 200
    Left  = 203
    Right = 205
    Down  = 208

`g_keys[256]` stores current down/up state.

`input_key_down(scancode)` reads this table.

## Keyboard event generation

`input_keyboard_irq` first updates key state, then handles modifier state and event generation.

Tracked modifiers include:

- left Shift;
- right Shift;
- Caps Lock;
- AltGr.

Release events update state but generally do not enqueue application events.

Special key make events become KEY events.

Printable make events become TEXT events after layout/modifier translation.

Thus:

    physical identity -> key state
    semantic special key -> KEY event
    printable result -> TEXT event

are separate outputs from one keyboard interrupt path.

## Keyboard layouts

The current layouts are:

    INPUT_LAYOUT_US
    INPUT_LAYOUT_ABNT2

The active layout defaults to US unless `SYS/KB.CFG` selects another valid value.

The configuration parser recognizes textual US/ABNT2 forms.

`input_save_layout_file` writes the current choice back to the filesystem.

ABNT2 has its own normal/shifted translation tables and special AltGr handling in the current implementation.

The mapping is still an explicit compact table, not a full Unicode input-method framework.

TEXT events currently contain a single `char`.

## Caps/Shift rule

For alphabetic characters, uppercase selection is based on:

    shifted != caps_lock

For non-alphabetic keys, the shifted table is used when Shift is active and a shifted mapping exists.

This implements the expected XOR-like Caps/Shift rule for Latin letters.

## Escape and pointer capture

A keyboard make event for Escape has a global side effect:

    g_capture_task = -1

before normal KEY-event generation.

Therefore Escape acts as an emergency release of relative pointer capture regardless of which CLVM application originally captured it.

This is useful for game-like input modes.

It also means Escape has both:

- routing semantics as INPUT_KEY_ESCAPE;
- global pointer-capture semantics.

## Mouse snapshot model

`InputMouse` contains:

    x
    y
    left_down
    right_down
    middle_down
    left_press_sequence

The interrupt-facing mouse state includes a monotonically changed `version`.

Writers increment version before and after updating mouse fields.

`input_mouse_snapshot()` loops until it sees:

- an even version;
- the same version before and after copying.

This is a seqlock-like read pattern.

It avoids returning a snapshot composed from two different device updates without taking a heavyweight lock.

## PS/2 relative mouse input

The PS/2 decoder assembles three-byte packets.

Packets without the required synchronization bit are ignored when starting a packet.

Overflow-bit packets are discarded.

PS/2 Y deltas are positive upward, whereas ChrisOS screen-space Y increases downward.

Therefore:

    screen_dx = packet_dx
    screen_dy = -packet_dy

The absolute cursor position is clamped to screen bounds.

Button bits update left/right/middle state.

A transition from left-up to left-down increments `left_press_sequence`.

## Absolute pointer input

`input_pointer_absolute` accepts coordinates in device range:

    0..xmax
    0..ymax

and scales them into screen coordinates.

This path is appropriate for USB tablet-style absolute pointing devices.

When pointer capture is active, successive absolute positions also contribute to accumulated relative deltas.

That permits a captured application to use movement deltas even when the underlying pointing device reports absolute positions.

## Press-edge detection

Global UI code can ask:

    input_left_pressed()

This compares the latest `left_press_sequence` against the globally consumed sequence.

`input_consume_left_press()` advances the consumed sequence.

This is different from checking `left_down`.

It detects a press edge that occurred since the last consume.

Because the consumed press sequence is global, this mechanism is not independently namespaced per task.

## Focus model

Window focus is tracked by:

    g_focused_id

`task_id_at(x,y)` selects the active, non-minimized task under a point with the highest z value.

`task_focus_at(x,y)` focuses that task.

For a normal window it calls `task_raise`, which also establishes the top/focus state.

A wallpaper-sized task is treated specially and can become focused without ordinary raise behavior.

Clicking empty space sets focus to -1.

## Desktop click-to-focus

During desktop update:

1. mouse state is sampled;
2. if a new left press exists, `task_focus_at(mouse.x, mouse.y)` runs;
3. the focused task is retrieved;
4. event routing then uses that focus decision.

Therefore the click that changes focus affects keyboard/text routing in the same desktop update iteration.

## Global keyboard event ownership problem

The low-level keyboard event queue is global.

A consumer removes events permanently with:

    input_next_event()

There is no peek-with-owner, per-task cursor or fan-out mechanism.

This means routing must have exactly one authoritative consumer that dispatches each event to its destination.

The current source does not consistently follow that architecture.

## CLVM routing path

`desktop.c` acts as a central router for CLVM application tasks.

If the focused task:

- exists;
- is `TASK_APP`;
- is not currently dragging;
- is not resizing;

then its language slot is selected.

The desktop drains the global input queue.

For every event:

    KEY  -> lang_slot_push_key(slot, key)
    TEXT -> lang_slot_push_text(slot, character)

Each `LangSlot` has separate key and text rings.

## Per-CLVM queues

A language slot contains:

    ev_key_q[LANG_EVQ]
    ev_text_q[LANG_EVQ]

plus independent count/read indexes.

`lang_slot_push_key/text` append when capacity remains.

When full, the new routed event is silently dropped.

Unlike the core queue, these per-slot queues do not maintain a lost-event counter.

`lang_slot_take_key/text` remove one entry and return zero when empty.

## CLVM event API

The ChrisC builtins are:

    ev_key()   -> syscall 83
    ev_text()  -> syscall 84

The dispatcher maps them directly to:

    lang_slot_take_key
    lang_slot_take_text

Applications commonly drain them in loops:

    k = ev_key();
    while (k) {
        ...
        k = ev_key();
    }

TEXT works similarly.

This API is poll-based from the application's perspective even though the events originated asynchronously.

## Focus restriction for CLVM events

Only the focused `TASK_APP` receives newly routed key/text events.

If focus moves away, old events already queued in the LangSlot remain there until consumed.

There is no queue flush automatically performed on focus loss in the inspected path.

This can be useful because it avoids losing already-delivered input, but it can also make an application process stale keystrokes after regaining execution.

## Drag/resize routing suppression

When the focused application window is dragging or resizing, desktop routing does not select its LangSlot.

However, the current desktop code still drains the global event queue.

Thus keyboard/text events arriving during drag/resize are discarded rather than deferred for the application.

This is current behavior, not merely a theoretical possibility.

## Native-task routing conflict

Several native task implementations consume `input_next_event()` themselves.

Examples include:

- native editor window;
- explorer;
- task manager.

They do so only when focused.

However, `desktop.c` drains the global queue **before** `task_run_all()`.

When the focused task is not `TASK_APP`:

    slot = -1

but the desktop still executes:

    while (input_next_event(&event)) {
        if (slot < 0)
            continue;
    }

Every event is therefore removed and discarded.

Later, when the focused native task's `run` callback executes and asks `input_next_event()`, the queue is empty.

This is a concrete routing bug in the current architecture.

A central router must either dispatch to native tasks too, or it must not drain the queue when it does not own the destination.

## Event queue loss layers

There are currently two independent loss points.

### Core queue overflow

The 64-entry input ring drops new events and increments `g_lost_events`.

### CLVM slot queue overflow

A full `LANG_EVQ` drops new events silently.

Additionally, the desktop/native routing bug can discard events even when neither queue is full.

Therefore “no low-level queue overflow” does not imply “application received all input.”

## Key-state polling

CLVM exposes `key(scancode)` through syscall ID 10.

The dispatcher checks application focus before exposing `input_key_down`.

An unfocused CLVM task receives false/zero state.

This is different from `ev_key`:

- `key()` answers current physical state;
- `ev_key()` returns a queued semantic key event.

Games often prefer state polling for movement and event queues for one-shot actions.

## Mouse position/button APIs

CLVM builtins include:

    mouse_x()
    mouse_y()
    mouse_btn()

The dispatcher snapshots global mouse state.

It applies task/window checks so a CLVM application does not blindly receive active button state for a different topmost task.

For game-sized/content-sized windows, it also checks whether the pointer is inside the task's body area rather than title/chrome.

The returned coordinates themselves remain based on the global screen pointer unless the application/library performs window-coordinate conversion.

## Pointer capture

The relative-input API is:

    mouse_cap()
    mouse_rel()
    mouse_dx()
    mouse_dy()

Capture is owned by a task ID:

    g_capture_task

Only the capture owner can consume accumulated relative deltas.

The dispatcher permits `mouse_cap()` only when the application's task is focused.

An unfocused caller receives -1.

## Shared delta snapshot

`mouse_dx()` and `mouse_dy()` need to describe one movement sample even though they are separate calls.

`input_mouse_axis` therefore snapshots:

    g_acc_dx
    g_acc_dy

on the first axis request, clears the accumulated source, and remembers which axes have been read.

After both axes have been consumed, the snapshot becomes invalid and the next call captures a fresh pair.

Without this mechanism, a device interrupt between separate X/Y reads could produce mismatched deltas.

## Capture and focus lifecycle gap

The header comment states that unfocused owners lose capture.

The core `input_capture_set` / focus functions do not directly enforce that invariant.

A focus change does not automatically clear `g_capture_task`.

Instead, CLVM `mouse_dx/mouse_dy` dispatcher paths check focus; when they discover that the owning task is no longer focused, they call:

    input_capture_release_task(t->id)

Capture is also released:

- by Escape;
- by `mouse_rel()`;
- during CLVM slot teardown.

Therefore capture can remain nominally owned by an unfocused task until one of those paths executes.

This is a lifecycle gap relative to the header-level contract.

The focus-changing operation itself should release capture from the previous owner.

## Capture accumulation side effect

While a stale capture owner remains installed, PS/2 relative movement continues accumulating in:

    g_acc_dx
    g_acc_dy

because raw relative packet handling accumulates deltas independently of focus.

A later release clears ownership but does not universally clear accumulated deltas.

`input_capture_set` clears the accumulator when ownership changes, which mitigates stale movement when a new owner captures.

Making focus-loss release immediate would make this lifecycle easier to reason about.

## Absolute devices and capture

For absolute pointer reports, deltas are accumulated only while capture exists.

The current absolute position is always updated.

This avoids manufacturing relative movement history for ordinary desktop pointer motion when nobody requested capture.

## Mouse capture is task-scoped, not slot-scoped

The input subsystem stores a task ID, not a language-slot ID.

CLVM maps its graphics/language context to the owning task before capture operations.

This is the correct ownership level for focus semantics because focus is also a task property.

Teardown translates the language slot back to the task and releases capture.

## Native UI focus checks

The UI helper layer checks `task_is_focused(owner)` for interactions such as row clicks and buttons.

This prevents background windows from acting on a global mouse click merely because the pointer overlaps their rectangle.

The window-manager/task layer therefore remains responsible for z ordering and focus, while widget helpers enforce that policy locally.

## Concurrency and memory ordering

Input data is modified by interrupt/device paths and read by normal kernel execution.

The mouse snapshot's version protocol provides a coherent multi-field read.

The event ring uses compiler barriers and volatile indexes.

Key state is a volatile byte table.

There are no explicit CPU memory-order primitives or locks around these paths.

On current x86-oriented execution, the design relies heavily on platform ordering and simple producer/consumer behavior.

If the input subsystem is reused on weaker memory-order architectures or receives multiple concurrent producers, these contracts need stronger atomics or locks.

## Complexity

Most operations are O(1):

- key-state update/lookup;
- queue push/pop;
- mouse snapshot in the uncontended case;
- CLVM queue push/pop;
- capture checks.

`task_id_at` scans at most TASK_MAX tasks:

    TASK_MAX = 32

so click focus selection is O(TASK_MAX), bounded by a small constant.

The mouse seqlock snapshot can retry if an update overlaps the read, but device update frequency keeps expected cost low.

## Security and isolation

Input routing is a security boundary because keyboard events can contain sensitive user data.

Positive controls include:

- CLVM key-state polling is focus-gated;
- CLVM event routing targets only the focused application slot;
- capture acquisition requires task focus;
- relative deltas are available only to the capture owner;
- mouse button state is filtered against topmost/window ownership;
- slot teardown releases pointer capture.

Current weaknesses include:

- global event consumers are not ownership-safe;
- event loss can be silent at the LangSlot layer;
- stale queues can survive focus transitions;
- focus change does not immediately revoke capture;
- global keyboard queue architecture does not yet express per-task provenance.

The native-task drain conflict is both a usability bug and an isolation/design problem because routing ownership is ambiguous.

## Validation evidence

`tools/test_keystate.c` verifies:

- ordinary keypad identity;
- E0-extended arrow identity without collision;
- make/break key state;
- Shift lifetime;
- Ctrl/Alt/AltGr distinction;
- keyboard layout selection;
- PS/2 relative delta sign;
- capture ownership;
- rejection of delta reads by another task;
- Escape capture release;
- absolute-device relative delta behavior under capture.

`tools/test_input.c` exercises keyboard event generation and queue consumption.

Application sources such as Editor, Shell, Explorer, Task Manager, Paint and Mine Chris provide integration evidence for the APIs they consume.

The existing test set does not directly cover the desktop/native-task drain bug described above.

## Missing focused tests

High-value routing tests include:

- focus a native editor task, enqueue keyboard event, run desktop update, prove the editor receives it;
- focus a CLVM task, prove exactly that LangSlot receives it and native tasks do not;
- switch focus with queued events and define whether old-slot queues persist or flush;
- drag/resize an app while typing and define deferred versus discarded behavior;
- overflow the core queue and validate lost-event accounting;
- overflow a LangSlot queue and expose/report loss;
- capture pointer, switch focus without making further CLVM input calls, verify capture is immediately revoked;
- task destruction while capture is active;
- simultaneous absolute-pointer update and snapshot consistency.

## Current limitations

At the documented revision:

- the lowest event queue is global rather than per-task;
- desktop routing drains the queue even when no CLVM slot owns the event;
- native focused consumers can consequently lose every queued event before their run callback;
- drag/resize of a focused CLVM window causes key/text events to be drained and discarded;
- per-CLVM queue overflow is silent;
- already-routed CLVM events remain queued across focus loss;
- pointer capture is not synchronously revoked by focus change;
- text events are single-byte chars rather than Unicode code points;
- keyboard mapping is a compact US/ABNT2 implementation rather than a general layout/IME system;
- low-level synchronization is based on volatile/compiler barriers and current producer-consumer assumptions;
- the global left-press consumption sequence is not namespaced per task.

## Roadmap boundary

A stronger routing architecture should have one authoritative dispatcher.

A useful model is:

    hardware event
      -> global ingress queue
      -> focus/capture router
      -> per-task queue
      -> native or CLVM adapter

Then:

- every task gets its own event queue;
- native and CLVM apps consume the same routed abstraction;
- queue loss can be counted per destination;
- focus change can explicitly flush, preserve or synthesize events by policy;
- capture revocation happens in the same focus-transition transaction;
- drag/resize can divert only mouse/chrome events while preserving keyboard input;
- Unicode text input can be represented independently of physical keys;
- future USB/HID devices feed one normalized event model.

The current API already contains most low-level primitives needed for that refactor, but the central ownership rule is not yet implemented consistently.

## Source map and revision

`kernel/gfx/input.c` and `input.h` implement device normalization, global event queueing, key state, layouts, mouse snapshots, deltas and capture.

`kernel/wm/task.c` and `task.h` implement hit testing, z selection and focus state.

`kernel/wm/desktop.c` performs the current global event drain and CLVM routing.

`compiler/lang_pipeline.c` owns the per-CLVM key/text queues.

`kernel/lang/clvm_sys.c` exposes focus-gated key/mouse state, event dequeue and capture syscalls.

Native task implementations such as `editor_window.c`, `explorer.c` and `taskmgr.c` directly consume the global event queue and reveal the current routing conflict.

`tools/test_input.c` and `tools/test_keystate.c` provide focused host-side validation.

All current-behavior claims in this chapter were reconciled against ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.
