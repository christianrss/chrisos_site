---
id: emulator-exceptions
lang: en
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chris_arch.h
  - chrisvm/machine/machine.h
  - chrisvm/cpu/common/exceptions.c
  - chrisvm/cpu/emulator/mmu.c
  - chrisvm/cpu/emulator/chriscpu.c
  - chrisvm/cpu/emulator/execute.c
  - chrisvm/tests/test_chrisvm.c
symbols:
  - chris_raise
  - deliver_frame
  - chris_push8
  - chris_pop8
  - chris_seg_load_cs
  - chris_translate
  - chris_va_read
  - chris_va_write
  - maybe_irq
depends_on:
  - x86-decoding
  - emulator-flags
  - x86-64-memory-privilege
related:
  - emulator-paging
  - chrisvm-chriscpu
  - determinism-replay
---

# Exceptions, interrupts and fault delivery in ChrisCPU

## Scope

ChrisCPU uses one central delivery entry point, chris_raise, for synchronous faults, software interrupts and injected external interrupt vectors. The implementation has two materially different operating modes.

When no IDT has been loaded, an exception is reported to the ChrisVM monitor as CHRIS_EXIT_EXCEPTION. This mode is useful for bring-up and host-side tests because a guest does not need to install handlers before faults become observable.

When IDTR is nonzero, ChrisCPU attempts guest delivery through a 64-bit IDT gate and a guest stack frame. If delivery itself fails, the implementation attempts a double fault and can finally stop with CHRIS_EXIT_TRIPLE.

This chapter describes what the source actually implements at revision e05a17fd76333114a3fb5c2452f38ca747d4ac56. The current model is sufficient for controlled emulator experiments, but it is not yet a complete long-mode interrupt/exception architecture.

## Exception state in ChrisCpu

ChrisCpu keeps both architectural and emulator-control state relevant to faults:

| Field | Role |
|---|---|
| arch.rip | current guest instruction pointer |
| arch.rsp | current guest stack pointer |
| arch.rflags | saved/restored control and status state |
| arch.cs / arch.ss | modeled code and stack segment state |
| arch.gdtr / arch.idtr | descriptor-table registers |
| arch.cr2 | most recent modeled page-fault address |
| arch.cpl | current privilege level used by paging checks |
| ex_vector | diagnostic exception vector |
| ex_error | diagnostic error code |
| delivering | nonzero while building an exception frame |
| halted | stops the run loop |
| exit_reason | monitor-visible stop classification |
| irq_pending / irq_vector | pending external interrupt injection |
| sti_delay | one-instruction interrupt inhibition after STI |
| rip_dirty | prevents the run loop from applying the normal RIP increment |

The diagnostic ex_vector/ex_error fields are distinct from the guest stack frame. They are especially important in monitor mode, where no guest handler receives the event.

## Mode 1: monitor-visible exceptions without an IDT

deliver_frame begins by checking whether both IDTR base and limit are zero. If so, the exception is not delivered into the guest.

Instead it:

- sets exit_reason to CHRIS_EXIT_EXCEPTION;
- stores vector and error in ex_vector/ex_error;
- sets halted;
- returns a special status to chris_raise.

chris_raise recognizes this result and returns to the run loop without converting the event into double fault.

This mode is why test_chrisvm.c can execute an invalid opcode, page fault, general-protection case or divide error without first constructing an IDT. The host test then inspects chris_exception_vector and, for page faults, CR2.

This is a ChrisVM monitor behavior, not an x86 hardware mode. Real hardware cannot replace exception delivery with a host exit simply because IDTR contains zeroes.

## Mode 2: guest IDT delivery

With an IDT present, deliver_frame computes the gate address as:

    IDTR.base + vector * 16

The IDT limit must include all sixteen bytes of the selected long-mode gate. The implementation reads the gate through chris_va_read, so descriptor access itself uses guest virtual-memory translation.

The gate is then validated against a narrow supported subset:

- Present must be set;
- gate type must be 0xE interrupt gate or 0xF trap gate;
- IST field must be zero.

Nonzero IST is rejected. Task gates and other legacy gate types are not supported.

The target offset is assembled from the low, middle and high offset fields. The target selector is taken from the gate and passed to chris_seg_load_cs.

## Code-segment loading

chris_seg_load_cs resolves selectors only through the GDT. read_desc rejects a null selector, checks the GDT limit and reads an eight-byte descriptor through guest virtual memory.

The accepted target descriptor must have:

- Present set;
- executable/code bit set;
- long-mode L bit set.

The loaded CS gets base zero, limit 0xffffffff and attributes copied from the descriptor.

This is intentionally incomplete segmentation validation. The path does not implement the full long-mode rules for descriptor privilege level, requested privilege level, conforming code segments, LDT selection or all type constraints. The selector load should therefore be understood as minimum structural validation, not a complete protection check.

## The current guest frame

After loading the target CS, deliver_frame records the current RSP and RIP. It then pushes five 64-bit values in this order:

    SS selector
    old RSP
    RFLAGS
    target CS selector
    frame RIP

If the event has an error code, that 64-bit error value is pushed last.

Because the stack grows downward, a handler sees the error code at the top when present, followed by RIP, CS, RFLAGS, old RSP and old SS.

This frame is a simplified project convention. It differs from architectural long-mode entry in important ways.

### RSP and SS are always pushed

On x86-64, the exact exception frame depends on privilege transition and IST/stack switching. The current implementation always saves RSP and SS, even though it rejects IST and does not perform a CPL stack switch.

IRETQ in execute.c mirrors this simplified convention by always popping RIP, CS, RFLAGS, RSP and SS.

### The saved CS is not the interrupted CS

deliver_frame calls chris_seg_load_cs with the gate target selector before the frame is pushed. It then pushes the same target selector as the saved CS field.

Therefore the frame does not preserve the original interrupted CS when the handler selector differs from the interrupted selector. A subsequent IRETQ cannot reconstruct the old CS from that frame.

This is a concrete compatibility defect, not merely an unimplemented optional feature.

### IRETQ does not revalidate restored segments

The current IRETQ path pops RIP, CS, RFLAGS, RSP and SS, then assigns the CS and SS selector fields directly. It does not call chris_seg_load_cs and does not reconstruct descriptor attributes from the restored selectors.

The frame producer and consumer therefore form a project-specific pair rather than a complete x86 privilege-return mechanism.

### Error-code removal is handler responsibility

IRETQ does not consume an exception error code. If deliver_frame pushed one, a guest handler must adjust the stack before executing IRETQ. This matches the general x86 convention that the error code is separate from the IRET frame, but it is especially important because the ChrisCPU frame already uses a simplified fixed five-word shape.

## Interrupt gate versus trap gate

For a type 0xE interrupt gate, deliver_frame clears IF in RFLAGS. A type 0xF trap gate leaves IF unchanged.

For both supported gate types the current path clears:

- TF, bit 8;
- RF, bit 16;
- VM, bit 17.

It then sets RIP to the target offset and marks rip_dirty so the normal interpreter increment does not overwrite the transfer.

This is only a subset of the complete architectural state transition. The implementation does not claim every long-mode flag-entry rule.

## Fault, trap and interrupt RIP selection

The saved frame RIP is whatever cpu->arch.rip contains when chris_raise is called. The caller therefore determines whether the event behaves like a fault or a trap.

For ordinary execution faults such as divide error, the executor raises before the run loop advances RIP. The saved address is the faulting instruction.

For software INT, execute.c explicitly advances RIP to the next instruction and sets rip_dirty before calling chris_raise. The frame therefore contains the return address after INT.

INT3 follows the same CHRIS_OP_INT path and therefore saves the next instruction address, matching breakpoint trap-style restart semantics.

External interrupts are considered by maybe_irq after normal instruction execution and RIP advancement. If IF is set, an interrupt is pending and sti_delay does not suppress it, maybe_irq calls chris_raise with the injected vector. The saved RIP is therefore the next instruction boundary.

This caller-driven design is compact, but correctness depends on every fault source invoking chris_raise at the correct retirement point.

## Invalid opcode paths

There are two important invalid-instruction paths.

If chris_decode returns a negative result because the fetched byte sequence is structurally incomplete, chriscpu.c raises CHRIS_EX_UD.

If decoding succeeds but classifies the instruction as CHRIS_OP_UD, execute.c reaches the invalid-operation path and raises CHRIS_EX_UD.

Selected legality checks also use fail_ud. For example, unsupported LOCK use on register ALU forms is rejected through #UD.

The decoder chapter documents why structural truncation and recognized invalid encodings remain separate parser outcomes even though both can ultimately reach vector 6.

## Divide error

DIV and IDIV raise CHRIS_EX_DE in two explicit cases:

- divisor equals zero;
- the computed quotient does not fit the destination width.

The executor checks fit before committing the quotient and remainder. This prevents an oversized quotient from being silently truncated.

test_chrisvm.c verifies both division by zero and a quotient-overflow case, observing vector zero in monitor mode.

## General protection from the MMU and system operations

chris_translate distinguishes a noncanonical virtual address from a normal paging failure. A noncanonical address returns a dedicated status to chris_va_read/chris_va_write, which raises CHRIS_EX_GP with error code zero.

Selected unsupported or invalid system accesses also use #GP. The MSR path, for example, raises #GP for an index outside the modeled MSR set.

This is still a subset of #GP sources. Full segmentation, privilege, descriptor, canonical-target and system-instruction validation would generate more protection faults on real x86-64.

## Page-fault generation

Paging failures originate in chris_translate. When a normal paging permission or presence check fails, the virtual-memory helper records the failing virtual address in CR2 and raises CHRIS_EX_PF.

The implemented page-fault error-code bits are:

| Bit | Meaning | Current source |
|---:|---|---|
| 0 | P: protection violation versus not-present | set for permission faults |
| 1 | W/R | set for writes |
| 2 | U/S | set when current CPL is 3 |
| 4 | I/D | set for instruction fetch when NX checking applies |

The implementation does not currently model all modern page-fault error bits such as reserved-bit violation, protection keys, shadow stack or SGX-specific state.

For write protection, supervisor writes honor read-only pages when CR0.WP is set. User accesses require the user bit through the page-table walk. Execute permission checks NX when EFER.NXE is active.

CR2 is set to the current virtual address at the chunk that failed. For a multi-page operation, that can be a later address than the start of the original memory request.

## Physical backing failures are not guest page faults

Page-table reads and final physical reads/writes can fail because the modeled physical address does not map to RAM or a device.

The implementation distinguishes this machine-model failure from an ordinary guest page-table fault. In several such paths it sets CHRIS_EXIT_UNMAPPED, halts the CPU and records the address for diagnostics instead of generating guest #PF.

That distinction is useful: a valid guest page-table translation to a machine resource that the emulator does not implement is not the same condition as a not-present guest PTE.

## Faults during exception delivery

Exception delivery itself reads the IDT, reads a GDT descriptor and writes a frame to the guest stack. Any of those operations can encounter virtual-memory failures.

The delivering field prevents recursive calls to chris_raise from chris_va_read and chris_va_write while a frame is already being constructed. Instead, the memory helper returns failure to deliver_frame. deliver_frame converts that into its delivery-failed result.

This avoids uncontrolled recursion such as:

    page fault while pushing page-fault frame
    -> page fault while pushing page-fault frame
    -> ...

The failure is instead handled by the double-fault escalation path.

## Double-fault escalation

chris_raise gives delivery at most two stages.

Stage one attempts the original vector.

If deliver_frame reports a delivery failure rather than monitor mode, chris_raise replaces the vector with CHRIS_EX_DF, forces an error code of zero and performs a second delivery attempt.

If the double-fault delivery succeeds, guest execution can continue at the double-fault handler. If it fails, the emulator classifies the state as triple fault.

This policy is deliberately simpler than the Intel/AMD exception-pair classification. Real double-fault generation depends on combinations of contributory exceptions and page faults during delivery. ChrisCPU currently escalates any frame-delivery failure into #DF rather than implementing the full exception-class matrix.

## Triple fault

After two failed delivery attempts, chris_raise:

- clears delivering;
- sets exit_reason to CHRIS_EXIT_TRIPLE;
- sets halted;
- dumps the trace ring;
- returns failure.

The model stops at the monitor. It does not emulate the platform reset that a hardware triple fault typically causes through the processor/platform reset path.

CHRIS_EXIT_TRIPLE is therefore a debugger-visible terminal condition in ChrisVM.

## Partial frame writes and rollback

chris_push8 calculates RSP minus eight, writes the value through guest virtual memory, and only then commits the new RSP. This protects each individual push from decrementing RSP when its write fails.

However, deliver_frame performs multiple pushes sequentially. If early pushes succeed and a later push faults, there is no transaction that restores the earlier stack writes or the original RSP before double-fault delivery begins.

A failed exception frame can therefore leave a partially modified stack. The second delivery attempt then observes that modified machine state.

Precise x86 exception delivery has stricter architectural behavior. Transactional frame construction or explicit rollback would make the emulator easier to reason about and closer to hardware.

## Descriptor and privilege limitations

The current IDT/GDT path has several explicit boundaries:

- no IST support;
- no TSS stack switching;
- no CPL transition stack selection;
- no LDT-based code selector loading;
- no complete DPL/RPL/CPL validation;
- no conforming-code-segment rules;
- software INT does not validate gate DPL;
- restored IRETQ CS/SS selectors are not descriptor-revalidated;
- no full nested-task or task-gate semantics.

These limitations are central to any attempt to boot software that expects real user/kernel transitions.

## Diagnostic vector state during double fault

chris_raise writes ex_vector and ex_error before entering its delivery loop. When the first delivery fails and the local vector is replaced with #DF, those diagnostic fields are not rewritten in the current source.

As a result, a successfully delivered double fault can still leave ex_vector/ex_error describing the original event rather than the final delivered vector. Guest behavior is controlled by the frame-delivery path, but monitor diagnostics can be misleading.

This should be corrected before ex_vector is treated as an authoritative post-event record.

## Current validation evidence

test_chrisvm.c has direct monitor-mode tests for:

- #UD from an invalid opcode;
- #PF and CR2 from an unmapped translated address;
- #GP from a noncanonical address;
- #DE from divide by zero;
- #DE from quotient overflow;
- #GP from an unsupported MSR;
- #PF while pushing to a faulting stack address.

These tests verify important exception sources and host-visible vectors.

The inspected test file does not construct a guest IDT and exercise the full deliver_frame success path. It therefore does not currently provide equivalent integration evidence for interrupt-gate versus trap-gate entry, saved-frame correctness, double-fault delivery, triple fault, IST rejection, software-INT DPL rules or IRETQ round trips.

## Hardening priorities

The highest-value exception work is:

1. save the interrupted CS before loading the handler CS and place the correct selector in the frame;
2. define frame layouts separately for same-CPL delivery, privilege transitions and IST;
3. implement TSS/IST stack switching and validate IST entries;
4. validate IDT gate DPL for software interrupts and implement CPL/RPL/DPL rules for code-segment transfer;
5. make IRETQ revalidate and reconstruct returned segment state;
6. add an architectural exception-pair matrix instead of escalating every delivery failure identically;
7. make frame construction transactional or define rollback for partial writes;
8. update ex_vector/ex_error when escalation changes the delivered vector;
9. add end-to-end tests with guest IDT/GDT handlers for interrupt and trap gates;
10. add deterministic tests for successful #DF delivery and terminal triple fault;
11. extend page-fault error-code coverage and reserved-bit checking;
12. distinguish and document machine-unmapped exits from guest protection faults at every memory boundary.

## Revision note

At revision e05a17fd76333114a3fb5c2452f38ca747d4ac56, ChrisCPU has useful monitor-mode exception reporting, basic long-mode IDT gate delivery, page-fault error construction, double-fault escalation and a terminal triple-fault state. The implementation is not yet a complete privilege-transition or precise exception-delivery model. In particular, the current guest frame convention, saved-CS handling and absent IST/TSS path are compatibility boundaries that must be fixed before user/kernel exception transitions can be considered reliable.
