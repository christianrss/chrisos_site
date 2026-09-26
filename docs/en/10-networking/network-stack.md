---
id: network-stack
lang: en
type: technical-chapter
volume: 10-networking
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/net/net.c
  - kernel/net/net_xfer.c
  - kernel/net/sock.c
  - kernel/net/virtio_net.c
symbols: []
depends_on:
  - buses-mmio-dma
  - interrupts-smp
related:
  - kernel-model
---

# Network stack and VirtIO networking

## Layered packet processing

Networking converts application data into packets transmitted through a network interface and performs the reverse operation on receive.

A useful separation is:

```text
application / socket
        ↓
transport protocol
        ↓
network protocol
        ↓
link framing
        ↓
network interface driver
        ↓
device queues / wire or virtual host
```

Each layer owns a different addressing and reliability problem. Ethernet addresses a local link, IP addresses routed networks, and transport protocols identify endpoints and delivery semantics.

## Network interface

A network driver moves packet buffers between host memory and a device. With VirtIO-net, the guest and virtual device exchange descriptor chains through virtqueues.

Receive buffers must remain allocated while the host can fill them. Transmit buffers/descriptors must not be recycled until completion establishes that the device no longer consumes them.

This is the same asynchronous ownership rule seen in storage and GPU devices.

## Packets are untrusted input

Network packets originate outside the kernel's trust boundary. Every length, header offset and protocol field must be validated before use.

A malformed length can otherwise turn packet parsing into an out-of-bounds memory access. Checksums and protocol validity are not substitutes for memory-safety bounds checking.

## Sockets

A socket provides a process/application-facing endpoint abstraction. The kernel maps application operations onto protocol state and packet queues.

Current ChrisOS socket state has ownership relationships to processes/slots. The locking audit notes that socket-table mutation is BSP/receive-path sensitive and does not yet have a general socket lock suitable for arbitrary AP receive concurrency.

That limitation must be preserved in documentation rather than generalized into "fully SMP network stack."

## Transfer service

`net_xfer.c` provides project-specific host/guest transfer functionality. Application protocols built on top of TCP or another transport should be treated separately from the transport implementation itself.

## Interrupt and polling boundaries

A device can notify receive completion asynchronously. The driver path must coordinate IRQ context with consumers that read or mutate packet queues.

If receive processing is deferred to a non-IRQ context, the handoff itself is a synchronization boundary.

## Validation

A useful network test hierarchy includes:

- parser/unit tests for malformed frames and lengths;
- driver queue lifecycle tests;
- deterministic virtual-device tests;
- QEMU end-to-end packet exchange;
- physical NIC tests for supported hardware profiles.

Success with VirtIO-net demonstrates the paravirtual path, not an arbitrary physical Ethernet controller.
