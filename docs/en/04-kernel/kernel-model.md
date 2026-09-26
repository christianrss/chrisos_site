---
id: kernel-model
lang: en
type: concept
volume: 04-kernel
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/start.c
  - kernel/metal/proc.c
  - kernel/metal/syscall.c
  - kernel/metal/mm.c
  - kernel/metal/pmm.c
  - kernel/metal/irq.c
  - kernel/metal/smp.c
  - kernel/metal/job.c
  - kernel/gfx/graphics.c
  - kernel/fs/fs.c
  - kernel/net/net.c
  - kernel/wm/main.c
  - docs/LOCKING.md
  - docs/RESOURCE_OWNERSHIP.md
symbols:
  - kstart
  - proc_switch
  - syscall_dispatch
  - irq_dispatch
depends_on:
  - power-on-kstart
  - x86-64-memory-privilege
related:
  - interrupts-smp
  - processes-syscalls
  - resource-lifetime
---

# Kernel model and trust boundaries

## Scope

The term “kernel” identifies privileged software, but it does not determine one internal architecture. A monolithic kernel, a microkernel and a hybrid system can all provide processes, virtual memory, filesystems and drivers while placing those mechanisms in different protection domains. To understand ChrisOS, the useful questions are concrete: which components execute in ring 0, which memory they can reach, which operations cross hardware privilege boundaries, which resources are globally shared, and which failures can be contained.

At revision `da3df29cb397932c43d32373871fb9380e688ade`, ChrisOS is a monolithic, modular x86-64 kernel. Memory management, physical allocation, process control, interrupt handling, storage, filesystem, networking, graphics, window management, language-runtime integration and most device drivers live in the privileged kernel image or execute through privileged kernel paths. Source directories and APIs divide responsibilities, but those divisions are not separate hardware protection domains.

## Monolithic does not mean unstructured

“Monolithic” describes protection placement, not source quality. A monolithic kernel can be decomposed into narrow modules with explicit ownership, dependency direction, state machines and interfaces.

ChrisOS uses subsystem boundaries such as:
- `kernel/metal` for CPU, memory, interrupts, processes and core hardware mechanisms;
- `kernel/fs` for block devices, partitions and filesystems;
- `kernel/gfx` for framebuffer, software rendering, VirtIO-GPU/VirGL and graphics resources;
- `kernel/net` for networking;
- `kernel/wm` for desktop/window-management policy;
- compiler/language layers for ChrisC, CLVM and native tooling.

A C function in one in-kernel subsystem calling another still executes with kernel privilege. The boundary improves maintainability and reasoning, but a stray pointer in either module can corrupt shared privileged memory.

## Contrast with a microkernel

A microkernel architecture normally keeps a smaller set of mechanisms privileged and places drivers, filesystems or services into isolated user processes communicating through IPC. A driver fault can then be confined to a server process if the hardware/resource model supports restart.

ChrisOS does not currently implement that separation. Its driver and filesystem code generally runs in the same privileged address space as page-table and scheduler code. Therefore calling ChrisOS “microkernel-like” because source modules are separate would be technically incorrect.

The project can still adopt microkernel-inspired ideas—narrow contracts, explicit ownership, restartable components—without claiming process isolation that is not present.

## Ring 0 and ring 3

The strongest native boundary currently implemented is x86 privilege separation between kernel and native user processes.

Ring 3 code:
- runs with user CS/SS selectors;
- executes in a process CR3;
- can access only pages whose page-table permissions allow user access;
- enters kernel services through the DPL-3 `int 0x80` gate;
- cannot execute instructions such as `lgdt` or direct CR3 manipulation.

Ring 0 code controls page tables, devices and global kernel state.

This boundary is hardware-enforced but only as strong as the mappings and entry validation created by the kernel. Mapping a kernel page with the user bit would undermine it; copying through an unchecked user pointer could bypass it.

## CLVM is a different boundary

ChrisC applications running through CLVM use another execution contract. A VM memory offset is not the same thing as a ring-3 virtual address, and a CLVM syscall interface is not the native `int 0x80` ABI.

The VM boundary is implemented by software checks and VM data structures. Native process isolation uses page tables and CPU privilege levels.

Both can be described as application isolation, but their threat models, memory representations and failure paths differ. Documentation and tests must not silently merge them into one generic “process” abstraction.

## Trusted computing base

The Trusted Computing Base is the code whose correctness is necessary for the properties the system claims. In ChrisOS the TCB is broad because many services run in ring 0.

High-consequence components include:
- PMM and page-table code;
- GDT/TSS and interrupt entry;
- process/address-space switching;
- user-copy and syscall dispatch;
- storage and filesystem metadata paths;
- device drivers with MMIO or DMA capability;
- graphics drivers that program shared device resources;
- network parsers running privileged;
- locking and TLB-reclamation protocols.

A small source file can be more security-critical than a large UI subsystem if it controls a page-table bit or DMA descriptor.

## DMA expands the trust boundary

CPU page protection does not automatically constrain a bus-mastering device. A device programmed with the wrong physical address can DMA into kernel memory without issuing a CPU load/store.

Therefore drivers that construct DMA descriptors belong to the effective memory-safety TCB. Correct ownership must include:
- physical frame lifetime;
- device-visible address;
- descriptor lifetime;
- completion acknowledgement;
- prohibition on reclaiming memory while hardware can still access it.

An IOMMU would provide another hardware protection layer, but documentation must not assume one unless the source configures it.

## Boot order is dependency architecture

`kstart` is an executable dependency graph.

The reviewed sequence begins with serial and build identity, then obtains Limine boot data, installs GDT/IDT/syscall/PIC/PIT/PS2 state, initializes physical/virtual memory and heap, establishes process state, initializes graphics, APIC/job/SMP support, probes ACPI/storage/filesystem/install paths, initializes language/audio, compiles the self-hosted compiler stage, enables interrupts, releases AP IRQ handling, starts desktop applications and finally networking/desktop loop.

The order encodes real prerequisites:
- PMM must exist before frame-backed mappings can grow;
- IDT must exist before interrupt delivery is safe;
- handlers must exist before IRQ lines are unmasked;
- heap must exist before heap consumers allocate;
- storage must exist before a disk filesystem can be used;
- job queue must exist before APs become workers;
- selected install/storage operations run before AP interrupt activity is released.

Changing order is an architectural change when it changes these assumptions.

## Global state

The current kernel uses global state in many core paths: current process, process table, job queue, device state, graphics state and filesystem state.

Global does not mean “unprotected”; it means ownership rules must answer:
- which CPU initializes;
- whether one CPU or many may mutate;
- which lock protects mutation;
- whether interrupts can enter while the state is inconsistent;
- how the state is torn down;
- whether the state outlives a process or device request.

The source repository's `docs/LOCKING.md` and `docs/RESOURCE_OWNERSHIP.md` provide additional subsystem-specific contracts.

## BSP-only user scheduling as a deliberate boundary

ChrisOS currently executes kernel jobs on multiple CPUs but keeps user process switching on the BSP. `proc_switch` panics when called from an AP, and syscall dispatch rejects off-BSP execution.

This is not “SMP absent”. It is a scoped SMP model:
- APs can execute kernel work;
- APs participate in TLB coherency;
- LAPIC IPIs/NMIs can target CPUs;
- user-process scheduler state remains global and BSP-owned.

The restriction removes an entire class of races around `g_current`, user return state and simultaneous CR3 switching while the rest of the kernel evolves.

## Mechanism and policy

A mechanism answers how an operation is possible. Policy decides when and to whom it applies.

Examples:
- `mm_map_cr3` is mechanism; which ranges receive `MM_USER` is policy;
- `apic_ipi` is mechanism; which CPU must acknowledge a TLB generation is policy;
- `proc_block` is mechanism; socket/join/IRQ conditions determine policy;
- block-device read/write is mechanism; filesystem layout and root selection are policy.

Experimental kernels often keep both in nearby code. Documentation should identify the distinction even where the implementation has not separated them into independent services.

## Resource ownership

A resource needs an owner and a release condition. ChrisOS shows this directly in process page records, file descriptor owners, socket cleanup, kthread stacks and graphics/storage resource objects.

Mapping is not ownership. A physical page can be mapped multiple times while one subsystem remains responsible for returning it to PMM.

Similarly, submitting DMA does not release a buffer; completion or cancellation must prove the device can no longer access it.

The ownership chapter and source audit should be treated as part of architecture, not as auxiliary coding style.

## Failure domains

Different failures have different containment boundaries.

A user page fault:
- may be demand-resolved;
- if invalid, can terminate one process;
- need not halt the kernel.

A ring-0 exception:
- may indicate corrupted invariants;
- currently goes to fatal panic;
- stops the CPU/system instead of guessing recovery.

A device interrupt storm:
- can be contained by masking the offending legacy IRQ.

A silent AP in TLB shootdown:
- can be fenced and targeted with NMI so physical-frame reuse remains safe.

A filesystem metadata failure may require a different containment strategy again.

Architecture is therefore partly a map of which failures are allowed to propagate.

## Asynchrony

Kernel state is modified not only through ordinary function calls. Interrupts, multiple CPUs and devices introduce asynchronous observation.

Even one CPU can deadlock if code holds a lock and an IRQ handler tries to acquire the same lock. Multiple CPUs add true parallel memory access. DMA adds actors outside the CPU instruction stream.

Correctness therefore depends on:
- lock ordering;
- interrupt-state rules;
- atomic operations;
- barriers;
- ownership handoff;
- device completion;
- TLB invalidation before frame reuse.

These concerns are cross-cutting; they cannot be hidden inside a generic statement that a module is “thread-safe”.

## Kernel interfaces

The kernel is an interface producer.

Native ring-3 ABI currently includes syscall numbers for exit, write, pixel output, file open/read/write/close and key query.

CLVM exposes a separate runtime syscall interface.

Internal interfaces include filesystem APIs, graphics APIs, block-device contracts, socket operations, process lifecycle and driver resource calls.

Stability requires each contract to define argument validity, ownership, concurrency context, errors and lifetime—not merely the function signature.

## Security boundary versus API boundary

Not every function boundary is a security boundary. Two C modules in ring 0 may validate one another's inputs for correctness, but hardware does not stop one from reading the other's memory.

Ring 3 → ring 0 is a hardware privilege boundary.
CLVM offset → host pointer is a software sandbox boundary.
Driver API → MMIO is an abstraction boundary with hardware side effects.
Filesystem API → on-disk metadata is a consistency boundary.

Using precise names prevents architecture diagrams from implying stronger isolation than exists.

## Validation boundary

A subsystem is not proven merely because source exists. Evidence should progress from:
1. code inspection;
2. host/unit tests where meaningful;
3. QEMU integration gates;
4. SMP/device stress;
5. real-hardware evidence where hardware support is claimed.

The documentation corpus distinguishes implementation from validation and roadmap so a stub such as IOAPIC is not presented as complete support.

## Current limitations

The kernel is not a fault-isolated driver/server architecture. User scheduling is BSP-only. Several global structures are intentionally simple. Fatal kernel exceptions stop the system. Modern hardware features are implemented unevenly by subsystem, and some drivers remain emulator-first.

These limitations are architectural facts that define the present trust model.

## Source map

`kernel/metal/start.c` is the highest-value dependency map. `proc.c`/`syscall.c` expose the native privilege boundary. `mm.c`/`pmm.c` define memory authority. `irq.c`/`smp.c`/`job.c` define asynchronous execution. Graphics, filesystem, networking and WM sources demonstrate the breadth of the monolithic privileged image. `docs/LOCKING.md` and `docs/RESOURCE_OWNERSHIP.md` document cross-cutting contracts. All source files are available without elision in the generated Source Atlas.
