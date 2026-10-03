---
id: network-stack
lang: en
type: technical-chapter
volume: 10-networking
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/net/net.c
  - kernel/net/net.h
  - kernel/net/sock.c
  - kernel/net/sock.h
  - kernel/net/net_xfer.c
  - kernel/net/net_xfer.h
  - kernel/net/virtio_net.c
  - kernel/net/virtio_net.h
  - makefile
symbols:
  - net_init
  - net_poll
  - net_rx_ethernet
  - virtio_net_init
  - virtio_net_poll
  - virtio_net_tx
  - sock_init
  - sock_on_tcp
  - sock_on_udp
  - sock_tick
  - net_xfer_tcp
depends_on:
  - buses-mmio-dma
  - interrupts-smp
related:
  - ethernet
  - ipv4
  - udp
  - tcp
  - virtio-net
  - sockets
---

# Network stack and VirtIO networking

## Scope

ChrisOS networking is a compact, poll-driven stack built around one legacy VirtIO-net PCI device and a small set of in-kernel protocol state machines.

The implementation is intentionally narrow. It is sufficient for the QEMU user-network environment used by the project, for UDP/TCP echo paths, simple socket clients and listeners, DNS queries, a host rebuild channel, and a TCP-based file-transfer service.

It is not a general-purpose BSD-compatible network stack.

The implemented layering is:

```text
process / CLVM application
        |
        v
socket table / project services
        |
        v
UDP or small TCP state machines
        |
        v
IPv4
        |
        v
Ethernet II
        |
        v
VirtIO-net legacy PCI
        |
        v
virtqueues / QEMU user network
```

This chapter documents integration across those boundaries. Protocol-specific wire formats are covered separately.

## Global architecture

The stack is split across four principal source files.

`virtio_net.c` owns the PCI device, VirtIO feature negotiation, receive/transmit virtqueues, DMA-visible buffers, MAC address, and polling of used rings.

`net.c` owns Ethernet dispatch, ARP handling, IPv4 header generation, built-in UDP/TCP echo behavior, one gateway-MAC cache, and the shared transmit packet buffer.

`sock.c` implements the process/application-facing socket table, basic listen/connect/send/recv/close semantics, DNS helper state, and the host rebuild client.

`net_xfer.c` implements a project-specific TCP file-transfer state machine on port 9016.

These pieces share global state and are designed to run under the current serialized polling model.

## Initialization order

`net_init` resets three pieces of top-level state:

- `g_net_ready = 0`;
- gateway MAC marked invalid;
- built-in TCP echo connection marked inactive.

It then calls `virtio_net_init`.

If device initialization fails, `net_init` returns zero and leaves the network unavailable.

After successful device initialization it:

1. marks the network ready;
2. initializes the transfer service;
3. initializes the socket table;
4. prints the fixed IPv4 address.

The fixed local address is 10.0.2.15.

## VirtIO device discovery

The driver searches PCI for the legacy VirtIO-net device and receives an I/O-port base address.

It resets device status, sets ACKNOWLEDGE and DRIVER, reads host feature bits, and only negotiates:

- `VIRTIO_NET_F_MAC`;
- `VIRTIO_NET_F_STATUS`.

If FEATURES_OK is not accepted by the device, initialization fails and VIRTIO_FAILED is written.

After negotiation, the driver reads the six-byte MAC address from device configuration space.

## Queue topology

The current driver uses two virtqueues:

- queue 0 for receive;
- queue 1 for transmit.

The physical ring allocation uses the queue size reported by the device, but ChrisOS requires that size to be at least eight.

`NET_QUEUE_SIZE` is eight.

Only eight RX descriptors are populated, and the TX path uses descriptor zero.

Ring memory is allocated as contiguous physical pages and mapped through the kernel's physical-to-virtual mapping helper.

## RX buffers

Each of the eight receive descriptors is backed by one physical page allocated through `pmm_alloc`.

The descriptor length exposed to the device is:

```text
NET_RX_BUF_SIZE = 2048 bytes
```

Each descriptor is marked WRITE because the device writes incoming packet bytes into guest memory.

All eight descriptors are posted to the available ring before the RX queue is notified.

## VirtIO packet header

The driver expects a 10-byte legacy VirtIO-net header at the beginning of every RX/TX device buffer.

This transport header is not part of Ethernet.

On receive, the driver strips it logically by calling:

```text
net_rx_ethernet(buf + 10, total_len - 10)
```

On transmit, it writes ten zero bytes before copying the Ethernet frame.

Thus protocol code above the driver always sees ordinary Ethernet framing.

## Synchronous RX ownership

Receive ownership is simple and important.

A used RX descriptor remains owned by the stack while `net_rx_ethernet` and all lower protocol handlers execute synchronously.

Only after the entire call chain returns does `rx_repost` put the descriptor back into the available ring.

The effective path is:

```text
used descriptor
  -> Ethernet
  -> ARP or IPv4
  -> UDP/TCP
  -> socket/service handling
  -> return
  -> descriptor repost
```

No protocol layer may retain a pointer into the RX descriptor after this sequence completes.

Persistent connection data is copied into dedicated kernel structures.

## Zero-copy receive boundary

From the VirtIO RX buffer through Ethernet, IPv4, UDP/TCP parsing, ChrisOS does not create a generic packet copy.

Parsers use offsets into the same receive frame.

This keeps memory traffic low and makes packet handling predictable.

The cost is that bounds validation and lifetime discipline become critical because every layer is operating directly on externally supplied bytes.

## RX completion trust

The driver verifies that a used descriptor ID is one of the eight RX descriptors and that the completion contains more than the ten-byte VirtIO header.

It does not currently reject a reported used length greater than the 2048-byte capacity of the posted buffer.

Under a correct VirtIO implementation that length must respect the descriptor.

Against a malicious or broken virtual device, however, the parser could be given a logical length larger than the real allocation.

This is a device-boundary hardening gap.

## Ethernet and IPv4 dispatch

The first protocol entry point is `net_rx_ethernet`.

It dispatches only:

- EtherType 0x0806 to ARP;
- EtherType 0x0800 to IPv4.

IPv4 dispatch then recognizes only protocol 17 (UDP) and protocol 6 (TCP).

There is no protocol registration framework.

Unknown EtherTypes and IPv4 protocol values are ignored.

## Static network configuration

The stack is compiled around QEMU's common user-network addresses:

```text
guest:   10.0.2.15
gateway: 10.0.2.2
DNS:     10.0.2.3
```

There is no DHCP client, route table, subnet configuration, interface list, or dynamically assigned address object.

Outbound UDP traffic always depends on one cached gateway MAC.

## ARP integration

ARP support serves two functions.

ChrisOS replies to ARP requests for 10.0.2.15.

It also learns one MAC address when an ARP reply claims sender protocol address 10.0.2.2.

That address is stored in `g_gw_mac` and guarded by `g_gw_mac_valid`.

There is no general neighbor table.

There is also no active ARP request/retry state machine in the inspected revision.

Client sends can therefore fail until gateway MAC state has been learned.

## Shared transmit buffer

The packet-building layer owns:

```text
static uint8_t g_tx[1600];
```

ARP, UDP, TCP, socket traffic, and project services can all build packets in this same array.

No allocator is used for normal network transmission.

This is efficient under serialized use but makes packet construction non-reentrant.

Two concurrent transmit callers can corrupt each other's packet contents.

## VirtIO transmit path

`virtio_net_tx` accepts Ethernet frames no larger than 1514 bytes.

It first drains previous TX completion, writes a zeroed ten-byte VirtIO header, copies the Ethernet frame into the driver's own TX page, configures descriptor zero, places it in the available ring, notifies queue 1, and drains completion again.

The device therefore DMA-reads the driver's private TX buffer, not `g_tx`.

After the copy, the protocol layer can reuse `g_tx`.

## Serial TX behavior

The TX implementation is intentionally single-buffered.

There is one TX physical buffer and descriptor zero is reused.

`virtio_drain_tx` spins while checking the used ring with a bound of 200000 iterations per invocation.

There is no multi-packet TX queue owned by the software stack and no asynchronous completion callback to an upper-layer packet object.

This reduces ownership complexity at the cost of throughput and concurrency.

## TX error propagation

`virtio_net_tx` returns success or failure.

However, `net_send_frame` discards that return value.

Some higher-level callers therefore report success after packet construction even when the device rejects transmission.

The mismatch is particularly visible for TCP: `net_tcp_xmit` allows a packet to fit the 1600-byte software buffer while the driver refuses Ethernet frames above 1514 bytes.

A robust stack should propagate link-layer failure upward.

## Poll loop

`net_poll` is the main progress engine.

When networking is ready it executes, in order:

1. `virtio_net_poll()`;
2. `sock_tick()`;
3. `host_rebuild_tick()`.

The driver poll reads the ISR byte, processes all completed RX descriptors, and drains TX completion.

Socket timers and host-rebuild workflow therefore advance only when this poll function runs.

The stack does not rely on a dedicated networking kernel thread.

## IRQ versus polling

The VirtIO driver exposes an ISR register and reads it, but packet protocol processing is performed from `virtio_net_poll`.

There is no separate receive worker queue between device completion and protocol parsing in this path.

This means the effective execution context of Ethernet/IP/TCP handling is the caller of `net_poll`.

That simplifies synchronization but can also make packet work visible as latency in whatever loop performs polling.

## Built-in UDP behavior

UDP port 7 is handled directly in `net.c` as an echo service.

Other UDP destinations can be handed to `sock_on_udp`.

`net_udp_send` limits payloads to 1400 bytes and uses the cached gateway MAC.

The generated UDP checksum is zero, which is permitted for IPv4 UDP but provides no transport checksum validation for those outgoing datagrams.

The dedicated UDP chapter documents wire details and receive validation.

## Built-in TCP behavior

`net.c` also contains a separate single-connection TCP echo state structure named `g_tcp`.

Port 7 uses this built-in path after project transfer and socket dispatch have had a chance to consume the packet.

The state records remote MAC, IPv4 address, remote port, send-next, and receive-next values.

This is independent of the socket table.

Consequently, ChrisOS currently has more than one small TCP state machine rather than one unified transport engine.

## Dispatch order for TCP

Incoming TCP follows this effective service order:

1. port 9016 is sent to `net_xfer_tcp`;
2. `sock_on_tcp` is asked to consume packets matching socket state;
3. remaining packets to port 7 go to the built-in echo connection;
4. other TCP traffic is ignored.

This ordering matters because the project transfer service has priority over the generic socket table for its dedicated port.

## Socket table

`sock.c` declares:

```text
SOCK_MAX = 16
SOCK_RX  = 2048
```

Index zero is not allocated by `alloc_sk`, so there are at most fifteen usable descriptors.

Socket states are:

- FREE;
- LISTEN;
- SYN_SENT;
- ESTABLISHED.

There is no complete TCP state graph such as SYN_RECEIVED, FIN_WAIT, TIME_WAIT, or CLOSE_WAIT.

## Socket ownership

Each socket records both:

- native process owner PID;
- optional CLVM application slot.

Visibility rules depend on caller type.

For a CLVM caller, the socket's slot must match.

For a native process, the socket must have a negative slot and owner equal to `proc_current()`.

Cleanup helpers can close every socket belonging to a process or CLVM slot.

This ownership model prevents ordinary callers from using arbitrary live descriptors from other applications.

## Listening and accept semantics

`sock_listen_for` allocates a descriptor and changes it to LISTEN.

When an incoming SYN matches that port, `sock_on_tcp` allocates a child, immediately marks the child ESTABLISHED, records the listener as parent, and sends SYN+ACK.

There is no explicit SYN_RECEIVED state.

`sock_accept` can return a child whose parent field still references the listener.

Therefore the implementation treats the connection as established earlier than a complete RFC TCP three-way handshake state machine would.

## Outbound connect

`sock_connect` allocates a socket, sets SYN_SENT, chooses an ephemeral local port starting at 40000, seeds the initial sequence value from `pit_ticks() * 2654435761`, and sends SYN.

If a gateway MAC has already been learned, it is copied into the socket.

When SYN+ACK arrives, the socket records remote MAC, advances receive-next, changes to ESTABLISHED, and transmits ACK.

## SYN retry

`sock_tick` scans all sockets.

For a socket still in SYN_SENT, if more than 30 ticks have passed since the last transmit, the SYN is resent using the original sequence number.

There is no retry-count limit, exponential backoff, connection timeout, or failure notification implemented in this loop.

Only SYN retransmission is performed here; ordinary data segments are not retransmitted by `sock_tick`.

## Socket send and receive

`sock_send` requires ESTABLISHED state and caps one call to 200 payload bytes.

The payload is sent with ACK|PSH.

Each socket has a 2048-byte receive array.

`sock_recv` copies bytes to the caller and compacts remaining bytes toward the front of that array.

There is no scatter/gather or packet queue per socket.

## Receive-buffer pressure

When TCP payload arrives for a socket, the implementation computes remaining room and copies only what fits.

However, `rcv_nxt` is advanced by the full incoming payload length before truncation.

An ACK is then sent.

This means excess bytes can be discarded while the peer is effectively told they were received.

The current flow control is therefore not lossless under receive-buffer pressure.

## TCP ordering limitations

The socket receive path does not implement a reassembly queue for out-of-order segments.

It does not verify that an incoming segment's sequence number equals the expected `rcv_nxt` before copying payload.

It simply sets:

```text
rcv_nxt = seq + payload_length
```

for accepted data.

There is no duplicate-segment suppression, selective acknowledgment, congestion control, advertised receive-window management, or retransmission of application data.

The current socket TCP path should be described as a small transport state machine, not full TCP.

## UDP socket path

`sock_on_udp` only considers destination ports 40000 and above.

It searches for a LISTEN socket with the same local port and an empty receive buffer.

The UDP payload is copied into that socket's 2048-byte RX array, capped at the array size.

The function does not use its received-frame-length argument for bounds validation before copying based on UDP length.

The direct UDP echo path validates more surrounding lengths than this socket path.

This is a concrete parser-hardening issue.

## DNS helper

`sock_dns` is a minimal DNS client built on UDP.

It uses server 10.0.2.3, constructs a fixed transaction ID of 0x1234, emits one A/IN question, and uses one persistent internally allocated socket.

Response parsing is intentionally simplistic: it scans raw response bytes for a type-A/class-IN pattern and reads four bytes at a fixed relative offset.

It is not a complete DNS message parser and does not robustly implement compression-pointer traversal or transaction matching.

## Host rebuild channel

`host_rebuild_tick` is another project-specific networking consumer.

When started, it connects to 10.0.2.2 port 9017, sends the eight bytes `rebuild\n`, waits for a reply beginning with 'O', then calls `machine_reboot()`.

Because it runs from `net_poll`, this workflow progresses through the same socket and timer machinery as other traffic.

## File-transfer service

`net_xfer.c` listens conceptually on TCP port 9016 through direct dispatch in `net.c`.

It implements one global transfer connection with phases:

- IDLE;
- HDR;
- PATH;
- DATA;
- DONE.

The application framing begins with a 12-byte CFS1 header carrying path length and file size, followed by path bytes and file bytes.

After complete reception, it writes the file through `fs_write` and returns one-byte ACK or error status.

This service bypasses the generic socket API.

## Transfer memory limits

The transfer path validates that path length is nonzero and below 512 bytes and that file size is nonzero and no larger than `CFS_MAX_FILE_SIZE`.

It allocates the incoming file buffer dynamically with `kmalloc`.

Only one global transfer is active at a time.

A new incoming SYN resets previous transfer state.

## Multiple transport state machines

There are three distinct TCP consumers in the current design:

1. built-in port-7 echo state in `net.c`;
2. generic socket table in `sock.c`;
3. file-transfer state in `net_xfer.c`.

They share packet builders and checksums but do not share one generalized TCP connection engine.

This is a central architectural fact of the current network stack.

Refactoring toward one TCP state machine would reduce duplicated sequence/length handling and make validation fixes apply uniformly.

## Concurrency and SMP

The stack contains many mutable globals:

- `g_vnet`;
- `g_tx`;
- gateway MAC state;
- built-in TCP state;
- socket table;
- ephemeral-port counter;
- DNS helper state;
- host-rebuild state;
- transfer state.

There is no general network lock around these structures.

The current design depends on effectively serialized polling and system-call use.

Arbitrary simultaneous AP receive/transmit/socket mutation would create data races.

The networking stack is not fully SMP-safe.

## Security boundary

Every RX packet originates outside the kernel trust boundary.

The current implementation has several strong local bounds checks, but validation is inconsistent across protocol consumers.

Known examples include:

- RX used length is not clamped against the 2048-byte posted descriptor;
- IPv4 checksum is not verified;
- IPv4 fragments are not rejected or reassembled;
- some TCP paths trust IPv4 total length more than physical frame length;
- UDP socket delivery does not use its frame-length argument when copying payload;
- ARP does not validate every format field;
- gateway ARP cache is unauthenticated.

These are implementation gaps, not merely missing features.

## Validation model

There is no single host-side unit-test suite that exhaustively feeds malformed packets through Ethernet, IPv4, UDP, TCP, and sockets.

Current evidence is largely integration-based:

- VirtIO-net initialization under QEMU;
- UDP/TCP echo behavior;
- socket and DNS consumers;
- host transfer on port 9016;
- rebuild channel on port 9017;
- host forwarding configured by the makefile.

Successful integration demonstrates the happy path but does not prove hostile-input safety.

## QEMU integration

The normal QEMU command uses VirtIO-net with user networking.

Host forwarding exposes guest services including port 7 and file-transfer port 9016.

This environment is the primary networking hardware/profile target for the current stack.

Support for this paravirtual device must not be generalized into support for arbitrary physical NICs.

## Performance characteristics

RX protocol processing is synchronous and mostly zero-copy.

TX performs one additional copy from the shared packet builder into the single VirtIO TX buffer.

Protocol lookups are small linear scans:

- up to fifteen usable sockets;
- one gateway entry;
- one transfer state;
- one built-in echo connection.

There are no large routing, neighbor, or connection hash tables.

The architecture favors small bounded structures over high-throughput networking.

## Recommended evolution

The highest-value structural improvements are:

1. centralize packet validation before transport dispatch;
2. clamp device completion lengths to posted buffers;
3. add active ARP resolution and a bounded neighbor table;
4. unify the three TCP state machines;
5. propagate TX failures;
6. add correct sequence/retransmission/window handling;
7. protect shared networking state or confine it to one explicit network execution context;
8. add deterministic malformed-packet tests and fuzzing;
9. separate DNS/application services from transport internals;
10. define a real route/interface model before expanding beyond QEMU user networking.

## Revision note

This chapter was reconciled against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. It describes the actual poll-driven VirtIO-net, protocol, socket, and project-service architecture, including the ownership and concurrency assumptions that make the current implementation work.
