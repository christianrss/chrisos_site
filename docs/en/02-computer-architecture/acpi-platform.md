---
id: acpi-platform
lang: en
type: technical-chapter
volume: 02-computer-architecture
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/acpi.c
  - kernel/metal/acpi.h
  - kernel/metal/bootinfo.c
  - kernel/metal/bootinfo.h
  - kernel/metal/mm.c
  - kernel/metal/apic.c
  - kernel/metal/ioapic.c
  - kernel/metal/smp.c
  - kernel/metal/pci.c
  - kernel/metal/start.c
  - docs/CURRENT_HARDWARE_AUDIT.md
  - docs/REAL_HARDWARE_PLAN.md
symbols:
  - acpi_probe
  - bootinfo_phys_to_virt
  - bootinfo_memmap_entry
  - bootinfo_mp_response
  - mm_lapic_virt
  - apic_init
  - apic_enable_local
  - ioapic_init
  - smp_init
depends_on:
  - pci-pcie
  - x86-64-memory-privilege
related:
  - reset-firmware
  - uefi
  - limine
  - boot-information
  - pic-apic-ioapic
  - interrupts-smp
  - timers
  - installation-real-hardware
---

# ACPI and platform description

## Scope

ACPI is the contract through which platform firmware describes hardware topology, configuration, power-management interfaces, interrupt routing, processor relationships and other machine-specific details to an operating system.

It is not merely a power-off interface and it is not a BIOS-call convention.

Modern ACPI combines:

- static system-description tables;
- a hierarchical namespace;
- AML bytecode methods and objects;
- fixed and generic hardware registers;
- operating-system capability negotiation;
- event, wake and power-management semantics.

The UEFI Forum defines ACPI as the interface used for Operating System-directed configuration and Power Management, OSPM. ACPI 6.6 is the current specification revision at this chapter review.

ChrisOS currently implements only a small discovery probe. It locates an RSDP-like signature in a legacy BIOS memory window, follows XSDT when Revision is at least 2, and prints selected child-table signatures. It does not yet validate ACPI checksums or parse MADT, MCFG or FADT into runtime platform state.

![ACPI discovery and platform-description graph](../../assets/diagrams/acpi-platform-en.svg)

The distinction between detecting a table and implementing the facility represented by that table is central to this chapter.

## ACPI as a platform description interface

A kernel should not contain motherboard-specific constants for every machine.

Firmware can describe facts such as:

- interrupt controllers;
- processors and APIC identities;
- global interrupt routing;
- PCIe ECAM configuration windows;
- fixed power-management registers;
- DSDT and SSDT locations;
- devices in the ACPI namespace;
- device resource requirements;
- wake and thermal relationships;
- platform-specific control methods.

ACPI moves part of platform knowledge from kernel source code into firmware-supplied data and executable description.

## Static tables and AML

Two broad categories should be separated.

Static data tables include MADT, MCFG, SRAT, SLIT, HPET and many other structures. They contain structured binary data.

Definition Blocks such as DSDT and SSDT contain AML, ACPI Machine Language. AML creates and extends a namespace and can contain executable control methods.

An operating system therefore eventually needs:

~~~text
binary ACPI table parser
+
AML interpreter and namespace engine
~~~

Useful ACPI support can still be implemented incrementally by parsing static tables before the AML runtime is complete.

## Discovery graph

A typical ACPI graph is:

~~~text
RSDP
 |
 +--> XSDT or RSDT
        |
        +--> FADT/FACP
        |      |
        |      +--> DSDT
        |      +--> FACS
        |
        +--> MADT
        +--> MCFG
        +--> HPET
        +--> SRAT
        +--> SLIT
        +--> SSDT
        +--> other tables
~~~

The root table is a directory of physical table addresses, not a complete machine description by itself.

## Root System Description Pointer

RSDP is the first ACPI structure that OSPM must obtain.

Its signature is eight bytes:

~~~text
RSD PTR<space>
~~~

The trailing space is part of the signature.

The first 20 bytes are compatible with ACPI 1.0. Revision 2 or later adds fields including Length, XsdtAddress and Extended Checksum.

A parser must not treat the signature alone as proof of validity.

## RSDP checksums

The first 20 bytes must sum to zero modulo 256.

For Revision 2 or later, the entire Length-byte RSDP must also sum to zero.

~~~text
sum(bytes[0:20]) & 0xFF == 0

if revision >= 2:
    sum(bytes[0:length]) & 0xFF == 0
~~~

Current acpi_probe checks the signature but validates neither checksum.

The checker accompanying this chapter creates valid and corrupted synthetic RSDPs to keep these rules executable.

## Legacy IA-PC RSDP search

For legacy IA-PC discovery, ACPI defines search locations including:

1. the first 1 KiB of the Extended BIOS Data Area;
2. the BIOS read-only-memory region from 0xE0000 through 0xFFFFF.

Candidates are searched on 16-byte boundaries and must pass signature and checksum validation.

Current ChrisOS scans 0xE0000..0xFFFFF.

It does not search the first KiB of EBDA.

This is one reason current acpi_probe is a bring-up probe rather than a complete legacy discovery implementation.

## RSDP on UEFI systems

ChrisOS targets UEFI for real hardware.

On UEFI systems the ACPI specification requires the OS loader to obtain the RSDP pointer from the EFI System Table Configuration Table and convey it to OSPM during handoff.

UEFI defines GUIDs for ACPI 1.0 and ACPI 2.0-or-later RSDP entries, with the newer entry preferred.

A robust architecture is therefore:

~~~text
UEFI firmware
    |
EFI System Table
    |
ACPI configuration-table GUID
    |
RSDP pointer
    |
bootloader handoff
    |
ChrisOS bootinfo
~~~

Legacy BIOS-range scanning should be fallback logic, not the primary UEFI path.

## Current Limine handoff

bootinfo.c currently requests:

- framebuffer;
- HHDM;
- memory map;
- multiprocessor information;
- command line.

The source does not preserve an RSDP pointer.

acpi_probe therefore rediscovers ACPI through the legacy scan.

A future boot contract should carry the firmware/bootloader-provided RSDP directly.

## Current scan mechanics

acpi_probe loops through Limine memory-map entries and examines candidate physical addresses in the BIOS range.

Candidates are converted with bootinfo_phys_to_virt, so probing depends on the HHDM mapping.

The code checks that candidate bytes are within one memory-map entry before dereferencing the signature.

This is useful bounds discipline but not enough because:

- memory-map membership does not prove ACPI identity;
- table checksums are not validated;
- RSDP Length is not validated;
- the declared object can extend beyond the checked bytes;
- child pointers are trusted after minimal signature checks.

## Revision handling

RSDP Revision 0 supplies RSDT.

Revision 2 or later also supplies XSDT.

Current acpi_probe only continues when:

~~~text
revision >= 2
~~~

and then follows XsdtAddress.

It has no RSDT fallback.

Therefore ACPI 1.0-style root traversal is not implemented.

## RSDT and XSDT

RSDT contains 32-bit physical pointers.

XSDT contains 64-bit physical pointers.

Both use the common System Description Table header.

On x86-64, XSDT is normally preferred when present because physical table addresses are not limited to 32 bits.

A complete implementation still benefits from RSDT fallback for compatibility.

## System Description Table header

Most ACPI tables begin with a 36-byte header containing:

- Signature;
- Length;
- Revision;
- Checksum;
- OEM ID;
- OEM Table ID;
- OEM Revision;
- Creator ID;
- Creator Revision.

Length includes the header.

The complete Length-byte table must sum to zero modulo 256.

A generic validator should enforce this once and be reused for every SDT.

## Current XSDT traversal

acpi_probe validates the XSDT signature, reads its Length and walks 64-bit child pointers beginning at byte 36.

It also imposes a project-local bound:

~~~text
entry_offset < 512
~~~

This prevents an unbounded loop but is not an ACPI semantic rule.

The current code does not validate:

- XSDT checksum;
- Length >= 36;
- divisibility of payload by eight;
- complete mapped/readable range;
- checksums of child tables.

## RSDT/XSDT entry-count arithmetic

For a valid table:

~~~text
payload = Length - 36
~~~

RSDT requires:

~~~text
payload % 4 == 0
count = payload / 4
~~~

XSDT requires:

~~~text
payload % 8 == 0
count = payload / 8
~~~

The checker validates these invariants.

## ACPI table registry

A maintainable ACPI core should discover tables once and register them.

Example:

~~~text
AcpiTable
  signature
  physical_address
  virtual_address
  length
  revision
  checksum_valid
~~~

Consumers can query:

~~~text
acpi_find(APIC, index)
acpi_find(MCFG, index)
acpi_find(FACP, index)
acpi_find(SSDT, index)
~~~

Multiple SSDTs are legal, so the registry cannot assume signature uniqueness.

## MADT

MADT has signature APIC.

It describes interrupt-controller and processor topology.

Its fixed portion includes a Local Interrupt Controller Address and Flags. A sequence of variable-length entries follows.

On x86, MADT entry types can describe:

- Processor Local APIC;
- I/O APIC;
- Interrupt Source Override;
- NMI source;
- Local APIC NMI;
- Local APIC Address Override;
- Processor Local x2APIC;
- Local x2APIC NMI.

A parser must advance using each subtable Length.

## Safe MADT walking

Each MADT variable entry starts with:

~~~text
Type   1 byte
Length 1 byte
~~~

A safe walker requires:

~~~text
Length >= 2
current + Length <= table_end
~~~

and advances by exactly Length bytes.

Zero or one-byte lengths must be rejected or a loop/overlap can occur.

The checker includes valid and malformed synthetic MADT entries.

## LAPIC physical address

The MADT fixed header supplies the local interrupt-controller physical address.

A Local APIC Address Override can replace it with a 64-bit address.

A robust kernel derives the address from MADT.

Current mm.c instead defines:

~~~text
LAPIC_PHYS = 0xFEE00000
~~~

and mm_selftest maps that constant.

This works with the current QEMU target but is not MADT-driven platform discovery.

## Current CPU topology source

smp_init uses the Limine multiprocessor response.

It obtains:

- CPU count;
- BSP LAPIC ID;
- AP LAPIC IDs;
- bootloader startup structures.

This information is used to start APs.

acpi_probe merely prints APIC when it sees the MADT signature.

Therefore MADT is not currently the source of CPU topology.

A future architecture can keep Limine as the processor-start mechanism while using MADT as authoritative platform description and cross-checking both views.

## I/O APIC

MADT can describe one or more I/O APICs.

Each I/O APIC description includes its physical address and Global System Interrupt base.

Interrupt Source Override entries map legacy ISA interrupt sources to GSIs and define polarity/trigger semantics.

Current ioapic_init does not parse or program this information. It prints that PIC still routes IRQs.

The presence of ioapic.c must therefore not be confused with implemented ACPI/IOAPIC routing.

## Global System Interrupts

ACPI expresses interrupt inputs as Global System Interrupt numbers.

Legacy IRQ number and GSI are not universally identical because an Interrupt Source Override can remap them.

This matters for:

- PIT;
- keyboard;
- ATA;
- ACPI SCI;
- PCI INTx routing.

Assuming IRQ == GSI can pass under a simple emulator and fail on physical hardware.

## Future MADT model

A useful parsed representation is:

~~~text
AcpiCpu
  uid
  apic_id
  enabled
  online_capable

AcpiIoApic
  id
  physical_address
  gsi_base

AcpiIso
  source_irq
  gsi
  polarity
  trigger
~~~

SMP, IOAPIC and interrupt-routing code should consume these normalized structures.

## MCFG

MCFG describes PCIe ECAM regions.

Each allocation identifies:

- ECAM base;
- segment group;
- start bus;
- end bus.

The previous PCI chapter derived:

~~~text
ecam =
base
+ ((bus - start_bus) << 20)
+ (device << 15)
+ (function << 12)
+ register
~~~

Current acpi_probe detects MCFG by signature but does not parse its allocations.

pci.c therefore continues to use CF8/CFC.

## MCFG range size

Each PCI bus consumes one MiB of ECAM address space.

For a valid inclusive range:

~~~text
bytes =
(end_bus - start_bus + 1)
* 0x100000
~~~

An end bus lower than the start bus is malformed.

The checker validates this arithmetic.

## FADT / FACP

The Fixed ACPI Description Table uses signature FACP.

FADT connects static ACPI data to the fixed hardware model and the AML namespace.

Important fields include:

- FIRMWARE_CTRL and X_FIRMWARE_CTRL;
- DSDT and X_DSDT;
- SCI_INT;
- PM1 event/control blocks;
- PM timer;
- reset register/value;
- boot architecture flags;
- hardware-reduced ACPI flags;
- platform capability flags.

Current acpi_probe recognizes FACP only by signature.

It does not parse these fields.

## DSDT

The Differentiated System Description Table contains AML.

FADT points to DSDT through DSDT or X_DSDT.

Loading DSDT builds the core ACPI namespace.

A DSDT is not a fixed C structure after the 36-byte header; its payload is AML bytecode.

ChrisOS currently has no DSDT loader or AML interpreter.

## SSDT

Secondary System Description Tables also contain AML Definition Blocks.

Multiple SSDTs may extend the namespace.

They must be retained in root-table order.

This is one reason the future ACPI registry should support duplicate signatures and stable discovery ordering.

## ASL and AML

Firmware developers generally write ACPI Source Language, ASL.

An ASL compiler produces AML.

~~~text
ASL -> compiler -> AML
                   |
                   v
                 OSPM
~~~

The kernel interprets AML; it does not execute ASL text.

## ACPI namespace

After DSDT/SSDT loading, ACPI exposes a hierarchical namespace.

It can contain:

- Device objects;
- Methods;
- integers;
- strings and buffers;
- Packages;
- Fields;
- Operation Regions;
- mutexes/events;
- thermal and power objects.

Paths can resemble:

~~~text
\_SB.PCI0
\_SB.PCI0.XHC
\_PR.CPU0
~~~

Exact namespace names are firmware data and must not be assumed universally.

## AML interpreter requirements

A general AML runtime requires substantially more than recognizing a few names.

It needs:

- opcode decoding;
- namespace construction;
- scope/name resolution;
- object model;
- integer/buffer/package semantics;
- method arguments and locals;
- control flow;
- conversions;
- Operation Regions;
- Field access;
- synchronization;
- resource-template decoding;
- execution limits and errors.

Searching DSDT bytes for selected ASCII names is not a substitute.

## Device identification and status methods

Common ACPI objects include:

- _HID: hardware ID;
- _CID: compatible ID;
- _UID: unique ID;
- _STA: device status;
- _CRS: current resources;
- _PRS: possible resources;
- _SRS: set resources.

These mechanisms are important for devices that are not self-enumerating through PCI or another bus.

ChrisOS currently evaluates none of them.

## PCI routing with _PRT

_PRT describes PCI interrupt routing within the ACPI namespace.

It maps PCI device/pin relationships to interrupt resources and can involve ACPI PCI link devices.

A complete INTx implementation may therefore require AML evaluation in addition to PCI configuration-space fields.

This is a direct dependency between the ACPI and PCI subsystems.

## _PIC

_PIC informs firmware methods which interrupt model OSPM selected.

AML methods can vary routing behavior depending on PIC versus APIC-style operation.

ChrisOS currently does not evaluate _PIC.

Its current interrupt path still retains PIC routing while LAPIC support is partial and IOAPIC routing is not implemented.

## _OSC

_OSC allows OSPM to communicate supported capabilities and negotiate control with firmware.

For PCIe this affects ownership of selected native services, including areas related to hot-plug and error handling.

ChrisOS currently has no AML runtime and therefore performs no PCI-host-bridge _OSC negotiation.

ECAM access alone is not proof that the OS owns every PCIe platform service.

## SCI

The System Control Interrupt is the central ACPI event interrupt in traditional ACPI hardware models.

FADT supplies SCI_INT.

SCI is used for fixed events and General Purpose Events.

ChrisOS currently has no ACPI SCI handler.

## General Purpose Events

GPEs can represent firmware/platform events such as wake, thermal or device notifications.

Correct support requires:

- GPE register discovery;
- status/enable management;
- SCI integration;
- AML method dispatch;
- correct clearing/masking.

Poor handling can produce interrupt storms.

ChrisOS has no GPE subsystem today.

## Fixed hardware and Generic Address Structure

Traditional ACPI platforms expose PM1, PM timer and GPE registers.

Newer descriptions use Generic Address Structures and can also be hardware-reduced.

GAS describes a register with:

- address-space ID;
- bit width;
- bit offset;
- access size;
- 64-bit address.

A generic ACPI register layer should convert GAS into safe I/O/MMIO accesses with exact widths.

ChrisOS currently has no GAS abstraction.

## ACPI reset

FADT can provide RESET_REG and RESET_VALUE.

When supported, these define a firmware-described reset mechanism.

Current acpi_probe does not parse or use them.

A future reboot path should prefer validated platform description before falling back to machine-specific reset tricks.

## Sleep and soft-off

ACPI defines system power-state semantics including working, sleep, hibernation and soft-off concepts.

Not every platform implements every state.

Transitions require coordination of devices, wake sources and firmware methods.

ChrisOS currently has no generic ACPI suspend/resume implementation.

## Why byte-searching for _S5 is not enough

Hobby kernels sometimes search DSDT bytes for the text _S5 and infer shutdown values.

DSDT is AML bytecode, not a text configuration file.

A pattern can occur in contexts that the shortcut does not understand.

Correct shutdown should use the ACPI namespace/AML semantics and validated FADT register descriptions.

ChrisOS should not build its long-term power architecture around a byte-pattern shortcut.

## FACS

FADT can point to the Firmware ACPI Control Structure.

FACS contains firmware/OS coordination fields such as elements related to waking and the ACPI Global Lock.

FACS does not use the ordinary SDT header/checksum format.

A generic table validator therefore must distinguish FACS from standard System Description Tables.

ChrisOS does not currently use FACS.

## Hardware-reduced ACPI

Some platforms do not implement the classic fixed ACPI register blocks.

FADT flags indicate hardware-reduced models.

An ACPI implementation must read the flags before assuming PM1/GPE I/O ports exist.

This is another reason hardcoded power-management port addresses are not a portable architecture.

## SRAT and SLIT

SRAT describes proximity affinity for processors, memory and other initiators.

SLIT describes relative locality distances.

These are inputs to NUMA policy.

ChrisOS does not currently implement NUMA-aware placement or scheduling, so these tables are future platform work rather than active runtime inputs.

## HPET and timers

An ACPI HPET table can describe the High Precision Event Timer.

A future timer subsystem can consume HPET through the central ACPI registry rather than scanning firmware independently.

Current ChrisOS timer paths are not driven by ACPI HPET discovery.

## Thermal and processor power management

ACPI namespace objects can describe thermal zones, cooling relationships, device power states, processor idle/performance capabilities and modern interfaces such as CPPC.

These require AML plus OS policy.

They are far beyond the current signature-printing acpi_probe.

## Firmware trust boundary

ACPI tables and AML are firmware-controlled kernel inputs.

A robust implementation must defend against:

- invalid lengths;
- physical-address overflow;
- corrupted checksums;
- malformed variable records;
- cyclic references;
- excessive AML execution;
- invalid Operation Regions;
- broken OEM firmware;
- hostile virtual firmware.

Parser hardening is part of kernel security.

## Physical pointer safety

ACPI tables contain physical addresses.

Before validating a table checksum, the kernel must first establish that the declared table range is safe to read.

The sequence should be:

~~~text
map/read minimal header
validate minimum length
validate arithmetic and maximum bounds
map/read declared range
validate checksum
only then parse fields
~~~

Checksum validation cannot make an unsafe pointer dereference safe.

## Checksums are not authentication

A checksum detects corruption and malformed data.

It does not authenticate firmware.

Malicious firmware can create fully checksummed hostile tables.

Secure Boot, measured boot and platform trust are separate concerns.

## Current ChrisOS boot ordering

start.c initializes APIC, IOAPIC and SMP before it calls acpi_probe.

Later it disables interrupts and runs ACPI discovery.

Thus ACPI cannot currently provide the topology used earlier by those subsystems.

For an ACPI-driven real-hardware design, validated static-table discovery needs to happen before MADT/MCFG/FADT consumers.

## Current LAPIC path

The current sequence is approximately:

~~~text
mm_selftest:
    map hardcoded 0xFEE00000

apic_init:
    obtain mapped LAPIC pointer

smp_init:
    obtain CPU topology from Limine MP

later:
    acpi_probe prints APIC signature
~~~

This is functional bring-up code, not final dependency architecture.

## Current IOAPIC path

ioapic_init currently prints that the PIC still routes IRQs.

No MADT I/O APIC records or Interrupt Source Overrides are used.

Therefore IOAPIC/ACPI support must remain classified as unimplemented or experimental rather than complete.

## Recommended implementation stages

### Stage 1: trusted root and table integrity

- pass RSDP through bootinfo;
- validate 20-byte and extended RSDP checksums;
- support RSDT and XSDT;
- validate all SDT headers/checksums;
- build a table registry.

### Stage 2: static platform tables

- parse MADT;
- parse MCFG;
- parse FADT fixed fields;
- add HPET as required;
- defer NUMA tables until consumers exist.

### Stage 3: interrupt and PCI consumers

- drive LAPIC/IOAPIC from MADT;
- apply Interrupt Source Overrides;
- expose ECAM from MCFG;
- expose SCI/reset data from FADT.

### Stage 4: AML core

- DSDT/SSDT loading;
- AML decoding;
- namespace;
- object model;
- resource decoding.

### Stage 5: platform methods

- _PIC;
- _PRT;
- _OSC;
- _STA/_CRS;
- event/power methods.

### Stage 6: full power/event model

- SCI;
- GPE;
- shutdown/reset;
- suspend/resume;
- thermal;
- processor power management.

This sequence creates hardware value before AML completeness.

## Suggested ACPI core structures

~~~text
AcpiContext
  rsdp
  root
  tables[]
  madt
  mcfg
  fadt
  namespace
  aml_runtime

AcpiTable
  signature
  physical_address
  length
  revision

AcpiMadt
  lapic_phys
  cpus[]
  ioapics[]
  overrides[]

AcpiMcfg
  segments[]
~~~

Consumers should receive parsed, validated models rather than raw firmware pointers.

## Packed structures are not validation

Packed C structures can simplify field naming.

They do not replace:

- length checks before field access;
- revision-aware optional fields;
- overflow-safe range validation;
- checksum validation;
- alignment/endian care.

A byte-reader/parser layer is safer when tables may be truncated or malformed.

## Reusable checksum algorithm

The arithmetic is simple:

~~~text
sum = 0
for byte in object:
    sum = (sum + byte) & 0xFF

valid when sum == 0
~~~

The difficult part is proving that the object range is safe to read before the loop.

## Deterministic ACPI in ChrisVM

ChrisVM will eventually need platform firmware description if it is to replace QEMU for native ChrisOS boot paths.

A minimal generated ACPI set can include:

~~~text
RSDP
XSDT
MADT
MCFG
FADT
DSDT
~~~

Every table can use deterministic addresses and reproducible checksums.

ChrisOS can then test its own ACPI parser without depending on OVMF table layouts.

## ChrisVM MADT generation

For multiprocessor ChrisVM, the virtual-machine configuration should define:

- virtual CPU/APIC identities;
- LAPIC address;
- I/O APIC;
- optional source overrides.

The same model should generate both virtual devices and MADT entries.

That avoids divergence between hardware behavior and firmware description.

## ChrisVM MCFG generation

When virtual PCIe/ECAM is implemented, one configuration object should define:

~~~text
PCI segment
bus range
ECAM base
~~~

ChrisVM can route that MMIO region and serialize the same values into MCFG.

The guest then exercises the same ECAM discovery path intended for physical UEFI systems.

## ChrisVM AML laboratory

A minimal DSDT can initially expose only objects needed by ChrisOS.

As the AML engine grows, deterministic test firmware can add:

- nested scopes;
- Packages;
- Operation Regions;
- _STA;
- _CRS;
- _PRT;
- _PIC;
- _OSC.

This gives the project controlled AML regression tests.

## Malformed firmware tests

ChrisVM or host tests should eventually inject:

- bad RSDP checksum;
- bad extended checksum;
- truncated XSDT;
- invalid child checksum;
- MADT entry with zero length;
- MCFG with inverted bus range;
- malformed resource templates;
- bounded AML failure cases.

Expected behavior is a controlled parser error, never unchecked kernel memory access.

## Reproducible checker

scripts/check_acpi_examples.py validates chapter mechanics:

1. 20-byte RSDP checksum.
2. Revision-2 extended RSDP checksum.
3. generic SDT checksum.
4. RSDT/XSDT entry-count arithmetic.
5. MADT variable-entry traversal.
6. malformed MADT length rejection.
7. MCFG bus-range sizing.
8. ECAM address arithmetic.
9. checksum repair after synthetic table construction.

It is not an AML interpreter or an ACPI firmware compliance suite.

## Current implementation matrix

| Capability | Current status |
|---|---|
| scan 0xE0000..0xFFFFF for RSDP signature | implemented |
| scan first 1 KiB of EBDA | not implemented |
| UEFI/bootloader RSDP handoff | not implemented in bootinfo |
| RSDP signature validation | implemented |
| RSDP 20-byte checksum | not implemented |
| RSDP extended checksum | not implemented |
| RSDT traversal | not implemented |
| XSDT traversal | partial |
| generic SDT checksum | not implemented |
| ACPI table registry | not implemented |
| MADT signature detection | implemented |
| MADT parsing | not implemented |
| LAPIC address from MADT | not implemented |
| I/O APIC from MADT | not implemented |
| Interrupt Source Overrides | not implemented |
| MCFG signature detection | implemented |
| MCFG allocation parsing / ECAM | not implemented |
| FADT signature detection | implemented |
| FADT parsing | not implemented |
| DSDT/SSDT loading | not implemented |
| AML interpreter | not implemented |
| ACPI namespace | not implemented |
| _PIC / _PRT / _OSC | not implemented |
| SCI/GPE | not implemented |
| generic ACPI reset/power-off | not implemented |
| suspend/resume | not implemented |
| ChrisVM ACPI generation | not implemented |

## Validation boundary

This chapter is reconciled with ChrisOS main revision da3df29cb397932c43d32373871fb9380e688ade.

The UEFI Forum lists ACPI Specification Version 6.6, released in May 2025, as the latest ACPI specification at review time.

Run:

~~~text
python scripts/check_acpi_examples.py
~~~

The checker validates only the chapter's mechanical examples and parser invariants.

## Review triggers

Review this chapter when:

- bootinfo begins carrying RSDP;
- ACPI checksum validation appears;
- RSDT support is added;
- a table registry is introduced;
- MADT begins driving LAPIC/IOAPIC/SMP;
- MCFG begins driving ECAM;
- FADT is parsed;
- DSDT/SSDT loading appears;
- AML/namespace support begins;
- SCI/GPE or power management is implemented;
- ChrisVM starts generating ACPI tables.

## Primary references

- UEFI Forum, Advanced Configuration and Power Interface Specification 6.6.
- UEFI Forum, UEFI Specification 2.11, EFI System Table and Configuration Table handoff.
- PCI/PCIe firmware interfaces referenced by ACPI _PRT and _OSC semantics.
- ChrisOS source files listed in this chapter front matter.
