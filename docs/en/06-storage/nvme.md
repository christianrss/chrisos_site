---
id: nvme
lang: en
type: technical-chapter
volume: 06-storage
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/fs/nvme.c
  - kernel/fs/nvme.h
  - kernel/fs/block_device.h
  - kernel/fs/bdev.c
  - kernel/gfx/hwgate.c
  - kernel/gfx/hwgate.h
  - kernel/metal/pci.c
symbols:
  - Nvme
  - nvme_probe
  - admin_cmd
  - io_rw
  - nvme_rw
  - wait_cq
  - ring_sq
  - ring_cq
  - hw_bar_map
  - hw_dma_alloc
depends_on:
  - block-storage
  - pci-pcie
  - buses-mmio-dma
related:
  - ahci
  - virtio-block
  - partitions-gpt
---

# NVMe queues and namespaces

## Scope

NVMe exposes storage through memory-resident submission and completion queues rather than SATA task files. The current ChrisOS driver reduces that model to one controller, one namespace, tiny two-entry queues and one 4 KiB data buffer behind the synchronous BlockDevice API.

The current path is:

~~~text
BlockDevice request
  -> copy up to 8 sectors through one DMA page
  -> write one 64-byte I/O command into the SQ
  -> ring the SQ doorbell
  -> poll the matching CQ entry by phase bit
  -> advance CQ head and ring CQ doorbell
  -> return BD_OK / BD_EIO / BD_ETIMEOUT
~~~

![Current NVMe queue path in ChrisOS](../../assets/diagrams/nvme-queue-path-en.svg)

The implementation is enough to demonstrate the essential NVMe queue protocol, but it deliberately leaves most performance and recovery features unused.

## Controller state

The Nvme structure stores:

- mapped MMIO window;
- doorbell stride;
- admin SQ/CQ DMA handles;
- I/O SQ/CQ DMA handles;
- one DMA data page;
- admin and I/O heads/tails;
- command identifier counter;
- independent phase bits;
- exposed sector count.

The driver is global and guarded by g_ready rather than instantiated once per PCI function.

Once the first controller is successfully registered, later probe calls return success without searching for another NVMe device.

## PCI discovery

nvme_probe scans PCI buses 0 through 7, all 32 devices and eight functions.

It requires class/subclass:

~~~text
0x0108
~~~

for NVM Express.

The driver enables PCI memory space and bus mastering, then maps BAR0 through hw_bar_map.

NVMe MMIO registers are accessed through the shared hwgate window abstraction rather than by dereferencing the BAR physical address directly.

## CAP and doorbell stride

The driver reads the 64-bit CAP register from offsets 0 and 4.

It extracts DSTRD from the upper dword and computes:

~~~text
stride = 4 << DSTRD
~~~

Submission and completion doorbells begin at MMIO offset 0x1000.

For queue 0 and queue 1 the driver computes doorbell offsets from that stride.

The implementation therefore does not assume that every controller uses the minimum four-byte doorbell spacing.

## Controller disable phase

Before programming admin queues, the driver reads CC at offset 0x14 and clears EN.

It then polls CSTS.RDY at offset 0x1c for up to 200,000 iterations, looking for RDY == 0.

A subtle current limitation is that the code exits the loop either when ready clears or when the loop budget is exhausted, but it does not explicitly reject the controller if the final state is still RDY == 1.

It proceeds to allocate/program queues.

The same pattern occurs later when enabling: the code polls for RDY == 1 but does not explicitly test that the loop actually observed readiness before issuing admin commands.

A hardened driver should make both transitions explicit failure gates.

## DMA allocations

The probe allocates five one-page DMA regions:

- admin submission queue;
- admin completion queue;
- I/O submission queue;
- I/O completion queue;
- data buffer.

If any allocation fails, the code calls hw_dma_free on all five handles and continues probing.

hw_dma_free safely rejects invalid handles, so cleanup can be written uniformly.

The queues/data use normal contiguous physical memory and expose both low and high address halves to the controller.

## Admin queue geometry

The Admin Queue Attributes register is written as:

~~~text
AQA = 1 | (1 << 16)
~~~

NVMe queue-size fields encode number of entries minus one.

Therefore both admin queues contain:

~~~text
1 + 1 = 2 entries
~~~

ASQ and ACQ receive the 64-bit physical addresses of their DMA pages.

The controller is then enabled with command-entry and completion-entry sizes:

~~~text
IOSQES = 6 -> 2^6 = 64 bytes
IOCQES = 4 -> 2^4 = 16 bytes
~~~

Those sizes match the command/completion offsets used by the code.

## Command identifier

Each admin or I/O command increments a 16-bit cid field.

The command identifier is stored in bits 31..16 of command dword zero.

The current completion wait does not compare the returned CID with the submitted CID.

Because the design permits only one synchronous command to be outstanding per queue in the intended execution model, phase/head position is treated as sufficient to identify the expected completion.

That assumption would break under multiple concurrent in-flight commands.

## Completion phase bit

NVMe completion queues are circular.

A stale entry at the current head may still contain old data, so queue wrap is distinguished by a phase tag.

ChrisOS stores an expected phase for admin and I/O queues, initially 1.

wait_cq reads completion dword 3 and tests bit 16.

When the phase matches:

1. status is extracted from bits above 16;
2. head advances with & 1;
3. wrap to head zero toggles expected phase;
4. the CQ doorbell is updated;
5. zero status returns success.

This is the core mechanism that makes a reused two-entry completion queue distinguish new entries from old ones.

## Bounded completion wait

wait_cq polls at most 400,000 times.

If no entry with the expected phase appears, it returns -2.

The BlockDevice path maps -2 to BD_ETIMEOUT.

A nonzero NVMe completion status becomes -1 and then BD_EIO.

The current wait is pure polling; no MSI/MSI-X or legacy interrupt completion handler is installed.

## Admin command construction

admin_cmd uses the current admin SQ tail to select one of two 64-byte entries.

It zeroes all 16 dwords and writes:

- opcode and CID;
- namespace ID;
- PRP1 low/high;
- CDW10;
- CDW11.

It advances the tail modulo two, rings the admin SQ doorbell and synchronously waits for one completion.

Only the fields needed by the current probe are modeled.

## Identify Controller

The first admin command uses opcode 0x06 with CNS = 1.

The data PRP points at the shared 4 KiB DMA page.

The driver reads NN from offset 516 and requires at least one namespace.

It does not enumerate all namespace IDs.

The implementation proceeds directly to namespace 1 later.

Therefore “controller reports one or more namespaces” becomes “ChrisOS will use namespace 1.”

Controllers where the relevant active namespace is not NSID 1 are outside this current policy.

## Creating the I/O Completion Queue

The driver issues admin opcode 0x05.

CDW10 encodes:

- queue identifier 1;
- queue size field 1, meaning two entries.

CDW11 is 1 in the current code.

This requests the attributes needed by the small I/O CQ.

The queue is backed by the allocated io_cq physical page even though only two 16-byte entries are used.

## Creating the I/O Submission Queue

Admin opcode 0x01 creates I/O SQ 1.

The queue-size field is again one, so there are two 64-byte entries.

CDW11 associates the SQ with CQ 1 and sets the current queue attributes.

Once both admin commands succeed, ordinary reads/writes can use queue pair 1.

## Identify Namespace

The driver sends Identify opcode 0x06 for NSID 1 with CNS = 0.

It reads namespace size from the first 64-bit NSZE field.

Only the low 32 bits are accepted.

If the next dword is nonzero, the namespace is rejected as too large for BlockDevice sector_count.

This creates the same approximately 2 TiB ceiling documented by the generic storage layer at 512-byte LBAs.

## LBA format restriction

The driver reads the namespace LBA-format information at offset 128 and extracts the LBA data-size exponent.

It requires:

~~~text
LBADS = 9
2^9 = 512 bytes
~~~

Any namespace using another selected logical block size is rejected.

The current driver does not negotiate or select an alternative LBA format.

## I/O command construction

io_rw writes one I/O command at the current two-entry SQ tail.

It sets:

- opcode 0x02 for read or 0x01 for write;
- CID;
- NSID = 1;
- PRP1 = physical address of the one-page data buffer;
- starting LBA in CDW10;
- NLB = count - 1 in CDW12.

Only PRP1 is populated.

There is no PRP2 or PRP list.

That is valid for the current transfer because data never exceeds one 4 KiB page.

## Eight-sector limit

nvme_rw chunks a BlockDevice request into at most eight sectors:

~~~text
8 * 512 = 4096 bytes
~~~

For writes, caller bytes are copied into the shared DMA page.

For reads, the page is copied back after successful completion.

A larger BlockDevice request therefore becomes several NVMe commands.

The limit is an implementation consequence of the single-page bounce buffer, not an NVMe protocol limit.

## Doorbell ownership

After placing a command in the SQ, ChrisOS advances the tail modulo two and writes it to the SQ doorbell.

After consuming a completion, it advances the CQ head and writes that value to the CQ doorbell.

These doorbell writes communicate ownership transitions:

- new SQ entries become visible to the controller;
- consumed CQ entries become available for reuse.

The code uses ordinary MMIO helper writes; the current design relies on the architectural/hardware-gate ordering provided by those volatile MMIO accesses.

## Synchronous single-command assumption

Although each queue contains two slots, the BlockDevice wrapper waits for every command before submitting the next one.

There is therefore no intended queue depth greater than one in flight.

The second slot mainly permits circular head/tail progression and phase-bit wrap.

The driver does not maintain a software table of outstanding CIDs.

This dramatically simplifies lifetime management but leaves NVMe's parallelism unused.

## Timeout recovery limitation

If wait_cq times out, nvme_rw returns BD_ETIMEOUT.

The current driver does not:

- issue Abort;
- reset the controller;
- recreate queues;
- prove that the timed-out command can no longer DMA into the shared data page.

The next request can reuse the same DMA storage.

Therefore timeout is not currently a fully closed ownership transition.

A hardened implementation must quiesce or reset the controller before reusing memory that an old request could still access.

## Completion error recovery

A nonzero completion status becomes BD_EIO.

The driver does not decode status-code type and status code into finer block-layer categories.

It also does not perform command-specific recovery.

This is adequate for a compact bring-up driver but weak for diagnostics and robustness.

## Probe failure resource lifetime

The driver frees all DMA allocations only in the immediate “allocation set incomplete” branch.

After all five allocations succeed, many later probe failures simply continue:

- controller/admin command failures;
- no namespace;
- I/O queue creation failure;
- namespace too large;
- sector size rejected;
- namespace too small.

Those paths do not release the five DMA handles before scanning onward.

Because g_nv fields are overwritten by a later candidate, successful allocations from failed probes can become leaked.

This is a current resource-lifetime defect.

## Readiness transition verification

The controller disable and enable loops are bounded, which is good for avoiding infinite boot hangs.

However, there is no explicit post-loop timeout result.

If CSTS never reaches the desired state, the code still continues.

That can turn a readiness failure into a later, less precise admin-command timeout.

A stronger design would return or reset immediately when the transition budget expires.

## Flush semantics

The registered BlockDevice sets flush = null.

Generic bd_flush therefore returns BD_OK without issuing NVMe Flush opcode 0x00.

A successful write plus generic flush is not evidence that volatile controller/device cache has been explicitly committed by this driver.

Crash-consistency guarantees must account for that gap.

## Concurrency

Nvme is one global structure with:

- shared queue memory;
- shared data page;
- shared head/tail values;
- shared CID counter.

No driver lock protects those fields.

Concurrent BlockDevice requests could reuse an SQ entry, overwrite the data bounce page or corrupt head/tail state.

The current synchronous architecture must serialize callers.

Supporting real queue depth requires per-request ownership and synchronization.

## Performance

The implementation exercises the NVMe programming model but not NVMe-scale performance:

- one controller;
- namespace 1 only;
- queue depth effectively one;
- two-entry queues;
- one I/O queue pair;
- one 4 KiB bounce page;
- maximum eight sectors per command;
- polling completions;
- no interrupt coalescing;
- no multi-core queue pairs;
- no scatter/gather PRP list.

Its value is architectural clarity and a working block path, not throughput.

## Validation targets

Strong validation should include:

- controller absent;
- RDY transition timeout;
- queue creation failure;
- namespace not equal to 1;
- non-512-byte LBA format;
- >32-bit NSZE;
- read/write crossing eight-sector boundaries;
- CQ wrap and phase toggling;
- nonzero completion status;
- forced completion timeout followed by safe reset;
- repeated failed probes to expose DMA leaks;
- explicit Flush command durability;
- concurrent submissions;
- physical hardware in addition to emulated NVMe.

The generic boot block test validates successful end-to-end I/O but does not prove these recovery boundaries.

## Current limitations

The current NVMe driver has:

- PCI scan only on buses 0..7;
- first successful controller only;
- namespace 1 only;
- two-entry admin and I/O queues;
- effectively one request in flight;
- one I/O queue pair;
- one 4 KiB shared data buffer;
- PRP1 only;
- maximum eight 512-byte sectors per command;
- uint32_t namespace capacity;
- 512-byte selected LBA format only;
- polling rather than interrupt completion;
- no Flush command;
- incomplete timeout recovery;
- incomplete controller-ready transition validation;
- probe-time DMA leaks after later failures;
- no detailed status-code decoding;
- no multi-queue/multi-core design.

These are ChrisOS implementation limits, not NVMe protocol limits.

## Source map

kernel/fs/nvme.c implements PCI discovery, controller setup, admin/I/O queue construction, phase-based completion polling, namespace identification and BlockDevice I/O.

kernel/gfx/hwgate.c provides BAR mapping, MMIO and DMA helpers.

kernel/fs/block_device.h and bdev.c expose the successful namespace as a common block device.

The implementation claims were reconciled against ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.
