---
id: volume-04-kernel
lang: en
type: volume-index
volume: 04-kernel
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
---

# Kernel architecture

<div class="abstract">Privilege, exception entry, interrupt routing, SMP, kernel workers, native processes, user/kernel memory crossing and fatal diagnostics.</div>

This volume is organized as a dependency chain rather than a short overview. Each implementation chapter is revision-bound to the ChrisOS `main` source and states its current limitations.

## Architecture and privilege

- [Kernel model and trust boundaries](kernel-model.md)
- [GDT and TSS](gdt-tss.md)
- [IDT and exception entry](idt-exceptions.md)

## Interrupts, time and parallel kernel execution

- [Interrupts and SMP](interrupts-smp.md)
- [PIC, LAPIC and IOAPIC](pic-apic-ioapic.md)
- [PIT timing and scheduler tick semantics](timers.md)
- [Kernel jobs and cooperative kernel threads](kernel-jobs-kthreads.md)

## Native userspace

- [Native processes and system calls](processes-syscalls.md)
- [User-mode entry and controlled return](user-mode-entry.md)
- [Safe user-memory access](user-copy.md)
- [Process lifecycle and state](process-lifecycle.md)

## Failure and observability

- [Panic, serial diagnostics and kernel log](panic-logging.md)

## Reading dependencies

The privilege and exception chapters should precede native userspace. SMP assumes the interrupt entry model. User-copy assumes virtual-memory translation. Process lifecycle depends on PMM/MM details in Volume 05.

The generated [Source Atlas](../99-source-atlas/index.md) is the file-level evidence layer; these authored chapters explain architecture, invariants, ownership, control flow, failure modes and limits rather than replacing source with excerpts.
