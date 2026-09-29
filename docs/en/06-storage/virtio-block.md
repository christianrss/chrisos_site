---
id: virtio-block
lang: en
type: technical-chapter
volume: 06-storage
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/fs/virtio_blk.h
  - kernel/fs/virtio_blk.c
  - kernel/fs/block_device.h
  - kernel/fs/bdev.h
  - kernel/fs/bdev.c
  - kernel/fs/storage.c
  - kernel/gfx/hwgate.h
  - kernel/gfx/hwgate.c
  - kernel/metal/pci.c
  - scripts/qemu.mk
symbols:
  - Vblk
  - virtio_blk_probe
  - kick
  - vblk_rw
  - vblk_read
  - vblk_write
  - hw_bar_map
  - hw_dma_alloc
  - hw_dma_w32
  - hw_dma_r32
  - bd_add_kind
depends_on:
  - block-storage
  - buses-mmio-dma
  - pci-pcie
  - physical-memory
related:
  - nvme
  - usb-storage
  - partitions-gpt
  - chrisfs
---

# VirtIO Block

## Scope

ChrisOS implements a compact VirtIO Block driver for PCI devices. The current path uses the modern VirtIO PCI capability model, negotiates only `VIRTIO_F_VERSION_1`, configures one split virtqueue with four descriptors, builds a fixed three-descriptor request chain, transfers data through one 4 KiB DMA page, notifies queue 0 through the PCI notification capability, and polls the used ring for completion.

The implementation is intentionally small. It is designed to make the transport mechanics visible: PCI capability discovery, common configuration, feature negotiation, split-ring layout, descriptor direction, avail/used indices, device configuration, request status and DMA ownership.

It is not a complete VirtIO Block stack. There is one global device, one queue, one request in flight, no interrupt-driven completion, no packed ring, no indirect descriptors, no discard/write-zeroes, no explicit flush, no multiqueue, no queue reset, and no robust recovery after an ambiguous timeout.

This chapter documents ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

![ChrisOS VirtIO Block PCI capabilities, split virtqueue and request chain](../../assets/diagrams/virtio-block-path-en.svg)

## Position in the storage stack

VirtIO Block is registered through the same `BlockDevice` interface as ATA, AHCI, NVMe and USB storage:

~~~text
ChrisFS / GPT / generic storage
        -> BlockDevice
        -> vblk_read / vblk_write
        -> vblk_rw
        -> kick
        -> split virtqueue descriptor chain
        -> VirtIO Block device
        -> used ring + status byte
~~~

`storage_init` probes VirtIO Block after NVMe and before USB mass storage. A successful probe registers a writable device named `virtio-blk` with kind `BD_VIRTIO`.

Root selection is performed later by generic storage discovery. The transport itself does not select the root filesystem.

## Device identification

The probe scans PCI buses 0 through 7, devices 0 through 31 and functions 0 through 7.

It requires the VirtIO vendor ID:

~~~text
0x1AF4
~~~

and accepts two block-device IDs:

~~~text
0x1042
0x1001
~~~

`0x1042` is the modern VirtIO Block PCI device ID. `0x1001` is the historical transitional block-device ID.

However, the implementation does **not** contain a legacy VirtIO PCI I/O-port transport. Even when the transitional ID is accepted, the driver still requires modern vendor-specific VirtIO PCI capabilities. A transitional device without those capabilities will not initialize through this driver.

The PCI command register is updated with `| 6`, enabling memory decoding and bus mastering.

## Modern VirtIO PCI capabilities

The driver starts at the standard PCI capability-list pointer in configuration offset `0x34`.

It walks the linked capability list and looks for PCI capability ID 9, the vendor-specific capability used by modern VirtIO PCI transport.

For each VirtIO capability, byte 3 of the capability header is interpreted as `cfg_type`. ChrisOS recognizes:

| cfg_type | Meaning | Required by current driver |
|---:|---|---|
| 1 | Common configuration | yes |
| 2 | Notification configuration | yes |
| 3 | ISR status | optional |
| 4 | Device-specific configuration | yes |

For every recognized capability, the code reads the BAR number and configuration offset, maps the corresponding BAR through `hw_bar_map`, and records an MMIO window plus offset.

For notification capability type 2, it also reads `notify_off_multiplier`.

The driver requires common, notify and device configuration regions. ISR capability is optional.

### Capability-parser limits

The current parser is pragmatic rather than defensive. It does not validate the VirtIO capability length or the advertised region length, and it has no explicit iteration limit or cycle detection for a malformed PCI capability chain.

MMIO accesses still pass through the bounded `hw_bar_map`/window abstraction, but the VirtIO capability metadata itself is not fully validated.

## Device reset and status sequence

The common configuration's `device_status` byte is at offset 20.

ChrisOS writes the following sequence:

~~~text
0   RESET
1   ACKNOWLEDGE
3   ACKNOWLEDGE | DRIVER
~~~

It then negotiates features, writes:

~~~text
11  ACKNOWLEDGE | DRIVER | FEATURES_OK
~~~

and checks that bit 3, `FEATURES_OK`, remains set.

After queue configuration, it writes:

~~~text
15  ACKNOWLEDGE | DRIVER | FEATURES_OK | DRIVER_OK
~~~

This is the expected high-level VirtIO initialization progression.

The driver does not set `FAILED` when initialization later fails, and several post-negotiation rejection paths continue PCI scanning without resetting the candidate device.

## Feature negotiation

The driver selects feature page 1:

~~~text
device_feature_select = 1
driver_feature_select = 1
~~~

and writes a single driver-feature bit:

~~~text
driver_feature = 1
~~~

On feature page 1, bit 0 corresponds to feature bit 32:

~~~text
VIRTIO_F_VERSION_1
~~~

No low-page VirtIO Block features are negotiated.

A notable detail is that ChrisOS does not read `device_feature` before writing its driver feature. Instead, it relies on the device's `FEATURES_OK` response to reject an unsupported negotiation. Modern VirtIO devices are expected to expose VERSION_1, so this works with the validated QEMU device, but explicit offered-feature intersection would be clearer and safer.

Because no block-specific features are negotiated, the driver does not opt into capabilities such as flush, discard, write zeroes, topology information, configurable block size, size/segment limits or multiqueue.

## Queue selection and size

ChrisOS uses queue 0, the request queue for the single-queue VirtIO Block configuration:

~~~text
queue_select = 0
~~~

It reads `queue_size` and requires the device to offer at least four entries.

The driver then programs:

~~~text
queue_size = 4
~~~

Only three descriptors are needed by the fixed request chain, but a four-entry queue gives a valid small power-of-two ring.

The implementation does not examine whether the queue was already enabled, does not support queue reset, and does not configure an MSI-X vector.

## One-page split-ring layout

The entire split virtqueue is stored in one 4096-byte DMA page referenced by `g_blk.q`.

ChrisOS chooses fixed offsets:

~~~text
0x000  descriptor table
0x040  available ring
0x800  used ring
~~~

For queue size four:

- descriptor table needs 4 × 16 = 64 bytes;
- available ring begins immediately at byte 64;
- used ring is placed at byte 2048.

The queue physical addresses written into the common configuration are:

~~~text
queue_desc   = q + 0
queue_driver = q + 64
queue_device = q + 2048
~~~

The corresponding high 32-bit physical values are written as well.

After programming the addresses, the driver sets:

~~~text
queue_enable = 1
~~~

The layout is deliberately sparse. It wastes most of the page but makes descriptor, avail and used regions easy to inspect and keeps each region naturally separated.

## Notification address

After selecting queue 0, the driver reads `queue_notify_off`.

The effective notification MMIO address is:

~~~text
notify_cfg_offset
+ queue_notify_off * notify_off_multiplier
~~~

The result is stored as `g_blk.noff`.

Every request is kicked by a 16-bit write of queue index 0 to that notification address.

The driver does not negotiate `VIRTIO_F_NOTIFICATION_DATA`, so the simple queue-index notification format is the relevant one.

## Optional ISR capability

If a type-3 ISR capability is found, ChrisOS stores its MMIO window and offset.

The request path remains polling-based. The ISR byte is read only after success or timeout. Reading the VirtIO ISR status is read-to-clear, so this acknowledges pending VirtIO interrupt state when the capability exists.

The code does not interpret the ISR bits and does not use them as the completion mechanism.

## Device configuration and capacity

VirtIO Block device-specific configuration begins with a 64-bit capacity expressed in 512-byte sectors.

ChrisOS reads:

~~~text
capacity_low
capacity_high
~~~

If the high 32 bits are nonzero, the driver prints:

~~~text
virtio-blk too large
~~~

and rejects the device.

Therefore the exposed capacity is limited to a 32-bit sector count. At 512 bytes per sector, the block interface can represent approximately 2 TiB.

The driver also rejects capacities below 2048 sectors.

The device configuration is read without a `config_generation` consistency loop. A device configuration change racing the two 32-bit capacity reads could therefore produce an inconsistent snapshot.

## Driver state

The global `Vblk` structure stores:

| Field | Meaning |
|---|---|
| `cwin`, `coff` | common configuration MMIO location |
| `nwin`, `noff` | notification MMIO location |
| `isr_win`, `isr_off` | optional ISR status location |
| `isr_ok` | whether ISR capability exists |
| `q` | DMA page holding the split virtqueue |
| `cmd` | DMA page holding request header and status |
| `data` | DMA page holding request payload |
| `avail` | monotonically wrapping available index |
| `sectors` | exposed capacity |

There is one global `g_blk` and one global ready flag. Once a block device is registered, further probes return success immediately.

## DMA allocations

Three physically contiguous one-page allocations are used:

- `q`: virtqueue structures;
- `cmd`: request header plus status byte;
- `data`: payload bounce buffer.

All are allocated with `hw_dma_alloc(1)`, which can return physical addresses above 4 GiB. The VirtIO descriptors and common configuration use full 64-bit physical addresses.

If one of these initial allocations fails, the driver attempts to free all three IDs.

Later rejection paths do not consistently release them, which creates a resource-lifetime gap described below.

## VirtIO Block request header

Each operation uses the request header at offset 0 of the `cmd` page.

ChrisOS writes four 32-bit values:

~~~text
offset 0   type
offset 4   reserved = 0
offset 8   sector low 32 bits
offset 12  sector high 32 bits = 0
~~~

Request type is:

~~~text
0  VIRTIO_BLK_T_IN   // read
1  VIRTIO_BLK_T_OUT  // write
~~~

The sector field in the VirtIO Block protocol is in 512-byte units.

The high 32 bits are always zero because the surrounding ChrisOS block API uses a 32-bit LBA.

## Fixed three-descriptor chain

Every request uses descriptor IDs 0, 1 and 2.

### Descriptor 0 — request header

Descriptor 0 points to the 16-byte request header in the `cmd` page.

Its flags are:

~~~text
VRING_DESC_F_NEXT
~~~

and `next = 1`.

The device reads this descriptor.

### Descriptor 1 — data buffer

Descriptor 1 points to the internal `data` page.

For a write, the device reads guest memory, so flags contain only:

~~~text
VRING_DESC_F_NEXT
~~~

For a read, the device must write into guest memory, so flags are:

~~~text
VRING_DESC_F_NEXT | VRING_DESC_F_WRITE
~~~

In both cases, `next = 2`.

### Descriptor 2 — status byte

Descriptor 2 points to `cmd + 32`, length one byte.

Its flag is:

~~~text
VRING_DESC_F_WRITE
~~~

because the device writes the request status.

The driver initializes the low status byte to `0xFF` before submission.

The expected success value is zero.

## Available ring publication

The queue's available ring begins at offset 64.

The driver always submits descriptor head 0. The ring entries are initialized to zero with the DMA page, and the code explicitly writes zero at offset 68.

For every request:

1. `g_blk.avail` is incremented as a 16-bit value;
2. the new index is saved locally as `idx`;
3. the avail flags/index dword at offset 64 is written with `idx` in the high 16 bits;
4. queue 0 is notified.

Because every available-ring entry contains descriptor head 0, the fixed descriptor chain can be reused after each synchronous completion.

The driver does not use `EVENT_IDX`, interrupt suppression, indirect descriptors or packed rings.

## Used-ring completion

The used ring begins at queue-page offset 2048.

ChrisOS reads the first 32-bit word there and interprets the upper 16 bits as `used.idx`.

A request is considered successful only when:

~~~text
used.idx == submitted_idx
and
status_byte == 0
~~~

With only one request outstanding, the used index is sufficient for the current happy-path synchronization. The driver does not inspect the used-ring element's descriptor ID to verify that the device completed head 0.

It also does not use the used element length for normal success handling.

## A concrete error-classification issue

VirtIO Block status values include nonzero errors such as I/O error and unsupported operation.

The current `kick` loop waits specifically for:

~~~text
used.idx == idx && status == 0
~~~

If the device advances `used.idx` but writes a nonzero status, ChrisOS does **not** immediately return an I/O error. It continues polling until the finite wait budget expires and then returns timeout.

As a result, some genuine VirtIO Block device errors are currently misclassified as:

~~~text
BD_ETIMEOUT
~~~

rather than:

~~~text
BD_EIO
~~~

Although `vblk_rw` contains a generic non-timeout error branch, the current `kick` implementation returns only success or timeout in practice.

This should be corrected by detecting completion independently from status, then mapping the status byte explicitly.

## Polling strategy and the QEMU yield path

The completion path has two polling stages.

First it performs up to 2000 tight iterations.

If completion has not arrived, it performs up to 4096 additional iterations. In each iteration it calls:

~~~text
serial_putc(0)
~~~

before checking the used ring again.

The source comment explains the purpose: QEMU disk writes complete on an I/O thread, and the serial operation exits the TCG execution path long enough for that host thread to make progress. A previous smaller yield budget was insufficient on busy hosts.

This is a highly environment-specific scheduling workaround. It is useful evidence about the validated QEMU configuration, but it is not a portable VirtIO synchronization primitive.

On physical hardware or another hypervisor, serial I/O should not be required to make block completion progress.

## Timeout diagnostics

If both polling phases expire, the driver optionally reads the ISR byte, prints diagnostics and returns `-2`.

The diagnostic includes:

- raw used-ring header value;
- length from the first used element;
- current status byte.

`vblk_rw` converts `-2` to `BD_ETIMEOUT`.

The timeout path does not reset the device, reset the queue, revoke DMA addresses or prove that the old request can no longer complete later.

Therefore reuse of the fixed descriptor chain and shared data page after an ambiguous timeout is not backed by a complete DMA-ownership recovery protocol.

## Data transfer size

The payload page is 4096 bytes.

With the block interface using 512-byte sectors:

~~~text
4096 / 512 = 8 sectors
~~~

`vblk_rw` caps each request at eight sectors. Larger operations are split into sequential requests.

For a caller request of `N` sectors, the number of VirtIO submissions is approximately:

~~~text
ceil(N / 8)
~~~

No scatter/gather beyond the fixed three-descriptor request is used for payload expansion.

## Read path

For reads, descriptor 1 is marked device-writable.

After successful completion, `vblk_rw` copies the internal DMA page into the caller buffer using 32-bit `hw_dma_r32` accesses and byte extraction.

The device transfer is DMA, but the software path is not zero-copy. CPU copy cost remains `O(n)` in transferred bytes.

## Write path

For writes, caller bytes are first packed into 32-bit values and copied into the internal DMA page.

Descriptor 1 is device-readable, the queue is notified, and the driver waits synchronously.

The block device is registered with:

~~~text
flush = 0
~~~

No `VIRTIO_BLK_T_FLUSH` request is issued, and the flush feature is not negotiated. Generic `bd_flush` treats a missing callback as success.

Consequently the current backend does not provide an explicit persistence barrier for filesystem durability.

## Read-only and other block features

Because only VERSION_1 is negotiated, ChrisOS does not inspect or accept block-specific feature bits.

One consequence is that the driver always registers:

~~~text
writable = 1
~~~

without checking a negotiated read-only capability.

A device that is effectively read-only may therefore still appear writable to the ChrisOS block registry and only reject the operation at request time.

Other omitted feature-driven behavior includes:

- flush;
- configurable block size;
- segment and request-size limits;
- topology information;
- discard;
- write zeroes;
- multiqueue.

## Memory ordering

Virtqueue operation normally requires ordering between:

1. descriptor/data writes;
2. publication of the available index;
3. device notification;
4. observation of the used index and status.

The current driver does not contain explicit VirtIO memory barriers around these transitions.

The validated x86/QEMU environment is comparatively forgiving because of coherent DMA and stronger CPU ordering. That result should not be generalized to weakly ordered architectures or non-coherent environments.

A portable driver should make the required producer/consumer barriers explicit.

## Concurrency and ownership

The driver has one global:

- queue page;
- request page;
- payload page;
- avail index.

There is no driver lock.

Concurrent callers could overwrite descriptors, request headers, payload data and queue indices while a previous operation is active.

The required invariant is therefore one request at a time.

VirtIO itself supports much greater concurrency; the limitation comes from the current ChrisOS implementation.

## Probe-time resource lifetime

Initial allocation failure is handled by freeing the queue, command and data pages.

After all allocations succeed, later rejection paths can continue without cleanup. Examples include:

- queue size below four;
- capacity above the 32-bit block limit;
- capacity below the minimum accepted size.

The device may also have reached `FEATURES_OK` or even have queue configuration state when the probe abandons it.

The driver does not reset the device or release all allocated DMA state on every such path.

This is a bounded resource leak today, but it should be fixed before supporting multiple devices or repeated probing.

## Other transport limitations

The current implementation does not:

- validate the full capability region lengths;
- guard against cyclic malformed PCI capability chains;
- negotiate low-page device features;
- read offered features before writing the selected feature;
- use MSI-X;
- use interrupt-driven request completion;
- interpret ISR reason bits;
- handle device configuration change notifications;
- use `config_generation` for stable device-config snapshots;
- use indirect descriptors;
- use packed virtqueues;
- negotiate `EVENT_IDX`;
- support multiple request queues;
- support queue reset;
- set `FAILED` on initialization failure;
- perform complete teardown.

These are implementation boundaries rather than VirtIO protocol limitations.

## Security and privilege

VirtIO PCI requires privileged PCI configuration, MMIO mapping and bus-master DMA.

The device receives physical addresses for the queue, request header and data page. ChrisOS currently does not constrain the device through an IOMMU domain.

Existing safeguards include:

- bounded MMIO-window access;
- kernel-owned physically contiguous DMA pages;
- full 64-bit DMA addresses;
- generic block-layer LBA bounds;
- a one-page maximum payload;
- finite polling loops.

Missing hardening includes IOMMU isolation, per-request DMA mapping, explicit memory barriers, concurrency locking and robust teardown after timeout.

## Performance characteristics

The current implementation favors inspectability over throughput.

Its main limits are:

- one request queue;
- queue size four;
- one outstanding request;
- one 4 KiB payload;
- synchronous polling;
- CPU bounce copies;
- no indirect descriptors;
- no multiqueue;
- no batching;
- no interrupt-driven sleep/wakeup;
- a serial-output yield loop in the slow completion path.

VirtIO Block can scale substantially beyond this design, especially with multiqueue and larger descriptor chains.

## Validation evidence

`scripts/qemu.mk` defines the dedicated `test-qemu-vblk` gate.

The test creates a 32 MiB image and attaches it using:

~~~text
-device virtio-blk-pci,drive=vblk
~~~

The gate requires:

~~~text
virtio-blk sectors=
bdev rw ok virtio-blk
~~~

The generic `bdev_rw_tests` function tests the last sector of each writable non-root device:

1. read the original sector;
2. write a deterministic pattern;
3. read it back;
4. compare all 512 bytes;
5. restore the original data.

Because the normal IDE disk remains root, the VirtIO Block disk is eligible for this round-trip test.

This validates, for the QEMU PCI device used by the project, capability discovery, feature negotiation, queue setup, notification, descriptor direction, DMA payload transfer, used-ring completion and request status on both write and read.

The source tree also contains a RISC-V QEMU gate using `virtio-blk-device`, but that does not by itself prove that this exact PCI transport path is the implementation being exercised there. The direct evidence for the driver described in this chapter is `test-qemu-vblk`.

## Current limitations

At the documented revision, ChrisOS VirtIO Block is limited to:

- one registered VirtIO Block device;
- modern PCI capability transport only, even though both modern and transitional block IDs are accepted;
- queue 0 only;
- split ring only;
- queue size four;
- one request outstanding;
- fixed descriptor chain 0 → 1 → 2;
- one 4 KiB payload page;
- maximum eight 512-byte sectors per request;
- synchronous polling;
- optional ISR acknowledgement but no interrupt-driven completion;
- only `VIRTIO_F_VERSION_1` negotiated;
- no block-specific feature negotiation;
- no explicit flush;
- writable flag set without read-only feature handling;
- no discard or write zeroes;
- no multiqueue;
- no indirect descriptors;
- no packed ring;
- no explicit VirtIO memory barriers;
- nonzero device status potentially misclassified as timeout;
- no robust queue/device recovery after timeout;
- no driver-level locking;
- 32-bit sector count, limiting exposed capacity to approximately 2 TiB;
- no config-generation consistency loop;
- incomplete cleanup/reset on failed probes;
- validation centered on QEMU rather than physical or diverse hypervisor implementations.

## Roadmap boundary

A more complete implementation could negotiate the full offered-feature intersection, map nonzero request statuses directly to block errors, add explicit memory barriers, implement `FLUSH`, honor read-only and block-size features, support indirect descriptors and larger transfers, add multiqueue, MSI-X and interrupt-driven completion, use config-generation retry loops, implement queue reset and complete teardown, isolate DMA through an IOMMU, and validate across additional hypervisors and hardware-backed VirtIO environments.

Those capabilities remain roadmap items until source and reproducible tests establish them.

## Source map and revision note

`kernel/fs/virtio_blk.c` implements PCI capability discovery, VirtIO status/feature setup, queue configuration, request construction, notification, polling and block adaptation. `kernel/fs/virtio_blk.h` exposes the probe entry point. `kernel/gfx/hwgate.c` provides MMIO and DMA helpers. `kernel/fs/block_device.h`, `kernel/fs/bdev.h` and `kernel/fs/bdev.c` define and register the common block interface. `kernel/fs/storage.c` integrates the device into generic discovery and validation. `scripts/qemu.mk` provides the dedicated VirtIO Block QEMU gate.

All current-behavior claims in this chapter were reconciled against ChrisOS `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.
