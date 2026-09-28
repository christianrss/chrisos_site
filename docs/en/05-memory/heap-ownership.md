---
id: heap-ownership
lang: en
type: technical-chapter
volume: 05-memory
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/metal/heap.c
  - kernel/metal/pmm.c
symbols:
  - heap_init
  - kmalloc
  - kfree
depends_on:
  - physical-memory
related:
  - tlb-shootdown
---

# Kernel heap, ownership and lifetime

## Why a heap exists above the PMM

The PMM allocates page-sized physical resources. Kernel code frequently needs smaller objects whose size and lifetime are not whole pages: structures, buffers, strings and tables.

A heap allocator obtains large backing regions and subdivides them.

ChrisOS heap arenas are backed by contiguous physical pages and accessed through the kernel's direct-map view. Each arena contains block headers recording size and whether the block is in use.

## Alignment and metadata

Allocators round requested sizes to alignment boundaries so returned objects satisfy CPU/ABI alignment requirements.

A block header introduces overhead but stores enough information for traversal and free/coalesce operations.

```text
+-------------+-------------------------+
| block header| user allocation         |
| size, used  | aligned payload         |
+-------------+-------------------------+
```

## Splitting

If a free block is larger than requested, the allocator can split it into an allocated block plus another free block, provided the remainder is large enough to contain metadata and a useful aligned payload.

Without splitting, small requests waste entire large blocks.

## Coalescing

Freeing neighboring blocks can create fragmentation. Coalescing merges adjacent free regions so a later larger allocation can reuse the combined range.

Physical contiguity of the underlying arena is separate from logical adjacency of heap blocks.

## Heap growth

When no existing arena can satisfy a request, the heap can request more pages from PMM. Current ChrisOS keeps a physical-memory reserve and limits the number of arenas.

This edge establishes lock ordering: heap code can enter PMM while growing.

## Ownership

Allocation answers "who may use this memory now?" Lifetime answers "who is responsible for eventually releasing it?"

The project's ownership document explicitly assigns destroy paths for process page tables, user leaf frames, JIT pages, file descriptors, sockets, kthread stacks, graphics contexts and several device buffers.

This matters because a leak is usually not caused by absence of `free` itself; it is caused by unclear responsibility during every success and error path.

## Destruction as architecture

A subsystem is not complete when it can create an object. It needs a symmetrical destroy path or an explicit boot-lifetime policy.

For example:

```text
create
  ↓
initialize
  ↓
publish / use
  ↓
detach from users
  ↓
stop asynchronous access
  ↓
unmap / release
  ↓
free backing storage
```

The order is especially important for DMA and TLB-visible resources. Memory cannot be freed while hardware or another CPU can still access it.

## Lock order

Current source documents an ordering among JIT compile, MM, heap and PMM locks. This prevents cycles such as CPU A holding PMM and waiting for heap while CPU B holds heap and waits for PMM.

Lock ordering is therefore part of memory architecture, not an implementation comment of secondary importance.

## Failure paths

Every multi-step allocation should be reviewed as a transaction. If step 4 fails, steps 1–3 must be undone in the reverse dependency order unless ownership has already transferred elsewhere.

This is one of the most important habits in kernel development because low-memory and partial-initialization paths are exactly where leaks and dangling references accumulate.
