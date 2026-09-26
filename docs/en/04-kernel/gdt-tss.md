---
id: gdt-tss
lang: en
type: concept
volume: 04-kernel
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/gdt.c
  - kernel/metal/gdt.h
  - kernel/metal/linker.ld
  - kernel/metal/user_enter.c
symbols:
  - gdt_init
  - gdt_reload_kernel_segments
  - gdt_read_tr
  - enter_user
depends_on:
  - x86-64-memory-privilege
  - privilege-rings
related:
  - idt-exceptions
  - user-mode-entry
  - processes-syscalls
---

# GDT and TSS

## Scope and prerequisites

The Global Descriptor Table remains part of the x86-64 architectural contract even though long mode no longer uses segmentation as the primary mechanism for ordinary address translation. Paging supplies the address-space isolation used by ChrisOS, but the processor still consults segment descriptors for privilege metadata, code/data segment state and the Task State Segment. A kernel that intends to cross between ring 0 and ring 3 therefore cannot treat the GDT as historical baggage.

This chapter covers the descriptor-table mechanism, the exact descriptor set installed by ChrisOS, the 64-bit TSS representation, the descriptor encoding used for that TSS, the segment reload sequence after `lgdt`, the role of `rsp0`, and the relationship between these structures and `iretq`-based entry into user mode. It does not treat paging as segmentation; page-table protection is documented separately.

## Segmentation in long mode

In legacy x86 modes, a logical address is formed from a segment selector plus an offset, and the selected descriptor contributes a base, limit, type and privilege attributes. In 64-bit mode the ordinary CS, DS, ES and SS base/limit behavior is largely flattened, but their selectors and descriptors still carry protection semantics. CS determines the current privilege level through its selector and descriptor, and transitions such as interrupt delivery or `iretq` validate privilege relationships. FS and GS have separate mechanisms for their bases and are not used by ChrisOS here as general address-space selectors.

A selector is not a byte address into the GDT. Its index is encoded in bits 3 and above, while the low bits carry the table indicator and requested privilege level. ChrisOS defines:

| Symbol | Selector | Intended use |
|---|---:|---|
| `GDT_KERNEL_CODE` | `0x08` | ring-0 64-bit code |
| `GDT_KERNEL_DATA` | `0x10` | ring-0 data/stack |
| `GDT_USER_DATA` | `0x18` | ring-3 data/stack descriptor |
| `GDT_USER_CODE` | `0x20` | ring-3 64-bit code descriptor |
| `GDT_TSS` | `0x28` | 64-bit TSS system descriptor |

Selectors passed to user mode are formed by ORing the user descriptor selectors with `3`. This sets the Requested Privilege Level to ring 3, so `enter_user` uses `GDT_USER_CODE | 3` for CS and `GDT_USER_DATA | 3` for SS.

## Descriptor layout used by ChrisOS

`gdt.c` allocates seven 64-bit slots aligned to 16 bytes. The null descriptor occupies slot 0. Slots 1 through 4 are ordinary code/data descriptors. Slots 5 and 6 together encode the 16-byte TSS system descriptor required in 64-bit mode.

The four ordinary descriptor constants are:

| Slot | Value | Meaning |
|---:|---|---|
| 1 | `0x00af9a000000ffff` | kernel code |
| 2 | `0x00cf92000000ffff` | kernel data |
| 3 | `0x00cff2000000ffff` | user data |
| 4 | `0x00affa000000ffff` | user code |

The access bytes distinguish executable versus writable data segments and encode Descriptor Privilege Level 0 or 3. The long-mode code descriptors have the L bit set. The data descriptors retain the conventional present/read-write attributes needed for valid selector state.

ChrisOS zeroes the entire table before writing these values. This is more than cosmetic: unused descriptors must not accidentally inherit stale present bits or addresses from uninitialized memory.

## The 64-bit Task State Segment

The x86-64 TSS is not used by ChrisOS as a hardware task-switching process object. Its important role is to supply privileged stack state and interrupt-stack-table slots to the processor.

The packed `tss64` structure in `gdt.c` contains the architecturally defined fields:

- `rsp0`, `rsp1` and `rsp2` for stack pointers associated with privilege transitions;
- `ist1` through `ist7` for optional dedicated interrupt stacks;
- reserved fields required by the hardware layout;
- `iomap_base` for the I/O permission bitmap boundary.

ChrisOS asserts at compile time that this structure is exactly 104 bytes. That assertion protects an architectural ABI: if compiler padding changed the layout, `ltr` would still accept a descriptor, but subsequent privilege transitions could read the wrong offsets.

At initialization, the TSS is zeroed and `rsp0` is set to `__stack_top`. The linker script creates this stack in `.bss` by reserving 1 MiB between `__stack_bottom` and `__stack_top`. `iomap_base` is set to `sizeof(tss)`. With no permission bitmap appended beyond the TSS, this places the bitmap outside the segment limit and prevents the structure from accidentally exposing an I/O bitmap.

The current implementation leaves every IST entry at zero. Consequently ChrisOS does not yet route exceptions such as double fault or NMI onto dedicated IST stacks through the IDT. The NMI entry currently executes on the interrupted stack. That is a concrete limitation, not merely an omitted explanation.

## Encoding the TSS descriptor

A 64-bit TSS descriptor consumes 16 bytes rather than the 8 bytes used by an ordinary code/data descriptor. `install_tss_descriptor` takes the linear address of the static TSS object, calculates `sizeof(tss) - 1` as the limit, then distributes the base and limit bits across `gdt[5]` and `gdt[6]`.

The access byte is `0x89`: present, DPL 0, system descriptor type, available 64-bit TSS. The low descriptor contains the lower portions of the base and limit, and the second 64-bit slot carries the upper 32 bits of the TSS base.

This encoding is sensitive to bit position. It is intentionally produced with shifts instead of a C bit-field structure because compiler-defined bit-field layout would create an unnecessary dependency in an architectural binary format.

## Loading the table

`gdt_init` performs the following sequence:

```text
zero GDT and TSS
    |
write kernel/user descriptors
    |
initialize TSS.rsp0 and iomap_base
    |
encode TSS descriptor
    |
construct { limit, base } GDTR operand
    |
lgdt
    |
far return to reload CS = 0x08
    |
reload DS/ES/SS = 0x10
clear FS/GS selectors
    |
ltr 0x28
    |
str -> verify TR == 0x28
```

`lgdt` changes GDTR but does not retroactively reload the hidden descriptor caches associated with the current segment registers. For that reason ChrisOS immediately performs a far-control transfer. It pushes the kernel code selector and a RIP label, then executes `lretq`. This reloads CS from the new GDT before execution continues at the local label.

After CS is valid, DS, ES and SS receive `0x10`. FS and GS selectors are cleared. Finally `ltr` loads the task register with selector `0x28`.

`gdt_read_tr` uses `str` to read back the visible task-register selector. `gdt_init` panics if the result is not `GDT_TSS`. This is a small but useful initialization invariant: the kernel refuses to continue if the descriptor table was accepted incompletely.

## Why `rsp0` matters

When execution transitions from a less privileged context to ring 0 through an interrupt or exception gate, the CPU needs a trusted ring-0 stack. The user stack cannot simply become the kernel stack: it belongs to an untrusted address-space context and may be unmapped, deliberately malformed or positioned to corrupt kernel state.

The TSS provides the ring-0 stack pointer used for that transition. In the present ChrisOS implementation `rsp0` points at the single linker-defined kernel stack. This is compatible with the current process model, which constrains user-process execution and switching to the BSP. It is not yet a general per-thread kernel-stack design.

A future preemptive, multi-user-thread scheduler would normally require the active TSS `rsp0` to track the kernel stack of the thread being scheduled, or otherwise use an entry mechanism that lands first on a safe per-CPU stack. The current code does neither because the scheduler model does not yet require it.

## Relation to user-mode entry

`enter_user` demonstrates the opposite direction of the privilege boundary. It does not ask the TSS to switch to ring 3. Instead it constructs an `iretq` frame manually:

```text
SS = GDT_USER_DATA | 3
RSP = requested user stack
RFLAGS = 0x202
CS = GDT_USER_CODE | 3
RIP = requested user entry
iretq
```

The processor validates the selectors and privilege transition against the GDT. The presence of correct user descriptors is therefore a prerequisite for user execution even though virtual-memory translation itself is controlled by CR3 and page-table U/S flags.

Before performing the transition, ChrisOS stores a kernel return address through `syscall_set_kernel_return`. The current syscall/termination path later rewrites an interrupt frame so execution can return to ring 0. That mechanism is documented with the syscall and user-entry code rather than hidden inside the GDT chapter.

## Reload path and SMP considerations

`gdt_reload_kernel_segments` repeats `lgdt`, the far-return CS reload, data-segment reload and `ltr`. The function exists because descriptor-register state is per logical processor. Loading GDTR and TR on one CPU does not install those registers on another CPU.

The current source exposes this reload primitive, while the broader SMP bring-up code is responsible for ensuring application processors establish valid descriptor state before they execute paths that depend on it. Any future change that makes the GDT or TSS per-CPU must preserve that distinction: memory containing a table may be shared, but GDTR, segment hidden state and TR are processor-local architectural state.

## Invariants

The implementation relies on several invariants:

| Invariant | Consequence if violated |
|---|---|
| `sizeof(tss64) == 104` | hardware reads fields at incorrect offsets |
| user descriptors have DPL 3 | ring-3 selector load or `iretq` fails |
| kernel code selector is valid before interrupts | exception entry can escalate into a fault cascade |
| TSS descriptor spans slots 5 and 6 | base address becomes truncated or malformed |
| TR contains `0x28` | privilege transition lacks the intended TSS |
| `rsp0` references mapped writable kernel memory | ring transition can fault while trying to construct a kernel frame |
| user selectors include RPL 3 | requested privilege does not match intended CPL |
| descriptor memory remains resident | GDTR/TR reference invalid storage |

The GDT and TSS objects are static kernel storage, so their lifetime is the kernel lifetime. No heap ownership or teardown path exists.

## Fault behavior

A malformed GDT installation can produce #GP, #SS, #TS or cascading faults during segment reload, interrupt delivery or `iretq`. Some failures occur before a normal C panic path is usable. This is why descriptor-table bring-up must happen before enabling general interrupt-driven execution and why the code performs a direct task-register verification immediately after `ltr`.

ChrisOS currently does not install dedicated IST stacks. That means stack corruption can reduce the kernel's ability to diagnose certain exceptional conditions. A double-fault-specific IST is a conventional hardening measure that is not present in the reviewed revision.

## Security boundary

The GDT does not replace page permissions. Its security function in current ChrisOS is to establish valid privilege-bearing selectors and the TSS entry-stack contract. User memory isolation comes from paging, and syscall buffer validation comes from explicit translation and U/S checks. These mechanisms are complementary.

The user descriptors are deliberately DPL 3. Kernel descriptors remain DPL 0. The system TSS descriptor is also kernel-controlled. User code cannot alter GDTR or TR because `lgdt` and `ltr` are privileged instructions.

## Performance

GDT setup occurs during processor initialization rather than in the normal hot path. Ordinary 64-bit execution does not repeatedly walk the GDT for every memory reference. The performance-sensitive aspect is privilege transition: segment state and TSS data must already be valid so hardware can perform the transition directly.

Because ChrisOS currently uses one fixed `rsp0` instead of updating it on every user-thread context switch, there is no per-switch TSS update cost. That simplicity corresponds directly to the current BSP-bound user-process model and must be revisited if the scheduling model changes.

## Validation evidence

The strongest direct evidence in the reviewed source is structural:

- the compile-time 104-byte TSS assertion;
- explicit descriptor values and explicit TSS descriptor encoding;
- the `ltr` followed by `str` verification;
- `enter_user` consuming the user selectors in an actual `iretq` transition;
- the linker-defined kernel stack used as `rsp0`.

Runtime validation should additionally exercise a ring-3 program, syscall/interrupt return, deliberate user faults and repeated transitions. Those tests belong to the validation volume and source gates; the existence of `gdt_init` alone is not proof of every transition case.

## Current limitations

The reviewed implementation has one static TSS, a fixed `rsp0` pointing to the linker-created kernel stack, no populated IST entries and no I/O permission bitmap. These properties are appropriate to describe as current design facts, not as full x86 task-management support.

The architecture also does not use hardware task switching. Processes are represented by ChrisOS data structures and page-table roots, not by one TSS per process.

## Source map

Primary implementation is `kernel/metal/gdt.c` and `kernel/metal/gdt.h`. The stack symbols consumed by the TSS originate in `kernel/metal/linker.ld`. The ring-3 selectors are consumed concretely by `kernel/metal/user_enter.c`. The generated Source Atlas contains the complete contents of each of these files at revision `da3df29cb397932c43d32373871fb9380e688ade`.
