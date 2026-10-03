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
  - kernel/wm/desktop.c
  - compiler/lang_pipeline.c
  - compiler/lang_pipeline.h
  - kernel/lang/clvm_sys.c
symbols:
  - buf_init
  - rebuild_line_index
  - line_for_pos
  - insert_at
  - delete_range
  - insert_block
  - find_from
  - handle_key
  - handle_text
  - draw_text_view
  - do_compile
  - do_debug
  - do_step
  - do_over
  - do_out
  - do_cont
  - do_bp
  - do_watch
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

## Event delivery from the desktop

ChrisEditor does not read the kernel keyboard event queue directly. `desktop_frame` identifies the focused `TASK_APP` and forwards key/text events to the corresponding language slot. The runtime stores them in separate circular queues.

The current runtime defines `LANG_EVQ = 8` for each queue. If eight key events or eight text events are already pending, the next event is dropped rather than blocking the desktop or growing memory.

Inside the editor main loop, `ev_key()` is drained until it returns zero, then `ev_text()` is drained in the same way. Key events represent controls such as arrows, escape, enter and editor shortcuts; text events represent printable characters.

During window dragging/resizing the desktop intentionally does not select the application slot for key/text delivery. The global events are still drained. This prevents an application from interpreting window-management interaction as editor input, but it also means input generated during that interval can be lost.

Pointer input is different: the application window library polls mouse state and performs local hit testing for buttons, scrollbars and editor regions.

## Modal state machine

The source describes the editor as a small VI-like editor. Its principal modes are Normal, Insert, Command, Visual and Visual-line. Escape returns to Normal mode. Commands include insertion with `i`, `a` and `o`, visual selection with `v`/`V`, line yank with `yy`, paste with `p`/`P`, deletion with `dd` and `x`, searching with `/`, repeat search with `n`/`N`, and movement with `h`, `j`, `k`, `l`, `0`, `$`, `gg` and `G`.

The command mode also connects editing to the development environment. The current command set includes `:w`, `:e`, `:n`, `:q`, `:wq`, `:cc` and `:make`. Therefore compilation is not merely an external host workflow: the editor contains explicit paths for invoking the ChrisOS compiler and build facilities.

## Editing algorithms

The contiguous buffer makes the performance properties explicit.

`insert_at` shifts every byte after the cursor one position to the right. Inserting near the beginning of an n-byte file is O(n). `delete_range` shifts the suffix left by the deleted length and is likewise O(n) in the worst case. `insert_block` shifts the suffix once and then copies the inserted block.

This is appropriate for the current bounded editor but differs from rope/piece-table designs that optimize large-file mutation.

Search is also deliberately simple. `find_from` performs a naive forward or backward scan and compares the search pattern at each candidate. With document length n and pattern length m, the worst case is O(n*m).

These costs are useful design facts because editor responsiveness can become an integration signal for CLVM memory access and rendering overhead as file sizes grow.

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

## Line index and lexical state

The editor maintains a line index instead of rescanning from byte zero for every vertical operation.

`rebuild_line_index` walks the document once, recording line-start offsets and a small lexical state for each indexed line. The state tracks whether a line begins inside a block comment and resets line-comment/string state at newline boundaries as appropriate.

The table is limited to 8192 line entries. Rebuild cost is O(n) in document bytes.

`line_for_pos` uses binary search over `g_line_starts`, reducing byte-offset-to-line lookup to O(log L) after the index is valid. Mutations set `g_line_index_dirty`, so the next index-dependent operation pays the O(n) rebuild cost.

This combination is a useful middle ground between rescanning on every cursor move and maintaining a complex incremental parse tree.

## Navigation and viewport state

The editor distinguishes document position from viewport position. `g_cur` tracks the cursor, while vertical and horizontal scroll state is stored separately. Additional cached values (`g_seen_*`) and `g_view_gen` allow the application to identify view changes and avoid treating every frame as a completely unrelated state.

`jump_line()` rebuilds or verifies the line index through `ensure_line_index()`, clamps a requested line to the known line count, maps it to a byte offset and then brings the cursor into view.

## Selection and clipboard-like state

Visual selection is represented by `g_sel_anchor`. Yanked data is stored separately through `g_yank`, `g_yank_len`, `g_yank_cap` and `g_yank_linewise`. This gives ChrisEditor its own editing-level selection/yank model rather than relying on a global desktop clipboard.

That distinction matters architecturally: input focus belongs to the window/task system, while the semantic meaning of a key sequence such as `yy` belongs to the editor state machine.

## Rendering pipeline

`draw_text_view` renders only the visible portion of the document. It derives the first byte from the line index, draws line numbers, tracks lexical string/comment state and applies simple syntax colors.

Rather than emitting every text fragment independently, the editor accumulates text runs and flushes them through `textruns`. The code flushes when the run count approaches 80 or the temporary string storage approaches 1600 bytes. This reduces the number of individual drawing calls for a visible frame.

Vertical and horizontal scrollbars are provided by the window library. The caret is painted separately by `paint_caret`, using the indexed line and current horizontal scroll to map the byte cursor to window coordinates.

The renderer remains byte/character-oriented. It does not establish Unicode grapheme layout, proportional source-text shaping or a general retained-mode widget tree.

## Source-aware behavior

The current editor recognizes source-oriented file names and contains a small ChrisC keyword model. Keywords visible in the reviewed implementation include `int`, `void`, `char`, `if`, `else`, `while`, `for`, `return`, `break` and `continue`. The editor can therefore apply source-aware rendering without requiring a separate language server.

This is intentionally a small lexical mechanism, not a complete ChrisC parser. Syntax coloring must not be confused with compiler semantic analysis.

## Debugger integration

ChrisEditor is not limited to compile and run buttons. The source includes debugger control paths built on `dbg_ctl`.

`do_debug` saves dirty text first, arms debugging, compiles the current source, derives the CLV output name and starts it. When the runtime exposes a source line, `dbg_follow` updates `g_dbg_line` and moves the editor to that line.

The editor has controls for:

- step into;
- step over;
- step out;
- continue;
- stop/detach;
- toggle a breakpoint on the current line;
- set a watch address parsed from decimal or hexadecimal command input.

The diagnostic/debug panel can display current debugger text and highlights the active source line in the gutter.

This is an early source-level debugging interface, not a claim of a full symbolic debugger. The quality of source mapping and supported inspection operations is bounded by the CLVM/compiler debug facilities.

## Compile and build integration

`do_compile()` first checks whether the current path is a recognized source file and then calls `sys_cc(g_path)`. Compiler diagnostics are copied into an error panel by `capture_err()`. The routine also scans diagnostics for a `:<digits>` pattern and stores the discovered line number in `g_err_line`, enabling source navigation from compiler output.

`do_make()` invokes `sys_make("Makefile", "all")` and routes failures through the same diagnostic panel. These paths make ChrisEditor an early self-hosting interface: edit, save, compile, inspect diagnostics and build can occur within the OS environment.

## File-browser algorithm

The editor-local browser scans directory entries using `readdir` with indices from 0 through 511.

`rebuild_index` counts acceptable entries by scanning from the beginning. `entry_at(want)` performs another scan from the beginning until it reaches the requested logical entry. The current design therefore favors simplicity over maintaining a cached directory vector.

The browser accepts text-like files for loading/saving and descends into directories. Path construction uses the bounded `join_path` routine.

A directory with more than 512 scanned entries is outside the current browser model. This is a concrete application limit separate from ChrisFS's theoretical directory capacity.

## File browsing

The editor contains directory and browse state in `g_dir`, `g_browse`, `g_scroll`, `g_hscroll`, `g_nshow` and `g_ntotal`. `join_path()` constructs a child path using bounded output capacity, while `parent_dir()` moves toward the parent by locating the last slash.

This is not a replacement for the dedicated file manager. It is an editor-local navigation facility designed to select documents without leaving the editing workflow.

## Memory and ownership

The main text and yank areas are explicit application allocations. Fixed arrays hold paths, commands, diagnostics, line indexes and transient rendering state. This architecture is suitable for the current CLVM application model because it makes ownership visible and avoids dependence on a sophisticated runtime object graph.

The trade-off is the presence of hard limits. Examples in the reviewed source include 512-byte paths, an 8192-entry line index, 80-byte command/status fields and a bounded diagnostic panel. Callers and future extensions must treat these limits as part of current behavior.

## Failure behavior

Allocation failure is handled through progressively smaller text buffers; if all allocations fail, editor operations report the missing buffer rather than assuming memory exists. File-open and save failures update status state. Compilation and make failures preserve diagnostic text for the user.

The implementation remains experimental. A successful editor operation does not imply transactional filesystem semantics, crash recovery or automatic preservation of unsaved work. Those capabilities would require separate persistence mechanisms.

## Algorithmic cost summary

| Operation | Current algorithm | Cost |
|---|---|---|
| insert one byte | shift suffix right | O(n) |
| delete range | shift suffix left | O(n) |
| paste block | shift suffix + copy block | O(n + k) |
| rebuild line index | linear scan | O(n) |
| position -> line | binary search after rebuild | O(log L) |
| plain search | naive substring scan | O(n*m) worst case |
| directory count | up to 512 readdir calls | O(D) with D <= 512 |
| retrieve nth visible entry | rescan from start | O(D) |
| key/text enqueue/dequeue | fixed ring | O(1) |

The table describes the source algorithms, not benchmark results. Actual latency also includes CLVM execution and rendering costs.

## Validation

The strongest dedicated regression evidence in the reviewed revision is `tools/test_editor_path.c`. It compiles and executes a ChrisC bounded-copy algorithm under CLVM, checks path-capacity boundaries and canaries, and verifies that the real editor source still uses bounded copies for path, directory and status state.

The editor also serves as an integration workload whenever the application corpus is compiled into the ChrisOS image. Its `EDITOR.LST` explicitly depends on `LIB/WIN.CC`, `LIB/UI.CC`, `LIB/APP.CC` and `EDITOR.CC`.

## Additional validation gaps

`tools/test_editor_path.c` gives strong focused evidence for bounded path copying, including CLVM execution of the copy algorithm and canary checks.

The inspected repository does not provide equivalent dedicated tests for every editing algorithm. In particular, the chapter does not treat line-index correctness across all comment/string edge cases, large-file insertion behavior, event-queue overflow or debugger UI state as fully proven merely because the implementation exists.

Useful future gates include randomized edit sequences compared with a host reference buffer, line-index rebuild/reference comparisons, search wraparound tests, 8192-line boundary tests, event-burst tests above `LANG_EVQ`, and debugger source-line mapping tests.

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
