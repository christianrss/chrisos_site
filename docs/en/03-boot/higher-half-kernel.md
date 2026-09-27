---
id: higher-half-kernel
lang: en
type: technical-chapter
volume: 03-boot
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/linker.ld
  - kernel/metal/start.c
  - kernel/metal/bootinfo.c
  - kernel/metal/bootinfo.h
  - kernel/metal/mm.c
  - kernel/metal/mm.h
  - kernel/metal/pmm.c
  - kernel/metal/gdt.c
  - kernel/metal/smp.c
  - compiler/jit/jit.c
  - compiler/chrisld/chrisld.c
  - docs/chrisvm-boot-protocol.md
  - makefile
symbols:
  - kstart
  - __kernel_start
  - __kernel_end
  - __stack_top
  - bootinfo_phys_to_virt
  - mm_init
  - mm_virt_to_phys
  - mm_kernel_cr3
  - mm_clone_kernel_space
  - mm_switch
depends_on:
  - linker-script
  - x86-64-memory-privilege
  - limine
  - boot-information
related:
  - page-table-layout
  - hhdm
  - virtual-memory
  - physical-memory
  - address-spaces
  - tlb
  - power-on-kstart
---

# Higher-half kernels, canonical addresses and ChrisOS

## Scope

ChrisOS is linked to execute at:

~~~text
0xffffffff80000000
~~~

This address is not chosen because physical RAM exists there.

It is a **virtual address** in the upper canonical portion of the x86-64 address space.

The production kernel therefore depends on several layers agreeing simultaneously:

~~~text
compiler
    emits code compatible with the kernel code model

linker
    assigns high virtual addresses

ELF
    records those addresses in PT_LOAD and e_entry

Limine
    allocates physical pages
    builds page tables
    maps those pages at the ELF virtual addresses

CPU
    enters long mode with paging active
    and executes kstart at the mapped higher-half address
~~~

If any of those layers disagree, the kernel does not merely behave incorrectly later. It can fail on the first instruction fetch or first global-data access.

![Higher-half kernel address relationships](../../assets/diagrams/higher-half-kernel-en.svg)

## Physical address and virtual address are different identities

A physical address identifies a location on the processor/platform physical address bus.

A virtual or linear address is the address used by executing software before page translation.

With paging active:

~~~text
virtual address
      |
      v
page-table walk
      |
      v
physical address
~~~

The same physical page may have more than one virtual alias.

The same virtual address can map to different physical pages in different CR3 address spaces.

Therefore an address printed by the linker is not automatically a physical address.

## The linked kernel address

kernel/metal/linker.ld begins the output layout with:

~~~text
. = 0xffffffff80000000;
__kernel_start = .;
~~~

This establishes a virtual link address.

Functions, constants, mutable data and BSS receive addresses at or above this location according to the linker script.

The executable entry kstart is therefore a high virtual address.

## Signed interpretation

As an unsigned 64-bit integer:

~~~text
0xffffffff80000000
=
18446744071562067968
~~~

Interpreted as a two's-complement signed 64-bit value:

~~~text
0xffffffff80000000
=
-2147483648
=
-2 GiB
~~~

This is exactly the lower boundary of the top 2 GiB of the 64-bit address space.

That fact is relevant to GCC's kernel code model.

## GCC kernel code model

The production build uses:

~~~text
-mcmodel=kernel
~~~

GCC defines this model for code that runs in the negative 2 GiB of the x86-64 address space.

ChrisOS chooses the bottom of that region:

~~~text
0xffffffff80000000
~~~

and grows upward.

This compiler model permits efficient addressing assumptions that would not be valid if the kernel were linked arbitrarily anywhere in the 64-bit space.

## Code model is not paging mode

The compiler code model and the CPU page-table mode are separate concepts.

~~~text
-mcmodel=kernel
    compiler assumption about code/data addresses

4-level paging
    hardware translation structure

higher-half mapping
    page-table content
~~~

The code model does not create mappings.

The linker does not create page tables.

The bootloader or kernel memory manager creates the translations.

## Why fno-pic and fno-pie also matter

The production build uses:

~~~text
-fno-pic
-fno-pie
~~~

and produces a fixed-address ET_EXEC kernel.

The current ChrisOS image is therefore not a relocatable PIE kernel whose base can be arbitrarily chosen at boot.

The linked virtual addresses are intended runtime virtual addresses.

Moving the kernel to a different virtual base would require a compatible rebuild or a deliberate relocation design.

## Long mode virtual addresses

In x86-64 long mode, addresses carried in 64-bit registers are not necessarily all valid linear addresses.

The architecture implements some number of virtual-address bits.

Addresses used for memory references must be in **canonical form**.

With the 4-level paging model used by current ChrisOS boot paths, the architectural model is the traditional 48-bit canonical form.

## 48-bit canonical form

For a 48-bit virtual-address implementation:

~~~text
bit 47
    |
    +-- if 0:
    |      bits 63:48 must all be 0
    |
    +-- if 1:
           bits 63:48 must all be 1
~~~

This sign-extension rule creates two canonical ranges.

## Lower canonical half

The lower canonical range is:

~~~text
0x0000000000000000
through
0x00007fffffffffff
~~~

These addresses have bit 47 equal to zero and upper bits zero.

Current ChrisOS user executables live in a tiny region of this lower half.

## Upper canonical half

The upper 48-bit canonical range is:

~~~text
0xffff800000000000
through
0xffffffffffffffff
~~~

These addresses have bit 47 equal to one and bits 63:48 all one.

The ChrisOS kernel address:

~~~text
0xffffffff80000000
~~~

lies well inside this upper canonical range.

## The canonical hole

Between the lower and upper ranges lies a large set of non-canonical bit patterns.

For 48-bit canonical addressing:

~~~text
0x0000800000000000
through
0xffff7fffffffffff
~~~

is non-canonical.

Software must not treat this as ordinary usable linear address space.

A reference using a non-canonical address faults according to the instruction/context rules before it can behave like a normal page-table miss.

## LA57 caveat

x86-64 can support five-level paging on processors implementing LA57.

That expands the implemented linear-address width and changes the canonical split.

Current ChrisOS documentation and code paths discussed here are based on **four-level paging**.

The current Limine boot contract used by ChrisOS does not request an alternative paging mode.

The current ChrisVM v1 documentation also explicitly constructs four-level paging.

Therefore this chapter uses 48-bit canonical arithmetic for the current implementation.

## Canonicality helper

For the current four-level model, a useful conceptual test is:

~~~text
top = address >> 48
sign = bit 47

canonical if:
    sign == 0 and top == 0x0000
or
    sign == 1 and top == 0xffff
~~~

This is a mathematical model for documentation and testing.

Production code should use architecture-appropriate helpers if canonicality checks become runtime policy.

## Decomposing a 4-level virtual address

With 4-KiB pages and 4-level paging:

~~~text
63                         48 47       39 38       30 29       21 20       12 11        0
+----------------------------+-----------+-----------+-----------+-----------+------------+
| canonical sign extension   | PML4 idx  | PDPT idx  | PD idx    | PT idx    | page off   |
+----------------------------+-----------+-----------+-----------+-----------+------------+
                              9 bits      9 bits      9 bits      9 bits      12 bits
~~~

Each table level has 512 entries because 9 bits select an index.

## ChrisOS kernel-base indices

For:

~~~text
0xffffffff80000000
~~~

the current 4-level indices are:

~~~text
PML4 = 511
PDPT = 510
PD   = 0
PT   = 0
offset = 0
~~~

Therefore the kernel base lies in the final PML4 entry and the second-to-last PDPT entry within that PML4 subtree.

## One-GiB PDPT windows

A PDPT entry covers:

~~~text
512 * 2 MiB
=
1 GiB
~~~

when viewed as the next paging level.

The interval beginning at:

~~~text
0xffffffff80000000
~~~

and ending before:

~~~text
0xffffffffc0000000
~~~

occupies PDPT index 510.

The interval beginning at:

~~~text
0xffffffffc0000000
~~~

occupies PDPT index 511.

## Current high virtual windows

Current source defines several notable high addresses:

~~~text
kernel base
0xffffffff80000000

MMIO window
0xffffffff90000000

MM self-test alias
0xffffffff91000000

historical/commented JIT neighborhood
0xffffffff92000000

current JIT executable base
0xffffffffc0000000
~~~

The first four are inside:

~~~text
PML4[511] / PDPT[510]
~~~

The current JIT base begins in:

~~~text
PML4[511] / PDPT[511]
~~~

## Source-comment inconsistency in jit.c

compiler/jit/jit.c currently says:

~~~text
Kernel/Limine live in the 1GiB at 0xffffffff80000000 (PDPT[2])
...
PDPT[3] is empty.
~~~

Under actual x86-64 four-level index extraction from the canonical virtual address, those entries are:

~~~text
0xffffffff80000000 -> PDPT[510]
0xffffffffc0000000 -> PDPT[511]
~~~

The comment appears to be using a local/relative numbering intuition rather than architectural PDPT indices, or it is stale.

The executable addresses themselves are not changed by this comment.

This chapter uses the architectural indices.

## PML4 upper-half convention

A common higher-half design places kernel mappings in upper PML4 entries while leaving lower entries available for user address spaces.

ChrisOS follows this pattern in mm_clone_kernel_space.

The function creates a fresh PML4 and copies entries:

~~~text
for i = 256 .. 511:
    dst[i] = src[i]
~~~

The lower half is not copied.

## Meaning of the 256/256 split

A 512-entry PML4 can be divided into:

~~~text
entries 0..255
    lower canonical half

entries 256..511
    upper canonical half
~~~

For the four-level canonical model.

By copying entries 256 through 511, ChrisOS shares the current kernel-side mappings into a newly created address space while leaving the lower half available for process-specific mappings.

## Kernel address-space sharing

Conceptually:

~~~text
kernel CR3
PML4:
  [0..255]   kernel's current lower-half state
  [256..511] kernel mappings

clone for process
PML4:
  [0..255]   initially empty / process-specific
  [256..511] copied kernel mappings
~~~

This is a common architectural shape for higher-half kernels.

It allows kernel code to remain mapped across process address-space switches.

## Shared entries are shared page-table subtrees

mm_clone_kernel_space copies PML4 entry values.

It does not deep-copy all upper-half page tables.

Therefore the new PML4 points to the same lower-level page-table subtrees for those kernel mappings.

This means later modifications to shared kernel mapping structures can be visible across cloned spaces depending on which level is changed.

The ownership and synchronization implications belong to the virtual-memory and address-space chapters.

## CR3

CR3 contains the physical base of the current top-level page table plus architecture-defined control bits.

At boot, Limine has already created page tables.

ChrisOS does not currently build a fresh kernel root before mm_init.

Instead mm_init executes:

~~~text
mov %cr3, cr3
mm_cr3_phys = cr3 & MM_ADDR_MASK
~~~

The kernel therefore **adopts the bootloader-created root**.

## Adoption versus ownership

This is an important distinction.

The page tables are initially created by Limine.

ChrisOS then:

- records their physical root;
- walks them;
- allocates new lower-level page tables when mappings are missing;
- writes entries into the hierarchy;
- creates MMIO mappings;
- creates JIT mappings;
- copies the upper PML4 half into process roots.

The bootloader hierarchy has become operational kernel state.

## Current page-table ownership problem

Because the inherited hierarchy is still active and mutated by ChrisOS, bootloader memory associated with it cannot simply be reclaimed.

The boot-information chapter defines this as an **adopted** resource.

A future clean ownership transition requires creating a new kernel-owned root and switching CR3.

## table_from_phys

Page-table entries contain physical addresses.

The CPU page-table walker accesses them physically.

Kernel software, however, needs a virtual address to edit their bytes.

ChrisOS uses:

~~~text
table_from_phys(phys)
    ->
bootinfo_phys_to_virt(phys)
~~~

This converts the physical page-table address through the HHDM.

## HHDM

HHDM means Higher Half Direct Map.

Limine provides an offset.

For eligible mapped physical memory, the basic relation is:

~~~text
virtual = physical + hhdm_offset
~~~

ChrisOS stores the bootloader-provided offset in bootinfo.

bootinfo_phys_to_virt then uses it to obtain a software-accessible virtual alias.

## Kernel higher-half mapping and HHDM are not the same mapping

This distinction is critical.

The kernel ELF is mapped at addresses beginning near:

~~~text
0xffffffff80000000
~~~

The HHDM is a direct mapping from physical addresses to another higher-half virtual region chosen/provided by the boot protocol.

These serve different purposes.

~~~text
kernel mapping
    maps the kernel image according to ELF virtual addresses

HHDM
    maps physical memory through a direct physical-to-virtual offset
~~~

A physical page belonging to kernel data may therefore be reachable through multiple virtual aliases.

## Virtual aliasing

Suppose a physical page P backs part of the kernel.

Possible aliases can include:

~~~text
kernel linked address K
    -> physical P

HHDM address H + P
    -> physical P
~~~

Both virtual addresses refer to the same physical bytes.

This is legal but creates considerations for cache attributes, permissions and reasoning about pointer identity.

Ordinary WB aliases with consistent attributes are generally manageable; MMIO must not be treated as arbitrary HHDM RAM.

## HHDM is not a universal cast

Current bootinfo_phys_to_virt is intentionally simple.

Conceptually it performs:

~~~text
phys + hhdm_offset
~~~

But the Limine mapping contract determines which physical classes are guaranteed to be present in the HHDM for the selected base revision.

The previous chapters document that current code is too permissive in some firmware paths.

Therefore:

~~~text
physical address
+
HHDM offset
~~~

is not a universal replacement for deliberate MMIO or firmware mapping policy.

## Why page tables use HHDM

Page-table frames are ordinary physical memory allocated by the PMM.

The kernel must write them.

Using the HHDM means the kernel does not need to create a temporary mapping every time it allocates a page-table page.

The physical address remains what goes into a page-table entry, while the HHDM alias is used by C code to edit that page.

## Walking a virtual address

mm_virt_to_phys walks the currently adopted hierarchy.

For a normal 4-KiB page:

~~~text
PML4 entry
    |
PDPT entry
    |
PD entry
    |
PT entry
    |
physical page base + page offset
~~~

The function also handles large-page leaves at the PDPT and PD levels.

## Huge-page awareness

Current mm_virt_to_phys checks the PS bit.

It recognizes:

~~~text
1-GiB style leaf at PDPT level

2-MiB style leaf at PD level

4-KiB leaf at PT level
~~~

This matters because bootloader-created mappings may use large pages.

A kernel cannot assume every inherited mapping is represented by a 4-KiB PT entry.

## Limine mappings before mm_init

By the time kstart executes:

- long mode is active;
- paging is active;
- the kernel ELF virtual addresses are mapped;
- HHDM mappings exist according to the boot protocol;
- framebuffer mapping exists;
- the bootloader's page tables are active.

Otherwise C code linked at the higher-half address could not execute.

## Entry at high RIP

The ELF e_entry contains the linked kstart address.

Limine transfers control with RIP set to that mapped higher-half location.

The CPU performs instruction fetch translation through the already active page tables.

Therefore higher-half execution begins **before** ChrisOS calls mm_init.

mm_init discovers/adopts the existing translation state; it does not create the initial ability to execute kstart.

## Why this ordering matters

A common beginner model is:

~~~text
kernel starts
then enables paging
then jumps higher
~~~

That is valid for some kernels and boot methods.

It is not the current ChrisOS Limine path.

Current ChrisOS receives a prepared long-mode/paging environment from Limine and starts directly in the linked higher-half image.

## The production boot path

Conceptually:

~~~text
firmware
    |
Limine
    |
parse kernel.elf
    |
allocate physical backing
    |
construct higher-half mappings
    |
construct HHDM
    |
enable/enter required x86-64 state
    |
set CR3
    |
set stack
    |
RIP = ELF e_entry = kstart
    |
ChrisOS
~~~

ChrisOS begins after the paging environment exists.

## Framebuffer mapping example

bootinfo stores the framebuffer virtual address supplied by Limine.

mm_init calls:

~~~text
fb_phys = mm_virt_to_phys(boot->fb_addr)
~~~

This is a useful demonstration that:

~~~text
framebuffer virtual address
!=
framebuffer physical address
~~~

The current page-table hierarchy is used to recover the backing physical address.

## Why framebuffer physical identity matters

If ChrisOS later replaces the inherited page tables, it needs enough information to recreate necessary mappings.

Remembering only a bootloader virtual pointer is insufficient once those page tables are gone.

The BootSnapshot design therefore proposes preserving physical framebuffer identity.

## MMIO window

ChrisOS defines:

~~~text
MMIO_WINDOW = 0xffffffff90000000
~~~

and reserves a small virtual interval beginning there for explicit MMIO mappings.

This is still in the higher half, but it is conceptually different from the linked kernel image and HHDM.

## Explicit MMIO mapping

map_mmio_page creates a mapping from a selected higher-half virtual page to a device physical page with flags including cache-control policy.

This is preferable to blindly dereferencing:

~~~text
hhdm_offset + device_phys
~~~

because MMIO needs explicit mapping semantics and memory-type consideration.

## Higher half is a namespace, not one mapping type

ChrisOS uses high virtual addresses for several different purposes:

~~~text
kernel ELF image
HHDM aliases
MMIO window
self-test alias
JIT executable window
AP stacks
other kernel-managed virtual regions
~~~

The term higher-half describes where these virtual addresses live, not a single universal translation rule.

## Current JIT window

Current JIT code uses:

~~~text
JIT_VIRT_BASE = 0xffffffffc0000000
~~~

This is the start of the final 1-GiB PDPT slot in PML4[511].

The JIT uses separate aliases:

~~~text
writable HHDM alias
    for code emission

executable JIT alias
    for execution
~~~

This is a W^X-oriented design.

## JIT dual mapping

For a JIT buffer:

~~~text
physical pages P

write pointer:
    HHDM(P)
    writable

execute pointer:
    JIT virtual window
    executable mapping
~~~

The same backing pages can be viewed under different virtual permissions.

The JIT chapter handles synchronization and W^X details.

## High virtual windows require collision management

Hard-coded virtual regions can collide if the project grows without a central layout plan.

Current notable constants already include kernel, MMIO, MM test, JIT and AP-stack regions.

A mature virtual-memory architecture should document/reserve these ranges centrally.

The higher half is enormous, but accidental overlap is still possible.

## Canonical-window arithmetic should be checked

When defining a new high virtual constant, verify:

- canonical form;
- alignment;
- PML4/PDPT/PD/PT indices;
- non-overlap with existing regions;
- compatibility with compiler code-model assumptions if code/data symbols can land there;
- expected user/kernel accessibility flags.

The checker for this chapter encodes representative address decomposition.

## Kernel/user split is policy

The x86-64 architecture does not inherently say:

~~~text
lower half = user
upper half = kernel
~~~

That is operating-system policy.

ChrisOS follows this conventional policy in mm_clone_kernel_space and in its user executable address choices.

The page-table U/S bit enforces privilege access, not the numerical half by itself.

## Supervisor bit still matters

A high virtual address is not automatically supervisor-only.

Page-table entries control whether user-mode access is permitted.

Similarly, a low address can be supervisor-only.

The numerical split is a layout convention that simplifies reasoning; protection still comes from page-table permissions.

## NX still matters

Likewise, a higher-half page is not automatically executable.

The NX bit controls instruction fetch where supported/enabled.

Current ChrisOS uses explicit MM_NX for several non-code mappings.

Segment and page permissions must cooperate.

## CR0.WP

The write-protect bit influences supervisor writes to read-only pages.

A complete kernel protection model requires:

- page-table W bit;
- CR0.WP behavior;
- NX;
- U/S;
- executable image segment permissions.

Higher-half placement alone provides no write protection.

## Canonical address does not mean mapped address

A canonical virtual address can still be unmapped.

Canonicality only means the bit pattern is architecturally valid as a linear address.

Translation can still fail because:

- PML4 entry absent;
- PDPT entry absent;
- PD entry absent;
- PT entry absent;
- permissions deny access;
- reserved-bit fault;
- NX violation.

## Non-canonical address is a different failure class

A non-canonical linear address is invalid before ordinary page translation can provide a normal mapping.

This distinction matters when diagnosing exceptions.

A high pointer can fail because it is:

~~~text
non-canonical
or
canonical but unmapped
or
canonical and mapped but permission-denied
~~~

These are different bugs.

## Higher half and relocations

The compiler emits relocations under the assumptions of the kernel code model.

The linker resolves symbols to addresses near 0xffffffff80000000.

For a PC-relative reference:

~~~text
S + A - P
~~~

can remain small even though both S and P are numerically high.

This is one reason RIP-relative addressing works efficiently for nearby kernel code/data.

## Absolute references

Absolute relocations may contain the full high canonical address.

The native linker must preserve the correct 64-bit value.

Truncation that might accidentally appear harmless for low addresses can completely break higher-half references.

## Signed 32-bit relationships

The kernel code model depends on assumptions related to the top 2-GiB region and addressing forms available to x86-64.

ChrisOS choosing exactly:

~~~text
-2 GiB
~~~

as its base is therefore not arbitrary decoration.

It is aligned with the compiler model.

## Higher half and linker-defined symbols

__kernel_start, __kernel_end and __stack_top all receive high virtual addresses.

Code that references them is referencing linked virtual addresses.

If PMM needs physical occupancy, it cannot simply reinterpret those values as physical addresses.

The boot memory map remains the authority for reserved physical ranges.

## Current PMM behavior

pmm_init prints:

~~~text
pmm kernel_virt __kernel_start .. __kernel_end
~~~

for diagnostics.

But it does not convert that linked virtual interval into physical pages and reserve it directly.

Instead physical memory containing the executable is protected because Limine marks it as:

~~~text
LIMINE_MEMMAP_EXECUTABLE_AND_MODULES
~~~

and PMM reserves that memory-map type.

This separation is correct in concept:

~~~text
linker symbols
    describe virtual image extent

Limine memory map
    describes physical occupied ranges
~~~

## Duplicate executable reservation loop

Current pmm_init reserves EXECUTABLE_AND_MODULES in the general reserved-type loop and then iterates again specifically over EXECUTABLE_AND_MODULES and marks the range used a second time.

Because pmm_reserve_page is idempotent with respect to an already used bitmap bit, this does not double-count free pages.

It is redundant source structure, not a separate higher-half mapping.

## HHDM versus kernel symbols in PMM

The PMM allocator works in physical page numbers.

When it needs to touch an allocated page's bytes during self-test, it obtains a virtual pointer through HHDM.

This yields a clean separation:

~~~text
allocator identity:
    physical

software access:
    HHDM virtual alias
~~~

The linked kernel virtual addresses are not used as the allocator's physical identity.

## New process address spaces

mm_clone_kernel_space allocates a new physical PML4 page through PMM.

The kernel edits that page via HHDM.

It copies upper-half PML4 entries from the inherited kernel root.

Then user code can populate lower-half mappings.

The object therefore has:

~~~text
physical identity:
    CR3 value

kernel editing pointer:
    HHDM alias

mapped contents:
    lower user half + shared upper kernel half
~~~

This is a direct example of the three address identities coexisting.

## CR3 is physical

The value loaded into CR3 is a physical address of the top-level page table, subject to architecture-defined low control bits/features.

It is not an HHDM pointer.

It is not the PML4's linked virtual address.

Current code masks it with MM_ADDR_MASK to obtain the table physical base.

## mm_switch

mm_switch takes:

~~~text
cr3_phys
~~~

and writes it directly to CR3.

This API naming correctly exposes the physical nature of the value.

A caller must not pass an HHDM virtual pointer.

## HHDM access to CR3 table

After obtaining the physical root, ChrisOS can edit the PML4 by:

~~~text
table_from_phys(mm_cr3_phys)
~~~

which produces an HHDM pointer.

Thus:

~~~text
CR3
    physical address P

CPU page walker
    uses P physically

kernel C code
    accesses table bytes at HHDM(P)
~~~

The distinction should remain explicit in all MM code.

## Initial stack is another bootloader mapping

At entry, Limine provides a valid stack.

The current linker also reserves a one-MiB region and defines __stack_top.

gdt.c assigns:

~~~text
tss.rsp0 = __stack_top
~~~

but that does not prove the BSP immediately switched its current RSP to the linker-reserved stack at initial entry.

The boot-information chapter therefore keeps BSP stack ownership as an explicit transition requirement.

## AP stacks

AP startup has a different path.

ChrisOS allocates AP stacks and establishes known virtual locations/ownership for them.

Higher-half virtual layout therefore grows beyond the main kernel ELF mapping.

The SMP chapter handles the exact AP handoff.

## Limine HHDM offset is runtime data

Unlike the kernel base, the HHDM offset is not hard-coded in linker.ld.

ChrisOS requests it from Limine and stores:

~~~text
info.hhdm_offset = hhdm->offset
~~~

Therefore source code should not assume one specific HHDM base unless that value is explicitly part of the boot protocol/configuration.

## Why a runtime HHDM offset is useful

The kernel can convert ordinary physical RAM pages using one relation without embedding a platform-specific direct-map base in every subsystem.

This also separates:

~~~text
kernel virtual layout
    fixed by linker

direct-map layout
    supplied by boot environment
~~~

## Future BootSnapshot relationship

A normalized BootSnapshot should preserve:

- HHDM offset;
- exact classes/ranges guaranteed direct-mapped;
- kernel executable virtual range;
- kernel physical backing information if needed;
- framebuffer virtual and physical identities;
- initial CR3 provenance until replacement.

This makes address-space ownership explicit.

## Kernel-owned page-table transition

A future ownership-clean boot should eventually:

1. copy/normalize boot data;
2. initialize PMM;
3. allocate a new PML4;
4. map the kernel ELF ranges with intended permissions;
5. build the desired HHDM;
6. map framebuffer;
7. map required MMIO;
8. map current stack and transition to kernel-owned stack;
9. switch CR3;
10. verify translations;
11. release inherited bootloader page tables when safe.

This is the real completion of higher-half ownership.

## Mapping the executing code during CR3 switch

Before switching to a new root, the new root must map the current instruction address.

Because RIP is already in the higher half, the new root must contain the higher-half kernel mapping **before** the CR3 write.

Otherwise the instruction immediately after the CR3 switch cannot be fetched.

## Mapping the current stack during CR3 switch

The current RSP must also remain valid.

The safest sequence is usually to ensure a kernel-owned stack is mapped in both the old and new address spaces, switch RSP deliberately, then switch or coordinate CR3 according to the chosen design.

The exact transition must be designed so neither instruction fetch nor stack access falls through an unmapped address.

## GDT, IDT and TSS pointers

Descriptor-table registers contain linear addresses of descriptor structures.

If a new page-table root is installed, those addresses must remain mapped.

Similarly:

- IDT entries point to handler addresses;
- TSS may point to kernel stack addresses;
- global variables referenced immediately after switch must remain mapped.

A CR3 handoff needs a complete live-state mapping audit.

## APs and page-table transition

Replacing the kernel root becomes harder once multiple CPUs are running.

Each CPU can have CR3 state and TLB entries.

Therefore a kernel-owned page-table handoff is simplest before APs are fully released into general runtime.

If performed later, it requires coordinated SMP/TLB transitions.

## TLB consequences

Writing CR3 changes translation context and flushes or invalidates relevant non-global translations according to x86 rules and enabled features.

Current ChrisOS already has runtime TLB shootdown machinery for mapping changes across CPUs.

A boot-time root replacement can be simpler if done before normal SMP concurrency.

## Global pages

The architecture supports global-page semantics when enabled.

A mature kernel can use them for mappings that persist across CR3 changes.

Current higher-half documentation should not assume ChrisOS already has a complete global-page optimization policy unless source explicitly implements it.

Correctness comes before such optimization.

## Process CR3 and kernel mappings

When a process runs with its own CR3, the upper-half kernel entries copied by mm_clone_kernel_space keep kernel code/data reachable during transitions into kernel mode.

This avoids having to switch to a completely separate kernel address space on every syscall/interrupt in the current architecture.

## User access prevention

Those shared high mappings still need supervisor-only permissions.

Copying upper-half PML4 entries does not by itself prove every leaf is protected.

The U/S bits throughout the page-table path determine user accessibility.

The address-spaces chapter should audit these permissions.

## Why higher-half kernels are useful

A higher-half kernel provides several architectural advantages:

- clear virtual separation from ordinary user addresses;
- stable kernel virtual addresses across process address spaces;
- easier shared-kernel mapping policy;
- lower-half space available for user programs;
- direct-map and kernel-service windows can be organized in the upper half;
- null/low-address bugs are less likely to alias kernel text directly.

These are design benefits, not security guarantees by themselves.

## Higher half does not hide the kernel

The kernel's address can be predictable.

Current ChrisOS uses a fixed base.

Higher-half placement is not address-space randomization.

It does not prevent an attacker or bug from knowing where kernel code is located.

## No current KASLR

Because linker.ld fixes the base and the kernel is non-PIE:

~~~text
KASLR = not implemented by this design
~~~

Adding KASLR would require a relocation-compatible executable model and careful early-boot support.

That is a separate feature.

## Canonical arithmetic for the kernel base

The kernel base has:

~~~text
bit 47 = 1

bits 63:48 = 0xffff
~~~

so it is canonical in the current 48-bit model.

The signed value is -2 GiB, matching GCC's documented kernel model region.

The checker validates all three facts.

## Address decomposition examples

For current source:

| Virtual address | PML4 | PDPT | PD | Role |
|---|---:|---:|---:|---|
| 0xffffffff80000000 | 511 | 510 | 0 | kernel base |
| 0xffffffff90000000 | 511 | 510 | 128 | MMIO window |
| 0xffffffff91000000 | 511 | 510 | 136 | MM self-test |
| 0xffffffff92000000 | 511 | 510 | 144 | historical JIT neighborhood |
| 0xffffffffc0000000 | 511 | 511 | 0 | current JIT base |

This table is mechanically reproduced by the checker.

## Why PD index changes by 2 MiB

Each PD entry represents 2 MiB of virtual span at the next level.

The difference:

~~~text
0x10000000
=
256 MiB
~~~

between kernel base and MMIO window corresponds to:

~~~text
256 MiB / 2 MiB
=
128 PD entries
~~~

which matches the MMIO address PD index 128 within PDPT[510].

## JIT boundary

The difference between:

~~~text
0xffffffff80000000
and
0xffffffffc0000000
~~~

is exactly:

~~~text
1 GiB
~~~

so the PDPT index advances from 510 to 511.

This is the correct architectural interpretation of the current constants.

## ChrisVM v1 incompatibility

The ChrisVM boot protocol v1 identity-maps guest RAM in low addresses and explicitly rejects the production ChrisOS ELF when its p_vaddr is:

~~~text
0xffffffff80000000
~~~

The documented error is:

~~~text
higher-half ELF is outside boot protocol v1
~~~

This is not a kstart bug.

It is a boot-protocol capability gap.

## Why ChrisVM cannot simply set RIP high

Setting RIP to the high e_entry is insufficient.

ChrisVM must also create mappings for:

- each higher-half PT_LOAD;
- boot information expected by the kernel;
- HHDM or equivalent normalized boot service;
- required framebuffer mapping;
- page-table structures with the same architectural contract.

Otherwise the first fetch or data access fails.

## ChrisVM protocol v2 target

The repository already defines the next milestone conceptually:

~~~text
load a higher-half ELF
publish explicit boot info
preserve the same architectural state
~~~

The desired endpoint is that the kernel does not care whether execution backend is ChrisCPU or ChrisHV.

The same principle should apply to boot source after normalization.

## Native linker and higher half

ChrisLd can accept:

~~~text
load_addr = 0xffffffff80000000
~~~

and place that value in p_vaddr.

This proves it can emit a high virtual address.

It does **not** prove full production higher-half support.

The native linker still needs:

- production section layout;
- Limine request segment;
- synthetic linker symbols;
- stack reservation;
- complete relocation support;
- boot validation.

## Native compiler and code model

A self-hosted kernel toolchain must also emit machine code compatible with the high-address model.

It is not enough for ChrisLd to assign high p_vaddr values if KCC emits addressing sequences that only work for low addresses.

Higher-half self-hosting is therefore a compiler + object + linker + boot problem.

## Differential higher-half tests

A useful native-toolchain gate should include code that references:

- nearby functions;
- nearby globals;
- linker-defined high symbols;
- addresses crossing text/data section boundaries;
- 64-bit absolute values;
- PC-relative relocations.

The resulting executable should be inspected for correct high canonical addresses.

## Reproducible checker

scripts/check_higher_half_examples.py validates:

1. 48-bit canonicality arithmetic for the current four-level model.
2. lower and upper canonical boundaries.
3. kernel base equals signed -2 GiB.
4. kernel base PML4/PDPT/PD/PT indices.
5. MMIO/test/JIT high-window indices.
6. one-GiB transition from PDPT[510] to PDPT[511].
7. linker base and production compiler flags.
8. inherited-CR3 adoption in mm_init.
9. HHDM physical-to-virtual path.
10. upper-half PML4 copying in mm_clone_kernel_space.
11. current ChrisVM v1 higher-half rejection.
12. the current jit.c PDPT comment mismatch.

The checker is a mathematical/source-contract test.

It does not prove the actual bootloader page tables on every machine.

## Current-source findings

At the reviewed revision:

~~~text
kernel virtual base
    fixed at 0xffffffff80000000

compiler
    -mcmodel=kernel
    -fno-pic
    -fno-pie

initial kernel CR3
    inherited from Limine

page-table editing
    performed through HHDM aliases

process kernel mappings
    copied from PML4 entries 256..511

MMIO window
    0xffffffff90000000

JIT executable window
    0xffffffffc0000000

ChrisVM v1
    cannot boot the production higher-half ELF
~~~

The architecture is functional but still depends on bootloader-owned initial paging state.

## Validation boundary

This chapter is reconciled with:

~~~text
ChrisOS main
da3df29cb397932c43d32373871fb9380e688ade
~~~

External architecture/compiler theory is based on the AMD64 architecture model and GCC x86 code-model documentation.

Run:

~~~text
python scripts/check_higher_half_examples.py --source .source
~~~

## Review triggers

Review this chapter when:

- the linker base changes;
- -mcmodel changes;
- PIE/KASLR is introduced;
- Limine paging-mode requests are added;
- LA57 is enabled;
- HHDM policy changes;
- kernel-owned page tables replace inherited CR3;
- mm_clone_kernel_space changes the kernel/user split;
- MMIO/JIT/AP-stack windows move;
- jit.c paging comments are corrected;
- ChrisVM v2 gains higher-half loading;
- ChrisCPU boots the real production kernel;
- native KCC/ChrisLd produce a booting higher-half image.

## Primary references

- AMD64 Architecture Programmer's Manual, canonical address rules and long-mode paging.
- GCC x86 Options, kernel code model.
- Limine boot protocol.
- ChrisOS source files listed in front matter.
