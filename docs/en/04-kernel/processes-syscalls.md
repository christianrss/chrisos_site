---
id: processes-syscalls
lang: en
type: concept
volume: 04-kernel
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/proc.c
  - kernel/metal/proc.h
  - kernel/metal/syscall.c
  - kernel/metal/syscall.h
  - kernel/metal/elf.c
  - kernel/metal/user_enter.c
  - kernel/metal/idt.c
  - kernel/metal/irq.c
  - kernel/metal/irq.h
  - kernel/fs/fs.c
  - kernel/gfx/input.c
  - tools/test_sys_write.c
symbols:
  - proc_create
  - proc_destroy
  - proc_switch
  - syscall_init
  - syscall_dispatch
  - syscall_write_term
  - user_span_ok
  - user_copy
  - enter_user
  - panic_user_fault
  - proc_commit
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

## Concrete process and syscall state

The implementation uses fixed-size kernel-resident tables rather than dynamically allocated process-control and descriptor objects.

The process table contains `PROC_MAX = 32` entries. Each private `Proc` record contains `used`, `alive`, scheduler `state`, `cr3`, virtual-memory accounting, heap break, framebuffer-page count, a 24-byte name and an array of `PROC_PAGES = 288` owned-page records. Each owned-page record stores one virtual and one physical address. This representation makes teardown deterministic: the kernel can walk the recorded pages and free frames without reconstructing ownership from page tables.

The syscall layer separately owns a static `UFile g_ufile[8]` table. Each entry contains only `used`, owner PID and a 128-byte path. It does not contain a file offset, access flags, reference count or underlying filesystem object. Consequently, the native descriptor ABI is a small PID-scoped path-handle table, not a POSIX open-file-description model.

Several user-execution variables are also global: `g_user_exited`, `g_user_exit_code`, `g_user_kernel_rip` and the accepted user-copy window. Their global nature is one reason native user execution is explicitly restricted to the BSP.

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

## Dispatch state machine

The complete software path for a normal native syscall is:

1. ring-3 code executes `int 0x80`;
2. the DPL-3 IDT gate transfers control through the common ISR stub;
3. the stub materializes register state as `struct irq_frame`;
4. `irq_dispatch` recognizes vector `0x80` before generic exception/IRQ handling;
5. `syscall_dispatch` reads the saved RAX number and saved argument registers;
6. the selected operation validates scalar limits, descriptor ownership and/or user memory;
7. the result is written back to saved RAX;
8. non-exit paths advance the saved RIP by two bytes;
9. the common interrupt return restores execution.

The `irq_frame` layout therefore forms part of the implementation ABI between assembly entry code and C. The dispatcher relies specifically on saved `rax`, `rdi`, `rsi`, `rdx`, `rip`, `cs` and `rflags`. Changing the assembly save order without changing the C structure would corrupt syscall interpretation even if the public syscall numbers stayed unchanged.

`SYS_EXIT` is the deliberate exception to step 8. It rewrites the saved control state so that the common return enters a kernel continuation instead of advancing to the next user instruction.

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

## User-copy algorithm and window

The default accepted copy window is `[0x400000, 0x500000)`; callers may replace it through `syscall_set_user_map`. `user_span_ok` first handles the zero-length case, then rejects upper-half addresses, integer wrap across the canonical lower-half limit, a start outside the configured window, or a length extending past the configured high bound.

For a non-empty span, `user_copy` obtains the current PID's CR3 and iterates until every requested byte has been transferred. For each chunk it translates the current user virtual address with `mm_translate`, requires `MM_PRESENT | MM_USER`, additionally requires `MM_WRITE` for kernel-to-user copies, limits the chunk to the remainder of the current 4 KiB page, converts the physical address through the HHDM and copies the bytes.

This design intentionally avoids dereferencing an untrusted user virtual pointer while the kernel is running under its own assumptions. A missing or disallowed page becomes a syscall error rather than a ring-0 page fault generated by a direct C dereference.

The algorithm is page-aware but the final transfer loop is byte-oriented. For a span of `n` bytes touching `p` pages, the copy performs `p` translations and `n` byte assignments, giving a cost proportional to `O(p * T_translate + n)`. Because syscall payload limits are currently small, simplicity dominates throughput.

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

## Descriptor allocation algorithm

Descriptor allocation is a linear scan from fd 2 through fd 7. With six allocatable slots the worst-case search is six entries, so the practical cost is bounded even though the algorithm is formally `O(UFILE_MAX)`. Ownership lookup is constant-index access followed by PID comparison.

`syscall_close_owner(pid)` performs another bounded linear scan over fd 2–7 during process teardown. This is important for PID reuse: a destroyed process cannot leave a stale file slot that a later process with the same numeric PID would accidentally inherit.

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

## Boundary behavior of file syscalls

Several details are part of the current observable behavior and should be preserved or deliberately versioned:

- `FOPEN` asks `copy_from_user` for exactly 127 bytes before searching for NUL. Therefore the entire 127-byte source span must be valid inside the configured user window even when the logical pathname is shorter.
- `FREAD` rejects requests above 512 bytes, reads into a 512-byte kernel buffer and copies exactly the filesystem's returned byte count to user memory.
- `FWRITE` copies the complete requested payload before descriptor validation. For fd 1 it writes through `serial_puts`; when `n == 512`, byte 511 is replaced by NUL and the function still reports 512. This is a concrete edge semantic, not a general binary-safe write contract.
- regular descriptor writes return the integer result of `fs_write` cast through RAX; unlike many other failures, the dispatcher does not normalize every negative filesystem return to a single pre-check branch.
- `FCLOSE` returns zero whether or not the supplied descriptor was actually owned and closed.

These behaviors are reasons to test the native ABI against ChrisOS itself rather than assuming Linux/POSIX semantics from familiar syscall names.

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

## Fault recovery versus syscall-copy failure

There are two distinct invalid-memory paths. A syscall copy never intentionally faults in user memory: translation failure or permission failure returns -1 to the dispatcher. By contrast, a CPU page fault arriving through vector 14 first calls `proc_fault_demand`. That routine may commit a page for configured VM, stack, heap or framebuffer regions. Only when demand handling fails and the saved CS indicates user mode does `panic_user_fault` record the fault, destroy the process and redirect control to the kernel continuation with exit code -11.

The distinction matters operationally. "Invalid pointer passed to a syscall" and "user instruction triggered a page fault" do not necessarily traverse the same recovery mechanism, even if both ultimately represent invalid user access.

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

## Concurrency and global-state constraints

The current native execution model is not re-entrant across CPUs. `g_current` is global rather than per-CPU, the user-return RIP and exit status are global, and the file table uses PID ownership without a lock in this layer. `proc_switch` panics when invoked off the BSP, while `syscall_dispatch` rejects a syscall observed on a nonzero CPU.

That restriction is an implementation invariant, not merely a performance limitation. Making native processes SMP-capable would require at least per-CPU current-process state, a defined ownership model for return continuations, synchronization for shared tables, scheduler rules for CR3 residency, and a decision about how process destruction coordinates with syscalls in flight.

## Algorithmic cost summary

| Operation | Current representation | Cost characteristic |
|---|---|---|
| PID allocation | scan process slots 1–31 | `O(PROC_MAX)`, bounded by 31 candidates |
| descriptor allocation | scan fd 2–7 | `O(UFILE_MAX)`, bounded by 6 candidates |
| descriptor ownership check | indexed slot + PID comparison | `O(1)` |
| owner descriptor cleanup | scan fd 2–7 | `O(UFILE_MAX)` |
| user copy | page translation plus byte copy | `O(p * T_translate + n)` |
| owned-page lookup in `proc_commit` | linear `ProcPage[]` scan | `O(npages)` |
| process teardown | release owned pages + address-space/resource cleanup | at least `O(npages + UFILE_MAX)` plus lower-layer costs |

The fixed caps make these algorithms acceptable for the present research system, but the representations would become scaling constraints before reaching workstation-scale process counts.

## Performance

`int 0x80` and byte-oriented user copies favor implementation clarity over peak syscall throughput. File operations cap buffers at 512 bytes, so overhead is currently bounded.

A future higher-throughput ABI might use SYSCALL/SYSRET, larger vectored transfers and a richer handle table. Those optimizations must preserve ownership and validation.

## Executable evidence

At revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, `tools/test_sys_write.c` is a focused host test for one boundary of this ABI. It verifies that an 80-byte `SYS_WRITE` payload is accepted only when the destination buffer has room for the required terminating byte, that capacity 80 is rejected for an 80-byte payload, and that payload length 81 is rejected.

That test is useful evidence for `syscall_write_term`; it is not evidence that descriptor ownership, user-copy translation, process exit, fault containment or the complete `int 0x80` path work in a booted system. Those require separate host, QEMU or hardware evidence.

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

## Revision reconciliation

This page was reconciled from `da3df29cb397932c43d32373871fb9380e688ade` to `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. The intervening ChrisOS commits changed repository documentation, contribution files and related project metadata but did not modify the implementation sources listed in this page's process/syscall contract. The reviewed revision can therefore advance without silently attributing new runtime behavior.

## Source map

Process identity/address spaces are in `proc.c`/`proc.h`. Entry is `user_enter.c`. The gate/dispatcher are `idt.c`, `irq.c` and `syscall.c`/`syscall.h`. ELF loading is in `elf.c`. File and input/graphics calls cross into their subsystem sources. The Source Atlas publishes all referenced source files without truncation.
