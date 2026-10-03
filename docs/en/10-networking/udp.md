---
id: udp
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
  - makefile
symbols:
  - net_udp_echo
  - net_udp_send
  - sock_on_udp
  - sock_dns
depends_on:
  - ethernet
  - ipv4
related:
  - network-stack
  - tcp
  - sockets
---

# UDP

## Scope

ChrisOS implements a small IPv4 UDP path for three primary uses:

- built-in UDP echo on port 7;
- one-shot datagram delivery into the project socket table;
- outbound datagrams used by helpers such as the DNS client.

The implementation is intentionally minimal.

It does not provide a full datagram socket API with peer addressing, packet queues, checksum verification, multicast, broadcast policy, or protocol-independent demultiplexing.

The receive path is:

```text
Ethernet 0x0800
    |
    v
IPv4 protocol 17
    |
    v
net_udp_echo()
    |
    +-- destination port 7 --> echo reply
    |
    +-- other port --> sock_on_udp()
```

Transmit uses `net_udp_send`, which constructs Ethernet, IPv4, and UDP headers directly in the shared packet buffer.

## UDP header

The UDP header is eight bytes:

| Offset | Size | Meaning |
|---|---:|---|
| 0 | 2 | source port |
| 2 | 2 | destination port |
| 4 | 2 | UDP length |
| 6 | 2 | checksum |

All integer fields are big-endian.

The length includes both the eight-byte UDP header and payload.

## Receive entry

IPv4 dispatch calls `net_udp_echo` when protocol byte 9 is 17.

The function requires at least 42 received bytes, enough for:

```text
14 Ethernet
20 minimum IPv4
 8 UDP
```

It then checks that IPv4 version is 4 and recomputes IHL from the packet.

IHL must be at least 20 bytes and the physical frame must contain Ethernet + IHL + a complete UDP header.

## Local-destination check

Before UDP port dispatch, the receive path requires the IPv4 destination to match the fixed ChrisOS address 10.0.2.15.

This is important because the generic IPv4 dispatcher itself does not enforce destination address.

UDP therefore performs its own local-address check.

There is no UDP behavior for IPv4 broadcast or multicast destinations.

## Port 7 echo

Destination UDP port 7 is reserved by the built-in echo service.

For that path, `net_udp_echo` reads:

- source port from UDP offset 0;
- destination port from UDP offset 2;
- length from offset 4.

The reply swaps source/destination ports, replies to the source IPv4 address, and uses the source Ethernet MAC as destination.

Payload bytes are copied unchanged.

The result is a conventional UDP echo response for well-formed input.

## Echo receive bounds

The echo path requires UDP length to be at least eight.

Payload offset is:

```text
14 + IHL + 8
```

and payload length is:

```text
UDP length - 8
```

Two physical-frame checks are then made:

```text
14 + IPv4 total_length <= received frame length
payload_offset + payload_length <= received frame length
```

These checks prevent the echo path from copying beyond the bytes physically delivered by the driver.

## Cross-layer length inconsistency

The direct echo path does not require strict equality between IPv4 total length and UDP length.

It does not enforce:

```text
IPv4 total_length == IHL + UDP length
```

A malformed packet can therefore contain inconsistent cross-layer lengths and still be accepted if both independent physical-frame bounds happen to pass.

A stronger validator should normalize and compare all three quantities:

- physical frame bytes;
- IPv4 total length;
- UDP length.

## UDP checksum on transmit

Both UDP transmit paths write zero into the checksum field.

That includes:

- built-in echo replies;
- `net_udp_send`.

For IPv4 UDP, a zero checksum means that the UDP checksum is omitted.

This is legal for IPv4 but provides no end-to-end UDP corruption detection.

ChrisOS currently has no UDP pseudo-header checksum generator.

## UDP checksum on receive

Incoming UDP checksum is not validated.

A nonzero checksum field is ignored.

A zero checksum is also accepted.

The stack therefore relies on lower-layer/device integrity and whatever protection exists outside this UDP implementation.

A hardened implementation should compute the pseudo-header checksum whenever the incoming field is nonzero.

## Outbound API

The public low-level transmit function is:

```text
net_udp_send(dst_ip, src_port, dst_port, payload, payload_len)
```

It returns -1 when:

- networking is not ready;
- destination IP pointer is null;
- payload exceeds 1400 bytes;
- gateway MAC has not been learned.

Otherwise it builds one datagram and returns the requested payload length.

## Payload-pointer contract

`net_udp_send` checks the destination-IP pointer but does not check `payload` when `payload_len > 0`.

The copy loop dereferences the pointer directly.

A caller passing a null payload with nonzero length can therefore fault in kernel context.

The API should explicitly require either zero length or non-null payload.

## Size budget

The maximum accepted application payload is 1400 bytes.

The resulting generated sizes are:

```text
UDP:       8 + 1400 = 1408
IPv4:     20 + 1408 = 1428
Ethernet: 14 + 1428 = 1442
```

This stays below the VirtIO driver's 1514-byte Ethernet frame ceiling.

Unlike the current raw TCP transmit helper, UDP therefore maintains a conservative margin below the actual link limit.

## Gateway routing

Every `net_udp_send` transmission uses the one cached gateway MAC.

The destination IPv4 address may be arbitrary, but Ethernet destination does not change based on local-subnet detection.

There is no route table or subnet mask calculation.

The network assumes the simple QEMU topology documented in the network-stack chapter.

## Gateway-resolution dependency

If the gateway MAC has not been learned from ARP, `net_udp_send` returns -1.

There is no active ARP request performed automatically by UDP.

The datagram is not queued while resolution occurs.

This creates a strong hidden precondition for DNS and other client-side UDP traffic.

## TX success-reporting gap

After the packet is built, `net_udp_send` calls the void `net_send_frame`.

That wrapper discards the success/failure result of `virtio_net_tx`.

The function then returns the payload length.

Thus a positive return means "packet construction reached the send call", not guaranteed device transmission.

This distinction matters for application retry/error handling.

## Non-echo receive dispatch

When a UDP packet is not addressed to port 7, `net_udp_echo` calls:

```text
sock_on_udp(frame, n)
```

and returns immediately.

There is no other UDP service registry.

The socket path therefore owns all non-echo UDP handling.

## Socket model is protocol-ambiguous

The `Sock` structure contains no transport-protocol field.

A LISTEN socket is identified only by state and local port.

The same LISTEN state is also used by TCP accept logic.

The current socket abstraction therefore does not explicitly distinguish "UDP socket" from "TCP listening socket".

This is a structural limitation of the API rather than only a parser issue.

## Critical port-offset bug

The current `sock_on_udp` implementation contains a concrete demultiplexing bug.

It assigns:

```text
dport = be16(udp + 0)
```

but UDP offset zero is the **source port**.

The destination port is at offset two.

The function then uses this misread value to:

- reject ports below 40000;
- find a LISTEN socket whose local port equals that value.

Thus it is matching the remote source port against the local listener port.

## DNS consequence

The DNS helper allocates an ephemeral local port at 40000 or above and sends a query to server port 53.

A normal DNS response has:

```text
source port      = 53
destination port = ephemeral local port
```

Because `sock_on_udp` reads offset zero, it sees 53, rejects it as below 40000, and does not deliver the response to the DNS socket.

Under the inspected revision, this means the intended UDP socket/DNS receive path is broken for normal DNS replies.

The correct first repair is to read destination port from `udp + 2`.

## Socket UDP length bug

`sock_on_udp` accepts a frame-length argument but explicitly discards it:

```text
(void)n;
```

It computes payload length solely from the UDP length field and then copies that many bytes, capped only by the 2048-byte socket RX capacity.

Although the caller has ensured that at least the UDP header physically exists, the payload length can still claim more bytes than the received frame contains.

This can produce an out-of-bounds read from the RX descriptor.

It is a memory-safety hardening issue.

## Socket delivery semantics

For a matching LISTEN socket, UDP payload is copied only when:

```text
socket.rx_len == 0
```

If unread data is already present, the new datagram is not queued.

There is no datagram ring or multi-message receive queue.

This means back-to-back packets can be dropped simply because the application has not consumed the previous receive buffer.

## Datagram boundaries

The socket RX array stores only payload bytes and one length.

It does not preserve:

- source IPv4 address;
- source port;
- destination address;
- per-datagram metadata.

Because only one datagram is stored, boundaries are implicitly represented by `rx_len`, but after generic `sock_recv` partially reads and compacts the buffer the API behaves more like a byte stream than a datagram API.

This is not conventional UDP socket semantics.

## Maximum socket delivery

`SOCK_RX` is 2048 bytes.

`sock_on_udp` caps copied data to that size.

For valid Ethernet/IPv4 UDP packets under the current link MTU, the payload should already be smaller than this.

The 2048 cap therefore mostly limits malformed length fields or future larger transports rather than normal 1500-byte Ethernet operation.

## Process wakeup

When a UDP payload is copied into a socket and that socket has a positive native process owner, `proc_unblock(owner)` is called.

This integrates network arrival with process blocking/wakeup.

CLVM slot ownership is stored too, but the receive helper only directly calls `proc_unblock` for a positive process owner.

The higher-level CLVM integration depends on its own calling/blocking model.

## DNS query construction

`sock_dns` creates a small DNS query in a 128-byte local buffer.

It uses:

```text
transaction ID = 0x1234
flags          = 0x0100
QDCOUNT        = 1
QTYPE          = A
QCLASS         = IN
server         = 10.0.2.3:53
```

Labels are encoded directly from the hostname.

The source local port comes from the global ephemeral counter.

## DNS parser limitations

Even after fixing UDP demultiplexing, the DNS response parser is deliberately simplistic.

It scans response bytes starting at offset 12 looking for the sequence representing type A and class IN.

It then assumes RDLENGTH/data are at a fixed relative position and reads four address bytes.

It does not robustly:

- match transaction ID;
- walk DNS names with compression pointers;
- distinguish question records from answers with a real message parser;
- validate response flags/counts thoroughly.

DNS should be treated as a project helper, not a complete resolver.

## Ephemeral ports

The global ephemeral counter begins at 40000.

The same counter is used by TCP connect and by the internal DNS UDP listener.

After 65535 wraps, code resets values below 40000 back to 40000.

There is no collision search before assigning an ephemeral port.

A newly allocated socket can therefore theoretically reuse a port already active in another socket.

## No UDP retransmission

UDP itself has no retransmission state in ChrisOS.

`net_udp_send` builds one packet and returns.

DNS does not implement a timeout/retry loop in the inspected helper.

Loss of a datagram therefore requires the calling logic to retry explicitly; the current DNS helper does not provide a robust retry policy.

## No bind/connect UDP API

The public socket header exposes generic listen/connect/send/recv operations rather than a UDP-specific bind/sendto/recvfrom interface.

UDP receive is wired into LISTEN sockets with high ports, while `net_udp_send` is the low-level explicit-address send helper.

There is no `sendto` carrying source metadata through a socket object and no `recvfrom` returning peer identity.

## Concurrency

UDP shares the global `g_tx[1600]` packet builder with ARP and TCP.

The socket table is also global.

There is no UDP-specific lock.

Concurrent transmitters can corrupt packet construction, and concurrent receive/socket operations can race on `rx_len` and payload bytes.

Normal operation relies on the serialized polling/system-call model described in the network-stack chapter.

## Security priorities

The highest-priority UDP fixes are concrete:

1. correct destination-port parsing in `sock_on_udp`;
2. validate UDP length against physical frame length and IPv4 total length;
3. reject UDP length smaller than eight before any payload access;
4. validate checksum when nonzero;
5. require non-null payload for nonzero transmit length;
6. return actual link-layer transmit status;
7. preserve datagram boundaries and source metadata in the socket API;
8. add a bounded receive queue instead of one overwrite-sensitive buffer.

## Validation evidence

There is no dedicated `test_udp.c` in the inspected source tree.

The built-in port-7 echo path and QEMU port forwarding provide end-to-end happy-path evidence.

The DNS helper intends to exercise client-side UDP, but the current source-port/destination-port bug prevents it from serving as valid evidence of successful socket UDP demultiplexing.

A source-grounded documentation corpus should distinguish these two facts.

## Recommended tests

A deterministic UDP suite should include:

- minimum eight-byte datagram;
- zero-byte payload;
- exact source/destination port decoding;
- port-7 echo with payload;
- checksum zero acceptance on IPv4;
- valid nonzero checksum after checksum support is added;
- UDP length below eight;
- UDP length beyond physical frame;
- UDP length beyond IPv4 total length;
- extra Ethernet padding after IPv4 total length;
- listener delivery to destination ephemeral port;
- DNS response from source port 53 to destination 40000+;
- datagram arrival while previous payload is unread;
- null payload with nonzero send length;
- gateway MAC unavailable;
- device TX failure propagation.

## Current limitations

UDP is currently a narrow IPv4-only datagram path.

There is no UDP checksum generation or verification, IPv6 UDP, datagram queue, multicast API, broadcast policy, source-address metadata, sendto/recvfrom API, or general interface/routing selection.

The built-in echo path is more robust than the socket UDP path.

The socket demultiplexing offset bug and missing physical-length validation are correctness issues in the inspected revision, not merely future enhancements.

## Revision note

This chapter was created against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. It documents both the functional port-7 UDP path and the currently broken generic socket/DNS demultiplexing path, including the exact source-port/destination-port offset error and receive-bounds gap.
