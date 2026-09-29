---
id: ahci
lang: en
type: technical-chapter
volume: 06-storage
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/fs/ahci.c
  - kernel/fs/ahci.h
  - kernel/fs/block_device.h
  - kernel/fs/bdev.c
  - kernel/gfx/hwgate.c
  - kernel/gfx/hwgate.h
  - kernel/metal/pci.c
  - kernel/metal/mm.c
  - kernel/metal/pmm.c
symbols:
  - ahci_probe
  - start_port
  - issue
  - ahci_rw
  - ahci_read
  - ahci_write
  - hw_bar_map
  - hw_dma_alloc
  - hw_mmio_r32
  - hw_mmio_w32
depends_on:
  - block-storage
  - pci-pcie
  - buses-mmio-dma
  - physical-memory
related:
  - ata
  - nvme
  - partitions-gpt
---

# AHCI and SATA DMA

## Scope

AHCI is the memory-mapped host-controller interface commonly used to drive SATA devices. Unlike legacy ATA PIO, the CPU does not move every data word through a task-file data port. Software builds command structures in DMA-visible memory, points an AHCI port at those structures, sets a command-issue bit, and waits for the controller to complete the transfer.

The current ChrisOS AHCI driver implements a deliberately small subset:

- PCI discovery by AHCI class code;
- BAR5 MMIO mapping;
- one active SATA port/device;
- one command slot;
- one PRDT entry;
- one 4 KiB data DMA buffer;
- IDENTIFY DEVICE;
- READ DMA EXT and WRITE DMA EXT;
- synchronous polling for completion;
- 512-byte BlockDevice sectors.

![Current ChrisOS AHCI path from PCI discovery through DMA command structures to BlockDevice](../../assets/diagrams/ahci-command-path-en.svg)

The implementation does not yet provide NCQ, interrupt-driven I/O, hotplug, multi-port registration, ATAPI, command recovery after timeout or an explicit cache-flush command.

## PCI discovery

ahci_probe scans:

~~~text
bus      0..7
device   0..31
function 0..7
~~~

It reads PCI vendor/device information and skips absent functions.

The class/subclass test requires:

~~~text
class/subclass = 0x0106
~~~

which identifies a SATA controller operating through AHCI.

When a controller matches, the code enables PCI memory space and bus mastering by ORing 6 into the PCI command register.

Both are required:

- memory space allows access to the AHCI BAR;
- bus mastering allows the controller to perform DMA.

## BAR5 and MMIO

The AHCI ABAR is taken from PCI BAR5.

ChrisOS maps that physical BAR through hw_bar_map.

hw_bar_map:

- reads the BAR;
- supports 64-bit memory BARs;
- probes BAR size;
- maps the region through the kernel MMIO mapper;
- records it in a bounded hardware-window table.

The hardware gate maps at least 64 KiB and caps a BAR window at 64 pages, or 256 KiB.

AHCI register accesses then use hw_mmio_r32 and hw_mmio_w32 with offsets relative to the mapped window.

The driver does not dereference the physical BAR directly.

## Enabling AHCI mode

After mapping BAR5, ahci_probe sets bit 31 in the global host-control register at offset 0x04.

That is the AHCI Enable bit in GHC.

The driver then reads the Ports Implemented register at offset 0x0c.

Only ports with their corresponding PI bit set are examined.

This prevents probing register blocks that the controller says are not implemented.

## Port register layout

For port number p, ChrisOS computes:

~~~text
port_base = 0x100 + p * 0x80
~~~

This matches the AHCI per-port register spacing.

The driver uses offsets including:

~~~text
+0x00 CLB
+0x04 CLBU
+0x08 FB
+0x0c FBU
+0x10 PxIS
+0x18 PxCMD
+0x20 PxTFD
+0x28 PxSSTS
+0x30 PxSERR
+0x38 PxCI
~~~

Only a subset of the AHCI port model is currently required.

## Device-present check

PxSSTS is read for each implemented port.

The driver requires:

~~~text
PxSSTS.DET == 3
~~~

which indicates a device is present and communication is established.

The current code does not additionally classify the device through PxSIG before issuing IDENTIFY DEVICE.

Therefore the supported path is effectively SATA ATA devices that respond to command 0xec.

ATAPI devices are not implemented as a separate protocol path.

## Static one-port state

The driver owns one global AhciPort and one g_ready flag.

Once a usable disk is successfully registered, ahci_probe returns.

Later calls return success without scanning for additional devices.

The current architecture therefore exposes at most one AHCI-backed BlockDevice.

Even if the controller implements multiple ports, the driver does not register all of them.

## DMA allocations

For a candidate port, the driver allocates two one-page DMA regions through hw_dma_alloc:

- ctl: controller metadata and command structures;
- data: transfer data.

Each allocation is 4 KiB.

hw_dma_alloc obtains physically contiguous PMM memory, maps it through HHDM and stores the physical and virtual addresses in the hardware-DMA registry.

AHCI uses both the low and high 32-bit halves of physical addresses, so unlike the legacy IDE bus-master path it is not intentionally limited to below-4-GiB buffers.

## Layout of the control page

The current implementation packs several AHCI structures into one 4 KiB control page.

Conceptually:

~~~text
offset 0x000: command list
offset 0x400: received-FIS area
offset 0x500: command table used by slot 0
offset 0x580: PRDT entry inside the command table
~~~

The command-list region occupies the first 1024 bytes, matching 32 possible 32-byte command headers.

The driver, however, only issues slot zero.

The received-FIS area begins at 0x400.

The command table for the active command begins at 0x500.

This compact layout is possible because the driver uses one command slot and one PRDT entry.

## Starting a port

start_port first reads PxCMD.

It clears:

- ST, the command-list run bit;
- FRE, the FIS receive-enable bit.

It then waits until the controller reports both command-list-running and FIS-receive-running state cleared.

Only after the engine stops does the function program:

- CLB/CLBU with the control-page physical base;
- FB/FBU with control-page base + 0x400.

It clears PxSERR by writing all ones, then sets FRE and ST again.

Stopping before replacing command-list/FIS addresses is an important controller-state transition.

## Bounded engine-stop wait

wait_bit polls an MMIO register for at most 200,000 iterations.

start_port uses it to wait for the command and FIS receive engines to stop.

If the bits do not reach the requested state, the port is rejected.

There is no more elaborate HBA reset in this failure path.

The probe moves on to another candidate.

## Building the command header

issue supports one to eight sectors.

It zeroes the complete 4 KiB control page before constructing the command.

The slot-zero command header receives:

- command FIS length = 5 dwords;
- write bit when appropriate;
- PRDT length = 1;
- command-table physical address at control base + 0x500.

The current driver uses exactly one PRDT entry and therefore one contiguous DMA data buffer per command.

## Host-to-device Register FIS

The command table begins with a Register Host-to-Device FIS.

The first dword includes:

- FIS type 0x27;
- command/control bit;
- ATA command opcode.

The driver uses command values including:

~~~text
0xec IDENTIFY DEVICE
0x25 READ DMA EXT
0x35 WRITE DMA EXT
~~~

Unlike the legacy ATA chapter's current task-file path, AHCI is issuing the 48-bit DMA EXT command family.

## LBA encoding

The FIS receives the lower 24 LBA bits in one dword and the next 24 bits in another.

The device register includes the LBA-mode bit.

Architecturally the FIS layout can represent a 48-bit SATA LBA.

However, the ChrisOS issue function receives lba as uint32_t.

Therefore the current AHCI BlockDevice path uses at most 32 meaningful LBA bits even though the command format itself contains fields for 48.

This aligns with the generic BlockDevice uint32_t sector_count limit.

## Sector count

The H2D FIS stores the sector count in the bytes corresponding to the 16-bit count field.

The current issue function restricts count to at most eight sectors.

That is not an AHCI protocol limit.

It comes from the current data buffer:

~~~text
8 sectors * 512 bytes = 4096 bytes
~~~

One 4 KiB DMA page holds the entire transfer.

## PRDT entry

The single PRDT entry at control offset 0x580 receives:

- data base address low;
- data base address high;
- byte-count-minus-one;
- interrupt-on-completion bit.

For n sectors:

~~~text
DBC = n * 512 - 1
~~~

The IOC bit is set.

Despite IOC being present, the current driver does not use an AHCI interrupt handler for ordinary completion.

The command is still polled synchronously.

## Clearing status and issuing slot zero

Before starting the command, issue writes all ones to PxIS to clear pending interrupt-status bits.

It then writes bit zero to PxCI.

That tells the HBA that command slot zero is ready for execution.

No other PxCI slot is used.

There is no queue-depth management in the current driver.

## Completion polling

issue loops up to 500,000 iterations.

Every 128 iterations it calls io_wait.

The primary completion condition is:

~~~text
PxCI bit 0 becomes zero
~~~

Once the controller clears the bit, the code reads PxTFD and PxIS.

If PxTFD has the error bit set, the command returns an error.

Otherwise the command is considered successful.

If PxCI never clears within the budget, issue returns its timeout code.

ahci_rw maps that timeout to BD_ETIMEOUT.

Other nonzero results become BD_EIO.

## Limited error decoding

The current driver reads PxIS for diagnostics but does not implement a comprehensive AHCI error-state decoder.

It primarily tests the task-file ERR bit after completion.

There is no detailed recovery path based on individual PxIS error bits, SATA error register contents or port state transitions.

This keeps the implementation small but limits diagnosability and recovery precision.

## Read/write bounce behavior

ahci_rw exposes the synchronous BlockDevice callback.

Requests are processed in chunks of at most eight sectors.

For a write:

1. caller bytes are copied into the 4 KiB DMA data page;
2. WRITE DMA EXT is issued;
3. completion is polled.

For a read:

1. READ DMA EXT is issued;
2. completion is polled;
3. bytes are copied from the DMA page to the caller.

The controller therefore DMAs into a persistent driver-owned page rather than arbitrary caller memory.

This simplifies physical contiguity and lifetime requirements at the cost of extra copies.

## IDENTIFY DEVICE

Probe uses the same issue path with command 0xec and one sector.

The returned 512-byte identification block is read as 128 32-bit values.

The code uses:

- dword 50 as the low 32 bits of the LBA48 sector count;
- dword 51 as the high 32 bits;
- dword 30 as a fallback containing the classic words 60-61 capacity.

If the high capacity dword is nonzero, the disk is rejected as too large for the current uint32_t BlockDevice model.

If the selected sector count is below 2048 sectors, the candidate is rejected.

## Logical sector-size assumption

The AHCI probe registers:

~~~text
sector_size = 512
~~~

It does not currently parse and normalize ATA IDENTIFY logical-sector-size extensions.

Therefore the current AHCI path assumes a 512-byte logical sector.

A SATA device exposing a different logical block size is not documented as supported.

## Registering the BlockDevice

After successful IDENTIFY, the driver fills:

- ctx = global AhciPort;
- sector_size = 512;
- sector_count = detected capacity;
- read = ahci_read;
- write = ahci_write;
- flush = null;
- writable = true.

It then calls bd_add_kind with BD_AHCI.

The absence of a flush callback means generic bd_flush returns BD_OK without issuing an ATA FLUSH CACHE command on this path.

## Durability boundary

The current AHCI write completes when the DMA command completes successfully.

There is no explicit FLUSH CACHE command in ahci.c.

Therefore a successful BlockDevice write followed by a successful generic bd_flush does not currently demonstrate that a volatile device write cache was explicitly flushed by this driver.

This differs from the legacy ATA driver, whose write path issues command 0xe7.

Filesystem crash-consistency claims must account for this limitation.

## Timeout ownership problem

A more serious recovery boundary appears on timeout.

If PxCI remains set for the entire wait budget, issue returns timeout.

The current ahci_rw path propagates BD_ETIMEOUT.

It does not:

- stop the port;
- clear or abort the command slot;
- reset the HBA;
- prove the controller can no longer DMA into the shared data page.

A later request can reuse the same DMA/control storage.

Therefore the current timeout path lacks a complete ownership-recovery protocol.

A hardened implementation should reset or otherwise quiesce the port before memory involved in a timed-out command is considered reusable.

## Probe-time resource leaks

For each candidate port, ahci_probe allocates ctl and data DMA pages before start_port and IDENTIFY complete.

Several later failure paths simply continue scanning without freeing those allocations.

Examples include:

- start_port failure;
- IDENTIFY failure;
- capacity rejected as too large;
- capacity too small.

Because the next candidate overwrites the global AhciPort fields, those DMA allocations can become unreachable from the driver.

This is a current resource-lifetime defect and should be distinguished from the intended steady-state architecture.

## Single-slot design

AHCI hardware supports multiple command slots, and SATA can support Native Command Queuing.

The current driver uses only slot zero.

Consequences:

- one in-flight command;
- no NCQ;
- no parallel request scheduling;
- no out-of-order completions;
- simple shared-buffer ownership.

This matches the synchronous BlockDevice interface but leaves much of AHCI's performance model unused.

## Polling versus interrupts

Although the PRDT entry requests interrupt-on-completion, the driver does not register an AHCI interrupt handler for normal I/O.

Completion is detected by polling PxCI.

This has two practical effects:

- implementation is simpler;
- CPU time is spent waiting, and the system cannot overlap this I/O with independent work through an asynchronous block API.

An interrupt-driven design would need command/request identity and concurrency rules that the current BlockDevice contract does not expose.

## MMIO and DMA abstraction boundary

AHCI does not call map_mmio_page or PMM directly.

It uses hwgate:

~~~text
PCI BAR -> hw_bar_map -> MMIO window
DMA pages -> hw_dma_alloc -> PMM + HHDM
register I/O -> hw_mmio_*
DMA memory -> hw_dma_*
~~~

That indirection centralizes bounds checking and physical/virtual conversion for several hardware drivers.

It also introduces global limits in hwgate, such as a bounded number of mapped windows and DMA slots.

## Concurrency model

The AHCI driver has global state and no internal request lock.

The same ctl and data pages are reused for every I/O.

Concurrent calls could:

- zero the command page while another command is active;
- overwrite the data bounce page;
- rewrite PxCI-related state;
- confuse completion.

The current design therefore assumes serialized access.

A future multi-request block layer must add explicit per-controller synchronization and per-request storage.

## Performance properties

The current AHCI implementation favors simplicity:

- one 4 KiB data page;
- maximum eight sectors per command;
- one command slot;
- one PRDT entry;
- caller-to-bounce copies;
- polling completion;
- no NCQ.

A large BlockDevice request is split into repeated eight-sector commands.

The controller performs DMA, so CPU data movement is lower than PIO at the hardware boundary, but the software still copies to or from the bounce page.

## Validation targets

A strong AHCI validation matrix should include:

- controller absent;
- multiple AHCI controllers;
- multiple implemented ports;
- port with DET not equal to 3;
- IDENTIFY success/failure;
- 512-byte read/write data integrity;
- transfers crossing eight-sector chunk boundaries;
- disk near the 32-bit sector-count limit;
- device with non-512 logical sectors;
- forced PxTFD error;
- forced timeout;
- proof that timeout recovery stops DMA before reuse;
- repeated failed probes to detect DMA leaks;
- explicit cache-flush durability testing;
- concurrent callers to confirm or enforce serialization;
- physical hardware in addition to QEMU emulation.

Current generic block tests provide end-to-end evidence for successful paths, not all failure-recovery invariants.

## Current limitations

The current AHCI driver has these explicit boundaries:

- scans only PCI buses 0 through 7;
- registers only the first successful AHCI disk;
- no ATAPI path;
- no port multiplier;
- assumes 512-byte logical sectors;
- BlockDevice capacity limited to uint32_t sectors;
- one command slot;
- one PRDT entry;
- maximum eight sectors per command;
- one shared data DMA page;
- synchronous polling rather than interrupt-driven completion;
- no NCQ;
- no explicit FLUSH CACHE implementation;
- incomplete timeout recovery;
- failure paths can leak probe-time DMA allocations;
- no hotplug or power-management lifecycle;
- limited AHCI/SATA error decoding.

These are properties of the current ChrisOS implementation, not of AHCI or SATA generally.

## Source map

kernel/fs/ahci.c implements PCI scan, port selection, engine startup, FIS/PRDT construction, IDENTIFY, synchronous read/write and BlockDevice registration.

kernel/gfx/hwgate.c and hwgate.h provide BAR mapping, MMIO access and DMA allocations used by the driver.

kernel/metal/mm.c maps the MMIO pages underneath hw_bar_map.

kernel/metal/pmm.c backs the DMA allocations.

kernel/fs/block_device.h and bdev.c expose the registered device to the common storage layer.

The implementation claims in this chapter were reconciled against ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.
