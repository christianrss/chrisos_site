---
id: graph-algorithms
lang: en
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - tools/check_test_gates.py
  - makefile
symbols:
  - ROOTS
  - main
  - rules
  - seen
  - stack
  - host-gates
depends_on:
  - graphs-union-find
  - arrays-lists-stacks-queues
  - trees-heaps-tries
  - algorithmic-complexity
  - sorting-searching
related:
  - systems-algorithms
  - string-parsing-algorithms
  - proof-invariants-induction
---

# Graph algorithms for systems software

<div class="abstract">
Graph algorithms turn a graph representation into answers about reachability, ordering, components, paths and spanning structure. Their correctness depends on edge direction, weights, cycle policy, queue/stack discipline and the meaning of visited state. This chapter develops breadth-first search, depth-first search, topological sorting, strongly connected components, shortest paths, minimum spanning trees and their systems-oriented failure modes. It also reconciles those foundations with current ChrisOS source. tools/check_test_gates.py parses Makefile targets into a directed dependency graph and performs an explicit LIFO stack traversal from host-gates, recording a seen set and reporting test targets that are not reachable. That is a concrete depth-first-style reachability algorithm. It is not topological sorting, cycle detection, shortest-path search or a general graph library. The reviewed source therefore supports one specific graph traversal while the broader algorithms remain foundational material for later subsystem design.
</div>

## Graph algorithm inputs

An algorithm is meaningful only after the graph contract is fixed.

For:

~~~text
G = (V, E)
~~~

the implementation must know:

- directed or undirected;
- weighted or unweighted;
- simple graph or multigraph;
- whether self-loops are legal;
- whether vertices are dense integer ids or arbitrary objects;
- whether the graph is static during traversal;
- whether unreachable vertices are errors or valid state.

The same edge list can produce different answers under different semantics.

A dependency edge:

~~~text
target -> prerequisite
~~~

is directed.

A physical-link edge between two peers may be undirected.

## Traversal state

Most traversal algorithms require at least:

~~~text
frontier
visited
~~~

The frontier determines which discovered vertex is processed next.

A queue gives breadth-first order.

A stack gives depth-first order.

Visited state prevents repeated work, infinite traversal around cycles and duplicate discovery.

Visited timing matters. Marking on discovery normally avoids inserting the same vertex into the frontier multiple times. Marking only when removed can create duplicates and larger memory use.

## Breadth-first search

BFS explores the graph by distance in number of edges from a source.

Conceptual algorithm:

~~~text
visited[s] = true
distance[s] = 0
queue.push(s)

while queue not empty:
    u = queue.pop_front()
    for v in adj[u]:
        if not visited[v]:
            visited[v] = true
            distance[v] = distance[u] + 1
            parent[v] = u
            queue.push_back(v)
~~~

With adjacency lists:

~~~text
time  = O(V + E)
space = O(V)
~~~

Each reachable vertex is discovered once and each outgoing edge is examined once.

## BFS shortest-path guarantee

In an unweighted graph, BFS discovers vertices in nondecreasing edge distance.

When v is first discovered from u:

~~~text
distance[v] = distance[u] + 1
~~~

No later path with fewer edges can exist because all smaller-distance frontiers were processed first.

This guarantee does not hold for arbitrary weighted graphs. If edges have unequal nonnegative costs, Dijkstra is the appropriate generalization.

## BFS parent reconstruction

Store:

~~~text
parent[v] = u
~~~

when v is first discovered.

Then a path from source to target can be reconstructed by walking parents backward.

The parent array is a traversal result, not necessarily the graph's structural parent relation.

For unreachable vertices, parent must use a sentinel that cannot be confused with a valid vertex id.

## Depth-first search

DFS follows one branch deeply before returning.

Iterative form:

~~~text
stack.push(s)

while stack not empty:
    u = stack.pop()
    if visited[u]:
        continue
    visited[u] = true
    for v in adj[u]:
        if not visited[v]:
            stack.push(v)
~~~

Recursive DFS expresses the same search through the call stack.

With adjacency lists:

~~~text
O(V + E)
~~~

for a complete traversal.

Iterative DFS makes memory limits explicit and avoids deep recursion in kernel/tool code.

## DFS ordering

DFS order depends on neighbor order and stack discipline.

If neighbors are pushed:

~~~text
a, b, c
~~~

onto a LIFO stack, c is processed first.

If deterministic traversal matters, the implementation may store adjacency in canonical order, push neighbors in reverse or sort before traversal.

If only reachability matters, traversal order may be irrelevant. That is the case for the current ChrisOS host-gate audit.

## Reachability

Reachability asks whether t can be reached from s.

BFS and DFS both answer this in O(V + E).

For repeated queries over a static graph, preprocessing components or transitive information can be useful.

For dynamic undirected edge additions, union-find can answer connectivity more cheaply than rerunning full traversal, but it cannot recover paths.

## Current ChrisOS Makefile graph

tools/check_test_gates.py treats Makefile rules as a directed graph.

For a rule conceptually written:

~~~text
A: B C
~~~

the parser stores:

~~~text
rules[A] = [B, C]
~~~

The direction used by the audit is:

~~~text
A -> B
A -> C
~~~

meaning that prerequisite targets or files are reachable from the aggregate target.

ROOTS currently contains:

~~~text
host-gates
~~~

The tool asks whether host test targets are reachable from that root through dependency edges.

## Explicit stack traversal in check_test_gates.py

The reviewed code creates:

~~~text
seen = set()
stack = list(ROOTS)
~~~

Then:

~~~text
while stack:
    name = stack.pop()
    if name in seen:
        continue
    seen.add(name)
    stack.extend(rules.get(name, []))
~~~

Because stack.pop removes the last item, the frontier is LIFO.

That makes the traversal depth-first in operational behavior.

The seen set guarantees termination even if the parsed dependency relation contains a cycle.

The output only depends on the reachable set, not on the exact DFS visitation order.

## Reachable host-gate invariant

After traversal, the script examines all parsed rule names.

A rule is reported as orphaned when it looks like a host test target and is not in seen.

The intended invariant is:

~~~text
every host test target should be reachable from host-gates
~~~

This turns a graph property into a CI policy.

Adding a test target without connecting it into the aggregate gate graph is detected.

## Complexity of the gate audit

Let V be parsed/reached names and E be stored prerequisite relationships.

The traversal itself is:

~~~text
O(V + E)
~~~

assuming average O(1) set membership.

The script later iterates over sorted(rules), which adds:

~~~text
O(R log R)
~~~

for R rule names.

That sorted pass exists for deterministic orphan inspection. It is not part of the DFS algorithm and does not make the traversal breadth-first or topological.

## Cycle behavior in the gate audit

The audit does not detect cycles.

Because it checks seen before expanding a name, a cycle such as:

~~~text
A -> B -> C -> A
~~~

terminates safely for reachability.

Termination is different from validating acyclicity.

A dedicated cycle detector needs additional state such as DFS colors, recursion-stack membership or indegree exhaustion under Kahn's algorithm.

The current tool must not be described as a cycle validator.

## DFS cycle detection

For directed graphs, a common coloring scheme is:

~~~text
WHITE = undiscovered
GRAY  = active on current DFS path
BLACK = fully processed
~~~

An edge u -> v with v GRAY is a back edge and proves a directed cycle.

This is stronger than one visited Boolean. A Boolean cannot distinguish an ancestor on the current path from a vertex completed elsewhere.

## Topological sorting

A topological order of a directed graph satisfies:

~~~text
for every edge u -> v:
    u appears before v
~~~

Such an order exists exactly when the graph is a DAG.

Two standard methods are DFS postorder reversal and Kahn's indegree algorithm.

## Kahn's algorithm

Compute indegree for every vertex.

Initialize a queue with all zero-indegree vertices.

Then:

~~~text
while queue not empty:
    u = pop()
    emit u
    for v in adj[u]:
        indegree[v]--
        if indegree[v] == 0:
            push(v)
~~~

If fewer than V vertices are emitted, a cycle exists.

Complexity:

~~~text
O(V + E)
~~~

For build systems and initialization dependencies, topological order can express a valid execution sequence.

Current check_test_gates.py does not compute such an order.

## Strongly connected components

In directed graphs, ordinary connected components are insufficient.

Vertices u and v are strongly connected when:

~~~text
u reaches v
and
v reaches u
~~~

A strongly connected component is a maximal set satisfying that relation.

SCCs are useful for dependency-cycle condensation, call graph analysis, module cycle detection and state-machine analysis.

Two classic linear-time algorithms are Tarjan and Kosaraju.

## Tarjan's SCC algorithm

Tarjan DFS assigns each vertex:

~~~text
index[v]
lowlink[v]
~~~

and maintains a stack of active vertices.

lowlink tracks the smallest DFS index reachable while staying within the active search structure.

When:

~~~text
lowlink[v] == index[v]
~~~

v is the root of an SCC; stack entries are popped until v.

Time:

~~~text
O(V + E)
~~~

The implementation is compact but its invariants are subtle.

## Kosaraju's algorithm

Kosaraju performs:

1. DFS on G to compute finish order;
2. transpose all edges;
3. DFS vertices in reverse finish order on the transposed graph.

Each second-pass DFS tree is one SCC.

Complexity is O(V + E), but the algorithm needs the transpose or incoming-edge traversal.

## Shortest paths and edge weights

Shortest path depends on the weight model.

| Edge weights | Typical algorithm |
|---|---|
| unweighted / unit | BFS |
| nonnegative | Dijkstra |
| negative allowed | Bellman-Ford |
| DAG | topological dynamic programming |
| all pairs, dense/small | Floyd-Warshall |

Using Dijkstra with negative edges is incorrect.

Algorithm selection is therefore a correctness decision, not only a performance choice.

## Dijkstra's algorithm

For nonnegative weights:

~~~text
dist[source] = 0
dist[others] = infinity
~~~

Use a min-priority queue keyed by tentative distance.

Repeatedly extract the minimum unsettled vertex u and relax:

~~~text
candidate = dist[u] + w(u,v)

if candidate < dist[v]:
    dist[v] = candidate
    parent[v] = u
~~~

With a binary heap:

~~~text
O((V + E) log V)
~~~

commonly simplified to O(E log V) on connected sparse graphs.

## Dijkstra invariant

When u is removed with the globally smallest tentative distance and all edge weights are nonnegative, dist[u] is final.

Negative edges invalidate that proof.

Fixed-width distance arithmetic also needs overflow checks:

~~~text
dist[u] + weight
~~~

must not wrap into a falsely small value.

## Bellman-Ford

Bellman-Ford repeatedly relaxes all edges.

After V-1 passes, every shortest simple path has enough opportunities to propagate.

One additional successful relaxation proves a reachable negative cycle.

Complexity:

~~~text
O(VE)
~~~

It is slower than Dijkstra but supports negative edges and explicit negative-cycle detection.

## DAG shortest paths

For a weighted DAG:

1. compute topological order;
2. process vertices in that order;
3. relax outgoing edges once.

Complexity:

~~~text
O(V + E)
~~~

Negative edge weights are allowed because cycles cannot create indefinite improvement.

## Floyd-Warshall

For all-pairs shortest paths:

~~~text
for k:
    for i:
        for j:
            d[i][j] = min(d[i][j], d[i][k] + d[k][j])
~~~

Complexity:

~~~text
O(V^3)
~~~

Memory:

~~~text
O(V^2)
~~~

Its regular dense access can suit small topology matrices but not huge sparse graphs.

## Minimum spanning trees

For a connected undirected weighted graph, a minimum spanning tree connects all vertices with:

~~~text
V - 1 edges
~~~

and minimum total edge weight.

An MST is not a shortest-path tree.

It minimizes total tree weight, not source-to-vertex distance.

## Kruskal's algorithm

Kruskal:

1. sorts edges by increasing weight;
2. initializes one DSU set per vertex;
3. scans edges;
4. accepts an edge if its endpoints are in different sets;
5. unions those sets.

Sorting dominates:

~~~text
O(E log E)
~~~

DSU operations add near-linear amortized cost.

This directly connects the sorting-searching and graphs-union-find foundations.

## Prim's algorithm

Prim grows one connected tree.

Using a min-priority queue, it repeatedly chooses the cheapest boundary connection leading to a new vertex.

With adjacency lists and a binary heap:

~~~text
O(E log V)
~~~

Kruskal is often convenient with an edge list.

Prim is natural with adjacency-based traversal.

## Determinism and tie breaking

Graph algorithms can have multiple valid outputs.

Examples:

- DFS order;
- BFS parent among equal-length choices;
- topological order;
- MST when weights tie.

If reproducible tests require deterministic output, define a tie-breaker such as numeric vertex id, lexical target name, insertion order or stable heap ordering.

Determinism is an additional contract beyond mathematical correctness.

## Memory and locality

Representation changes hardware cost.

Adjacency vectors offer sequential neighbor access.

Pointer-linked adjacency can cause cache misses.

BFS frontier can grow to graph width.

DFS frontier often tracks depth but can still reach O(V).

Dijkstra adds priority-queue metadata.

Floyd-Warshall trades O(V^2) memory for dense regular access.

Peak frontier size matters in constrained systems.

## Concurrency and graph mutation

Most textbook algorithms assume a stable graph during traversal.

Concurrent mutation can invalidate adjacency pointers, visited assumptions, indegrees, heap entries and shortest-path proofs.

Policies include:

- graph read lock;
- immutable snapshot;
- version and restart;
- specialized concurrent algorithms.

The current host-gate script reads a Makefile snapshot in one process; it is not a concurrent graph engine.

## Failure containment

Defensive graph processing validates:

- V and E bounds;
- endpoint ranges;
- allocation-size overflow;
- weight arithmetic;
- queue/stack capacity;
- recursion depth;
- cycles where a DAG is required.

Even O(V + E) can be a denial-of-service vector when V and E are unbounded.

Resource budgets remain necessary.

## Validation model for this chapter

The deterministic checker accompanying this chapter verifies:

- BFS distance and parent reconstruction;
- iterative DFS reachability;
- directed cycle detection with colors;
- topological ordering and cycle rejection;
- Tarjan SCC partitioning;
- Dijkstra on nonnegative weights;
- Bellman-Ford with negative edges and negative-cycle detection;
- Kruskal MST using DSU;
- source anchors proving current Makefile dependency traversal;
- LIFO stack semantics and seen-set termination;
- current boundary: no claim that check_test_gates performs topological sort, SCC, shortest paths or cycle validation.

## Current ChrisOS implementation boundary

At revision da3df29cb397932c43d32373871fb9380e688ade, tools/check_test_gates.py establishes a concrete graph algorithm:

- parses Makefile targets/prerequisites into adjacency lists;
- starts from ROOTS containing host-gates;
- uses a LIFO stack;
- records seen vertices;
- follows prerequisite edges;
- reports host-test rules outside the reachable set.

The source does not establish reusable implementations of BFS, topological sort, Tarjan/Kosaraju SCC, Dijkstra, Bellman-Ford, Floyd-Warshall, Kruskal or Prim.

They are documented as foundations and design tools, not as implemented kernel features.

## Revision provenance

Implementation-facing statements were reconciled against ChrisOS main revision da3df29cb397932c43d32373871fb9380e688ade.

Reviewed source:

- tools/check_test_gates.py;
- makefile.

The concrete claim is deliberately narrow: current ChrisOS tooling contains depth-first-style dependency reachability from host-gates. Broader graph algorithms remain theory until source proves otherwise.
