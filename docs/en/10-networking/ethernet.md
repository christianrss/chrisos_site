---
id: ethernet
lang: en
type: technical-chapter
volume: 10-networking
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/net/net.c
  - kernel/net/net.h
  - kernel/net/virtio_net.c
  - kernel/net/virtio_net.h
  - makefile
symbols:
  - eth_build
  - net_rx_ethernet
  - net_arp
  - net_send_arp_reply
  - net_send_frame
  - net_init
  - virtio_process_rx
  - virtio_net_tx
depends_on: []
related:
  - ipv4
  - virtio-net
  - network-stack
---

# Ethernet framing

## Scope

Ethernet is the link-layer format used by the current ChrisOS network stack.

ChrisOS does not implement a general physical Ethernet controller in this path. The active device is the legacy VirtIO-net PCI interface used under QEMU, but the network layer receives and emits ordinary Ethernet frame bytes after the VirtIO-specific 10-byte packet header is removed or inserted by the driver.

The architectural boundary is:

    VirtIO RX descriptor
       -> 10-byte virtio-net header
       -> Ethernet frame
       -> EtherType dispatch
       -> ARP or IPv4

and on transmit:

    ARP / IPv4 packet builder
       -> Ethernet header
       -> complete L2 frame
       -> virtio_net_tx()
       -> 10-byte virtio-net header
       -> VirtIO TX queue

This chapter focuses on that Ethernet boundary rather than the IPv4, UDP, TCP, socket, or VirtIO queue internals documented elsewhere.

## Ethernet II header

The current stack assumes a 14-byte Ethernet II header:

| Offset | Size | Meaning |
|---|---:|---|
| 0 | 6 | destination MAC |
| 6 | 6 | source MAC |
| 12 | 2 | EtherType, big-endian |
| 14 | variable | payload |

`ETH_HDR_LEN` is defined as 14.

`net_rx_ethernet` refuses a frame shorter than 14 bytes and reads the EtherType from bytes 12 and 13.

There is no 802.1Q VLAN-tag parser and no 802.3 length/LLC path in this revision.

## MAC addresses

MAC addresses are represented as six raw bytes.

The local address is not hard-coded by the network layer. `virtio_net_init` reads six bytes from the VirtIO device configuration and `virtio_net_mac` exposes the resulting array.

Outgoing Ethernet headers therefore combine:

- destination MAC selected by the protocol path;
- source MAC returned by `virtio_net_mac`;
- a two-byte EtherType.

The current networking code does not provide a separate MAC-address type.

## Header construction

`eth_build` writes the complete 14-byte header.

It copies exactly six destination bytes and six source bytes, then writes the EtherType with `write_be16`.

The function does not allocate memory and does not validate its pointers. Its callers pass storage inside the static transmit buffer.

Its work is constant-time: twelve byte copies plus one 16-bit write.

## Network byte order

EtherType is encoded in big-endian order.

The network stack uses small helpers such as `read_be16`, `read_be32`, `write_be16`, and `write_be32` rather than depending on libc byte-order routines.

For Ethernet, the important field is:

    frame[12] = EtherType high byte
    frame[13] = EtherType low byte

The same explicit byte-order policy is reused by IPv4 and transport headers.

## Receive entry point

The link-layer parser is:

    net_rx_ethernet(const uint8_t *frame, uint32_t len)

It first requires:

- network stack ready;
- non-null frame pointer;
- length at least 14.

It then reads the EtherType and dispatches only two values:

    0x0806 -> ARP
    0x0800 -> IPv4

Every other EtherType is silently ignored.

There is no default diagnostic or protocol registration table.

## Destination-MAC filtering

`net_rx_ethernet` does not inspect bytes 0..5 before dispatch.

It therefore relies on the network device/backend to decide which unicast, broadcast, or other frames are delivered to the guest.

Once a frame reaches this function, protocol dispatch is based only on EtherType.

This is an important separation: the current software stack is not itself enforcing "destination MAC must be ours" at the Ethernet parser.

## VirtIO receive boundary

VirtIO-net RX buffers include a 10-byte `virtio_net_hdr` before the Ethernet bytes.

`virtio_process_rx` receives a used descriptor, obtains its buffer, and calls:

    net_rx_ethernet(buf + 10, total_len - 10)

when the reported length exceeds the 10-byte VirtIO header.

The Ethernet parser therefore never sees the VirtIO header.

This keeps device transport format separate from the L2 parser.

## RX buffer ownership

Eight receive descriptors are provisioned by the current VirtIO driver.

Each descriptor owns a 2048-byte receive buffer.

The important lifetime rule is synchronous:

1. VirtIO marks one RX descriptor used.
2. The driver points `net_rx_ethernet` directly into that descriptor's buffer.
3. All Ethernet/ARP/IP processing runs before the call returns.
4. Only after return does `rx_repost` give the descriptor back to the device.

Upper layers must therefore not retain the frame pointer after receive processing returns.

Current paths copy persistent values such as gateway MAC bytes instead of storing pointers into RX buffers.

## RX copy behavior

There is no additional Ethernet-frame copy between VirtIO RX and `net_rx_ethernet`.

The parser operates directly on the posted receive buffer after the 10-byte transport header.

This reduces per-packet copy cost.

The trade-off is the strict buffer-lifetime rule described above.

## RX length trust boundary

The driver receives `elem.len` from the VirtIO used ring.

It checks that the descriptor ID is one of the eight RX descriptors and that the total length is larger than the VirtIO header.

It does not explicitly clamp the reported used length to the 2048-byte posted buffer before passing the logical frame length upward.

With the expected QEMU/VirtIO device this follows the device contract, but a malicious or defective device reporting an impossible length would weaken the safety assumptions of upper parsing.

A hardened driver should verify the completion length against the posted descriptor capacity.

## Transmit frame buffer

The network layer owns one global transmit array:

    static uint8_t g_tx[1600];

ARP, UDP, and TCP builders all use this same storage.

Ethernet headers are written at offset zero.

Higher-layer headers and payload follow immediately.

This design avoids allocation on packet transmit, but it makes transmit construction non-reentrant.

## Driver transmit limit

`virtio_net_tx` accepts Ethernet frame lengths from 1 through 1514 bytes.

The maximum corresponds to:

    14-byte Ethernet header
    + 1500-byte payload

without an FCS in the supplied software buffer.

The driver prepends its separate 10-byte VirtIO network header before posting the packet to the TX queue.

Jumbo frames are not supported by this path.

## TX copy and ownership

The network layer passes its `g_tx` pointer to `virtio_net_tx`.

The VirtIO driver copies the full Ethernet frame into its own single TX buffer after the 10-byte VirtIO header.

Therefore the link/network layer regains ownership of `g_tx` when the call returns; the device is not DMA-reading directly from `g_tx`.

The driver uses descriptor zero and drains TX completion around submission.

This is simple but intentionally serial.

## Error propagation gap

`net_send_frame` calls `virtio_net_tx` and discards its return value.

ARP reply generation and several higher-layer transmit paths therefore do not receive explicit feedback if the link-layer driver rejects the frame.

For example, a device-not-ready condition can cause `virtio_net_tx` to return zero while the caller continues without an error code.

A future network interface should propagate TX completion/failure status upward.

## FCS and padding

ChrisOS builds the MAC header and network payload only.

It does not append a four-byte Ethernet frame check sequence in `eth_build` or `virtio_net_tx`.

It also does not explicitly pad a short frame to the traditional Ethernet minimum.

The current ARP reply is exactly 42 bytes:

    14-byte Ethernet header
    + 28-byte ARP payload

before the VirtIO transport header.

This works within the current virtual-device environment, where lower layers handle the actual link transmission representation.

It should not be generalized into a claim that ChrisOS currently implements physical-wire Ethernet framing, preamble, inter-packet gap, padding, or FCS generation.

## ARP as the first Ethernet consumer

EtherType 0x0806 is sent to `net_arp`.

The current ARP implementation is deliberately small.

It handles:

- opcode 1: request;
- opcode 2: reply.

The receive function requires at least 42 bytes, matching an Ethernet header plus the common 28-byte Ethernet/IPv4 ARP payload.

## ARP request handling

For an ARP request, `net_send_arp_reply` extracts:

- sender hardware address at frame offset 22;
- sender protocol address at offset 28;
- target protocol address at offset 38.

It replies only when the target protocol address equals the fixed ChrisOS IPv4 address.

The response uses:

    EtherType      = 0x0806
    hardware type  = 1
    protocol type  = 0x0800
    hardware size  = 6
    protocol size  = 4
    operation      = 2

The destination Ethernet MAC is the requester's sender MAC.

## ARP validation limits

The receive path does not currently validate all ARP header fields before using fixed offsets.

It checks packet length and operation, but it does not first require the incoming hardware type, protocol type, HLEN, and PLEN to equal the Ethernet/IPv4 values expected by those offsets.

A malformed 42-byte ARP packet can therefore be interpreted according to the expected layout even when its metadata describes something else.

This is a parser-hardening gap.

## Static IPv4 configuration

The Ethernet/ARP behavior is coupled to a fixed IPv4 environment:

    guest IP = 10.0.2.15
    gateway  = 10.0.2.2

These values match the QEMU user-network configuration assumed by the project.

There is no DHCP configuration path in `net.c`.

`net_status` reports the VirtIO MAC plus the fixed 10.0.2.15 address.

## Gateway MAC cache

ChrisOS does not maintain a general ARP neighbor table.

It has exactly one six-byte cache:

    g_gw_mac[6]

plus:

    g_gw_mac_valid

An incoming ARP reply updates this cache only when the sender protocol address is exactly 10.0.2.2, the configured gateway.

Other ARP replies do not become reusable neighbor entries.

## No active ARP-request builder

In the inspected revision, `net.c` contains an ARP reply builder but no general function that emits an ARP request for an unresolved destination or gateway.

Outbound helpers such as `net_udp_send` require `g_gw_mac_valid` and fail when the gateway MAC has not yet been learned.

The implementation therefore lacks a normal active neighbor-resolution state machine with request, retry, timeout, and cache aging.

This is one of the largest functional limitations of the current L2/L3 boundary.

## ARP cache security

The gateway cache is unauthenticated.

Any delivered ARP reply whose sender protocol address equals 10.0.2.2 can replace `g_gw_mac`.

There is no pending-request correlation, expiry time, duplicate-address detection, trust policy, or ARP-spoofing defense.

This is acceptable for the current experimental QEMU environment but not a hardened LAN design.

## IPv4 handoff

EtherType 0x0800 is passed to `net_ipv4`.

Ethernet does not inspect IP destination, checksum, fragmentation, or protocol fields.

Those are network-layer responsibilities.

The current layering is therefore explicit at dispatch time even though all functions happen to live in `net.c`.

The IPv4 chapter documents the next boundary.

## Concurrency model

Ethernet and packet construction currently use global mutable state:

- one global `g_tx` buffer;
- one gateway MAC cache;
- one global network-ready flag;
- one global VirtIO-net device instance;
- one driver TX buffer.

There is no link-layer lock around packet construction or gateway-cache mutation.

The current design assumes serialized/poll-driven use.

Concurrent AP transmitters could overwrite `g_tx` while another packet is being built.

This stack must not be described as generally SMP-safe.

## Polling model

`net_poll` calls `virtio_net_poll`.

The VirtIO driver acknowledges/reads the ISR byte, processes all completed RX descriptors, and drains TX.

Receive protocol handling occurs synchronously from that poll path rather than being queued into a separate Ethernet worker.

This keeps ownership simple but means parsing and responses execute in the caller's polling context.

## Complexity

Ethernet dispatch itself is O(1): one minimum-length check, one big-endian field read, and a small EtherType branch.

Header construction is O(1).

Transmit has O(frame length) copy cost because the driver copies the Ethernet frame from `g_tx` into its own TX buffer.

RX Ethernet dispatch adds no payload copy.

ARP reply construction is O(1) with fixed-size fields.

The current design therefore favors minimal code and predictable small costs over generality.

## QEMU integration

The project run configuration attaches:

    -device virtio-net-pci,netdev=n0

with QEMU user networking.

Host forwarding maps host UDP/TCP port 7007 to guest port 7, and host TCP port 9016 to guest port 9016.

These routes exercise the same Ethernet/VirtIO receive and transmit boundaries indirectly through higher protocols.

They are integration infrastructure, not a dedicated Ethernet parser unit test.

## Validation evidence

There is no standalone `test_ethernet.c`, `test_arp.c`, or equivalent host unit test in the inspected tree.

Current evidence consists of:

- successful VirtIO-net initialization logs;
- network-stack boot/use under QEMU user networking;
- echo and transfer paths that depend on valid RX/TX Ethernet framing;
- source-level bounds checks in the parser.

That evidence does not exhaust malformed-frame cases.

A dedicated deterministic L2 test suite remains necessary.

## Recommended tests

Useful tests should construct raw byte arrays and verify:

- frames shorter than 14 are rejected;
- unknown EtherTypes are ignored;
- 0x0806 dispatches ARP and 0x0800 dispatches IPv4;
- header construction produces exact destination/source/EtherType bytes;
- ARP request to 10.0.2.15 yields the expected 42-byte reply;
- ARP request for another IP yields no reply;
- malformed HLEN/PLEN/type fields are rejected after parser hardening;
- gateway cache updates only for the intended gateway;
- TX failure propagates to callers;
- reported VirtIO RX length cannot exceed the posted buffer.

Concurrency tests should also prove or explicitly reject simultaneous transmitters.

## Current limitations

The link layer supports only untagged Ethernet II frames carrying ARP or IPv4.

There is no VLAN, IPv6 EtherType path, LLC/SNAP parser, jumbo frame, multicast-management API, general neighbor table, DHCP integration, active ARP resolution, cache expiry, or L2 authentication.

Physical Ethernet FCS/padding/preamble are not implemented by this software layer.

The implementation is tightly aligned with the current QEMU VirtIO-net environment.

## Revision note

This chapter was created against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. It documents the current Ethernet byte format, ownership boundaries, ARP behavior, transmit/receive constraints, and validation gaps without treating the VirtIO transport as part of the Ethernet protocol itself.
