---
id: virtio-gpu-transport
lang: en
type: technical-chapter
volume: 08-graphics
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - kernel/gfx/vgpu.c
  - kernel/gfx/vgpu.h
  - kernel/gfx/virtq.c
  - kernel/gfx/virtq.h
  - kernel/gfx/virtgpu_enc.c
  - kernel/gfx/virtgpu_enc.h
  - kernel/gfx/gpures.c
  - kernel/gfx/gpures.h
  - kernel/gfx/hwgate.c
  - kernel/gfx/hwgate.h
  - SYS/DRV/VIRTIOGPU.CC
  - tools/test_virtq.c
  - tools/test_gpures.c
  - tools/test_virgl_cmd.c
symbols:
  - virtq_init
  - virtq_alloc
  - virtq_publish
  - virtq_take
  - virtq_reclaim
  - vgpu_boot
  - vgpu_submit
  - vgpu_res_create_2d
  - vgpu_res_attach
  - vgpu_res_detach
  - vgpu_res_unref
  - vgpu_set_scanout
  - vgpu_flush_rect
depends_on:
  - buses-mmio-dma
related:
  - virtio-gpu-virgl
  - gfx3d-api
  - virgl-command-stream
---

# VirtIO-GPU transport and resources

## Scope

This chapter isolates the transport and resource-management layer underneath ChrisOS graphics.

The subject is not the VirGL command language itself. It is the machinery that discovers the VirtIO GPU PCI function, maps its configuration regions, negotiates features, builds split virtqueues, moves commands through DMA, validates completions and owns VirtIO resource identifiers.

That distinction matters because the same transport carries both ordinary 2D commands and optional 3D/VirGL requests.

A useful dependency view is:

```text
PCI / MMIO / DMA
      |
      v
VirtIO PCI capabilities
      |
      v
split virtqueue transport
      |
      v
VirtIO-GPU control protocol
      |
      +--> 2D resources / scanout / cursor
      |
      +--> 3D resources / contexts / SUBMIT_3D
```

VirGL sits above the final 3D branch, not below the transport.

## Device discovery

The kernel driver scans PCI buses 0 through 7 and device numbers 0 through 31, function zero.

It accepts:

```text
vendor 0x1AF4
device 0x1050
```

The search is therefore deliberately narrower than a general PCI enumerator.

Once found, the driver sets PCI command bits for memory-space access and bus mastering.

Bus mastering is required because the device consumes guest physical addresses from virtqueue descriptors and resource backing entries.

## VirtIO PCI capability parsing

The PCI capability list is walked from configuration offset 0x34.

The driver looks for vendor-specific capability ID 9 and interprets the VirtIO configuration type from the high byte.

The current path records:

- type 1: common configuration;
- type 2: notify configuration;
- type 3: ISR configuration;
- type 4: device-specific configuration.

The BAR referenced by each capability is mapped through `hw_bar_map`.

The common and notify mappings are mandatory. The ISR and device-specific mappings are optional for basic bring-up but support interrupt acknowledgement and discovery metadata.

## BAR mapping boundary

`hw_bar_map` reads the BAR, determines whether it is 64-bit, temporarily probes its size, restores the original BAR and maps pages through the MMIO mapper.

The hardware gate keeps at most eight MMIO windows.

Each mapped window is capped to 64 pages, or 256 KiB.

This cap is a ChrisOS policy, not a VirtIO protocol property.

The GPU transport therefore depends on generic MMIO window capacity being available before device initialization.

## Feature negotiation state machine

The GPU driver resets device status to zero and then writes the standard ACKNOWLEDGE and DRIVER progression.

It reads both device-feature selector words.

The implementation requires the high word's low bit, corresponding to feature bit 32 used by modern VirtIO.

Without that requirement, initialization fails.

If 3D is desired and supported, the guest also requests `VGPU_F_VIRGL`.

If VirGL is selected and the device advertises `VGPU_F_CONTEXT_INIT`, that feature is requested as well.

## FEATURES_OK retry

The requested words are written into the driver-feature registers and FEATURES_OK is set.

The driver reads status back.

If the device rejects the proposed set, ChrisOS restarts negotiation and retries with the mandatory modern VirtIO bit but without the optional low-word GPU features.

This fallback allows the transport to survive an unsupported optional feature combination and still expose 2D VirtIO-GPU.

A second FEATURES_OK failure aborts initialization.

## Split virtqueue implementation

ChrisOS implements its own split virtqueue helper in `kernel/gfx/virtq.c`.

The general helper supports:

```text
VQ_MAX = 128
```

descriptors.

The queue size must:

- be at least 2;
- be no larger than 128;
- be a power of two.

A non-power-of-two size returns zero from `virtq_bytes` and is rejected by `virtq_init`.

## Queue memory layout

For a queue size N, ChrisOS places:

1. N 16-byte descriptors;
2. the available ring;
3. padding to a four-byte boundary;
4. the used ring.

The descriptor region begins at offset zero.

The available ring begins immediately after the descriptors.

The used ring begins after the available ring, aligned to four bytes.

`virtq_bytes` computes the complete required footprint before initialization.

## Queue metadata

The device-visible queue memory is separate from host-side bookkeeping.

`Virtq` stores:

- memory pointer and byte capacity;
- queue size;
- freelist head;
- number of free descriptors;
- last consumed used index;
- per-descriptor next links;
- per-descriptor software flags;
- offsets of descriptor, available and used areas.

The freelist lives in the C structure, not in a device-visible linked list.

## Initialization

`virtq_init` zeros the device-visible bytes and initializes every descriptor index into a software freelist.

Initially:

```text
free_head = 0
nfree = qsz
last_used = 0
```

Each `link_next[i]` points to the next index and the final descriptor points to 0xffff.

This is the allocator state used for request chains.

## Descriptor allocation

`virtq_alloc(q,n,&head)` requires enough free descriptors.

It removes N entries from the freelist and connects their software flags using `VQ_DESC_F_NEXT`.

The returned head is the first descriptor of the allocated chain.

For the GPU control transport, ordinary submissions allocate exactly two descriptors:

- request;
- response.

This means a queue with 16 descriptors can hold at most eight two-descriptor requests if they were all outstanding simultaneously.

The current GPU driver serializes submissions, so it normally has only one such chain outstanding.

## Descriptor population

`virtq_set` writes the device-visible descriptor:

```text
address : 64 bits
length  : 32 bits
flags   : 16 bits
next    : 16 bits
```

Request descriptors are device-readable.

Response descriptors add `VQ_DESC_F_WRITE`, authorizing the device to write into guest memory.

The software next-link selected by allocation becomes the descriptor's next field.

## Publishing to the available ring

`virtq_publish` issues a memory barrier before touching the available ring.

It reads the current avail index, selects the ring slot with modulo queue size, writes the descriptor head, executes another barrier, increments the avail index, and executes a final barrier.

On x86 builds, the helper uses `mfence`.

The intent is to prevent the device from observing the avail index before descriptor content and ring entry are globally visible.

## Consuming the used ring

`virtq_take` reads the used index after a barrier.

If it equals `last_used`, no completion is available.

Otherwise it reads the next used element, validates that the returned descriptor ID is below queue size, copies the used length, increments `last_used`, and returns one completion.

Invalid used IDs are treated as transport corruption and return an error.

## Descriptor reclamation

`virtq_reclaim` walks the software chain beginning at the head.

Every descriptor is returned to the freelist and `nfree` is incremented.

The traversal stops when the saved NEXT flag is no longer present.

The function clears software flags as it reclaims entries.

The driver is therefore responsible for reclaiming every accepted chain exactly once.

## GPU queue sizing

The GPU-specific setup begins with:

```text
VGPU_QSZ = 16
```

If the device advertises fewer descriptors, ChrisOS selects the largest supported size among 16, 8, 4 and 2.

A queue smaller than two is rejected.

Even though the generic virtqueue code supports up to 128, the GPU transport deliberately caps itself at 16.

This keeps one queue inside a single 4 KiB DMA page with ample margin.

## Queue programming

After `virtq_init`, setup writes the queue size and physical addresses of:

- descriptor table;
- available ring;
- used ring.

The driver marks MSI-X vector as 0xffff in this path and enables the queue.

The notify offset is then read from common configuration and combined with the notify multiplier.

The resulting MMIO location is stored in `VqBind`.

## Control and cursor queues

Queue zero is the control queue.

Queue one is configured only if the device reports at least two queues.

Cursor commands use the cursor queue, while resource management and 3D commands use the control queue.

If cursor queue setup fails, the rest of the graphics device can still operate.

This makes cursor acceleration optional rather than a prerequisite for scanout.

## Shared command and response staging

The current control transport allocates four DMA pages for command staging and four for response staging.

Before a request is submitted, encoded bytes are copied into the shared command DMA.

The response area is cleared at its beginning.

The descriptor chain points directly to these staging areas.

Because this storage is reused, the driver protects it with global `g_busy` serialization.

## Serialization contract

`vgpu_submit_vq` rejects a new control request while `g_busy` is set.

The current design is therefore synchronous from the guest driver's perspective.

It does not attempt to fill the virtqueue with many in-flight commands.

This leaves queue depth mostly as robustness headroom rather than a throughput pipeline.

The simplification reduces command-buffer lifetime complexity but limits command-level parallelism.

## Notification and completion

After the chain is published, the driver writes the queue index to the calculated notify MMIO address.

Completion is detected by polling `virtq_take`.

The code also installs an IRQ handler and acknowledges ISR state, but the normal synchronous request path still waits on the used ring.

The IRQ count is therefore diagnostic/supporting state rather than the primary completion mechanism.

## Polling budgets

The wait loop has fast and slow profiles.

It combines a spin-count limit with a TSC elapsed-cycle budget.

The loop periodically executes `pause`.

Slower operations, including several 3D/control paths, use the larger budget.

Timeout marks the GPU dead, clears live and online state and returns an error.

The current transport does not attempt device reset and replay after such a timeout.

## Fenced requests

A global 64-bit sequence `g_fence_seq` starts at one.

For fenced requests the driver writes the FENCE flag and sequence into the VirtIO-GPU header.

When a completion arrives, the returned fence must match.

A mismatch is logged and rejected.

This prevents a stale or unexpected response from being accepted as completion for the current request.

## Response validation

Transport completion and protocol success are separate checks.

The driver validates:

- used descriptor identity;
- returned fence;
- nonzero response type;
- response not in the error range;
- expected command-specific response when one is known.

Thus a used-ring entry alone does not prove that RESOURCE_CREATE, DISPLAY_INFO or SUBMIT_3D succeeded.

## Encoder boundary

`virtgpu_enc.c` serializes VirtIO-GPU protocol structures into byte arrays.

It uses explicit little-endian 32-bit writes rather than C struct layout.

This avoids depending on compiler padding.

The common header occupies:

```text
VGPU_HDR_SIZE = 24 bytes
```

and contains type, flags, fence and context fields plus zeroed padding.

## Encoder validation

The encoder rejects invalid zero IDs where the command requires an object, zero dimensions, insufficient destination capacity and out-of-range values for selected 3D fields.

For example, 2D resource dimensions above 8192 are rejected.

3D dimensions above 8192, array size above 256 and sample count above 16 are rejected.

`vgpu_enc_submit3d` limits one encoded submission to 4096 dwords, although the higher Gfx3D batching layer currently uses a smaller 1024-dword command batch.

## 2D resource lifecycle

`vgpu_res_create_2d` first allocates a local resource ID.

It emits RESOURCE_CREATE_2D and then records type, state, dimensions, format and backing metadata in the local pool.

When DMA backing is supplied, `vgpu_res_attach` emits RESOURCE_ATTACH_BACKING.

Attach validates that the backing range lies within the DMA allocation.

One backing entry is encoded for the current resource.

## Resource pool

The GPU transport tracks:

```text
GPU_RES_MAX = 96
GPU_CTX_MAX = 16
```

The resource pool is distinct from DMA allocation.

A resource can refer to a whole DMA allocation or a region beginning at `backing_off`.

The 96-resource cap was sized with cached chunk meshes, window targets, atlas, scanout, cursor and headroom in mind.

Exhaustion is reported to callers rather than panicking.

## Resource identifiers

Resource ID zero is reserved as invalid.

Allocation increments `next_res`, wrapping away from zero.

Before choosing an ID, the allocator checks whether it is still live.

The pool may search up to 100000 candidate IDs before giving up in the pathological wrap/collision case.

A released resource entry is marked FREE and its ID is cleared.

## Ownership

Every resource has an integer owner.

Release verifies ownership and returns a distinct error for a foreign owner.

Context/resource attachment also requires matching owners.

The mechanism is bookkeeping isolation inside the graphics subsystem; it is not a hardware IOMMU security boundary.

The DMA backing itself remains kernel-managed memory.

## Resource states

The enum contains:

```text
FREE
ALLOC
CREATED
BACKED
ATTACHED
SCANOUT
```

Current code uses the major lifecycle states but does not make the enum a complete formal state machine.

For example, context attachment increments `ctx_attached` but does not necessarily rewrite `state` to ATTACHED.

Therefore callers should rely on the actual operations and ownership checks rather than assuming every enum value is a strict transition invariant.

## Backing detach and unref

`vgpu_res_detach` sends RESOURCE_DETACH_BACKING.

When the local state is BACKED, it returns to CREATED.

`vgpu_res_unref` sends RESOURCE_UNREF and then releases the local resource slot.

`vgpu_res_drop` additionally frees ordinary DMA backing when that DMA is not one of the protected global allocations such as primary framebuffer, command/response queues or cursor storage.

The transport tries to keep device and local ownership changes paired.

## Scanout state

`vgpu_set_scanout` emits SET_SCANOUT.

If the resource exists locally, its state becomes SCANOUT.

Changing scanout also increments cursor generation because QEMU may discard the current cursor sprite when the scanout resource changes.

Presentation and cursor lifecycle are therefore coupled at this lower device layer.

## Transfer-to-host path

For normal desktop updates, CPU-rendered pixels are copied into the scanout backing.

TRANSFER_TO_HOST_2D tells the device to consume the changed backing region.

RESOURCE_FLUSH asks the display side to make the resource update visible.

The two operations have different roles: transfer updates host resource content, while flush updates display presentation.

## 3D transport reuse

The same control queue carries:

- CTX_CREATE and CTX_DESTROY;
- CTX_ATTACH_RESOURCE and CTX_DETACH_RESOURCE;
- RESOURCE_CREATE_3D;
- TRANSFER_TO_HOST_3D and TRANSFER_FROM_HOST_3D;
- SUBMIT_3D.

The transport does not interpret the VirGL dwords inside SUBMIT_3D.

It only packages the byte count, context and command payload and validates VirtIO-GPU completion.

This is the boundary between the VirtIO transport and the VirGL command-stream layer.

## Stress validation at boot

Before depending on 3D, `vgpu_boot` runs a 2D lifecycle stress test.

A small 8×8 resource is repeatedly created, transferred, flushed, detached and unreferenced using one DMA page.

Normal boot uses four cycles.

The graphics stress flag raises the cycle count to 1000.

At the end, both live-resource count and free-descriptor count must return to their original values.

This checks both resource leakage and virtqueue descriptor leakage.

## virtqueue unit test

`tools/test_virtq.c` initializes an eight-descriptor queue and repeats a two-descriptor allocate/publish/complete/reclaim cycle 1000 times.

It synthesizes used-ring entries directly in memory.

After every cycle, all eight descriptors must be free again.

The test also rejects a non-power-of-two queue size and verifies that allocating more descriptors than available fails.

This is meaningful evidence for allocator/ring bookkeeping independent of QEMU.

## resource-pool unit test

`tools/test_gpures.c` verifies distinct IDs, owner rejection, release, and 1000 repeated resource/context allocation cycles.

The final live counts must be zero.

This validates local bookkeeping but does not exercise a real VirtIO device.

## Legacy ChrisC driver

`SYS/DRV/VIRTIOGPU.CC` contains a smaller educational VirtIO-GPU driver written in ChrisC.

It discovers the same PCI device and manually lays out a four-entry queue in DMA memory.

It creates resource 1, attaches framebuffer backing, sets scanout and then hands the device to the kernel hardware gate.

This file is valuable as a compact explanation of the protocol, but it is not the authoritative implementation for current kernel transport semantics.

The C kernel driver has richer queue management, capability negotiation, ownership, stress tests, cursor support, capsets and failure handling.

## Concurrency limitations

Resource pools and global transport state are not protected as a fully concurrent multi-client subsystem.

Control submission is serialized by `g_busy`, but local pool operations themselves do not form a broad locking protocol for arbitrary parallel callers.

The intended usage is controlled kernel/Gfx3D sequencing.

A future asynchronous driver would need explicit locking, per-request command storage and a completion-dispatch structure keyed by descriptor/fence.

## Failure containment

Encoding failures are returned before device submission.

Virtqueue descriptor failure, MMIO notify failure, malformed used IDs, device error responses, fence mismatches and timeouts all propagate as transport errors.

Several fatal transport failures set dead/live state so future work is refused.

Higher Gfx3D policy can then degrade to software rendering.

The transport itself does not pretend a timed-out request succeeded.

## Current limitations

The PCI search covers a limited bus/function range.

The GPU queue is intentionally capped at 16 descriptors even though the generic helper supports 128.

Control traffic uses one shared command and response staging pair.

Completion is synchronous and poll-driven.

There is no request cancellation, reset/recovery state machine or general asynchronous completion dispatcher.

Resource and context pools are fixed-size.

These constraints are acceptable for the current experimental kernel but should be explicit before scaling the renderer.

## Recommended next tests

Useful additions include malformed used-ring indices, avail/used wrap beyond 16-bit boundaries, forced MMIO notify failure, response-fence mismatch, queue sizes 2/4/16/128, concurrent resource-owner attempts, DMA backing offset boundaries, scanout replacement and deliberate timeout/recovery behavior.

A QEMU integration test should also prove that repeated 2D partial updates preserve descriptor count and resource count over long runs.

## Revision note

This chapter was created from ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`. It treats split virtqueues, VirtIO-GPU protocol encoding and resource ownership as a transport layer below VirGL and the backend-neutral Gfx3D API.
