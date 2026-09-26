---
id: desktop-applications
lang: en
type: technical-chapter
volume: 11-desktop
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/wm/desktop.c
  - kernel/wm/task.c
  - kernel/wm/ui.c
  - APPS/EDITOR/EDITOR.CC
  - APPS/SHELL/SHELL.CC
  - APPS/EXPLORER/EXPLORER.CC
symbols: []
depends_on:
  - pixels-framebuffer
  - chrisc-clvm
related:
  - kernel-model
---

# Desktop, windows and applications

## Desktop as systems integration

A graphical desktop sits above many lower-level contracts simultaneously: timer/input delivery, graphics, task lifecycle, filesystem access, language runtime and resource ownership.

For this reason a desktop that remains interactive under repeated application open/close cycles is a broader integration test than a static boot image.

## Window state

A window/task record typically contains geometry, lifecycle state, focus/z-order information and application-specific backing state.

Current ChrisOS `task.c` maintains a finite task/window table. Slot reuse matters: closing a window must detach every resource that would otherwise leak into the next occupant of the slot.

## Composition

`ui.c` and graphics primitives draw desktop background, taskbar, icons, windows and cursor into the common presentation path.

The current architecture should not be mistaken for a modern GPU compositor with independently scheduled GPU surfaces for every window. It is a smaller desktop appropriate to the project's current graphics model.

## Focus and input routing

Keyboard/mouse input must be delivered to the intended task. Focus state and capture state are therefore part of the security/correctness contract.

Mouse capture has a defined owner and teardown paths. Losing focus or closing the owning slot must not leave input permanently captured.

## ChrisC applications

First-party applications are valuable because they exercise the public runtime interfaces rather than privileged internal calls. Examples include editor, shell, explorer/file manager and task manager paths.

The editor is especially important for self-hosting direction because it connects source text, filesystem, compilation/run commands and debugger workflows.

## Failure containment

A desktop should survive an application fault when the architecture claims that application is isolated. Native process faults and CLVM faults have different containment mechanisms, so the UI layer must handle both lifecycle models rather than assuming one universal "process."

## Responsiveness

Interactive scheduling has human-visible latency requirements. Long filesystem operations, shader compilation or device polls on the desktop path can make the system appear hung even when the kernel remains logically correct.

Performance analysis therefore needs latency and frame timing in addition to total throughput.

## Applications as contract tests

A complex first-party application becomes a regression workload for:

- filesystem paths and permissions;
- text rendering and input;
- VM memory;
- syscall ABI;
- window create/destroy;
- compilation/debug state;
- resource cleanup.

The application is not itself proof of every subsystem, but repeated realistic use exposes interface failures that isolated unit tests may miss.
