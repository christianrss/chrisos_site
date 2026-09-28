---
id: reset-firmware
lang: en
type: technical-chapter
volume: 03-boot
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/start.c
  - kernel/metal/bootinfo.c
  - kernel/metal/bootinfo.h
  - kernel/metal/linker.ld
  - kernel/metal/gdt.c
  - kernel/metal/mm.c
  - iso_root/boot/limine/limine.conf
  - README.md
symbols:
  - kstart
  - bootinfo_init
  - bootinfo_get
  - bootinfo_mp_response
  - gdt_init
  - mm_init
  - smp_init
depends_on:
  - acpi-platform
  - x86-registers-flags
  - x86-64-memory-privilege
related:
  - uefi
  - limine
  - boot-information
  - elf-linking
  - linker-script
  - higher-half-kernel
  - power-on-kstart
  - installation-real-hardware
---

# Reset, CPU startup and firmware

## Scope

The first instruction executed by a processor after reset is not the first instruction of ChrisOS.

Between electrical reset and **kstart** there is an entire chain of machine initialization:

~~~text
power / reset
    |
CPU architectural reset state
    |
firmware reset vector
    |
platform initialization
    |
memory/chipset initialization
    |
UEFI services and Boot Manager
    |
Limine
    |
ELF loading + page tables + boot protocol
    |
ChrisOS kstart
~~~

ChrisOS intentionally delegates the low-level firmware and bootloader portions of this chain to platform firmware and Limine.

The kernel does not contain a 16-bit reset stub, does not enter protected mode itself, does not enter long mode itself, does not initialize DRAM from a cold memory controller, and does not implement a UEFI firmware stack.

Its linked entry point is the C function **kstart** in a higher-half ELF64 image. Substantial machine state must therefore exist before the first ChrisOS C instruction executes.

![Reset to ChrisOS entry](../../assets/diagrams/reset-firmware-en.svg)

## Reset is an architectural state transition

Reset does not mean "jump to address zero."

A hardware reset establishes architectural state:

- control registers receive reset values;
- paging is disabled;
- the processor is not yet in the operating system's long-mode environment;
- instruction execution begins at the defined reset vector;
- platform devices and DRAM are not yet in the OS-owned runtime state.

Intel documents CR0 as **0x60000010** after power-up reset. Protection Enable and Paging are clear, so execution begins in real-address mode with paging disabled.

The operating system normally never sees this initial state directly on a PC because firmware executes first.

## The x86 reset vector

The reset code address is formed from unusual initial CS state:

~~~text
CS selector   = 0xF000
hidden CS base = 0xFFFF0000
EIP           = 0xFFF0

linear address =
0xFFFF0000 + 0xFFF0
= 0xFFFFFFF0
~~~

The first instruction is therefore fetched sixteen bytes below the 4-GiB boundary.

The executable checker accompanying this chapter verifies this arithmetic.

## Why the hidden CS base matters

Ordinary real-mode segment translation is usually presented as:

~~~text
linear = segment * 16 + offset
~~~

If that ordinary relation were applied immediately to CS=0xF000:

~~~text
0xF000 << 4 = 0x000F0000
0x000F0000 + 0xFFF0 = 0x000FFFF0
~~~

That is not the reset vector.

At reset the visible selector and hidden segment base have a special architectural relationship. Once software reloads CS with a far control transfer, normal real-mode segment-base rules apply.

This demonstrates that visible register values do not always describe the processor's complete hidden architectural state.

## The reset vector is only a doorway

The vector itself contains only enough firmware code to transfer control into a larger initialization image.

Modern platform initialization requires far more than sixteen bytes.

Firmware must progressively establish:

- temporary execution storage;
- chipset state;
- clocks and silicon dependencies;
- DRAM;
- permanent memory;
- platform buses and protocols;
- boot devices;
- console services;
- the environment used by the OS loader.

The reset vector begins firmware. It does not directly begin ChrisOS.

## Reset types are not equivalent

Power-on reset, cold reset, warm reset and processor INIT events are distinct mechanisms.

They can preserve different portions of platform state.

An x86 INIT event is especially relevant to multiprocessor startup but is not equivalent to resetting the whole platform.

Therefore an OS or emulator should not model every reset-like operation as a complete cold-boot reset-vector replay.

## BSP and APs

One logical processor acts as the Bootstrap Processor for initial firmware execution. Other logical processors are Application Processors.

The classic x86 OS model can start APs through INIT and Startup IPIs.

ChrisOS currently does not own this lowest-level startup path.

Instead, **smp_init** consumes Limine's multiprocessor response and writes an **ap_entry** address into bootloader-provided per-CPU structures.

Thus:

~~~text
architectural INIT/SIPI startup
!=
current Limine-assisted ChrisOS AP startup
~~~

The later SMP chapter covers the runtime implementation.

## Firmware creates the machine that the kernel later manages

Before permanent memory is available, firmware cannot assume that ordinary DRAM is ready.

Platform firmware performs work such as:

- early processor/chipset initialization;
- temporary RAM setup;
- memory-controller initialization;
- DRAM discovery and training;
- permanent-memory establishment;
- firmware-volume discovery;
- boot-device initialization.

This work is silicon-specific.

By the time ChrisOS runs **pmm_init**, DRAM has already been initialized and described to the boot environment.

The PMM allocates pages. It does not train DRAM.

## BIOS and UEFI are different firmware interfaces

Legacy PC BIOS historically exposed real-mode interrupt services and boot-sector-oriented flows.

UEFI defines a substantially different firmware interface including:

- executable image loading;
- handles and protocols;
- Boot Services;
- Runtime Services;
- device paths;
- variables;
- configuration tables;
- a standardized Boot Manager;
- PE/COFF executable images.

ChrisOS's real-hardware plan targets UEFI.

Legacy BIOS compatibility is not the architectural center of the physical-machine roadmap.

## UEFI and Platform Initialization are different layers

The UEFI specification describes the standardized interface used by firmware applications, OS loaders and operating systems.

The Platform Initialization specifications describe a common architecture for constructing firmware itself.

A firmware can provide the UEFI interface without being internally identical to one reference PI implementation.

Nevertheless, the PI phases are a useful model for understanding how a machine becomes bootable.

At review time the UEFI Forum lists:

- UEFI Specification 2.11;
- Platform Initialization Specification 1.10.

## Common PI phase model

A common PI-based flow is:

~~~text
Reset
  |
SEC
  |
PEI
  |
DXE
  |
BDS
  |
UEFI boot application
  |
ExitBootServices
  |
operating system
~~~

Recovery, sleep-resume and implementation-specific paths can differ.

## SEC

SEC is the earliest PI architecture phase.

Its job is to establish enough execution environment to enter PEI.

Responsibilities can include:

- reset-vector entry;
- temporary execution storage;
- early security/measurement roots;
- locating the PEI Foundation;
- handing initial state to PEI.

At this point normal DRAM may not yet be usable.

## Temporary RAM

Firmware needs stack and data storage before permanent DRAM exists.

The implementation can use platform-specific techniques such as cache-as-RAM or on-chip memory.

The key lesson is architectural:

~~~text
CPU can execute
before
normal system DRAM is fully initialized
~~~

This is far earlier than ChrisOS entry.

## PEI

Pre-EFI Initialization establishes the minimum state required for DXE.

A major PEI responsibility is permanent-memory initialization.

PEI modules can initialize:

- memory controller and DRAM;
- boot mode;
- recovery paths;
- platform security state;
- chipset dependencies.

PEI produces Hand-Off Blocks describing state for DXE.

## HOBs

Hand-Off Blocks are structured records used to transfer state from PEI into DXE.

They can describe resources and initialization results.

This is firmware-internal state transfer.

It is conceptually similar to boot information passed to a kernel, but it is not the Limine protocol and it is not directly consumed by ChrisOS.

## Memory training versus PMM

Memory training deals with electrical/timing properties needed to make DRAM reliable.

A physical page allocator deals with ownership of memory that is already functioning.

These are different layers:

~~~text
firmware:
make DRAM usable

bootloader:
describe usable memory

ChrisOS PMM:
allocate/free physical pages
~~~

Confusing them makes a hobby kernel appear to do more hardware initialization than it actually does.

## DXE

Driver Execution Environment performs much of the platform initialization visible in a mature UEFI firmware.

The DXE Foundation provides major firmware services and a dispatcher.

DXE drivers can initialize:

- processors;
- buses;
- storage;
- console devices;
- network devices;
- platform protocols.

This phase builds the environment used by the UEFI Boot Manager.

## Dependency-driven DXE dispatch

DXE drivers can have dependency expressions.

The dispatcher waits until required protocols/services exist before running dependent drivers.

Conceptually:

~~~text
protocol produced
      |
dependent driver becomes eligible
      |
new protocol produced
~~~

This resembles dependency-driven OS initialization but remains firmware architecture.

## Boot Services

Before handoff to the OS, UEFI Boot Services provide functionality such as:

- memory allocation;
- protocol lookup;
- image loading;
- events and timers;
- device access;
- handle management.

A bootloader can use these services to prepare the OS.

After **ExitBootServices**, these services are no longer valid for normal use.

ChrisOS does not call them directly in its current architecture because Limine is the UEFI loader layer.

## Runtime Services

Selected Runtime Services can survive the transition into the OS, subject to the UEFI runtime mapping/calling contract.

Examples include variable and time services.

Booting through UEFI does not imply that the kernel has implemented a full Runtime Services integration.

ChrisOS currently has no general native UEFI Runtime Services subsystem.

## BDS and Boot Manager

Boot Device Selection connects initialized firmware to boot policy.

The UEFI Boot Manager uses mechanisms including:

- BootOrder;
- Boot#### variables;
- device paths;
- EFI applications;
- fallback paths.

Eventually it loads an EFI executable.

In ChrisOS's current architecture, that executable is Limine's EFI program, not the ChrisOS ELF kernel itself.

## Removable media fallback

On x86-64 UEFI removable media, the standardized fallback executable path is:

~~~text
\EFI\BOOT\BOOTX64.EFI
~~~

The ChrisOS installation plan uses this path for Limine.

The chain is therefore:

~~~text
firmware
  -> BOOTX64.EFI
  -> Limine
  -> kernel.elf
  -> kstart
~~~

## EFI System Partition

The ESP is firmware-readable storage for EFI boot artifacts.

ChrisOS's installation flow writes the EFI loader and associated boot files there.

ChrisFS serves a different purpose: persistent operating-system data after ChrisOS is running.

Thus:

~~~text
ESP:
firmware-visible boot chain

ChrisFS:
ChrisOS filesystem
~~~

A working ChrisFS driver does not eliminate the need for a firmware-readable ESP.

## PE/COFF versus ELF

UEFI applications are normally PE/COFF executable images.

The ChrisOS kernel is ELF64.

Limine bridges this format boundary.

Firmware loads an EFI executable; Limine then loads and interprets the kernel ELF according to its boot protocol.

The firmware does not simply treat the kernel ELF as an EFI application.

## Current Limine configuration

The repository contains:

~~~text
/ChrisOS
    protocol: limine
    path: boot():/boot/kernel.elf
    resolution: 1920x1080x32
~~~

The requested resolution is a bootloader preference.

The kernel correctly consumes the actual framebuffer geometry returned by Limine rather than treating the requested resolution as an unconditional hardware fact.

## Limine requests embedded in the kernel

The current kernel requests:

- framebuffer information;
- HHDM;
- memory map;
- multiprocessor information;
- executable command line.

These requests live in special sections retained by the linker script.

They are part of the boot protocol contract between the ELF image and Limine.

## Limine request segment

The linker script retains:

~~~text
.limine_requests_start
.limine_requests
.limine_requests_end
~~~

inside a dedicated loadable segment.

This is important for the native toolchain roadmap.

A linker that emits only one generic executable text segment does not reproduce the real kernel boot contract.

## Kernel linker entry

The current linker script declares:

~~~text
OUTPUT_FORMAT(elf64-x86-64)
OUTPUT_ARCH(i386:x86-64)
ENTRY(kstart)
~~~

and starts the image at:

~~~text
0xffffffff80000000
~~~

The kernel's first linked instruction is therefore reached through a 64-bit C entry point, not a real-mode startup stub.

## Higher-half address

The address:

~~~text
0xffffffff80000000
~~~

is in the upper canonical half under the conventional 48-bit x86-64 canonical-address model.

Limine must establish mappings that make the kernel's ELF virtual addresses executable before transferring control to **kstart**.

The kernel does not first execute at a low identity address and relocate itself there.

## ELF load classes

The linker creates load classes for:

~~~text
requests  writable
text      executable
data      writable
~~~

The BSS is NOLOAD.

The ELF loader must zero memory where program-header memory size exceeds file size.

This is why a bootable kernel image is not merely raw machine code.

## Initial stack and the reserved kernel stack

The linker reserves one MiB between:

~~~text
__stack_bottom
__stack_top
~~~

inside the BSS/data memory image.

Later **gdt.c** uses **__stack_top** as TSS ring-0 **rsp0**.

However, there is no reset/entry assembly in the repository that loads RSP from **__stack_top** before entering **kstart**.

Therefore the reserved stack symbol must not be described as evidence that ChrisOS itself established the initial entry stack.

The initial stack is provided by the boot environment; **__stack_top** is definitely used later for privilege-transition state.

## C entry implies an existing ABI environment

Because **kstart** is compiled C, the processor must already be in a state compatible with the generated 64-bit code.

The kernel build uses a freestanding x86-64 environment and disables the red zone.

The bootloader must provide a valid execution stack before the C prologue executes.

A C function cannot repair an invalid initial stack before its own prologue has already relied on it.

## bootinfo_init

The first major ownership transfer inside ChrisOS is **bootinfo_init**.

It requires:

- supported Limine base revision;
- framebuffer response;
- HHDM response;
- memory map response;
- multiprocessor response.

It records:

- HHDM offset;
- framebuffer address and geometry;
- usable-memory total;
- memory-map count;
- CPU count;
- BSP LAPIC ID.

This converts bootloader-owned structures into kernel-owned summary state.

## Framebuffer contract

ChrisOS receives a framebuffer before initializing its own graphics subsystem.

The initial screen is therefore not created by a native GPU driver programming display hardware from reset.

Firmware and bootloader have already established a display mode and framebuffer mapping.

ChrisOS later consumes that framebuffer and can optionally initialize other graphics paths.

## HHDM contract

Limine provides a Higher-Half Direct Map offset.

**bootinfo_phys_to_virt** adds that offset to physical addresses.

Early memory-management code relies on this mapping.

Thus ChrisOS starts inside an already-paged virtual-memory environment.

Its MM subsystem manages and extends that environment; it does not create the first page tables from reset.

## Memory map handoff

The ownership chain is approximately:

~~~text
firmware initializes DRAM
        |
UEFI knows memory regions
        |
Limine obtains/normalizes boot memory information
        |
Limine response
        |
ChrisOS bootinfo
        |
PMM
~~~

The PMM decides which pages ChrisOS can allocate after handoff.

It is not a firmware memory-training subsystem.

## Multiprocessor handoff

Limine supplies the current multiprocessor response used by ChrisOS.

That response contains CPU records and BSP/AP information used by **smp_init**.

Therefore current AP bring-up is bootloader-assisted.

A future kernel could own lower-level startup sequencing, but that is not the implementation being documented at this revision.

## ExitBootServices

A UEFI loader normally obtains the current memory map and then calls **ExitBootServices**.

The memory-map key synchronizes the handoff. If boot-time allocations change after the map was obtained, the loader may need to acquire the map again and retry.

Limine encapsulates this loader responsibility for ChrisOS.

ChrisOS does not itself implement the current UEFI ExitBootServices sequence.

## Ownership after ExitBootServices

After Boot Services end, the OS owns resources according to UEFI memory-type semantics.

Some firmware memory can be reclaimed; runtime regions require different treatment.

ChrisOS sees the bootloader's memory-map classification and then constructs PMM reservations.

The detailed conversion is handled in later boot-information and PMM chapters.

## UEFI variables are not ESP files

UEFI variables such as BootOrder are firmware-managed objects keyed by names and GUIDs.

They are separate from files stored in the ESP.

Reading **BOOTX64.EFI** from FAT does not imply the OS can read or write firmware NVRAM variables.

ChrisOS currently has no general UEFI-variable subsystem.

## Secure Boot

Secure Boot is a firmware trust policy for authenticated EFI images and related chains of trust.

It is not synonymous with UEFI.

A UEFI machine can operate with Secure Boot disabled.

The ChrisOS roadmap does not currently claim a complete custom Secure Boot implementation.

## Measured boot

Measured boot records measurements for later attestation, commonly using TPM facilities.

Verified boot and measured boot solve different problems.

Neither should be conflated with the basic correctness of the reset-to-kernel execution chain.

## POST terminology

POST is a broad historical label for power-on testing.

Modern PI firmware performs initialization across several phases.

For technical documentation, describing SEC/PEI/DXE/BDS responsibilities is more precise than treating all pre-OS work as one undifferentiated POST routine.

## Firmware volumes

PI implementations commonly store firmware modules in Firmware Volumes.

These can contain PEI modules, DXE drivers and other firmware files.

ChrisOS does not parse these volumes because firmware consumes them before kernel handoff.

They belong to the platform firmware implementation, not the operating-system filesystem.

## Flash mapping

The reset vector is near the top of the 32-bit physical-address range.

Chipset/platform logic maps firmware flash contents so reset code is visible there.

That region must not be confused with ordinary writable DRAM.

The mapping can later change as platform initialization proceeds.

## Microcode

Firmware commonly applies CPU microcode updates before the OS starts.

A mature OS can also support microcode updates.

Microcode changes internal processor implementation while preserving the architectural ISA contract.

ChrisOS currently does not provide a production microcode-management subsystem.

## Feature discovery

Reset establishes baseline architectural state, not permission to use every optional CPU feature blindly.

Firmware and the OS use mechanisms such as CPUID and control registers to discover and enable features.

A future real-hardware hardening phase should make ChrisOS CPU requirements explicit before optional facilities are used.

## Long-mode transition

Entering x86-64 long mode conceptually requires a coordinated transition involving:

- protected-mode state;
- CR4.PAE;
- page tables;
- EFER.LME;
- CR0.PG;
- a 64-bit code segment.

ChrisOS does not perform this transition from reset.

Limine hands control to the kernel in the required execution environment.

## Why kstart is a design boundary

A direct C ELF entry expresses a deliberate architecture:

~~~text
firmware + bootloader:
own pre-C machine transition

ChrisOS:
own kernel initialization after handoff
~~~

This reduces bootstrap code inside the kernel but makes the bootloader contract an essential dependency.

## First source-level work in kstart

The source-level sequence begins with:

1. serial initialization;
2. build identity;
3. bootinfo initialization;
4. boot flags;
5. GDT;
6. IDT/syscall/PIC/PIT/PS2;
7. PMM and MM;
8. heap/process state;
9. framebuffer graphics;
10. APIC/IOAPIC/SMP;
11. ACPI probe;
12. storage/filesystem/runtime.

This is already operating-system initialization.

It is many abstraction levels after CPU reset.

## Earliest diagnostic boundary

**kstart** calls **serial_init** immediately.

If serial initialization fails, interrupts are disabled and the CPU halts.

Therefore "no serial output" does not prove that firmware or Limine failed.

Two states can look similar externally:

~~~text
never entered kstart
or
entered kstart and failed serial initialization
~~~

Physical bring-up should use multiple diagnostic channels when possible.

## ISO boot versus installed-disk boot

Booting the installation ISO and booting the installed disk are different validation gates.

The installed-disk test must remove the installation medium and verify that firmware can discover the ESP, execute the installed EFI loader, locate its configuration and load the intended kernel.

The ChrisOS real-hardware plan correctly treats this as a separate requirement.

## Boot success versus self-hosting

A machine can successfully boot a host-built kernel.

That does not prove the kernel was compiled and linked inside ChrisOS.

The current repository audits explicitly separate installed boot success from the self-hosted kernel milestones.

Boot provenance must therefore be recorded independently from boot success.

## Current production kernel build path

The actual kernel path is approximately:

~~~text
kernel source
    |
host GCC + NASM
    |
host ld with kernel/metal/linker.ld
    |
higher-half kernel ELF
    |
Limine
    |
ChrisOS
~~~

The native toolchain is progressing toward reproducing this but has not yet proven the full production kernel build/install/reboot chain.

## Why the linker script is part of boot architecture

A kernel linker script defines more than addresses.

The current script controls:

- entry symbol;
- higher-half virtual base;
- Limine request segment;
- executable code segment;
- writable data segment;
- BSS;
- one-MiB reserved kernel stack region;
- discarded metadata.

A native linker must reproduce these semantics before its output is boot-equivalent.

## ChrisVM protocol v1

ChrisVM currently bypasses reset and firmware.

Protocol v1 directly creates:

- long mode;
- page tables;
- GDT;
- stack;
- framebuffer;
- ELF entry state.

It does not implement:

- reset vector;
- BIOS;
- UEFI;
- Limine;
- firmware memory initialization.

This is a deliberate direct-guest bootstrap for current tests.

## ChrisVM protocol v1 cannot boot the real ChrisOS kernel

The real kernel is linked at:

~~~text
0xffffffff80000000
~~~

Protocol v1 rejects the higher-half ELF.

It also provides no Limine bootinfo structures.

Therefore "ChrisCPU executes ELF" and "ChrisVM boots ChrisOS" remain different milestones.

## Two future ChrisVM boot models

ChrisVM can eventually support two useful modes.

### Direct kernel mode

Create the exact higher-half mappings and explicit boot-information contract needed by ChrisOS without implementing UEFI.

Advantages:

- smaller scope;
- deterministic;
- faster path to running the kernel.

### Firmware mode

Model enough x86 platform hardware to execute UEFI firmware and Limine.

Advantages:

- validates the real firmware/loader path;
- exercises device discovery before the kernel.

This is much larger in scope.

Both modes are useful and should be named separately.

## Suggested ChrisVM progression

~~~text
Stage 1
current direct long-mode test guests

Stage 2
higher-half ELF
explicit ChrisOS bootinfo
real kernel entry

Stage 3
PCI/ACPI/interrupt platform
more native drivers

Stage 4
optional UEFI + Limine path

Stage 5
reset-vector and firmware research fidelity
~~~

The emulator does not need full reset fidelity before it can become useful for OS development.

## Responsibility matrix

| Responsibility | CPU/Firmware | Limine | ChrisOS |
|---|---:|---:|---:|
| reset architectural state | yes | no | no |
| reset-vector execution | firmware | no | no |
| DRAM initialization | firmware | no | no |
| UEFI environment | firmware | no | no |
| EFI boot policy | firmware | no | no |
| load Limine EFI application | firmware | no | no |
| parse Limine kernel requests | no | yes | declares |
| load ELF64 kernel | no | yes | produces image |
| establish boot mappings | no | yes | consumes |
| framebuffer handoff | firmware/loader | yes | consumes |
| HHDM | no | yes | consumes |
| memory-map handoff | firmware-derived | yes | consumes |
| MP handoff | platform-derived | yes | consumes |
| PMM/MM/heap | no | no | yes |
| filesystem/runtime/desktop | no | no | yes |

## Failure localization

Before early ChrisOS serial output, likely failure classes include:

- firmware boot policy;
- missing EFI loader;
- Limine configuration;
- kernel image loading;
- ELF/protocol mismatch;
- entry-state error;
- serial initialization.

After stable early serial output, the firmware-to-kernel transition has at least progressed to **kstart**.

This sharply reduces the search space during hardware bring-up.

## Boot identity

The real-hardware plan calls for explicit boot identity such as:

~~~text
ChrisOS <version>
Build: <id>
Compiler: <toolchain>
Kernel SHA256: <hash>
~~~

This prevents false validation of an old kernel image.

A boot test without image provenance can succeed while testing the wrong artifact.

## Reproducible source checks

The chapter's checker validates:

1. reset-vector arithmetic;
2. special reset CS base versus normal real-mode segment arithmetic;
3. higher-half canonicality;
4. x86-64 ELF machine number;
5. source-level **ENTRY(kstart)**;
6. current higher-half base;
7. Limine request sections;
8. Limine protocol and kernel path;
9. mandatory boot responses consumed by **bootinfo_init**.

The script does not emulate firmware or certify physical hardware.

## Current implementation matrix

| Layer / feature | Status |
|---|---|
| ChrisOS-owned reset-vector code | not implemented by design |
| 16-bit kernel bootstrap | not implemented by design |
| protected-mode transition in kernel | not implemented by design |
| long-mode transition in kernel | not implemented by design |
| UEFI firmware | external platform dependency |
| Limine | used external bootloader |
| higher-half ELF64 kernel | implemented |
| Limine request segment | implemented |
| framebuffer request | implemented |
| HHDM request | implemented |
| memory-map request | implemented |
| MP request | implemented |
| C entry kstart | implemented |
| native UEFI Runtime Services layer | not implemented |
| UEFI variable subsystem | not implemented |
| ChrisOS-owned Secure Boot | not implemented |
| fully self-hosted production kernel boot | not proven |
| ChrisVM direct small-guest boot | implemented |
| ChrisVM real higher-half ChrisOS boot | not implemented |
| ChrisVM UEFI/Limine boot | not implemented |
| ChrisVM reset/firmware execution | not implemented |

## Validation boundary

This chapter is reconciled with ChrisOS main revision **da3df29cb397932c43d32373871fb9380e688ade**.

At review time, the UEFI Forum lists UEFI Specification 2.11 and Platform Initialization Specification 1.10.

Intel's system-programming documentation defines the processor reset-state and reset-vector behavior described here.

Run:

~~~text
python scripts/check_reset_firmware_examples.py --source .source
~~~

The script validates chapter arithmetic and selected source contracts. It is not a UEFI, Limine or physical-hardware compliance suite.

## Review triggers

Review this chapter when:

- bootloader changes;
- Limine request contract changes;
- linker entry or kernel virtual base changes;
- pre-C assembly entry is introduced;
- initial stack ownership changes;
- UEFI/ACPI/SMBIOS pointers are added to bootinfo;
- Runtime Services integration appears;
- Secure Boot/measured boot becomes supported;
- self-hosted kernel install+reboot is proven;
- ChrisVM boots the real higher-half kernel;
- ChrisVM gains UEFI or reset-vector execution.

## Primary references

- Intel 64 and IA-32 Architectures Software Developer's Manual, Processor Management and Initialization.
- UEFI Forum, UEFI Specification 2.11.
- UEFI Forum, Platform Initialization Specification 1.10.
- ChrisOS source files listed in the chapter front matter.
