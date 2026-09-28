---
id: graphs-union-find
lang: en
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/gfx/shader/sh_int.h
  - kernel/gfx/shader/sh_sem.c
  - kernel/fs/cfs.c
symbols:
  - ShComp
  - scope_parent
  - scope_has
  - push_scope
  - pop_scope
  - dir_find
  - walk_full
depends_on:
  - arrays-lists-stacks-queues
  - trees-heaps-tries
  - algorithmic-complexity
  - proof-invariants-induction
related:
  - bitmaps-rings-free-lists
  - graph-algorithms
  - systems-algorithms
  - string-parsing-algorithms
---

# Graphs, connectivity and union-find

<div class="abstract">
Graphs model arbitrary relationships rather than a single hierarchy. Their correctness and cost depend on the exact representation of vertices and edges, whether edges are directed or weighted, and which invariants are required by the subsystem. Union-find, also called disjoint-set union, solves a narrower problem: maintain a partition of elements under repeated merge and connectivity queries. This chapter develops graph models, adjacency representations, reachability, components, cycles, directed acyclic graphs and disjoint-set forests with path compression and union by rank or size. It also draws a strict boundary around current ChrisOS source. The shader semantic analyzer stores lexical scopes through a parent array, and ChrisFS walks a rooted directory hierarchy. Both are tree-shaped special cases, not general graph containers and not union-find. No reusable graph or disjoint-set implementation is established by the reviewed revision, so those algorithms are documented here as foundations rather than attributed to ChrisOS.
</div>

## Why graphs are different from trees

A tree imposes strong structure:

- one root;
- every non-root node has exactly one parent;
- no cycles;
- exactly one simple path between connected nodes.

A graph removes some or all of those restrictions.

A graph is usually written:

~~~text
G = (V, E)
~~~

where:

- V is the set of vertices;
- E is the set of edges.

For an undirected graph, an edge {u, v} has no direction.

For a directed graph, an edge is an ordered pair:

~~~text
(u, v)
~~~

meaning an arc from u to v.

Graphs can model:

- hardware topology;
- dependency relations;
- control flow;
- call relations;
- networks;
- filesystem links;
- scene dependencies;
- resource ownership;
- routing;
- synchronization dependencies.

The important point is that the graph model must come from real subsystem semantics, not merely because the source contains pointers.

## Vocabulary and invariants

Important terms include:

| Term | Meaning |
|---|---|
| vertex | object represented as a node |
| edge | relationship between vertices |
| path | sequence of adjacent vertices |
| cycle | path returning to its start without trivial repetition |
| connected component | maximal connected set in an undirected graph |
| strongly connected component | directed set in which every vertex reaches every other |
| degree | number of incident edges |
| indegree | incoming directed edges |
| outdegree | outgoing directed edges |
| DAG | directed acyclic graph |
| forest | disjoint collection of trees |

A representation is correct only if its stored state preserves the intended edge semantics.

For example, an undirected edge normally requires symmetric adjacency:

~~~text
v in adj[u]
u in adj[v]
~~~

unless the implementation uses a canonical single-edge record.

## Adjacency matrix

For n vertices, an adjacency matrix stores:

~~~text
A[u][v]
~~~

as a bit, Boolean, weight or edge record.

For an unweighted directed graph:

~~~text
A[u][v] = 1  iff  edge u -> v exists
~~~

Memory cost is:

~~~text
Theta(n^2)
~~~

Advantages:

- O(1) edge-existence query;
- simple representation;
- good for dense graphs;
- bit matrices can exploit word-level operations.

Disadvantages:

- wasteful for sparse graphs;
- enumerating neighbors costs O(n) per vertex;
- resizing is expensive.

Systems software frequently handles sparse topology, so an adjacency matrix is not automatically appropriate.

## Adjacency lists

An adjacency-list representation associates each vertex with its outgoing neighbors.

Conceptually:

~~~text
adj[0] -> 1, 4
adj[1] -> 2
adj[2] -> 0, 3
...
~~~

Memory for a graph with n vertices and m directed edges is:

~~~text
Theta(n + m)
~~~

assuming one stored adjacency entry per edge.

For an undirected graph represented symmetrically, the adjacency entries usually total 2m.

Advantages:

- efficient sparse storage;
- neighbor iteration proportional to degree;
- natural for traversal algorithms.

Costs:

- edge-existence query can require scanning a neighbor set;
- pointer-based lists have poor locality;
- mutation and synchronization can be more complex.

The "list" in adjacency list need not be a linked list. It can be a vector, fixed array, hash set, sorted array or compressed index range.

## Edge lists

An edge list stores pairs:

~~~text
(u0, v0)
(u1, v1)
...
~~~

This is compact and simple for batch algorithms.

It is useful when the main operation is to scan or sort all edges, as in Kruskal's minimum-spanning-tree algorithm.

It is poor for repeated neighborhood queries unless an additional index exists.

## Weighted graphs

A weighted edge carries a value:

~~~text
(u, v, w)
~~~

The meaning of w is subsystem-specific:

- latency;
- cost;
- distance;
- capacity;
- probability;
- priority.

A weight is not necessarily a geometric distance.

Algorithms must state whether weights may be negative, whether parallel edges exist and whether overflow is possible when accumulating path cost.

## Paths and reachability

A path from s to t is a sequence:

~~~text
s = v0, v1, ..., vk = t
~~~

where each consecutive pair is connected by an appropriate edge.

Reachability asks whether at least one path exists.

In an unweighted graph, breadth-first search also gives shortest path by number of edges.

Depth-first search is useful for structural traversal, cycle detection and component discovery.

Detailed traversal and shortest-path algorithms belong to the later graph-algorithms chapter. Here the focus is representation and invariants.

## Cycles

Cycles matter because many systems relationships must be acyclic.

Examples:

- build dependencies;
- initialization ordering;
- ownership trees;
- parent-scope relations.

For a DAG, topological ordering exists.

If a supposedly hierarchical structure develops a cycle, recursive traversal may fail to terminate or loop until a guard trips.

This is why parent-chain code often needs a depth bound even when cycles should be impossible.

## Graphs versus parent arrays

A parent array:

~~~text
parent[v] = p
~~~

can encode a rooted tree or forest when each element has at most one parent.

It is much narrower than a general graph because each vertex has only one stored incoming parent relation.

This exact distinction appears in the shader compiler.

## ChrisC shader scope hierarchy

The shader compiler's ShComp contains:

~~~text
int cur_scope;
int nscope;
int scope_parent[SH_SCOPE_MAX];
~~~

push_scope creates a new scope id and records:

~~~text
scope_parent[new] = cur_scope
cur_scope = new
~~~

pop_scope moves back to the parent:

~~~text
cur_scope = scope_parent[cur_scope]
~~~

This representation forms a lexical-scope parent tree while scopes are created under the current scope.

It is not a generic graph.

There is no adjacency list and no ability for one scope to have multiple parents.

## Guarded scope ancestry lookup

scope_has starts from cur_scope and repeatedly follows:

~~~text
scope_parent[s]
~~~

until it reaches scope zero or a guard reaches SH_SCOPE_MAX.

The guard bounds traversal even if state becomes inconsistent.

The normal semantic invariant is:

~~~text
each non-root scope points to an earlier ancestor scope
~~~

This makes the scope relation acyclic.

The code is a concrete example of a parent-linked tree, not union-find.

## Why shader scopes are not union-find

Union-find parent pointers have different semantics.

In DSU:

~~~text
parent[x]
~~~

means "the next representative link in the disjoint-set forest."

The root represents an equivalence class.

Path compression is allowed to rewrite parent[x] directly to the representative because intermediate hierarchy has no semantic meaning.

Shader lexical scopes are different.

The chain:

~~~text
scope 7 -> scope 4 -> scope 1 -> scope 0
~~~

encodes actual nesting.

Replacing scope 7's parent directly with scope 0 would destroy lexical ancestry information and change name visibility.

Therefore the existence of a parent array does not imply DSU.

## ChrisFS hierarchy as another special case

ChrisFS path traversal starts at CFS_ROOT_INODE.

walk_full resolves components one at a time using dir_find and advances to the child inode.

This exposes a rooted namespace relation.

At the reviewed revision, directory lookup is a linear scan of directory blocks and entries.

The namespace is hierarchical, but this source does not establish a reusable graph container.

Filesystems can become graph-like when they support hard links, mount graphs or other multi-parent relationships, but such properties must be established from actual format and implementation semantics before making that claim.

## Connected components

For an undirected graph, vertices u and v are in the same connected component if a path exists between them.

Connectivity can be answered by graph traversal if the graph is static:

1. start from an unvisited vertex;
2. visit every reachable vertex;
3. label them with one component id;
4. repeat for remaining vertices.

That costs O(V + E) for adjacency-list representation.

But repeated online connectivity queries under edge additions motivate a different structure: union-find.

## The disjoint-set abstraction

Union-find maintains a partition of elements.

Core operations:

~~~text
make_set(x)
find(x)
union(a, b)
~~~

Semantics:

- make_set(x): x starts in its own set;
- find(x): returns a representative for x's current set;
- union(a, b): merges the two sets if they differ.

Connectivity query:

~~~text
find(a) == find(b)
~~~

The representative's numeric value has no inherent semantic meaning. It is an implementation-selected label.

## Forest representation

A common DSU stores:

~~~text
parent[i]
rank[i]   or   size[i]
~~~

Initially:

~~~text
parent[i] = i
rank[i] = 0
~~~

Each set is represented by a rooted tree.

A root satisfies:

~~~text
parent[root] = root
~~~

find follows parent pointers to the root.

Naively, repeated unions can create long chains and O(n) finds.

Two optimizations solve this.

## Path compression

A recursive find can be written conceptually:

~~~text
find(x):
    if parent[x] != x:
        parent[x] = find(parent[x])
    return parent[x]
~~~

After the operation, nodes on the search path point much closer to the root.

Example before:

~~~text
7 -> 5 -> 3 -> 1
               ^ root
~~~

After find(7):

~~~text
7 ─┐
5 ─┼──> 1
3 ─┘
~~~

The partition is unchanged. Only representation is flattened.

This rewrite is valid because intermediate DSU parent relationships carry no external meaning.

## Union by rank

Union by rank attaches the shallower representative under the deeper representative.

Conceptually:

~~~text
ra = find(a)
rb = find(b)

if ra == rb:
    return

if rank[ra] < rank[rb]:
    parent[ra] = rb
else if rank[ra] > rank[rb]:
    parent[rb] = ra
else:
    parent[rb] = ra
    rank[ra]++
~~~

Rank is an upper-bound style structural measure, not necessarily exact height after path compression.

## Union by size

An alternative stores set size.

The smaller tree is attached under the larger root:

~~~text
if size[ra] < size[rb]:
    swap(ra, rb)

parent[rb] = ra
size[ra] += size[rb]
~~~

This also prevents pathological growth.

Rank and size are alternative heuristics. A structure usually chooses one.

## Complexity of optimized DSU

With both path compression and union by rank or size, a sequence of m operations on n elements has near-linear total cost.

The standard amortized bound is:

~~~text
O(m alpha(n))
~~~

where alpha is the inverse Ackermann function.

For all realistic system sizes, alpha(n) is extremely small.

The important point is not that each individual find is strict O(1). The guarantee is an amortized bound across a sequence.

## DSU invariants

A robust implementation should preserve:

- every parent index is in range;
- each forest has exactly one self-parent root;
- following parent pointers terminates;
- rank/size metadata is meaningful only at roots unless otherwise specified;
- union never splits sets;
- find returns equal representatives exactly for elements in the same partition.

With size-based union:

~~~text
size[root] = number of members in that set
~~~

should remain true.

Non-root size entries may be stale if the implementation does not maintain them.

## Why DSU is not a general graph representation

Union-find answers connectivity under set merges.

It does not retain the original graph edges.

After:

~~~text
union(A, B)
union(B, C)
~~~

the DSU knows A, B and C are connected.

It cannot tell whether the original edges were:

~~~text
A-B and B-C
~~~

or:

~~~text
A-C and B-C
~~~

or many other possibilities.

DSU therefore cannot replace an adjacency representation when path reconstruction, degree, neighbors or edge identity matter.

## Typical systems uses

Potential systems uses include:

- grouping physical or virtual resources into equivalence classes;
- Kruskal-style spanning-tree construction;
- incremental connectivity in topology discovery;
- alias/equivalence analysis;
- connected-component merging;
- image/region labeling.

These are design examples, not claims about current ChrisOS subsystems.

The reviewed revision contains no reusable DSU implementation.

## Memory layout

For n elements, a compact DSU can use two arrays:

~~~text
parent[n]
rank[n]
~~~

or:

~~~text
parent[n]
size[n]
~~~

With 32-bit parent and size:

~~~text
8n bytes
~~~

before alignment or auxiliary state.

The arrays provide good locality compared with pointer-allocated nodes.

If n is bounded below 65536, smaller index widths may be possible, but truncation limits must be explicit.

## Failure and corruption behavior

Graph structures can fail through:

- out-of-range vertex ids;
- duplicate or inconsistent edges;
- dangling adjacency references;
- unintended cycles;
- stale edge indexes;
- capacity exhaustion.

DSU-specific failures include:

- parent cycles without a self-root;
- invalid parent index;
- rank/size corruption;
- union of uninitialized elements;
- races that lose a parent update.

A parent cycle such as:

~~~text
1 -> 2 -> 3 -> 1
~~~

causes find to loop unless guarded.

Debug builds can validate roots and range constraints.

## Concurrency

Naive DSU mutation is not thread-safe.

Two concurrent unions can race on:

- parent roots;
- rank;
- size.

A coarse lock around all operations is simplest.

More scalable concurrent union-find algorithms use atomic compare-and-swap and carefully designed linking rules.

Path compression itself is a write operation even during a logically read-like find.

That matters when designing read concurrency.

Graph adjacency mutation similarly needs an ownership model:

- single writer;
- coarse graph lock;
- per-vertex locks;
- immutable snapshots;
- RCU-style publication.

The correct strategy depends on read/write ratio and consistency requirements.

## Security and adversarial complexity

Graphs expose resource-amplification risks.

An untrusted input can construct:

- very high-degree vertices;
- extremely deep DFS paths;
- huge edge counts;
- pathological duplicate edges;
- cycles where acyclicity was assumed.

Defensive parsers therefore need:

- vertex/edge count limits;
- range validation;
- traversal budgets;
- visited state for potentially cyclic graphs;
- overflow checks for n + m memory calculations.

DSU's optimized asymptotic performance is robust, but the implementation still needs bounds validation.

## Validation model for this chapter

The deterministic checker accompanying this chapter verifies:

- adjacency-list and adjacency-matrix agreement on a small graph;
- connected-component labeling;
- directed versus undirected edge semantics;
- cycle detection on parent chains;
- DSU make/find/union behavior;
- union by size;
- path compression;
- representative equivalence;
- partition-size preservation;
- current shader-source anchors for scope_parent, scope_has, push_scope and pop_scope;
- current ChrisFS path-walk anchors.

It also verifies the implementation boundary: the reviewed source shows parent-linked scope and path hierarchies, not a reusable DSU API.

## Current ChrisOS boundary

At revision da3df29cb397932c43d32373871fb9380e688ade, the inspected source demonstrates:

- shader lexical scopes stored as a bounded parent hierarchy;
- ChrisFS paths resolved as a rooted hierarchy.

It does not establish a reusable current implementation of:

- adjacency list;
- adjacency matrix;
- generic graph object;
- disjoint-set union;
- path compression;
- union by rank;
- union by size.

Those concepts are therefore presented as required foundations for later graph algorithms and future subsystem designs, not as implemented ChrisOS features.

## Relationship to later chapters

This chapter establishes representation and connectivity.

The later graph-algorithms chapter can then build on:

- BFS;
- DFS;
- topological sorting;
- strongly connected components;
- shortest paths;
- minimum spanning trees.

Union-find is introduced here because its representation and invariants are a fundamental data-structure topic even though one of its classic uses, Kruskal's algorithm, belongs to graph algorithms.

## Revision provenance

Implementation-facing statements were reconciled against ChrisOS main revision da3df29cb397932c43d32373871fb9380e688ade.

Reviewed source:

- kernel/gfx/shader/sh_int.h;
- kernel/gfx/shader/sh_sem.c;
- kernel/fs/cfs.c.

Reviewed symbols and state:

- ShComp.scope_parent;
- SH_SCOPE_MAX;
- scope_has;
- push_scope;
- pop_scope;
- dir_find;
- walk_full;
- CFS_ROOT_INODE.

The boundary is intentional: specialized trees must not be relabeled as arbitrary graphs, and ordinary parent arrays must not be relabeled as union-find unless representative semantics and union/find operations exist.
