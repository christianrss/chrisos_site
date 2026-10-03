---
id: ipv4
lang: en
type: technical-chapter
volume: 10-networking
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/net/net.c
  - kernel/net/net.h
  - kernel/net/sock.c
  - kernel/net/net_xfer.c
  - makefile
symbols:
  - ip_build
  - ip_checksum
  - csum16
  - net_ipv4
  - net_udp_send
  - net_tcp_xmit
depends_on:
  - ethernet
related:
  - udp
  - tcp
  - sockets
  - network-stack
---

# IPv4 and addressing

## Scope

ChrisOS implements a compact IPv4 layer sufficient for the current QEMU VirtIO-net environment.

The stack can:

- build IPv4 headers for UDP and TCP;
- compute an IPv4 header checksum;
- dispatch received IPv4 packets to UDP or TCP;
- recognize packets addressed to the fixed local IPv4 address;
- use one learned gateway MAC for outbound traffic.

It does not implement a general routing table, DHCP, IPv4 fragmentation/reassembly, ICMP, path-MTU discovery, multicast management, or a full neighbor-resolution subsystem.

The current data path is:

    Ethernet EtherType 0x0800
            |
            v
        net_ipv4()
        /        \
       v          v
     UDP          TCP

On transmit:

    UDP/TCP builder
         |
         v
      ip_build()
         |
         v
    Ethernet frame
         |
         v
    VirtIO-net TX

## Fixed addressing

The local IPv4 address is compiled into `net.c`:

    10.0.2.15

The configured gateway is:

    10.0.2.2

These values match the QEMU user-network environment used by the project.

There is no DHCP client and no runtime interface configuration in this layer.

`net_our_ip` returns the static four-byte local address.

## IPv4 header layout

The transmit builder always emits a 20-byte IPv4 header with no options.

The layout is:

| Offset | Size | Field |
|---|---:|---|
| 0 | 1 | version + IHL |
| 1 | 1 | DSCP/ECN |
| 2 | 2 | total length |
| 4 | 2 | identification |
| 6 | 2 | flags + fragment offset |
| 8 | 1 | TTL |
| 9 | 1 | protocol |
| 10 | 2 | header checksum |
| 12 | 4 | source address |
| 16 | 4 | destination address |

`ip_build` writes all of these fields explicitly.

## Version and IHL

Transmit byte zero is:

    0x45

The high nibble 4 identifies IPv4.

The low nibble 5 means five 32-bit words, or 20 bytes.

ChrisOS therefore never generates IPv4 options.

On receive, UDP and TCP paths compute:

    ihl = (ip[0] & 0x0F) * 4

and require `ihl >= 20`.

Packets with larger IHL values are structurally skipped over, but the option bytes are not interpreted.

## DSCP and ECN

Transmit byte one is always zero.

No differentiated-services or explicit-congestion-notification policy is implemented.

Received DSCP/ECN bits are ignored.

## Total length

`ip_build` writes the caller-provided total IPv4 length into bytes 2..3 in big-endian order.

For a normal generated packet:

    total_length = 20-byte IPv4 header + transport header + payload

UDP and TCP callers compute that value before calling `ip_build`.

The field is 16-bit, but actual packet sizes are constrained much earlier by the Ethernet and static-buffer limits.

## Identification field

The transmit identification field is:

    pit_ticks() & 0xFFFF

It is therefore derived from the low 16 bits of the system tick count.

Packets created within the same tick may receive the same identification value.

Because transmit packets are marked Don't Fragment, the current stack does not rely on this field for local reassembly.

It should not be interpreted as a globally unique packet identifier.

## Flags and fragment offset

The transmit builder writes:

    ip[6] = 0x40
    ip[7] = 0x00

This represents the IPv4 Don't Fragment flag with fragment offset zero.

ChrisOS therefore sends only unfragmented IPv4 datagrams and asks the network not to fragment them.

There is no local transmit fragmentation fallback.

## Fragment receive gap

The receive path does not reject fragmented IPv4 packets.

It does not inspect the More Fragments bit or fragment offset before passing payload bytes to UDP or TCP parsing.

This is an important correctness and security limitation.

A non-initial fragment does not begin with a transport header, but the current transport parser may still interpret its first bytes as UDP/TCP fields.

ChrisOS currently has no fragment reassembly table, timeout, overlap policy, or duplicate-fragment handling.

A hardened implementation should either:

1. reject all fragmented packets explicitly; or
2. implement validated reassembly before transport dispatch.

## TTL

Transmit TTL is fixed at:

    64

Received TTL is not validated or decremented because ChrisOS is not acting as an IPv4 router in this path.

There is also no ICMP Time Exceeded generation.

## Protocol field

The current stack recognizes:

    17 -> UDP
     6 -> TCP

`net_ipv4` reads byte 9 and dispatches only these two protocol numbers.

Other protocol values are silently ignored.

There is no ICMP protocol handler.

## Source and destination addresses

`ip_build` copies four source bytes and four destination bytes into the header.

Normal outgoing packets use the fixed local source address.

Received UDP/TCP handlers require the destination address to equal 10.0.2.15 before handling their built-in service paths.

Source addresses are accepted as supplied by the received packet and are later used for responses.

## Destination validation location

`net_ipv4` itself does not check the destination address.

The UDP and TCP handlers perform `ip_is_us(ip + 16)`.

This means destination validation is currently distributed across transport handlers rather than centralized in the IPv4 entry point.

Future protocols added to `net_ipv4` must remember to perform equivalent validation unless the check is moved into the IPv4 layer.

## Internet checksum

ChrisOS computes the standard one's-complement style IPv4 header checksum.

`csum16`:

1. reads data in 16-bit big-endian words;
2. adds them into a 32-bit accumulator;
3. if one byte remains, places it in the high byte;
4. folds carry bits back into the low 16 bits;
5. returns the one's complement.

For IPv4 transmit, `ip_checksum` first writes zero into header bytes 10 and 11, then computes over the header length.

The generated path always passes 20 bytes.

## Receive checksum gap

The receive path never verifies the IPv4 header checksum.

A packet with a corrupted header can therefore reach UDP or TCP parsing if the surrounding length checks happen to pass.

This is a major parser-validation gap.

The existing checksum implementation can be reused for receive verification, but a verifier must not mutate untrusted packet bytes while checking them.

A separate read-only checksum path would be preferable.

## Minimum receive boundary

`net_ipv4` requires only:

    Ethernet 14 bytes + minimum IPv4 header 20 bytes = 34 bytes

before reading the protocol byte.

It does not itself validate:

- IPv4 version;
- IHL;
- total length;
- header checksum;
- flags/fragment offset;
- TTL;
- destination address.

Those checks are partially deferred to transport handlers.

## UDP receive checks

The UDP path performs stronger IPv4 structural checks than `net_ipv4`.

It requires:

- version 4;
- IHL at least 20;
- enough received bytes for Ethernet + IHL + 8-byte UDP header;
- destination IP equal to the local address.

It also reads IPv4 total length and rejects when:

    14 + ip_total > received_frame_length

before accepting the echo payload.

That provides an upper bound against a total-length field larger than the actual RX buffer.

## UDP total-length consistency gap

The UDP path does not fully require internal consistency between:

- IPv4 total length;
- IHL;
- UDP length.

It separately validates UDP length and buffer bounds, but it does not require:

    ip_total == ihl + udp_len

or even enforce that the UDP datagram ends exactly at the IPv4 total-length boundary.

This is less dangerous than the TCP gap because the direct payload bounds are checked against the received frame, but malformed cross-layer length combinations are not rejected systematically.

## TCP receive checks

The TCP path requires:

- at least 54 bytes for Ethernet + minimum IPv4 + minimum TCP;
- IPv4 version 4;
- IHL at least 20;
- enough physical bytes for IHL plus a 20-byte TCP header;
- destination IP equal to the local address.

It then reads the TCP data-offset field to locate payload.

## TCP IPv4-length safety gap

The built-in TCP echo path derives payload length from the IPv4 total-length field:

    payload_len = 14 + ip_total - payload_off

when the total-length endpoint is beyond the computed TCP header.

It does not first require:

    14 + ip_total <= received_frame_length

before using that derived payload length.

A forged IPv4 total length larger than the actual received frame can therefore produce a logical TCP payload length extending beyond received bytes.

The transfer path in `net_xfer.c` follows a similar pattern.

This is a concrete memory-safety hardening issue and should be fixed before treating the stack as robust against hostile packets.

## Routing model

ChrisOS does not maintain a route table or subnet mask in this layer.

`net_udp_send` always requires the cached MAC address of the configured gateway.

It does not distinguish between:

- a destination on the local subnet;
- an off-subnet destination.

All UDP client traffic is therefore sent to the one learned gateway MAC.

This matches the simple QEMU user-network topology but is not a general IPv4 routing design.

## Gateway dependency

If `g_gw_mac_valid` is false, `net_udp_send` returns -1.

As documented in the Ethernet chapter, the current stack has no general active ARP-request builder.

Thus outbound IPv4 client traffic depends on the gateway MAC having been learned from received ARP activity.

There is no route-resolution queue waiting for neighbor discovery.

## UDP transmit size

`net_udp_send` limits application payload to:

    1400 bytes

The resulting IPv4 packet is:

    20 IP
    + 8 UDP
    + up to 1400 payload
    = up to 1428 bytes

With the 14-byte Ethernet header the frame is at most 1442 bytes, safely below the driver's 1514-byte Ethernet-frame limit.

The code intentionally leaves margin below the standard 1500-byte IPv4 payload size.

## TCP transmit size mismatch

`net_tcp_xmit` performs a different bound:

    14 + ip_total <= NET_TX_BUF

where `NET_TX_BUF = 1600`.

This permits construction of frames as large as 1600 bytes.

However, `virtio_net_tx` rejects Ethernet frames larger than 1514 bytes.

Therefore TCP payloads above approximately 1460 bytes can fit the network-layer build buffer but still be rejected by the driver.

Because `net_send_frame` discards the driver's return value, that rejection is not propagated.

This is a cross-layer MTU mismatch.

## No path-MTU discovery

ChrisOS does not implement ICMP Fragmentation Needed handling or path-MTU discovery.

Combined with DF=1 on every generated IPv4 packet, oversized datagrams cannot be fragmented locally and cannot be automatically reduced based on ICMP feedback.

The current small UDP limit avoids this issue for that path.

TCP relies on callers staying within the effective Ethernet MTU.

## Header options

Transmit never generates IPv4 options.

Receive can skip a header larger than 20 bytes because UDP/TCP use IHL when locating transport data.

The option content itself is neither parsed nor validated.

Unknown or malformed option encodings are effectively ignored as opaque header bytes.

Because receive checksum is not verified, even option bytes do not receive integrity checking at the IPv4 layer.

## ICMP absence

There is no ICMP echo, destination-unreachable, time-exceeded, or fragmentation-needed handler in the current stack.

Consequences include:

- no ping response;
- no protocol-unreachable feedback;
- no path-MTU discovery;
- no TTL-expiry messaging;
- no explicit network-layer error reporting to sockets.

This is one reason the current environment depends heavily on known QEMU topology and fixed services.

## Forwarding

ChrisOS does not forward IPv4 packets between interfaces.

There is one VirtIO-net device instance and no router state.

Received packets not intended for current service paths are simply ignored.

The TTL is therefore never decremented by this implementation.

## Broadcast and multicast

There is no explicit IPv4 broadcast or multicast handling policy in `net.c`.

Transport handlers primarily expect the destination to equal the single local unicast address.

There is no IGMP implementation and no multicast membership table.

## Memory and ownership

IPv4 parsing is zero-copy relative to the VirtIO RX Ethernet frame.

Pointers into the IP header remain valid only while the RX descriptor remains owned by the stack.

Current handlers process synchronously and copy persistent connection fields such as IP addresses into their own state.

Transmit uses the same global `g_tx[1600]` buffer described in the Ethernet chapter.

There is no allocation per IPv4 packet.

## Concurrency

IPv4 transmit and receive share global state with Ethernet and transport layers.

There is no lock protecting `g_tx`, gateway state, or the simple built-in TCP connection state.

The current polling model effectively serializes normal operation.

Arbitrary concurrent AP callers could race while constructing IPv4 packets.

The networking subsystem is not generally SMP-safe in this revision.

## Complexity

IPv4 header construction is O(1), excluding payload construction in upper layers.

Header checksum cost is O(IHL), which is always 20 bytes on generated packets.

Receive dispatch is O(1).

No routing-table lookup, reassembly search, neighbor-table search, or option processing exists.

The simplicity is deliberate but pushes many standard IPv4 responsibilities outside the implementation.

## QEMU environment

The default run configuration uses QEMU user networking with VirtIO-net.

The fixed guest address 10.0.2.15 and gateway 10.0.2.2 align with that environment.

Port forwarding provides host access to guest TCP/UDP services.

Successful echo or file-transfer traffic therefore demonstrates that generated IPv4 headers are usable in this environment.

It does not prove general interoperability across arbitrary routed networks.

## Validation evidence

There is no dedicated `test_ipv4.c` in the inspected tree.

Existing evidence is indirect:

- UDP echo uses generated IPv4 headers;
- TCP echo and transfer use the same builder;
- QEMU port-forwarding exercises receive and transmit;
- socket/DNS paths depend on outbound IPv4 packets.

The parser still lacks systematic malformed-header tests.

## Recommended tests

A deterministic IPv4 test suite should cover:

- exact 20-byte header bytes from `ip_build`;
- known checksum vectors;
- version other than 4;
- IHL below 5 and IHL larger than the received frame;
- invalid header checksum;
- total length below IHL;
- total length larger than received frame;
- total length smaller/larger than UDP/TCP lengths;
- DF, MF, and nonzero fragment offsets;
- TTL zero;
- unknown protocols;
- destination not equal to local IP;
- TCP forged total length larger than RX frame;
- transmit payload at 1460 and 1461 bytes to expose the driver MTU boundary.

## Current limitations

The current IPv4 implementation is static and QEMU-oriented.

It has no DHCP, route table, subnet mask logic, ICMP, fragmentation/reassembly, PMTU discovery, multicast control, forwarding, receive checksum verification, or robust length normalization before transport dispatch.

Generated packets are simpler and better constrained than accepted receive packets.

The largest immediate hardening priorities are:

1. validate IPv4 checksum;
2. reject or reassemble fragments;
3. centralize version/IHL/total-length validation;
4. guarantee `ip_total <= received bytes`;
5. reconcile TCP transmit size with the actual Ethernet MTU.

## Revision note

This chapter was created against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. It documents the fixed-address IPv4 builder and receive dispatch exactly as implemented, including fragmentation, checksum, routing, MTU, and malformed-length gaps that remain unresolved.
