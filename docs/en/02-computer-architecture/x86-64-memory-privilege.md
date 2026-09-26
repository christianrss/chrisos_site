---
id: x86-64-memory-privilege
lang: en
type: technical-chapter
volume: 02-computer-architecture
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/gdt.c
  - kernel/metal/idt.c
  - kernel/metal/mm.c
  - kernel/metal/mm.h
  - kernel/metal/proc.c
  - kernel/metal/linker.ld
  - chrisvm/chris_arch.h
  - chrisvm/cpu/emulator/mmu.c
  - chrisvm/cpu/common/exceptions.c
symbols:
  - mm_switch
  - mm_map_cr3
  - mm_clone_kernel_space
  - proc_map_user
  - chris_translate
  - chris_va_read
  - chris_va_write
  - chris_raise
depends_on:
  - cpu-datapath-isa
  - x86-registers-flags
  - x86-instruction-encoding
related:
  - virtual-memory
  - kernel-model
---

# x86-64 memory, privilege and architectural state

## Long mode

x86-64 long mode provides 64-bit general-purpose registers and a large virtual address space while retaining substantial historical architecture. Segmentation is greatly reduced for ordinary address calculation, yet segment selectors, descriptor tables and privilege metadata remain relevant to transitions and exception delivery.

ChrisOS links its kernel in the higher half. Its linker script uses an entry symbol `kstart` and places the kernel at a high canonical virtual address rather than assuming identity between physical and virtual addresses.

## Canonical virtual addresses

Not every 64-bit bit-pattern is a valid current x86-64 virtual address. Implementations support a defined virtual-address width, and high unused bits must form a canonical extension of the implemented sign bit. Software must therefore distinguish "64-bit integer" from "valid virtual address."

ChrisOS process mapping code rejects user addresses at or beyond its configured user boundary; kernel addresses occupy the high region.

## Rings and privilege

The architecture defines privilege levels conventionally numbered 0 through 3. Mainstream operating systems use ring 0 for the kernel and ring 3 for user programs.

Privilege is attached to execution state and descriptors. A ring-3 program cannot simply emit an instruction that rewrites CR3 or disables interrupts and expect success. The CPU validates whether the operation is permitted.

This provides a hardware basis for isolation:

| Boundary | Required property |
|---|---|
| User execution | Privileged state and supervisor mappings remain protected |
| Entry to kernel | An approved gate selects entry state and handler |
| Request handling | Kernel validates data supplied across the boundary |
| Return | Restored state satisfies user privilege and address constraints |

## Control registers

Several control registers are central to kernel engineering.

| Register | Role relevant here |
|---|---|
| CR0 | global operating-mode and protection controls, including paging enable |
| CR2 | faulting linear address after a page fault |
| CR3 | physical base of the top-level page-translation structure plus architecture-defined control bits |
| CR4 | additional architectural features, including paging-related controls |

ChrisOS `mm_switch` writes CR3 when changing address spaces. That single machine instruction changes the translation context against which subsequent virtual memory references are interpreted.

## Descriptor tables

The GDT provides descriptors and selectors still required for code/data privilege conventions and the task-state segment. The IDT maps exception and interrupt vectors to handler descriptors.

A correct IDT entry is not merely a function pointer. It encodes target offset, selector, gate type and privilege/presence properties. The processor constructs the architectural transfer according to these fields.

## Exceptions

Exceptions are synchronous consequences of instruction execution. Examples include invalid opcode, general-protection fault and page fault. Interrupts from external devices are asynchronous relative to the currently executing instruction stream.

A kernel must preserve enough machine state to diagnose or recover from the event, determine its origin and either resume, terminate a process or fail the system in a controlled way.

## Architectural state in ChrisCPU

ChrisCPU has to represent the state that guest instructions can observe. The project's architectural state includes general registers, instruction pointer, flags and control/segment-related state required by the implemented subset.

The significance is methodological: ChrisOS kernel code provides concrete examples of *using* x86-64, while ChrisCPU provides concrete examples of *implementing the visible behavior* of x86-64.

## Architecture is not microarchitecture

None of these contracts require an emulator to reproduce speculative execution, physical register renaming or commercial cache hierarchies to be functionally correct for supported instructions. Those mechanisms affect timing and performance, not the basic architectural result.

This boundary also explains why QEMU or ChrisVM can run software compiled for an ISA without physically containing the same processor design.

## Address domains and translation structure

An effective address is calculated from instruction operands. A linear address includes the architecture's applicable segment treatment. A physical address selects a location in the machine's physical address map, which can contain RAM, device registers or holes. These are different domains even when particular mappings make their numbers equal. The host pointer used to store guest RAM is a fourth domain. Adding a guest physical address to an arbitrary host pointer without checking the backing region would violate the emulator's memory boundary.

For four-level paging with 4 KiB tables and eight-byte entries, each table contains 512 entries. Selecting one requires nine address bits. Four such indices plus a twelve-bit page offset consume 48 bits. The remaining high bits must repeat bit 47 for canonical addresses in this model. The two canonical intervals are `0x0000000000000000` through `0x00007fffffffffff` and `0xffff800000000000` through `0xffffffffffffffff`. The numerical gap is not mapped by merely installing a page-table entry.

| Address bits | Role | Shift used by ChrisCPU |
|---|---|---:|
| 47:39 | PML4 index | 39 |
| 38:30 | PDPT index | 30 |
| 29:21 | PD index | 21 |
| 20:12 | PT index | 12 |
| 11:0 | Offset within 4 KiB page | 0 |

`chris_translate` begins with CR3 rounded down by clearing its low twelve bits. At each level it calculates `table + index * 8`, reads the entry through physical memory and applies permission checks. A nonleaf entry supplies the next table. A leaf combines a frame base with the page offset. The function directly returns the input address when CR0.PG is clear, before its canonical-address check. This is the implemented branch order, not a complete model of every nonpaged execution mode.

## A walk that can be reconstructed byte for byte

![Page-table descent, permission checks and physical access](../../assets/diagrams/paging-permission-walk.svg)

Consider CR3 = `0x1000`, a PML4 entry at `0x1000` containing `0x2007`, a PDPT entry at `0x2000` containing `0x3007`, a PD entry at `0x3000` containing `0x4007`, and a PT entry at `0x4008` containing `0x8007`. The low value seven sets present, writable and user-accessible bits. Translating virtual `0x1234` uses indices zero, zero, zero and one, then offset `0x234`. The final physical address is `0x8234`.

All addresses of table entries in this example are physical. The walk does not recursively translate them through the same virtual mapping. Otherwise translation would depend on itself without a terminating base case. ChrisCPU obtains them through `chris_phys_read`; the kernel obtains a host-accessible virtual view of physical tables through its boot-information mapping helper. These are distinct implementation strategies for the same table interpretation problem.

A page-size bit at the PDPT level terminates the walk with a 1 GiB leaf; at the PD level it selects a 2 MiB leaf. The remaining offset is respectively thirty or twenty-one bits. Large pages shorten walks and reduce table storage, but coarsen allocation and protection granularity. A single four-level walk is bounded by four entry reads; processing an n-byte span still depends on how many page boundaries it crosses and how the implementation chunks it.

## Permissions are accumulated along the path

The leaf is not the sole authority. User access requires appropriate permission in every traversed ancestor as well as the leaf. A writable leaf beneath a read-only ancestor does not restore write permission. ChrisCPU checks each entry before descending. It classifies an access as user when CPL equals three, as write when the access argument is one and as instruction fetch when that argument is two.

For writes to an entry without its writable bit, user access fails; supervisor access fails when CR0.WP is set. Clearing WP permits the supervisor write in this inspected path, but never grants a user write. For instruction fetch, an NX bit denies execution when EFER.NXE is enabled. NX restricts execution, not ordinary data reads. A correct frame-address mask must therefore remove NX from the physical address even on a permitted data read.

The source currently uses `entry & ~0xfff` for a 4 KiB leaf and for following a nonleaf table. That clears low attribute bits but retains high bits such as NX. The independent probe demonstrates a data translation with a leaf of `0x8000000000008007` returning `0x8000000000008234`, rather than physical `0x8234`. Large-page branches use explicit address masks. This is a concrete difference between branches, not a speculative warning or a claim that NX is supposed to become a physical address.

## Accessed and dirty bits are writes performed by the walker

Translation can mutate page tables. The walker sets accessed bit five on traversed entries that lack it and dirty bit six on a written leaf. These updates let an operating system observe use without recording every application access in software. They also mean that page-table memory is not immutable merely because the guest operation is a read.

In the first cold walk of the example, the probe observes four entry reads and four accessed-bit write attempts. A read leaves the leaf's dirty bit clear; a subsequent write sets it. The inspected implementation casts the return from `write_pte` to void. A physical backing that rejects those writes therefore does not cause translation to fail. A separate probe characterization reproduces success while the accessed bits remain absent. Correcting this requires a defined failure policy and tests for table-memory side effects, not only checking the returned physical address.

The walker contains no allocation and no cache lookup. Its temporary state is a table address, one entry and a level index. It does not establish multiprocessor atomicity for accessed/dirty updates, reserved-bit validation, five-level paging or all control-register transition rules. The presence of `tlb_gen` elsewhere in the CPU cannot be used to attribute a hardware-like TLB implementation to this function.

## Fault classification and partial memory operations

| Translation result | Meaning in this implementation | Wrapper action |
|---|---|---|
| 0 | Translation succeeded | Access physical backing |
| −1 | Presence or permission failure | Set CR2 and request page fault |
| −2 | Noncanonical paged address | Request general protection |
| −3 | Physical table read failed | Halt with unmapped exit and record CR2 |

The page-fault error records relevant present/protection, write, user and instruction-fetch conditions. For example, a missing user write reports six: write plus user, with present clear. A user read denied by an ancestor's supervisor-only permission reports five: protection plus user. An NX-denied user instruction fetch reports twenty-one: protection plus user plus instruction fetch. These values are checked by the source probe rather than inferred from a successful build.

`chris_va_read` and `chris_va_write` loop over chunks bounded by 4 KiB physical-page offsets, even for a translation ending in a large page. A zero-length access returns immediately. Otherwise each chunk translates and accesses physical memory before the next chunk is examined. If the second page is absent, the first chunk has already been read into the destination or written into guest memory. The probe reproduces two retained bytes on a four-byte write spanning a missing second page. This is observable helper behavior; it is not blanket certification of x86 instruction-level fault atomicity.

When `cpu->delivering` is nonzero, wrappers return failure without recursively raising another exception. `chris_raise` separately attempts delivery and then a double-fault path; failure of both leads to a triple-fault exit. Its exception-frame implementation is simplified and does not establish every privilege-transition rule. The MMU probe stubs delivery deliberately, so it checks requested vector and error code without claiming successful guest handler entry.

## How the kernel creates and shares mappings

`mm_init` records the current CR3 physical root, initializes its lock and translation-invalidation runtime, and marks mapping support ready. `mm_map_cr3` rejects an unavailable subsystem, zero root and unaligned virtual or physical addresses. Under `mm_lock`, it obtains intermediate tables through `ensure_table_flags`, allocating and zeroing missing tables. User mappings propagate the user bit through ancestors before installing the leaf. This is why adding MM_USER only to a leaf would be insufficient.

Intermediate allocation can fail and return an error. Tables already installed earlier in the walk are not rolled back in that function, so error handling must distinguish an absent requested leaf from an unchanged entire tree. `mm_map_cr3` does not itself perform a translation shootdown after installing its leaf. Whether the target address space is inactive or whether a caller must invalidate translations depends on the calling path; the mapping helper alone cannot prove safe replacement of an active mapping.

`mm_clone_kernel_space` allocates a new root and copies entries 256 through 511 from the kernel root. It shares the referenced kernel-half subtrees rather than recursively duplicating them. This creates an ownership constraint: freeing a process root must not free the shared kernel hierarchy. The header explicitly separates freeing user intermediate tables from ownership of leaf frames, which remain associated with the process page list.

`proc_map_user` rejects virtual addresses at or above `0x0000800000000000` and adds MM_USER. `proc_switch` restricts process switching to the bootstrap processor because its scheduling state is global; it then calls `mm_switch`, whose inline assembly writes CR3 with a compiler memory clobber. That clobber constrains compiler motion but does not substitute for a multiprocessor invalidation protocol. Mapping, switching, unmapping and physical-page reclamation are distinct operations with distinct synchronization requirements.

## Descriptors and scope of current protection

The kernel GDT contains kernel code/data, user data/code and a two-slot TSS descriptor. `gdt_init` zeroes a 104-byte TSS, initializes RSP0 to the kernel stack top, places the I/O-map offset beyond the structure, loads the GDT, reloads segments and loads TR. It verifies the resulting TSS selector. These fields provide ingredients for controlled entry; they do not eliminate the need to audit stack ownership when scheduling or supporting multiple processors.

The IDT holds 256 sixteen-byte gates. Ordinary initialization uses attribute `0x8e`; `idt_set_user_gate` uses `0xee`, changing gate privilege while retaining the interrupt-gate type and presence. Gate DPL controls software invocation; it is not the same as making an interrupt handler execute at the caller's privilege. Every gate here uses IST zero. That observation identifies which stack-selection facility is configured, without asserting a separate emergency stack that the source does not install.

The source probe `python scripts/check_mmu.py --source .source` passed 22 contract checks and reproduced three explicitly named gaps. Its RAM is synthetic and exception delivery is stubbed. The result establishes the documented walker behavior at the declared revision; it does not establish kernel boot, complete page-fault recovery or privilege isolation. The [Intel system programming manuals](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html) remain the normative reference for permissions, faults and transitions. Dedicated chapters must develop allocation, shootdowns, exception frames and reclamation before those topics can be regarded as completely documented.
