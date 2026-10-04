---
id: driver-compatibility
lang: en
type: technical-chapter
volume: 13-real-hardware
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/metal/pci.c
  - kernel/metal/ps2.c
  - kernel/fs/storage.c
  - kernel/fs/bdev.c
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
  - scripts/qemu.mk
  - tools/qemu_gate.py
symbols:
  - pci_read
  - storage_init
  - ata_pio_identify
  - ahci_probe
  - nvme_probe
  - virtio_blk_probe
  - usb_msc_probe
  - xhci_hid_probe
  - ps2_init
  - vgpu_boot
  - ac97_init
  - virtio_net_init
depends_on:
  - hardware-profile
  - bringup-diagnostics
  - validation-evidence
related:
  - installation-real-hardware
  - qemu-gates
  - hardware-gates
  - fault-injection
---

# Driver compatibility: implementation, discovery and evidence

## Scope

Driver compatibility in ChrisOS is not a binary property.

A controller family can be represented in source while a particular physical device remains unusable because discovery, firmware assumptions, DMA addressing, interrupt routing, sector geometry, queue layout, or device-specific behavior falls outside the implementation envelope.

This chapter defines the compatibility contract used by the documentation. It separates four questions:

1. is a software path implemented;
2. can the kernel discover the device;
3. does the implemented path pass a deterministic virtual-machine gate;
4. has the same class been reproduced on identified physical hardware.

Only the fourth question establishes physical compatibility for a recorded machine/controller profile.

## Compatibility state model

For documentation purposes, each device path is described by an evidence tuple:

[
C = (I, D, Q, P)
]

where:

- (I) — implementation exists in the current source revision;
- (D) — discovery path covers the tested topology;
- (Q) — a QEMU gate proves the path with explicit positive markers;
- (P) — a revision-bound physical-hardware record proves the path on a named machine.

The states are intentionally not collapsed into a single word such as "supported".

For example:

[
(1,1,1,0)
]

means that the driver exists, the tested topology is discoverable, and QEMU evidence exists, but physical compatibility has not been established.

## Why implementation is weaker than compatibility

A driver can contain correct protocol logic and still fail on a real system because the device is never discovered.

Likewise, a discovered controller can still fail because:

- the BAR layout differs;
- DMA memory is not addressable by the device;
- an interrupt path is not routed as expected;
- a queue size is smaller than the implementation assumes;
- firmware leaves the controller in an unexpected state;
- a disk uses an unsupported logical sector size;
- the device is behind an untraversed PCIe bridge;
- the device exposes a protocol revision or feature combination not exercised by QEMU.

Therefore source presence is evidence of implementation, not proof of hardware interoperability.

## PCI discovery boundary

ChrisOS uses legacy PCI configuration mechanism #1 through the standard configuration I/O ports.

The generic helpers in `kernel/metal/pci.c` operate on bus, slot and function coordinates and several helper searches scan:

    bus 0
    slots 0..31
    functions 0..7

Several subsystem-specific drivers do their own wider scan.

AHCI, NVMe and VirtIO block currently scan:

    buses 0..7
    devices 0..31
    functions 0..7

The VirtIO-GPU path scans buses 0..7 and devices 0..31, but probes function 0 in that search.

This is not a generic PCIe fabric enumerator.

There is no recursive bridge traversal that discovers every secondary/subordinate bus and no general ECAM/MCFG enumeration layer that makes arbitrary PCIe topology visible.

The practical invariant is:

    device protocol may be implemented
    AND
    device may still be invisible

when it resides outside the scanned topology.

## Discovery complexity

A flat scan over (B) buses, (D) devices and (F) functions has worst-case configuration-read complexity:

[
O(BDF)
]

For the AHCI/NVMe/VirtIO-block search envelope:

[
8 	imes 32 	imes 8 = 2048
]

function coordinates are candidates before class/vendor filtering.

The current approach is simple and deterministic for QEMU and small PC layouts. It scales poorly as a general PCIe discovery strategy because it ignores the graph structure encoded by bridges.

A bridge-aware enumerator should instead traverse discovered bridge edges and validate secondary/subordinate bus ranges.

## Block-device abstraction

Storage drivers register through the common block-device layer.

The abstraction carries:

- sector size;
- sector count;
- read function;
- write function;
- optional flush operation;
- writability;
- device kind and flags.

This allows the filesystem, partition parser and installer to operate without embedding controller-specific protocol logic.

The compatibility consequence is useful: a driver only becomes a viable ChrisOS storage device after both protocol initialization and block-device registration succeed.

## Global storage geometry assumptions

The present storage stack is strongly centered on 512-byte sectors.

The common installation and filesystem path expects:

    sector_size = 512

NVMe explicitly rejects namespaces whose active LBA data size is not (2^9) bytes.

USB mass storage and VirtIO block register 512-byte sectors in their current paths.

The common sector count is 32-bit. Several drivers reject capacity representations that require high 32-bit words.

At 512 bytes per sector, the addressable envelope is approximately:

[
2^{32} 	imes 512 = 2 	ext{TiB}
]

before filesystem/layout constraints are considered.

Consequently, "NVMe driver implemented" does not imply compatibility with 4 KiB-native namespaces or arbitrarily large devices.

## ATA PIO

The ATA path implements legacy programmed-I/O access and the classic ATA register interface.

Compatibility characteristics include:

- legacy ATA I/O-port model;
- polling-oriented command completion;
- 512-byte logical sectors in the current storage contract;
- no claim of broad modern SATA-controller compatibility through this path.

ATA remains useful as a simple baseline and QEMU gate because its control surface is small and failures are comparatively easy to localize.

It should not be used as evidence that arbitrary contemporary storage controllers are supported.

## AHCI

The AHCI path discovers PCI mass-storage controllers matching the AHCI class/subclass/prog-if contract, maps controller MMIO through the hardware-gate layer, examines implemented ports, and attempts to start an attached SATA device.

The probe scans buses 0..7, devices 0..31 and functions 0..7.

Current compatibility is bounded by:

- the finite PCI scan envelope;
- the controller register model exercised by QEMU;
- available DMA buffers;
- implemented command-list/FIS behavior;
- the common 32-bit sector-count envelope;
- SATA devices that present the expected ATA identify behavior.

The QEMU AHCI gate requires explicit serial evidence including:

    ahci disk sectors=
    bdev rw ok ahci

This proves the current software path against the emulated ICH9 AHCI configuration used by the gate.

It does not establish compatibility with a physical AHCI controller.

## NVMe

The NVMe path initializes an NVMe PCI controller, admin queues and an I/O queue, identifies a namespace, and exposes it as a block device.

A namespace is rejected when the active LBA data size is not 512 bytes.

The path also rejects capacities outside its current representation envelope.

Important compatibility boundaries therefore include:

- PCI visibility;
- controller register/doorbell assumptions;
- queue allocation and DMA addressing;
- namespace 1 behavior used by the implementation;
- 512-byte LBA format;
- bounded sector count.

A physical NVMe claim requires recording the PCI vendor/device ID, controller model, namespace geometry, firmware version when available, and the exact ChrisOS revision.

## VirtIO block

VirtIO block is a virtual-device compatibility path, not a physical storage-driver substitute.

The implementation negotiates the VirtIO PCI interface, validates queue capacity, allocates queue state and exposes the virtual disk through the same block-device layer.

It rejects devices when the capacity requires unsupported high bits and currently registers a 512-byte sector geometry.

The strongest current evidence for this path is virtualization evidence.

Its presence is valuable because it exercises the generic storage layer without tying validation to ATA/AHCI/NVMe.

## USB mass storage

The current USB mass-storage implementation is explicitly narrow.

The source identifies it as:

    UHCI host + BOT mass storage

and states that it is not a generic USB stack.

The path uses Bulk-Only Transport and SCSI-style commands to determine capacity and perform block I/O.

Compatibility must therefore not be generalized to:

- xHCI mass storage;
- arbitrary USB host controllers;
- UAS;
- arbitrary USB composite-device layouts.

The driver registers 512-byte blocks and uses the same bounded block-device geometry as the rest of the current stack.

## xHCI HID

The xHCI implementation is also deliberately constrained.

Its source describes a poll-only path for:

- one QEMU xHCI keyboard;
- one boot mouse.

The implementation is meaningful evidence that ChrisOS can construct xHCI rings, reset ports, configure endpoints and translate boot-protocol HID reports into the input subsystem.

It is not a general claim of USB HID compatibility across physical xHCI controllers and device topologies.

A hardware record must identify:

- xHCI PCI ID;
- root port;
- negotiated speed;
- keyboard/mouse device;
- observed ready markers;
- sustained input behavior after desktop start.

## PS/2 input

PS/2 initialization contains bounded waits for controller input/output readiness and treats input as an optional platform path.

A system without usable PS/2 can still be viable if another input path works.

Therefore PS/2 failure should be recorded as a device-class result, not automatically as a whole-machine boot failure.

For early physical bring-up, PS/2 remains attractive because it avoids USB-controller complexity.

## Framebuffer graphics

The fundamental graphics compatibility boundary is the boot framebuffer.

ChrisOS requires a Limine-provided framebuffer and currently requires 32 bits per pixel.

This path depends more on firmware/bootloader handoff than on a native GPU driver.

A machine can therefore display the ChrisOS desktop without ChrisOS containing a native driver for its modern GPU, provided firmware and Limine expose a compatible framebuffer.

This distinction must remain explicit:

    framebuffer display works

is not equivalent to:

    native GPU is supported.

## VirtIO GPU and VirGL

VirtIO GPU is a virtualization-oriented accelerated graphics path.

The implementation negotiates VirtIO features and can request the VirGL feature.

VirGL is used only when the feature is negotiated and valid capsets are available; otherwise the graphics stack can fall back to software rendering.

The source emits evidence such as:

    VIRGL feature: yes/no
    3D backend -> virgl
    3D backend -> software
    VirGL failure

Compatibility should be reported at the backend actually selected, not inferred from device presence.

## Audio

The native audio path currently targets AC97.

AC97 is useful for QEMU and legacy hardware experiments, but it is not representative of the High Definition Audio controllers present in most modern systems.

No documentation should convert the existence of `ac97_init` into a claim of general PC audio support.

A machine can be classified as boot-compatible while audio remains unavailable.

## Networking

The implemented NIC path is VirtIO network.

That establishes a useful virtual-machine network target but does not provide broad bare-metal NIC coverage.

Physical Ethernet controllers from Intel, Realtek, Broadcom and others require their own drivers before physical network compatibility can be claimed.

Networking is therefore currently an optional capability in the physical-hardware profile.

## Evidence provided by QEMU gates

`scripts/qemu.mk` contains dedicated gates for device paths including:

- ATA;
- AHCI;
- NVMe;
- VirtIO block;
- USB;
- VirtIO GPU;
- xHCI;
- installation;
- safe/SMP variants;
- conditional VirGL coverage.

The gate runner requires positive serial markers and rejects fatal markers.

This is stronger than merely observing that QEMU remained alive for a timeout.

A gate establishes:

    implementation + tested virtual topology + expected observable behavior

for the revision under test.

It does not establish physical-hardware compatibility.

## Physical compatibility record

A physical result should minimally capture:

| Field | Required evidence |
|---|---|
| ChrisOS revision | Git commit and kernel build identity |
| Machine | vendor and model |
| Firmware | vendor, version, UEFI/legacy mode |
| Secure Boot | enabled/disabled state |
| CPU | model and logical CPU count |
| PCI device | bus/device/function, vendor/device IDs |
| Controller | model/class under test |
| Media | model, capacity, logical sector size |
| Boot flags | exact command line |
| Discovery | serial markers proving controller/device visibility |
| Operation | class-specific read/write/input/render/network evidence |
| Failure state | last successful marker and fatal context |
| Repetition | number of successful cold/warm repetitions |

A compatibility claim without revision provenance is temporary anecdote, not maintainable evidence.

## Compatibility classes

The documentation uses the following classes:

| Class | Meaning |
|---|---|
| Implemented | source path exists and is reachable |
| QEMU-validated | deterministic virtual gate passes |
| Physically observed | at least one identified machine passed a recorded manual procedure |
| Hardware-gated | repeatable physical automation exists |
| Unsupported | no current implementation or an explicit incompatibility is known |

"Physically observed" is intentionally weaker than "hardware-gated".

The latter requires repeatability and retained artifacts.

## Failure classification

A driver test should report the earliest failed layer:

1. device not visible to PCI/firmware discovery;
2. controller visible but class/vendor rejected;
3. BAR or MMIO setup failed;
4. DMA/queue allocation failed;
5. controller reset/init timed out;
6. device/namespace/port not present;
7. geometry or feature set rejected;
8. block/input/network operation failed;
9. higher-level subsystem failed after driver readiness.

This ordering prevents downstream symptoms from being mistaken for discovery failures.

## Safety boundary for storage compatibility

Storage compatibility testing is potentially destructive.

The current storage initialization can perform write/read/restore tests on writable non-root disks, and blank-device discovery can format a sufficiently empty writable device.

Therefore physical storage tests must use disposable media or a dedicated target until the probing policy becomes read-only by default.

A compatibility matrix must never recommend testing against a disk containing valuable data.

## Revision drift

Compatibility is revision-bound.

Changes to any of the following can invalidate prior results:

- PCI enumeration;
- bootloader/BootInfo handling;
- physical memory allocation;
- DMA translation;
- interrupt/APIC setup;
- driver queue layout;
- filesystem geometry;
- timeout behavior;
- QEMU machine configuration.

The source revision recorded in this chapter is therefore part of the technical contract, not metadata decoration.

## Current matrix at the reviewed revision

At revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, the evidence boundary is:

| Path | Implemented | QEMU evidence | Physical evidence in repository |
|---|---:|---:|---:|
| ATA PIO | yes | yes | not established |
| AHCI | yes | yes | not established |
| NVMe | yes | yes | not established |
| VirtIO block | yes | yes | virtual device |
| UHCI + USB BOT mass storage | yes | yes | not established |
| PS/2 keyboard/mouse | yes | partial/integration | not established |
| xHCI boot HID | yes | yes | not established |
| Limine framebuffer | yes | yes | not established as a matrix |
| VirtIO GPU | yes | yes | virtual device |
| VirGL | yes | conditional | virtual device |
| AC97 | yes | integration path | not established |
| VirtIO network | yes | integration path | virtual device |
| native modern GPU | no | no | no |
| HDA | no | no | no |
| general physical NIC families | no | no | no |

The table describes evidence present in the inspected repository. It must not be read as a promise that every device within an implemented class works.

## Highest-value compatibility work

The next improvements are structural rather than adding more nominal driver names:

1. recursive PCI bridge traversal;
2. ACPI MCFG/ECAM enumeration;
3. stable PCI identity export in boot logs;
4. read-only hardware discovery mode;
5. model/serial/capacity reporting for storage;
6. physical AHCI and NVMe evidence records;
7. physical xHCI evidence records;
8. hardware-gate automation with serial capture and power/reset control;
9. HDA only after core boot/storage/input evidence is stable;
10. physical NIC drivers only with repeatable device-specific gates.

## Revision note

This chapter was reconciled against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

The current source contains substantial driver coverage and explicit QEMU gates, but the repository does not yet contain a general physical-hardware compatibility matrix. Compatibility claims must therefore remain scoped to implemented paths, discovery limits and the exact evidence class available for each device.
