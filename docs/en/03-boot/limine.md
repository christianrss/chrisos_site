---
id: limine
lang: en
type: technical-chapter
volume: 03-boot
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/bootinfo.c
  - kernel/metal/bootinfo.h
  - kernel/metal/linker.ld
  - kernel/metal/start.c
  - kernel/metal/smp.c
  - kernel/metal/pmm.c
  - kernel/metal/mm.c
  - iso_root/boot/limine/limine.conf
  - makefile
  - .cursor/install.sh
symbols:
  - kstart
  - bootinfo_init
  - bootinfo_get
  - bootinfo_phys_to_virt
  - bootinfo_memmap_count
  - bootinfo_memmap_entry
  - bootinfo_mp_response
  - smp_init
  - pmm_init
  - mm_init
depends_on:
  - uefi
  - reset-firmware
related:
  - boot-information
  - acpi-platform
  - elf-linking
  - linker-script
  - higher-half-kernel
  - interrupts-smp
  - physical-memory
  - hhdm
  - installation-real-hardware
---

# Limine boot protocol

## Scope

Limine is the current boundary between platform boot firmware and the ChrisOS kernel.

On the intended physical-hardware path, UEFI loads the Limine EFI image. Limine then loads the ChrisOS ELF64 executable, constructs the entry virtual-memory environment, resolves protocol requests embedded in the kernel image, publishes response structures, exits UEFI Boot Services, and transfers control to the kernel entry point.

ChrisOS therefore does not receive boot state in a hand-written register convention.

It declares data structures inside its own executable:

~~~text
ChrisOS ELF
  |
  +-- request start marker
  +-- base revision tag
  +-- framebuffer request
  +-- HHDM request
  +-- memory-map request
  +-- MP request
  +-- executable command-line request
  +-- request end marker
~~~

Limine discovers these structures, writes response pointers into them, prepares the x86-64 environment, and jumps to the ELF entry point.

![Limine request/response and ChrisOS handoff](../../assets/diagrams/limine-en.svg)

The current ChrisOS revision pins Limine commit:

~~~text
ee5d29cd0a8034612dcd1df3f00052480db785c5
~~~

from the v9.x-binary branch. The pinned header supports LIMINE_API_REVISION up to 3, and ChrisOS selects API revision 3.

The kernel separately requests Limine base revision 3.

Those two numbers describe different contracts.

## Limine the bootloader versus the Limine boot protocol

The Limine project provides a bootloader and is the reference implementation of the Limine boot protocol.

The protocol itself is a specification that other compliant bootloaders could implement.

ChrisOS should therefore distinguish:

~~~text
Limine bootloader implementation
from
Limine boot protocol ABI
~~~

The kernel source depends primarily on the protocol structures. The disk and ISO build also depend on Limine bootloader binaries and host tooling.

## Why a boot protocol exists

A 64-bit kernel needs more than an instruction pointer.

Useful boot state includes:

- memory topology;
- virtual mapping information;
- framebuffer information;
- processor topology;
- firmware-derived tables;
- modules;
- executable metadata;
- boot arguments.

Without a protocol, every bootloader/kernel pair would need a private ABI.

Limine defines this ABI as discoverable request and response structures.

## Three different revision domains

Limine-related source exposes several independent notions of revision.

They must not be conflated.

### Header API revision

The pinned limine.h supports a compatibility macro:

~~~text
LIMINE_API_REVISION
~~~

ChrisOS defines:

~~~text
#define LIMINE_API_REVISION 3
~~~

and the build also supplies:

~~~text
-DLIMINE_API_REVISION=3
~~~

This selects names and structure/API compatibility in the pinned C header.

For example, older API revisions used names such as SMP or kernel-file while newer compatibility modes use MP or executable-file naming.

### Protocol base revision

ChrisOS embeds:

~~~text
LIMINE_BASE_REVISION(3)
~~~

Base revision controls global protocol semantics such as:

- request delimiter behavior;
- identity-map availability;
- HHDM coverage;
- firmware-table pointer semantics;
- portions of machine state at entry.

This is not the same thing as the C header API revision.

### Individual request revision

Each request structure contains its own revision field.

All five current ChrisOS feature requests use:

~~~text
.revision = 0
~~~

A feature revision evolves one feature's request/response shape without being the same as the protocol base revision.

The version model is therefore:

~~~text
C header API revision
        |
protocol base revision
        |
per-feature request revision
~~~

All three can have different values.

## Current pinned header

.cursor/install.sh documents the exact dependency:

~~~text
LIMINE_SHA =
ee5d29cd0a8034612dcd1df3f00052480db785c5

branch:
v9.x-binary

comment:
API revision 3
~~~

The script fetches that Limine revision when third_party/limine/limine.h is absent.

This pin is important for reproducibility.

Building against an arbitrary newer limine.h is not equivalent to building the reviewed ChrisOS source.

## Current upstream protocol state

The current Limine protocol specification defines base revisions 0 through 6 and marks base revisions 0 through 5 deprecated.

ChrisOS still requests base revision 3 because that is the contract paired with its pinned Limine dependency and current implementation.

This does not make current boots invalid.

It does mean protocol modernization is now explicit technical debt.

A future migration should update:

- pinned Limine bootloader;
- limine.h;
- API compatibility usage;
- base revision;
- memory-map assumptions;
- ACPI/RSDP handling;
- machine-state documentation;
- native KCC parsing expectations;
- CI source-contract checks.

## Request discovery

Protocol requests are static objects embedded in the loaded kernel image.

ChrisOS begins the request region with:

~~~text
LIMINE_REQUESTS_START_MARKER
~~~

and closes it with:

~~~text
LIMINE_REQUESTS_END_MARKER
~~~

Under base revision 3, request delimiters are mandatory when present.

Only requests in the delimited loaded-image region are intended to be accepted.

## Why alignment matters

The protocol specifies request markers and base-revision tags on 8-byte aligned boundaries.

The C objects are naturally based on 64-bit words.

The linker script places the entire request section at a 4-KiB boundary, which is stronger alignment than required for the section start.

Individual compiler-emitted objects still need compatible alignment.

## Source-level placement

bootinfo.c uses attributes such as:

~~~text
__attribute__((used, section(".limine_requests")))
~~~

The used attribute prevents the compiler from discarding an otherwise apparently unreferenced request object.

The section attribute groups request objects into the expected linker section.

These attributes are part of the boot ABI, not cosmetic annotations.

## Linker preservation

kernel/metal/linker.ld contains:

~~~text
.limine_requests : ALIGN(4K) {
    KEEP(*(.limine_requests_start))
    KEEP(*(.limine_requests))
    KEEP(*(.limine_requests_end))
} :requests
~~~

KEEP prevents linker garbage collection from dropping the request metadata.

The section is attached to the requests PT_LOAD program header.

A self-hosted linker that omits these semantics can create a syntactically valid ELF that Limine cannot boot correctly.

## Request segment permissions

The linker defines:

~~~text
requests PT_LOAD FLAGS(6)
~~~

ELF program-header flag value 6 is:

~~~text
PF_R | PF_W
~~~

and not executable.

This is appropriate because Limine needs to write response pointers into request structures.

The protocol metadata is data, not kernel code.

## Base revision tag handshake

A base revision tag contains three 64-bit values.

Conceptually the kernel writes:

~~~text
magic_0
magic_1
requested_revision
~~~

The bootloader indicates successful support by modifying the final component to zero.

Current ChrisOS checks:

~~~text
LIMINE_BASE_REVISION_SUPPORTED
~~~

and panics if revision 3 was not accepted.

The pinned header also exposes loaded-base-revision metadata, but ChrisOS does not currently report it.

## Why the support check belongs before responses

If the bootloader cannot honor the requested base revision, pointer and mapping semantics may differ from what the kernel expects.

The global base revision must therefore be validated before treating feature responses as protocol data.

Current bootinfo_init performs the support test first.

## The five current feature requests

ChrisOS currently embeds these requests:

| Request | Required by bootinfo? | Main consumer |
|---|---:|---|
| framebuffer | yes | graphics / bootinfo |
| HHDM | yes | physical-memory access |
| memory map | yes | PMM / diagnostics |
| MP | yes | SMP |
| executable command line | optional | boot flags |

The first four are hard boot dependencies.

The command line is intentionally optional.

## Missing requests are architectural information

The current kernel does not request:

- bootloader information;
- firmware type;
- custom stack size;
- paging mode;
- executable file metadata;
- modules;
- RSDP;
- SMBIOS;
- EFI System Table;
- EFI memory map;
- executable load address;
- TSC frequency;
- entropy.

A later subsystem must not assume those responses already exist.

## Entry ABI

The current Limine protocol specifies the architecture ABI used at handoff.

For x86-64 it uses:

~~~text
System V ABI
without FP/SIMD for protocol interaction
~~~

This matches the general ABI family used by the ChrisOS kernel.

The host build also disables MMX/SSE/SSE2 for the early kernel compilation profile and initializes floating-point/SIMD state explicitly later.

## ELF entry point

ChrisOS does not issue an Entry Point feature request.

Therefore Limine enters at the executable-format entry point.

The linker defines:

~~~text
ENTRY(kstart)
~~~

so the ELF e_entry resolves to kstart.

This is why kstart(void) receives no boot-info argument.

Protocol state is found through the static request structures that Limine modified before entry.

## Executable placement

The Limine protocol maps executables in the higher half at or above:

~~~text
0xffffffff80000000
~~~

Non-relocatable executables must already be linked for suitable higher-half virtual addresses.

ChrisOS starts exactly at:

~~~text
0xffffffff80000000
~~~

in its linker script.

That directly matches the protocol's non-relocatable higher-half model.

## Program-header permissions

Limine reflects ELF PT_LOAD permissions into page mappings.

For ChrisOS:

~~~text
requests -> RW
text/rodata -> RX load class
data/bss -> RW
~~~

Execute protection on x86-64 depends on NX availability.

This provides useful initial segment separation before the kernel's own MM subsystem fully owns virtual memory.

## Physical placement is not the virtual link address

The ELF is virtually linked into the higher half.

Its physical placement is selected by the bootloader.

The protocol does not imply:

~~~text
physical == virtual
~~~

A future consumer that needs the executable physical base should request the executable-address feature rather than reverse-engineer bootloader page tables.

## Default paging mode

ChrisOS does not issue a paging-mode request.

For x86-64, the Limine default is four-level paging.

This matches the current ChrisOS MM implementation, which explicitly walks:

~~~text
PML4
 -> PDPT
 -> PD
 -> PT
~~~

This compatibility is currently implicit.

A stronger future contract would either request four-level paging explicitly or teach the kernel to support five-level paging.

## Current MM assumption

Functions such as mm_translate begin at a PML4 and use four indices.

They are not LA57-aware.

A future change that requests five-level paging therefore requires a corresponding MM redesign.

The boot protocol and MM assumptions must evolve together.

## Initial x86-64 machine state

At entry, rip is the executable entry point and the bootloader establishes 64-bit execution with paging enabled.

The protocol specifies baseline facts including:

- a 64-bit code segment;
- data selectors;
- FS and GS bases zero;
- IF clear;
- VM clear;
- DF clear;
- CR0.PE enabled;
- CR0.WP enabled;
- CR0.PG enabled;
- CR4.PAE enabled;
- EFER.LME and EFER.LMA enabled;
- NX enabled if available;
- A20 open;
- legacy PIC IRQs masked;
- UEFI Boot Services exited when booted through EFI.

ChrisOS can begin as normal freestanding x86-64 C because these preconditions already exist.

## What base revision 3 does not guarantee

Later base revisions strengthen x86 machine-state guarantees.

Base revision 5, for example, specifies more complete control-register, RFLAGS, descriptor-table, APIC and IOMMU state.

ChrisOS requests base revision 3.

Documentation must therefore not retroactively attribute every newer guarantee to the current handoff.

The kernel initializes important state such as GDT and IDT itself.

## Initial stack

Limine supplies an entry stack in bootloader-reclaimable memory.

The current protocol specifies at least 64 KiB unless a Stack Size request asks for more.

ChrisOS makes no Stack Size request.

Therefore the guaranteed bootloader entry-stack size is the default protocol minimum, not the one-MiB region reserved by the linker.

The linker-reserved __stack_top is later used for TSS rsp0 and belongs to a different ownership stage.

## Invalid return address

The protocol places an invalid zero return address on the x86-64 entry stack before entering the executable.

A kernel entry function should never return.

kstart eventually transfers into the kernel runtime rather than returning to the loader.

## General-purpose registers

Other general-purpose registers are defined by the Limine entry contract rather than used as an ad-hoc boot-info channel.

Because kstart has no parameters, boot state is obtained from the request objects.

## Descriptor table ownership

Limine provides entry descriptor-table state.

ChrisOS quickly runs gdt_init and idt_init and assumes ownership of its own GDT, TSS and IDT.

The bootloader's descriptor tables are an entry mechanism, not a permanent kernel subsystem.

## HHDM

The Higher Half Direct Map request returns an offset.

For a physical address that is actually represented in the HHDM:

~~~text
virtual = physical + offset
~~~

Current ChrisOS implements this in bootinfo_phys_to_virt.

The offset is selected by the bootloader and must never be hardcoded.

## HHDM is not a universal physical-address cast

Base revision determines which memory classes are mapped by the HHDM.

For base revision 3, the relevant current protocol classes are:

- usable;
- bootloader reclaimable;
- executable and modules;
- framebuffer.

The first 4 GiB are not unconditionally direct-mapped.

Therefore:

~~~text
phys + hhdm_offset
~~~

is valid only for a physical range that is guaranteed to be in the HHDM.

It is not a generic ioremap operation.

## ChrisOS already documents the MMIO exception

dump_lapic_not_ram explicitly reports that:

~~~text
HHDM + LAPIC
is not a valid MMIO mapping
~~~

The LAPIC is later mapped through a dedicated MMIO mapper.

This is the correct distinction:

~~~text
RAM-like direct map
!=
device MMIO
~~~

## Base revision 3 and the ACPI gap

The current ACPI probe calls bootinfo_phys_to_virt while scanning legacy physical firmware addresses.

But base revision 3 does not generally HHDM-map reserved, ACPI-reclaimable or ACPI-NVS regions.

A real machine can therefore satisfy:

~~~text
RSDP physical address exists
but
physical + HHDM offset is not mapped
~~~

This is a portability gap.

The preferred fix is to add the Limine RSDP request rather than depend on legacy physical scanning.

## Base revision 4 mapping changes

The current upstream protocol extends HHDM coverage in base revision 4 to include:

- reserved-mapped;
- ACPI reclaimable;
- ACPI NVS.

It also adds LIMINE_MEMMAP_RESERVED_MAPPED.

This is a concrete benefit of modernizing beyond base revision 3.

The migration must still audit every memory-type assumption in ChrisOS.

## Framebuffer response

The framebuffer response can describe:

- address;
- width;
- height;
- pitch;
- bits per pixel;
- memory model;
- channel masks;
- EDID;
- alternate modes at higher response revisions.

ChrisOS currently chooses the first framebuffer and requires 32 bpp.

## Current framebuffer simplification

bootinfo_init copies:

- address;
- width;
- height;
- pitch;
- bpp.

It does not retain:

- memory model;
- red/green/blue mask sizes;
- channel shifts;
- EDID;
- mode list.

The current graphics abstraction is narrower than the Limine response.

Physical hardware should therefore validate the pixel format rather than treating all 32-bpp framebuffers as identical.

## Framebuffer address

The framebuffer address is already a protocol-visible mapped virtual address.

ChrisOS stores it directly.

Later mm_init translates that virtual address back to its physical backing with mm_virt_to_phys.

This works while the inherited mappings remain installed.

## Framebuffer pitch

The code preserves the returned pitch.

It does not assume:

~~~text
pitch == width * 4
~~~

This is necessary for firmware framebuffers.

## Memory-map response

The memory map contains:

~~~text
entry_count
entries[]
~~~

Each entry contains:

~~~text
base
length
type
~~~

The entry base is a physical address.

The pointer to the entry object is a protocol pointer.

These are different address domains.

## Current memory types

The pinned header defines:

| Type | Meaning |
|---:|---|
| 0 | USABLE |
| 1 | RESERVED |
| 2 | ACPI_RECLAIMABLE |
| 3 | ACPI_NVS |
| 4 | BAD_MEMORY |
| 5 | BOOTLOADER_RECLAIMABLE |
| 6 | EXECUTABLE_AND_MODULES |
| 7 | FRAMEBUFFER |

memmap_type_name understands these types.

## bootinfo retains the original memory-map response

bootinfo_init stores:

~~~text
static struct limine_memmap_response *memmap_response;
~~~

Later functions continue traversing that original response.

The memory map is not deep-copied into kernel-owned storage.

This affects when bootloader memory can be reclaimed.

## Limine response lifetime

The protocol places response structures and associated data in bootloader-reclaimable memory.

Reclaimable means the OS may reclaim the memory after it has stopped depending on it.

It does not mean the memory can be freed immediately at kstart.

Current ChrisOS keeps live pointers into that memory after early boot.

## Current PMM behavior

pmm_init leaves LIMINE_MEMMAP_BOOTLOADER_RECLAIMABLE reserved.

It never later releases that class.

This is conservative and safe.

The cost is permanently losing those pages from the allocator.

## Bootloader page tables are also reclaimable memory

The Limine protocol states that the bootloader page tables live in bootloader-reclaimable memory.

Current mm_init reads the inherited CR3:

~~~text
mm_cr3_phys = current CR3
~~~

and adopts those tables as the kernel page-table root.

The kernel then modifies and extends them.

Therefore reclaiming bootloader memory is not merely a matter of copying the memory-map response.

## Safe reclamation sequence

A future reclaim path needs approximately:

1. copy all durable response information;
2. finish AP handoff and remove MP response dependence;
3. construct kernel-owned page tables;
4. switch CR3;
5. stop using the bootloader entry stack;
6. prove no pointers remain into bootloader-reclaimable pages;
7. release eligible pages into PMM.

Current ChrisOS has not reached this stage.

## USABLE memory accounting

bootinfo_init sums lengths of USABLE entries into usable_bytes.

pmm_init subsequently frees only complete pages from USABLE ranges.

This cleanly separates protocol parsing from allocator geometry.

## PMM alignment policy

Usable ranges are aligned inward to complete 4-KiB pages.

Reserved ranges are aligned outward.

This prevents a page partially intersecting reserved data from being allocated.

## ACPI reclaimable memory

ACPI_RECLAIMABLE ranges begin effectively reserved because the PMM bitmap starts fully used and only USABLE ranges are released.

A future ACPI subsystem can reclaim those pages only after table lifetime has been resolved.

## HHDM self-test scope

PMM self-tests use bootinfo_phys_to_virt only on pages allocated from USABLE memory.

That is valid for base revision 3 because USABLE memory is HHDM-mapped.

The test does not imply arbitrary physical addresses are mapped.

## MP request

The MP request does more than report topology.

Its presence prompts the bootloader to bootstrap secondary processors.

The x86 response provides:

- flags;
- BSP LAPIC ID;
- CPU count;
- CPU descriptors.

Each descriptor includes:

- processor ID;
- LAPIC ID;
- goto_address;
- extra_argument.

## x2APIC request policy

Current ChrisOS sets MP flags to zero.

It therefore does not request x2APIC.

This matches current fixed-size LAPIC-ID lookup structures and xAPIC-oriented assumptions.

A future x2APIC migration must update both the boot request and the kernel interrupt/SMP data model.

## AP handoff

smp_init:

1. identifies the BSP;
2. allocates kernel-owned AP stacks;
3. assigns a logical CPU index;
4. writes extra_argument;
5. writes ap_entry to goto_address;
6. waits for APs to report online.

The bootloader performs the low-level processor bootstrap.

ChrisOS takes ownership when the AP jumps into ap_entry.

## MP pointer semantics

Limine response pointers are already provided according to the protocol pointer rules.

Current ap_info_virt contains defensive logic that adds the HHDM offset when a pointer does not look high-half.

This historical compatibility logic should eventually be reconciled to one pinned pointer interpretation rather than remaining heuristic.

## AP stack transition

Current AP code switches from the bootloader-provided AP execution stack to a PMM-backed kernel AP stack before normal worker execution.

That is a good ownership transition and reduces long-term dependency on bootloader AP stack memory.

## Executable command line

The command-line response is optional.

If present, bootinfo parses tokens including:

- safe;
- nosmp;
- noapic;
- noac97;
- nonet;
- nojit;
- gfx.stress;
- gfx.virgl.debug;
- gfx.backend=framebuffer or virtio;
- gfx.3d=auto, software or virgl.

This is the earliest configuration channel into ChrisOS policy.

## Safe mode

The safe token enables:

~~~text
nosmp
noapic
noac97
nonet
nojit
~~~

This is useful in physical bring-up because risky subsystems can be suppressed without rebuilding the kernel.

## Current Limine configuration

The repository configuration is:

~~~text
/ChrisOS
    protocol: limine
    path: boot():/boot/kernel.elf
    resolution: 1920x1080x32
~~~

It does not currently set an explicit executable command line.

The parser exists and can consume one when configured.

## Request revision zero

Every current feature request uses revision zero.

This is a conservative baseline.

The kernel should not consume fields whose semantics require higher request revisions without explicitly negotiating them.

## Response validation

bootinfo_init currently checks:

- supported base revision;
- framebuffer response presence;
- nonzero framebuffer count;
- framebuffer pointer array;
- HHDM response;
- memory-map response;
- memory-map pointer array;
- MP response;
- nonzero CPU count;
- CPU array;
- non-null memory-map entries;
- 32-bpp first framebuffer.

This is a useful validation boundary.

## Hardening opportunities

Further checks could include:

- upper bound on memory-map entry count;
- checked base + length arithmetic;
- overlap diagnostics;
- framebuffer size and pitch overflow;
- pixel-format validation;
- CPU count bounds;
- LAPIC-ID policy;
- command-line length bound;
- response revision checks.

A trusted bootloader is still an external input boundary.

## Checked range arithmetic

Any range expressed as:

~~~text
base + length
~~~

can overflow modulo 2^64.

Parser code should use a checked helper such as:

~~~text
length <= UINT64_MAX - base
~~~

before forming the end address.

The chapter checker demonstrates this arithmetic.

## Current protocol versus project pin

There are now two protocol time axes:

~~~text
ChrisOS pin
  Limine v9.x
  API revision 3
  base revision 3

current upstream protocol
  newer header model
  base revision 6 current
  base revisions 0..5 deprecated
~~~

Documentation must describe the current source truth rather than pretending the migration already happened.

## Controlled base-revision migration

A safe migration should:

1. update the pinned Limine revision;
2. update the protocol header;
3. update API compatibility code;
4. request the current base revision;
5. add new memory-map type handling;
6. add RSDP request;
7. audit HHDM behavior;
8. audit entry-state assumptions;
9. run BIOS and UEFI QEMU gates;
10. run installed-disk OVMF-only boot;
11. update real-hardware baseline.

## RSDP is the highest-priority missing request

The ACPI chapter currently depends on a legacy memory scan.

Limine already has a dedicated RSDP feature.

The desired path is:

~~~text
firmware
 -> Limine
 -> RSDP response
 -> ChrisOS ACPI parser
~~~

This avoids depending on whether legacy firmware physical regions happen to be present in the HHDM.

## Bootloader information request

A bootloader-info response could expose bootloader name/version.

ChrisOS could log:

~~~text
Bootloader: Limine <version>
Loaded base revision: <n>
~~~

This would improve reproducibility and hardware triage.

## Firmware-type request

A firmware-type response would let ChrisOS explicitly confirm whether the current boot was EFI64 or another supported firmware mode.

This is more robust than inferring the environment from deployment context.

## Executable-address request

The executable-address feature can expose physical and virtual load bases.

This is useful for:

- exact memory accounting;
- linker validation;
- boot provenance;
- relocation diagnostics.

ChrisOS currently does not request it.

## Stack-size request

The entry stack defaults to the protocol minimum because no stack-size request exists.

If early boot becomes deeper before a kernel-owned BSP stack switch, ChrisOS can either request a larger boot stack or explicitly switch to a kernel-owned stack earlier.

The second approach gives stronger ownership.

## Paging-mode request

ChrisOS implicitly depends on default 4-level paging.

An explicit paging-mode request would encode that dependency directly.

Alternatively, LA57 support requires a five-level MM implementation.

## EFI System Table request

Limine can provide the EFI System Table.

ChrisOS should request it only if there is a concrete Runtime Services design.

Preserving firmware interfaces without using them expands the lifetime and security surface unnecessarily.

## EFI memory map request

The normalized Limine memory map is enough for current PMM operation.

Raw EFI memory descriptors become relevant mainly for UEFI Runtime Services or firmware-specific attribute handling.

They should be requested when there is a real consumer.

## Self-hosting implications

The native compiler and linker must reproduce the boot ABI.

KCC must parse and compile:

- limine.h;
- request initializers;
- large 64-bit constants;
- section attributes;
- volatile global data.

ChrisLd must preserve:

- request markers;
- base revision tag;
- request objects;
- PT_LOAD permissions;
- higher-half layout;
- ELF entry.

Boot equivalence is a linker and metadata problem as much as a code-generation problem.

## KCC's own Limine dependency

KCC currently predefines:

~~~text
LIMINE_API_REVISION = 3
~~~

during preprocessing.

A Limine API migration therefore affects the compiler bootstrap path too.

It is not isolated to bootinfo.c.

## Why request objects are volatile

The source initializes response fields to zero.

An external bootloader modifies those objects before the kernel executes.

volatile prevents the compiler from treating the memory as immutable source-initialized state.

The used attribute solves object retention.

These attributes solve different problems.

## External references and linker GC

Normal compiler/linker reachability cannot see that Limine scans the loaded image for magic request structures.

Without KEEP, a linker can discard apparently unreachable protocol metadata.

This is a classic example of data being referenced by an external interpreter rather than a normal symbol relocation.

## Toward a durable BootSnapshot

A stronger internal boundary would copy the required boot state into a kernel-owned structure:

~~~text
BootSnapshot
  protocol revision
  bootloader identity
  firmware type
  framebuffer
  HHDM
  memory ranges[]
  CPUs[]
  RSDP
  SMBIOS
  executable load identity
  command line
~~~

After page-table replacement and AP handoff, all Limine-owned pointers could then be discarded.

## ChrisVM mismatch

ChrisVM boot protocol v1 does not implement Limine.

It directly establishes:

- long mode;
- page tables;
- GDT;
- stack;
- framebuffer;
- ELF entry.

It provides no request scan or Limine responses.

The real ChrisOS kernel therefore cannot use that protocol.

## ChrisVM v2 alternatives

Two useful approaches exist.

### Limine-compatible ABI

ChrisVM could scan Limine requests and populate responses.

This maximizes binary compatibility with the existing kernel.

It also couples ChrisVM to Limine protocol versions.

### Kernel-owned normalized boot ABI

ChrisOS can finish a boot-adapter layer:

~~~text
Limine adapter ----\
                    -> BootSnapshot -> kernel subsystems
ChrisVM adapter ---/
~~~

This preserves one internal kernel contract while allowing multiple external boot environments.

## Preferred long-term boundary

The cleaner design is:

~~~text
external boot environment
      |
small boot adapter
      |
kernel-owned immutable boot snapshot
      |
PMM / MM / SMP / graphics / ACPI
~~~

bootinfo.c already begins this architecture but still retains external memory-map and MP response pointers.

## Deterministic parser testing

A future refactor can separate parsing from global request objects and feed synthetic responses.

Host tests can then cover:

- unsupported base revision;
- absent mandatory response;
- null entry;
- overlapping memory maps;
- overflow;
- huge CPU count;
- framebuffer edge cases;
- command-line tokenization.

This would make the boot boundary fuzzable.

## Failure localization

Current bootinfo panic paths identify failures such as:

~~~text
unsupported base revision
framebuffer absent
HHDM absent
memory map absent
MP response absent
framebuffer not 32 bpp
MP without CPUs
null memory-map entry
~~~

Once one of these messages appears, the CPU reached kstart and the loader transferred control.

Failures before that remain firmware/loader/image-load territory.

## Current implementation matrix

| Capability | ChrisOS status |
|---|---|
| pinned Limine dependency | implemented |
| pinned v9.x API revision 3 | implemented |
| Limine base revision 3 | implemented |
| migration to current base revision 6 | not implemented |
| request start/end markers | implemented |
| dedicated request PT_LOAD | implemented |
| framebuffer request | implemented |
| HHDM request | implemented |
| memory-map request | implemented |
| MP request | implemented |
| command-line request | implemented |
| bootloader-info request | not implemented |
| firmware-type request | not implemented |
| stack-size request | not implemented |
| paging-mode request | not implemented |
| RSDP request | not implemented |
| SMBIOS request | not implemented |
| EFI System Table request | not implemented |
| EFI memory-map request | not implemented |
| executable-address request | not implemented |
| TSC frequency request | not implemented |
| entropy request | not implemented |
| deep-copy all Limine response data | not implemented |
| reclaim bootloader-reclaimable memory | not implemented |
| kernel-owned replacement page-table root | not implemented |
| x2APIC MP request | not implemented |
| ChrisVM Limine-compatible boot | not implemented |

## Reproducible checker

scripts/check_limine_examples.py validates:

1. request start/end markers;
2. base revision 3 source contract;
3. API revision 3 source/build contract;
4. exact five current feature requests;
5. request revision zero;
6. linker KEEP rules and request PT_LOAD;
7. higher-half base;
8. four-level MM dependency;
9. base-revision-3 HHDM model;
10. absence of RSDP, paging-mode and stack-size requests;
11. PMM reservation of bootloader-reclaimable memory;
12. retained Limine memory-map and MP pointers;
13. pinned Limine SHA;
14. checked physical-range arithmetic.

It is a source/protocol consistency checker, not a Limine conformance test.

## Validation boundary

This chapter is reconciled with ChrisOS main revision:

~~~text
da3df29cb397932c43d32373871fb9380e688ade
~~~

and the project's pinned Limine dependency:

~~~text
ee5d29cd0a8034612dcd1df3f00052480db785c5
~~~

The current upstream Limine protocol was also reviewed. It now treats base revision 6 as the current non-deprecated base revision and revisions 0 through 5 as deprecated.

This chapter intentionally describes the pinned ChrisOS contract first and upstream evolution second.

Run:

~~~text
python scripts/check_limine_examples.py --source .source
~~~

## Review triggers

Review this chapter when:

- the pinned Limine commit changes;
- LIMINE_API_REVISION changes;
- requested base revision changes;
- a feature request revision changes;
- RSDP/SMBIOS/firmware-type requests are added;
- paging mode becomes explicit;
- x2APIC is requested;
- bootinfo deep-copies memory-map or MP data;
- kernel-owned page tables replace inherited CR3;
- bootloader-reclaimable pages begin to be freed;
- linker request layout changes;
- ChrisLd boots a real kernel;
- ChrisVM gains a Limine-compatible or normalized real-kernel handoff.

## Primary references

- Limine Boot Protocol, official limine-protocol specification.
- Limine official protocol header.
- Pinned Limine v9.x limine.h at ee5d29cd0a8034612dcd1df3f00052480db785c5.
- ChrisOS source files listed in this chapter front matter.
