---
id: pic-apic-ioapic
lang: en
type: concept
volume: 04-kernel
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/irq.c
  - kernel/metal/irq.h
  - kernel/metal/apic.c
  - kernel/metal/apic.h
  - kernel/metal/ioapic.c
  - kernel/metal/ioapic.h
  - kernel/metal/mm.h
  - kernel/metal/smp.c
  - kernel/metal/bootinfo.c
symbols:
  - pic_init
  - pic_set_mask
  - irq_set_handler
  - irq_eoi
  - irq_dispatch
  - apic_init
  - apic_enable_local
  - apic_ipi
  - apic_ipi_nmi
  - ioapic_init
depends_on:
  - idt-exceptions
  - buses-mmio-dma
related:
  - interrupts-smp
  - timers
  - tlb-shootdown
---

# PIC, Local APIC and IOAPIC routing

## Scope

Interrupt delivery on an x86 multiprocessor is not one device or one table. It is a chain: a device asserts an interrupt source, an interrupt controller maps that source to a vector and destination, the target processor accepts the vector, the IDT selects an entry stub, the kernel dispatches the event, and the controller is eventually acknowledged. ChrisOS currently uses a deliberately hybrid arrangement. Legacy PIC routing remains active for ordinary hardware IRQs, Local APIC functionality is enabled for per-CPU interrupt control and inter-processor interrupts, and the IOAPIC module is still a diagnostic stub rather than a completed external-interrupt router.

This distinction is essential when reading the source. The presence of LAPIC code does not mean that all device interrupts are routed through an IOAPIC. The reviewed revision explicitly leaves PIC lines in service.

## The 8259 PIC model

The traditional PC interrupt architecture contains two cascaded Intel 8259-compatible Programmable Interrupt Controllers. The master services IRQ 0–7. The slave services IRQ 8–15 and is connected through the master's IRQ2. Each controller exposes a command port and a data/mask port.

ChrisOS defines:

| Controller | Command | Data |
|---|---:|---:|
| PIC1 / master | `0x20` | `0x21` |
| PIC2 / slave | `0xA0` | `0xA1` |

At reset or firmware handoff, legacy PIC vector placement conflicts with processor-reserved exception vectors. `pic_init` therefore reprograms the pair so the master begins at vector `0x20` and the slave at `0x28`. IRQ 0 then becomes vector 32; IRQ 15 becomes vector 47.

## PIC initialization sequence

The initialization command sequence is explicit in `irq.c`. ChrisOS disables interrupts with `cli`, sends ICW1 `0x11` to both command ports, establishes vector bases, tells the master that the slave is connected on IRQ2, tells the slave its cascade identity, selects 8086 mode with ICW4, then masks every IRQ line.

`io_wait` calls are placed between programming writes where hardware timing historically requires separation.

The resulting state is not “interrupts enabled”. It is a configured but fully masked PIC. Individual subsystems later unmask only lines they have initialized. For example, `pit_init` installs the IRQ0 handler and unmasks IRQ0.

This staged policy prevents a device line from entering the kernel before its handler and underlying device state are ready.

## Masks and the cascade line

`pic_set_mask(irq, masked)` reads the current data-port mask, modifies the corresponding bit and writes the result back. IRQ numbers 0–7 use the master; 8–15 use the slave.

When a slave IRQ is unmasked, the function also clears the master's IRQ2 mask. Without this, the slave can assert its output but the master would suppress the cascade and no slave interrupt could reach the CPU.

The function ignores IRQ numbers outside 0–15. This is a legacy IRQ interface; LAPIC vectors and MSI-like mechanisms are separate concerns.

## IRQ handler table

ChrisOS maintains a 16-entry static array of function pointers. `irq_set_handler` installs a callback for a legacy IRQ. `irq_get_handler` exposes the current entry. The IDT itself does not point directly to these callbacks: vectors 32–47 first enter the common assembly stub and `irq_dispatch`, which converts the vector back to `irq = vector - 32`.

That extra layer centralizes frame construction, exception separation, storm handling and end-of-interrupt policy.

## End of interrupt

A controller commonly holds an interrupt in service until software acknowledges it. In PIC mode ChrisOS sends `PIC_EOI` to the slave first for IRQ 8–15, then to the master. Master EOI is required in both ranges because the cascade itself occupied an in-service master line.

`irq_eoi` also calls `apic_eoi` when the Local APIC has been software-enabled. This reflects the hybrid topology: LAPIC state may be active while PIC delivery still exists. The implementation intentionally acknowledges both paths where appropriate rather than assuming an IOAPIC-only machine.

## Interrupt-storm containment

`irq_dispatch` increments a per-IRQ hit counter for IRQs 1–15. If one of these lines reaches 10,000 deliveries, the kernel masks the line and reports an “irq storm” message.

IRQ0 is explicitly excluded because it is the 60 Hz timer. Counting a healthy periodic timer toward the same threshold would eventually disable the system clock.

This mechanism is coarse containment, not rate-based interrupt moderation. The counter is cumulative rather than measured per unit of time and there is no automatic re-enable. Its purpose is to keep a stuck line from livelocking boot or the desktop.

## Local APIC

Every x86 processor in an APIC-capable multiprocessor system has a Local APIC responsible for local vector handling, task-priority state, local timer facilities and IPI transmission/reception. ChrisOS currently uses the LAPIC primarily for software enablement, EOI and IPIs.

`apic.c` keeps a pointer to the mapped LAPIC page and a boolean-like `g_apic_on`. The physical APIC window is not ordinary RAM. `bootinfo.c` explicitly logs that simply adding the HHDM offset to physical `0xFEE00000` does not create a valid MMIO mapping and checks that the address is not mislabeled as usable memory. The actual usable virtual mapping is supplied through `mm_lapic_virt()`.

This separation matters because MMIO requires page-table mappings with semantics appropriate to device memory, not an assumption that all physical addresses belong to the normal direct map.

## Enabling the LAPIC

`apic_enable_local` retrieves the virtual LAPIC mapping and writes the Spurious Interrupt Vector Register at offset `0xF0`. The value `0x100 | 0xFF` sets the software-enable bit and chooses vector `0xFF` for spurious interrupts.

The function deliberately does not touch IMCR or disable the i8259 routing path. Its source comment states the reason: the PIT and ATA path still use the PIC. Therefore “LAPIC enabled” in ChrisOS means the local controller is available, not that legacy interrupt routing has been retired.

`apic_init` itself is even more conservative: it records the mapped pointer but leaves `g_apic_on = 0`. Later SMP initialization calls `apic_enable_local` unless the `noapic` boot flag is set.

## Fixed IPIs

`apic_ipi(dest_lapic, vector)` writes the destination APIC ID into the Interrupt Command Register high dword at offset `0x310`, then writes the low ICR at `0x300` with the vector and level-assert bit.

The routine polls delivery-status bit 12 for at most 100,000 iterations, executing `pause` between checks. Clearing the bit means the APIC accepted completion of the send operation. If LAPIC is unavailable or the delivery bit does not clear inside the bounded spin, the function returns -1.

A successful return says that the ICR send completed; it does not prove the destination executed the handler. Higher-level protocols such as TLB shootdown require their own acknowledgement state.

## NMI IPIs

`apic_ipi_nmi` uses delivery mode 100b, the APIC encoding for NMI, and sets level assert. The vector field is ignored for NMI delivery. It uses the same bounded delivery-status polling.

ChrisOS uses this stronger delivery class in the TLB-fencing path. Ordinary maskable interrupts can be delayed while IF is clear; NMI cannot be blocked by IF. That makes it useful for forcing a non-responsive AP into the TLB stop handler after the normal protocol decides it must be fenced.

NMI use is therefore coupled to a formal memory-reclamation invariant: a CPU whose translations may still reference pages being reclaimed cannot simply be forgotten. It must acknowledge invalidation or be stopped and marked appropriately before reuse is considered safe.

## APIC identity and SMP

`smp.c` records LAPIC IDs supplied by Limine during multiprocessor discovery. It does not rely exclusively on reading one shared LAPIC mapping to identify the executing CPU. A source comment documents a previous failure mode in which the shared MMIO view could yield the BSP ID and cause a later NMI to target the desktop CPU.

ChrisOS instead identifies an AP at runtime primarily from the virtual address range of its dedicated stack. `smp_current_cpu` derives the CPU index from RSP. The recorded CPU-index-to-LAPIC-ID map is then used when an IPI needs a hardware destination.

This is a concrete example of separating software CPU identity from hardware APIC destination identity.

## IOAPIC status

The IOAPIC is the component that would normally replace the 8259 PIC as the router for external interrupt inputs in an APIC-based system. It contains redirection-table entries that select vectors, delivery modes, polarities, trigger modes, masks and destinations.

In the reviewed ChrisOS revision, `ioapic_init` does not enumerate an IOAPIC, map registers or program a redirection table. It only writes:

```text
ioapic: PIC still routes IRQ (full IOAPIC in fase7 PASSO 01)
```

Therefore the correct documentation statement is: IOAPIC routing is not yet implemented. LAPIC/IPI support exists, but ordinary external IRQs still depend on PIC routing.

## Boot order

`kstart` establishes this chain in a deliberate order:

```text
GDT
IDT
syscall gate
PIC remap/mask
PIT handler + IRQ0 unmask
...
memory and heap
graphics
...
apic_init
ioapic_init
job_init
smp_init
...
sti near desktop start
```

The BSP programs the PIC before general interrupts are enabled. APs enter worker loops with IF initially clear. A later `smp_release_ap_irqs` allows each AP worker to enable its LAPIC and execute `sti` only after installation-sensitive work has completed.

A comment in `smp.c` records why: allowing AP interrupts during ATA copy previously prevented that copy from completing. The boot ordering is therefore a synchronization rule derived from observed failure, not arbitrary sequencing.

## Controller ownership and concurrency

PIC programming is global machine state. The current functions do not wrap every mask update in a dedicated lock, so callers must respect initialization/interrupt context and avoid competing writes that lose bits in the read-modify-write sequence.

LAPIC registers are local-controller state, but ICR send operations are also multi-register transactions. `apic_ipi` writes destination then command and waits for delivery completion before returning, serializing sends from the current call path. A future design with concurrent IPI senders on the same CPU would need an explicit serialization policy.

The legacy handler array is static and simple. Registration is expected during controlled initialization rather than arbitrary concurrent mutation while interrupts are firing.

## Failure modes

A wrong PIC vector base can alias hardware IRQs with CPU exceptions. A masked cascade line can suppress every slave device. Missing EOI can stop future interrupts from the controller. Premature EOI can violate a device driver's assumptions. An unmapped or incorrectly cached LAPIC page can fault or produce undefined device interaction. Sending an IPI to the wrong APIC ID can stall a synchronization protocol or halt the wrong CPU if the delivery mode is NMI.

These are not interchangeable failures. Diagnostics should identify which stage of the delivery chain is missing: source assertion, controller redirection, CPU receipt, IDT entry, handler dispatch, device clearing or EOI.

## Current architectural boundary

ChrisOS at revision `da3df29cb397932c43d32373871fb9380e688ade` should be described as a PIC-routed external-interrupt system with Local APIC support for per-CPU enablement and IPIs. It is not yet an IOAPIC-routed interrupt architecture. This boundary also means modern capabilities such as full redirection-table policy, interrupt affinity for external devices and systematic migration away from the 8259 are future implementation work.

## Source map

Legacy controller programming and generic IRQ dispatch are in `kernel/metal/irq.c` and `irq.h`. LAPIC EOI/IPI code is in `kernel/metal/apic.c`/`apic.h`. `kernel/metal/ioapic.c` documents the current stub status. SMP destination identity and delayed AP interrupt enablement are in `kernel/metal/smp.c`. Boot/MMIO assumptions are visible in `kernel/metal/bootinfo.c` and the memory subsystem interfaces. The Source Atlas publishes these files in full.
