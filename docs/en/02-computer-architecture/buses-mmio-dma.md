---
id: buses-mmio-dma
lang: en
type: technical-chapter
volume: 02-computer-architecture
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/pci.c
  - kernel/metal/port.c
  - kernel/gfx/hwgate.c
  - chrisvm/machine/machine.c
symbols: []
depends_on:
  - cpu-datapath-isa
related:
  - block-storage
  - virtio-gpu-virgl
  - chrisvm-chriscpu
---

# Buses, port I/O, MMIO and DMA

## Why devices require an addressing model

A CPU must communicate with controllers that are not ordinary RAM: storage, network interfaces, timers, interrupt controllers and GPUs. Architectures expose these devices through defined address spaces and bus protocols.

The software contract is usually register-oriented. A driver writes configuration or command fields and reads status. The electrical transport may be PCI Express or another physical interconnect, but kernel code generally sees enumerated devices and addressable register windows.

## Port-mapped I/O

x86 retains a separate I/O-port address space accessed by instructions such as `IN` and `OUT`. ChrisOS `kernel/metal/port.c` is the low-level boundary for such operations.

Port I/O is distinct from ordinary memory. A numeric port such as the classic serial range around 0x3F8 is not a RAM pointer.

ChrisVM therefore models an I/O bus separately. ChrisCPU executing an I/O instruction dispatches the operation to a registered device rather than dereferencing guest RAM.

## Memory-mapped I/O

MMIO maps device registers into the processor's physical address space. A load or store targets an address range owned by a device rather than DRAM.

This requires several disciplines:

- the kernel must discover or assign the correct physical range;
- page tables must map it with appropriate attributes;
- compiler optimizations must not remove semantically required volatile accesses;
- ordering rules may require barriers;
- normal RAM caching behavior may be invalid for device registers.

A pointer type alone does not capture these requirements.

## PCI discovery

PCI/PCIe standardizes device identification, configuration space and resources. A kernel enumerates devices, checks vendor/device/class information, and discovers Base Address Registers (BARs) describing port or MMIO windows.

A driver should not hard-code a random MMIO address merely because one QEMU configuration placed a device there. Enumeration separates device identity from a particular host layout.

## DMA

Programmed I/O makes the CPU explicitly move each value through device operations. Direct Memory Access allows a device to read or write system memory after software supplies descriptors or buffer addresses.

```text
CPU
 │ allocate buffer
 │ program physical address
 ▼
device controller
 │
 ├──────── DMA read/write ────────┐
 │                                ▼
 │                           system memory
 │
 └── interrupt/completion ──> CPU
```

DMA changes the ownership problem. The buffer must remain alive and physically suitable while the device can access it. Freeing or repurposing memory too early creates corruption even if the C pointer itself is no longer used.

## Address-width constraints

Not all devices can address all physical memory. The ChrisOS PMM exposes a DMA32-oriented allocation path for devices with below-4-GiB requirements. This distinction became materially relevant to USB/UHCI-related work: a device that cannot issue 64-bit DMA addresses cannot safely receive an arbitrary high physical page.

## VirtIO

VirtIO defines paravirtual devices optimized for virtual machines. Instead of emulating every quirk of physical legacy hardware, guest and host exchange structured descriptors through virtqueues and device-specific protocols.

VirtIO does not eliminate DMA-like ownership. Guest memory referenced by descriptors must remain valid until the host/device side completes the operation.

## Emulator perspective

ChrisVM cleanly separates RAM from I/O and MMIO buses. The CPU executor should not contain hard-coded knowledge of every device. It performs an architectural access; machine/bus logic resolves the target and invokes the registered device.

This is the same separation desirable in a kernel driver stack: processor mechanism, bus enumeration, device transport and subsystem policy remain distinct layers.
