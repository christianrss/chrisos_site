---
id: file-manager
lang: en
type: technical-chapter
volume: 11-desktop
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - APPS/EXPLORER/EXPLORER.CC
  - APPS/EXPLORER/EXPLORER.LST
  - APPS/EXPLORER/Makefile
  - LIB/WIN.CC
  - LIB/UI.CC
  - LIB/APP.CC
depends_on:
  - input-routing
  - window-manager
  - desktop-applications
  - chriseditor
  - chrisfs
---

# File Manager: ChrisOS Explorer

The ChrisOS file manager is implemented by the Explorer application in `APPS/EXPLORER`. It is a ChrisC program compiled to CLVM bytecode and linked at source-list level with the common window, UI and application libraries. The application provides a graphical view over ChrisFS directories and connects file types to the rest of the desktop.

The implementation is intentionally small. Its value is architectural: it demonstrates directory enumeration, navigation, selection, scrolling and application dispatch through the same interfaces available to other ChrisC applications.

## Execution path

```text
ChrisFS directory
      |
      v
readdir()
      |
      v
Explorer entry filtering
      |
      v
selection + scrolling
      |
      +--> directory -> change cwd
      +--> .CLV      -> launch application
      +--> text      -> spawn ChrisEditor
      |
      v
window manager / CLVM applications
```

The file manager is therefore a bridge between persistent filesystem state and desktop applications.

## Application construction

`APPS/EXPLORER/EXPLORER.LST` includes `LIB/WIN.CC`, `LIB/UI.CC`, `LIB/APP.CC` and `APPS/EXPLORER/EXPLORER.CC`. Its Makefile compiles this source list into `APPS/EXPLORER/EXPLORER.CLV`.

This follows the same application model used by ChrisEditor and ChrisShell: application behavior is written in ChrisC, common desktop facilities are provided by libraries, and the resulting CLVM program runs inside the ChrisOS application environment.

## State model

The current directory is held in `g_cwd[96]`. Directory entries use `g_ent[64]`, assembled paths use `g_path[160]`, and a separate `g_show[64]` buffer is used for the visible portion of long directory paths.

Selection and viewport state are explicit integers: `g_sel` is the selected entry, `g_scroll` is vertical list offset and `g_hscroll` is horizontal path offset. `g_ntotal` records the number of accepted entries and `g_nshow` tracks rows rendered in the current frame.

These fixed buffers and counters are part of the current implementation. They are not a generic variable-length filesystem UI abstraction.

## Directory enumeration

`count_entries()` and `entry_at()` both use `readdir(g_cwd, index, g_ent)`. Enumeration is bounded to 512 attempts. Entries are accepted only when `name_ok()` succeeds.

`name_ok()` rejects empty names and bytes outside printable ASCII, currently 32 through 126. The Explorer consequently has a narrower display-name model than a Unicode-capable desktop file manager.

The current design re-enumerates directory data to count entries and again to locate a particular visible/selected entry. This keeps application state small and simple at the cost of repeated filesystem traversal.

## Path construction

`join_path()` concatenates the current directory, an optional slash and an entry name into `g_path`. `cwd_set()` replaces the active directory and resets vertical scrolling, horizontal scrolling and selection.

`parent_cwd()` scans the current path for its final slash and truncates there. Unlike the simplified `cd ..` behavior of the current ChrisShell, Explorer therefore supports stepping upward through nested path components.

The reviewed implementation uses fixed arrays and direct byte copies. These routines should not be described as a general dynamically sized path library.

## File-type dispatch

`open_entry()` determines what an activation means.

A name recognized by `is_clv()` is launched with `app_launch(g_path)`. A text-like name recognized by `is_textish()` starts `APPS/EDITOR/EDITOR.CLV` through `app_spawn_arg()`, passing the selected path to ChrisEditor. If neither file classification applies but `isdir(g_path)` succeeds, the Explorer enters that directory.

This is a compact form of file association:

```text
.CLV       -> CLVM application launcher
text/source -> ChrisEditor
folder      -> Explorer navigation
```

The association logic is hard-coded in the application source. The reviewed revision does not establish a registry, MIME database or user-configurable association layer.

## CLV recognition

`is_clv()` checks the extension shape and accepts upper- or lower-case final `V`/`v`. The implementation is deliberately lightweight rather than a complete case-insensitive extension parser.

Launching a `.CLV` file crosses an important boundary: a filesystem object becomes executable application input to the desktop/runtime stack.

## Text-file recognition

`is_textish()` contains small extension checks for source/text-oriented names. Recognized files are opened in ChrisEditor rather than rendered by Explorer itself.

This separation keeps the file manager focused on navigation and dispatch. Editing semantics, buffer management, compilation integration and source-aware rendering remain responsibilities of ChrisEditor.

## Graphical layout

The main loop creates a 520×380 window titled `Files` through `win_begin()`. The current directory is displayed near the top, followed by a parent row and the directory listing.

The list uses 18-pixel rows. Available list height determines `view`, the number of visible entries. The selected row is kept inside the vertical viewport by adjusting `g_scroll`. `win_vscroll()` provides the vertical scrollbar and `win_hscroll()` controls the displayed offset for long current-directory paths.

The implementation therefore demonstrates both logical scrolling and reusable window-library scrollbar widgets.

## Selection and keyboard input

Keyboard events are read with `ev_key()`. In the reviewed source, key code 7 moves selection upward, key code 8 moves downward and key code 3 activates the selected entry.

Selection is clamped whenever directory contents change so that `g_sel` remains valid for the current entry count. When the directory is empty, selection returns to zero and the UI displays `(empty dir)`.

The exact numeric key codes are an application-facing convention supplied by the current input/application libraries, not hardware scan codes.

## Pointer interaction

Pointer state comes from `mouse_btn()`, `mouse_x()`, `mouse_y()` and `win_mouse_in()`. The application converts global pointer coordinates to window-local coordinates using `win_ox()` and `win_oy()`.

A press transition is detected using `g_prev`, avoiding repeated activation while a button remains held. Clicking the first visible row invokes `parent_cwd()`. Clicking an entry computes the corresponding directory index, updates `g_sel` and calls `open_entry()`.

This is a concrete example of the input-routing and window-coordinate layers being consumed by a ChrisC desktop application.

## Horizontal path display

Long current-directory paths are not allowed to overflow the path display. `copy_show()` takes a byte offset and copies at most 46 visible bytes into `g_show`. The horizontal scrollbar changes that offset.

This is display clipping, not path truncation in the filesystem itself. The application maintains the current path separately from the shortened visible string.

## Empty directories and bounded work

The main loop explicitly tracks `g_empty`. When no valid entries are returned, Explorer renders `(empty dir)` rather than leaving an ambiguous blank list.

Directory scans stop after at most 512 `readdir()` indices. Rendering also stops once the visible row budget is exhausted. These bounds are significant for a graphical OS environment because they prevent a single frame from intentionally iterating over an unlimited number of entries.

## Relationship to ChrisEditor and ChrisShell

The three applications expose different views of the same underlying system:

```text
Explorer   -> graphical filesystem navigation
ChrisEditor -> source/text manipulation
ChrisShell  -> command-oriented filesystem/build/runtime control
```

Explorer hands text-oriented files to ChrisEditor. ChrisShell can manipulate the same filesystem through commands such as `ls`, `cat`, `mkdir` and `rm`. Together they form the current user-facing development environment over ChrisFS.

## Current limitations

The reviewed Explorer is not intended to match a mature desktop file manager. It does not establish copy/move dialogs, drag-and-drop, thumbnails, metadata/property panels, recursive search, mount browsing, permissions UI, trash/recycle semantics, configurable file associations or Unicode filenames.

Directory enumeration is bounded, file associations are embedded in source code, and path/name storage uses fixed byte arrays. Those constraints should be treated as implementation facts rather than hidden behind a more ambitious description.

## Architectural significance

Explorer proves that ChrisOS can expose filesystem objects to graphical applications without placing file-management policy inside the kernel. ChrisFS provides directory/file operations; the application decides how to enumerate, display and activate objects; the window/input libraries provide interaction; and the runtime launches the selected CLVM application.

That separation is important for the project's educational purpose: filesystem mechanism, application policy, GUI behavior and executable loading remain observable as distinct layers.
