---
id: hardware-profile
lang: en
type: technical-chapter
volume: 13-real-hardware
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/start.c
  - kernel/metal/bootinfo.c
  - kernel/metal/pci.c
  - kernel/metal/ps2.c
  - kernel/metal/acpi.c
  - kernel/metal/smp.c
  - kernel/fs/storage.c
  - kernel/fs/ata_pio.c
  - kernel/fs/ahci.c
  - kernel/fs/nvme.c
  - kernel/fs/virtio_blk.c
  - kernel/fs/usb_msc.c
  - kernel/fs/xhci.c
  - kernel/gfx/graphics.c
  - kernel/gfx/vgpu.c
  - kernel/gfx/ac97.c
  - kernel/net/virtio_net.c
  - SYS/DRV/HWDISC.CC
  - scripts/qemu.mk
symbols:
  - kstart
  - bootinfo_init
  - storage_init
  - ps2_init
  - smp_init
  - virtio_gpu_boot
  - ac97_init
  - xhci_hid_probe
  - virtio_net_init
depends_on:
  - uefi-disk-boot
  - installation-real-hardware
  - x86-64-memory-privilege
related:
  - bringup-diagnostics
  - driver-compatibility
  - qemu-gates
  - hardware-gates
---

# ChrisOS hardware profile and evidence boundary

## Scope

ChrisOS contains enough native x86-64 drivers to define a meaningful hardware target, but the existence of a driver is not the same as verified support on physical hardware.

This chapter defines the current hardware profile as an **evidence model**, not as a marketing compatibility list.

Four distinct states must remain separate:

1. **implemented** — source contains an executable path for the device/class;
2. **host-tested** — algorithms or driver-adjacent logic are exercised by host tests;
3. **QEMU-validated** — a QEMU gate reaches explicit success markers with a modeled device;
4. **physical-hardware validated** — the same path has been reproduced on a named real machine/controller/device with recorded evidence.

At revision e05a17fd76333114a3fb5c2452f38ca747d4ac56, much of the practical platform is implemented and QEMU-validated.

A general physical-hardware compatibility matrix has not yet been established.

That distinction is the central rule of this chapter.

## Current practical target

The narrowest credible current physical bring-up target is approximately:

    x86-64 machine
    UEFI firmware
    Secure Boot disabled
    Limine boot
    32-bpp firmware framebuffer
    conventional PC-compatible serial/PIT/PIC assumptions
    one storage controller reachable by current discovery
    512-byte logical sectors
    PS/2 or currently supported xHCI HID input
    network optional
    audio optional

This is a **candidate bring-up profile**, not a promise that any machine matching those labels will boot.

Real systems differ in PCI topology, firmware behavior, interrupt routing, ACPI data, graphics handoff and controller details.

## Evidence levels

### Level 0 — source path

A subsystem is Level 0 when a concrete current implementation exists.

Examples include:

- AHCI;
- NVMe;
- ATA PIO;
- VirtIO block;
- USB mass storage;
- xHCI HID;
- PS/2;
- VirtIO GPU;
- AC97;
- VirtIO network.

Level 0 proves the code exists.

It says nothing about whether the code has run successfully on either emulation or physical hardware.

### Level 1 — deterministic/host test

A host test can validate:

- data structures;
- protocol encoding;
- arithmetic;
- filesystem format;
- queue logic;
- parser behavior;
- state-machine invariants.

This is stronger than source inspection but still does not prove a real controller interaction.

### Level 2 — virtual hardware gate

A QEMU gate proves that a driver path can communicate with a particular modeled device under a known virtual topology.

Current gates include classes such as:

- ATA;
- AHCI;
- NVMe;
- VirtIO block;
- USB mass storage;
- xHCI HID;
- VirtIO GPU;
- SMP;
- disk installation and UEFI reboot.

This is integration evidence.

It still does not establish physical compatibility.

### Level 3 — physical hardware record

A hardware path reaches Level 3 only when the project records at least:

- machine or motherboard model;
- firmware vendor/version;
- PCI vendor/device/class identifiers;
- controller mode;
- disk/input/device model;
- ChrisOS revision;
- boot configuration;
- serial/boot log;
- expected success marker;
- reboot/repeat result.

Without this record, "works on hardware" remains anecdotal.

## CPU architecture

The primary kernel is x86-64.

Bootinfo requires Limine to provide:

- framebuffer response;
- HHDM response;
- memory-map response;
- multiprocessor response.

The kernel assumes it enters an already established 64-bit environment rather than performing firmware-era CPU mode transitions itself.

The current installed-disk path is therefore best characterized as:

    x86-64 + Limine handoff

rather than a generic "any x86 PC" target.

## Multiprocessor state

ChrisOS contains an SMP path based on the Limine MP response.

The kernel tracks:

    cpu_online_count

and allocates dedicated AP stacks.

Current compile-time limits include:

    SMP_MAX_APS = 8
    SMP_CPU_CAP = 16

The actual launch loop stops when the next AP index reaches SMP_MAX_APS.

Therefore the practical current implementation does not imply arbitrary CPU-count scalability.

## QEMU SMP evidence

The default QEMU gate runs with:

    QEMU_SMP = 4

and requires:

    cpu_online_count=4

This is meaningful SMP evidence inside QEMU.

It does not prove correct AP startup, APIC routing or TLB shootdown behavior on arbitrary physical multiprocessor systems.

## Safe mode

The boot command-line token:

    safe

sets:

- nosmp;
- noapic;
- noac97;
- nonet;
- nojit.

The QEMU safe-mode gate expects:

    safe mode
    smp off
    desktop 60Hz

This mode is important for physical bring-up because it removes several optional/high-variance subsystems while preserving a graphical kernel boot.

A first physical boot should therefore keep safe mode available as a diagnostic fallback.

## Firmware profile

The strongest installed-disk path is UEFI.

The installer writes BOOTX64.EFI into the fallback path and the resulting disk boots under OVMF.

The physical compatibility boundary still includes:

- firmware storage drivers;
- GPT/ESP acceptance;
- fallback-file policy;
- framebuffer availability;
- Secure Boot policy.

No Secure Boot trust chain is currently implemented.

## Limine dependency

Limine is part of the current hardware contract.

The kernel directly consumes Limine revision-3 requests for:

- framebuffer;
- HHDM;
- memory map;
- multiprocessor information;
- executable command line.

The current hardware profile therefore cannot be defined independently of Limine handoff behavior.

## Framebuffer requirement

Framebuffer availability is mandatory in the current normal boot path.

bootinfo_init panics when the framebuffer is missing or not 32 bpp.

kstart also checks:

    boot->fb_bpp != 32

and refuses the framebuffer through gfx_init when the contract is not satisfied.

Therefore a practical current machine needs a firmware/bootloader path that provides a usable 32-bpp framebuffer.

## Native physical GPU support

The mandatory display path is a firmware-provided linear framebuffer.

ChrisOS also contains VirtIO GPU and VirGL support, but these are virtualization-oriented devices and are validated in QEMU-oriented environments.

There is no general native Intel/AMD/NVIDIA physical GPU driver in the reviewed kernel.

Therefore:

    firmware framebuffer = candidate physical baseline
    VirtIO GPU/VirGL     = virtualized acceleration path
    native PC GPU        = not established

## Graphics resolution

The Limine configuration requests:

    1920x1080x32

but firmware may provide another usable mode.

The real contract is not "the machine must have a 1920x1080 monitor."

The stronger requirement is:

- usable Limine framebuffer;
- 32 bpp;
- valid width/height;
- valid pitch;
- memory accessible according to the handoff.

Physical validation should record the actual returned mode.

## PCI configuration mechanism

The current generic PCI access uses legacy configuration mechanism #1:

    0xCF8
    0xCFC

This works on conventional PC-compatible PCI systems where that mechanism is exposed.

It is not equivalent to a complete PCIe ECAM implementation.

Although ACPI probing can notice an MCFG table signature, the reviewed PCI layer does not use MCFG to enumerate PCI Express configuration space.

This limits portability.

## PCI topology limits

Discovery policy is inconsistent by subsystem.

Some older helper functions in kernel/metal/pci.c scan only:

    bus 0
    slots 0..31
    functions 0..7

Several newer storage/GPU drivers scan:

    buses 0..7
    devices 0..31
    functions 0..7

There is no general recursive bridge traversal that discovers arbitrary downstream PCIe buses.

Therefore a supported class can still be invisible when it sits behind an unscanned bridge or bus number.

This is one of the main physical-hardware limitations.

## Hardware discovery application

SYS/DRV/HWDISC.CC provides a simple PCI-view application.

It classifies devices such as:

- IDE/ATA;
- AHCI/SATA;
- NVMe;
- USB;
- display;
- network;
- audio.

It also probes selected BARs for AHCI/NVMe and recognizes several VirtIO IDs.

However, the application scans bus 0 and function 0 per slot.

It is useful as a diagnostic view, not a complete PCI enumeration engine.

## Storage profile

The storage layer probes several classes:

- ATA PIO;
- AHCI;
- NVMe;
- VirtIO block;
- USB mass storage.

This gives ChrisOS a broader implemented storage surface than most other physical-device categories.

Storage is also the most heavily QEMU-gated hardware area.

## ATA PIO

The ATA path targets legacy IDE-compatible PIO behavior.

It is valuable for simple virtual machines and older PC-compatible hardware.

Modern systems may not expose legacy IDE mode at all.

ATA PIO should therefore be considered a compatibility path, not the preferred modern physical target.

## AHCI

AHCI is the strongest candidate SATA path for early physical validation.

The driver searches PCI storage-class devices and has a dedicated QEMU gate requiring:

    ahci disk sectors=
    bdev rw ok ahci

The installation integration test also writes the target through a modeled AHCI controller.

Physical AHCI is still not established until named SATA controllers are recorded.

## NVMe

The NVMe driver is implemented and has a QEMU gate requiring:

    nvme disk sectors=
    bdev rw ok nvme

The current storage model expects 512-byte logical sectors.

The driver rejects incompatible namespace LBA sizing rather than pretending full 4Kn support.

A physical NVMe device using a supported 512-byte LBA format is therefore a plausible target, but still needs explicit controller/device validation.

## Sector-size boundary

The filesystem/storage/install path is centered on:

    512-byte logical sectors

Native 4 KiB logical-sector devices are outside the current validated profile.

A drive's physical sector size may differ internally; what matters to the current software contract is the logical block size presented by the driver.

## Capacity boundary

Common block-device sector counts are currently represented with 32-bit fields.

With 512-byte sectors, this places the practical addressing model near the 2 TiB range.

Large physical drives should not be assumed supported merely because GPT itself can express larger LBAs.

The block layer must evolve before broad >2 TiB claims are safe.

## VirtIO block

VirtIO block is an implemented and QEMU-validated virtualization path.

It is not a normal bare-metal PC storage controller.

Its presence improves virtual-machine coverage and can be useful under hypervisors, but it should not inflate the physical storage compatibility list.

## USB mass storage

ChrisOS contains a USB mass-storage path and a QEMU gate.

This demonstrates the driver/device protocol path against a modeled USB storage environment.

Physical USB compatibility additionally depends on the host controller, hub topology and actual device behavior.

The current result is QEMU evidence, not general USB-stick hardware certification.

## xHCI input

ChrisOS has an xHCI HID probe/poll path.

The QEMU xHCI gate requires:

    xhci hid ready

with USB keyboard and mouse attached to the modeled xHCI controller.

This is useful progress because modern PCs commonly use USB rather than PS/2.

Still, one QEMU xHCI model is far narrower than the xHCI controller diversity present on real chipsets.

## PS/2 input

The PS/2 path directly implements the 8042-style controller sequence and keyboard/mouse device initialization.

When PS/2 initialization fails, ChrisOS logs:

    PS/2 unavailable (keyboard/mouse disabled)

rather than aborting boot.

This makes PS/2 optional to the kernel boot itself.

It is nevertheless a useful fallback on machines or emulators exposing a traditional controller.

## Input profile

The practical current input matrix is:

    PS/2 keyboard/mouse   implemented
    xHCI HID              implemented + QEMU gate
    QEMU USB tablet       virtualized helper path
    arbitrary USB HID     not established
    Bluetooth input       not implemented as a baseline
    touchpad-specific HW  not established

A real machine needs at least one working input path if interactive desktop validation is required.

## Network profile

The reviewed network initialization calls:

    virtio_net_init()

and fails gracefully when it is unavailable.

Thus the implemented network path is VirtIO network.

There is no general native Ethernet-driver set for common physical NICs such as:

- Intel e1000/e1000e/igc;
- Realtek RTL81xx;
- Intel ixgbe;
- Broadcom families;
- Wi-Fi devices.

Therefore networking should be considered **optional and normally unavailable on physical hardware** under the current profile.

The boot flag:

    nonet

explicitly disables network initialization.

## Audio profile

ChrisOS contains:

- PC speaker control;
- AC97 audio support.

The AC97 path discovers PCI multimedia audio class devices with I/O BAR assumptions and is optional at boot.

The command-line flag:

    noac97

disables it.

Most modern PCs use Intel HD Audio or other codecs/controllers rather than AC97.

No general HDA driver is part of the reviewed baseline.

Therefore audio should not be a requirement for physical bring-up.

## Interrupt architecture

The kernel initializes:

- legacy PIC;
- PIT;
- local APIC-related code;
- an IOAPIC layer;
- SMP.

The current code has explicit fallback controls:

    noapic
    nosmp

and safe mode enables both.

This is a signal that interrupt/topology behavior remains a bring-up-sensitive area.

QEMU success should not be generalized to arbitrary motherboard routing.

## PIT timing

kstart requires:

    pit_init(60)

to succeed.

The desktop announces:

    desktop 60Hz

after initialization.

This gives the current system a strong conventional-PC timer assumption.

A future hardware profile may migrate toward HPET/APIC timers, but the current boot remains tightly connected to PIT availability.

## ACPI state

The current ACPI probe is diagnostic rather than a complete ACPI platform layer.

It searches the legacy physical area:

    0xE0000 .. 0x100000

for the RSDP and then recognizes selected XSDT entries including:

- APIC;
- MCFG;
- FACP.

This is not equivalent to using the UEFI configuration-table path or fully parsing AML.

Physical firmware that does not make RSDP discoverable through the current assumptions can therefore appear ACPI-less to ChrisOS even if it is perfectly compliant.

## MCFG gap

The ACPI probe may log MCFG, but PCI enumeration still uses CF8/CFC rather than ECAM.

Thus detecting MCFG does not currently expand PCIe reachability.

A future physical-hardware milestone should connect ACPI MCFG to a real PCIe ECAM enumerator.

## SMP and APIC coupling

SMP startup uses Limine MP information.

The code tracks LAPIC IDs and starts APs through Limine-provided CPU records.

Local APIC behavior and TLB coordination become more important as additional CPUs come online.

If a physical system boots in safe mode but fails with SMP enabled, the evidence should be recorded as:

    BSP-only profile works
    SMP profile fails

rather than "hardware unsupported."

## Memory profile

The kernel consumes the Limine memory map and sums usable regions.

Physical memory is therefore not assumed to be one contiguous range.

The memory map also carries reserved, ACPI and framebuffer categories.

However, successful boot still depends on the rest of the kernel handling the machine's particular layout correctly.

Memory capacity alone is not enough to classify compatibility.

## Required boot services from Limine

The kernel panics if any of these are missing:

- framebuffer;
- HHDM;
- memory map;
- MP response.

This is a stronger contract than a minimal text-only single-CPU boot.

Physical hardware validation must therefore verify all four handoff components.

## Candidate first-machine profile

For a deliberate first real-machine experiment, the lowest-risk candidate is:

    architecture:
        x86-64

    firmware:
        UEFI
        Secure Boot disabled
        CSM not required

    boot:
        Limine BOOTX64.EFI
        fallback path available

    display:
        firmware framebuffer
        32 bpp

    CPU:
        start with safe/nosmp mode if necessary

    storage:
        512-byte logical sectors
        simple AHCI SATA or a tested NVMe controller
        capacity within current block-layer limits

    input:
        PS/2 when available
        otherwise xHCI HID candidate

    network:
        disabled unless VirtIO environment

    audio:
        disabled unless AC97 is intentionally tested

This is a research bring-up target, not a certified minimum specification.

## What is outside the current candidate profile

High-risk or unsupported categories include:

- Secure Boot enforcement;
- 4Kn-only storage;
- >2 TiB assumptions in the current block model;
- PCIe devices hidden behind arbitrary bridge topology;
- systems requiring ECAM-only enumeration;
- native modern Intel/AMD/NVIDIA GPU acceleration;
- common physical Ethernet NICs;
- Wi-Fi;
- Bluetooth;
- Intel HD Audio;
- arbitrary USB hubs/controllers/devices;
- complex ACPI/AML-dependent platform management;
- suspend/resume;
- battery/power-management support;
- IOMMU/device passthrough;
- broad laptop-specific hardware.

A machine containing these components can still boot if those components are nonessential.

They simply cannot be counted as supported devices.

## QEMU compatibility matrix

Current QEMU gates give strong integration coverage for:

| Subsystem | Current evidence |
|---|---|
| ATA root | QEMU gate |
| AHCI | QEMU read/write gate |
| NVMe | QEMU read/write gate |
| VirtIO block | QEMU read/write gate |
| USB mass storage | QEMU read/write gate |
| xHCI HID | QEMU gate |
| VirtIO GPU | QEMU gate |
| VirGL | conditional QEMU/host graphics gate |
| SMP | QEMU 4-vCPU marker |
| safe mode | QEMU gate |
| installed UEFI disk | QEMU + OVMF gate |

This table is intentionally labeled QEMU evidence.

It is not a physical hardware table.

## Why emulation coverage is still valuable

QEMU gates provide:

- deterministic topology;
- known device IDs;
- reproducible failures;
- serial logs;
- CI execution;
- fault localization.

They are the correct prerequisite for hardware testing.

The mistake would be treating them as the final validation tier.

## Physical compatibility matrix schema

A future hardware matrix should contain rows like:

    system:
      manufacturer:
      model:
      board:
      firmware:
      firmware_version:

    cpu:
      model:
      cpu_count_seen:
      smp_enabled:

    pci:
      controller_ids:

    display:
      framebuffer_mode:
      pitch:
      bpp:

    storage:
      controller:
      device:
      logical_sector_size:
      root_mount:

    input:
      ps2:
      xhci:

    audio:
      controller:
      result:

    network:
      controller:
      result:

    result:
      boot:
      reboot:
      install:
      persistence:

    revision:
      ChrisOS commit:

This makes support auditable and regression-testable.

## Required physical success markers

A useful full-system physical boot should capture markers in sequence such as:

- ChrisOS selfhost line;
- build identity;
- bootinfo revision;
- framebuffer dimensions;
- memory-map output;
- CPU count;
- storage detection;
- root device;
- cfs mounted;
- desktop 60Hz.

Optional subsystems can then add their own evidence.

## Serial as the primary bring-up channel

The kernel initializes serial before almost everything else.

If serial initialization fails, kstart disables interrupts and halts.

Therefore the existing architecture strongly depends on early serial diagnostics.

For physical testing, a machine with accessible legacy serial output is much easier to diagnose.

Systems without usable serial need an alternative early logging mechanism before they can be considered convenient bring-up targets.

## Failure classification by profile layer

A failed machine should be classified by the first missing layer:

1. firmware never starts BOOTX64.EFI;
2. Limine starts but kernel entry does not occur;
3. bootinfo contract fails;
4. framebuffer fails;
5. CPU/interrupt/SMP initialization fails;
6. storage discovery fails;
7. root filesystem fails;
8. input fails;
9. desktop fails;
10. optional network/audio/GPU path fails.

This prevents optional peripheral failures from being confused with core platform incompatibility.

## Driver implementation versus hardware support

The project should use language such as:

    "NVMe driver implemented; QEMU gate passes"

instead of:

    "NVMe supported"

until physical controllers are in the hardware matrix.

Likewise:

    "xHCI HID path passes QEMU"

is more precise than:

    "USB keyboards are supported on PCs."

This editorial rule should apply throughout the site.

## Revision-bound support

Hardware compatibility is revision-sensitive.

A future change to:

- PCI enumeration;
- memory management;
- APIC;
- storage DMA;
- interrupt handling;
- bootloader version;

can change whether a machine works.

Every physical record should therefore pin the exact ChrisOS commit.

A compatibility matrix without revision provenance becomes stale quickly.

## Immediate hardware-enablement priorities

The highest-value steps before broad real-hardware claims are:

1. build a real PCI/PCIe enumerator with bridge traversal;
2. consume ACPI MCFG and support ECAM;
3. improve ACPI RSDP/table acquisition through bootloader/UEFI data;
4. establish one physical AHCI machine gate;
5. establish one physical NVMe machine gate;
6. establish one physical xHCI keyboard/mouse gate;
7. formalize a hardware evidence record;
8. make disk probing non-destructive until explicit approval;
9. move the ESP to a physically conservative FAT32 design;
10. add native common Ethernet drivers only after the core boot/storage profile is stable;
11. add HDA only as an optional profile expansion;
12. preserve safe mode as the first-line fallback for APIC/SMP/device issues.

## Current classification

At the reviewed revision:

    x86-64 Limine boot          implemented + QEMU validated
    UEFI installed-disk boot   QEMU/OVMF validated
    32-bpp framebuffer         required + QEMU validated
    SMP                        implemented + QEMU validated
    ATA                        implemented + QEMU validated
    AHCI                       implemented + QEMU validated
    NVMe                       implemented + QEMU validated
    VirtIO block               implemented + QEMU validated
    USB mass storage           implemented + QEMU validated
    PS/2                       implemented
    xHCI HID                   implemented + QEMU validated
    VirtIO GPU                 implemented + QEMU validated
    VirGL                      implemented + conditional QEMU validation
    AC97                       implemented
    VirtIO network             implemented
    general physical NICs      not implemented
    native modern GPU drivers  not implemented
    HDA                        not implemented
    broad ACPI platform        not implemented
    general PCIe topology      not implemented
    physical hardware matrix   not yet established

## Revision note

At revision e05a17fd76333114a3fb5c2452f38ca747d4ac56, ChrisOS has a coherent QEMU-validated x86-64 platform with multiple storage paths, SMP, framebuffer graphics and several virtualized devices. The project is now at the point where physical support should be defined through recorded machine profiles rather than inferred from driver source. The most important physical compatibility constraints are current PCI enumeration limits, firmware/framebuffer assumptions, 512-byte-sector storage expectations, incomplete ACPI/PCIe platform discovery and the absence of native networking/modern GPU/audio drivers.
