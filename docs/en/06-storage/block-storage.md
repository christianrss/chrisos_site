---
id: block-storage
lang: en
type: technical-chapter
volume: 06-storage
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/fs/block_device.h
  - kernel/fs/storage.c
  - kernel/fs/ata_pio.c
  - kernel/fs/ahci.c
  - kernel/fs/nvme.c
  - kernel/fs/virtio_blk.c
symbols: []
depends_on:
  - buses-mmio-dma
related:
  - chrisfs
---

# Block storage stack

## Sector-oriented devices

Persistent storage devices expose addressable blocks rather than arbitrary C objects. A block layer converts device-specific protocols into a common contract such as read sectors, write sectors, flush and report capacity.

The filesystem above should not need to know whether a request reaches ATA, AHCI, NVMe or VirtIO Block.

```text
ChrisFS / installer
       │
       ▼
  BlockDevice
   /  |  |  \
 ATA AHCI NVMe VirtIO
       │
       ▼
 physical or virtual controller
```

## Logical block addressing

Modern software addresses storage by logical block number. A request identifies an LBA and count. Controllers translate that abstraction to their internal media.

ChrisOS currently uses a 512-byte sector contract in the storage layer. A driver must not silently reinterpret the unit, because filesystem offsets and GPT calculations depend on exact block geometry.

## ATA and AHCI

ATA PIO is conceptually simple: software communicates through I/O registers and transfers data under CPU control. DMA-capable ATA paths introduce memory descriptors and completion status.

AHCI standardizes SATA host-controller operation around memory-resident command structures, ports and DMA.

Although both may ultimately speak to SATA disks, the driver programming models are different. The block abstraction prevents those protocol details from leaking into ChrisFS.

## NVMe

NVMe is designed for non-volatile storage attached through PCIe. Its model uses submission and completion queues in memory. Commands identify namespaces and logical blocks; the controller performs DMA and posts completion entries.

The queue model makes ownership and memory ordering explicit. Descriptors cannot be recycled until completion proves the controller no longer consumes them.

## VirtIO Block

VirtIO Block is a paravirtual storage device. The guest builds descriptor chains in virtqueues, not physical SATA/NVMe command structures.

The device is ideal for VM testing but is not evidence that a physical NVMe or AHCI driver works. Documentation therefore classifies QEMU and physical-hardware evidence separately.

## Timeouts and failure

A driver that waits forever for completion can hang the kernel. The ChrisOS block paths distinguish timeout from general I/O errors in several current drivers.

Timeout handling must still preserve ownership. If a controller could continue DMA after software declares timeout, reusing the backing buffer too soon would be unsafe. Real driver design often requires reset/cancel sequencing before memory is released.

## Discovery and root selection

`storage.c` discovers block devices and chooses a usable filesystem source according to current project policy. Presence of a driver source file does not mean every controller revision, PCI topology or physical device is supported.

## Installation

The installer operates above block devices. It writes GPT structures, an EFI system partition and ChrisFS content. That means a failure can occur at several layers:

```text
installer policy
  ↓
partition geometry
  ↓
filesystem format/copy
  ↓
BlockDevice
  ↓
controller protocol
  ↓
DMA / interrupts
```

Debugging storage requires identifying which layer violated its contract rather than treating every failure as "disk I/O."
