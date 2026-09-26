---
id: kernel-model
lang: en
type: technical-chapter
volume: 04-kernel
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/start.c
  - kernel/metal/syscall.c
  - kernel/wm/main.c
symbols: []
depends_on:
  - power-on-kstart
  - x86-64-memory-privilege
related:
  - interrupts-smp
  - processes-syscalls
---

# Kernel model and trust boundaries

## What a kernel is

A kernel is the privileged software layer that owns the machine-wide mechanisms ordinary programs must not control directly. It manages address spaces, privileged CPU state, interrupt handling, physical memory, device access and shared resource policy.

The word "kernel" does not imply one universal internal architecture. Systems can organize privileged services as monolithic kernels, microkernels, hybrid structures or other designs. The relevant question is where code runs, which address space it occupies and what failure boundaries actually exist.

## ChrisOS model

The current ChrisOS kernel is best described as **monolithic and modular**. Core memory management, filesystems, device drivers, graphics, window management, networking and language/runtime integration are compiled into the privileged kernel image or invoked through privileged kernel services.

"Modular" here refers to source and interface separation, not strong process isolation between every subsystem. A bug in a ring-0 driver can still corrupt kernel memory because it shares the privileged address space.

## Trusted computing base

The trusted computing base is the set of components whose correct behavior is required to preserve the system's security and integrity properties. In ChrisOS that includes, among other code, low-level memory management, page-table manipulation, interrupt entry, process isolation, user-copy code and device paths able to DMA into memory.

A useful rule is:

```text
greater privilege
      +
greater memory reach
      +
more asynchronous behavior
      =
higher consequence of bugs
```

A line count is therefore not a measure of trust importance.

## Boundaries visible in ChrisOS

Several boundaries coexist.

| Boundary | What it separates |
|---|---|
| ring 3 → ring 0 | native user process from privileged kernel |
| CLVM guest memory → kernel | virtual-machine offsets from host/kernel pointers |
| process CR3 → kernel CR3/shared high half | user address spaces from kernel mappings |
| driver API → device registers | subsystem policy from hardware protocol |
| ChrisC app → CLVM syscalls | language application from kernel services |

These boundaries are not equally strong. An in-kernel C module calling another in-kernel module is mainly an interface boundary; a ring-3 process crossing through a syscall is also a hardware privilege boundary.

## Policy and mechanism

Operating-system architecture benefits from separating **mechanism** from **policy**.

Mechanism answers how something can be done: map a page, schedule a runnable process, submit a block request.

Policy answers which choice the system makes: which process runs, which page permissions are permitted, which disk becomes the root filesystem.

ChrisOS still contains places where mechanism and policy are close together, which is common in an experimental kernel. Documentation must identify the current interface rather than pretending a conceptual separation has already become a separate service.

## Global state

Monolithic kernels often use global structures because there is one kernel instance. Global state is not automatically wrong, but it requires explicit rules:

- who initializes it;
- which CPU may mutate it;
- which lock protects it;
- whether interrupt context may access it;
- what happens during teardown;
- whether a process or VM owns part of it.

`docs/LOCKING.md` and `docs/RESOURCE_OWNERSHIP.md` in the ChrisOS source repository document these contracts for several current subsystems.

## Failure domains

A user process page fault can be contained by marking or terminating that process. A kernel page fault while holding a critical lock may make continuation unsafe. A device DMA bug can overwrite memory without executing a CPU store instruction.

This difference explains why kernel code typically validates external inputs, checks arithmetic for overflow and has stricter ownership requirements than ordinary application code.

## Boot-time dependency graph

`kstart` demonstrates architecture through initialization order. Physical memory must exist before page-table or heap structures can allocate pages. Interrupt handlers must exist before asynchronous interrupts are useful. Storage must be initialized before ChrisFS can mount. Language/runtime services come after the core machine and storage foundations they depend on.

The order is therefore a partial dependency graph encoded as executable control flow.

## The kernel as an interface producer

The kernel presents several contracts upward:

- system calls to native user programs;
- CLVM syscalls to ChrisC programs;
- filesystem operations;
- graphics surfaces and drawing operations;
- process/task lifecycle;
- network/socket interfaces.

A stable operating system is not merely code that "boots." It is a set of contracts whose invalid inputs, ownership transitions and failure outcomes are sufficiently defined to be relied on by other software.
