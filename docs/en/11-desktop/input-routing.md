---
id: input-routing
lang: en
type: technical-chapter
volume: 11-desktop
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/input.h
  - kernel/gfx/input.c
  - kernel/metal/ps2.h
  - kernel/metal/ps2.c
  - kernel/fs/xhci.c
  - kernel/wm/task.h
  - kernel/wm/task.c
  - kernel/wm/desktop.c
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
  - input_mouse_delta_for
  - input_mouse_axis
  - ps2_init
  - ps2_mouse_poll
depends_on:
  - window-manager
  - desktop-applications
  - interrupts-smp
---

# Input routing: from device interrupts to the focused application

Input is a boundary between asynchronous hardware and synchronous application logic. A keyboard may interrupt the processor at any instruction, a PS/2 mouse arrives as a three-byte packet, and a USB tablet can report absolute coordinates. Applications, however, want stable concepts such as **text**, **special keys**, **pointer position**, **button transitions**, and, for games, relative motion owned by one task.

ChrisOS implements this boundary in layers. Device drivers normalize hardware reports into the shared input subsystem; the input subsystem maintains keyboard and pointer state plus a bounded event queue; desktop and task code consume those abstractions according to focus and capture rules. This chapter describes the implementation at revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. It does not describe a future event server or a POSIX input model.

## 1. The routing problem

A useful input path has to preserve several different kinds of information:

1. **state** — whether a key or mouse button is currently down;
2. **transitions** — a press that occurred since the last consumer observation;
3. **text** — characters after layout and modifier interpretation;
4. **commands** — arrows, Enter, Escape and function keys that are not ordinary text;
5. **motion** — absolute desktop coordinates and relative deltas;
6. **ownership** — which task is allowed to consume captured relative motion.

These are deliberately not represented by one variable. Polling only current state loses short transitions. Keeping only events makes continuous movement awkward. Treating text as raw scan codes pushes keyboard-layout policy into every application. ChrisOS therefore keeps complementary representations.

The high-level flow is:

```text
PS/2 IRQ 1 -------------------> input_keyboard_irq(scancode)
USB HID keyboard ------------> input_keyboard_irq(normalized set-1 code)
                                  |-- key-state table
                                  |-- modifier/layout state
                                  `-- bounded InputEvent queue

PS/2 IRQ 12 / poll -----------> input_mouse_irq_byte(byte)
                                  `-- 3-byte packet decoder --+
USB absolute pointer ---------> input_pointer_absolute(...) ---+--> mouse state
                                                               |    + relative deltas
                                                               `--> press sequence

application / desktop --------> input_next_event()
                             --> input_mouse_snapshot()
                             --> input_key_down()
                             --> capture/delta API
```

The important architectural decision is that PS/2 and USB do not expose unrelated application APIs. They converge on `kernel/gfx/input.c`.

## 2. Public data model

`kernel/gfx/input.h` defines two event classes. `INPUT_EVENT_TEXT` carries a character, while `INPUT_EVENT_KEY` carries an `InputKey` value for non-text actions. The special-key enumeration currently includes Backspace, Tab, Enter, Escape, cursor movement, Home, End, Delete and selected function keys.

Pointer state is represented by `InputMouse`:

```c
typedef struct {
    int x;
    int y;
    bool left_down;
    bool right_down;
    bool middle_down;
    uint32_t left_press_sequence;
} InputMouse;
```

The press sequence is significant. A boolean answers “is the button down now?” but cannot prove that a complete press happened between two frames. Incrementing `left_press_sequence` on the rising edge gives the desktop a monotonic transition marker.

The keyboard also has a 256-entry state table. Ordinary Set-1 make code `N` uses index `N`; an `E0`-prefixed make code uses `128 + N`. This keeps, for example, an extended arrow distinct from a keypad key with the same low scan code.

## 3. Initialization and persistent layout

`input_init(width, height)` resets queue indices, key state, lost-event accounting, pointer state and modifier state. The pointer starts at the center of a screen whose dimensions are clamped to at least one pixel. The routine also attempts to load `SYS/KB.CFG`.

Two layouts are currently modeled: US and ABNT2. `input_load_layout_file()` recognizes a small textual configuration, while `input_save_layout_file()` persists either `us` or `abnt2`. This is intentionally a small kernel-era mechanism rather than a general Unicode input-method framework.

The current mapping tables are byte-oriented. That means the routing layer is useful for the present ChrisOS applications, but it is not yet a complete international text system. Dead keys, composed Unicode text, IMEs and arbitrary layout packages remain outside the implemented contract.

## 4. Keyboard path

### 4.1 PS/2 entry

`ps2_init()` configures the i8042-compatible controller, tests the first port, optionally enables the auxiliary mouse port, enables device scanning and registers IRQ handlers. Keyboard IRQ 1 reads port `0x60` only when output data is present, then calls `input_keyboard_irq(value)`.

The interrupt handler is intentionally thin: hardware acknowledgement and byte acquisition remain in the device layer; semantic decoding belongs to the shared input layer.

### 4.2 USB convergence

The xHCI/HID path also emits normalized keyboard transitions through `input_keyboard_irq()`. For an extended key it first emits `0xE0`, then the make or break code. Consequently desktop applications do not need to know whether the key originated on PS/2 or USB.

### 4.3 Make, break and extended codes

`input_keyboard_irq()` first handles the `0xE0` prefix. `input_keystate_note()` records the following make/break transition in the 256-entry table. The high bit distinguishes release from press for Set-1 codes.

Modifier handling is stateful:

- left Shift and right Shift track press/release;
- Caps Lock toggles on a press;
- extended Alt is used as AltGr;
- Escape releases mouse capture before normal key dispatch continues.

Extended keys are translated by `extended_key()`. Ordinary control keys are translated by `plain_key()`. A recognized special key becomes `INPUT_EVENT_KEY`; printable input becomes `INPUT_EVENT_TEXT` after layout, Shift, Caps Lock and the currently implemented ABNT2 AltGr rules are applied.

This separation matters for editors and shells. Cursor-left should not be represented as a printable byte, while typing `a` should not require every application to decode scan code `0x1E`.

## 5. The bounded keyboard event queue

The event queue contains 64 slots and uses head/tail indices. A producer computes the next head position; if it would collide with the tail, the event is dropped and `g_lost_events` is incremented. Otherwise the event is copied and the head advances.

For capacity `C = 64`, the ring intentionally leaves one slot unused to distinguish full from empty, so the maximum number of queued events is:

\[
N_{max} = C - 1 = 63.
\]

Push and pop are constant-time operations, **O(1)**, and storage is **O(C)** with a fixed bound. There is no allocation in the interrupt path.

`input_next_event()` is the consumer interface. `input_clear_events()` discards all pending events by advancing the tail to the current head. `input_lost_events()` exposes overflow evidence instead of silently pretending that delivery is lossless.

The implementation uses volatile indices plus compiler barriers. This is a small freestanding design, not a general multi-producer lock-free queue with a formal C11 atomic memory-order proof. Any future move to multiple concurrent producers on different CPUs should revisit this contract and use explicit atomic operations or locking.

## 6. Pointer path

### 6.1 PS/2 packets

A standard PS/2 mouse report is assembled from three bytes. The first byte must contain the synchronization bit (`0x08`); otherwise the decoder waits for a valid packet start. Overflow flags cause the completed packet to be rejected.

The second and third bytes are signed X and Y deltas. PS/2 defines positive Y upward, while screen coordinates increase downward, so ChrisOS applies:

\[
\Delta x_{screen} = \Delta x_{ps2}, \qquad
\Delta y_{screen} = -\Delta y_{ps2}.
\]

The pointer is clamped to the framebuffer bounds. Button bits update left, right and middle state, and a left-button rising edge increments the press sequence.

`ps2_mouse_poll()` provides an additional drain path for auxiliary bytes. The source documents why: IRQ 12 can be masked or interact with GPU activity, so the desktop can poll pending AUX bytes to keep pointer tracking responsive. Interrupts are temporarily disabled while the polling loop drains up to 16 bytes, preventing the IRQ handler from consuming the same byte concurrently.

### 6.2 Absolute USB pointer

`input_pointer_absolute(x, y, xmax, ymax, buttons)` maps a device coordinate range into screen coordinates. Ignoring integer rounding, the mapping is:

\[
x_s = x \frac{W-1}{x_{max}}, \qquad
y_s = y \frac{H-1}{y_{max}}.
\]

Inputs are clamped to the advertised device range before scaling. When a task owns pointer capture, movement between successive absolute positions is also accumulated as relative delta. This allows an absolute tablet path to participate in APIs used by interactive applications without pretending that the hardware itself reports relative motion.

## 7. Stable snapshots across interrupt updates

Pointer state can change asynchronously. Copying `x`, then being interrupted, then copying `y` could otherwise produce a mixed snapshot from two different reports.

ChrisOS uses a small versioned-read protocol. Writers increment `g_mouse.version` before and after modifying the pointer structure, with compiler barriers around the fields. A reader in `input_mouse_snapshot()` retries if the first version is odd or if the version changed during the copy.

Conceptually:

```text
writer: version++  -> write fields -> version++
reader: read v1 -> copy fields -> read v2 -> accept iff v1 == v2 and even
```

This resembles a sequence counter. It avoids taking a blocking lock for a tiny snapshot. The current implementation should still be understood in the context of ChrisOS's present execution model; compiler barriers alone are not a universal replacement for architecture-aware atomics on arbitrary SMP designs.

## 8. Focus, routing and capture

Window focus and pointer capture solve different problems.

**Focus** determines which desktop task is the active target for ordinary application interaction. The window manager maintains task stacking and focus. The desktop can hit-test windows and raise or focus a task when the user interacts with it.

**Capture** is explicit ownership of relative mouse movement. `input_capture_set(task_id)` records one owner and clears accumulated deltas. `input_mouse_delta_for(task_id, ...)` returns motion only if the caller owns capture. `input_capture_release_task(task_id)` releases ownership when that task goes away. Escape also releases capture in the keyboard path.

This is particularly important for a 3D program. A desktop pointer is naturally absolute and bounded by screen edges. A first-person camera instead needs an unbounded stream of relative motion. Capture creates that semantic boundary without making all desktop applications consume mouse deltas.

`input_mouse_axis()` additionally provides a paired-sample mechanism for runtimes that request X and Y separately. The first axis request snapshots accumulated motion; the paired request sees the same sample, preventing X from one frame and Y from another from being combined accidentally.

## 9. Concurrency, ownership and failure modes

The subsystem avoids dynamic allocation in hardware-facing paths. Its principal bounded resources are the 64-slot event ring and fixed keyboard/pointer state.

Relevant failure modes are explicit:

| Failure | Current behavior | Observable consequence |
|---|---|---|
| keyboard event ring full | drop newest event | `input_lost_events()` increases |
| invalid PS/2 packet start | ignore until sync byte | packet stream resynchronizes |
| PS/2 X/Y overflow | reject packet | one motion sample is lost |
| pointer outside range | clamp | pointer remains on-screen |
| capture caller is not owner | return zero/no sample | task cannot steal relative motion |
| keyboard config missing/invalid | retain default layout | US remains usable |
| PS/2 mouse IRQ unreliable | poll AUX bytes | desktop can continue receiving movement |

The design favors bounded damage over blocking in an interrupt context. A full queue does not allocate memory or wait for a consumer. A malformed mouse stream does not move the pointer with arbitrary bytes.

## 10. Security and privilege boundary

Today this input system is kernel-resident and the task model is still evolving. Capture is an ownership check by task identifier, not a mature security boundary comparable to a protected desktop session in a production multi-user OS.

Future user-mode isolation must answer additional questions: who may observe global keystate, whether background tasks may read text events, how synthetic input is authorized, what happens when the focused process crashes, and whether capture is revoked on every focus transition. Those are roadmap requirements, not properties that should be attributed to the current implementation.

## 11. Validation evidence

The source tree contains host-side tests for input behavior. `tools/test_input.c` initializes the subsystem, injects keyboard scan codes and verifies event production. `tools/test_keystate.c` checks state identity, including the distinction between extended arrow codes and keypad codes, and exercises modifier/key-state transitions.

A useful validation matrix for this layer is:

1. inject make/break pairs and verify `input_key_down()`;
2. verify US and ABNT2 printable mappings with Shift/Caps/AltGr combinations;
3. fill the event ring and verify deterministic overflow accounting;
4. feed valid, desynchronized and overflowed PS/2 packets;
5. verify coordinate clamping at every screen edge;
6. update pointer state while repeatedly taking snapshots;
7. transfer/release capture and verify non-owners receive no deltas;
8. run the same application path with PS/2 and USB-originated input.

Hardware validation should additionally cover keyboards, mice and USB tablets on real machines because emulators often provide cleaner timing and simpler controller behavior than physical firmware and controllers.

## 12. Current limitations

At the reviewed revision, the implementation is intentionally compact. Important limitations include:

- text events carry a single `char`, not a Unicode scalar or composed text sequence;
- only US and a limited ABNT2 mapping are built in;
- the queue is bounded and can drop events under sustained producer pressure;
- the queue synchronization model is not a general SMP multi-producer design;
- PS/2 support focuses on the standard three-byte mouse packet;
- capture is task-ID ownership, not a complete capability/security system;
- `keyboard_pop()` and `mouse_pop()` in the PS/2 compatibility interface are stubs; consumers should use the shared input API described here;
- higher-level routing remains coupled to the current kernel desktop/task architecture.

These limitations are part of the architecture. Documentation should not replace them with a more advanced design that has not yet been implemented.

## 13. Roadmap boundaries

Reasonable future work includes Unicode text composition, richer HID report parsing, configurable layouts, explicit atomic/SMP semantics, per-task event channels, stronger focus/capture revocation, scroll/wheel events and a clearer user/kernel input ABI. Those changes should preserve the useful separation already present: hardware decoding below, normalized input state/events in the middle, and desktop/application policy above.

## 14. What to retain

The core lesson is that input routing is not merely “read a key and send it to a window.” ChrisOS currently combines several mechanisms because each preserves different information:

- a **key-state table** for continuous state;
- a **bounded event ring** for discrete text and commands;
- a **versioned pointer snapshot** for coherent asynchronous reads;
- a **press sequence** for edge detection;
- **relative accumulators and capture ownership** for interactive applications;
- device-specific PS/2/USB code that converges on the same shared API.

That structure is the bridge between interrupt-driven hardware and the window/application model described in the surrounding desktop chapters.