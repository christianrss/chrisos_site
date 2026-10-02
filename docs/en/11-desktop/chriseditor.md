---
id: chriseditor
lang: en
type: technical-chapter
volume: 11-desktop
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - APPS/EDITOR/EDITOR.CC
  - APPS/EDITOR/EDITOR.LST
  - APPS/EDITOR/Makefile
  - LIB/WIN.CC
  - LIB/UI.CC
  - LIB/APP.CC
  - tools/test_editor_path.c
depends_on:
  - input-routing
  - window-manager
  - desktop-applications
  - chrisc-clvm
  - chrisfs
---

# ChrisEditor: a self-hosted modal editor

ChrisEditor is the ChrisOS graphical text and source editor. It is important for more than desktop usability: the application is part of the path from a system that merely executes software to one that can inspect, modify, compile and build its own software from inside the ChrisOS environment.

The current implementation is written in ChrisC and compiled to CLVM bytecode. Its source lives in `APPS/EDITOR/EDITOR.CC`; `EDITOR.LST` combines the editor with the window, UI and application libraries, and the application Makefile produces `APPS/EDITOR/EDITOR.CLV`.

## Execution path

The application crosses several ChrisOS layers:

```text
keyboard / pointer
        |
        v
input routing
        |
        v
window + UI libraries
        |
        v
ChrisEditor state machine
        |
        +--> ChrisFS file I/O
        |
        +--> compiler / make system calls
        |
        v
CLVM execution
```

This makes the editor a useful integration workload: failures can expose defects in input routing, window focus, the ChrisC compiler, CLVM, filesystem calls, memory handling or desktop repainting.

## Modal state machine

The source describes the editor as a small VI-like editor. Its principal modes are Normal, Insert, Command, Visual and Visual-line. Escape returns to Normal mode. Commands include insertion with `i`, `a` and `o`, visual selection with `v`/`V`, line yank with `yy`, paste with `p`/`P`, deletion with `dd` and `x`, searching with `/`, repeat search with `n`/`N`, and movement with `h`, `j`, `k`, `l`, `0`, `$`, `gg` and `G`.

The command mode also connects editing to the development environment. The current command set includes `:w`, `:e`, `:n`, `:q`, `:wq`, `:cc` and `:make`. Therefore compilation is not merely an external host workflow: the editor contains explicit paths for invoking the ChrisOS compiler and build facilities.

## Buffer model

The document is stored in a dynamically allocated byte buffer referenced by `g_buf`. `buf_init()` first attempts a 262144-byte allocation, then falls back to 65536 bytes and finally 8192 bytes. The current length is `g_len`, capacity is `g_cap`, and the cursor is represented by a byte offset in `g_cur`.

This is deliberately simpler than a rope, piece table or balanced-tree editor representation. Direct byte storage makes indexing and CLVM implementation straightforward, but insertion or deletion in the middle of a large document can require moving a suffix of the buffer. For a buffer of length `n`, such edits are therefore potentially O(n).

The implementation separately maintains line metadata in `g_line_starts` and `g_line_states`, with room for 8192 indexed lines. `g_line_index_dirty` records whether the index must be rebuilt. This avoids rediscovering every line boundary for operations that work in line coordinates.

## File paths and bounded copying

Paths are stored in 512-byte `g_path` and `g_dir` arrays. A dedicated `copy_cap()` routine copies at most `cap - 1` bytes and always terminates the destination. `path_set()`, `dir_set()` and `status_set()` use this bounded operation rather than planting a terminator at an unchecked source-derived index.

This behavior has a host-side regression test in `tools/test_editor_path.c`. The test exercises boundary lengths around the path capacity and checks canary bytes after destination buffers. It also scans `EDITOR.CC` to ensure that the bounded-copy implementation remains in use. This is concrete validation evidence for a class of memory-corruption defect rather than a documentation-only claim.

## Loading and saving

`load_file()` opens `g_path`, reads at most `g_cap - 1` bytes, appends a terminating zero and resets cursor, scrolling, dirty state and mode state. `save_file()` writes exactly `g_len` bytes and clears the dirty flag after the operation.

The current editor therefore treats its working document primarily as a byte sequence. The implementation does not expose a general Unicode text model in the reviewed source; documentation should not imply one.

## Navigation and viewport state

The editor distinguishes document position from viewport position. `g_cur` tracks the cursor, while vertical and horizontal scroll state is stored separately. Additional cached values (`g_seen_*`) and `g_view_gen` allow the application to identify view changes and avoid treating every frame as a completely unrelated state.

`jump_line()` rebuilds or verifies the line index through `ensure_line_index()`, clamps a requested line to the known line count, maps it to a byte offset and then brings the cursor into view.

## Selection and clipboard-like state

Visual selection is represented by `g_sel_anchor`. Yanked data is stored separately through `g_yank`, `g_yank_len`, `g_yank_cap` and `g_yank_linewise`. This gives ChrisEditor its own editing-level selection/yank model rather than relying on a global desktop clipboard.

That distinction matters architecturally: input focus belongs to the window/task system, while the semantic meaning of a key sequence such as `yy` belongs to the editor state machine.

## Source-aware behavior

The current editor recognizes source-oriented file names and contains a small ChrisC keyword model. Keywords visible in the reviewed implementation include `int`, `void`, `char`, `if`, `else`, `while`, `for`, `return`, `break` and `continue`. The editor can therefore apply source-aware rendering without requiring a separate language server.

This is intentionally a small lexical mechanism, not a complete ChrisC parser. Syntax coloring must not be confused with compiler semantic analysis.

## Compile and build integration

`do_compile()` first checks whether the current path is a recognized source file and then calls `sys_cc(g_path)`. Compiler diagnostics are copied into an error panel by `capture_err()`. The routine also scans diagnostics for a `:<digits>` pattern and stores the discovered line number in `g_err_line`, enabling source navigation from compiler output.

`do_make()` invokes `sys_make("Makefile", "all")` and routes failures through the same diagnostic panel. These paths make ChrisEditor an early self-hosting interface: edit, save, compile, inspect diagnostics and build can occur within the OS environment.

## File browsing

The editor contains directory and browse state in `g_dir`, `g_browse`, `g_scroll`, `g_hscroll`, `g_nshow` and `g_ntotal`. `join_path()` constructs a child path using bounded output capacity, while `parent_dir()` moves toward the parent by locating the last slash.

This is not a replacement for the dedicated file manager. It is an editor-local navigation facility designed to select documents without leaving the editing workflow.

## Memory and ownership

The main text and yank areas are explicit application allocations. Fixed arrays hold paths, commands, diagnostics, line indexes and transient rendering state. This architecture is suitable for the current CLVM application model because it makes ownership visible and avoids dependence on a sophisticated runtime object graph.

The trade-off is the presence of hard limits. Examples in the reviewed source include 512-byte paths, an 8192-entry line index, 80-byte command/status fields and a bounded diagnostic panel. Callers and future extensions must treat these limits as part of current behavior.

## Failure behavior

Allocation failure is handled through progressively smaller text buffers; if all allocations fail, editor operations report the missing buffer rather than assuming memory exists. File-open and save failures update status state. Compilation and make failures preserve diagnostic text for the user.

The implementation remains experimental. A successful editor operation does not imply transactional filesystem semantics, crash recovery or automatic preservation of unsaved work. Those capabilities would require separate persistence mechanisms.

## Validation

The strongest dedicated regression evidence in the reviewed revision is `tools/test_editor_path.c`. It compiles and executes a ChrisC bounded-copy algorithm under CLVM, checks path-capacity boundaries and canaries, and verifies that the real editor source still uses bounded copies for path, directory and status state.

The editor also serves as an integration workload whenever the application corpus is compiled into the ChrisOS image. Its `EDITOR.LST` explicitly depends on `LIB/WIN.CC`, `LIB/UI.CC`, `LIB/APP.CC` and `EDITOR.CC`.

## Current limitations

The reviewed implementation uses a contiguous text buffer and fixed-size auxiliary structures. Its source-aware logic is deliberately small. The documentation does not claim a language server, Unicode grapheme editing, multi-document buffer architecture, persistent undo journal, collaborative editing or crash-safe recovery because those properties are not established by the reviewed source.

## Architectural significance

ChrisEditor closes an important loop in ChrisOS:

```text
ChrisC source
   -> ChrisEditor modifies source
   -> ChrisFS persists source
   -> sys_cc / sys_make builds it
   -> CLVM executes generated programs
   -> desktop hosts the resulting applications
```

For a system intended as a playground for kernels, compilers, virtual machines and low-level tooling, this loop is more important than editor feature count. It demonstrates that the language/runtime/filesystem/desktop stack is becoming usable as a development environment rather than only as a bootable demonstration.
