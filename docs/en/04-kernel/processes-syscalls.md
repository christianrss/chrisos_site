---
id: processes-syscalls
lang: en
type: concept
volume: 04-kernel
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/proc.c
  - kernel/metal/proc.h
  - kernel/metal/syscall.c
  - kernel/metal/syscall.h
  - kernel/metal/elf.c
  - kernel/metal/user_enter.c
  - kernel/metal/idt.c
  - kernel/metal/irq.c
  - kernel/fs/fs.c
  - kernel/input/input.c
symbols:
  - proc_create
  - proc_destroy
  - proc_switch
  - syscall_init
  - syscall_dispatch
  - enter_user
depends_on:
  - virtual-memory
  - kernel-model
  - user-mode-entry
related:
  - elf-linking
  - user-copy
  - process-lifecycle
---

# Native processes and system calls

## Scope

A native ChrisOS process combines a protected virtual address space, process-owned resources and controlled ring-3 execution. The current system-call interface uses software interrupt `int 0x80` and a small register ABI. It is separate from CLVM execution and its syscall layer.

This chapter defines the native process/syscall contract at revision `da3df29cb397932c43d32373871fb9380e688ade`: process identity and CR3, entry vector, syscall numbering, register arguments, user-buffer validation, descriptor ownership, exit/fault return, current CPU restriction and concrete limitations.

## Native process versus CLVM application

Native processes execute machine code under x86 page-table and CPL protection. Their failure can be identified through saved CS/RIP/CR2 and their memory is owned through process mappings.

ChrisC applications can instead execute through CLVM slots. CLVM uses a guest memory model and VM dispatch.

The word “application” therefore does not identify one ABI in ChrisOS. Native and VM programs must be debugged, secured and scheduled according to their own contracts.

## Process identity

`PROC_MAX = 32`. PID 0 is reserved for the kernel. User PIDs occupy slots 1–31.

`proc_current` returns one global current PID. `proc_switch` may mutate it only on the BSP.

A process owns:
- CR3;
- region metadata;
- recorded physical frames;
- file descriptors and sockets keyed by PID;
- alive/state/name metadata.

The lifecycle chapter defines allocation and destruction in detail.

## Address space creation

`proc_create` obtains an address-space root using `mm_clone_kernel_space`. It commits the first user stack page before reporting success.

The new process therefore begins with the high-level kernel mapping context required for privilege transitions plus process-specific user mappings.

The exact ELF loader controls which executable segments and initial entry addresses are installed; process creation itself is independent of a particular executable format.

## Switching CR3

Before entering a native process, the kernel must select its CR3 with `proc_switch`.

The function rejects AP callers because `g_current` and related user execution state are global.

Changing CR3 changes translation context and may affect TLB state. The memory subsystem is responsible for valid roots and flush/coherency behavior.

## Entry mechanism

`enter_user` builds an `iretq` frame with user CS, user SS, user RSP, RFLAGS and entry RIP.

User selectors use RPL 3. Page mappings must independently have USER permission.

The initial user flags set IF, so normal interrupts may preempt the process.

Before the transition, the function records a kernel return RIP used when the process exits or is terminated by a user fault.

## Syscall gate

`syscall_init` calls:

```c
idt_set_user_gate(0x80u);
```

The gate attributes become DPL 3, permitting `int 0x80` from user code. Other normal exception/IRQ gates remain DPL 0.

The assembly interrupt path saves a common `irq_frame`. `irq_dispatch` recognizes vector `0x80` and calls `syscall_dispatch`.

This reuses the interrupt entry machinery for syscalls.

## Register ABI

The dispatcher reads the syscall number from saved RAX. Arguments use saved general registers according to each operation.

The current syscall numbers are:

| Number | Name | Main arguments |
|---:|---|---|
| 1 | `SYS_EXIT` | RDI = exit code |
| 2 | `SYS_WRITE` | RDI = fd, RSI = user buffer, RDX = bytes |
| 3 | `SYS_PUTPIXEL` | RDI = x, RSI = y, RDX = color |
| 4 | `SYS_FOPEN` | RDI = user path |
| 5 | `SYS_FREAD` | RDI = fd, RSI = destination, RDX = bytes |
| 6 | `SYS_FWRITE` | RDI = fd, RSI = source, RDX = bytes |
| 7 | `SYS_FCLOSE` | RDI = fd |
| 8 | `SYS_KEY` | RDI = key code |

Return values are written to saved RAX. Error is generally represented as all-bits-one via cast of -1 to `uint64_t`.

## BSP-only syscall execution

At the top of `syscall_dispatch`, the kernel checks `smp_current_cpu()`.

If the CPU is not zero, it writes -1 to RAX, advances saved RIP and returns.

The syscall layer therefore explicitly enforces the same single-CPU userspace model as process switching.

## Saved RIP advancement

Most non-exit syscall cases execute `frame->rip += 2`.

This encodes the current software-interrupt instruction/entry convention. The ABI depends not only on register choices but on how the saved return RIP is interpreted.

A future migration to SYSCALL/SYSRET must define its own RCX/R11, MSR and return-address semantics rather than retaining this logic blindly.

## SYS_EXIT

`SYS_EXIT` stores the integer exit code and calls the controlled-return path.

`syscall_return_to_kernel` replaces saved RIP with the kernel continuation recorded before `enter_user`, changes CS to the kernel code selector, sets RFLAGS and marks `g_user_exited`.

The subsequent common `iretq` therefore returns to ring 0 rather than to another user instruction.

This is the current process-run control model, not a POSIX wait/exit/zombie implementation.

## SYS_WRITE

Only fd 1 is accepted. Size is capped at 80 bytes.

The kernel copies from user memory into an 81-byte stack buffer, writes a safe NUL terminator and prints to serial.

The 81-byte capacity fixes an exact boundary bug: an 80-byte payload still needs byte 80 for NUL.

The syscall never passes the raw user pointer to the serial string routine.

## User-memory validation

`copy_from_user`/`copy_to_user` perform:
- canonical/lower-half range checks;
- configured user-window checks;
- current-process CR3 lookup;
- page-by-page translation;
- Present/User flag validation;
- Write validation for kernel-to-user copies;
- kernel access to the physical frame.

Missing user pages return error in syscall copy context.

This boundary is documented in full in the user-copy chapter.

## File descriptor table

The native syscall layer has `UFILE_MAX = 8` entries. Slots 0 and 1 are not allocated by `FOPEN`; searches begin at 2.

Each `UFile` stores:
- used;
- owner PID;
- path up to 128 bytes.

The file abstraction is path-backed rather than a persistent open-file object with offset/state in this structure.

`ufile_owned` rejects descriptors not owned by the current PID.

## SYS_FOPEN

The syscall copies up to 127 bytes from user memory into a 128-byte kernel array and forces the final byte to NUL.

It then finds a free fd from 2 through 7, marks it used, stores owner PID and copies the path.

No filesystem open operation is performed at this layer at that moment; the descriptor primarily captures path/ownership for later read/write operations.

If no slot is free, return is -1.

## SYS_FREAD

The request must be at most 512 bytes and the descriptor must belong to the current process.

`fs_read(path, kbuf, n)` reads into a kernel buffer. The exact returned byte count is copied to user memory.

Errors from filesystem or user-copy become -1.

There is no per-fd offset in `UFile`; semantics depend on `fs_read` path behavior rather than POSIX file-position state.

## SYS_FWRITE

The syscall caps at 512 bytes and first copies from user memory.

fd 1 is treated as serial output.

For other descriptors, ownership is required and `fs_write(path, kbuf, n)` performs the operation.

Again, the lower filesystem sees only kernel memory, not raw user pointers.

## SYS_FCLOSE

If the descriptor is owned by the process, the used and owner fields are cleared.

The function returns zero even when an unowned/invalid fd does not match the ownership condition in the current code. That concrete behavior should be preserved in ABI tests if compatibility matters.

## SYS_PUTPIXEL

Coordinates and color are passed directly to `gfx_put_pixel` after register conversion.

Unlike buffer syscalls, no user pointer crosses the boundary.

Security/correctness therefore depends on graphics-side bounds checking for coordinates rather than user-copy logic.

## SYS_KEY

The key syscall queries `input_key_down((int)RDI)` and returns 1 or 0.

This is a polling-style input ABI, not an event queue exposed to native user programs.

## Unknown syscall

Unknown RAX values produce -1, advance RIP by two and return.

There is no signal or process termination for an unsupported number.

## Descriptor cleanup

`syscall_close_owner(pid)` scans fd 2–7 and invalidates entries owned by a process.

`proc_destroy` calls this during teardown. This prevents file slots from remaining attached to a reused PID slot.

Socket resources have a separate process cleanup path.

## Fault path

Before fatal exception handling, page fault vector 14 can be demand-resolved.

If unresolved and saved CS indicates user mode, `panic_user_fault`:
- records PID/CR2/RIP;
- destroys the process;
- logs diagnostics;
- sets exit code -11;
- redirects the frame to kernel continuation.

Therefore invalid user memory does not automatically panic the kernel.

## Process states

The process layer defines READY plus block states for socket, join and IRQ.

The syscall file shown here does not by itself implement a POSIX blocking syscall scheduler. Subsystems can change process state through `proc_block`/`proc_unblock`.

Timer tick records that a slice is due, but user scheduler execution remains much smaller than a production preemptive SMP scheduler.

## ABI ownership rules

A useful syscall contract is not just register numbering.

Ownership rules include:
- user buffer remains user-owned; syscall makes a kernel copy where required;
- fd slot is owned by PID until close/destroy;
- process-owned pages are released at destroy;
- kernel-return state belongs to the current BSP user execution;
- filesystem lower layer receives kernel buffers.

These rules determine whether an error path leaks or accesses stale memory.

## Security implications

The DPL-3 gate is intentionally narrow. User pointers receive explicit translation. File descriptors enforce PID ownership. Kernel and user selectors are separate. Page permissions remain enforced.

However, the syscall API is intentionally small and not POSIX-compatible. It has global return state, small fd table and direct graphics/input operations.

Security review should focus on each implemented contract rather than assuming semantics from Linux or another OS.

## Performance

`int 0x80` and byte-oriented user copies favor implementation clarity over peak syscall throughput. File operations cap buffers at 512 bytes, so overhead is currently bounded.

A future higher-throughput ABI might use SYSCALL/SYSRET, larger vectored transfers and a richer handle table. Those optimizations must preserve ownership and validation.

## Validation

A native ABI test suite should exercise:
- every syscall number;
- unknown syscall;
- 0/80-byte write limits;
- 0/512-byte file limits;
- invalid user pointers and cross-page spans;
- fd exhaustion and ownership;
- close and process-destroy cleanup;
- normal exit return;
- invalid user fault containment;
- AP rejection;
- coordinate/input edge cases.

The tests should be tied to exact build revision because saved-frame behavior is part of the ABI.

## Current limitations

At most 31 user processes and six dynamically allocated file slots are available in this native layer. User execution is BSP-only. File descriptors store paths rather than general open-file objects. There is no fork/exec/wait POSIX model described here, no signals and no SYSCALL/SYSRET fast path.

These limits are explicit design state, not omissions to hide under a generic “system calls supported” claim.

## Source map

Process identity/address spaces are in `proc.c`/`proc.h`. Entry is `user_enter.c`. The gate/dispatcher are `idt.c`, `irq.c` and `syscall.c`/`syscall.h`. ELF loading is in `elf.c`. File and input/graphics calls cross into their subsystem sources. The Source Atlas publishes all referenced source files without truncation.
