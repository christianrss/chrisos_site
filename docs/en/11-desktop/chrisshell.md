---
id: chrisshell
lang: en
type: technical-chapter
volume: 11-desktop
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - APPS/SHELL/SHELL.CC
  - APPS/SHELL/SHELL.LST
  - APPS/SHELL/Makefile
  - LIB/WIN.CC
  - LIB/UI.CC
  - LIB/APP.CC
depends_on:
  - input-routing
  - window-manager
  - desktop-applications
  - chrisc-clvm
  - chrisfs
---

# ChrisShell: the graphical command environment

ChrisShell is the command-oriented application of the ChrisOS desktop. It is written in ChrisC, linked with the common window, UI and application libraries, compiled to CLVM bytecode and installed into the system image as `APPS/SHELL/SHELL.CLV`.

Its role is broader than displaying a prompt. The shell exposes filesystem operations, program execution, compilation, builds, application launching, runtime diagnostics and library reload operations through a small interactive interface. It is therefore one of the main control surfaces connecting the desktop to the self-hosted development stack.

## Architecture

```text
keyboard input
     |
     v
command line buffer
     |
     v
run_line() dispatcher
     |
     +--> ChrisFS: pwd/cd/ls/cat/mkdir/rm
     +--> compiler: cc
     +--> build system: make
     +--> runtime: run/app_spawn
     +--> diagnostics: heap/fps
     +--> dynamic libraries: reload
     |
     v
scrollable output log
```

The shell is an application, not the kernel command interpreter. Commands are decoded in `APPS/SHELL/SHELL.CC` and translated into ChrisC/CLVM library or syscall interfaces.

## Command-line state

The current input line is stored in the fixed 160-byte `g_line` array and its logical length in `g_n`. This is a deliberately bounded interface. It does not implement an arbitrarily large command language or a POSIX-compatible parser.

Command recognition is performed by `starts_word()`, which matches a command name only when the following byte is either zero or a space. `arg_after()` advances past the command prefix and spaces to locate the remaining argument text.

This means the current grammar is intentionally simple: command plus remainder. Documentation must not imply shell quoting, pipelines, redirections, variable expansion, globbing or job-control syntax unless those mechanisms are added to the source.

## Command history

`g_hist` reserves 1280 bytes, divided into eight 160-byte slots. `hist_save()` stores commands in a circular eight-entry history, while `hist_load()` reconstructs a selected entry into the active command buffer.

The design is small but useful for an OS development environment: recent compile, run and diagnostic commands can be recalled without requiring a persistent history database.

## Working directory model

The shell keeps its own current-directory string in `g_cwd`, currently sized at 96 bytes. `cwd_init()` starts at the root representation, while `set_cwd()` changes the stored path. `join_cwd()` combines relative command arguments with the current directory and accepts a leading `/` as an absolute path.

In the reviewed implementation, `cd ..` returns to the root rather than implementing a general component-by-component parent traversal. The shell's path model is consequently simpler than a mature Unix shell.

## Filesystem commands

The built-in filesystem surface includes:

- `pwd` — prints the shell working directory;
- `cd` — changes the shell working directory after checking `isdir()`;
- `ls` — enumerates entries with `readdir()`;
- `cat` — opens and reads a file in bounded chunks;
- `mkdir` — creates a directory;
- `rm` — removes a path with `unlink()`;
- `clear` — resets the shell output log.

`cmd_ls()` limits enumeration to 512 iterations and filters names to printable ASCII before writing them to the log. `cmd_cat()` reads up to 180 bytes per iteration and limits itself to 64 iterations. These bounds are part of the current implementation and prevent the UI operation from becoming an unbounded loop.

## Compiler integration

The `cc` command resolves its argument against the current directory and invokes `sys_cc()`. The parser accepts the `cc -c` spelling by skipping `-c` before resolving the source path.

On failure, the shell obtains diagnostic text with `sys_err()` and appends it to the visible log. On success it emits `cc ok`.

This creates a direct interactive route from source stored in ChrisFS to the ChrisC compiler from inside ChrisOS.

## Build integration

The `make` command invokes the OS build interface rather than launching a host process. Together with `cc`, this makes ChrisShell part of the self-hosting path: source editing can be followed by compilation/build without leaving the operating-system environment.

ChrisShell is therefore complementary to ChrisEditor. The editor provides source-oriented interaction; the shell provides command-oriented orchestration.

## Program and application execution

`run` resolves a path relative to `g_cwd` and passes it to `sys_run()`. Failure diagnostics are retrieved through `sys_err()`.

The shell also has explicit application shortcuts. In the reviewed source, `doom` launches `GAMES/DOOM/ENGINE.CLV` with `app_spawn()`, while `world` launches `GAMES/WORLD.CLV`. These commands are useful integration probes because they cross application loading, CLVM execution, graphics and window-management boundaries.

They should not be interpreted as a general package manager or process-control language.

## Runtime diagnostics

`heap` displays values returned by `sys_heap_used_kb()` and `sys_heap_free_kb()`. `fps` reports the current frame rate together with `sys_frame_p50()` and `sys_frame_p95()` timing values.

These commands turn the shell into a lightweight observability interface. They are especially useful in ChrisOS because application, graphics and runtime development occur together and regressions can otherwise be difficult to localize.

## Runtime library reload

`reload` calls `lib_reload()`. When no argument is supplied, the reviewed implementation defaults to `LIB/WIN.CLS`. This provides an experimental path for replacing/reloading runtime library material without expressing the operation as a complete system reboot.

The presence of this command does not by itself establish general-purpose hot code replacement. Its semantics are those provided by the current `lib_reload()` implementation.

## Output log

Shell output is not written into an unbounded terminal stream. `log_init()` attempts a 49152-byte allocation and falls back to 8192 bytes if necessary. `log_trim()` begins discarding old content when the log approaches capacity, normally dropping 4096 bytes before compacting the remainder.

`log_line()` accepts printable ASCII plus newline and limits the amount copied from a single supplied message. The UI can therefore render a bounded scrollable history without continuously consuming heap memory.

This is an application log model rather than a full terminal emulator. There is no evidence in the reviewed source for ANSI/VT escape-sequence emulation, pseudo-terminals or a TTY line discipline.

## Error handling

Most command paths report a compact success/failure result in the log. Runtime/compiler failures can additionally expose `sys_err()` text. Memory allocation failure for the large log degrades to a smaller allocation; if no log exists, logging routines return without dereferencing an invalid buffer.

The implementation is intentionally direct. It does not provide shell-level transactions or rollback for filesystem operations.

## Security boundary

ChrisShell is a privileged-looking interface from a user's perspective because it can compile, remove files, launch applications and reload libraries. Architecturally, however, the actual authority is determined by the syscalls and runtime interfaces that ChrisOS exposes to the CLVM application.

A future capability or permission model should therefore be enforced below the command parser. Hiding a command in the UI is not a security boundary.

## Current limitations

The reviewed shell is not POSIX `sh`, Bash or a Unix TTY environment. Its parser is intentionally small; history is limited to eight commands; paths and command lines have fixed buffers; directory enumeration and `cat` use bounded loops; output is a custom graphical log; and advanced shell-language constructs are not established by the source.

These constraints are useful pedagogically because the implementation exposes the essential mechanisms without burying them beneath a large compatibility layer.

## Architectural significance

ChrisShell helps close the ChrisOS development loop:

```text
ChrisEditor -> source in ChrisFS
     |
     v
ChrisShell -> cc / make
     |
     v
CLVM program
     |
     v
run / app_spawn
     |
     v
observe with heap / fps / errors
```

A self-hosted operating-system playground needs more than a compiler in isolation. It needs a usable route for invoking that compiler, manipulating source files, starting generated programs and inspecting failures. ChrisShell provides that command-oriented route in the current desktop architecture.
