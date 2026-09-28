---
id: idt-exceptions
lang: en
type: concept
volume: 04-kernel
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/idt.c
  - kernel/metal/idt.h
  - kernel/metal/idt_stubs.asm
  - kernel/metal/irq.c
  - kernel/metal/irq.h
  - kernel/metal/panic.c
  - kernel/metal/syscall.c
symbols:
  - idt_init
  - idt_load
  - idt_set_user_gate
  - irq_dispatch
  - panic_exception
  - panic_user_fault
depends_on:
  - gdt-tss
  - x86-64-memory-privilege
related:
  - interrupts-smp
  - page-faults
  - processes-syscalls
---

# IDT, exception entry and interrupt frames

## Scope

The Interrupt Descriptor Table is the x86-64 dispatch structure that maps an interrupt vector to privileged entry metadata. It is used for processor exceptions, hardware interrupt vectors, software-generated interrupts and inter-processor interrupt vectors. A correct IDT is only the first part of the entry path: assembly stubs must normalize the hardware frame, preserve register state, maintain ABI stack alignment, preserve SIMD/FPU state when necessary, call C code with a stable representation and restore the interrupted context before `iretq`.

ChrisOS implements all of these stages explicitly. This chapter documents the exact gate representation, the 256-entry initialization policy, the assembly frame created by `idt_stubs.asm`, exception handling in `irq_dispatch`, page-fault special handling, the vector `0x80` syscall gate and the dedicated NMI path used by TLB-shootdown containment.

## Vector space and hardware contract

x86 defines 256 interrupt vectors. Vectors 0–31 are architecturally reserved for processor exceptions and interrupts such as divide error, invalid opcode, general protection, page fault and NMI. External interrupt controllers normally deliver hardware IRQs through configurable vectors above this range. Software can invoke a gate using instructions such as `int n` when descriptor privilege rules permit it.

An IDT entry in 64-bit mode is 16 bytes. ChrisOS models it with packed `struct idt_gate`:

| Field | Function |
|---|---|
| `offset_low` | handler address bits 0–15 |
| `selector` | target code-segment selector |
| `ist` | optional TSS IST index |
| `attributes` | type, DPL and Present bits |
| `offset_middle` | handler bits 16–31 |
| `offset_high` | handler bits 32–63 |
| `reserved` | must remain zero |

`idt_init` has a compile-time assertion that the structure is 16 bytes. Every gate uses `GDT_KERNEL_CODE` as target selector and currently uses IST index 0.

## Gate attributes

The default attributes are `0x8e`. This denotes a present 64-bit interrupt gate at DPL 0. Because the DPL is zero, ring-3 software cannot invoke arbitrary exception/IRQ vectors using `int` merely because those vectors exist in the IDT.

`idt_set_user_gate` uses `0xee`. The difference is DPL 3. ChrisOS applies this to vector `0x80` during `syscall_init`, making the software interrupt intentionally callable from user mode while still transferring execution to the ring-0 code selector.

This distinction is part of the syscall attack surface. Setting all gates to DPL 3 would allow user code to enter arbitrary kernel handlers with frames they were not designed to accept.

## Building all 256 gates

`idt_init` iterates through all 256 vectors and initially points every vector to the corresponding entry in `isr_stub_table`. Vector 2 is then replaced with `nmi_entry`. The table is loaded with `lidt` through a packed pointer containing `sizeof(idt)-1` and the linear address of the static table.

The complete initialization rule is therefore simple and deterministic:

```text
for vector = 0..255:
    IDT[vector] -> isr_stub_table[vector], interrupt gate, DPL0
IDT[2] -> nmi_entry
lidt IDTR
```

Later, `syscall_init` changes the attributes for vector 0x80 without changing its stub target.

## Exceptions with and without hardware error codes

Not all exceptions push the same information before transferring control. Some exceptions push an error code supplied by hardware; others do not. A common C dispatcher is easier to reason about if the stack shape is identical for every vector.

`idt_stubs.asm` generates 256 entry labels with NASM macros. For vectors where hardware already pushes an error code—8, 10, 11, 12, 13, 14, 17, 21, 29 and 30—the stub pushes only the vector number. Every other stub pushes a synthetic zero error code and then the vector number.

After that normalization, every path jumps to `isr_common`. The dispatcher can therefore address `frame->vector` and `frame->error` at fixed offsets independent of the exception class.

## Register preservation and `irq_frame`

`isr_common` clears the direction flag with `cld`. C code generally assumes forward string operations; inheriting DF=1 from interrupted code would violate that expectation.

The stub then pushes general-purpose registers. The corresponding C structure is `struct irq_frame` in `irq.h`:

```text
r15 r14 r13 r12 r11 r10 r9 r8
rbp rdi rsi rdx rcx rbx rax
vector error rip cs rflags
```

The comment in assembly states that the vector is at offset +120 from the frame pointer, error at +128 and RIP at +136. The C structure ordering mirrors the pushes so `irq_dispatch(struct irq_frame *frame)` can inspect and modify the saved context directly.

When an interrupt crosses privilege levels, the CPU also creates additional stack state such as old RSP and SS below the architectural frame. The current C structure exposes the common fields used by this kernel; code must not assume that every entry source has identical hardware words beyond the declared structure.

## Preserving SIMD/FPU state

Calling C from an interrupt handler without preserving extended processor state can corrupt an interrupted computation. ChrisOS reserves 528 bytes, aligns an address to 16 bytes and executes `fxsave` before entering `irq_dispatch`. After the C handler returns, `fxrstor` restores that saved state.

The pointer to the aligned FXSAVE area is stored in temporary stack storage associated with the frame. The stub also aligns RSP before the C call so the compiler receives a valid ABI stack alignment.

This is an important difference between a demonstration stub and a usable interrupt entry path. Preserving only integer registers is insufficient once kernel or interrupted code can use x87/SSE architectural state.

## Returning from the handler

After `irq_dispatch` returns, the stub restores the extended state, resets RSP to the general-register frame, pops registers in reverse order, removes the normalized vector and error slots, then executes `iretq`.

Because the dispatcher receives a pointer to the saved frame, it may intentionally modify fields before return. ChrisOS uses this property when a user process exits or faults: the syscall/fault path can rewrite RIP, CS and RFLAGS so control resumes in a kernel return location rather than returning to the dead user context.

## Exception dispatch policy

`irq_dispatch` first recognizes special software and architectural vectors:

1. vector `0x80` enters `syscall_dispatch`;
2. vector 14 reads CR2 and asks `proc_fault_demand` whether a missing user page can be materialized;
3. if a page fault remains unresolved and the saved CS indicates nonzero CPL, `panic_user_fault` contains the fault to the user process;
4. any remaining vector below 32 goes to `panic_exception`.

This ordering is deliberate. Demand paging must run before treating a valid lazy mapping as a fatal user error. User-mode faults must be separated from kernel faults so a bad process does not automatically halt the entire system. Kernel exceptions remain fatal in the current implementation.

## Page-fault path

For vector 14, CR2 carries the linear address that caused the page fault. `irq_dispatch` reads it directly. `proc_fault_demand` recognizes process-managed VM, stack, heap and framebuffer ranges and may allocate/map the missing page. If it succeeds, the handler returns without modifying the saved instruction pointer; `iretq` retries the interrupted instruction with the new mapping present.

If demand allocation does not apply, the saved CS low two bits distinguish a user-origin fault. `panic_user_fault` records fault metadata, destroys the process, logs RIP, CR2, error code, CPU and build identity, sets exit code -11 and rewrites the saved frame for a controlled return to kernel code.

If the fault originated in ring 0, `panic_exception` logs vector, error, RIP and CR2 plus kernel identity and halts.

## NMI path

Vector 2 does not use the normal 256-stub path. `nmi_entry` preserves a smaller register set, aligns RSP and calls `mm_tlb_nmi_stop`. The comments document why the NMI runs on the interrupted stack: `smp_current_cpu` relies on AP stack identity.

The function return determines whether the processor returns or halts. An AP fenced during TLB-shootdown recovery may disable interrupts and halt forever. The BSP must return; an earlier design that halted it froze the desktop. This NMI is therefore not a general-purpose NMI diagnostics framework. It is a targeted containment path for the current memory/SMP design.

The use of NMI matters because IF does not block NMI delivery. It provides a stronger stop mechanism when an AP does not service an ordinary IPI during a TLB synchronization operation.

## Hardware IRQ and high-vector behavior

After exception handling, vector `0xF0` is recognized as the TLB-shootdown IPI. The handler polls the TLB protocol and sends LAPIC EOI before returning.

Vectors at or above 48 that are not handled specially return without passing through the legacy PIC IRQ calculation. The PIC-mapped hardware range begins at 32. Vectors 32–47 map to IRQ 0–15.

This layout is tied to `pic_init`, which remaps PIC1 to `0x20` and PIC2 to `0x28`.

## Stack and reentrancy constraints

Interrupt entry consumes the currently active privileged stack unless a privilege transition or IST selection changes it. Because current IDT entries set `ist=0`, kernel-origin exceptions remain on the current kernel stack, and the NMI path explicitly remains on the interrupted stack.

Nested interrupts, NMIs and faults can therefore consume additional stack depth. The linker reserves a 1 MiB bootstrap/kernel stack, but stack size alone does not solve corrupted-stack recovery. Dedicated IST configuration would be required to provide an independent emergency stack for selected exceptions.

The dispatcher also calls subsystems that have their own locking and CPU-context restrictions. Interrupt-safe code must avoid acquiring locks in an ordering that can deadlock against interrupted code holding the same lock. Those subsystem-specific rules are documented with their locks and drivers.

## Security properties

The IDT is kernel-owned static memory and loaded with a privileged instruction. Gate DPL controls software invocation, not the origin of hardware exceptions. The DPL 3 permission is deliberately limited to vector 0x80.

The assembly stub saves enough state to prevent ordinary C handler activity from silently destroying interrupted integer and FXSAVE state. User-origin page faults are contained to their process when possible. These mechanisms reduce privilege-boundary ambiguity, but they do not make every handler safe: any handler dereferencing untrusted data still requires explicit validation.

## Failure modes

Critical failure classes include malformed gate offsets, invalid code selector, incorrect descriptor attributes, wrong assembly/C frame agreement, stack misalignment before C, omitted hardware error-code normalization and extended-state corruption.

A mistake in exception entry can recursively fault while trying to deliver the first fault. That can escalate to a double fault and, without a valid recovery stack/descriptor, reset the machine. This is why the binary layouts and push/pop order are architectural invariants rather than implementation details.

## Validation

Static evidence includes the 16-byte gate assertion, full 256-entry generation, explicit list of hardware-error-code exceptions, matching `irq_frame` layout, FXSAVE/FXRSTOR pair and a DPL-3-only syscall gate.

Runtime validation should exercise each implemented fault class that can be safely induced, verify page-fault retry, verify user-fault containment, verify register preservation across interrupts, stress nested timer/device activity and test TLB IPI/NMI behavior on SMP. The generated Source Atlas exposes the complete stubs and C dispatcher so those tests can be reviewed against the exact revision.

## Current limitations

No IDT gate currently selects an IST slot. Kernel exceptions are fatal rather than recoverable. The NMI path is specialized for TLB fencing. The software syscall path uses `int 0x80` rather than SYSCALL/SYSRET MSRs. These are current implementation properties and should not be generalized into claims about what x86-64 itself requires.

## Source map

The table is defined in `kernel/metal/idt.c`/`idt.h`. Assembly entry and return are in `kernel/metal/idt_stubs.asm`. The shared C dispatcher and frame contract are `kernel/metal/irq.c`/`irq.h`. Fatal kernel exception reporting is `kernel/metal/panic.c`, while containment of user faults and the DPL-3 syscall gate involve `kernel/metal/syscall.c`. All are mirrored in full by the Source Atlas at revision `da3df29cb397932c43d32373871fb9380e688ade`.
