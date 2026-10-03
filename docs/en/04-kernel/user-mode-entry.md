---
id: user-mode-entry
lang: en
type: concept
volume: 04-kernel
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/user_enter.c
  - kernel/metal/user_enter.h
  - kernel/metal/gdt.c
  - kernel/metal/gdt.h
  - kernel/metal/proc.c
  - kernel/metal/proc.h
  - kernel/metal/syscall.c
  - kernel/metal/syscall.h
  - kernel/metal/idt.c
  - kernel/metal/irq.c
  - kernel/metal/irq.h
symbols:
  - enter_user
  - syscall_set_kernel_return
  - syscall_return_to_kernel
  - proc_switch
  - syscall_init
depends_on:
  - gdt-tss
  - virtual-memory
related:
  - user-copy
  - process-lifecycle
  - idt-exceptions
---

# User-mode entry and controlled return to ring 0

## Scope

Executing application code at CPL 3 requires more than jumping to a lower-half address. The processor must enter with user selectors, a valid user stack, page tables whose mappings carry the User/Supervisor permission, an interrupt/syscall path back into the kernel, and a kernel-owned recovery path for exit or fault.

ChrisOS performs the actual privilege drop through `iretq` in `enter_user`. The surrounding process and syscall code establish the address space, track the current CR3, expose a DPL-3 vector `0x80`, validate memory crossing the boundary and allow exit/fault handling to rewrite the saved interrupt frame back to a kernel return address.

This chapter documents the ring transition itself and its control-flow invariants. Process allocation and syscall buffer-copy semantics have their own chapters.

## CPL, selectors and page permissions

x86-64 protection combines multiple mechanisms. The low two bits of CS determine the Current Privilege Level. The GDT descriptor selected by CS has a Descriptor Privilege Level. The page-table U/S bit determines whether a translation is accessible from user mode.

A valid user execution context therefore needs both:
- selectors that are legal for ring 3;
- page mappings marked user-accessible.

ChrisOS defines user data selector `0x18` and user code selector `0x20`. `enter_user` ORs both with 3 to make selectors with RPL 3.

This does not itself mark any virtual address as user-accessible. That is done through the process memory mapping layer, which passes `MM_USER` when creating user mappings.

## Process address-space context

Each process slot contains a CR3 value. `proc_create` obtains it with `mm_clone_kernel_space`, then commits an initial user stack page.

`proc_switch(pid)` checks that the caller is the BSP. If an AP attempts a process switch, the kernel panics. For a valid used process, it updates `g_current` and calls `mm_switch(cr3)`.

Thus the current privilege transition is built on an already-selected process address space. `enter_user` does not select CR3; it assumes the caller has arranged the correct mappings and entry/stack addresses.

This separation is useful: address-space ownership stays in process/memory code, while `enter_user` is a small architectural transition primitive.

## User virtual regions

The process header establishes fixed region bases used by current runtime paths:

| Region | Base |
|---|---:|
| VM | `0x02000000` |
| heap | `0x04000000` |
| framebuffer | `0x06000000` |
| stack | `0x07F00000` |
| library | `0x08000000` |

These constants are not a complete generic process ABI by themselves, but they define concrete ranges used by current ChrisOS allocation/demand-fault logic.

The stack region can demand-commit pages from `PROC_STACK_VIRT` through four pages. A valid user RSP passed to `enter_user` must point into a mapping suitable for user writes because ordinary call/stack operations will immediately use it.

## Preparing a return target

Immediately before the privilege transition, `enter_user` evaluates `__builtin_return_address(0)` and passes it to `syscall_set_kernel_return`.

This saves a ring-0 instruction pointer associated with the call site. The current syscall/fault mechanism later uses that global address when it wants to terminate user execution and resume kernel code.

This is not a general continuation object. It is a single global return location and therefore fits the current BSP-only user execution model. Concurrent independent user contexts on multiple CPUs would require per-task or per-CPU return state rather than one global `g_user_kernel_rip`.

## Constructing the `iretq` frame

`enter_user` computes:

```c
cs = GDT_USER_CODE | 3;
ss = GDT_USER_DATA | 3;
rflags = 0x202;
```

`0x202` sets the always-conventional reserved bit 1 and IF, so maskable interrupts are enabled after user mode begins.

The inline assembly pushes five values in the order required for a return across privilege levels:

```text
push SS_user
push RSP_user
push RFLAGS
push CS_user
push RIP_user
iretq
```

`iretq` pops RIP, CS and RFLAGS; because the return changes CPL from 0 to 3, it also consumes the saved RSP and SS to install the user stack.

The instruction performs privilege checks. This is not equivalent to manually writing CS or simply changing the low bits of an address.

## What the CPU validates

The target code selector must reference a present executable descriptor appropriate for user privilege. The stack selector must reference a valid writable data segment. The target addresses must be canonical. The page tables used when the CPU begins fetching at user RIP must permit user access.

If these contracts are inconsistent, the transition raises an exception such as #GP or #SS instead of entering the application.

After entry, ordinary instruction fetch/data access can still page fault if a legal process region is demand-mapped but not resident. The page-fault handler may commit such a page and retry the instruction.

## Kernel entry from user mode

ChrisOS exposes vector `0x80` by changing that IDT gate to DPL 3. User code can execute the software interrupt. The CPU transfers through the ring-0 code selector and the interrupt-entry path produces `irq_frame` for `irq_dispatch`.

The TSS/GDT infrastructure supplies trusted privileged stack state for a ring transition. This is why the GDT/TSS chapter is a prerequisite even though the process itself is primarily page-table based.

`irq_dispatch` recognizes vector `0x80` before ordinary IRQ handling and invokes `syscall_dispatch`.

## Syscall CPU restriction

`syscall_dispatch` checks `smp_current_cpu()`. If execution somehow enters the syscall path on a non-BSP CPU, it returns -1 and advances saved RIP by 2.

This mirrors `proc_switch`'s stronger BSP-only invariant. The reviewed architecture does not support migrating current user execution across APs.

The restriction simplifies global state such as current process and kernel return target but is an explicit scalability limitation.

## Returning normally after a syscall

Most syscall cases place a result into saved RAX, advance saved RIP by 2 bytes and return to the common interrupt stub. The stub restores registers and executes `iretq`.

The 2-byte increment corresponds to the `int imm8` instruction length for `int 0x80`. The saved RIP in this path is treated as pointing at the software-interrupt instruction rather than an already advanced architectural return in the conventions used by this system, so the dispatcher advances it explicitly.

This convention must remain consistent between user code generation, interrupt entry and syscall dispatch. Changing the syscall instruction mechanism would require revisiting it.

## Controlled return to the kernel

For `SYS_EXIT`, the kernel does not return to the next user instruction. `syscall_return_to_kernel` rewrites the saved frame:

- RIP becomes `g_user_kernel_rip`;
- CS becomes `GDT_KERNEL_CODE`;
- RFLAGS becomes `0x202`;
- `g_user_exited` is set.

When the assembly stub reaches `iretq`, it therefore returns into ring 0 rather than ring 3.

The stack shape deserves attention. A privilege-return frame can include user RSP/SS fields created on entry. The current handler changes the fields it uses for the return convention established by this kernel. Any later restructuring of stubs or process stacks must validate the exact hardware frame and cleanup behavior.

## Fault containment return

A user page fault that cannot be satisfied reaches `panic_user_fault`. Despite the historical function name, this path does not panic the kernel.

It records the process fault, destroys the process, logs diagnostic identity, sets exit code -11 and invokes the same controlled-return mechanism. The common stub then resumes kernel code.

This is an important protection boundary: a process fault is treated as process failure when the saved CS identifies user origin, while a ring-0 exception remains a system panic.

## Demand paging during user execution

Before terminating a user page fault, `irq_dispatch` calls `proc_fault_demand(pid, cr2)`. The function recognizes pages in current VM, stack, heap and framebuffer ranges.

If `proc_commit` successfully allocates a physical page, zeros it, maps it with user/write permissions and records ownership, the page-fault handler simply returns. The same saved RIP is retried.

This means user entry does not require every allowed process page to be resident in advance. It requires enough initial state—especially entry code and initial stack—to begin, while selected regions can grow lazily.

## Security of the transition

Several independent conditions prevent user code from retaining ring-0 privilege:

- user CS/SS selectors carry RPL 3 and point to DPL-3 descriptors;
- user pages are explicitly marked `MM_USER` rather than inheriting unrestricted supervisor mappings;
- only the syscall IDT gate is intentionally set to DPL 3;
- privileged operations such as CR3 changes, `lgdt` and device I/O remain unavailable at CPL 3 unless explicitly mediated;
- syscall pointers are not trusted merely because they are canonical; the copy layer translates and validates page flags.

A privilege transition is therefore a composition of descriptor, page-table and syscall-interface policies.

## Global state constraints

`g_user_kernel_rip`, `g_user_exited`, `g_user_exit_code` and `g_current` are global state in the current source. That is compatible with the rule that user process switching and syscalls execute on the BSP.

It is not sufficient for simultaneous independent userspace execution across CPUs. A future SMP userspace model should place return/exit/current-task state in per-thread or per-CPU structures and make process lifetime synchronization safe across cores.

## Interrupt enable semantics

The initial user RFLAGS is `0x202`, so IF is set. Hardware IRQs can therefore preempt user execution once controller masks and CPU state permit.

On interrupt entry to an interrupt gate, the processor clears IF for the handler. The common stub/`iretq` restore the saved flags on return. Kernel code therefore does not need to manually re-enable interrupts simply to resume the prior user IF state.

NMI remains independently deliverable.

## Stack safety

The user stack cannot be used as trusted kernel stack state during privileged handling. The TSS provides ring-0 stack information for privilege transitions.

Conversely, `enter_user` deliberately installs the provided user RSP. The caller must not pass a kernel pointer or an unmapped/non-user stack and expect `iretq` to validate application semantics. Architectural selector checks and page faults will enforce hardware constraints, but logical stack-region validity belongs to the process loader/runtime.

The current TSS has one fixed `rsp0` rather than a per-user-thread kernel stack. This matches the current single-BSP user execution model.

## Failure modes

Entry can fail because of invalid selectors, noncanonical RIP/RSP, absent target mappings, supervisor-only page permissions, invalid stack descriptor state or corrupted GDT/TSS state.

After entry, a process can fault on ordinary demand pages, illegal addresses or privileged instructions. Demand faults may be recovered; invalid user faults terminate the process; kernel-origin faults panic.

A corrupted global kernel return RIP would make exit/fault containment return to the wrong ring-0 location. This global is therefore part of control-flow integrity even though it is a small variable.

## Performance

`iretq`-based transition and `int 0x80` are simple and architecturally clear but are not the lowest-overhead syscall mechanism available on x86-64. SYSCALL/SYSRET can reduce transition cost when configured correctly.

ChrisOS currently prioritizes an explicit gate/frame path that integrates with the same dispatcher machinery. Performance claims should be measured before replacing it, because system-call overhead may not dominate current workloads.

Demand paging shifts allocation cost from process setup to first access. This reduces eager memory commitment but creates page-fault latency on first touch.

## Validation

A complete gate should:
- enter ring 3 and verify CPL;
- perform each supported syscall;
- confirm interrupt delivery while user IF is set;
- fault a demand-mapped page and verify transparent retry;
- trigger an invalid user access and verify process-only termination;
- exit normally and verify return to the correct kernel continuation;
- verify that supervisor-only pages are inaccessible;
- reject non-BSP process/syscall execution according to current policy.

The reviewed source establishes the mechanism, but runtime tests establish that descriptor, paging and frame conventions agree in practice.

## Current limitations

User execution is BSP-only. The kernel return target is global. Initial transition uses a fixed TSS ring-0 stack. The syscall mechanism is `int 0x80` rather than SYSCALL/SYSRET. The process model has fixed virtual-region constants and limited process/page slot counts.

These are implementation boundaries, not properties of user mode in general.

## Source map

`kernel/metal/user_enter.c` performs the privilege drop. GDT/TSS definitions are in `kernel/metal/gdt.c`/`gdt.h`. Process CR3 and user-region ownership are in `kernel/metal/proc.c`/`proc.h`. The ring-0 return convention and vector 0x80 dispatch are in `kernel/metal/syscall.c`/`syscall.h`; `kernel/metal/idt.c` supplies the DPL-3 gate change. Every source is mirrored in full by the Source Atlas at revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.
