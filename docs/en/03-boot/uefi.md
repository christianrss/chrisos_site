---
id: uefi
lang: en
type: technical-chapter
volume: 03-boot
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/bootinfo.c
  - kernel/metal/bootinfo.h
  - kernel/metal/start.c
  - kernel/metal/linker.ld
  - kernel/fs/install.c
  - iso_root/boot/limine/limine.conf
  - scripts/qemu.mk
  - makefile
  - docs/INSTALLATION.md
  - docs/REAL_HARDWARE_PLAN.md
  - docs/HARDWARE_COMPATIBILITY.md
  - docs/NATIVE_TOOLCHAIN_AUDIT.md
symbols:
  - bootinfo_init
  - bootinfo_get
  - bootinfo_phys_to_virt
  - install_disk
  - install_auto
depends_on:
  - reset-firmware
related:
  - limine
  - boot-information
  - acpi-platform
  - partitions-gpt
  - elf-linking
  - installation-real-hardware
---

# UEFI

## Scope

UEFI defines the standardized interface between platform firmware and pre-operating-system software.

It is the environment in which the ChrisOS bootloader executes on the intended physical-hardware profile.

ChrisOS itself does not currently call UEFI Boot Services or Runtime Services directly. Limine occupies that boundary:

~~~text
platform firmware
      |
UEFI interfaces
      |
Limine EFI image
      |
Limine boot protocol
      |
ChrisOS ELF64 kernel
~~~

This distinction is fundamental.

The kernel consumes framebuffer, memory-map, HHDM and multiprocessor information through Limine structures. It does not receive an EFI System Table pointer in its current bootinfo structure and it does not invoke GetMemoryMap, ExitBootServices, GetVariable or SetVariable.

![UEFI to ChrisOS handoff](../../assets/diagrams/uefi-en.svg)

At the time of this review, the UEFI Forum lists UEFI Specification 2.11 as the current UEFI specification.

## What UEFI standardizes

UEFI defines an execution and service environment for firmware applications, OS loaders and drivers.

Major concepts include:

- EFI images;
- image handles;
- the EFI System Table;
- Boot Services;
- Runtime Services;
- a handle/protocol database;
- device paths;
- configuration tables;
- memory maps;
- event and timer services;
- console protocols;
- graphics output;
- block and filesystem protocols;
- firmware variables;
- boot policy;
- security and image authentication mechanisms.

UEFI is therefore much broader than "the firmware can read FAT."

## UEFI is not the operating system

UEFI provides services before the OS takes control.

An operating system can use firmware facilities while its loader is running and then transition to owning the machine.

After ExitBootServices, most UEFI Boot Services disappear from the contract.

The OS must then own:

- memory allocation;
- device drivers;
- scheduling;
- interrupts;
- filesystems;
- process execution;
- most hardware policy.

ChrisOS intentionally crosses this boundary through Limine rather than by embedding UEFI loader code in the kernel.

## EFI image entry

A UEFI application is loaded as an EFI image.

Its entry point conceptually receives:

~~~text
ImageHandle
SystemTable
~~~

The ImageHandle identifies the loaded image in the firmware handle database.

The SystemTable provides access to the core UEFI environment.

Limine is the EFI application in the current ChrisOS boot chain.

The ChrisOS kernel entry does not use this EFI application signature.

## EFI System Table

The EFI System Table is one of the primary roots of the UEFI interface.

Important members include:

- table header;
- firmware vendor string;
- firmware revision;
- console input handle and protocol;
- console output handle and protocol;
- standard error handle and protocol;
- Runtime Services pointer;
- Boot Services pointer;
- number of configuration-table entries;
- configuration-table array.

Conceptually:

~~~text
EFI_SYSTEM_TABLE
  |
  +-- ConIn
  +-- ConOut
  +-- StdErr
  +-- BootServices
  +-- RuntimeServices
  +-- ConfigurationTable[]
~~~

A UEFI loader should treat these pointers as firmware-owned interfaces with precisely defined lifetimes.

## Table headers

UEFI service tables use EFI_TABLE_HEADER metadata.

The header includes fields such as:

- signature;
- revision;
- header size;
- CRC32;
- reserved field.

The CRC protects table contents against accidental corruption.

As with ACPI checksums, CRC integrity is not cryptographic authentication.

A robust direct UEFI consumer validates structural assumptions before calling function pointers.

ChrisOS currently does not parse EFI service tables directly.

## Handles

A UEFI handle is an opaque identifier associated with one or more protocols.

A handle does not itself imply a device type.

The meaning comes from protocols installed on that handle.

For example, one handle can expose a block device through Block I/O and also have a Device Path describing its location.

Another handle can represent a loaded image.

This avoids a global C structure hierarchy hardcoded into firmware clients.

## Protocols

A protocol is an interface identified by a GUID.

Protocols can expose:

- data;
- function pointers;
- device capabilities;
- driver relationships.

Important examples include:

- Loaded Image Protocol;
- Device Path Protocol;
- Graphics Output Protocol;
- Block I/O Protocol;
- Disk I/O Protocol;
- Simple File System Protocol;
- File Protocol;
- Simple Text Input/Output;
- RNG Protocol;
- TCG2 Protocol.

Boot Services provide mechanisms for discovering and opening protocols.

## Protocol database

The firmware maintains a database associating protocol GUIDs with handles.

Clients can locate handles that support a protocol and then open that protocol.

A mature loader typically avoids assuming that "disk zero" or "GPU zero" is represented by a fixed global pointer.

Instead it discovers capabilities through the protocol database.

This is conceptually similar to capability-oriented driver discovery.

## OpenProtocol and ownership semantics

OpenProtocol is more than a pointer lookup.

The call can track which agent/controller relationship is being established and can enforce aspects of driver binding semantics.

UEFI drivers use protocol-open attributes to express relationships such as:

- by handle;
- by driver;
- by child controller;
- exclusive access.

A simple OS loader often uses only a small subset of this machinery, but the full model is designed for a dynamic firmware driver environment.

## LocateProtocol and LocateHandleBuffer

Boot Services provide discovery helpers.

LocateProtocol returns an interface for a matching protocol when one is sufficient.

LocateHandleBuffer can return handles matching search criteria.

These are useful for discovering GOP, filesystem or other services without hardcoding addresses.

The ChrisOS kernel does not make these calls; Limine owns its own UEFI-side discovery.

## Device paths

UEFI device paths describe locations as sequences of typed nodes.

A path can encode relationships through:

- hardware devices;
- ACPI nodes;
- messaging/bus nodes;
- media nodes;
- file paths;
- end nodes.

The path is not a POSIX pathname.

A file path node can appear as one component inside a larger path that identifies the disk, partition and file.

## Why device paths matter

Boot variables do not merely store a string such as C:\bootloader.

A UEFI load option can carry a binary device path identifying the target.

That path can include enough information to locate:

~~~text
PCI controller
 -> storage device
 -> partition
 -> filesystem path
~~~

This makes boot policy independent of operating-system drive-letter conventions.

## Loaded Image Protocol

A loaded EFI image can query the Loaded Image Protocol associated with its ImageHandle.

The structure includes information such as:

- parent image handle;
- System Table;
- device handle from which the image was loaded;
- file path;
- image base;
- image size;
- code memory type;
- data memory type;
- unload callback.

A bootloader can use this information to understand its own origin.

ChrisOS does not consume Loaded Image Protocol directly because it is not the EFI application.

## Boot Services lifetime

Boot Services exist until ExitBootServices succeeds.

Important categories include:

- task-priority and events;
- memory allocation;
- protocol handling;
- image services;
- miscellaneous boot services.

After the handoff, the OS must not continue calling ordinary Boot Services functions.

This lifetime boundary is one of the most important UEFI concepts for an OS loader.

## AllocatePages

AllocatePages reserves page-granular physical memory from the UEFI memory map.

A loader can request:

- any suitable pages;
- pages below a maximum address;
- a particular address.

The allocation changes the memory map.

This becomes important immediately before ExitBootServices because every allocation can invalidate a previously obtained MapKey.

## AllocatePool

AllocatePool allocates smaller buffers from firmware-managed boot memory.

It is convenient for loader data structures.

Like other Boot Services allocations, it changes memory ownership and can affect the memory-map generation.

A loader should not perform casual allocations between the final GetMemoryMap and ExitBootServices.

## UEFI memory map

GetMemoryMap returns an array of EFI memory descriptors.

Each descriptor includes fields such as:

- Type;
- PhysicalStart;
- VirtualStart;
- NumberOfPages;
- Attribute.

The call also reports:

- total buffer size;
- MapKey;
- descriptor size;
- descriptor version.

A critical rule is that callers must use the returned descriptor size when iterating.

They must not assume the compile-time C structure size is the stride forever.

## Memory descriptor stride

Conceptually:

~~~text
cursor = map_buffer

while cursor < map_buffer + map_size:
    descriptor = cursor
    consume descriptor
    cursor += descriptor_size
~~~

Using sizeof(EFI_MEMORY_DESCRIPTOR) as the iteration stride rather than the returned DescriptorSize is a common bootloader bug.

The executable checker in this chapter models descriptor-stride arithmetic.

## Common UEFI memory types

The UEFI memory map distinguishes classes such as:

- Reserved;
- Loader Code;
- Loader Data;
- Boot Services Code;
- Boot Services Data;
- Runtime Services Code;
- Runtime Services Data;
- Conventional Memory;
- Unusable Memory;
- ACPI Reclaim Memory;
- ACPI Memory NVS;
- MMIO;
- MMIO Port Space;
- persistent/unaccepted platform memory categories in newer specifications.

The exact ownership rules differ by type.

A kernel cannot safely mark every descriptor as free after handoff.

## Conventional memory

EfiConventionalMemory represents memory available for general-purpose allocation at the UEFI level.

After the loader has completed handoff, this typically becomes a source of OS-owned free memory, subject to reservations introduced by the loader/kernel.

ChrisOS does not see raw EFI descriptors directly in its current design.

It sees the Limine memory map after Limine has processed the firmware environment.

## Boot Services memory after handoff

Boot Services Code and Boot Services Data are used by firmware before ExitBootServices.

After the transition, they are no longer needed by Boot Services and can generally become reclaimable according to the UEFI handoff rules.

However, the OS should not infer this from numeric address ranges.

It must use descriptor types and the loader contract.

## Runtime memory

Runtime Services Code and Data remain firmware-owned for runtime interfaces.

Descriptors used for runtime services carry runtime semantics and must be preserved appropriately if the OS intends to use Runtime Services.

A kernel that does not use Runtime Services can simplify policy, but it still must not overwrite runtime firmware regions arbitrarily.

## ACPI memory classes

UEFI distinguishes ACPI Reclaim Memory and ACPI Memory NVS.

ACPI Reclaim memory can become reusable after the OS has consumed the required ACPI tables and no longer needs the storage.

ACPI NVS must be preserved across relevant power-management transitions.

This is one connection between the UEFI memory map and the previous ACPI chapter.

## GetMemoryMap two-call pattern

The first GetMemoryMap call is often used to discover the required buffer size.

The caller then allocates a buffer with enough extra space for possible map growth and calls again.

Conceptually:

~~~text
GetMemoryMap(NULL)
 -> BUFFER_TOO_SMALL + required_size

allocate buffer with margin

GetMemoryMap(buffer)
 -> descriptors + MapKey
~~~

Because allocation itself changes the map, the margin is important.

## MapKey

GetMemoryMap returns a MapKey identifying the current memory-map generation.

ExitBootServices requires the current key.

If the memory map changes after that GetMemoryMap call, the old key is stale.

ExitBootServices can then fail with EFI_INVALID_PARAMETER.

This is deliberate synchronization, not a random firmware failure.

## Correct ExitBootServices loop

A robust loader uses a sequence conceptually like:

~~~text
repeat:
    obtain fresh memory map
    map_key = returned key

    avoid allocations and protocol operations that mutate map

    status = ExitBootServices(image_handle, map_key)

until success
or a non-retryable failure occurs
~~~

If the call fails because the key became invalid, the loader obtains a new map and retries.

## The transition point

Before successful ExitBootServices:

~~~text
firmware Boot Services own part of machine policy
~~~

After successful ExitBootServices:

~~~text
operating system / loader-created environment owns normal runtime control
~~~

Runtime Services are a specifically defined exception.

This moment is a hard lifecycle boundary.

## ChrisOS and ExitBootServices

No ChrisOS source path currently calls GetMemoryMap or ExitBootServices.

That is expected.

Limine is the UEFI bootloader and owns this transition before entering the kernel.

The kernel therefore begins after the firmware Boot Services lifecycle has effectively been resolved by the loader.

## Why bootinfo cannot reconstruct raw UEFI history

After Limine transforms firmware information into its own boot protocol structures, ChrisOS does not automatically retain:

- the original EFI System Table;
- original EFI memory descriptors;
- the MapKey;
- protocol handles;
- Boot Services function pointers;
- the ImageHandle of Limine.

These details belong to the loader side unless explicitly forwarded.

The current bootinfo does not forward them.

## Configuration tables

The EFI System Table contains a ConfigurationTable array.

Each entry pairs:

~~~text
VendorGuid
VendorTable pointer
~~~

Well-known tables can include pointers to platform structures such as:

- ACPI RSDP;
- SMBIOS entry structures;
- other vendor/platform tables.

This is the UEFI-native way a loader can find important firmware data without scanning legacy physical-memory windows.

## UEFI and the current ACPI gap

The previous ACPI chapter found that current ChrisOS scans the legacy BIOS region for RSDP.

A better UEFI-oriented chain is:

~~~text
EFI System Table
 -> ACPI configuration-table GUID
 -> RSDP
 -> bootloader request/response
 -> ChrisOS bootinfo
~~~

Because ChrisOS does not receive EFI System Table directly, Limine should be the layer that forwards RSDP through its protocol.

Current ChrisOS bootinfo does not request/store that response yet.

## SMBIOS

SMBIOS is another example of firmware metadata commonly discoverable through UEFI configuration tables.

It can describe product, board, firmware, memory-device and system-identification information.

ChrisOS's real-hardware plan mentions SMBIOS as optional identification data.

No general SMBIOS parser is present in the current kernel.

## Graphics Output Protocol

Graphics Output Protocol, GOP, provides a firmware graphics interface.

It exposes:

- supported modes;
- current mode;
- framebuffer base and size;
- pixel format;
- pixel bit masks where applicable;
- horizontal and vertical resolution;
- PixelsPerScanLine.

A UEFI application can query and set graphics modes before boot handoff.

## PixelsPerScanLine

PixelsPerScanLine is especially important.

The framebuffer stride can exceed visible horizontal resolution.

Thus:

~~~text
pitch_bytes
may be greater than
width * bytes_per_pixel
~~~

ChrisOS correctly consumes the actual pitch returned through Limine rather than assuming width times four.

The real-hardware plan explicitly requires testing multiple framebuffer sizes and recording pitch.

## GOP pixel formats

GOP can describe pixel layout using predefined formats or explicit bit masks.

A kernel that assumes every firmware framebuffer is one fixed ARGB/XRGB ordering can produce incorrect colors on another machine.

Limine abstracts framebuffer metadata to the kernel, but ChrisOS still needs to respect the returned layout contract.

The current graphics path strongly expects a 32-bpp framebuffer.

## GOP is not GPU acceleration

A GOP framebuffer gives a pre-OS linear framebuffer.

It is not equivalent to a native GPU driver.

After boot, an operating system can keep using the framebuffer as a simple display path without implementing:

- command submission;
- VRAM management;
- shaders;
- 3D acceleration;
- display-engine power management.

This is why GOP is appropriate for ChrisOS hardware profile 1.

## Block I/O Protocol

EFI_BLOCK_IO_PROTOCOL exposes block-oriented access to media.

Its media structure describes properties such as:

- media present;
- removable media;
- media ID;
- block size;
- last block;
- alignment constraints.

The protocol supports block reads, writes and flushes.

UEFI firmware drivers use this abstraction before the OS's native storage drivers take over.

## Disk I/O Protocol

Disk I/O provides byte-oriented access over a disk-like device.

It can simplify reads/writes that are not aligned to full block boundaries.

A bootloader can use either higher-level filesystem protocols or lower-level disk protocols depending on its own design.

ChrisOS does not depend on UEFI Block I/O after kernel entry.

Its native storage stack uses ATA, AHCI, NVMe, VirtIO and USB paths.

## Partition discovery

UEFI firmware can discover partitions including GPT.

The EFI System Partition uses the well-known GUID:

~~~text
C12A7328-F81F-11D2-BA4B-00A0C93EC93B
~~~

Current install.c writes that GUID into the first GPT partition entry.

The checker validates the byte-order reconstruction of the GUID used by the source.

## Simple File System Protocol

EFI_SIMPLE_FILE_SYSTEM_PROTOCOL represents a mounted firmware-readable filesystem volume.

OpenVolume returns the root EFI_FILE_PROTOCOL.

A loader can then navigate files and directories.

This is the UEFI-side abstraction for reading boot files from FAT volumes.

ChrisOS does not call it directly.

## EFI File Protocol

EFI_FILE_PROTOCOL supports operations such as:

- Open;
- Close;
- Read;
- Write;
- GetPosition;
- SetPosition;
- GetInfo;
- SetInfo;
- Flush.

UEFI file paths use firmware conventions and Unicode strings rather than POSIX byte-path semantics.

The protocol is not the same as ChrisFS's file API.

## EFI filesystem format

UEFI defines a specific EFI FAT filesystem profile.

The current UEFI 2.11 specification describes FAT32 for a system partition and FAT12/FAT16 for removable media, while requiring firmware FAT support according to the EFI filesystem rules.

For a hard-disk EFI System Partition, the project target should be a conforming FAT32 system partition.

## Important current ChrisOS installer mismatch

The real-hardware plan says:

~~~text
GPT + FAT32 ESP + ChrisFS
~~~

but current install.c writes a FAT16-style filesystem:

- the BPB label contains FAT16;
- FAT entries are uint16_t;
- the root directory is a fixed region;
- FAT16 cluster-chain encoding is used.

At the same time, the GPT partition uses the EFI System Partition GUID.

Therefore the current installed hard-disk ESP does **not** yet match the project's stated FAT32 target.

This may work under permissive firmware/emulators but should not be called a spec-conforming physical UEFI hard-disk ESP until the installer is corrected and tested.

## Why this matters for real hardware

Firmware compatibility differs.

An emulator accepting a FAT16-formatted GPT ESP does not prove that physical UEFI firmware will accept the same layout.

The physical hardware gate should require:

- FAT32 ESP;
- correct BPB/FSInfo/FAT32 structures;
- ESP GPT type;
- fallback boot path;
- second boot with install media removed.

This is a concrete implementation gap discovered while reconciling this chapter.

## Removable-media FAT nuance

UEFI permits FAT12, FAT16 or FAT32 for removable media according to the EFI filesystem rules.

That does not turn a FAT16 hard-disk ESP into the project's intended FAT32 system partition.

Media class and system-partition semantics must be distinguished.

## ESP directory layout

For removable-media fallback on x86-64:

~~~text
\EFI\BOOT\BOOTX64.EFI
~~~

is the conventional default EFI application.

Current installer code creates the hierarchy:

~~~text
EFI/
  BOOT/
    BOOTX64.EFI
~~~

and also places kernel/configuration data in its ESP layout.

## Current ESP writer

Current install.c writes a minimal FAT hierarchy itself rather than invoking firmware filesystem services.

That is expected because installation runs after ChrisOS has booted and owns its native block devices.

The installer constructs:

- GPT;
- ESP filesystem structures;
- directories;
- BOOTX64.EFI;
- kernel ELF;
- Limine configuration;
- ChrisFS partition.

This is an OS-side disk formatter, not a UEFI Boot Services operation.

## Boot variables

UEFI variable services provide persistent firmware key/value storage.

Variables are identified by:

~~~text
Unicode name
+
Vendor GUID
~~~

Attributes can specify behavior such as:

- nonvolatile storage;
- visibility during Boot Services;
- visibility during Runtime Services;
- authenticated-write requirements.

## Standard boot variables

UEFI Boot Manager uses standard global variables including:

- BootOrder;
- BootNext;
- BootCurrent;
- Timeout;
- Boot#### load options.

A Boot#### variable contains an EFI_LOAD_OPTION describing attributes, description, device path and optional data.

BootOrder contains an ordered list of the numeric #### identifiers.

## ChrisOS does not currently create Boot####

The current installer intentionally relies on the fallback path.

Repository documentation explicitly states that it does not install an NVRAM Boot#### entry.

This is a valid simplification for early bring-up because fallback-path boot avoids firmware-specific NVRAM management.

It should be documented as:

~~~text
installed fallback loader: implemented
UEFI NVRAM boot registration: not implemented
~~~

## Why fallback is useful

The removable-media-style fallback path provides a boot method that can work without modifying firmware boot variables.

This reduces installer complexity and avoids:

- firmware variable write failures;
- vendor-specific boot-manager behavior;
- stale Boot#### entries;
- NVRAM capacity issues.

Later, explicit Boot#### registration can improve user experience while preserving fallback recovery.

## BootNext

BootNext can request a one-time boot option for the next boot.

Firmware generally removes/consumes the one-shot behavior after using it.

This is useful for installers and firmware update flows.

ChrisOS does not currently manipulate BootNext.

## Runtime variable services

GetVariable, SetVariable, GetNextVariableName and QueryVariableInfo are Runtime Services.

An OS that wants to manage firmware variables after boot must preserve and correctly call the firmware runtime environment.

ChrisOS currently does not do this.

Therefore adding a shell command that writes BootOrder would require a new firmware-runtime subsystem, not merely a FAT file write.

## UEFI calling convention on x86-64

UEFI defines an x64 calling convention represented in source by EFIAPI.

It follows the x64 firmware ABI convention, which is different from the normal System V AMD64 ABI used by the current ChrisOS kernel build.

Directly calling UEFI function pointers from ordinary SysV-compiled kernel C would therefore require ABI-aware wrappers or compiler attributes.

This is another reason Runtime Services integration is a distinct engineering task.

## System V versus UEFI x64 ABI

Current ChrisOS C kernel code follows the System V AMD64 convention used by its host GCC build.

Conceptually, normal integer argument registers begin:

~~~text
SysV:
RDI RSI RDX RCX R8 R9
~~~

UEFI x64 uses the firmware x64 convention with its own argument-register and stack requirements.

A function pointer cannot be called safely merely because both sides execute 64-bit x86 instructions.

ABI is part of the binary contract.

## SetVirtualAddressMap

Runtime firmware initially operates with mappings established during boot.

An OS that wants to call Runtime Services in its own virtual-address environment can use the UEFI runtime virtual-address transition defined by SetVirtualAddressMap.

Runtime descriptors are associated with their virtual addresses for subsequent calls.

This is a delicate one-way lifecycle operation.

ChrisOS currently avoids this complexity by not using Runtime Services.

## ConvertPointer

ConvertPointer supports converting pointers stored by runtime components when virtual mappings are established.

This belongs to the runtime transition mechanism.

A kernel that has no Runtime Services integration should not expose partial implementations of these calls.

## Console protocols

The System Table exposes console input/output interfaces.

Simple Text Output can display text before a graphics or native console exists.

Simple Text Input can receive basic keyboard input through firmware.

These protocols are useful for bootloaders.

ChrisOS does not use them after entry; it initializes its own serial, framebuffer and input stack.

## Firmware events

UEFI Boot Services support event objects, notification callbacks and timer events.

Firmware drivers and applications can use these for asynchronous coordination.

These events stop being a general OS runtime primitive after ExitBootServices.

ChrisOS has its own interrupts, timers, jobs and event-like mechanisms.

## LoadImage

LoadImage asks firmware to load a UEFI image.

The source can be represented by a device path or buffer.

Firmware performs image-format validation appropriate to UEFI executables.

This is how a boot manager or another EFI application can load another EFI image.

The ChrisOS kernel ELF is not a normal UEFI PE/COFF application, so Limine performs the separate kernel-load step.

## StartImage

StartImage transfers control to the loaded EFI image's entry point.

The child image receives its own ImageHandle and access to the System Table.

When Limine is loaded as an EFI application, it participates in this firmware image model.

ChrisOS kstart does not.

## PE32+ on x86-64

The x86-64 UEFI application format is PE32+ for the x64 machine architecture.

The conventional fallback filename reflects architecture:

~~~text
BOOTX64.EFI
~~~

Other architectures use different machine-specific fallback names.

This filename is not arbitrary branding.

## Image authentication

Under Secure Boot policy, firmware can authenticate images before execution.

Trust policy can involve:

- Platform Key;
- Key Exchange Keys;
- allowed signature database;
- forbidden/revoked signature database;
- authenticated variable updates.

The exact policy is firmware state, not a property inferred solely from the presence of BOOTX64.EFI.

## Secure Boot variables

Common variables associated with Secure Boot state include:

- PK;
- KEK;
- db;
- dbx;
- SecureBoot;
- SetupMode.

A production installer that wants first-class Secure Boot integration must understand signing and trust enrollment policy.

ChrisOS currently lists a custom Secure Boot implementation as out of scope.

## Limine and Secure Boot

Using Limine as the bootloader does not by itself mean Secure Boot is configured.

Whether the EFI image is accepted under Secure Boot depends on platform trust policy and image signing/enrollment.

The ChrisOS documentation should therefore avoid claiming Secure Boot simply because the system boots through UEFI.

## TCG2 and measured boot

UEFI defines interfaces such as TCG2 for interaction with TPM-backed measured boot environments.

Measured boot records events and measurements rather than merely deciding whether to execute an image.

ChrisOS does not currently integrate with TCG2.

This can become a later security/attestation research area.

## Watchdog timer

UEFI includes a watchdog mechanism in Boot Services.

The firmware can reset a misbehaving boot application if the watchdog expires.

OS loaders generally manage this according to their boot sequence.

After ExitBootServices, the operating system must use its own watchdog/device mechanisms.

ChrisOS does not expose UEFI watchdog control because Limine owns the pre-kernel stage.

## Time services

UEFI Runtime Services can provide GetTime/SetTime and wakeup-time functions.

This is firmware time, distinct from the kernel's timer interrupt and monotonic scheduling clock.

An OS can use RTC/ACPI/other hardware directly instead.

ChrisOS currently does not use UEFI Runtime Services for timekeeping.

## ResetSystem

UEFI Runtime Services includes ResetSystem.

It can request platform reset or shutdown modes.

ChrisOS currently does not route its reboot path through a generic UEFI Runtime Services layer.

The previous ACPI chapter also described ACPI reset as another possible platform mechanism.

A mature kernel can choose among validated platform reset mechanisms.

## Capsule update

UEFI Runtime Services can support firmware capsule update workflows.

This is a mechanism for delivering firmware updates through standardized interfaces.

It is well outside the current ChrisOS boot scope.

The presence of UEFI does not require ChrisOS to become a firmware update utility.

## Security boundary of firmware calls

Calling firmware code after the OS owns the machine is a major trust boundary.

Firmware runtime code executes with high privilege and may depend on:

- preserved memory regions;
- platform-specific mappings;
- synchronization assumptions;
- calling conventions.

A kernel should minimize and isolate firmware runtime dependencies.

ChrisOS's current "no Runtime Services" design is simple, though it gives up conveniences such as direct NVRAM variable management.

## Bootloader trust boundary

Limine is also privileged code.

It controls:

- where the kernel ELF is loaded;
- page mappings at entry;
- boot information;
- framebuffer handoff;
- CPU handoff data.

ChrisOS validates portions of the response before use, but it fundamentally trusts the bootloader to establish a coherent execution environment.

This is normal for a boot protocol.

## Current ChrisOS source boundary

Searches of the reviewed source tree find no native calls or definitions corresponding to:

- EFI_SYSTEM_TABLE;
- GetMemoryMap;
- ExitBootServices;
- BootOrder manipulation.

That absence is consistent with the architecture:

~~~text
UEFI implementation details
      handled by Limine

ChrisOS
      consumes Limine protocol
~~~

## Installer versus bootloader responsibilities

The installer runs as ChrisOS code after the OS has already booted.

It writes files that the next firmware boot can consume.

Therefore the installer needs knowledge of:

- GPT;
- ESP type GUID;
- EFI filesystem format;
- fallback filename;
- Limine configuration placement.

It does not need to call current Boot Services to write the disk.

## Current hard-disk boot status

Repository documentation currently distinguishes:

- QEMU installation image creation: proven in existing gates;
- installed-disk boot without installation ISO under a dedicated OVMF gate: not yet proven;
- physical UEFI machine boot: not yet proven.

This distinction must remain visible.

A successful image-format self-test is not the same as firmware actually booting that disk.

## OVMF

OVMF is a UEFI firmware implementation commonly used with QEMU.

A dedicated installed-disk UEFI test should boot the generated disk under OVMF with the installation media removed.

That gate validates more of the actual firmware discovery path than simply examining ESP bytes.

The real-hardware plan identifies such a gate but does not claim it has passed.

## QEMU acceptance is not universal firmware acceptance

UEFI implementations differ in strictness and quirks.

A layout accepted by one virtual firmware can still fail on:

- another OVMF revision;
- AMI-based physical firmware;
- Insyde firmware;
- enterprise/server firmware;
- devices with unusual block geometry.

The installer must target the specification, not observed permissiveness.

## FAT32 conversion requirement

Before the project claims a spec-aligned hard-disk ESP for profile 1, install.c should evolve from its current minimal FAT16 writer to a correct FAT32 system-partition writer.

That requires details such as:

- FAT32 BPB fields;
- 32-bit FAT entries;
- root directory as a cluster chain;
- FSInfo structure where required by the profile;
- backup boot sector;
- cluster-count rules;
- correct FAT32 identification;
- robust long filename handling;
- capacity calculations.

The exact implementation belongs in the partitions/install chapter, but the UEFI requirement belongs here.

## Device paths for explicit boot registration

If ChrisOS later creates Boot#### variables, it will need to construct a correct EFI device path to the installed loader.

A reliable load option cannot simply store a POSIX string.

It must encode the partition/device context and file path according to UEFI device-path structures.

This is a nontrivial next step beyond the fallback path.

## GPT and ESP GUID

The installer already writes the correct GPT type GUID bytes for the EFI System Partition.

The checker reconstructs them as:

~~~text
C12A7328-F81F-11D2-BA4B-00A0C93EC93B
~~~

This is an example where the current implementation already aligns with the UEFI/GPT boot model even though the filesystem format still needs work.

## Boot provenance

UEFI can find several bootloaders and several storage devices.

The kernel therefore needs its own artifact identity to prove which image ultimately executed.

ChrisOS already has build-identity work.

The hardware plan's desired markers include version, build ID, compiler/toolchain stage and kernel hash.

This is essential when testing fallback and NVRAM boot paths.

## Future direct UEFI data handoff

Even while keeping Limine, ChrisOS can request additional firmware-derived information through the boot protocol.

Useful candidates include:

- ACPI RSDP;
- SMBIOS;
- EFI System Table pointer if Runtime Services are intentionally supported;
- EFI memory-map information only if needed beyond Limine's abstraction.

The kernel should not preserve firmware pointers merely because they exist.

Every retained interface expands the boot ABI and trust surface.

## Why Limine remains valuable

Limine isolates ChrisOS from many firmware-loader details.

It handles the work needed to provide:

- ELF kernel loading;
- higher-half entry;
- initial paging;
- framebuffer discovery;
- HHDM;
- memory map;
- multiprocessor information.

This lets the kernel focus on OS architecture rather than duplicating a UEFI loader.

The project's stated plan is to keep Limine.

## If ChrisOS eventually implements its own loader

Replacing Limine would require a separate EFI application, not just modifications to kstart.

That loader would need at minimum:

- EFI entry point and ABI;
- System Table access;
- filesystem/device discovery;
- kernel ELF parsing;
- memory allocation;
- page-table construction;
- framebuffer selection;
- memory-map capture;
- ExitBootServices retry logic;
- bootinfo construction;
- transfer to higher-half kernel.

This is a substantial standalone project.

## ChrisVM relationship

ChrisVM currently bypasses UEFI entirely.

A future firmware-fidelity mode would need enough virtual hardware to run a UEFI implementation.

That can include:

- reset-capable x86 CPU behavior;
- chipset/platform devices expected by firmware;
- flash mapping;
- PCI;
- timers;
- storage;
- graphics;
- ACPI generation;
- EFI-compatible boot media.

This is much larger than the direct-kernel boot path.

## Direct-mode ChrisVM remains useful

For most ChrisOS kernel development, ChrisVM can first implement a Limine-equivalent explicit handoff without implementing UEFI.

That provides:

- deterministic kernel entry;
- higher-half mappings;
- bootinfo;
- virtual framebuffer;
- memory map;
- CPU topology.

Later UEFI execution can validate the pre-kernel platform chain as a separate fidelity tier.

## Reproducible checker

scripts/check_uefi_examples.py validates chapter-level mechanics and current source contracts:

1. EFI System Partition GUID reconstruction.
2. x86-64 fallback filename.
3. page-count arithmetic.
4. memory-descriptor stride iteration.
5. MapKey freshness model.
6. current installer ESP type GUID.
7. current installer FAT16 marker and 16-bit FAT state.
8. BOOTX64.EFI installation path.
9. Limine kernel protocol/path.
10. absence of native EFI System Table / ExitBootServices code in current kernel source.

These tests do not execute firmware.

## Current implementation matrix

| Capability | ChrisOS status |
|---|---|
| boot through Limine EFI image | project architecture / QEMU build path |
| EFI System Table consumed by kernel | not implemented |
| Boot Services called by kernel | not implemented |
| Runtime Services called by kernel | not implemented |
| GetMemoryMap in kernel | not implemented |
| ExitBootServices in kernel | not implemented; loader responsibility |
| GOP consumed indirectly through Limine framebuffer | implemented |
| raw GOP protocol in kernel | not implemented |
| UEFI memory map consumed directly | not implemented |
| Limine memory map consumed | implemented |
| ESP GPT type GUID | implemented |
| fallback EFI/BOOT/BOOTX64.EFI written | implemented |
| hard-disk FAT32 ESP | not implemented; current writer is FAT16-style |
| Boot#### NVRAM registration | not implemented |
| BootOrder manipulation | not implemented |
| UEFI variable services | not implemented |
| Secure Boot owned/configured by ChrisOS | not implemented |
| TCG2 measured boot | not implemented |
| installed-disk OVMF-only second-boot gate | not yet proven |
| physical UEFI machine boot | not yet proven |
| ChrisVM UEFI firmware execution | not implemented |

## Validation boundary

This chapter is reconciled with ChrisOS main revision **da3df29cb397932c43d32373871fb9380e688ade**.

The UEFI Forum currently lists UEFI Specification 2.11, released in December 2024, as the latest UEFI specification.

The project uses Limine as an external bootloader. This chapter does not attempt to document Limine internals; the next chapter documents the boot protocol from the ChrisOS side.

Run:

~~~text
python scripts/check_uefi_examples.py --source .source
~~~

The checker validates selected calculations and repository facts only.

## Review triggers

Review this chapter when:

- installer ESP changes from FAT16-style to FAT32;
- the installed-disk OVMF gate is added or passes;
- Boot####/BootOrder support appears;
- Runtime Services are introduced;
- EFI System Table is preserved in bootinfo;
- RSDP/SMBIOS firmware tables are forwarded through Limine;
- Secure Boot becomes a supported project target;
- Limine is replaced or supplemented by a custom EFI loader;
- ChrisVM gains UEFI firmware execution.

## Primary references

- UEFI Forum, UEFI Specification 2.11.
- UEFI Forum, Platform Initialization Specification 1.10.
- ChrisOS source files listed in this chapter front matter.
