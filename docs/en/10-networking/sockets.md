---
id: sockets
lang: en
type: technical-chapter
volume: 10-networking
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/net/sock.c
  - kernel/net/sock.h
  - kernel/net/net.c
  - kernel/lang/clvm_sys.c
  - kernel/metal/proc.c
  - kernel/metal/proc.h
  - tools/test_sock_owner.c
  - APPS/NET/BROWSER.CC
  - APPS/NET/SSH.CC
  - APPS/NET/TLS.CC
symbols:
  - sock_init
  - sock_listen_for
  - sock_accept_for
  - sock_connect_for
  - sock_send_for
  - sock_recv_for
  - sock_close_for
  - sock_close_slot
  - sock_close_proc
  - sock_on_tcp
  - sock_on_udp
depends_on:
  - tcp
  - udp
related:
  - network-stack
---

# Socket ownership and API

## Scope

ChrisOS exposes a small in-kernel socket table to native processes and CLVM applications.

The API is intentionally much smaller than BSD/POSIX sockets.

There is no separate `socket()` creation call, no address-family object, no file-descriptor integration layer, no `bind()`, no `sendto()`, no `recvfrom()`, no `select/poll/epoll`, and no socket options.

Instead, the main operations are:

- listen;
- accept;
- connect;
- send;
- receive;
- close.

Descriptors are direct indexes into a fixed global socket array.

The same table is also reused for the project's limited UDP receive path.

## Table size

The implementation defines:

```text
SOCK_MAX = 16
SOCK_RX  = 2048
```

The array contains sixteen `Sock` objects.

However, `alloc_sk` scans indexes 1 through 15 and never returns index zero.

Therefore there are at most fifteen simultaneously allocated application-visible socket descriptors.

Descriptor zero is effectively reserved/unused.

## Socket structure

Each `Sock` stores:

- state;
- parent listener descriptor;
- remote IPv4 address;
- remote port;
- local port;
- remote MAC address;
- send-next sequence;
- receive-next sequence;
- 2048-byte receive buffer;
- receive length;
- 256-byte last-segment scratch state;
- last transmit tick;
- MAC-known flag;
- native process owner PID;
- CLVM slot.

This object mixes transport state, buffering, ownership, and retry metadata.

There is no separate protocol control block abstraction.

## Implemented states

Only four states exist:

```text
FREE
LISTEN
SYN_SENT
ESTABLISHED
```

There is no explicit protocol field identifying TCP versus UDP.

That omission matters because UDP receive also searches LISTEN sockets.

A LISTEN entry is therefore an overloaded object whose meaning depends on which receive path happens to match it.

## Initialization

`sock_init` iterates over all sixteen slots and sets state to FREE.

It does not explicitly clear every field in every structure.

Allocation resets the fields currently needed for ownership and buffering:

- state;
- rx_len;
- last_len;
- parent;
- owner;
- slot.

Other fields are overwritten later by listen/connect/accept paths when they become relevant.

A stricter design would fully initialize or zero a socket object on allocation.

## Allocation

`alloc_sk(owner, slot)` returns the first FREE entry from index 1 upward.

Before the caller assigns its final semantic state, the function temporarily marks the object ESTABLISHED.

Callers such as `sock_listen_for` and `sock_connect_for` immediately replace that state.

When all fifteen usable entries are occupied, allocation returns -1.

There is no dynamic growth.

## Ownership model

Every socket records two identity fields:

```text
owner = native process PID
slot  = CLVM application slot or negative
```

The access rule is implemented by `fd_visible`.

For a CLVM caller with `slot >= 0`:

```text
socket.slot must equal caller slot
```

For a native caller:

```text
socket.slot < 0
and
socket.owner == proc_current()
```

This creates two ownership domains over the same table.

## Native wrappers

The simple functions:

- `sock_listen`;
- `sock_accept`;
- `sock_connect`;
- `sock_send`;
- `sock_recv`;
- `sock_close`

call their `*_for` equivalents with slot = -1.

That causes visibility to be checked against the current native process PID.

A native process cannot normally operate another process's network descriptor.

## CLVM wrappers

CLVM syscalls use explicit application slots.

Relevant syscall cases are:

```text
140 listen
141 accept
142 connect
143 send
144 recv
145 close
146 DNS helper
```

Before invoking the socket function, the CLVM layer calls `vm_sync_slot`.

The slot value is then passed into `sock_*_for`.

This binds socket access to the application slot rather than merely to the host process executing the VM.

## Listen

`sock_listen_for(port, slot)` allocates one descriptor, changes its state to LISTEN, stores the local port, and clears parent.

It does not check whether another socket is already listening on the same port.

Multiple LISTEN entries can therefore exist for the same port.

`find_listen` returns the first matching table entry, so duplicate listeners are not load-balanced or rejected deterministically by policy; the lowest-index matching entry wins.

## No protocol binding

`sock_listen_for` does not specify TCP or UDP.

The same LISTEN object can potentially be examined by both:

- `sock_on_tcp`;
- `sock_on_udp`.

The API therefore cannot express "listen for TCP only" or "bind UDP only".

This is a fundamental abstraction gap.

## Accept

`sock_accept_for` first verifies ownership and requires the descriptor to be LISTEN.

It then scans the entire table for a child satisfying:

```text
child.parent == listener_fd
child.state == ESTABLISHED
```

When found, it clears the child's parent field and returns the child descriptor.

If no child exists, it returns -1.

There is no explicit accept backlog queue.

Pending children are represented only by socket-table entries whose `parent` still points at the listener.

## Early established state

The TCP receive path creates a child immediately when SYN arrives.

That child is marked ESTABLISHED before the peer's final ACK is validated.

Consequently, `sock_accept` can return a connection that has not completed a conventional three-way handshake.

This behavior is a property of the TCP implementation, but it materially changes the socket API's meaning of "accepted".

## Connect

`sock_connect_for(ip, port, slot)` allocates a descriptor and configures:

- SYN_SENT;
- remote IPv4;
- remote port;
- ephemeral local port;
- initial sequence number;
- receive-next = 0;
- gateway/remote MAC state.

The ephemeral counter starts at 40000.

After 16-bit wrap, any value below 40000 is reset to 40000.

There is no collision search before assigning an ephemeral port.

## Connect return semantics

`sock_connect_for` returns the descriptor immediately after attempting to send SYN.

It does not block waiting for ESTABLISHED.

If the gateway MAC is not yet available, the internal transmit helper does not send the SYN, but the descriptor still remains in SYN_SENT and is returned to the caller.

`sock_tick` may transmit/retransmit later once a MAC becomes available.

Thus a nonnegative connect result means "socket allocated and connection attempt started", not "connected".

## Send

`sock_send_for` requires:

- descriptor visible to caller;
- state ESTABLISHED;
- nonnegative requested length.

Lengths above 200 are truncated to 200.

The function emits PSH|ACK through the TCP helper and returns the truncated length.

It does not wait for acknowledgment.

It does not expose short-send semantics caused by lower-layer failure because the underlying packet builder/transmit chain does not propagate device failure back to this API.

## Null send buffer gap

`sock_send_for` does not reject a null `buf` when `n > 0`.

The lower TCP packet builder will eventually dereference the payload pointer.

A bad kernel caller can therefore cause a fault.

The CLVM syscall path avoids this by copying validated guest memory into a local 200-byte temporary buffer before calling the socket layer.

## CLVM send boundary

Syscall 143 limits `n` to 200.

It verifies:

- nonnegative guest address/length;
- VM memory exists;
- requested range is inside VM memory;
- slot synchronization succeeds.

Only then are bytes copied from guest memory into a kernel stack buffer and passed to `sock_send_for`.

This provides a stronger user-memory boundary than the raw kernel socket function itself.

## Receive

`sock_recv_for` requires:

- visible descriptor;
- non-null destination pointer;
- positive requested length;
- state ESTABLISHED.

If no buffered bytes exist, it returns zero.

Otherwise it copies up to the caller's requested length from the beginning of the 2048-byte receive array.

Remaining bytes are shifted toward index zero.

The receive buffer is therefore a compacted byte stream, not a queue of mbufs or packet objects.

## Receive complexity

Because unread bytes are shifted after every partial receive, a small read can cost O(remaining buffered bytes).

Repeated one-byte reads from a full buffer can therefore produce quadratic copying behavior relative to the original buffered length.

A ring buffer with head/tail indexes would avoid this compaction cost.

## Blocking behavior for native callers

The native `sock_recv` wrapper simply returns zero when no data is available.

The socket library itself does not put the native process to sleep.

Native code must poll, yield, or arrange blocking at a higher layer if desired.

## Blocking behavior for CLVM

Syscall 144 adds blocking semantics around `sock_recv_for`.

When receive returns zero, the CLVM layer:

1. sets VM state to `CLVM_WAITING`;
2. blocks the current process with `PROC_ST_BLOCK_SOCK`;
3. pushes the syscall arguments and syscall number back onto the VM stack;
4. returns so execution can resume later.

When network input is delivered, socket receive code may call `proc_unblock(owner)`.

This is the bridge between network arrival and CLVM scheduling.

## Receive wakeups

TCP payload delivery calls `proc_unblock` when `owner > 0`.

UDP delivery does the same.

The socket stores a native process owner even for CLVM-created entries because allocation records `proc_current()` plus the CLVM slot.

Thus the hosting process can be woken while slot-based visibility still protects the descriptor from other CLVM applications.

## Close

`sock_close_for` verifies visibility.

If state is ESTABLISHED, it sends FIN|ACK.

It then immediately marks the entry FREE and resets slot to -1.

There is no wait for FIN acknowledgment or peer shutdown.

The descriptor can be reallocated immediately after this local close.

## Cleanup on process exit

Process teardown in `proc.c` calls:

```text
sock_close_proc(pid)
```

after closing other syscall-owned resources.

`sock_close_proc` scans all sockets and closes every non-FREE entry whose owner matches the exiting PID.

ESTABLISHED sockets receive a best-effort FIN|ACK before being freed.

This prevents ordinary socket-table leakage across native process lifetime.

## Cleanup on CLVM slot teardown

CLVM resource cleanup calls:

```text
sock_close_slot(slot_id)
```

alongside shader, voxel, input-capture, and file-descriptor cleanup.

Every matching socket is freed, again sending FIN|ACK for ESTABLISHED entries.

This ties network resources to the lifetime of the CLVM application slot.

## Ownership test evidence

`tools/test_sock_owner.c` directly tests ownership rules.

It proves that:

- slot 2 cannot close a socket owned by slot 1;
- slot 2 cannot accept from slot 1's listener;
- the owning slot can close its socket;
- cleanup by slot invalidates that slot's socket;
- one native process cannot close another process's socket;
- the owning native process can close it.

This is real host-side unit evidence for access control.

## Limits of the ownership test

The test stubs networking functions.

It does not validate:

- TCP handshake;
- packet parsing;
- receive wakeup;
- port collision;
- accept backlog;
- cleanup FIN transmission;
- concurrency.

It validates descriptor ownership only.

## TCP child lookup

Established TCP sockets are found by the tuple:

```text
remote IP
remote port
local port
```

Owner PID and CLVM slot are not part of `find_conn`.

Normally the local ephemeral/listener port distinguishes connections.

However, because duplicate listeners and ephemeral-port collisions are possible, the table does not provide a strong namespace guarantee across owners.

## Duplicate local ports

There is no check preventing two applications from listening on the same TCP port.

There is also no search to ensure a newly selected ephemeral port is unused.

This can create ambiguous receive routing.

The first matching listener/connection encountered by the global table scan wins.

A production socket layer would enforce binding rules and tuple uniqueness.

## UDP reuse of LISTEN

The current UDP receive path also scans LISTEN sockets.

As documented in the UDP chapter, it currently contains a source-port/destination-port offset bug and does not validate payload bounds against the physical frame.

Even after those bugs are fixed, the socket abstraction still lacks per-datagram peer metadata and protocol typing.

Therefore the present socket table is substantially more TCP-stream-oriented than a real dual-protocol API.

## DNS internal socket

`sock_dns` allocates one persistent internal socket descriptor and puts it in LISTEN with an ephemeral local port.

It bypasses the public ownership/visibility wrappers when inspecting its receive buffer.

The helper is therefore an internal consumer of the same global table rather than an independent resolver subsystem.

The UDP demultiplexing bug described in the UDP chapter prevents the intended normal DNS response from reaching this socket in the inspected revision.

## Application consumers

Several CLVM applications demonstrate intended socket use.

The browser:

- resolves `example.com`;
- connects to port 80;
- sends a small HTTP/1.0 request;
- receives up to 120 bytes.

The SSH sample connects to port 22 and sends an SSH banner.

The TLS sample performs a small X25519 computation and sends 32 bytes to port 443.

These are API consumers and experiments, not proof of complete application-protocol or TCP interoperability.

## No generic file-descriptor semantics

Socket descriptors are indexes into `g_sk`, not entries in a unified POSIX descriptor table.

The CLVM filesystem has separate descriptor management.

As a result, generic operations such as read/write/close over one descriptor namespace are not provided by this socket layer.

The API remains explicitly network-specific.

## No readiness multiplexing

There is no `select`, `poll`, `epoll`, event object, or readiness callback API.

A caller either:

- attempts receive and sees data/zero;
- relies on CLVM blocking behavior;
- polls at application level.

This is sufficient for the small application set but limits scalable multiplexed servers.

## Concurrency

The entire socket table is global and unlocked.

Allocation, close, RX delivery, send, timer retransmission, and cleanup can all mutate entries.

The current system relies on effectively serialized network polling and syscall activity.

Concurrent access from multiple CPUs is not generally safe.

A future design should either guard the table with locks or confine all socket state transitions to one network execution context.

## Security and correctness priorities

The socket layer's highest-value improvements are:

1. add an explicit protocol/type field;
2. reject duplicate TCP listeners according to a defined binding policy;
3. ensure ephemeral-port uniqueness;
4. make connect completion observable separately from allocation;
5. validate null send buffers;
6. replace receive compaction with a ring/queue structure;
7. model accepted connections only after valid handshake completion;
8. implement proper close/error states;
9. preserve UDP datagram metadata and boundaries;
10. add locking or execution-context confinement;
11. extend host tests to lifecycle, blocking, collision, and receive behavior.

## Revision note

This chapter was created against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. It documents the fixed 16-entry socket table, native/CLVM ownership rules, direct index descriptors, blocking bridge, cleanup hooks, and the protocol-model limitations present in the current implementation.
