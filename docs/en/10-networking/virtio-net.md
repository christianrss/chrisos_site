---
id: virtio-net
lang: en
type: technical-chapter
volume: 10-networking
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/net/virtio_net.c
  - kernel/net/virtio_net.h
  - kernel/metal/pci.c
  - kernel/metal/pci.h
  - kernel/metal/pmm.h
  - kernel/metal/bootinfo.c
  - kernel/metal/bootinfo.h
  - kernel/metal/port.c
  - kernel/metal/port.h
  - kernel/metal/start.c
  - makefile
symbols:
  - virtio_net_init
  - virtio_net_poll
  - virtio_net_tx
  - virtio_process_rx
  - virtio_setup_rx
  - virtio_setup_tx
  - vq_setup_page
  - pci_find_virtio_net
depends_on:
  - buses-mmio-dma
related:
  - network-stack
  - ethernet
  - interrupts-smp
---

# VirtIO-net

## Scope

ChrisOS currently uses one legacy-style VirtIO-net PCI transport as its only implemented network device path.

The driver is intentionally small. It performs:

- PCI discovery through configuration I/O ports;
- legacy VirtIO feature negotiation;
- allocation and attachment of one receive and one transmit virtqueue;
- eight posted receive buffers;
- one reusable transmit buffer;
- polling of used rings;
- synchronous handoff of Ethernet frames to `net_rx_ethernet`.

It does not implement a modern VirtIO PCI capability transport, multiqueue, mergeable receive buffers, checksum offload, segmentation offload, MSI/MSI-X, receive filtering control, or asynchronous transmit ownership.

This chapter documents the transport and memory model exactly as implemented.

## PCI discovery

`pci_find_virtio_net` scans only PCI bus zero:

```text
bus  0
slot 0..31
func 0..7
```

It reads configuration space through the classic 0xCF8/0xCFC mechanism.

The vendor must be:

```text
0x1AF4
```

and the device ID must be either:

```text
0x1000
0x1041
```

The match alone does not imply that ChrisOS supports every transport associated with those IDs.

## Legacy I/O requirement

After finding a matching vendor/device pair, the PCI helper enables:

```text
PCI command bit 0 -> I/O space
PCI command bit 2 -> bus master
```

It then reads BAR0 and requires bit zero to indicate an I/O BAR.

The I/O base is:

```text
BAR0 & 0xFFFC
```

A memory BAR is rejected.

Therefore the actual driver depends on the legacy port-I/O VirtIO register layout even though the matcher accepts two device IDs.

A modern capability-only VirtIO-net function without a compatible legacy I/O BAR is not supported by this code.

## PCI scan limitations

The PCI search does not scan buses beyond bus zero.

It also breaks function scanning when vendor 0xFFFF is encountered.

There is no bridge traversal, ECAM support, PCIe capability walk, or generic device-enumeration object reused by the driver.

This is adequate for the current QEMU machine layout but not general PCI topology discovery.

## Legacy register map

The driver accesses registers relative to the discovered I/O base.

Important offsets are:

```text
+0   host features
+4   guest features
+8   queue PFN
+12  queue size
+14  queue select
+16  queue notify
+18  device status
+19  ISR
+20  device-specific configuration
```

All access uses x86 `inb/inw/inl` and `outb/outw/outl`.

No MMIO mapping is used for this network device.

## Device status sequence

Feature negotiation begins by writing zero to the status register.

ChrisOS then ORs:

```text
ACKNOWLEDGE
DRIVER
```

After feature selection it sets FEATURES_OK and reads status back.

If FEATURES_OK is not retained, it writes VIRTIO_FAILED and aborts.

After queue setup succeeds, DRIVER_OK is added.

The driver's internal `ready` flag is only set after this sequence completes.

## Negotiated features

ChrisOS reads the 32-bit host feature word and accepts only bits shared with:

```text
VIRTIO_NET_F_MAC
VIRTIO_NET_F_STATUS
```

Every other offered feature is dropped.

There is no negotiation of checksum offload, guest checksum, MAC control, mergeable buffers, indirect descriptors, event index, multiqueue, TSO/UFO, or modern VERSION_1.

The small negotiated set keeps packet format simple.

## MAC feature assumption

After negotiation, `virtio_read_mac` unconditionally reads six bytes from device-specific configuration starting at offset +20.

The code does this even if the host did not advertise `VIRTIO_NET_F_MAC`.

In the current QEMU configuration the feature is expected to be present.

As a generic driver contract, however, feature absence should be handled explicitly rather than reading a field whose availability is feature-dependent.

## Link-status handling

When the host feature word includes `VIRTIO_NET_F_STATUS`, the code writes `VIRTIO_NET_S_LINK_UP` to the device-specific field at offset +26.

The source treats that field as something it can set.

The current implementation does not use link-state transitions to gate packet transmission or receive processing after initialization.

There is no link-change state machine or carrier-down notification to sockets.

## Queue selection

VirtIO queue zero is used for RX.

Queue one is used for TX.

For each queue, ChrisOS:

1. writes the queue index to QUEUE_SEL;
2. reads QUEUE_NUM;
3. requires it to be at least eight;
4. allocates enough contiguous physical pages for the full ring layout;
5. writes the ring page frame number to QUEUE_PFN.

The software only provisions eight RX descriptors, even if the device reports a larger queue.

## Ring layout

Each queue contains:

- descriptor table;
- available ring;
- used ring.

Descriptor entries use the standard 16-byte shape:

```text
64-bit address
32-bit length
16-bit flags
16-bit next
```

ChrisOS computes:

```text
desc_bytes  = queue_size * 16
avail_bytes = 4 + queue_size * 2
used_offset = align_up(desc_bytes + avail_bytes, 4096)
used_bytes  = 4 + queue_size * 8
```

The used ring therefore begins on the next 4 KiB boundary after descriptors plus avail.

## Ring allocation

`vq_setup_page` computes the total bytes, rounds to 4096-byte pages, and calls:

```text
pmm_alloc_contig(pages)
```

The returned physical run is converted into a kernel virtual address using the Limine HHDM:

```text
virtual = physical + hhdm_offset
```

The entire ring memory is zeroed before attachment.

There is no per-ring dynamic free path if later initialization fails.

## Physical-address model

VirtIO descriptor addresses contain physical addresses returned by the PMM.

The PMM supports physical memory up to 32 GiB in this project.

The legacy queue PFN is written as a 32-bit value containing:

```text
page_phys >> 12
```

Within the current PMM range, that PFN is representable.

RX/TX packet buffers are also described to the device by physical address directly.

## RX queue population

ChrisOS allocates eight packet pages with `pmm_alloc`.

Each buffer is exposed with descriptor length:

```text
2048 bytes
```

and flag:

```text
VRING_DESC_F_WRITE
```

because the device writes incoming packet data.

Descriptors 0..7 are placed into the available ring and `avail->idx` is set to 8.

The RX queue is then attached and notified.

## RX buffer size versus page size

Each RX packet buffer consumes one 4096-byte physical page but only advertises 2048 bytes to the device.

The remaining half page is unused by this driver.

This simplifies allocation and alignment but doubles physical-page consumption relative to the advertised receive capacity.

Eight RX buffers therefore reserve eight pages for 16 KiB of usable posted packet bytes.

## VirtIO-net header

Every RX buffer is expected to begin with a ten-byte VirtIO-net header.

ChrisOS does not inspect any of its fields.

Because no offload features are negotiated, the driver simply skips those ten bytes and treats the remainder as an Ethernet frame.

On TX, it writes ten zero bytes.

This makes the upper network stack independent of the device transport header.

## RX processing

`virtio_process_rx` snapshots the used index and processes entries until:

```text
last_used == used->idx
```

For each used element it reads:

- descriptor ID;
- total written length.

The descriptor ID must be below eight.

Packets whose total length is at most ten bytes are skipped.

Valid-looking packets are passed synchronously to:

```text
net_rx_ethernet(buf + 10, total_len - 10)
```

and the descriptor is reposted afterward.

## RX descriptor lifetime

The upper network stack receives a pointer directly into the DMA-backed RX page.

No generic packet copy occurs.

The descriptor is not reposted until `net_rx_ethernet` and all nested protocol/service calls return.

That means the frame pointer is valid only during this synchronous call chain.

A future asynchronous protocol queue would need either reference-counted buffer ownership or a copy before repost.

## RX repost

`rx_repost` computes:

```text
slot = avail->idx % queue_max
```

writes the descriptor ID into that ring slot, increments `avail->idx`, executes the compiler memory barrier, and notifies queue zero.

One device notification is therefore generated for every reposted buffer.

There is no batching of multiple returned RX descriptors before notification.

## Queue-size versus software array shape

The C structures for `vring_avail` and `vring_used` declare ring arrays sized to `NET_QUEUE_SIZE`, which is eight.

However, pointer arithmetic and modulo operations use the full queue size reported by the device.

The backing allocation is sized for that reported queue size, so the physical layout may contain more than eight ring entries even though the C type declares eight.

Indexing beyond the declared array bound is not a clean C object-model representation of that variable-length ring.

A safer implementation would model the ring tails through byte offsets or flexible-array-style accessors.

## RX completion-length gap

The used-ring element supplies a total length.

The driver checks only:

```text
total_len > 10
```

before passing `total_len - 10` upward.

It does not require:

```text
total_len <= 2048
```

even though the posted descriptor length is 2048.

A conforming device should not exceed descriptor capacity, but an impossible used length from a faulty or hostile device could cause upper-layer parsers to trust bytes beyond the real RX buffer.

This is a direct device-boundary hardening gap.

## TX storage

TX uses one physical page allocated with `pmm_alloc`.

Only one packet can be staged at a time.

The packet layout in that page is:

```text
10-byte zeroed virtio-net header
Ethernet frame
```

The driver accepts Ethernet length from 1 to 1514 bytes.

Therefore total staged bytes are at most 1524, well below the 4096-byte allocation.

## TX descriptor use

Only descriptor zero is used for transmit.

For every send, the driver writes:

- buffer physical address;
- total length;
- flags = 0;
- next = 0.

The descriptor is placed in the next available-ring slot, but the descriptor ID is always zero.

There are no descriptor chains and no scatter/gather packet assembly.

## TX copy

The caller supplies an ordinary Ethernet frame pointer.

`virtio_net_tx` copies the frame byte-by-byte into the driver's private TX page.

This makes TX ownership simple: after the copy completes, the upper-layer packet buffer may be reused.

The price is one complete software copy for every packet.

## TX completion

Before building a new TX packet, `virtio_net_tx` calls `virtio_drain_tx`.

It calls the same function again immediately after notifying queue one.

`virtio_drain_tx` repeatedly samples the used index and advances `last_used` while completions appear.

The spin loop is bounded at 200000 iterations.

The ISR port is also read during this loop.

There is no explicit error when the bound expires with an outstanding descriptor.

## Synchronous transmit semantics

Because TX waits/drains around every submission and only one buffer exists, the driver behaves synchronously from the upper layer's perspective.

It does not maintain multiple packets in flight.

There is no software TX ring of packet objects, completion callback, or waiter per packet.

This favors simplicity over throughput.

## Polling path

`virtio_net_poll` does three things:

1. returns immediately if the driver is not ready;
2. reads the ISR byte;
3. processes RX and drains TX.

Packet delivery therefore progresses when the kernel calls `net_poll`, which in turn calls this function.

The current path is polling-oriented even though the VirtIO device has an ISR status register.

## Interrupt model

This network driver does not set up MSI/MSI-X or a dedicated queue interrupt handler.

Reading the ISR acknowledges/observes device interrupt state, but protocol work occurs in polling context.

This keeps RX parsing out of interrupt-handler code.

It also means receive latency depends on how often the main system path calls `net_poll`.

## Memory barriers

`vio_mb` is implemented as:

```text
asm volatile("" ::: "memory")
```

This is a compiler barrier, not an explicit CPU fence instruction.

It prevents compiler reordering around ring index updates but does not itself emit a hardware memory-ordering instruction.

On the current x86 target, the implementation relies on the platform's strong ordering behavior for ordinary memory operations.

That assumption should remain architecture-specific.

## Initialization failure paths

Initialization can fail because:

- no matching PCI device is found;
- feature negotiation is rejected;
- RX ring allocation fails;
- any RX packet page allocation fails;
- TX ring allocation fails;
- TX packet page allocation fails.

Queue-setup failure writes VIRTIO_FAILED.

Allocated memory from earlier partial steps is not reclaimed.

A retry after partial failure is therefore not a clean resource-lifecycle operation.

## Ready state

`g_vnet.ready` starts at zero.

It becomes one only after:

- discovery;
- negotiation;
- MAC read;
- RX setup;
- TX setup;
- DRIVER_OK;
- an RX notification.

`virtio_net_tx` refuses work while not ready.

`virtio_net_poll` also becomes a no-op.

## Boot-time disable

Kernel startup calls `net_init` only when the boot flag `nonet` is not active.

The broader `safe` boot mode also sets `nonet`.

This allows the entire network stack to remain uninitialized for diagnostic or reduced-feature boots.

## QEMU configuration

The normal run command attaches:

```text
-device virtio-net-pci,netdev=n0
-netdev user,id=n0,...
```

with host forwards for guest services.

This is the environment against which the driver is primarily exercised.

Successful network services under that QEMU configuration provide integration evidence for device discovery, ring setup, RX/TX, and protocol handoff.

## Test coverage

There is no dedicated host `test_virtio_net.c` in the inspected tree.

The generic graphics-side `virtq.c` has its own host tests, but the network driver does not reuse that helper; it contains a separate legacy ring implementation.

Therefore those `virtq` tests do not directly validate `kernel/net/virtio_net.c`.

Current evidence is mostly boot/QEMU integration.

## Missing transport features

The driver does not support:

- modern VirtIO PCI capabilities;
- VERSION_1 negotiation;
- indirect descriptors;
- event index;
- mergeable RX buffers;
- multiqueue;
- control virtqueue;
- promiscuous/filter configuration;
- checksum offload;
- TSO/UFO/GSO;
- MSI/MSI-X;
- dynamic link-state notifications;
- asynchronous multi-packet TX.

This is a deliberately small driver.

## Concurrency

`g_vnet`, RX/TX ring indices, and the one TX buffer are global and unlocked.

The driver assumes serialized access through the current polling/network path.

Two CPUs calling `virtio_net_tx` concurrently could overwrite the shared TX page and queue state.

RX polling from multiple CPUs could likewise race on `last_used` and repost indexes.

The driver is not generally SMP-safe.

## Recommended hardening

High-value changes are:

1. clamp used RX length to the posted descriptor size;
2. represent variable-length rings without fixed-eight C array bounds;
3. handle missing MAC feature explicitly;
4. separate legacy and modern PCI transports clearly;
5. reclaim partial allocations on failed init;
6. propagate TX timeout/failure;
7. add explicit queue ownership/locking or single-thread confinement;
8. batch RX repost notifications;
9. add dedicated host tests for ring math and malformed used entries;
10. eventually reuse a common, tested VirtIO queue abstraction.

## Revision note

This chapter was created against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. It documents the current legacy port-I/O VirtIO-net transport, its DMA/ring ownership model, eight-buffer RX path, single-buffer synchronous TX design, and the exact hardening gaps visible in the source.
