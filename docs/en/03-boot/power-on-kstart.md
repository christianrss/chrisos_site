---
id: power-on-kstart
lang: en
type: technical-chapter
volume: 03-boot
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/start.c
  - kernel/metal/serial.c
  - kernel/metal/bootinfo.c
  - kernel/metal/gdt.c
  - kernel/metal/idt.c
  - kernel/metal/irq.c
  - kernel/metal/pit.c
  - kernel/metal/pmm.c
  - kernel/metal/mm.c
  - kernel/metal/apic.c
  - kernel/metal/ioapic.c
  - kernel/metal/smp.c
  - kernel/metal/sse_init.c
  - kernel/metal/proc.c
  - kernel/metal/linker.ld
  - docs/chrisvm-boot-protocol.md
  - makefile
symbols:
  - kstart
  - serial_init
  - bootinfo_init
  - gdt_init
  - idt_init
  - syscall_init
  - pic_init
  - pit_init
  - pmm_init
  - mm_init
  - heap_init
  - proc_init
  - apic_init
  - smp_init
depends_on:
  - reset-firmware
  - uefi
  - limine
  - boot-information
  - elf-linking
  - linker-script
  - higher-half-kernel
related:
  - kernel-model
  - gdt-tss
  - idt-exceptions
  - physical-memory
  - virtual-memory
  - interrupts-smp
---

# From power-on to kstart: the complete ChrisOS boot handoff

## Scope

kstart is the first C function in the ChrisOS kernel, but it is not the beginning of the machine history.

Before its first instruction executes, multiple independently owned execution environments have already existed:

~~~text
hardware reset
    ↓
firmware
    ↓
UEFI or BIOS boot path
    ↓
Limine
    ↓
ELF loading
    ↓
higher-half mappings
    ↓
bootloader-owned GDT / stack / page tables
    ↓
RIP = kstart
    ↓
ChrisOS kernel initialization
~~~

This chapter reconstructs that path chronologically and follows the exact current kstart sequence until ChrisOS reaches its desktop event loop.

The central problem is ownership. Some state is created by hardware or firmware. Some is created by Limine and borrowed by ChrisOS. Some is later replaced, adopted or created by the kernel itself.

![Power-on to kstart timeline](../../assets/diagrams/power-on-kstart-en.svg)

## Boot is an ownership transfer

Boot is not only a chain of function calls. Each stage creates resources and assumptions that the next stage may depend on.

Examples include CPU mode, page tables, stack, descriptor tables, framebuffer mappings, memory-map data, HHDM mappings, AP descriptors and interrupt-controller state.

A robust kernel needs to know which resources it owns, which it has adopted and which remain borrowed.

## Stage 0: architectural reset

At hardware reset the processor is not executing ChrisOS. Firmware owns the machine.

There is no ChrisOS page-table hierarchy, GDT, IDT, heap, process table, scheduler or filesystem.

The reset-firmware chapter covers the architectural reset vector and the compatibility machinery that exists before a 64-bit operating-system kernel can run.

## Stage 1: firmware

Firmware initializes enough platform state to discover and launch a boot environment.

On UEFI systems this includes standardized services for storage, executable loading, graphics, allocation and memory-map discovery.

On BIOS systems the internal path differs substantially.

ChrisOS deliberately does not expose those differences to kstart. Limine normalizes both paths into one boot protocol.

## Stage 2: Limine

The firmware or an earlier boot stage loads Limine.

Limine becomes responsible for parsing the ChrisOS executable, finding embedded requests, allocating physical memory, mapping the kernel and handing execution to the ELF entry point.

ChrisOS therefore starts from a Limine contract rather than directly from a UEFI or BIOS ABI.

## Current Limine base revision

The current source requests:

~~~text
LIMINE_BASE_REVISION(3)
~~~

bootinfo_init verifies that the requested revision was supported.

The current Limine specification classifies base revisions 0 through 5 as deprecated, while still defining their behavior. ChrisOS is therefore intentionally using an older defined contract.

This matters because guarantees introduced in revision 5 or revision 6 must not be silently attributed to a revision-3 kernel.

## Revision 3 HHDM rule

Base revision 3 introduced a restrictive HHDM.

The HHDM directly maps only specified memory-map classes, including ordinary usable RAM, bootloader-reclaimable memory, executable/modules memory and framebuffer memory.

It does not establish that every physical address in the platform can be dereferenced through physical plus HHDM offset.

The current bootinfo code explicitly warns that the LAPIC physical address must not be treated this way.

## Stage 3: embedded requests

ChrisOS embeds:

~~~text
request start marker
base revision 3 tag

framebuffer request
HHDM request
memory-map request
MP request
executable command-line request

request end marker
~~~

The linker script places and retains these objects in the Limine request section.

Limine writes response pointers into them before kernel entry.

## Requests form a pre-entry communication channel

The request section is writable because the bootloader updates response fields.

The final values observed by kstart are therefore a combined product of the linked kernel image and bootloader execution.

They are not compile-time constants.

## Stage 4: ELF loading

The production image is an ELF64 ET_EXEC for EM_X86_64 with ENTRY(kstart).

Its linker script starts at:

~~~text
0xffffffff80000000
~~~

and divides the image into:

~~~text
requests  RW
text      RX
data      RW
~~~

Limine maps those PT_LOAD segments in the higher half with permissions derived from the ELF program headers.

## Virtual address is not physical placement

The address 0xffffffff80000000 is a virtual link address.

Limine chooses physical backing and constructs page tables so that instruction fetches and data accesses at the linked virtual addresses reach the correct physical pages.

## Stage 5: HHDM

Limine creates the Higher Half Direct Map according to the requested base revision and returns its offset.

ChrisOS later stores:

~~~text
info.hhdm_offset = hhdm->offset
~~~

The offset is runtime state, not a linker constant.

## Stage 6: page tables

Before kstart can execute at a high canonical address, paging must already be active.

The initial translation hierarchy is built by Limine and lives in bootloader-reclaimable memory.

Its exact internal page-table shape is not an ABI guarantee. The promised mappings are the contract.

## Stage 7: x86-64 entry state

For the current Limine x86-64 contract, relevant entry guarantees include:

~~~text
RIP
    executable entry point

64-bit execution
    active

CR0.PE
CR0.WP
CR0.PG
    enabled

CR4.PAE
    enabled

EFER.LME
EFER.LMA
    enabled

EFER.NXE
    enabled if supported

RFLAGS.IF
direction flag
VM flag
    cleared

A20
    open
~~~

ChrisOS does not request five-level paging, so current documentation assumes the default four-level mode.

## Do not import newer-revision guarantees

Limine base revision 5 strengthened several x86-64 machine-state guarantees.

ChrisOS requests base revision 3.

Therefore current ChrisOS documentation cannot assume revision-5-only promises about every unrelated CR0, CR4 or EFER bit, exact task-register state, exact LDTR state or a normalized empty IDTR.

The safe rule is:

~~~text
depend only on revision-3 guarantees
or establish the state explicitly in ChrisOS
~~~

## GDT at entry

Limine provides a valid 64-bit segmentation environment and a bootloader-provided GDT.

That GDT is in bootloader-reclaimable memory.

ChrisOS installs its own GDT early rather than treating the bootloader GDT as permanent kernel infrastructure.

## IDT at entry

For the revision relevant to ChrisOS, the protocol states that the IDT is undefined and the executable must load its own.

The current order is:

~~~text
kstart
  serial_init
  build_info_log
  bootinfo_init
  gdt_init
  idt_init
~~~

Several operations therefore execute before the kernel has installed a ChrisOS IDT.

## Early exception window

Before idt_init completes, ChrisOS performs port I/O, serial loopback, build logging, Limine-response validation, memory-map traversal, command-line parsing, serial printing and GDT/TSS installation.

Maskable interrupts are disabled, but synchronous exceptions remain possible.

CLI does not prevent page faults, general-protection faults or invalid-opcode faults.

This is a real early-boot boundary.

## Initial stack

Limine supplies RSP pointing to the top of a bootloader-reclaimable stack of at least 64 KiB unless a larger Stack Size feature is requested.

ChrisOS currently makes no Stack Size request.

The initial execution of kstart therefore runs on a bootloader-owned stack.

The protocol places an invalid zero return address on that stack. kstart is not expected to return.

## General-purpose registers

The Limine x86-64 contract sets the other general-purpose registers to zero at entry.

Normal compiled C code quickly overwrites them, so the more important persistent dependencies are RSP, page tables, descriptor state and the request-response structures.

## UEFI Boot Services are already gone

If Limine was booted through EFI, Boot Services are exited before the executable receives control.

kstart is not an ordinary UEFI application entry point.

Later firmware interaction must use persistent tables, runtime facilities with their own rules, or kernel drivers.

## Interrupt flag at entry

IF is clear when kstart begins.

That allows the BSP to initialize most of the system without maskable asynchronous interrupt delivery.

The eventual STI near the end of kstart is a major transition from serialized boot to interrupt-driven runtime.

## kstart is directly the ELF entry

The linker script says:

~~~text
ENTRY(kstart)
~~~

and start.c defines:

~~~text
void kstart(void)
~~~

There is no project-owned production assembly trampoline between Limine and this C function.

The compiler ABI matters immediately.

## Phase A: diagnostics

The first action is serial_init.

If it fails:

~~~text
CLI
HLT forever
~~~

The kernel refuses to continue without its earliest diagnostic channel.

## serial_init behavior

The current function:

1. initializes the kernel log;
2. disables UART interrupts;
3. programs the COM1 divisor;
4. selects 8N1 framing;
5. configures FIFO;
6. enters loopback;
7. writes 0xae;
8. verifies the same byte is read back;
9. exits loopback;
10. marks serial available;
11. initializes its spinlock.

No heap, PMM, APIC or scheduler is required.

## Why polling serial works early

Early serial uses port I/O and polling.

It does not depend on IDT delivery.

This is exactly the kind of primitive needed before the exception and IRQ frameworks exist.

## Build identity

After serial succeeds, kstart prints the self-host marker and calls build_info_log.

Build provenance appears before most subsystems, so later failures can be associated with a concrete kernel image.

## Phase B: bootinfo_init

The next major transition is bootinfo_init.

This validates Limine features and populates the first ChrisOS boot-information structure.

## Mandatory responses

Current source requires:

- supported base revision;
- at least one framebuffer;
- HHDM response;
- memory-map response;
- MP response;
- at least one processor;
- 32-bpp framebuffer.

Failure is fatal.

## Partial normalization

bootinfo_init copies many scalar values, but current code retains the raw memory-map response pointer.

SMP later also receives the raw MP response.

The handoff is therefore not yet fully deep-copied into kernel-owned storage.

## Boot flags

The command line can set:

~~~text
safe
nosmp
noapic
noac97
nonet
nojit
gfx.backend=...
gfx.3d=...
gfx.stress
gfx.virgl.debug
~~~

Safe mode expands into several conservative disables.

## LAPIC diagnostic

bootinfo_init prints the arithmetic HHDM-plus-LAPIC value only as a warning and explicitly says it is not a valid MMIO mapping to dereference.

It also inspects the memory-map classification around physical 0xfee00000.

This keeps RAM direct-map semantics separate from device MMIO.

## Phase C: replace the GDT

gdt_init constructs a kernel-owned GDT and TSS.

The GDT includes kernel code/data, user code/data and a 64-bit TSS descriptor.

The bootloader GDT can then cease being an architectural dependency.

## TSS RSP0

gdt_init assigns:

~~~text
tss.rsp0 = __stack_top
~~~

where __stack_top is created by linker.ld after a one-MiB stack reservation.

This defines the ring-transition stack target stored in the TSS.

It does not prove that the BSP current RSP has switched to this stack.

## GDT reload

gdt_init performs:

~~~text
LGDT
far control transfer to reload CS
reload DS / ES / SS
clear FS / GS selectors
LTR
~~~

It then verifies the task-register selector.

This is a clear transition from bootloader-owned to kernel-owned descriptor state.

## Phase D: install the IDT

idt_init builds 256 gates, installs the NMI entry at vector 2 and executes LIDT.

From this point, faults can enter ChrisOS exception handling.

## Why GDT precedes IDT

IDT gates contain a code selector.

Current gates use the ChrisOS kernel-code selector, so the kernel must establish its GDT first.

## syscall_init

After the IDT exists, syscall_init changes vector 0x80 into a user-accessible software-interrupt gate.

The current syscall ABI therefore depends on the IDT path.

## Phase E: legacy PIC

pic_init executes CLI again and remaps the legacy PIC:

~~~text
master base = 0x20
slave base  = 0x28
~~~

All IRQs are masked at the end.

This avoids collisions between CPU exception vectors and hardware IRQ vectors.

## Phase F: PIT at 60 Hz

pit_init(60) installs IRQ0 handling and programs the PIT.

Its integer divisor is derived from:

~~~text
1193182 / 60
~~~

IRQ0 becomes unmasked in the PIC, while CPU IF remains clear.

## PIC mask and CPU IF are different controls

A timer interrupt needs both:

~~~text
PIC IRQ0 unmasked
and
RFLAGS.IF = 1
~~~

pit_init satisfies the first condition.

The final STI much later satisfies the second.

## PS/2

ps2_init runs after the timer setup.

Failure is nonfatal; ChrisOS logs that keyboard/mouse are unavailable and continues.

## Phase G: physical memory

The kernel executes:

~~~text
pmm_init
pmm_selftest
~~~

PMM depends on bootinfo because free/used state comes from the Limine memory map.

## Conservative PMM policy

The allocator frees only usable pages and reserves important classes again, including low memory, reserved memory, ACPI NVS, bad memory, bootloader-reclaimable memory, executable/modules memory and framebuffer memory.

## Why bootloader-reclaimable remains reserved

The initial stack and page tables still live in bootloader-reclaimable memory and remain in use.

The class cannot yet be globally returned to PMM.

## PMM self-test

The self-test allocates physical pages, accesses them through HHDM aliases, writes signatures and verifies reuse.

This jointly tests allocator state and direct-map access to ordinary RAM.

## Phase H: virtual memory

Next:

~~~text
mm_init
mm_selftest
~~~

mm_init reads CR3 and stores the physical root of the Limine-created hierarchy.

ChrisOS adopts the bootloader page tables rather than replacing them.

## Adopted hierarchy

After mm_init, ChrisOS walks and mutates the inherited tables.

It creates mappings, allocates child tables, maps MMIO and copies upper-half mappings into process roots.

The bootloader hierarchy becomes mutable kernel infrastructure.

## Framebuffer translation check

mm_init translates the framebuffer virtual address through the current tables.

Failure is fatal.

This validates one key inherited mapping.

## MM self-test

The self-test:

1. allocates a physical page;
2. maps it at MM_TEST_VIRT;
3. obtains its HHDM alias;
4. writes through one alias;
5. validates through the other;
6. maps LAPIC MMIO explicitly;
7. reads the LAPIC ID.

It checks RAM aliasing and controlled device mapping.

## Phase I: heap, SSE and processes

The next sequence is:

~~~text
heap_init
sse_bsp_init
heap_selftest
proc_init
~~~

Only after PMM and MM work does ChrisOS build higher-level memory and process state.

## Phase J: graphics

ChrisOS obtains bootinfo and initializes graphics from the Limine framebuffer virtual address, dimensions, pitch and 32-bpp format.

The framebuffer is still a bootloader-provided mapping.

Afterward virtio_gpu_boot is attempted as an additional graphics path.

## First deliberate frame

The kernel clears to:

~~~text
0x00101828
~~~

and presents it.

This is the first deliberate graphical state in the current kstart flow after graphics initialization.

## Phase K: APIC, jobs and SMP

The sequence is:

~~~text
apic_init
ioapic_init
job_init
smp_init
smp_job_selftest
~~~

This occurs after memory management is established.

## Current IOAPIC limitation

ioapic_init currently only logs that the PIC still routes IRQs.

Full IOAPIC routing is not implemented by this function today.

The call name must not be treated as proof of a completed APIC routing architecture.

## SMP still uses raw Limine MP data

smp_init consumes the MP response exposed by bootinfo_mp_response.

That data remains bootloader-owned.

A future BootSnapshot should copy CPU topology information needed after boot.

## Phase L: long interrupts-off subsystem phase

After the SMP self-test, kstart executes CLI and initializes:

~~~text
ACPI
storage
filesystem
installer
language runtime
audio
AC97
compiler preparation
~~~

The source explicitly says compiler preparation should occur with interrupts off because timer preemption interferes with the guest compiler.

## ACPI after MM

ACPI probing runs only after explicit virtual-memory and MMIO primitives exist.

That ordering is especially important under revision 3 because HHDM is restrictive.

## Storage and filesystem

The kernel initializes storage and filesystem, performs installer tests/automation and, when CFS is active, writes the accumulated boot log to:

~~~text
SYS/BOOT.LOG
~~~

Boot observability becomes persistent at this point.

## Language runtime

lang_init establishes the language subsystem.

lang_make_cc runs before interrupts are enabled so the compiler-building phase is not preempted by the timer.

## Phase M: final STI

Near the end:

~~~text
STI
~~~

enables maskable interrupts on the BSP.

This is the transition from serialized initialization to interrupt-driven runtime.

By this point ChrisOS has its own GDT, IDT, syscall gate, IRQ handlers, timer programming, memory managers, heap, process layer, graphics, APIC/SMP state, filesystem and language runtime.

## AP interrupt release

Immediately after BSP STI:

~~~text
smp_release_ap_irqs
~~~

allows AP worker contexts to participate in their interrupt path.

AP existence and AP interrupt participation are separate milestones.

## Desktop startup

The final sequence is:

~~~text
desktop_init
desktop_boot_apps
gfx_present
optional net_init
desktop marker
desktop_run
~~~

desktop_run is the persistent runtime loop and a practical boot-completion boundary.

## Network is optional

net_init failure logs a warning and does not abort the desktop.

Networking is not a prerequisite for boot completion.

## Exact current high-level order

The current start.c order is:

~~~text
serial_init
build_info_log

bootinfo_init
boot flag handling

gdt_init
idt_init
syscall_init
pic_init
pit_init
ps2_init

pmm_init
pmm_selftest
mm_init
mm_selftest
heap_init
sse_bsp_init
heap_selftest
proc_init

gfx_init
virtio_gpu_boot
gfx_clear
gfx_present

apic_init
ioapic_init
job_init
smp_init
smp_job_selftest

CLI
acpi_probe
storage_init
fs_init
install_selftest
install_auto
persistent boot log
lang_init
speaker_off
optional ac97_init

gfx_clear
gfx_present
lang_make_cc

STI
smp_release_ap_irqs
desktop_init
desktop_boot_apps
gfx_present
optional net_init
desktop_run
~~~

The checker introduced by this chapter verifies critical anchors directly from start.c.

## Dependency graph

Important dependencies include:

~~~text
bootinfo_init
    -> pmm_init
    -> mm_init
    -> heap_init
    -> proc_init

gdt_init
    -> idt_init
    -> syscall_init

pic_init
    -> pit_init

mm_init
    -> explicit MMIO mapping
    -> APIC/SMP

job_init
    -> smp_init

fs_init
    -> persistent boot log

lang_init
    -> lang_make_cc

most runtime initialization
    -> final STI
~~~

## Borrowed state at entry

| Resource | Initial owner | Current ChrisOS behavior |
|---|---|---|
| GDT | Limine | replaced by gdt_init |
| initial stack | Limine | initially retained |
| page tables / CR3 | Limine | adopted by mm_init |
| HHDM | Limine mapping | retained and used |
| framebuffer mapping | Limine | retained and used |
| memory-map response | Limine memory | referenced after normalization |
| MP response | Limine memory | referenced by SMP |

This explains why bootloader-reclaimable memory remains conservatively reserved.

## GDT transition

~~~text
Limine GDT
    ↓
gdt_init
    ↓
ChrisOS GDT
    ↓
CS/data selectors reloaded
    ↓
TSS loaded
~~~

This ownership transfer is relatively complete.

## IDT transition

~~~text
undefined boot entry state
    ↓
idt_init
    ↓
ChrisOS owns vectors 0..255
~~~

This is one of the sharpest boot-state boundaries.

## Stack transition remains incomplete

linker.ld reserves one MiB and gdt_init puts __stack_top into TSS.RSP0.

start.c does not explicitly switch the BSP current RSP to __stack_top.

Therefore the TSS ring-transition stack does not prove current BSP stack ownership.

## Page-table transition remains incomplete

The current flow is:

~~~text
Limine builds CR3 hierarchy
    ↓
mm_init reads it
    ↓
ChrisOS mutates it
~~~

There is no current complete build-new-root, switch-CR3, free-old-root sequence.

The page tables are adopted rather than replaced.

## Bootinfo transition remains incomplete

Scalar values are copied, but raw memory-map and MP responses remain referenced.

A full BootSnapshot must deep-copy the state needed after boot.

## Three major ownership gaps

~~~text
stack
    borrowed -> kernel-owned

page tables
    adopted -> kernel-owned

boot responses
    borrowed -> deep-copied snapshot
~~~

Closing these transitions would make much more bootloader-reclaimable memory actually reclaimable.

## Early-IDT hardening opportunity

serial, build logging, bootinfo and GDT setup all run before idt_init.

One future hardening path is a minimal emergency IDT installed immediately at entry.

This is not current behavior.

## Early stack-switch hardening opportunity

Another improvement is moving the BSP to a kernel-owned stack shortly after entry.

That would shorten the lifetime of a borrowed critical resource.

Current start.c does not explicitly do this.

## Base-revision modernization

The current Limine specification marks base revision 3 deprecated.

Moving to a newer base revision is an architectural migration because mapping and entry guarantees change.

HHDM, firmware-table access, ACPI and reclaim policies must be reviewed together.

## BIOS and UEFI converge before kstart

Before Limine, BIOS and UEFI differ significantly.

After handoff, ChrisOS intentionally sees one path:

~~~text
same kernel ELF
same request section
same kstart
same bootinfo_init
same subsystem sequence
~~~

This is one of the core advantages of a boot protocol.

## ChrisVM must reproduce the handoff

ChrisVM v1 can execute a simpler low-address guest contract but rejects the production higher-half ChrisOS ELF.

A future ChrisVM protocol must reproduce enough of the machine and boot contract for the same production kstart to execute without emulator-specific shortcuts.

## Minimum internal ChrisVM boot contract

A compatible path needs at least:

- higher-half PT_LOAD mappings;
- long-mode execution;
- valid initial stack;
- suitable GDT state;
- safe pre-IDT behavior;
- HHDM-like physical-memory access;
- memory map;
- framebuffer mapping and metadata;
- MP metadata;
- command line;
- correct CR3;
- request/response semantics or a semantically equivalent internal representation.

Forcing RIP to kstart is not sufficient.

## Failure classes by stage

Before serial, failure may appear as a silent hang, reset or triple fault.

After serial but before IDT, the last serial message can identify the stage, but exception diagnostics may still be unavailable.

After IDT, ChrisOS panic handling can report exceptions.

After PMM/MM, allocation and translation self-tests localize memory failures.

After filesystem initialization, logs can become persistent.

## Stable boot markers

A mature automated gate should emit stable milestones such as:

~~~text
entry
serial-ok
bootinfo-ok
gdt-ok
idt-ok
pmm-ok
mm-ok
heap-ok
gfx-ok
smp-ok
fs-ok
runtime-ok
desktop
~~~

Current source has many useful logs but not yet one formal milestone protocol.

Such markers would benefit QEMU, ChrisVM and real-hardware smoke tests.

## Reproducible checker

scripts/check_power_on_kstart_examples.py validates:

1. ENTRY(kstart).
2. Limine base revision 3.
3. request delimiter order.
4. mandatory response checks.
5. critical start.c ordering.
6. gdt_init before idt_init.
7. idt_init before syscall_init.
8. pic_init before pit_init.
9. PMM before MM.
10. MM before heap, process and SMP.
11. CLI before the ACPI/storage/language phase.
12. lang_make_cc before final STI.
13. final STI before desktop runtime.
14. PIC remap to 0x20 and 0x28.
15. pit_init(60).
16. inherited CR3 adoption.
17. TSS.RSP0 using __stack_top.
18. absence of an explicit BSP RSP switch to __stack_top in start.c.
19. current IOAPIC stub behavior.
20. ChrisVM v1 rejection of the production higher-half ELF.

This is a source-contract checker, not a replacement for hardware boot testing.

## Current findings

At the reviewed revision:

~~~text
Limine base revision
    3

initial BSP stack
    bootloader-reclaimable

initial GDT
    bootloader-reclaimable

initial IDT
    undefined by revision-3 contract

initial CR3
    Limine-created hierarchy

ChrisOS GDT
    installed early

ChrisOS IDT
    installed after serial + bootinfo + GDT

PMM
    reserves bootloader-reclaimable

MM
    adopts inherited CR3

BSP interrupts
    enabled only near the end

IOAPIC routing
    not fully implemented

desktop_run
    steady-state destination
~~~

## Ownership timeline

~~~text
RESET
  firmware-owned machine
        ↓

LIMINE
  bootloader-owned:
    page tables
    stack
    GDT
    protocol responses
        ↓

KSTART EARLY
  serial
  bootinfo
  ChrisOS GDT
  ChrisOS IDT
        ↓

MEMORY
  PMM owns allocator state
  MM adopts Limine CR3
        ↓

RUNTIME BUILD
  heap/process/graphics/SMP/fs/lang
        ↓

STI
  asynchronous runtime
        ↓

DESKTOP
~~~

## Validation boundary

This chapter is reconciled with:

~~~text
ChrisOS main
da3df29cb397932c43d32373871fb9380e688ade
~~~

and with the current Limine protocol specification.

Because ChrisOS requests base revision 3, newer revision-only guarantees are excluded from current implementation claims.

Run:

~~~text
python scripts/check_power_on_kstart_examples.py --source .source
~~~

## Review triggers

Review this chapter when:

- kstart ordering changes;
- Limine base revision changes;
- requests are added or removed;
- an emergency IDT is added;
- BSP stack switching is introduced;
- bootloader page tables are replaced;
- BootSnapshot becomes fully deep-copied;
- PIC/PIT policy changes;
- IOAPIC routing becomes complete;
- SMP release sequencing changes;
- interrupts are enabled earlier;
- ChrisVM gains a production-equivalent higher-half handoff;
- ChrisCPU or ChrisHV boots the real kernel through kstart.

## Primary references

- Limine boot protocol, current specification.
- AMD64 architecture documentation for long-mode execution state.
- ChrisOS source files listed in front matter.
