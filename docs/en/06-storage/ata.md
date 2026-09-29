---
id: ata
lang: en
type: technical-chapter
volume: 06-storage
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/fs/ata_pio.c
  - kernel/fs/ata_pio.h
  - kernel/fs/block_device.h
  - kernel/fs/storage.c
  - kernel/metal/pci.c
  - kernel/metal/pci.h
  - kernel/metal/irq.c
  - kernel/metal/pmm.c
  - kernel/metal/bootinfo.c
symbols:
  - AtaPio
  - ata_pio_configure
  - ata_pio_identify
  - ata_pio_make_device
  - ata_try_identify
  - ata_program
  - ata_poll
  - ata_dma_xfer
  - ata_dma_wait
  - ata_dma_abort
  - ata_read_chunk
  - ata_write_chunk
  - ata_flush_raw
  - pci_find_ide
depends_on:
  - block-storage
  - pci-pcie
  - pic-apic-ioapic
  - physical-memory
related:
  - ahci
  - buses-mmio-dma
  - partitions-gpt
---

# ATA PIO and IDE bus-master DMA

## Scope

The current ChrisOS ATA driver supports legacy task-file I/O through the primary and secondary IDE-compatible port ranges and can optionally accelerate transfers through PCI IDE bus-master DMA. The same driver intentionally preserves a PIO fallback so that a failed DMA path does not automatically make the disk unusable.

The effective architecture is:

~~~text
BlockDevice request
    -> try IDE bus-master DMA, at most 16 sectors
        -> success: complete request chunk
        -> failure: stop DMA and soft-reset ATA path
            -> retry through PIO, at most 255 sectors
~~~

![ATA block I/O path with DMA, IRQ/status completion, abort/reset and PIO fallback](../../assets/diagrams/ata-io-path-en.svg)

This chapter documents the code that exists today rather than the full ATA specification. In particular, the current command programming path is still 28-bit LBA even though IDENTIFY can read a larger LBA48 capacity field.

## Driver state

AtaPio stores:

- command-block I/O base;
- control/alternate-status port;
- selected drive number;
- sector count exposed to BlockDevice;
- polling budget;
- IDE bus-master I/O base;
- a boolean indicating whether DMA was discovered.

ata_pio_configure initializes the default state to the primary channel:

~~~text
I/O base = 0x1f0
control  = 0x3f6
drive    = 0
poll limit = 1,000,000 iterations
DMA disabled
~~~

storage_init then calls ata_pio_identify and, if successful, wraps the state in a BlockDevice.

## Legacy task-file registers

The code uses the conventional register offsets relative to the ATA command-block base:

~~~text
+0 data
+2 sector count
+3 LBA low
+4 LBA mid
+5 LBA high
+6 drive/head
+7 status or command
~~~

The control/alternate-status register is accessed through the separate control base, normally 0x3f6 or 0x376.

PIO data transfers move one 16-bit word at a time through the data register.

A 512-byte sector therefore contains:

~~~text
512 / 2 = 256 words
~~~

The read and write loops perform exactly 256 inw/outw operations per sector.

## Primary and secondary channels

ata_pio_identify searches two legacy channel pairs:

~~~text
primary:   0x1f0 / 0x3f6
secondary: 0x170 / 0x376
~~~

For each channel it tries both drive numbers.

The scan is repeated up to eight attempts. After the first attempt, the code performs a soft reset on both legacy control ports and waits before trying again.

This makes discovery tolerant of a device or emulator that needs additional time to settle after boot.

The function returns immediately after the first successful IDENTIFY.

The current storage layer therefore exposes at most the first ATA device discovered by this AtaPio instance.

## Device selection and 400 ns delay

ata_select writes the drive/head register:

~~~text
0xe0
| drive << 4
| LBA bits 27..24
~~~

It then performs four reads of the control port.

Those repeated alternate-status reads implement the traditional short delay after drive selection without using a wall-clock timer.

The selected high LBA nibble also shows a critical property of the current I/O path: only bits 24..27 of the LBA are placed in the drive/head register.

## IDENTIFY sequence

ata_try_identify:

1. selects the drive;
2. waits until BSY clears;
3. zeros sector-count and LBA registers;
4. sends command 0xEC;
5. waits for DRQ;
6. reads 256 identification words.

The driver rejects the device if word 49 does not report LBA support.

The initial capacity comes from words 60-61, the classic 28-bit LBA sector-count field.

If word 83 bit 10 indicates LBA48 support, the code also reads words 100-103.

The high 32 bits are required to be zero because the current BlockDevice sector_count is only uint32_t.

If the low 32 bits contain a plausible value, that value replaces the 28-bit count.

## Capacity versus command-addressability boundary

The IDENTIFY parser can therefore expose a sector count above 2^28 sectors when the LBA48 capacity field is present.

However, the actual ATA command programming routine still uses:

- LBA0, LBA1 and LBA2;
- the four high 28-bit LBA bits in drive/head;
- legacy READ SECTORS 0x20 and WRITE SECTORS 0x30 for PIO;
- READ DMA 0xC8 and WRITE DMA 0xCA for DMA.

It does not issue READ/WRITE *_EXT commands and does not program the expanded LBA48 register sequence.

Therefore the current data path is effectively limited to 28-bit LBA addressing even if a larger sector_count is discovered.

This is an important current implementation limitation.

A disk larger than the 28-bit addressable range can be identified, but LBAs above 0x0fffffff are not faithfully represented by ata_program because bits 28..31 of the uint32_t LBA are not programmed into the device.

The documentation must not describe the current ATA I/O path as full LBA48 support.

## Status polling

ata_poll repeatedly reads the status register.

It recognizes:

- 0xff as absent device;
- BSY;
- ERR;
- DF;
- DRQ when data is required.

There is also a special empty-bus optimization: repeated status zero before BSY has ever been observed causes the function to return ENODEV after a smaller idle threshold rather than burning the entire poll budget.

This avoids a long boot delay on machines with no legacy ATA disk.

If the poll budget is exhausted, the function returns BD_ETIMEOUT.

## PIO read

ata_read_chunk sends command 0x20.

For each requested sector it:

1. waits for the device to become non-busy and assert DRQ;
2. reads 256 16-bit words;
3. expands each word into two bytes in the destination buffer.

The caller limits the PIO request count to at most 255 sectors so it fits the one-byte task-file sector-count field without relying on the ATA special encoding of zero as 256 sectors.

The path is synchronous and CPU-driven.

While the data loop runs, the CPU performs every transfer.

## PIO write

ata_write_chunk sends command 0x30.

For each sector it:

1. waits for DRQ;
2. packs two source bytes into a 16-bit word;
3. writes 256 words to the data port.

ata_bd_write issues a cache flush after the complete high-level write request.

ata_flush_raw selects the drive, sends FLUSH CACHE command 0xE7 and waits for completion.

This is a stronger durability step than the current AHCI/NVMe/VirtIO Block wrappers, whose BlockDevice flush callbacks are currently absent.

## IDE bus-master discovery

IDENTIFY word 49 bit 8 is used as the device-side DMA capability check.

If the bit is set, pci_find_ide scans PCI bus zero for class 0x0101.

When found, it:

- enables I/O space and bus mastering in the PCI command register;
- reads BAR4;
- requires an I/O BAR;
- records the bus-master base.

The ATA driver then enables DMA mode in its state.

It also installs ide_irq as the handler for IRQ14 and unmasks that PIC line.

The current code uses one global bus-master base and one global IRQ-completion flag.

## IRQ boundary

ide_irq marks g_ide_irq = 1.

If a bus-master base exists, it reads the bus-master status register and writes the same value back to acknowledge/clear status bits according to the controller model.

DMA completion waiting does not rely exclusively on the interrupt.

ata_dma_wait treats either:

- g_ide_irq becoming nonzero; or
- the bus-master interrupt-status bit becoming set

as evidence that completion may have occurred.

It then also waits for ATA BSY to clear and checks the bus-master error bit.

This dual condition helps the path work even when the interrupt timing differs from polling.

## Current IRQ limitation

The code always installs the IDE handler on IRQ14.

Legacy secondary IDE commonly uses IRQ15, but the current driver does not select IRQ14 versus IRQ15 based on the channel that ultimately succeeds.

Because ata_pio_identify scans both channels while the DMA interrupt configuration is global, DMA operation on a secondary-channel device is not documented as fully handled.

This is a concrete current limitation, not a limitation of ATA itself.

## DMA buffer lifetime

The driver uses two persistent global allocations:

- one contiguous data buffer;
- one PRDT page.

The data area is 8192 bytes:

~~~text
16 sectors * 512 bytes = 8192 bytes
~~~

The allocations are performed lazily on the first DMA transfer and retained for the life of the driver.

This avoids repeated PMM allocation during filesystem/install I/O.

It also means the driver is built around one shared DMA transaction state rather than per-request buffers.

## 32-bit DMA addressability

The IDE bus-master path requires the data and PRDT physical addresses to fit in 32 bits.

ata_dma_acquire allocates from the normal PMM and then rejects either address if it exceeds 0xffffffff.

If that happens, it frees the newly allocated memory and reports failure.

The current ATA path does not use pmm_alloc_dma32 directly for these buffers.

Therefore success depends on the general PMM returning low enough memory.

This is another implementation boundary that matters more as physical RAM layouts grow.

## PRDT layout

The driver programs one PRDT entry.

Conceptually:

~~~text
entry address = physical address of DMA data buffer
entry count   = transfer byte count
EOT           = set
~~~

prdt[0] stores the physical buffer address.

prdt[1] stores the byte count ORed with bit 31 as the end-of-table marker.

Because one transfer is limited to 16 sectors, the maximum byte count is 8192 and fits comfortably within one PRD.

No scatter/gather list of multiple discontinuous data regions is used.

## DMA command sequence

ata_dma_xfer:

1. validates DMA availability and a count from 1 to 16 sectors;
2. ensures persistent DMA storage exists;
3. copies caller data into the bounce buffer for writes;
4. builds the PRDT entry;
5. stops the bus-master engine;
6. programs the PRDT address;
7. clears bus-master status;
8. configures transfer direction;
9. clears the IRQ-completion flag;
10. programs the ATA DMA command;
11. starts the bus-master engine;
12. waits for completion;
13. stops the engine;
14. copies from the bounce buffer to caller memory for reads.

The use of a bounce buffer means the ATA controller does not DMA directly into arbitrary caller buffers.

## Why a bounce buffer is useful

A bounce buffer gives the driver a known physical layout and addressability.

Caller memory might be:

- virtually contiguous but physically fragmented;
- above the 32-bit DMA boundary;
- not easy to describe with the current one-entry PRDT.

Copying through a fixed contiguous low-address-compatible region simplifies the hardware contract.

The cost is an extra memory copy on every DMA read and write.

## Bounded DMA wait

ata_dma_wait loops for 200,000 iterations.

It polls:

- bus-master status;
- ATA drive status;
- the IRQ-completion flag.

A completed transfer whose drive remains BSY is not accepted yet.

A bus-master error produces BD_EIO.

Exhausting the loop produces BD_ETIMEOUT.

The wait contains occasional I/O reads from port 0x80 to introduce spacing in the tight polling loop.

The budget is finite, so a broken controller does not block forever in this function.

## DMA abort and fallback

When ata_dma_xfer returns any error, the high-level read/write path invokes ata_dma_abort.

The abort routine:

- stops the bus-master engine;
- soft-resets the selected ATA control port;
- waits for the device to become non-busy.

Only after that recovery step does the code retry through PIO.

This ordering is important for memory ownership.

Falling back while an old DMA engine could still write into the persistent buffer would risk concurrent controller activity against data the CPU is reusing.

## Request chunking

For each BlockDevice request:

DMA attempt:

~~~text
chunk <= 16 sectors
~~~

PIO fallback:

~~~text
chunk <= 255 sectors
~~~

The LBA, remaining count and byte pointer advance by the chunk size that actually completed.

Large BlockDevice requests therefore become several device commands.

The generic block layer does not know about these limits.

## Write completion and flush

After all chunks of a high-level write have completed, ata_bd_write calls ata_flush_raw.

If the flush fails, the write function returns that failure.

Thus “all data words transferred” is not the final success boundary for writes.

The current ATA BlockDevice has a real flush callback, and bd_flush reaches the same raw flush operation.

## Concurrency model

The driver has no per-device lock.

Important state is shared globally or inside one AtaPio instance:

- selected task-file ports;
- drive number;
- one DMA data buffer;
- one PRDT;
- one IRQ-completion flag;
- one bus-master base.

Two concurrent requests could overwrite the PRDT, bounce data, task-file registers or completion state.

The current architecture must therefore serialize access to the ATA device.

The synchronous BlockDevice call pattern currently makes that feasible, but the locking contract is implicit rather than enforced in ata_pio.c.

## Error mapping

The ATA implementation maps hardware conditions into the block-layer domain:

- no bus/device -> BD_ENODEV;
- poll budget exceeded -> BD_ETIMEOUT;
- ERR, DF or bus-master error -> BD_EIO;
- successful command -> BD_OK.

This normalization allows storage.c and ChrisFS to remain unaware of ATA status-bit details.

## Performance properties

PIO is expensive because every sector requires 256 programmed I/O word transfers.

DMA reduces CPU data-movement work but still uses a bounce copy and synchronous wait.

The current maximum DMA payload is only 8 KiB.

There is no command queue, request merging or overlapping I/O.

The design prioritizes a small understandable driver and a recovery path over throughput.

## Validation targets

Strong ATA validation should include:

- primary master and slave;
- secondary master and slave;
- disk absent;
- IDENTIFY timeout;
- PIO read/write/flush;
- DMA read/write;
- forced DMA error followed by PIO fallback;
- data integrity across the 16-sector DMA chunk boundary;
- requests larger than 255 sectors;
- capacity near the 28-bit LBA boundary;
- behavior above 0x0fffffff LBA;
- DMA buffers placed above 4 GiB;
- IRQ14 completion and secondary-channel behavior;
- reboot persistence after flush.

The existing boot-level block tests provide end-to-end read/write evidence on non-root devices, but they do not isolate every ATA-specific case above.

## Current limitations

The current ATA implementation is deliberately constrained:

- legacy task-file I/O model;
- first successfully identified ATA device only;
- current command path is 28-bit LBA;
- IDENTIFY may report a larger LBA48 capacity than the command path can address;
- no READ/WRITE *_EXT command sequence;
- global IRQ14 configuration does not model secondary-channel IRQ15;
- DMA buffers must fall below 4 GiB;
- normal PMM allocation is used rather than a guaranteed DMA32 allocator;
- one PRDT entry and one persistent bounce buffer;
- maximum DMA chunk is 16 sectors;
- no concurrent request serialization inside the driver;
- no NCQ;
- synchronous polling remains part of DMA completion handling.

These are properties of the current ChrisOS driver, not general ATA constraints.

## Source map

kernel/fs/ata_pio.c contains task-file programming, IDENTIFY, PIO loops, DMA setup, completion, reset/fallback and BlockDevice callbacks.

kernel/fs/ata_pio.h defines AtaPio state.

kernel/metal/pci.c provides pci_find_ide and bus-master BAR discovery.

kernel/metal/irq.c provides the IRQ registration and PIC-facing framework used by the IDE handler.

kernel/metal/pmm.c and bootinfo.c supply physical DMA storage and HHDM access.

The implementation claims in this chapter were reconciled against ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.
