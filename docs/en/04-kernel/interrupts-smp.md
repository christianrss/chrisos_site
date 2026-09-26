---
id: interrupts-smp
lang: en
type: concept
volume: 04-kernel
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/idt.c
  - kernel/metal/idt_stubs.asm
  - kernel/metal/irq.c
  - kernel/metal/apic.c
  - kernel/metal/ioapic.c
  - kernel/metal/smp.c
  - kernel/metal/smp.h
  - kernel/metal/job.c
  - kernel/metal/tlb_proto.c
  - kernel/metal/mm.c
symbols:
  - irq_dispatch
  - smp_init
  - smp_current_cpu
  - ap_entry
  - ap_c_entry
  - smp_lapic_of
  - job_worker_forever
depends_on:
  - x86-64-memory-privilege
  - kernel-model
  - idt-exceptions
related:
  - pic-apic-ioapic
  - kernel-jobs-kthreads
  - tlb-shootdown
---

# Interrupts and symmetric multiprocessing

## Scope

Multiprocessing turns kernel execution from a single sequence occasionally interrupted by hardware into several instruction streams that can mutate shared state at the same time. ChrisOS brings additional x86-64 processors online through the Limine multiprocessor protocol, assigns dedicated mapped stacks, places them in a kernel job-worker loop, records hardware LAPIC destinations and integrates them into a formal TLB-coherency protocol.

At the same time, not every kernel feature is SMP-distributed. Native user-process switching is intentionally BSP-only. External hardware IRQs still use legacy PIC routing. AP interrupt enablement is delayed during boot. This chapter describes the exact scope of SMP rather than using “multicore support” as a binary label.

## Synchronous versus asynchronous entry

Processor exceptions are synchronous with the current instruction: divide error, invalid opcode, general protection and page fault are examples. Hardware IRQs are asynchronous from the interrupted code's perspective. IPIs are asynchronous messages initiated by another CPU. NMI is an interrupt class that is not blocked by the normal IF flag.

All can enter privileged code through vector mechanisms, but their recovery semantics differ. A user page fault can be associated with a virtual access and may be demand-resolved. A timer IRQ marks time passing. A TLB IPI exists because another CPU changed translation state. An NMI used for fencing means ordinary participation has already failed.

## BSP and AP terminology

The Bootstrap Processor (BSP) is the processor that executes the primary boot sequence. Additional logical processors are Application Processors (APs).

ChrisOS starts with `cpu_online_count = 1`. `smp_init` obtains the Limine MP response and programs AP startup records.

The source defines:
- up to 8 AP indices through `SMP_MAX_APS`;
- CPU-facing arrays with `SMP_CPU_CAP = 16`;
- four mapped pages per AP stack;
- virtual stack base `0xffffffff92000000`;
- stack stride `0x10000`.

These constants bound the current implementation independently of how many CPUs firmware reports.

## Capturing the kernel address space

At entry to `smp_init`, ChrisOS reads CR3 into global `kernel_cr3`.

Each AP entry begins by writing this CR3. This ensures the AP executes with the kernel page-table root expected by the addresses it will use.

An AP cannot safely execute higher-half kernel code, mapped AP stacks or MMIO interfaces before its translation context is consistent with the BSP's initialized kernel environment.

## Limine MP response

The Limine response supplies CPU descriptors including LAPIC ID and fields that the kernel can use to provide a startup function and an extra argument.

ChrisOS first clears startup fields for non-BSP processors, initializes mapping arrays, records the BSP LAPIC ID, then iterates APs.

For each AP within the configured cap it:
- assigns a software CPU index beginning at 1;
- records LAPIC ID ↔ CPU index relationships;
- allocates/maps a dedicated stack;
- stores the software index in `extra_argument`;
- publishes `ap_entry` as `goto_address`.

The source uses compiler barriers around publication so initialization stores are not casually reordered by the compiler relative to the handoff fields.

## AP stack allocation

`alloc_ap_stack(index)` computes a virtual base from AP stack base plus index times stride. It allocates four 4 KiB physical pages from PMM and maps them writable.

Failure to allocate an AP stack is fatal because the AP cannot safely enter C without private stack storage.

The function returns the top of the mapped stack.

The stride is larger than the mapped stack itself, leaving separation between CPU stack regions. `smp_current_cpu` later uses this virtual layout as an identity mechanism.

## AP entry and stack switch

`ap_entry` first writes `kernel_cr3`. It resolves the Limine MP info pointer into a kernel-usable virtual address if necessary, extracts software index/LAPIC ID and falls back to an index lookup if the extra argument is invalid.

It verifies index bounds and verifies that the stack was allocated.

Then it switches RSP to the AP stack and calls `ap_c_entry(index)`.

The source comment warns not to touch old locals after the stack switch. A previous bug involving old frame-pointer/spilled state caused AP index corruption and made APs answer TLB operations as CPU 0.

This illustrates why stack switching is an ABI boundary, not just assignment of a pointer.

## CPU-local initialization

`ap_c_entry` loads the IDT register with `idt_load` and initializes SSE state.

It then recomputes current CPU identity from the stack when possible. If LAPIC mapping metadata is missing, it can read the LAPIC ID and store it.

The CPU is registered with the TLB runtime as online and `cpu_online_count` is atomically incremented.

The AP then enters `job_worker_forever`. It does not enter native user scheduling.

## Why IDT state is CPU-local

IDTR is a CPU register. Constructing the IDT once in memory on the BSP is not sufficient; each AP must load the table address into its own IDTR.

Similar reasoning applies to CR3 and SIMD control state.

Kernel documentation must distinguish shared memory objects from processor-local architectural registers. A shared array does not imply that CPU-local register state is automatically synchronized.

## Current CPU identity

The source warns against relying on a shared LAPIC mapping to discover current CPU. Instead `smp_current_cpu` reads RSP.

If RSP is below the AP stack base, the function returns CPU 0. Otherwise it subtracts the base, divides by stride and validates the resulting index.

This works because AP steady-state kernel execution uses its assigned stack range.

It is not a universal CPU-identification technique: code that moves an AP temporarily to an unrelated stack would break the assumption unless identity handling changes.

## Hardware destination identity

Software CPU index and LAPIC ID are separate.

`g_lapic_of_cpu` stores the LAPIC destination corresponding to a CPU index. `smp_lapic_of` returns it with a “known” flag.

The separation is important because TLB protocol and per-CPU arrays use compact software indices, while `apic_ipi` requires hardware LAPIC destination IDs.

A prior bug documented in source could target the BSP with an NMI when LAPIC identity was inferred incorrectly. The current mapping preserves boot-published IDs to avoid that ambiguity.

## Waiting for AP startup

After publishing startup functions, the BSP expects `want = next` online CPUs. It spins with `pause` while `cpu_online_count < want`, bounded by 100,000,000 iterations.

It then logs the count and enables the BSP LAPIC unless disabled by boot flag.

The bounded wait avoids a literal infinite startup hang, but current source does not turn a partial online count into a panic here. Documentation should therefore distinguish “requested APs” from “successfully incremented online count”.

## AP interrupt state

AP code reaches the worker loop with IF intentionally clear.

`job_worker_forever` waits until `smp_release_ap_irqs` sets a global flag. Then each AP, on its own worker iteration, enables its LAPIC unless `noapic` and executes `sti`.

The source records a historical reason: AP interrupt activity enabled too early interfered with ATA copy during install.

Thus SMP bring-up has two milestones:
1. AP online and capable of polling/executing kernel jobs;
2. AP released to accept maskable interrupts.

## Job execution

APs primarily execute work from the global job ring. The BSP can also consume jobs.

This gives parallel kernel execution without a distributed user scheduler. The job layer is protected by a spinlock for queue structure and atomics for completion accounting.

Kthreads build private-stack callbacks on top of the same workers.

## User processes remain BSP-only

`proc_switch` verifies `smp_current_cpu() == 0` and panics otherwise. `syscall_dispatch` also rejects non-BSP entry.

Therefore a statement such as “ChrisOS schedules applications across all CPUs” would be false at this revision.

The supported statement is narrower: the kernel has SMP workers and inter-CPU coherency mechanisms while native user execution remains BSP-owned.

## Shared-memory races

Once APs are online, ordinary C state can be accessed concurrently. A read/modify/write expression is not automatically atomic.

ChrisOS provides CAS-based spinlocks and atomic-add primitives. Subsystems must define which state is protected by which lock.

Lock correctness includes:
- mutual exclusion;
- ordering between multiple locks;
- whether interrupt context can acquire them;
- whether callbacks may sleep/spin;
- publication ordering.

A lock cannot repair a resource-lifetime error where memory is freed before another CPU stops using it.

## Interrupt reentrancy

Even without SMP, an IRQ can interrupt code holding a lock and attempt to reacquire the same lock on the same CPU. This deadlocks because the interrupted code cannot resume to release it.

`spin.h` offers `irq_save`/`irq_restore` for cases that need local interrupt exclusion in addition to a spinlock. Individual locks must specify whether that rule applies.

On SMP, disabling local interrupts does not stop other CPUs. Shared data still needs an inter-CPU synchronization primitive.

## TLB coherence

When one CPU changes a mapping, another CPU can retain a stale Translation Lookaside Buffer entry. Reusing the physical page before all relevant CPUs invalidate or stop using the old translation can produce use-after-free at hardware speed.

ChrisOS has a formal `TlbWorld`:
- CPUs are ABSENT, ONLINE or FENCED;
- each shootdown publishes a generation, virtual range and byte count;
- online CPUs track which generation they have seen;
- heartbeats show worker progress;
- silent CPUs can be fenced;
- reuse is forbidden until required acknowledgements or fenced-stop conditions are satisfied.

This is a memory-lifetime protocol, not just a performance cache flush.

## IPI and NMI escalation

Normal TLB notification can target online CPUs with fixed LAPIC IPIs.

If a CPU remains silent past the configured quiet budget, the protocol can classify it as fenced. An NMI path can invalidate/stop it even if IF blocks normal interrupts.

The NMI handler calls `mm_tlb_nmi_stop`. An AP that must stop can enter permanent halt; the BSP is deliberately allowed to return because halting it previously froze the desktop.

This asymmetry is part of the current recovery model.

## CPU retirement

`smp_retire_cpu` atomically decreases `cpu_online_count` but never below 1.

The comment explicitly states that TLB membership—not this count—decides who must acknowledge a shootdown. This prevents a simple online-count change from falsely proving memory-reclamation safety.

The distinction between “number of CPUs for scheduling/status” and “formal participants in a translation generation” is critical.

## Memory ordering

The code uses GCC atomic builtins, explicit compiler barriers and architecture-specific instructions such as `pause`.

On x86-64, the hardware memory model is relatively strong compared with some architectures, but compiler transformations still matter and atomic read-modify-write operations carry ordering semantics.

Documentation should not reduce this to “x86 does not reorder”. Correctness depends on both language/compiler and CPU models.

## Failure modes

SMP bring-up can fail through:
- missing Limine MP response;
- PMM exhaustion allocating AP stacks;
- wrong software index publication;
- stack-switch ABI errors;
- incorrect CPU/LAPIC mapping;
- AP not reaching online state;
- early interrupt enablement;
- lock cycles;
- stale TLB translations;
- wrong IPI/NMI destination.

Several of these have concrete historical comments in the source because they previously caused desktop freezes or TLB misidentification.

## Validation

Useful evidence includes:
- multiple APs incrementing online count;
- job self-test across APs;
- per-CPU identity correctness;
- TLB generation acknowledgement under memory-map churn;
- forced silent-CPU fencing tests;
- IPIs delivered to intended LAPIC IDs;
- boot/install stress with delayed AP IRQ release;
- lock-order stress;
- user process paths remaining on BSP.

A successful multicore boot alone does not prove TLB reclamation or lock correctness.

## Current limitations

AP count is statically capped. CPU identity depends on AP stack ranges. User processes do not migrate to APs. IOAPIC routing is not implemented. AP workers poll rather than sleep on a scheduler primitive. Panic handling does not yet coordinate a system-wide SMP stop.

These limits define the current SMP stage precisely.

## Source map

`smp.c`/`smp.h` implement AP lifecycle, stacks and identity. `job.c` runs AP work. `tlb_proto.c` and memory code define translation coherence. `apic.c` sends IPIs/NMIs. `idt.c`/`idt_stubs.asm` and `irq.c` implement vector entry. `ioapic.c` documents the unimplemented external-routing stage. The full sources are available in the Source Atlas.
