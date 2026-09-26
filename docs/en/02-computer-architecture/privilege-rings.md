---
id: privilege-rings
lang: en
type: technical-chapter
volume: 02-computer-architecture
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/gdt.c
  - kernel/metal/gdt.h
  - kernel/metal/idt.c
  - kernel/metal/idt_stubs.asm
  - kernel/metal/irq.c
  - kernel/metal/irq.h
  - kernel/metal/user_enter.c
  - kernel/metal/syscall.c
  - kernel/metal/proc.c
  - chrisvm/cpu/common/exceptions.c
  - chrisvm/cpu/emulator/execute.c
  - chrisvm/cpu/emulator/mmu.c
symbols:
  - gdt_init
  - idt_set_user_gate
  - enter_user
  - irq_dispatch
  - syscall_dispatch
  - user_span_ok
  - user_copy
  - panic_user_fault
  - deliver_frame
  - chris_seg_load_cs
depends_on:
  - x86-64-memory-privilege
related:
  - kernel-model
  - processes-syscalls
  - idt-exceptions
---

# Privilege rings, controlled entry and protection boundaries

## Privilege is an execution property

An operating system must let untrusted code calculate values without granting it arbitrary control over memory translation, interrupt delivery or devices. Privilege mechanisms separate those authorities. x86 labels execution privilege levels zero through three, with smaller numbers representing greater privilege. The ChrisOS paths examined here use kernel and user roles conventionally associated with zero and three. A privilege number is not a source-language type or a property conferred by naming a function `kernel`.

The current privilege level, CPL, describes the executing context. Descriptor privilege level, DPL, belongs to a descriptor or gate. Requestor privilege level, RPL, occupies the low two bits of a selector. Their comparisons depend on the operation. Reducing every rule to “smaller number wins” is insufficient: accessing a data segment, invoking an interrupt gate and returning to less privileged code have different checks and state transitions.

Paging supplies another part of the boundary. A user instruction cannot access a supervisor mapping merely because its address is numerically known. Conversely, entering the kernel does not prove that an address supplied by a user is safe to dereference. The memory chapter explains permissions along page-table paths. This chapter follows controlled entry and the software checks that remain necessary after hardware has selected an authorized handler.

## Selectors are references, not raw code addresses

A segment selector contains a descriptor index, a table-selection bit and RPL. With the GDT selected, shifting the selector right by three obtains an eight-byte slot index. ChrisOS defines kernel code at `0x08`, kernel data at `0x10`, user data at `0x18`, user code at `0x20` and TSS at `0x28`. The user-entry function ORs three into the user selectors, producing `0x23` for CS and `0x1b` for SS.

| Selector component | Purpose | Example |
|---|---|---|
| Index | Locate descriptor slot | `0x20 >> 3` selects slot four |
| Table bit | Choose GDT or LDT | Zero in these configured selectors |
| RPL | Requested privilege context | Low bits three on user selectors |

The GDT descriptor then supplies access attributes. Long-mode code still depends on valid code descriptors even though ordinary address calculation uses a mostly flat address space. The TSS descriptor spans two slots because its base address needs additional high bits. `install_tss_descriptor` constructs those fields explicitly; confusing the second slot with another independent segment would corrupt the reference to the TSS.

`gdt_init` establishes the table and a 104-byte TSS, sets the ring-zero stack pointer and loads TR. The TSS I/O-map offset is placed beyond its structure. These are configuration facts, not a proof that every I/O instruction is authorized correctly in every backend. Host execution, emulated execution and a future hardware-virtualized backend need their own enforcement paths for the same architectural rule.

## Entering user mode through an explicit return frame

`enter_user` constructs a frame containing SS, user RSP, RFLAGS, CS and user RIP, then executes IRETQ. The push order makes RIP the first item consumed from the stack. RFLAGS is initialized to `0x202`, which includes the architecturally fixed bit one and IF. This selects the intended user entry point and stack through a controlled architectural transition rather than a normal C call.

The function also records a kernel return address using `__builtin_return_address(0)` through `syscall_set_kernel_return`. That value belongs to this implementation's return-to-kernel scheme. It is not a general saved process context: it does not capture every callee-saved register, stack lifetime, address space or scheduler state. The caller must already have arranged valid user code and stack mappings. A frame containing plausible integers cannot substitute for those prerequisites.

The TSS stack pointer matters on entry from less privileged code to kernel code. The processor must not continue placing privileged handler state on an untrusted user stack. Separate emergency stacks through IST can address other failure scenarios, but the configured IDT gates in this source use IST zero. The documentation must not infer an emergency stack merely because the TSS structure reserves IST fields.

## Gate authority and the system-call route

![Controlled entry, pointer validation and return](../../assets/diagrams/privilege-boundary.svg)

The diagram separates the intended architectural boundary from the software validation path. The emulator limitations described below mean it must not be read as a claim that every gate check already works in ChrisCPU.

An IDT gate combines a target offset, target code selector, type, presence and DPL. ChrisOS builds 256 gates, ordinarily with attributes `0x8e`. `syscall_init` changes vector `0x80` to the user-callable form through `idt_set_user_gate`, whose attributes are `0xee`. The change permits software invocation from user privilege while still selecting the kernel code descriptor as the destination.

Gate DPL is not a request to run the handler at that DPL. It restricts who can invoke the gate using the relevant software instruction. An external interrupt has a different origin from a user-issued INT, and a page fault is a synchronous architectural event rather than a user-selected service number. The CPU's event-class rules and the kernel's dispatch decisions must therefore remain separate.

The route in the inspected kernel is interrupt vector `0x80`, not an inference of SYSCALL support from an MSR name. Assembly stubs normalize vector/error information, save general registers and call `irq_dispatch`. That function recognizes vector `0x80` before generic interrupt handling and calls `syscall_dispatch`. The dispatcher reads the service number from saved RAX and arguments from the saved register frame.

## Frame layout is an ABI between assembly and C

The C `irq_frame` starts with R15 and continues through the saved general registers to RAX, followed by vector, error, RIP, CS and RFLAGS. The assembly comment records vector at offset 120, error at 128 and RIP at 136. Those offsets follow fifteen eight-byte general-register slots. Changing push order without changing the C structure would reinterpret a saved value as another register or control field, even if both files compiled.

The stubs clear DF before entering C, save floating-point/SIMD state with FXSAVE into aligned storage, align the stack for the C call, then restore state. These operations establish calling-environment conditions beyond preserving RAX. The structure does not list every possible processor-pushed tail field; its declared prefix must be interpreted together with the assembly and transition context. A C structure declaration alone cannot prove the full frame shape for every event.

A source review also finds repeated `frame->rip += 2` in ordinary system-call return paths. INT normally saves a return address after its instruction, and ChrisCPU's INT handler explicitly advances RIP before raising the event. The inspected stubs and dispatch route do not visibly subtract two beforehand. This discrepancy requires a targeted execution test of return addresses; it is not resolved by assuming all saved RIP values point at the trapping opcode. No such guest execution test is claimed in this chapter.

## Validating spans without integer wraparound

A kernel service receiving a pointer and length must validate a span, not only its first byte. If it checked `address + length <= limit` using arithmetic that can wrap, a large input could evade the intended bound. `user_span_ok` instead compares length against `limit - address` after checking the address is below the limit. The subtraction is safe because the preceding check establishes its ordering precondition.

The helper first accepts a zero-length span. For nonzero length, it rejects addresses at or above `0x0000800000000000`, rejects spans exceeding that boundary, checks the configured user interval and rejects spans longer than the remaining interval. The configured interval initially covers `0x400000` through `0x500000`, with the upper endpoint excluded. This policy is narrower than the entire canonical user half and can be changed through `syscall_set_user_map`.

Bounds are only one layer. `user_copy` obtains the current process CR3 and walks each page through `mm_translate`. It requires present and user leaf flags, and additionally requires writable for a copy to user memory. It accesses physical backing through the higher-half direct mapping rather than directly dereferencing the supplied user virtual address. Missing mappings return an error instead of intentionally taking a ring-zero page fault on the user pointer.

## Copying, ownership and concurrency

The copy loop chooses each chunk as the lesser of bytes remaining and bytes to the page boundary. It then copies byte by byte and repeats translation for the next page. For n bytes spanning p pages, the local work is O(n + p × h), where h is the bounded table-walk depth, excluding other contention or device costs. Its temporary storage is constant; the caller owns the kernel buffer and supplies its capacity through the service's own validation.

Checks and copies are separate operations. The helper does not visibly pin the translated frame for the whole operation or hold a page-table lock through each byte copy. Safety against concurrent unmapping therefore depends on broader execution and ownership constraints. The process-switch path explicitly confines user processes to the bootstrap processor, and the syscall dispatcher rejects execution on another CPU. Those restrictions narrow the concurrency model but should not be promoted into a proof that arbitrary concurrent mapping mutation is safe.

Partial progress also matters. If a later page fails translation, earlier chunks have already been copied. A return value of error does not imply that the destination buffer is unchanged. Services that require all-or-nothing publication need their own staging or rollback contract. The current helper's behavior is analogous to the chunked memory-access concern documented for the emulator, but the two functions operate in different address domains and must be reviewed independently.

## Service-specific authority and fault containment

For SYS_WRITE, the dispatcher accepts descriptor one and lengths up to 80 bytes, copies into an 81-byte local buffer and passes it to the terminator helper before serial output. The extra byte accommodates the terminator at the maximum accepted length. A pointer check does not replace this capacity check: memory can be valid while a destination buffer is too small. Error paths set saved RAX to −1; successful output returns the byte count in RAX.

File-like handles use a small `UFile` table containing used state, owner process and path. `ufile_owned` verifies descriptor range, active state and owner identity before access. This illustrates object authority beyond rings: two processes can execute at the same CPL but must not automatically use each other's handles. Closing an owner's handles scans the bounded table, so its cost is bounded by the table capacity rather than by arbitrary filesystem size.

On a page fault, `irq_dispatch` first asks `proc_fault_demand` whether the current process can resolve the fault. Otherwise it examines saved CS privilege bits and directs user-origin faults to `panic_user_fault`. That path records the fault, destroys a positive process identifier, logs diagnostic context and arranges return to the kernel. A remaining kernel exception takes the kernel panic route. This describes the dispatch order; it does not prove that every malformed user request is safely contained.

## Emulated protection is a separate implementation obligation

`deliver_frame` in ChrisCPU reads a sixteen-byte gate, checks presence and supported gate types, rejects nonzero IST, loads the target code selector and pushes a frame using the current stack. The inspected path does not implement the kernel's entire hardware privilege-transition expectation: no TSS-selected stack switch or gate-DPL comparison is visible there. `chris_seg_load_cs` checks selected descriptor properties but does not update the model's CPL field. IRETQ similarly loads selectors without visibly reconciling CPL.

This matters because the MMU decides whether an access is user from `arch.cpl`, not merely from the low bits of the stored CS selector. A selector that appears to name ring three does not by itself prove user permission enforcement in this backend. MOVCR, MSR and CLI/STI paths likewise need explicit architectural privilege checks. These observations identify implementation gaps; the kernel's use of the correct machine instruction does not repair a missing emulator check.

Validation must therefore cover both directions: authorized transitions should reach the intended handler and return state; unauthorized operations should fault without granting authority or corrupting preserved state. Existing arithmetic, decode and MMU probes provide narrower evidence and do not execute the full ring transition. Required future guest cases include user writes to supervisor pages, privileged-instruction rejection, gate-DPL rejection, stack switching, saved return RIP and restoration of CPL. Until those execute successfully, this chapter documents source behavior and open obligations rather than certifying isolation.
