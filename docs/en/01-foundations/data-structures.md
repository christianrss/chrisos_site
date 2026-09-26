---
id: data-structures
lang: en
type: technical-chapter
volume: 01-foundations
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - data-representation-layout
  - algorithmic-complexity
related:
  - systems-algorithms
---

# Data structures for systems software

<div class="abstract">
A data structure is a representation plus invariants chosen to support a set of operations. In systems software, asymptotic complexity is only part of the choice: locality, bounded memory, allocation failure, address stability, lock scope, interrupt safety and serialization often matter equally. This chapter develops the structures that recur in kernels, compilers, filesystems, drivers, graphics and emulators, then gives a selection model for deciding among them.
</div>

## Representation, invariant and operation

A structure should be described through three questions:

1. **Representation:** how are elements stored?
2. **Invariant:** what must remain true after every operation?
3. **Operations:** which queries and mutations must be efficient?

For a circular queue, for example, the representation may be a fixed array plus <code>head</code>, <code>tail</code> and <code>count</code>. The invariant states that indices remain inside capacity and count never exceeds capacity. Enqueue and dequeue are then modular index updates.

Without the invariant, the structure is just fields.

## Arrays

An array stores equal-sized elements contiguously.

Core properties:

| Operation | Typical cost |
|---|---:|
| index by position | O(1) |
| sequential traversal | O(n) |
| search unsorted | O(n) |
| insertion/removal in middle | O(n) movement |
| append to fixed free slot | O(1) |

Arrays are dominant in systems code because they provide predictable storage and strong locality. Fixed-capacity arrays also avoid allocator dependency.

Their main weakness is structural rigidity: inserting in the middle or growing beyond capacity can be expensive or impossible.

Kernel tables often deliberately accept O(n) search because n is small, bounded and the representation is simple.

## Dynamic arrays

A dynamic array tracks pointer, length and capacity. When capacity is exhausted, a larger region is allocated and elements are copied.

Geometric growth, often doubling, gives amortized O(1) append. However, an individual grow operation is O(n), allocates memory and invalidates raw pointers to elements.

Those consequences can make a dynamic vector unsuitable for kernel structures whose addresses must remain stable or whose mutation occurs in interrupt context.

## Linked lists

A singly linked node stores payload plus a pointer to the next node. A doubly linked list also stores a previous pointer.

Advantages:

- O(1) insertion/removal when the node or predecessor is already known;
- stable node addresses;
- no need for contiguous storage.

Costs:

- pointer overhead per node;
- poor spatial locality;
- O(n) indexed access and ordinary search;
- allocator dependence unless nodes are embedded or pooled.

A linked list is not automatically the best representation for frequently modified collections. On modern hardware, a compact array can outperform a list despite requiring occasional movement.

## Intrusive lists

Systems software often embeds linkage fields directly into the owning object rather than allocating separate list nodes.

Conceptually:

    struct Task {
        ...
        Task *next;
        Task *prev;
    }

This avoids an extra allocation and can make ownership clearer. The same object may participate in several lists only if it has distinct linkage fields for each role.

The invariant must specify whether a node can be unlinked, linked once, or present in multiple collections.

## Stacks

A stack follows last-in, first-out order.

With an array and stack pointer:

- push: write at top, increment;
- pop: decrement, read;
- both O(1).

The CPU call stack is a specialized stack representation supporting return addresses, saved registers, locals and arguments according to ABI rules.

Stacks are useful when nested operations must unwind in reverse order: parser recursion, traversal, temporary resource rollback and exception frames.

A bounded stack must define overflow behavior; an unbounded conceptual recursion can become a kernel stack overflow.

## Queues

A queue follows first-in, first-out order.

A naive array queue that shifts all elements after dequeue costs O(n). A linked queue avoids movement but requires nodes and pointer chasing. A circular array queue retains O(1) enqueue/dequeue without allocation.

Queues are central to:

- runnable work;
- device commands;
- packets;
- event delivery;
- producer/consumer pipelines.

The queue discipline itself can vary: FIFO, priority, deadline, fair queueing or work stealing.

## Circular buffers and rings

A ring maps monotonically advancing logical positions onto a fixed array with modular arithmetic.

For capacity C:

    next(i) = (i + 1) mod C

Common representations distinguish full from empty using one of:

- a separate count;
- leaving one slot unused;
- monotonic producer/consumer counters wider than the array index;
- generation bits.

Rings are attractive in driver interfaces because producer and consumer can exchange ownership of descriptors without relocating objects.

Memory ordering becomes part of the invariant when producer and consumer run concurrently or one side is a device.

## Deques

A double-ended queue supports insertion and removal from both ends.

Array deques use circular indexing. Linked deques use a doubly linked structure.

Deques appear in work-stealing schedulers: an owner may push/pop one end while thieves take from the other. Correct lock-free implementations require stronger atomic reasoning than ordinary FIFO rings.

## Bitmaps

A bitmap stores one Boolean state per bit.

For resource i:

    byte = i / 8
    bit  = i % 8

Advantages:

- extremely compact;
- fast state test/update;
- good cache density;
- efficient word-level scanning.

Finding a free bit may be O(n) in the number of bits unless hierarchical summaries or hardware bit-scan operations are used.

Bitmaps are natural for physical-page allocation, CPU affinity, descriptor availability and capability sets.

## Sets represented as bitsets

When the universe is small and fixed, a bitset can represent a set more efficiently than a hash table.

Union, intersection and difference become word-level OR, AND and AND-NOT operations.

For 64 possible CPUs, for example, a 64-bit integer can encode membership and allow fast mask operations.

The structure is ideal only when identifiers map densely into a bounded range.

## Hash tables

A hash table maps a key through a hash function into buckets.

Expected lookup can be O(1), but collision handling is required. Major strategies include:

- separate chaining;
- open addressing;
- linear/quadratic probing;
- Robin Hood variants;
- cuckoo hashing.

Systems concerns include deterministic worst case, resize cost, attacker-controlled collision patterns and memory allocation.

A fixed-size open-addressed table can avoid per-entry allocation but needs a load-factor policy and tombstone rules.

## Binary search trees

A binary search tree maintains an ordering invariant:

    keys(left) < key(node) < keys(right)

Lookup follows one branch per comparison.

An unbalanced tree can degenerate to O(n). Balanced trees such as AVL or red-black trees keep height O(log n).

Trees are useful when ordered traversal, predecessor/successor queries or range lookup matter in addition to exact-key search.

## B-trees and B+ trees

Storage systems often use high-fanout trees whose nodes contain many keys.

A B-tree reduces tree height by matching node size to storage or cache blocks. B+ trees commonly store records in leaves and keep internal nodes primarily as routing keys.

For disks or SSD pages, reducing random I/O operations is often more important than minimizing individual comparisons.

Filesystems and databases therefore use structures shaped by block-level cost models.

## Heaps and priority queues

A binary heap is commonly stored in an array. For index i:

    left  = 2i + 1
    right = 2i + 2
    parent = floor((i - 1) / 2)

A min-heap maintains parent <= children.

Typical costs:

| Operation | Cost |
|---|---:|
| inspect minimum | O(1) |
| insert | O(log n) |
| remove minimum | O(log n) |
| build heap | O(n) |

Priority queues are useful for timers, deadline scheduling and event simulation.

A heap is not the same as a memory allocator heap; the name refers to a tree-order property.

## Tries and radix trees

A trie walks components of a key rather than comparing complete keys. Radix trees compress paths.

They are useful for:

- prefix lookup;
- routing tables;
- sparse integer indexes;
- virtual-memory mappings in some systems;
- name lookup.

Their memory footprint and branching factor depend strongly on key representation.

## Graphs

A graph contains vertices and edges. It can be represented by:

- adjacency matrix: O(V²) space, O(1) edge test;
- adjacency lists: O(V+E) space;
- compressed sparse forms.

Graphs model dependency networks, control flow, resource relationships and build systems.

Breadth-first search uses a queue and explores by distance layers. Depth-first search uses recursion or an explicit stack and explores along paths.

Both are O(V+E) with adjacency-list representation.

## Disjoint-set union

Union-find represents a partition of elements into disjoint sets.

Operations:

- find representative;
- union two sets.

Path compression plus union by rank/size yields near-constant amortized performance, formally O(alpha(n)).

It is useful in connectivity problems, clustering and some allocation/graph algorithms.

## Free lists

A free list stores reusable objects or memory blocks in linked form.

Allocation removes an entry; free inserts it back. If all blocks have one size, operations can be O(1).

General-purpose allocators need additional policy when block sizes differ. They may use size classes, boundary tags, segregated lists, trees or buddy systems.

A free list is simple but can fragment memory if the allocation model is not constrained.

## Buddy allocation

A buddy allocator manages power-of-two block sizes. Splitting divides one block into two equal buddies; freeing can coalesce a block with its free buddy.

Allocation and free are typically logarithmic in the range of block orders, with predictable metadata.

The cost is internal fragmentation because requests round up to power-of-two classes.

Buddy systems are common for physical or large-block allocation, though the current ChrisOS PMM uses a bitmap scan rather than a buddy tree.

## Slabs and object caches

A slab allocator reserves pages and divides them into fixed-size objects of a specific class.

Benefits:

- amortized page allocation;
- stable object size;
- reduced fragmentation;
- object reuse;
- potential per-CPU caches.

Slabs are useful for frequently allocated kernel object types such as task descriptors or file objects.

They add metadata and lifecycle complexity compared with a single general heap.

## Arenas

An arena allocates many objects from a region and releases them together.

Allocation can be a simple bump pointer:

    result = cursor
    cursor += aligned_size

This is extremely fast and cache-friendly. Individual free is normally unsupported.

Arenas are effective when lifetimes are naturally grouped, such as parser temporary data or one-shot build phases.

## Sparse versus dense representation

If identifiers occupy most positions in a small range, arrays and bitsets are efficient.

If identifiers are sparse across a huge key space, hash tables, trees or radix structures may use less memory.

The decision should begin with domain size and operation profile, not with familiarity.

## Stable addresses

Some subsystems store pointers to elements. A vector resize can move all elements and invalidate those pointers; a node-based structure keeps node addresses stable.

Stable address requirements often dominate data-structure choice in kernels and device code.

Another option is indirect handles: an object can move internally while a stable table entry remains externally visible.

## Ownership and lifetime

Every structure must define who owns its elements.

Questions include:

- Does insertion transfer ownership?
- Does removal return ownership?
- Can multiple structures reference the same object?
- Are references counted?
- Can an object disappear while readers hold pointers?
- Is reclamation immediate or deferred?

Concurrency makes lifetime harder than lookup complexity.

## Concurrency

A coarse lock around an entire structure is simplest. Fine-grained locks can improve parallelism but create ordering and deadlock problems. Lock-free designs avoid owner blocking but require careful atomic operations and memory reclamation.

Read-copy-update, hazard pointers and epoch reclamation solve specific concurrent read/reclamation problems, but they impose substantial proof burden.

A small operating system should not adopt them merely because they are sophisticated. The workload must justify the complexity.

## Selection matrix

| Requirement | Often suitable |
|---|---|
| tiny bounded table, frequent scan | fixed array |
| O(1) FIFO without allocation | circular queue |
| one bit of state per resource | bitmap |
| ordered dynamic lookup | balanced tree |
| expected fast exact-key lookup | hash table |
| highest-priority item | heap |
| grouped short-lived allocation | arena |
| fixed-size reusable objects | slab/free list |
| block-oriented ordered index | B-tree/B+ tree |
| prefix lookup | trie/radix tree |

This is not a rule table. Concurrency, failure semantics and locality can reverse a choice.

## The systems principle

A data structure is good when it makes the important invariants easy to preserve under the actual constraints.

The simplest correct bounded array can be superior to an asymptotically faster dynamic structure if it:

- fits known scale;
- avoids allocation;
- keeps addresses stable;
- reduces lock complexity;
- improves locality;
- makes failure explicit.

The following chapter maps these ideas onto the concrete structures and algorithms present in the current ChrisOS main branch.
