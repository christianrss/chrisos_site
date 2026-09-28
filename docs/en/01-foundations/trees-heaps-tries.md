---
id: trees-heaps-tries
lang: en
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - compiler/chrisc/chrisc.c
  - kernel/fs/cfs.c
  - kernel/metal/heap.c
symbols:
  - Node
  - Compiler
  - node
  - gen_expr
  - dir_find
  - walk_parent
  - walk_full
  - kmalloc
  - kfree
depends_on:
  - arrays-lists-stacks-queues
  - recursion-recurrences-amortization
related:
  - hash-tables
  - graphs-union-find
  - string-parsing-algorithms
  - compiler-pipeline
  - chrisfs
---

# Trees, binary heaps and tries

<div class="abstract">
Trees represent hierarchical relationships, binary heaps impose a partial order over a complete tree, and tries organize keys by shared prefixes. These structures solve different problems even though they may all be drawn as branching diagrams. This chapter develops rooted trees, traversal, binary search trees, balancing, priority heaps, tries, compressed radix trees, complexity, memory representation, failure modes and concurrency. It then maps the theory onto current ChrisOS source without inventing structures that do not exist. ChrisC stores its AST in a fixed contiguous Node array with integer child links left, right and third plus next links for sibling/statement chains; that is a real indexed syntax tree, not a binary-search tree. ChrisFS exposes a rooted path hierarchy, but each path component is found by a linear directory scan rather than a balanced search tree or trie. The kernel file named heap.c is a memory allocator built from arenas and sequential blocks; it is not a binary heap or priority queue.
</div>

## Prerequisites and scope

This chapter assumes arrays, linked structures, recursion and complexity analysis.

Three families are covered:

- **trees:** hierarchical parent/child relationships;
- **binary heaps:** complete binary trees satisfying an order invariant;
- **tries:** trees whose edges encode key prefixes.

The same word "heap" is also used for dynamic memory allocation. That usage is unrelated to the binary-heap data structure.

This distinction matters in ChrisOS because:

~~~text
kernel/metal/heap.c
~~~

implements the kernel's dynamic-memory allocator, not a priority heap.

## Rooted trees

A rooted tree contains:

- one root;
- zero or more child edges from each node;
- exactly one parent for every non-root node;
- no cycles;
- exactly one simple path from the root to each node.

Terminology:

| Term | Meaning |
|---|---|
| root | node with no parent |
| parent | immediate predecessor |
| child | immediate descendant |
| leaf | node with no children |
| depth | edges from root to node |
| height | longest downward path to a leaf |
| subtree | node plus all descendants |
| sibling | nodes sharing a parent |

If cycles are allowed, the structure is a graph rather than a tree.

## Tree size, height and shape

A tree may contain n nodes but have very different heights.

A chain has:

~~~text
height = n - 1
~~~

A balanced binary tree has height:

~~~text
Theta(log n)
~~~

Many tree operations are O(h), where h is height.

Therefore shape is part of the cost model.

The statement "tree lookup is O(log n)" is only justified when a balancing or shape invariant ensures logarithmic height.

## Tree representations

Common representations include:

- pointers from parent to children;
- parent pointers;
- first-child/next-sibling links;
- arrays of child indices;
- fixed child fields such as left/right;
- implicit arithmetic indices, as in binary heaps.

Systems code often prefers indices over pointers when:

- storage is in a fixed pool;
- serialization matters;
- objects may move as a block;
- bounds checking is useful;
- pointer width would be wasteful.

## Indexed trees

Suppose nodes live in:

~~~text
Node nodes[N]
~~~

and child references are integer indices.

A sentinel such as -1 means "no child".

Useful invariants are:

~~~text
child == -1
or
0 <= child < nnode
~~~

and, for a true tree:

- every node except root has one parent;
- no child edge creates a cycle;
- every reachable child points to a live node;
- root is reachable from the owning object.

An invalid index is the indexed equivalent of a bad pointer.

## Tree traversal

Depth-first traversal can be:

- preorder: node, children;
- inorder: left, node, right for binary trees;
- postorder: children, node.

Breadth-first traversal visits nodes level by level.

Recursive DFS uses O(h) call-stack space.

Iterative DFS uses an explicit stack.

BFS uses a queue and may require O(w) space where w is maximum width.

All complete traversals are Theta(n) in the number of visited nodes.

## ChrisC AST representation

The current ChrisC compiler defines:

~~~text
#define NODE_MAX 131072

typedef struct Node {
    NodeKind kind;
    int left, right, third, next;
    ...
} Node;
~~~

Compiler contains:

~~~text
Node nodes[NODE_MAX];
int nnode;
~~~

node allocates the next slot and initializes:

~~~text
left = right = third = next = -1
~~~

This is an indexed node pool.

The relationships are not C pointers; they are integer indices into the same Compiler-owned array.

## AST semantics

The fields have syntactic meaning depending on NodeKind.

Typical expression nodes use:

- left for the first operand;
- right for a second operand;
- third for ternary or additional state;
- next for chains such as statements or argument-like sequences.

The AST is therefore not necessarily a strict binary tree in representation.

It is better described as:

~~~text
indexed syntax tree + linked sibling/list chains
~~~

Some nodes have one child, some two, some three, and some participate in next chains.

## AST ownership

All Node storage belongs to one Compiler instance.

Consequences:

- child indices are meaningful only within that instance;
- no per-node heap allocation is required;
- nodes are physically contiguous;
- NODE_MAX bounds total AST size;
- node addresses remain stable while Compiler storage itself remains stable.

The node function rejects allocation when:

~~~text
nnode == NODE_MAX
~~~

with an AST-full error.

That turns unbounded syntax growth into explicit bounded failure.

## AST traversal in code generation

gen_expr consumes a node id and recursively generates code for child expressions.

For binary operations, the usual pattern is conceptually:

~~~text
generate(left)
generate(right)
emit(operator)
~~~

This is a postorder-like traversal for expression evaluation.

The runtime cost for a well-formed expression tree is proportional to visited nodes plus operation-specific work.

Peak host recursion depends on expression depth, not total AST size.

The AST representation therefore connects directly to the previous chapter on recursion.

## Trees are not automatically search trees

A general syntax tree does not satisfy:

~~~text
keys(left subtree) < key(node) < keys(right subtree)
~~~

That invariant belongs to a binary search tree.

ChrisC's AST left/right fields encode syntax operands, not ordered-key partitions.

Therefore the presence of left and right fields is not evidence of a BST.

Classification must follow invariants, not field names.

## Binary search trees

A BST associates an ordered key with each node.

Invariant:

~~~text
all keys in left subtree < node key
all keys in right subtree > node key
~~~

or another explicitly defined duplicate-key policy.

Lookup, insertion and deletion cost:

~~~text
O(h)
~~~

where h is tree height.

If insertion order creates a chain, h can become n.

An ordinary unbalanced BST therefore has worst-case O(n) operations.

## Balanced trees

Self-balancing trees maintain height constraints during mutation.

Examples include:

- AVL trees;
- red-black trees;
- B-trees and B+ trees.

AVL maintains a stricter height-balance relation.

Red-black trees encode color invariants that keep height O(log n) with fewer structural constraints.

B-trees use many keys per node to match block/cache geometry and reduce tree height.

The correct tree depends on the workload: exact lookup, ordered iteration, range queries, persistent storage or cache locality.

## Rotations

Balanced binary trees repair local shape using rotations.

A right rotation transforms:

~~~text
        y                x
       / \              / \
      x   C    ->       A   y
     / \                  / \
    A   B                B   C
~~~

while preserving inorder key order.

Rotations change parent/child links but not the sorted sequence.

In pointer-based kernels they also require careful ownership and synchronization.

ChrisOS's reviewed sources do not currently establish a generic AVL or red-black tree implementation.

## Binary heaps

A binary heap is not a BST.

It satisfies two properties:

1. **shape:** complete binary tree;
2. **order:** parent dominates children.

For a min-heap:

~~~text
parent <= child
~~~

For a max-heap:

~~~text
parent >= child
~~~

Only the root is guaranteed globally minimal or maximal.

Searching for an arbitrary key is still O(n).

## Array representation of a heap

A complete binary tree maps naturally into an array.

With zero-based index i:

~~~text
parent(i) = floor((i - 1) / 2)
left(i)   = 2i + 1
right(i)  = 2i + 2
~~~

No child pointers are needed.

This gives excellent locality and compact storage.

The active heap is usually the prefix:

~~~text
a[0:n]
~~~

of the backing array.

## Heap insertion

To insert x into a min-heap:

1. append x at index n;
2. increment n;
3. compare with parent;
4. while x is smaller than parent, swap upward.

This is sift-up.

Height is O(log n), so insertion is O(log n).

Peek-min is O(1) because the root is a[0].

## Remove-min

For a min-heap:

1. save root;
2. move last element into root;
3. decrement n;
4. repeatedly swap the replacement with its smaller child while order is violated.

This is sift-down.

Complexity is O(log n).

A priority queue is commonly implemented using a heap because it needs fast access to the highest-priority element, not arbitrary ordered search.

## Build-heap

Repeated insertion of n items costs O(n log n).

Bottom-up heap construction can do better.

Starting from the last internal node and sifting down each internal node yields:

~~~text
Theta(n)
~~~

build time.

The reason is that most nodes are near leaves and travel only a short distance.

This is a useful example where summing per-node heights gives a tighter result than multiplying n by worst-case height.

## The ChrisOS kernel heap is not a binary heap

kernel/metal/heap.c defines:

~~~text
struct heap_block {
    uint64_t size;
    uint32_t used;
    ...
}

struct heap_arena {
    uint8_t *base;
    uint64_t limit;
}
~~~

kmalloc_in_arenas linearly walks blocks inside arenas looking for a free block with sufficient size.

The allocator:

- splits free blocks;
- marks blocks used;
- grows by adding arenas;
- coalesces forward on free;
- protects state with heap_lock.

This is a dynamic memory heap in the allocator sense.

There is no:

- complete binary-tree shape;
- parent/child index formula;
- sift-up;
- sift-down;
- min/max root invariant.

Calling it a binary heap would be technically wrong.

## Allocator complexity versus priority-heap complexity

The naming overlap can hide different costs.

Current kmalloc search is based on scanning arenas and blocks until a fitting free block is found.

That is not O(log n) because no balanced tree or binary priority heap indexes free blocks in the reviewed code.

By contrast, binary heap insertion/removal are O(log n) due to tree height.

The chapter therefore keeps allocator theory and binary-heap theory separate.

## Tries

A trie stores keys by prefixes.

For keys:

~~~text
car
cat
dog
~~~

a character trie can share:

~~~text
c
└─ a
   ├─ r
   └─ t

d
└─ o
   └─ g
~~~

Lookup follows one edge per key unit.

For key length L, complexity is often:

~~~text
O(L)
~~~

independent of the number of stored keys, assuming child selection is bounded appropriately.

## Trie node representation

A trie node may store children as:

- fixed fanout array;
- sorted vector;
- linked list;
- hash map;
- balanced tree;
- bitmap plus compact child array.

The best choice depends on alphabet size and sparsity.

For ASCII byte keys, a 256-pointer child array offers direct O(1) edge selection but large memory overhead.

Sparse representations use less memory but add child-search work.

## Prefix semantics

A trie must distinguish:

~~~text
key ends here
~~~

from:

~~~text
prefix continues
~~~

For example, if both "net" and "network" exist, the node after t must record that "net" is a complete key while still having child edges.

Without an end marker or stored value, prefixes cannot be distinguished from complete keys.

## Compressed tries and radix trees

Path compression merges chains with one child.

Instead of:

~~~text
c -> o -> m -> p -> i -> l -> e -> r
~~~

a radix node can store a longer edge label such as:

~~~text
"compiler"
~~~

This reduces node count and pointer overhead.

Patricia tries are a related compressed representation, often defined over bits.

Radix structures are useful for:

- route tables;
- prefix matching;
- path indexes;
- symbol/name dictionaries;
- IP prefixes.

The reviewed ChrisOS source does not establish a generic trie/radix implementation.

## ChrisFS namespace as a rooted hierarchy

ChrisFS paths are hierarchical.

walk_full begins at:

~~~text
CFS_ROOT_INODE
~~~

and processes path components in order.

For each component it calls dir_find, reads the resulting inode, verifies intermediate nodes are directories, checks walk permission, then advances cur to the child inode.

Conceptually:

~~~text
root
  ↓ component 0
directory
  ↓ component 1
directory
  ↓ component 2
target
~~~

This is a rooted namespace traversal.

However, the on-disk directory lookup is not implemented as a trie or balanced search tree.

## ChrisFS directory lookup cost

dir_find loops through directory blocks and each directory-entry slot until a matching name is found.

The comparison checks name length and bytes.

Therefore one path component lookup is a linear scan over the directory entries represented by the scanned blocks.

For a path with d components and directory populations k1, k2, ..., kd, a simplified comparison-work model is:

~~~text
O(k1 + k2 + ... + kd)
~~~

plus storage/cache access costs.

This is different from:

- O(log k) balanced-tree directory indexing;
- O(L) trie lookup by total path characters.

The logical namespace is tree-shaped while the per-directory search algorithm is linear.

## Tree shape versus storage representation

A filesystem can expose a tree to users without storing one monolithic pointer tree in memory.

ChrisFS represents directory membership through directory entries containing inode identifiers.

walk_full reconstructs the path relation dynamically by following those entries from the root.

This illustrates an important principle:

~~~text
abstract data model != physical storage representation
~~~

A hierarchical API does not imply a generic tree container underneath.

## Failure behavior in hierarchical lookup

Tree-like traversal can fail because:

- path component is absent;
- intermediate inode is not a directory;
- permission check fails;
- referenced inode is outside valid range;
- directory data is corrupt;
- depth exceeds parser/path limits;
- cycle exists in corrupted metadata even though a tree was intended.

ChrisFS explicitly rejects non-directory intermediate components and invalid inode ranges in dir_find.

A complete filesystem consistency proof belongs to the ChrisFS chapters and fsck validation, not this foundation chapter.

## Security considerations

Tree, heap and trie implementations can expose different attack surfaces.

Trees:

- pathological unbalanced height;
- recursion-depth exhaustion;
- invalid/cyclic links;
- use-after-free during mutation.

Priority heaps:

- capacity overflow;
- incorrect comparator;
- stale position indices;
- synchronization bugs during swaps.

Tries:

- memory amplification from sparse prefixes;
- adversarially long keys;
- Unicode/canonicalization ambiguity;
- deep traversal.

Bounds, canonicalization and ownership need to be explicit in systems code.

## Concurrency

Mutable trees are harder to synchronize than flat arrays because one operation may modify multiple links.

Balanced-tree insertion may update:

- parent;
- child;
- grandparent;
- colors/balance metadata.

Priority-heap mutation swaps multiple array locations.

Trie mutation can allocate a path of nodes.

Approaches include:

- one coarse lock;
- lock coupling;
- immutable/persistent nodes;
- read-copy-update;
- versioned structures;
- thread confinement.

The reviewed ChrisC AST is built and consumed as compiler-owned state; this chapter does not claim concurrent AST mutation support.

ChrisFS has its own filesystem locking contract, documented in the storage chapters.

## Performance and locality

Tree performance depends not just on O(h) but node layout.

Pointer trees can cause:

- cache misses;
- TLB misses;
- allocator fragmentation.

Array-indexed ASTs improve density.

Binary heaps are especially cache-friendly because the complete tree is contiguous.

Tries can be memory-heavy because fanout metadata may dominate payload.

Compressed radix representations trade more key comparisons per node for fewer nodes.

## Selection guide

| Requirement | Typical candidate |
|---|---|
| exact unordered lookup | hash table |
| ordered lookup/range queries | balanced search tree |
| minimum/maximum priority | binary heap |
| prefix lookup | trie/radix tree |
| syntax hierarchy | general tree/AST |
| filesystem namespace | rooted hierarchy, storage-specific indexing |
| ordered persistent block index | B-tree/B+ tree |

The representation should follow operations and invariants, not terminology.

## Validation evidence

The chapter-specific deterministic checker validates:

- indexed-tree child bounds and traversal;
- preorder/inorder/postorder models;
- BST ordering and unbalanced worst-case height;
- binary-heap parent/child index equations;
- min-heap insertion, peek and remove;
- bottom-up heap construction;
- trie insertion/exact lookup/prefix behavior;
- current ChrisC source anchors for NODE_MAX, Node.left/right/third/next, node initialization and gen_expr;
- ChrisFS anchors for CFS_ROOT_INODE, dir_find linear block/slot scanning, walk_parent and walk_full;
- kernel allocator anchors showing heap_block/heap_arena scanning, split/coalesce and absence of a binary-heap contract.

These deterministic models verify the concepts and source classification. They do not prove the complete compiler AST, filesystem consistency or allocator.

## Current implementation boundary

At revision da3df29cb397932c43d32373871fb9380e688ade the reviewed source establishes:

- an indexed ChrisC syntax tree;
- a hierarchical ChrisFS namespace with linear per-directory lookup;
- a kernel dynamic-memory allocator named heap.

The reviewed source does not establish a reusable:

- binary search tree;
- AVL tree;
- red-black tree;
- B-tree;
- binary priority heap;
- trie;
- radix tree.

Those structures are therefore documented as foundations and possible future representations, not current ChrisOS implementations.

## Roadmap boundary

The curriculum continues:

~~~text
hash tables
      ↓
trees / heaps / tries
      ↓
graphs / union-find
      ↓
bitmaps / rings / free lists
      ↓
systems algorithms
~~~

The next stage generalizes from acyclic hierarchies to arbitrary graph relationships and disjoint-set connectivity.

## Revision provenance

Implementation-facing statements were reconciled against ChrisOS main revision da3df29cb397932c43d32373871fb9380e688ade.

Reviewed sources:

- compiler/chrisc/chrisc.c;
- kernel/fs/cfs.c;
- kernel/metal/heap.c.

Reviewed symbols/state:

- Node;
- Compiler;
- node;
- gen_expr;
- NODE_MAX;
- dir_find;
- walk_parent;
- walk_full;
- CFS_ROOT_INODE;
- heap_block;
- heap_arena;
- kmalloc;
- kfree.

The classifications in this chapter are intentionally strict: left/right AST fields do not imply a BST, a hierarchical filesystem namespace does not imply a trie, and a dynamic-memory heap is not a binary priority heap.
