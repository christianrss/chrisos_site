---
id: boot-information
lang: en
type: technical-chapter
volume: 03-boot
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/bootinfo.c
  - kernel/metal/bootinfo.h
  - kernel/metal/pmm.c
  - kernel/metal/mm.c
  - kernel/metal/smp.c
  - kernel/metal/acpi.c
  - kernel/metal/start.c
  - docs/chrisvm-boot-protocol.md
  - docs/REAL_HARDWARE_PLAN.md
symbols:
  - bootinfo_init
  - bootinfo_get
  - bootinfo_memmap_count
  - bootinfo_memmap_entry
  - bootinfo_mp_response
  - bootinfo_phys_to_virt
  - pmm_init
  - mm_init
  - smp_init
depends_on:
  - limine
related:
  - physical-memory
  - hhdm
  - interrupts-smp
  - acpi-platform
  - higher-half-kernel
  - resource-lifetime
  - chrisvm
---

# Boot information, normalization and ownership

## Scope

Boot information is not merely a bag of values handed to the kernel.

It is a lifetime and ownership problem.

At kernel entry, ChrisOS receives data created by an external environment. Today that environment is Limine. In the future it can also be ChrisVM or another boot adapter.

The kernel must answer four different questions for every piece of boot state:

1. what fact is being communicated;
2. where the original bytes live;
3. how long those bytes remain valid;
4. whether the kernel has copied the fact into memory it owns.

Those questions determine whether memory can be reclaimed safely.

The current ChrisOS code only partially normalizes Limine state.

It copies some scalar values into struct bootinfo, but it keeps direct pointers to Limine-owned structures for the memory map and multiprocessor response.

That distinction is the center of this chapter.

![Boot information ownership transition](../../assets/diagrams/boot-information-en.svg)

## External protocol data versus kernel state

At entry, Limine is the producer.

ChrisOS is the consumer.

Conceptually:

~~~text
external boot protocol
      |
      v
raw boot responses
      |
      v
validation
      |
      v
normalization
      |
      v
kernel-owned boot snapshot
      |
      v
PMM / MM / SMP / graphics / ACPI
~~~

The current implementation stops halfway:

~~~text
Limine responses
      |
      +-- copy scalars into struct bootinfo
      |
      +-- keep memmap_response pointer
      |
      +-- keep mp_request.response pointer
~~~

This means protocol objects remain part of the live kernel state.

## What normalization means

Normalization converts bootloader-specific data into kernel-defined data.

The purpose is not merely prettier naming.

It provides architectural decoupling.

For example, instead of every subsystem depending on:

~~~text
struct limine_memmap_entry
~~~

the kernel can expose:

~~~text
struct boot_mem_range {
    uint64_t base;
    uint64_t length;
    enum boot_mem_type type;
};
~~~

Then Limine becomes one adapter rather than the data model of the entire kernel.

The same principle applies to CPUs, framebuffer description, firmware roots and command-line options.

## Ownership vocabulary

This chapter uses four ownership classes.

### Borrowed

The kernel can read the object, but the storage belongs to the bootloader.

Example today:

~~~text
memmap_response
~~~

### Copied

The kernel has duplicated required fields into its own static or allocated memory.

Example today:

~~~text
info.hhdm_offset
info.fb_width
info.cpu_count
~~~

### Adopted

The kernel begins using an object created by the bootloader as its own runtime object.

The strongest example today is the active page-table hierarchy referenced by CR3.

ChrisOS does not merely read it; the memory manager extends it.

### Reclaimable

Storage can be returned to the allocator only after no borrowed or adopted object depends on it.

This is a proof obligation, not merely a memory-map type.

## Current struct bootinfo

The current header defines a deliberately small structure:

~~~text
struct bootinfo {
    hhdm_offset
    fb_addr
    fb_width
    fb_height
    fb_pitch
    fb_bpp
    usable_bytes
    memmap_entries
    cpu_count
    bsp_lapic_id
}
~~~

These are scalar values copied from Limine responses.

Once copied, these individual fields no longer require the original response objects to remain valid.

However, other APIs still expose original response data.

## Scalar snapshot versus full snapshot

The current struct is better described as a scalar summary than a complete boot snapshot.

It omits:

- copied memory ranges;
- copied CPU descriptors;
- bootloader identity;
- firmware type;
- RSDP;
- SMBIOS roots;
- framebuffer color masks;
- framebuffer memory model;
- command-line copy;
- executable physical base;
- executable virtual base;
- protocol/base revision metadata;
- paging mode;
- provenance information.

The missing fields are not all mandatory.

The point is that the kernel currently lacks one complete internal object describing everything it intends to keep.

## Why pointer retention matters

Suppose bootinfo_init copied every memory range into kernel memory.

Then the original Limine memmap response could eventually be discarded.

But today bootinfo_memmap_entry does:

~~~text
entry = memmap_response->entries[index]
~~~

on every call.

Therefore PMM and any later consumer still require the Limine response tree.

Similarly, smp_init obtains:

~~~text
bootinfo_mp_response()
~~~

which returns the original Limine MP response.

So two major kernel subsystems still depend directly on bootloader-owned objects.

## Memory ownership graph

The current dependency graph is approximately:

~~~text
Limine bootloader-reclaimable memory
  |
  +-- memory-map response
  |      |
  |      +-- entry pointer array
  |      +-- entry objects
  |             |
  |             +--> PMM queries
  |
  +-- MP response
  |      |
  |      +-- CPU pointer array
  |      +-- per-CPU objects
  |             |
  |             +--> SMP bootstrap
  |
  +-- initial page tables
  |      |
  |      +--> active CR3
  |      +--> kernel MM modifies them
  |
  +-- entry/AP boot stacks
~~~

This graph explains why BOOTLOADER_RECLAIMABLE cannot yet simply be released.

## Lifetime categories

A robust boot architecture should classify information by lifetime.

### Entry-only

Required only before or during initial transition.

Examples can include:

- loader temporary stack metadata;
- raw protocol markers;
- transient loader handles.

### Early-boot

Needed until a kernel subsystem takes ownership.

Examples:

- raw CPU descriptors until SMP has copied topology;
- raw memory map until PMM has built its internal state;
- loader page tables until kernel-owned page tables are active.

### Persistent

Information intentionally retained for the lifetime of the kernel.

Examples:

- normalized physical-memory topology;
- framebuffer geometry;
- firmware roots;
- system identity;
- kernel image provenance.

### Conditionally reclaimable

Information needed until a subsystem finishes consuming it.

Examples:

- ACPI reclaimable regions after required tables are copied/parsed;
- bootloader-reclaimable responses after normalization.

## Current initialization order

kstart calls bootinfo_init very early.

Later major consumers are initialized in approximately this conceptual order:

~~~text
bootinfo_init
   |
GDT / IDT / interrupts
   |
PMM
   |
MM
   |
heap and runtime state
   |
graphics
   |
APIC / SMP
   |
ACPI
   |
storage / filesystem / desktop
~~~

This order creates an important design issue.

If bootloader data is to be reclaimed early, every consumer that still uses it must either:

- run before reclamation; or
- consume a kernel-owned copy.

A BootSnapshot solves the second case.

## BootSnapshot design goal

The desired internal structure should be independent of Limine.

Conceptually:

~~~text
BootSnapshot
{
    protocol;
    firmware;
    kernel_image;
    hhdm;
    framebuffer;
    memory_ranges[];
    cpus[];
    firmware_roots;
    command_line;
    provenance;
}
~~~

This is not necessarily one literal giant C struct.

It is an architectural ownership boundary.

The important property is:

~~~text
after snapshot finalization,
kernel subsystems do not require raw bootloader objects
~~~

## Snapshot immutability

Most boot information is immutable after entry.

That suggests an internal API such as:

~~~text
const struct boot_snapshot *boot_snapshot_get(void)
~~~

Mutability should be limited to early construction.

Once finalized:

- memory topology should not be rewritten casually;
- boot CPU topology should be treated as historical entry data;
- command line should be immutable;
- firmware root addresses should remain stable facts.

Runtime hotplug data, if added later, belongs elsewhere.

## Normalized memory ranges

The memory map is one of the most important pieces to normalize.

A kernel-owned range can be:

~~~text
struct boot_mem_range {
    uint64_t base;
    uint64_t length;
    uint32_t type;
    uint32_t flags;
};
~~~

The type should be a ChrisOS enum rather than a Limine numeric constant.

Possible internal types:

~~~text
BOOT_MEM_USABLE
BOOT_MEM_RESERVED
BOOT_MEM_ACPI_RECLAIM
BOOT_MEM_ACPI_NVS
BOOT_MEM_BAD
BOOT_MEM_BOOTLOADER
BOOT_MEM_KERNEL
BOOT_MEM_FRAMEBUFFER
BOOT_MEM_MMIO
BOOT_MEM_UNKNOWN
~~~

The exact enum can evolve without leaking the external protocol ABI.

## Why retain original type metadata

Normalizing does not mean losing information.

If a future Limine revision introduces a new memory type, the adapter can preserve:

- normalized category;
- raw protocol type;
- flags indicating incomplete interpretation.

This is safer than silently mapping every unknown type to usable memory.

Unknown memory must default to reserved.

## Memory map invariants

Before a range enters the snapshot, validate:

- base is representable;
- length is nonzero or intentionally ignored;
- base + length does not wrap;
- page-alignment behavior is explicit;
- type is known or mapped to reserved;
- range count stays within a configured bound.

The raw boot map is external input.

It should be parsed defensively.

## Sorting

Bootloaders often provide ordered maps, but the kernel should decide whether sorted order is an internal invariant.

A normalized snapshot can sort by base address.

Advantages:

- easier overlap detection;
- simpler diagnostics;
- deterministic tests;
- easier adjacent-range coalescing.

The adapter must not assume sorting unless the external protocol explicitly guarantees it.

## Overlap detection

After sorting by base, ranges can be checked with:

~~~text
prev_end <= current_base
~~~

If ranges overlap, possible policies are:

- panic as malformed input;
- apply explicit priority rules;
- split ranges into non-overlapping canonical segments.

For ChrisOS, failing closed is preferable during early hardening.

Silent overlap resolution can mark reserved hardware memory as usable.

## Adjacent-range coalescing

Two adjacent ranges with the same normalized type can be merged:

~~~text
A.end == B.base
and
A.type == B.type
~~~

This reduces range count.

However, raw provenance can be useful for debugging, so coalescing should occur only after validation and optionally preserve source metadata.

## Page alignment is not protocol normalization

The boot snapshot should preferably retain exact byte ranges from the bootloader.

PMM can later transform them into complete-page geometry.

Why?

Because these are different concerns:

~~~text
BootSnapshot:
what firmware/loader reported

PMM:
which complete pages are allocatable
~~~

Mixing them loses fidelity.

## PMM transformation

Current PMM correctly applies asymmetric alignment:

~~~text
usable:
round start upward
round end downward

reserved:
round start downward
round end upward
~~~

This ensures only wholly usable pages become free.

A future normalized map should preserve this rule at the PMM boundary.

## Memory-map capacity

The snapshot needs a finite capacity or dynamic allocation strategy.

Using dynamic allocation during the earliest boot phase introduces a circular dependency because heap/PMM may not yet be initialized.

Options include:

- fixed static array with a strict maximum;
- boot arena carved from known kernel BSS;
- two-pass sizing and later heap copy;
- early allocator dedicated to boot metadata.

A fixed array is simplest initially.

## Fixed array sizing

For example:

~~~text
#define BOOT_MAX_MEM_RANGES 256
~~~

would allow deterministic storage.

If the external map exceeds capacity, the kernel should fail clearly rather than truncate silently.

The actual number should be chosen from observed firmware maps plus margin and tested across machines.

## CPU topology normalization

The MP response should also be copied.

A kernel-owned descriptor can contain:

~~~text
struct boot_cpu {
    uint32_t processor_id;
    uint32_t apic_id;
    uint32_t logical_index;
    uint32_t flags;
};
~~~

This lets SMP stop depending on struct limine_mp_info after handoff.

## BSP identity

The snapshot should explicitly identify the BSP.

Do not require every consumer to infer BSP status by comparing APIC IDs repeatedly.

Possible fields:

~~~text
bsp_index
bsp_apic_id
cpu_count
cpus[]
~~~

This also creates one place to validate duplicate APIC IDs.

## CPU-count bounds

Current bootinfo verifies cpu_count is nonzero.

A hardened adapter should also reject or clamp according to explicit capacity.

SMP already has project limits such as SMP_CPU_CAP and SMP_MAX_APS.

The boot adapter should reconcile incoming topology with those limits before downstream code indexes fixed arrays.

## Duplicate CPU identifiers

Malformed topology can contain duplicate:

- processor IDs;
- LAPIC IDs.

These should be detected during normalization.

Duplicate APIC IDs can cause interrupts, TLB shootdowns and CPU accounting to target the wrong logical CPU.

That is not merely diagnostic metadata.

## x2APIC future-proofing

Current code uses uint32_t LAPIC IDs but several lookup structures mask IDs to 8 bits.

A BootSnapshot should not bake that truncation into the boot ABI.

Keep full-width APIC identifiers in the normalized topology.

Any xAPIC-only restriction belongs in the APIC/SMP subsystem.

## MP startup and ownership timing

There is a subtlety.

Limine MP descriptors are not only data.

Their goto_address and extra_argument fields are an active synchronization interface used to start APs.

Therefore the kernel cannot drop the raw MP response before AP handoff completes.

The sequence should be:

~~~text
copy topology
   |
allocate kernel AP state/stacks
   |
program Limine goto_address
   |
wait for AP handoff
   |
verify APs are on kernel-owned stacks
   |
drop Limine MP objects
~~~

This is different from memory-map normalization, where a deep copy can remove the dependency immediately.

## Framebuffer normalization

Current bootinfo copies geometry but loses color-layout information.

A fuller descriptor can contain:

~~~text
address
physical_address if known
width
height
pitch
bpp
memory_model
red_mask_size
red_mask_shift
green_mask_size
green_mask_shift
blue_mask_size
blue_mask_shift
~~~

The kernel graphics layer can then decide whether the mode is supported.

## Virtual versus physical framebuffer address

Limine gives a mapped framebuffer virtual address.

For ownership purposes, distinguish:

~~~text
fb_virtual
fb_physical
~~~

The physical backing can be derived once the inherited page tables are still active.

If the kernel later replaces the page tables, it needs the physical address to recreate the mapping.

Therefore physical framebuffer identity should be captured before page-table replacement.

## Framebuffer size arithmetic

A framebuffer byte-span cannot safely be calculated only as:

~~~text
width * height * bytes_per_pixel
~~~

because pitch may exceed visible row width.

The memory span needed for scanout access is more accurately based on:

~~~text
pitch * height
~~~

with checked multiplication.

Both values can overflow if boot input is malformed.

## Pixel format validation

A 32-bpp framebuffer can still use unsupported channel masks.

Normalization should copy the masks first.

The graphics backend can then classify:

~~~text
XRGB8888
XBGR8888
custom mask layout
unsupported
~~~

Current code only checks bpp == 32.

## HHDM normalization

HHDM is currently copied as a scalar offset.

That is useful but incomplete.

The kernel also needs to know **where the direct-map operation is valid**.

A future internal HHDM model can expose:

~~~text
bool boot_phys_is_direct_mapped(uint64_t phys, uint64_t size)
~~~

rather than encouraging arbitrary:

~~~text
phys + offset
~~~

casts.

This would encode the mapping policy derived from the normalized memory ranges.

## Physical-to-virtual conversion API

Current:

~~~text
bootinfo_phys_to_virt(phys)
~~~

blindly adds the HHDM offset.

A safer API can be split:

~~~text
boot_hhdm_contains(phys, size)
boot_phys_to_hhdm(phys, size)
~~~

The second operation can panic or return null if the range is not guaranteed mapped.

MMIO must continue through explicit mapping APIs.

## Command-line ownership

Current bootflag_parse reads the Limine command-line string immediately and copies only interpreted booleans/enums into static globals.

This means the kernel does not need the command-line string later for those flags.

That is already a good normalization pattern:

~~~text
external string
 -> parse
 -> kernel-owned configuration state
~~~

If the shell or diagnostics later need the raw command line, copy it explicitly into bounded kernel storage.

## Command-line limits

The parser currently walks until NUL without an explicit maximum.

The bootloader is trusted, but a defensive adapter should enforce a maximum such as:

~~~text
BOOT_CMDLINE_MAX
~~~

before tokenization.

The copy should always be NUL-terminated.

## Unknown flags

Unknown boot flags are currently ignored.

That can be acceptable for forward compatibility.

A useful diagnostic mode could log unknown tokens so typos such as:

~~~text
noampic
~~~

do not silently appear to work.

## Firmware roots

A normalized boot layer is the right place to carry roots such as:

- RSDP;
- SMBIOS entry points;
- EFI System Table if intentionally retained;
- device tree on non-x86 targets.

Subsystems should consume these roots through internal boot APIs rather than depend on Limine request types.

## RSDP ownership

An RSDP pointer is not the same thing as copied ACPI tables.

The snapshot can store the physical or protocol-defined address of the RSDP.

Then the ACPI subsystem can:

1. validate RSDP;
2. find XSDT/RSDT;
3. validate tables;
4. decide which table bytes must remain accessible;
5. reclaim ACPI reclaimable memory only after lifetime is resolved.

Boot normalization and ACPI ownership are separate stages.

## SMBIOS ownership

Likewise, SMBIOS entry points can be stored in boot state while the SMBIOS subsystem decides what to parse and retain.

The boot layer should not turn into a SMBIOS parser.

It should transport validated roots.

## Bootloader identity

A persistent snapshot should ideally record:

~~~text
boot_protocol
bootloader_name
bootloader_version
protocol_base_revision
firmware_type
~~~

This greatly improves bug reports.

For example:

~~~text
ChrisOS build: ...
Boot protocol: Limine
Bootloader: Limine 9.x
Base revision: 3
Firmware: UEFI64
~~~

This is much more useful than merely knowing the kernel reached kstart.

## Kernel image identity

The boot environment can also provide or help derive:

- kernel physical base;
- kernel virtual base;
- executable size;
- loaded modules.

The project already values build ID and SHA256 provenance.

A BootSnapshot should connect bootloader provenance with kernel artifact provenance.

## Snapshot and security

Boot information is privileged input.

If the bootloader is compromised, the kernel cannot fully protect itself from malicious page tables or fabricated memory maps.

However, defensive validation still matters because it catches:

- firmware bugs;
- bootloader bugs;
- accidental corruption;
- incompatible revisions;
- emulator defects;
- future adapter mistakes.

Trust and validation are not mutually exclusive.

## The inherited page-table problem

Even after all metadata is copied, the current kernel still depends on bootloader-owned page tables.

mm_init reads:

~~~text
CR3
~~~

and stores it in:

~~~text
mm_cr3_phys
~~~

Then map_4k and related functions extend that same hierarchy.

This is adoption, not normalization.

## Why replacing page tables matters

A kernel-owned root provides:

- clear lifetime;
- known permissions;
- known direct-map geometry;
- no hidden loader-only mappings;
- safe bootloader-memory reclamation;
- easier ChrisVM parity;
- reproducible paging layout.

The replacement should occur only after enough physical memory is available to allocate the new hierarchy.

## Page-table transition plan

A staged migration can be:

~~~text
1. parse and copy boot memory map
2. initialize PMM
3. allocate new PML4 hierarchy
4. map kernel ELF
5. map kernel stack
6. build HHDM for intended ranges
7. map framebuffer
8. map required MMIO windows
9. switch CR3
10. verify translations
11. retire inherited tables
~~~

The exact ordering must keep code, stack and data continuously mapped.

## Mapping the currently executing instruction

When switching CR3, the new page tables must already map:

- the current RIP page;
- current RSP stack pages;
- global data used immediately after the write;
- page-table manipulation code;
- interrupt/trap structures if interrupts can occur.

A page-table handoff is an executable transition, not merely a data copy.

## TLB behavior

Writing CR3 changes translation context and invalidates relevant TLB state according to x86 semantics.

The boot-time switch occurs before normal SMP traffic if possible.

Doing it before APs are fully active simplifies TLB coordination.

This is another reason to choose the ownership transition point deliberately.

## BSP stack transition

The BSP entry stack is also bootloader-owned.

ChrisOS currently later relies on a linker-reserved stack for TSS rsp0 but does not immediately switch the BSP runtime stack to it.

A complete ownership transition should explicitly move RSP to a kernel-owned BSP boot stack before reclaiming loader memory.

## AP stacks

APs already perform a more explicit transition.

smp_init allocates PMM-backed stacks and ap_entry switches RSP before entering normal worker code.

This makes AP stack ownership clearer than BSP stack ownership.

The BSP should eventually follow the same principle.

## Reclamation barrier

Bootloader-reclaimable pages can only be freed after all of these are true:

~~~text
memory map copied
MP topology copied
AP bootstrap finished
BSP on kernel stack
APs on kernel stacks
new kernel page tables active
no response pointers retained
no loader modules needed
no bootloader data structures referenced
~~~

This is a barrier.

Reclamation before the barrier is unsafe.

## Reclaim API

Rather than letting PMM silently reinterpret memory types at arbitrary times, use an explicit transition such as:

~~~text
boot_release_bootloader_memory()
~~~

The function should assert the barrier conditions.

It can then convert eligible normalized boot ranges into PMM-free pages.

This makes lifetime visible in code.

## ACPI reclaim barrier

ACPI reclaimable memory has a different barrier.

It becomes eligible only when the ACPI subsystem confirms the necessary table contents no longer require those original pages.

Therefore there can be multiple release phases:

~~~text
release bootloader memory
release ACPI reclaimable memory
release init-only kernel sections
...
~~~

Resource lifetime should be phase-specific.

## Boot phases

A useful boot state machine is:

~~~text
BOOT_RAW
  |
BOOT_VALIDATED
  |
BOOT_SNAPSHOT_READY
  |
BOOT_PMM_READY
  |
BOOT_KERNEL_PAGING
  |
BOOT_SMP_HANDOFF_DONE
  |
BOOT_BOOTLOADER_RELEASED
  |
BOOT_RUNTIME
~~~

Subsystem APIs can assert a minimum phase.

This catches accidental use of raw loader data after release.

## Current bootinfo_ready flag

Today bootinfo has one boolean:

~~~text
bootinfo_ready
~~~

It only distinguishes:

~~~text
not initialized
initialized
~~~

A richer state machine would encode ownership transitions more accurately.

## Why bootinfo is currently coupled to Limine

bootinfo.c contains both:

- protocol declarations;
- protocol validation;
- command-line parsing;
- kernel-facing accessors.

That makes it both adapter and kernel boot database.

A cleaner structure is:

~~~text
boot/limine.c
    raw Limine adapter

boot/snapshot.c
    normalization + ownership

boot/config.c
    command-line policy

kernel subsystems
    consume only snapshot/config APIs
~~~

This reduces external protocol leakage.

## Header coupling

bootinfo.h forward-declares:

~~~text
struct limine_mp_response;
~~~

and exposes:

~~~text
struct limine_mp_response *bootinfo_mp_response(void);
~~~

That is the strongest visible protocol leak in the public bootinfo API.

A kernel-internal normalized CPU interface would remove Limine from this header entirely.

## Desired public API

A future header can expose only ChrisOS types:

~~~text
const struct boot_snapshot *boot_snapshot_get(void);

uint64_t boot_memory_count(void);
int boot_memory_range(index, struct boot_mem_range *);

uint32_t boot_cpu_count(void);
int boot_cpu(index, struct boot_cpu *);

const struct boot_framebuffer *boot_framebuffer(void);
const struct boot_firmware_roots *boot_firmware(void);
~~~

No Limine type needs to appear.

## ChrisVM integration

ChrisVM v1 has no boot-info structure.

Its protocol 2 milestone explicitly needs:

- higher-half ELF;
- explicit boot info;
- same architectural state;
- backend-independent kernel behavior.

A BootSnapshot provides the natural target.

ChrisVM does not need to impersonate UEFI.

It only needs a boot adapter that supplies the same kernel facts.

## ChrisVM adapter model

Conceptually:

~~~text
Limine adapter
  framebuffer response
  memory map response
  MP response
  RSDP response
       |
       v
    BootSnapshot
       ^
       |
ChrisVM adapter
  machine RAM ranges
  virtual framebuffer
  vCPU topology
  synthetic ACPI roots
~~~

The kernel below BootSnapshot does not care which producer was used.

## Why not pass ChrisVM-specific structs directly

If ChrisVM introduces another public boot API parallel to Limine, every subsystem gains branches:

~~~text
if Limine ...
else if ChrisVM ...
~~~

That scales poorly.

Normalize once at the boot boundary instead.

## Backend independence

The ChrisVM documentation already states:

~~~text
the kernel should not detect whether the backend is ChrisCPU or ChrisHV
~~~

The same principle applies one layer higher:

~~~text
the kernel should not care whether boot facts came from Limine or ChrisVM
~~~

Only the boot adapter should know.

## Deterministic snapshot serialization

For debugging and tests, BootSnapshot can support a deterministic textual dump:

~~~text
protocol=limine
firmware=uefi64
hhdm=...
mem[0]=...
cpu[0]=...
fb=...
rsdp=...
~~~

A canonical dump makes QEMU, ChrisVM and physical-machine comparisons easier.

## Snapshot hashing

A non-security diagnostic hash of normalized boot state can help detect unexpected platform differences.

For example:

~~~text
BootSnapshot SHA256: ...
~~~

Two boots with the same kernel but different memory topology naturally produce different hashes.

The hash should be treated as identity/diagnostic metadata, not authentication.

## Boot reproducibility

Perfect bit-for-bit boot state is not expected across physical boots because addresses and firmware allocations may differ.

Reproducibility means:

- deterministic parser behavior;
- deterministic normalization;
- explicit ordering;
- explicit ignored fields;
- no dependence on uninitialized memory.

The same raw boot responses should produce the same normalized snapshot.

## Testable normalization

The normalization logic should be callable by host tests with synthetic input.

For example:

~~~text
normalize_memory_map(raw_entries)
normalize_cpu_topology(raw_cpus)
normalize_framebuffer(raw_fb)
parse_boot_config(cmdline)
~~~

These functions can be tested without booting QEMU.

This is cheaper and catches structural errors earlier.

## Fuzzing

Memory-map normalization is particularly suitable for fuzzing.

Interesting cases include:

- zero-length ranges;
- wrapping ranges;
- maximum addresses;
- overlapping ranges;
- duplicate ranges;
- unknown types;
- unsorted input;
- thousands of entries.

The expected result should always be either:

- a validated canonical snapshot; or
- a clean explicit rejection.

Never silent memory corruption.

## Diagnostics before panic

When possible, malformed external data should print enough information to diagnose the failure.

For a bad memory range:

~~~text
boot: invalid mem range index=17
base=...
length=...
type=...
reason=overflow
~~~

This matters on real hardware where reproducing the firmware environment may be difficult.

## Unknown memory is reserved

One of the most important safety rules is:

~~~text
unknown memory type -> reserved
~~~

Never default unknown memory to usable.

A future Limine revision can add new memory classes.

Old kernels must fail safe.

## Unknown CPU fields

Likewise, extra CPU metadata can be ignored if the required identifier fields remain valid.

But topology counts and identifiers must still be bounded and checked.

## Snapshot versioning

The internal BootSnapshot may eventually evolve.

It can carry:

~~~text
version
size
flags
~~~

if it needs to be serialized or shared across components.

If it remains an internal C structure only, normal source-level evolution may be enough.

Avoid adding version machinery without a real binary compatibility consumer.

## Static versus dynamic snapshot allocation

Early boot favors static storage.

A practical initial implementation can use:

~~~text
static struct boot_snapshot snapshot;
static struct boot_mem_range ranges[BOOT_MAX_MEM_RANGES];
static struct boot_cpu cpus[BOOT_MAX_CPUS];
static char cmdline[BOOT_CMDLINE_MAX];
~~~

Once heap is live, these can remain static.

There is no requirement to dynamically shrink them immediately.

Correct ownership matters more than saving a few KiB.

## Capacity accounting

Fixed arrays should publish their capacities and reject overflow.

For example:

~~~text
if raw_count > BOOT_MAX_MEM_RANGES:
    panic("boot: too many memory ranges")
~~~

Never truncate the tail of a memory map.

A truncated map can omit reserved firmware ranges and turn them into accidental allocator targets.

## Memory accounting consistency

After normalization, derive totals such as:

- usable bytes;
- reserved bytes;
- bootloader bytes;
- framebuffer bytes;
- ACPI bytes.

These totals should use checked addition.

They become useful diagnostics and invariants.

The existing usable_bytes can then be derived from the snapshot rather than copied separately during parsing.

## Avoid duplicated source of truth

Today bootinfo stores both:

~~~text
usable_bytes
memmap_entries
~~~

and also preserves the original memory map.

If later the map were mutated or normalized differently, these could diverge.

A stronger architecture derives summary values from the one canonical snapshot.

The snapshot should be the source of truth.

## CPU count source of truth

Similarly, cpu_count is copied into struct bootinfo while the original MP response remains live.

SMP uses both.

After normalization, there should be one canonical CPU topology.

This eliminates possible divergence.

## Boot configuration source of truth

The parsed booleans already form the canonical runtime boot configuration.

They can be grouped into:

~~~text
struct boot_config {
    safe;
    nosmp;
    noapic;
    noac97;
    nonet;
    nojit;
    gfx_backend;
    gfx_3d;
    gfx_stress;
    gfx_debug;
};
~~~

This is cleaner than many unrelated static globals.

## Default policy

Every boot option must have a defined default before parsing.

For example:

~~~text
gfx backend = virtio preferred
gfx 3D = auto
safe = false
~~~

The snapshot/config initialization should set these explicitly.

Do not rely on BSS zero semantics when zero is not a self-documenting policy.

## Source reconciliation: what is copied today

Current bootinfo_init copies these facts:

| Fact | Copied into ChrisOS-owned scalar? |
|---|---:|
| HHDM offset | yes |
| framebuffer virtual address | yes |
| framebuffer width | yes |
| framebuffer height | yes |
| framebuffer pitch | yes |
| framebuffer bpp | yes |
| total usable bytes | yes |
| memory-map entry count | yes |
| CPU count | yes |
| BSP LAPIC ID | yes |
| individual memory ranges | no |
| individual CPU descriptors | no |
| command-line bytes | no |
| RSDP | no request |
| SMBIOS | no request |
| firmware type | no request |
| bootloader identity | no request |

This table is the current ownership boundary.

## Source reconciliation: what remains borrowed

The kernel still borrows:

~~~text
memmap_response
mp_request.response
mp_request.response->cpus[]
per-CPU limine_mp_info objects
~~~

These remain external protocol objects.

The first major refactor should remove these from normal kernel-facing APIs.

## Source reconciliation: what is adopted

The kernel adopts:

~~~text
current CR3 page-table hierarchy
~~~

and then mutates it.

This is stronger coupling than a borrowed pointer because the object has become operational kernel state.

It must be explicitly replaced before bootloader memory can be reclaimed.

## Source reconciliation: what is already normalized well

Boot flags are a strong example.

The raw string is read once.

Persistent policy becomes ChrisOS-owned static state.

No subsystem later asks Limine for the string.

The same pattern should be applied to memory and CPU topology.

## Recommended implementation sequence

A low-risk evolution is:

### Stage 1: introduce ChrisOS types

Add:

~~~text
boot_mem_range
boot_cpu
boot_framebuffer
boot_config
boot_firmware_roots
boot_snapshot
~~~

without changing current runtime behavior.

### Stage 2: deep-copy memory map

Build the normalized memory range array in bootinfo_init.

Change PMM accessors to read it.

Remove memmap_response from normal runtime use.

### Stage 3: copy CPU topology

Copy processor/APIC IDs.

Keep raw MP structures only inside SMP bootstrap.

After AP handoff, stop exposing them.

### Stage 4: capture firmware roots

Add Limine RSDP request first.

Then SMBIOS and firmware-type if useful.

### Stage 5: capture framebuffer format fully

Copy channel masks and memory model.

### Stage 6: create kernel page tables

Build and switch to a kernel-owned CR3.

Capture framebuffer physical backing first.

### Stage 7: move BSP stack

Switch BSP to a kernel-owned stack.

### Stage 8: reclaim Limine memory

Assert no raw response/table/stack dependencies remain.

Release BOOTLOADER_RECLAIMABLE pages.

### Stage 9: add ChrisVM adapter

Have ChrisVM protocol v2 produce the same internal snapshot.

## Reclamation is not the first goal

Do not optimize primarily for freeing bootloader memory.

The architectural value comes first:

- protocol independence;
- explicit ownership;
- testability;
- safer HHDM use;
- reproducible debugging;
- ChrisVM compatibility.

Memory reclamation becomes a natural consequence.

## Reproducible checker

scripts/check_boot_information_examples.py validates:

1. current scalar fields in struct bootinfo;
2. current retained memmap response;
3. current public exposure of limine_mp_response;
4. current CR3 adoption in mm_init;
5. BOOTLOADER_RECLAIMABLE remains reserved in PMM;
6. command-line is parsed into kernel-owned flags;
7. current ChrisVM v1 has no boot info;
8. checked range arithmetic;
9. canonical range sorting and overlap detection examples;
10. page-alignment transformations;
11. framebuffer span arithmetic using pitch;
12. a synthetic BootSnapshot normalization model.

The synthetic model is illustrative; it is not yet the ChrisOS implementation.

## Validation boundary

This chapter describes the current source and the proposed ownership architecture.

It does **not** claim that BootSnapshot already exists in ChrisOS.

Current code still has:

~~~text
struct bootinfo
memmap_response
bootinfo_mp_response()
inherited CR3
~~~

The proposed BootSnapshot is the documented next architectural boundary.

This chapter is reconciled with:

~~~text
ChrisOS main
da3df29cb397932c43d32373871fb9380e688ade
~~~

Run:

~~~text
python scripts/check_boot_information_examples.py --source .source
~~~

## Review triggers

Review this chapter when:

- struct bootinfo changes;
- memory map is deep-copied;
- Limine types disappear from bootinfo.h;
- CPU topology is normalized;
- RSDP/SMBIOS requests are added;
- framebuffer format metadata is copied;
- command-line representation changes;
- BSP switches stacks explicitly;
- kernel-owned page tables replace inherited CR3;
- BOOTLOADER_RECLAIMABLE memory is released;
- ACPI reclaimable memory begins to be released;
- ChrisVM protocol v2 publishes real kernel boot information.

## Primary references

- Limine boot protocol and pinned Limine header used by ChrisOS.
- ChrisOS bootinfo, PMM, MM and SMP source files listed in front matter.
- ChrisVM boot protocol v1 documentation.
