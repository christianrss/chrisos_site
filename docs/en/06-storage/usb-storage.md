---
id: usb-storage
lang: en
type: technical-chapter
volume: 06-storage
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/fs/usb.h
  - kernel/fs/usb_msc.h
  - kernel/fs/usb_msc.c
  - kernel/fs/xhci.h
  - kernel/fs/xhci.c
  - kernel/fs/block_device.h
  - kernel/fs/bdev.h
  - kernel/fs/bdev.c
  - kernel/fs/storage.c
  - kernel/gfx/hwgate.h
  - kernel/gfx/hwgate.c
  - kernel/metal/pci.c
  - scripts/qemu.mk
symbols:
  - UsbMsc
  - UsbHid
  - usb_msc_probe
  - port_reset
  - control
  - bulk
  - scsi
  - usb_rw
  - usb_read
  - usb_write
  - run_qh
  - td_write
  - td_wait
  - xhci_hid_probe
  - hw_dma_alloc_low
  - bd_add_kind
depends_on:
  - block-storage
  - buses-mmio-dma
  - pci-pcie
  - physical-memory
related:
  - virtio-block
  - partitions-gpt
  - chrisfs
  - interrupts-smp
---

# USB mass storage and host controllers

## Scope

ChrisOS does not yet contain a generic USB subsystem. Its storage path is a deliberately narrow implementation built around **UHCI + USB Mass Storage Bulk-Only Transport (BOT) + SCSI block commands**. A separate xHCI implementation exists, but it is currently dedicated to poll-driven boot HID devices and does not provide Mass Storage support.

That distinction is fundamental. The current storage stack is not:

~~~text
generic USB core
    -> arbitrary host controller
    -> arbitrary class driver
~~~

It is closer to:

~~~text
UHCI-specific enumeration and scheduling
    -> one USB device with bulk IN/OUT endpoints
    -> BOT wrapper
    -> SCSI READ(10) / WRITE(10)
    -> BlockDevice
~~~

The source itself states this boundary in `usb.h`: the only storage backend is UHCI, the only storage class path is MSC/BOT, EHCI is future work, and xHCI is a separate HID-only path.

This chapter documents ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

![ChrisOS USB storage path from UHCI to BOT/SCSI and BlockDevice](../../assets/diagrams/usb-storage-path-en.svg)

## Position in the storage stack

The USB disk path is integrated through the generic block layer:

~~~text
ChrisFS / GPT / storage discovery
        -> BlockDevice
        -> usb_read / usb_write
        -> usb_rw
        -> SCSI READ(10) / WRITE(10)
        -> USB BOT
        -> bulk OUT / bulk IN
        -> UHCI transfer descriptors
        -> USB mass-storage device
~~~

`storage_init` probes USB Mass Storage after ATA, AHCI, NVMe and VirtIO Block.

A successful probe registers:

~~~text
name = "usb"
kind = BD_USB
sector_size = 512
writable = 1
flush = 0
~~~

Root selection remains a separate generic-storage decision.

## Host-controller reality: UHCI for storage, xHCI for HID

ChrisOS currently has two distinct USB-related paths.

### UHCI storage path

`usb_msc.c` scans for PCI class code:

~~~text
0x0C0300
~~~

which means USB controller with UHCI programming interface.

Storage, USB control transfers, BOT, SCSI and an incidental USB tablet/HID path live in this file.

### xHCI HID path

`xhci.c` scans PCI class code:

~~~text
0x0C0330
~~~

and implements a separate xHCI path for a boot keyboard and mouse.

It has command rings, event rings, endpoint configuration and transfer TRBs, but it does **not** implement USB Mass Storage. No MSC/BOT path is attached to xHCI.

Therefore “USB storage support” in current ChrisOS means “USB storage on UHCI,” not “USB storage through all supported USB host controllers.”

## UHCI PCI discovery

The storage probe scans PCI buses 0 through 7, devices 0 through 31 and functions 0 through 7.

For a UHCI-class function, the driver reads PCI BAR4 at offset `0x20`.

It requires an I/O-space BAR:

~~~text
bar & 1 != 0
~~~

The UHCI I/O base is:

~~~text
bar & ~3
~~~

The PCI command register is updated with `| 5`, enabling:

- I/O-space decoding;
- bus mastering.

The storage path is therefore tied to the traditional UHCI port-I/O register model, not MMIO.

## Why low DMA memory is required

UHCI schedule pointers and transfer descriptors use 32-bit physical addresses.

ChrisOS therefore allocates:

~~~text
hw_dma_alloc_low(4)
~~~

This reserves four contiguous pages, or 16 KiB, from the DMA32 allocator.

Unlike NVMe or VirtIO Block, which can write high and low physical-address halves, this UHCI path depends on memory being addressable below the 4-GiB boundary.

This is one of the clearest examples in ChrisOS of a hardware DMA-width constraint propagating into physical-memory allocation policy.

## Shared 16-KiB DMA arena

The UHCI storage implementation lays multiple structures into one four-page DMA allocation.

The important regions are:

| Offset | Use |
|---:|---|
| 0x0000 | 1024-entry UHCI frame list |
| 0x1000 | queue head and transfer descriptors |
| 0x2000 | control SETUP packet and control payload |
| 0x3000 | bulk-transfer payload buffer |
| ~0x3400 | incidental UHCI HID report buffer |

The frame list occupies the first 4096 bytes exactly:

~~~text
1024 entries × 4 bytes = 4096 bytes
~~~

Every frame-list entry initially points to the queue head at page offset 4096 with the queue-head link type encoded.

This fixed layout avoids dynamic schedule allocation, but it also makes the driver single-owner and tightly couples storage, enumeration and UHCI HID polling to the same DMA arena.

## UHCI halt and reset

Before reprogramming the schedule, the driver can halt the controller by clearing the Run/Stop bit and polling status.

`uhci_reset` then performs a host-controller reset and waits for the reset bit to clear.

The waits are finite.

The driver also writes ones to USBSTS through `uhci_ack` to clear pending status bits and avoid leaving IRQ 11 asserted.

The implementation nevertheless remains polling-oriented; it does not use IRQ 11 as its normal completion mechanism.

## UHCI transfer descriptors

`td_write` builds one UHCI transfer descriptor with:

- link pointer;
- active/status field;
- USB token;
- data-buffer address.

When a TD links to another TD, ChrisOS sets the depth-first bit in the link pointer.

A source comment records why: without depth-first traversal, the host controller completed the SETUP TD and returned to the queue head before the status stage, preventing the full control transfer from finishing.

This is an implementation-level scheduling detail that matters because ChrisOS builds very small ad-hoc TD chains rather than a general asynchronous schedule.

## USB token construction

The `token` helper assembles:

- PID;
- device address;
- endpoint number;
- data-toggle bit;
- encoded maximum length.

ChrisOS uses the standard USB PIDs visible in the source:

~~~text
0x2D  SETUP
0x69  IN
0xE1  OUT
~~~

The maximum-length field uses the UHCI convention where zero-length transfers are encoded with `0x7FF`, otherwise `len - 1`.

## Waiting for TD completion

`td_wait` polls the TD active bit.

A completed TD with bits in the error mask returns failure. If activity remains pending too long, the function returns timeout.

The timeout logic counts UHCI frame-number changes and also uses a guard counter.

A particularly environment-specific detail appears here: periodically reading port `0x80` forces a VM exit under KVM/QEMU long enough for the emulated UHCI frame timer to advance. The source explicitly notes that a `pause`-only loop could stall forever in that environment.

This is a useful validation workaround, but it is not a generic USB synchronization primitive.

## Queue-head execution model

`run_qh` operates synchronously:

1. halt UHCI;
2. initialize the queue head;
3. clear UHCI status;
4. program the frame-list base;
5. start the controller;
6. wait for the first TD.

Every control or bulk transaction therefore reuses the same queue-head/TD region.

This design is simple to reason about but prevents concurrent USB requests.

## Control transfers

`control` builds the standard three-stage USB control transfer:

~~~text
SETUP
optional DATA
STATUS
~~~

The setup packet is stored around offset 8192.

For requests with a data stage, the implementation uses a single data TD.

That is an important compatibility limitation: the code does not segment control payloads according to endpoint-zero maximum packet size. Configuration descriptors can be requested up to 128 bytes, but the implementation does not first fetch and honor `bMaxPacketSize0` from the device descriptor.

QEMU tolerates the tested sequence. Broader hardware compatibility should not be inferred from that result.

## Port reset and device addressing

The probe examines two UHCI root ports.

For each connected port, it:

1. waits for connection;
2. asserts port reset;
3. clears reset and enables the port;
4. sends `SET_ADDRESS` while the device is at address 0;
5. assigns sequential addresses beginning at 1.

The implementation is intentionally limited to two root ports and has no hub enumeration.

USB devices behind external hubs are therefore outside the current path.

## Configuration-descriptor discovery

After setting the address, ChrisOS requests the first nine bytes of the configuration descriptor.

It reads `wTotalLength`, caps it at 128 bytes, then requests up to that amount.

The descriptor parser walks interface and endpoint descriptors.

It records:

- the most recently seen interface class;
- interface number;
- bulk IN endpoint number;
- bulk OUT endpoint number;
- first interrupt IN endpoint.

This parser is compact and supports the tested storage/tablet arrangement, but it does not construct a general hierarchy of configurations, interfaces and alternate settings.

## A significant class-matching limitation

The current storage path decides that a device is a Mass Storage candidate when it has:

~~~text
bulk IN endpoint
and
bulk OUT endpoint
and
no USB disk has been registered yet
~~~

It does **not** require the interface descriptor to identify:

~~~text
bInterfaceClass    = 0x08  Mass Storage
bInterfaceSubClass = 0x06  SCSI transparent
bInterfaceProtocol = 0x50  Bulk-Only Transport
~~~

In fact, only `bInterfaceClass` is recorded at all, and that field is used for the incidental HID path, not to gate MSC binding.

Therefore an unrelated USB interface with bulk IN/OUT endpoints can be misidentified as storage and probed with SCSI/BOT commands.

The dedicated QEMU storage device behaves as expected, but the matcher is too broad for general hardware.

## Endpoint properties are not fully consumed

Endpoint descriptors contain more than endpoint number and transfer type.

The current MSC path does not retain or validate the endpoint maximum packet size.

`bulk` instead hardcodes a transfer chunk of at most:

~~~text
64 bytes
~~~

This matches full-speed bulk maximum packet size and the validated UHCI/QEMU environment, but it is not a generic endpoint-driven implementation.

The code also does not model short packets as a first-class completion result.

## SET_CONFIGURATION

Once bulk endpoints have been found, the driver sends:

~~~text
SET_CONFIGURATION
~~~

using the configuration value from the descriptor, defaulting to 1 if zero.

The bulk IN and OUT data toggles are then initialized to DATA0.

No interface alternate-setting selection is implemented.

## Bulk transfer engine

`bulk` divides every BOT phase into chunks of at most 64 bytes.

For each packet it:

1. copies OUT data into the shared DMA bulk buffer when needed;
2. constructs one TD;
3. executes the queue head synchronously;
4. toggles the endpoint data toggle;
5. copies IN data back to the caller when needed.

The entire mechanism is serial.

For a 4096-byte block payload:

~~~text
4096 / 64 = 64 USB bulk packets
~~~

plus BOT command and status phases.

That makes this implementation educationally transparent but comparatively expensive in CPU and controller restarts.

## Bulk-Only Transport

The `scsi` helper implements the three BOT phases:

~~~text
Command Block Wrapper (CBW)
optional data phase
Command Status Wrapper (CSW)
~~~

The CBW is 31 bytes and begins with the correct `USBC` signature bytes.

The driver uses a fixed command tag of 1.

The data direction byte is set to IN or OUT, LUN remains zero, and the SCSI command descriptor block is copied into the CBW.

### BOT validation gaps

The CSW is 13 bytes, but ChrisOS validates only:

~~~text
csw[12] == 0
~~~

It does not verify:

- CSW signature;
- matching command tag;
- data residue;
- phase-error status in a structured way.

There is also no BOT reset-recovery sequence, no `CLEAR_FEATURE(ENDPOINT_HALT)` recovery and no explicit stall handling.

A nonzero CSW status becomes generic I/O failure.

## SCSI command set used

The implemented storage path uses a very small subset of SCSI.

### READ CAPACITY(10)

During probe:

~~~text
opcode = 0x25
~~~

The driver receives eight bytes.

It interprets only the first four bytes as the last logical block address and computes:

~~~text
sector_count = last_lba + 1
~~~

### READ(10)

Normal reads use:

~~~text
opcode = 0x28
~~~

### WRITE(10)

Normal writes use:

~~~text
opcode = 0x2A
~~~

No `INQUIRY`, `TEST UNIT READY`, `REQUEST SENSE`, `MODE SENSE`, `SYNCHRONIZE CACHE` or capacity-16 path is implemented.

## Block-size assumption

READ CAPACITY(10) also returns the logical block length in bytes 4 through 7.

ChrisOS currently ignores those four bytes and unconditionally registers:

~~~text
sector_size = 512
~~~

This is a major current assumption.

A device with a logical block size other than 512 bytes would be represented incorrectly by the block layer.

The current generic `BlockDevice` contract itself also requires 512-byte sectors.

## Capacity limit

READ CAPACITY(10) exposes a 32-bit last-LBA field.

The common ChrisOS block interface also uses 32-bit LBAs and sector counts.

If READ CAPACITY(10) returns `0xFFFFFFFF`, standards-compliant software should normally switch to READ CAPACITY(16). ChrisOS does not do that.

The current increment would wrap to zero, after which the device is rejected by the minimum-size check.

The practical exposed storage model therefore remains below the 32-bit/512-byte boundary, approximately 2 TiB.

## Read and write chunking

`usb_rw` limits one SCSI READ(10) or WRITE(10) to:

~~~text
8 sectors
~~~

At 512 bytes each:

~~~text
8 × 512 = 4096 bytes
~~~

This matches the one-page maximum payload used by the storage abstraction and keeps BOT transfer length within the current code's simple bounds.

Larger caller requests are split sequentially.

The SCSI transfer-length field is written as a 16-bit big-endian sector count.

## CPU-copy behavior

The USB path is not zero-copy.

Each 64-byte OUT packet is packed from caller memory into the shared DMA buffer.

Each IN packet is copied back from that buffer to caller memory.

For disk I/O, the CPU therefore performs repeated packet-sized copies in addition to UHCI schedule programming.

## Concurrency model

The implementation uses global objects:

~~~text
g_usb
g_hid
g_ready
~~~

and one shared DMA arena.

There is no storage-driver lock.

Concurrent disk requests would race on:

- shared TDs;
- queue head;
- bulk buffer;
- endpoint toggles;
- controller run/halt state.

The practical invariant is one active UHCI transfer sequence at a time.

The incidental UHCI tablet polling path shares the same controller and DMA arena, which reinforces the need for serialized ownership.

## Timeout and recovery

A stalled TD can produce `-2`, which is mapped by `usb_rw` to:

~~~text
BD_ETIMEOUT
~~~

Other BOT/SCSI failures become:

~~~text
BD_EIO
~~~

The driver has some controller-level cleanup during unsuccessful probing: after a candidate controller fails to retain a useful device, it resets UHCI and frees the DMA allocation.

However, request-time timeout recovery is limited. There is no complete class-level recovery sequence that:

- resets BOT;
- clears halted bulk endpoints;
- resynchronizes data toggles;
- reissues sense commands;
- proves the device/controller no longer owns the in-flight transfer.

A timeout can therefore leave protocol state less well defined than the happy path.

## Probe cleanup behavior

The USB path is stronger than several other early storage drivers in one respect: if a UHCI controller does not ultimately produce a retained storage/HID device, the code resets the controller, frees the DMA arena and clears global controller state.

There are still narrow lifetime concerns once `keep` becomes true, because shared state is intentionally retained for future I/O.

There is no hot-unplug teardown after successful registration.

## Write persistence

The USB `BlockDevice` is registered with:

~~~text
flush = 0
~~~

The driver does not issue SCSI `SYNCHRONIZE CACHE`.

The generic block layer treats a missing flush callback as success.

Therefore write completion currently means that the BOT/SCSI write command completed successfully from the driver's perspective; it is not an explicit stable-media durability boundary.

## Writable flag

The device is always registered with:

~~~text
writable = 1
~~~

There is no media write-protect discovery or SCSI mode-page check.

Read-only media can therefore be presented as writable until a write command fails.

## HID sharing in the UHCI file

`usb_msc.c` also contains a small UHCI HID path used for an absolute tablet.

It detects interface class 3 and an interrupt IN endpoint, sets configuration, sends a class request, and polls short interrupt reports.

This code is useful for the QEMU USB tablet scenario but should not be interpreted as a general USB HID stack.

It also means the file name `usb_msc.c` understates how much UHCI-specific controller functionality lives there.

## xHCI architecture boundary

The separate xHCI implementation is structurally more modern.

It allocates a larger DMA arena and manages:

- command ring;
- event ring;
- Event Ring Segment Table;
- Device Context Base Address Array;
- endpoint-zero rings;
- interrupt endpoint rings;
- slot/address/configure commands;
- transfer events.

The path scans xHCI PCI class `0x0C0330`.

Despite that richer controller implementation, its public API is explicitly HID-oriented:

~~~text
xhci_hid_probe
xhci_hid_ready
xhci_hid_poll
~~~

It claims boot keyboard and mouse devices and does not expose bulk storage endpoints to the block stack.

Therefore the next architectural step is not “switch USB storage to the existing xHCI backend” without further work; a reusable host-controller/class boundary would first be needed.

## Security and trust boundaries

The UHCI controller bus-masters into a kernel-owned low-memory DMA arena.

There is no IOMMU domain limiting the controller to the schedule and data pages.

Relevant safeguards include:

- DMA32 allocation dedicated to the controller;
- fixed-size 16-KiB arena;
- bounded descriptor buffer offsets;
- finite transfer waits;
- block-layer LBA range checks;
- fixed maximum storage chunk size.

Missing hardening includes IOMMU isolation, descriptor ownership tracking across concurrency, complete malformed-descriptor parsing defenses, hot-unplug handling and robust post-timeout recovery.

## Performance characteristics

The current path prioritizes simplicity over throughput.

Major costs include:

- UHCI rather than EHCI/xHCI storage;
- controller halt/restart around small transactions;
- 64-byte bulk packets;
- synchronous TD polling;
- CPU copies for every packet;
- one request at a time;
- eight-sector SCSI request cap;
- no command pipelining;
- no asynchronous completion;
- no scatter/gather.

The implementation is therefore suitable as a transparent systems-learning path and functional QEMU storage backend, not as a high-performance USB storage stack.

## Validation evidence

`scripts/qemu.mk` defines `test-qemu-usb`.

The gate creates a 32-MiB disk image and attaches:

~~~text
-device usb-storage,bus=usb-bus.0,port=1,drive=usbdisk
~~~

It also attaches a USB tablet on port 2.

The required log evidence is:

~~~text
usb msc sectors=
bdev rw ok usb
~~~

The generic `bdev_rw_tests` routine tests the last sector of the writable non-root USB device by:

1. reading the original sector;
2. writing a deterministic pattern;
3. reading it back;
4. comparing all 512 bytes;
5. restoring the original contents.

The test therefore exercises the full implemented storage chain under QEMU:

~~~text
UHCI PCI discovery
-> port reset/addressing
-> configuration descriptor
-> bulk endpoint discovery
-> SET_CONFIGURATION
-> READ CAPACITY(10)
-> BOT CBW/data/CSW
-> WRITE(10)
-> READ(10)
-> block-layer verification
~~~

A separate `test-qemu-xhci` gate validates xHCI HID with `qemu-xhci`, USB keyboard and USB mouse. It is evidence for the HID controller path, not USB Mass Storage over xHCI.

## Current limitations

At the documented revision, USB storage is limited to:

- UHCI only;
- two root ports;
- no hub enumeration;
- no EHCI storage;
- no xHCI storage;
- no generic host-controller abstraction;
- no generic USB device model;
- one registered storage device;
- LUN 0 only;
- broad bulk-endpoint matching instead of strict MSC class/subclass/protocol matching;
- fixed 64-byte bulk chunks without endpoint-MPS-driven sizing;
- single-TD control data stage rather than endpoint-zero packet segmentation;
- configuration descriptors capped at 128 bytes;
- BOT tag fixed at 1;
- CSW validation limited to status byte;
- no BOT reset recovery;
- no endpoint-halt recovery;
- no `REQUEST SENSE`;
- no `TEST UNIT READY`;
- no `INQUIRY`;
- no `SYNCHRONIZE CACHE`;
- no READ CAPACITY(16);
- READ CAPACITY block-length field ignored;
- 512-byte logical-block assumption;
- 32-bit LBA/capacity model;
- maximum eight sectors per SCSI read/write command;
- polling completion;
- no driver-level request locking;
- no hotplug lifecycle after registration;
- validation centered on QEMU.

## Roadmap boundary

A fuller design should separate a generic USB device/class layer from host-controller implementations, add strict interface matching, consume endpoint maximum-packet sizes, support proper control-transfer packetization, BOT reset recovery, CSW signature/tag/residue validation, sense handling, READ CAPACITY(16), block-size validation, `SYNCHRONIZE CACHE`, hotplug and disconnect handling, and a storage-capable xHCI backend.

EHCI or xHCI storage should be added behind a reusable USB transfer API rather than by duplicating BOT/SCSI logic inside each controller driver.

Those features remain future work until implemented and covered by reproducible tests.

## Source map and revision note

`kernel/fs/usb_msc.c` currently combines UHCI host-controller scheduling, USB enumeration, a small tablet/HID path, BOT, SCSI and block adaptation. `kernel/fs/usb.h` explicitly documents the non-generic architecture and the separation between UHCI MSC and xHCI HID. `kernel/fs/xhci.c` provides the independent xHCI HID path. `kernel/gfx/hwgate.c` supplies DMA32 allocation. `kernel/fs/block_device.h`, `kernel/fs/bdev.h` and `kernel/fs/bdev.c` define and register the generic block device. `kernel/fs/storage.c` integrates USB into storage discovery and validation. `scripts/qemu.mk` contains the dedicated USB storage and xHCI HID gates.

All current-behavior claims in this chapter were reconciled against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.
