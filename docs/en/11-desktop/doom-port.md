---
id: doom-port
lang: en
title: "Doom port: bringing a real C game engine into ChrisOS"
type: technical-chapter
volume: 11-desktop
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - GAMES/DOOM/DOOM.CC
  - GAMES/DOOM/ENGINE.LST
  - GAMES/DOOM/MAIN.CC
  - GAMES/DOOM/I_CHRIS.CC
  - GAMES/DOOM/I_VIDEO.CC
  - GAMES/DOOM/I_INPUT.CC
  - GAMES/DOOM/I_SOUND.CC
  - GAMES/DOOM/W_FILE.CC
  - tools/doom_qemu_long_smoke.py
  - tools/doom_qemu_smoke.py
  - tools/test_doom_jit_smoke.c
  - tools/test_doom_path_pcs.c
  - tools/test_doom_compile.c
  - tools/test_doom_engine.c
symbols:
  - doomgeneric_Create
  - DG_Init
  - DG_DrawFrame
  - DG_SleepMs
  - DG_GetTicksMs
  - DG_GetKey
  - I_InitGraphics
  - I_FinishUpdate
  - I_StartTic
  - poll_key
  - W_OpenFile
  - W_Read
  - W_CloseFile
depends_on:
  - chrisc-clvm
  - input-routing
  - gfx2d
  - chrisfs
---

# Doom port: bringing a real C game engine into ChrisOS

The Doom work in ChrisOS is more than a game demo. It is an integration test for the compiler/runtime boundary, framebuffer, input, filesystem, memory allocation, timing, and compatibility layer required to host a substantial pre-existing C codebase.

Two different targets exist in the reviewed tree and they must not be confused.

`GAMES/DOOM/DOOM.CC` is a small ChrisC bring-up/demo. It loads a Doom WAD far enough to find `PLAYPAL`, maintains a 320×200 8-bit framebuffer, accepts a small keyboard control set, and draws a synthetic moving pattern. It does **not** execute the complete Doom game engine.

`GAMES/DOOM/ENGINE.LST` is the actual porting path. It combines ChrisOS support libraries and platform adapters with a large set of source files from `third_party/doomgeneric_src/doomgeneric`, ending in the ChrisOS-specific `MAIN.CC`. The generated `ENGINE.CLV` is therefore the important artifact when discussing the real engine port.

## Why Doom is a useful systems test

A real Doom engine exercises several layers simultaneously:

1. C language and ABI compatibility sufficient for a large legacy program.
2. Dynamic memory and standard-library-like services.
3. Binary file access for WAD data.
4. A stable 320×200 indexed framebuffer.
5. Palette updates.
6. Keyboard event translation.
7. A clock and sleep primitive.
8. A host-specific entry point and command-line model.

A failure after the kernel has booted is consequently not just a graphics problem. The failure can originate in the compiler, CLVM semantics, memory model, libc subset, filesystem, platform shims, or assumptions inside upstream Doom code.

## Two validation targets, not one

The repository's Doom tests distinguish the lightweight demo from the full engine.

`tools/test_doom_compile.c` compiles `GAMES/DOOM/DOOM.LST`, which belongs to the smaller bring-up target. It is valuable compiler coverage but must not be cited as proof that `ENGINE.LST` compiles.

`tools/test_doom_engine.c` is the engine-specific compile gate. It reads `ENGINE.LST`, allocates an 8 MiB output buffer, invokes `chrisc_compile_files_ex`, and verifies that the compiler progress callback reports every source in the list.

The distinction prevents a common documentation error: "Doom compiles" can refer either to the demo or to the much larger engine port.

## Build composition

`ENGINE.LST` starts with ChrisOS library implementations such as string, stdio, stdlib, ctype and math. It then adds the ChrisOS Doom adapters:

- `I_CHRIS.CC`
- `I_SOUND.CC`
- `I_VIDEO.CC`
- `W_FILE.CC`
- `I_INPUT.CC`

After those adapters, the list includes the DoomGeneric engine modules: game state, event handling, maps, monsters, rendering, menus, WAD handling, zone allocation and many other original subsystems. `MAIN.CC` is appended as the executable entry point.

This structure is significant: ChrisOS is not reimplementing Doom gameplay from scratch. The port attempts to preserve the upstream engine while replacing the operating-system-facing edges.

## Entry point and synthetic argv

`MAIN.CC` builds an argument vector manually. The reviewed version supplies approximately the equivalent of:

```text
doom -iwad GAMES/DOOM/DOOM1.WAD -mb 16
```

It assigns `myargc` and `myargv`, initializes the DoomGeneric host layer with `DG_Init()`, and calls `D_DoomMain()`. The outer ChrisC entry point then repeatedly invokes `doomgeneric_Tick()` and yields with `wait(1)`.

The explicit argument construction avoids depending on a conventional Unix process startup ABI. It also makes the WAD location and requested memory setting deterministic inside the current environment.

## Runtime memory and execution assumptions

The engine test and runtime tooling reveal another boundary: the full engine is a much larger CLVM workload than ordinary demos.

Several diagnostic tools instantiate `ENGINE.CLV` with a 32 MiB VM memory region. The synthetic command line additionally passes `-mb 16` to Doom itself. These are different layers: the former is VM memory made available by the harness, while the latter is an argument interpreted by the Doom engine's own memory configuration.

Documentation should not collapse those two quantities into one heap limit.

The port can execute through interpreter or JIT paths depending on the surrounding runtime configuration. Correctness therefore depends not only on source compilation but also on CLVM instruction semantics and JIT equivalence for the generated program.

## Video path

The ChrisOS backend uses the classic Doom resolution and representation:

- width: 320 pixels;
- height: 200 pixels;
- one byte per pixel;
- 64,000-byte screen buffer;
- 256-entry palette, three bytes per entry.

`I_InitGraphics()` points Doom's `I_VideoBuffer` at `DG_Screen`. `I_SetPalette()` forwards palette changes to `setpal()`. `I_FinishUpdate()` calls `DG_DrawFrame()`, which ultimately invokes `fb_blit()`.

The important data path is therefore:

```text
Doom renderer
    ↓
I_VideoBuffer / DG_Screen (320×200 indexed pixels)
    ↓
DG_DrawFrame()
    ↓
fb_blit()
    ↓
ChrisOS graphics path
```

There is no claim here that the backend implements a modern GPU API. It is deliberately a small indexed-framebuffer compatibility boundary.

## Video ABI details

The video boundary has several concrete invariants.

`DG_Screen` is exactly 64,000 bytes and `I_ReadScreen` copies exactly 64,000 bytes. `I_InitGraphics` sets `I_VideoBuffer = DG_Screen`, width 320 and height 200.

Palette transport is separate from pixel transport. `I_SetPalette` forwards the supplied 768-byte palette to `setpal`; the indexed screen buffer itself continues to contain one-byte color indices.

Several configuration hooks are intentionally stubs. For example, `I_GetPaletteIndex` currently returns zero rather than performing RGB lookup, and window-title/configuration callbacks do not establish a full desktop-video backend.

These no-op surfaces matter because upstream code may legally call them even if the current gameplay path rarely depends on their result.

## Input translation

The full engine path does not rely on `DG_GetKey()` for gameplay. That function currently reports no event. Instead, `I_StartTic()` polls ChrisOS key state and translates state transitions into Doom events using `D_PostEvent()`.

`poll_key()` compares the current key state with `key_was[128]`. A transition from up to down posts a key-down event; a transition from down to up posts a key-up event. This edge detection prevents a held key from being emitted as a new press every poll.

The mapping includes Escape, Enter, Tab, Backspace, Space/use, Ctrl/fire, Shift, arrow keys, WASD, weapon numbers, and Y/N for confirmation dialogs.

This is an adapter between two different input models: ChrisOS exposes polled key state, while Doom expects an event stream.

## Timing

`DG_GetTicksMs()` converts the ChrisOS `ticks()` clock from an assumed 60 Hz basis into milliseconds:

```text
milliseconds = ticks × 1000 / 60
```

`DG_SleepMs()` performs the inverse approximation and calls `wait()` for at least one tick. This is intentionally coarse. It is sufficient as a bring-up bridge, but it is not a high-resolution timer implementation.

## Input-state memory

The edge translator stores prior state in `key_was[128]`. `poll_key(sc, code)` indexes this array directly with each hard-coded scan code used by the adapter.

The current mapped scan codes are all below 128, so the table covers the explicit mapping. Extending the adapter with a scan code at or above 128 would require changing the storage or validating the index.

Each transition builds a local `dg_event` with type 0 for key down and 1 for key up, and copies the translated Doom key code into both `data1` and `data2`.

That is a concrete ABI adaptation, not merely "keyboard support."

## WAD access

`W_FILE.CC` adapts Doom's WAD file interface to the ChrisC file API. `W_OpenFile()` opens a path with `fopen()`, obtains its size with `fsize()`, allocates a small descriptor, and retains the integer file descriptor. `W_Read()` seeks to an offset and calls `fread()`. `W_CloseFile()` closes the descriptor and frees the wrapper.

The reviewed repository contains both `DOOM1.WAD` and a very small `DOOM1.MINI.WAD`. The full entry point explicitly selects `GAMES/DOOM/DOOM1.WAD`.

The separate demo in `DOOM.CC` takes another approach: it reads the entire WAD into allocated memory, scans the directory, locates the `PLAYPAL` lump and copies 768 palette bytes. That code is useful for validating WAD parsing and palette transport, but should not be described as the full game engine.

## WAD I/O failure semantics

`W_OpenFile` rejects a failed `fopen`, allocation failure and non-positive `fsize`. On allocation failure it closes the already-open descriptor before returning.

`W_Read`, however, trusts the supplied offset and length and delegates semantics to `fseek`/`fread`; it does not compare `offset + buffer_len` against the cached WAD length itself. The engine's WAD layer is expected to request valid ranges.

The adapter also does not memory-map the WAD: `mapped` remains null and reads are descriptor-based.

This keeps the host shim small, but malformed or unexpected upstream requests are not independently range-checked by this layer.

## Audio status

Audio is not implemented in the reviewed Doom backend. `I_SOUND.CC` provides the symbols expected by the engine, but initialization, playback, music, channel management and precaching are effectively no-ops. Sound-start calls return failure-like values and `I_SoundIsPlaying()` returns false.

This is an explicit port limitation rather than evidence that ChrisOS as a whole cannot produce audio.

## Compatibility shims versus native services

The port illustrates a useful rule for bringing existing software into a new OS: preserve the application-facing contract and make the smallest possible host adapter.

For Doom, the adapters are narrow:

| Engine expectation | ChrisOS bridge |
|---|---|
| indexed video buffer | `DG_Screen` / `I_VideoBuffer` |
| frame presentation | `fb_blit()` |
| palette | `setpal()` |
| key events | `key()` + `D_PostEvent()` |
| monotonic-ish time | `ticks()` |
| sleep/yield | `wait()` |
| WAD file access | `fopen/fseek/fread/fsize` |
| heap | ChrisC runtime allocation |
| sound/music | currently stubbed |

This keeps most Doom source code unaware of ChrisOS-specific details.

## Executable evidence in the repository

The current tree contains several increasingly strong validation tools:

- `test_doom_engine.c`: compiles the full `ENGINE.LST` and checks compile-progress coverage;
- `test_doom_path_pcs.c`: loads `ENGINE.CLV`, gives the VM 32 MiB and steps the interpreter while reporting PC/SP checkpoints;
- `test_doom_jit_smoke.c`: parses the engine image, JIT-compiles it and executes repeated instruction-budget slices;
- `doom_qemu_smoke.py`: boots ChrisOS in QEMU and captures serial evidence;
- `doom_qemu_long_smoke.py`: enables `SYS/SMOKE.DOOM`, boots for a longer interval and defines success as opening `DOOM1.WAD`, reaching engine/startup evidence and seeing none of its configured fatal markers.

These files define useful evidence levels. Their presence does not mean every one was executed successfully in this documentation update. A documentation build should report actual test results separately from describing available gates.

## What the current port proves

The presence of a generated `ENGINE.CLV` and the broad source list demonstrates that the ChrisC/CLVM toolchain can process a substantially larger body of DoomGeneric-derived code than the small standalone demo. It also shows concrete host bindings for video, input, timing and WAD files.

It does **not**, by itself, prove that every game path is correct, that every map can be completed, that audio works, or that the engine has reached production-quality compatibility. A compiled artifact and a fully validated runtime are different milestones.

## Debugging the bring-up

For a port at this stage, debugging should proceed by boundary rather than by visual symptom.

A practical sequence is:

```text
1. Confirm MAIN.CC starts.
2. Confirm synthetic argv is intact.
3. Confirm DG_Init returns.
4. Confirm DOOM1.WAD opens and has a plausible length.
5. Confirm W_Read returns correct header bytes.
6. Confirm D_DoomMain advances beyond WAD initialization.
7. Confirm I_InitGraphics establishes I_VideoBuffer.
8. Confirm I_StartTic posts transitions correctly.
9. Confirm I_FinishUpdate reaches fb_blit.
10. Only then debug gameplay/rendering corruption.
```

This approach separates compiler/runtime faults from data-file faults and device-adapter faults.

## Algorithmic and performance considerations

At 320×200, `I_ReadScreen` is O(64,000) for every full copy. Frame presentation also processes a 64,000-byte indexed surface before the downstream graphics path handles scaling/composition.

Input polling is O(K) in the fixed mapped-key set per tic. WAD reads are proportional to the requested byte count plus filesystem seek/read cost.

The adapter code is intentionally simple; Doom's heavier costs remain in the upstream renderer, gameplay and WAD/zone systems. The port should therefore be profiled as an end-to-end workload rather than optimizing these shims in isolation.

## Known limitations at the reviewed revision

The current integration has several deliberate or incomplete areas:

- sound and music are stubbed;
- `DG_GetKey()` itself does not supply gameplay input;
- timing is derived from a 60 Hz tick assumption;
- the video path is fixed to 320×200 indexed output;
- several video configuration hooks are no-ops;
- the standalone `DOOM.CC` target is a visual/WAD demo, not the complete Doom engine;
- successful compilation of `ENGINE.CLV` should not be equated with complete runtime validation.

These boundaries are useful documentation. They define where further work belongs instead of hiding incomplete behavior behind a generic statement that “Doom was ported.”

## Architectural lesson

Doom is valuable to ChrisOS because it forces independent subsystems to agree on real contracts. Small test programs can validate a syscall or a framebuffer function in isolation. Doom combines memory, files, events, timing, rendering and a large C program into one workload.

For that reason, the port is best understood as a systems-integration benchmark: the closer the unmodified engine gets to correct execution, the more complete and compatible the ChrisC/CLVM userspace environment has become.
