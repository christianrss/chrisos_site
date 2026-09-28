---
id: sorting-searching
lang: en
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - APPS/EDITOR/EDITOR.CC
  - compiler/edit/editmodel.c
  - tools/test_pmm_heap_smp.c
  - tools/run_doom_cmp_scan.py
symbols:
  - line_for_pos
  - find_from
  - edit_search
  - cmp_u64
depends_on:
  - algorithmic-complexity
  - arrays-lists-stacks-queues
  - recursion-recurrences-amortization
  - trees-heaps-tries
related:
  - graph-algorithms
  - string-parsing-algorithms
  - systems-algorithms
  - hash-tables
---

# Sorting and searching algorithms

<div class="abstract">
Sorting and searching are not interchangeable utilities but families of algorithms whose contracts depend on order, representation, mutation policy, stability, key distribution and workload shape. This chapter develops linear and binary search, lower/upper bounds, insertion and selection sort, merge sort, quicksort, heapsort, counting/radix techniques and the comparison-sorting lower bound. It also reconciles those foundations with the current ChrisOS tree. The ChrisC editor performs a genuine binary search over a sorted line-start index in line_for_pos; its text find path and the host edit model use direct left-to-right pattern scans. The PMM SMP test calls the host C library qsort only to place physical addresses in order before duplicate detection, so the source does not establish a ChrisOS qsort implementation. A diagnostic script whose docstring says "Binary-search" does not actually implement binary search in the reviewed revision; it probes a fixed candidate list. The implementation boundary is therefore based on executed control flow, not names or comments.
</div>

## Ordering as a contract

A sort takes a collection and produces an ordering according to a comparator or key.

For elements a and b, a comparator should define a consistent relation such as:

~~~text
a < b
a == b
a > b
~~~

For comparison algorithms to behave correctly, the comparison relation normally needs a strict weak ordering:

- irreflexive: not a < a;
- asymmetric: a < b excludes b < a;
- transitive;
- equivalence induced by neither a < b nor b < a is transitive.

If a comparator changes during sorting or violates transitivity, even a correct algorithm can produce meaningless results.

Systems code also needs the representation contract:

- element width;
- key width;
- signed versus unsigned order;
- byte order when comparing encoded values;
- whether pointers are compared by address or pointed-to content;
- ownership during swaps or moves.

## Stable and unstable sorting

A stable sort preserves the input order of elements whose keys compare equal.

Input:

~~~text
(5,A) (2,X) (5,B)
~~~

Stable result:

~~~text
(2,X) (5,A) (5,B)
~~~

Unstable result may legally produce:

~~~text
(2,X) (5,B) (5,A)
~~~

Stability matters for multi-key ordering.

For example, if records are first sorted by name and then stably sorted by priority, the secondary name order survives among equal priorities.

Kernel tables often do not need stability, but tools, diagnostics and UI data may.

## In-place and out-of-place algorithms

An in-place algorithm uses O(1) or O(log n) auxiliary storage beyond the input, depending on the definition and recursion stack.

Out-of-place algorithms allocate an auxiliary buffer.

This distinction matters in:

- boot code before general allocation;
- interrupt context;
- memory-pressure paths;
- deterministic firmware code;
- large datasets where temporary storage doubles peak memory.

A lower asymptotic time cost may be unacceptable if it requires memory unavailable in the execution context.

## Linear search

Linear search inspects candidates one by one.

For n elements:

~~~text
worst-case comparisons = n
time = O(n)
extra memory = O(1)
~~~

It does not require sorted input.

Conceptually:

~~~text
for i in 0..n-1:
    if a[i] == key:
        return i
return not_found
~~~

Linear search is often correct and optimal enough for tiny fixed tables.

Using binary search on eight entries can add ordering and mutation complexity without meaningful benefit.

## Binary search precondition

Binary search requires a monotonic search space.

For a sorted ascending array:

~~~text
a[0] <= a[1] <= ... <= a[n-1]
~~~

A classic exact-match search maintains an interval that may contain the key.

~~~text
lo = 0
hi = n

while lo < hi:
    mid = lo + (hi - lo) / 2
    if a[mid] < key:
        lo = mid + 1
    else:
        hi = mid
~~~

At termination, lo is the first index whose value is not less than key.

This is lower_bound semantics.

A separate equality test determines whether the key exists.

## Overflow-safe midpoint

The expression:

~~~text
(lo + hi) / 2
~~~

can overflow when lo and hi are large integers.

Safer form:

~~~text
lo + (hi - lo) / 2
~~~

Some bounded applications know that indices cannot approach integer limits, but the bound must be part of the proof rather than an assumption.

## Lower bound and upper bound

For sorted data:

~~~text
lower_bound(key)
~~~

returns the first position p such that:

~~~text
a[p] >= key
~~~

while:

~~~text
upper_bound(key)
~~~

returns the first position p such that:

~~~text
a[p] > key
~~~

Therefore equal-key range is:

~~~text
[lower_bound(key), upper_bound(key))
~~~

These variants are more useful than exact-match search when duplicates exist.

## Greatest element not above a query

Another common binary-search contract is:

~~~text
find greatest i such that a[i] <= x
~~~

This is the contract used by the ChrisC editor line index.

The algorithm can bias midpoint upward:

~~~text
mid = (lo + hi + 1) / 2
~~~

and when a[mid] <= x, set lo = mid.

The upward bias is important because assigning lo = mid with a downward midpoint could fail to shrink a two-element interval.

## ChrisC editor line index

APPS/EDITOR/EDITOR.CC maintains:

~~~text
g_line_starts[]
g_line_count
~~~

The line-start array is constructed in increasing text-offset order while scanning the buffer.

line_for_pos clamps p to the buffer bounds and then performs:

~~~text
lo = 0
hi = g_line_count - 1

while lo < hi:
    mid = (lo + hi + 1) / 2
    if g_line_starts[mid] <= p:
        lo = mid
    else:
        hi = mid - 1
~~~

The returned lo is the index of the last line whose start offset is not greater than p.

That is a concrete binary search because:

- the searched array is sorted;
- the predicate start <= p is monotonic;
- every iteration shrinks the candidate interval.

For L indexed lines, the lookup is O(log L).

## Index rebuild cost

Binary search does not make the entire line-number operation O(log n) under all circumstances.

The editor marks the line index dirty after edits.

ensure_line_index can rebuild g_line_starts by scanning the whole buffer.

Thus the cost model has two layers:

- clean index: line_for_pos O(log L);
- dirty index: rebuild O(N) plus search O(log L), where N is text length.

Caching changes amortized behavior but does not erase rebuild cost.

## Direct substring search in the ChrisC editor

find_from scans candidate positions in the text.

For each candidate it compares pattern bytes until mismatch or full match.

Forward direction:

~~~text
i = start
while i + pattern_length <= text_length:
    compare text[i + j] against pattern[j]
    if all equal:
        return i
    i++
~~~

Backward direction scans candidate starts in reverse but performs the same direct pattern comparison.

This is naive substring search.

For text length N and pattern length M:

~~~text
worst case = O(N * M)
~~~

It uses O(1) auxiliary search state.

find_next and find_prev add wraparound behavior by restarting from the beginning or end if the first pass fails.

## Host edit-model search

compiler/edit/editmodel.c::edit_search uses the same basic algorithm:

- determine pattern length;
- scan candidate start i from from;
- compare each pattern byte;
- return first matching logical position.

The editor data is stored in a gap buffer, so char_at translates logical index to physical storage around the gap.

The search algorithm is linear-by-candidates, but each logical character access remains O(1).

No KMP, Boyer-Moore or suffix index is established in this source.

## Search algorithm selection

Typical choices:

| Data condition | Useful search |
|---|---|
| tiny unsorted array | linear scan |
| sorted static array | binary search |
| hashable equality key | hash table |
| ordered dynamic set | balanced tree |
| prefix lookup | trie/radix structure |
| substring in text | direct scan, KMP, Boyer-Moore, automata |
| repeated text queries | suffix/prefix indexes depending workload |

Search complexity cannot be chosen without accounting for the maintenance cost of the index that enables it.

## Insertion sort

Insertion sort grows a sorted prefix.

For each element x:

1. preserve x;
2. shift larger elements right;
3. place x into the gap.

Conceptually:

~~~text
for i = 1 .. n-1:
    x = a[i]
    j = i
    while j > 0 and x < a[j-1]:
        a[j] = a[j-1]
        j--
    a[j] = x
~~~

Properties:

- worst-case O(n^2);
- best-case O(n) on already sorted data with a guarded loop;
- O(1) extra storage;
- stable when equal elements are not moved past one another;
- excellent constants for very small arrays.

Production hybrid sorts often use insertion sort for small partitions.

## Selection sort

Selection sort repeatedly selects the minimum remaining element and swaps it into position.

Properties:

- O(n^2) comparisons in best and worst cases;
- O(n) swaps;
- O(1) auxiliary memory;
- normally unstable in its simple swap form.

It can be useful when writes are much more expensive than comparisons.

## Merge sort

Merge sort divides the sequence, recursively sorts halves and merges two sorted runs.

Recurrence:

~~~text
T(n) = 2T(n/2) + Theta(n)
~~~

which yields:

~~~text
Theta(n log n)
~~~

Typical array merge sort requires O(n) auxiliary storage.

It is naturally stable when the merge chooses the left element first on equal keys.

For linked lists, merging can be performed by relinking nodes with little extra element storage.

## Quicksort

Quicksort partitions elements around a pivot, then recursively sorts partitions.

Average behavior with appropriate pivot selection:

~~~text
O(n log n)
~~~

Worst case:

~~~text
O(n^2)
~~~

A poor deterministic pivot on already ordered or adversarial input can trigger the worst case.

Practical implementations mitigate this with:

- randomized pivots;
- median-of-three sampling;
- recursion-depth limits;
- switching to heapsort at excessive depth;
- insertion sort for tiny partitions.

The last combination is the idea behind introsort.

## Partition invariants

A partition loop must maintain a precise invariant.

For one common three-way design:

~~~text
[ < pivot | == pivot | unknown | > pivot ]
~~~

Three-way partitioning is valuable with many duplicate keys because it avoids recursively sorting a large equal-key region.

Pointer/index bounds must be proved separately from comparison correctness.

## Heapsort

Heapsort builds a binary heap and repeatedly extracts the maximum or minimum depending on desired output order.

Properties:

- O(n log n) worst-case;
- O(1) auxiliary array storage;
- normally unstable;
- less locality-friendly than sequential merge passes;
- deterministic worst-case bound.

Bottom-up heap construction is O(n), not O(n log n), because most nodes are near leaves and require little sift-down work.

## Counting sort

Counting sort applies when keys lie in a manageable integer range K.

It counts occurrences and reconstructs output.

Cost:

~~~text
O(n + K)
~~~

Memory:

~~~text
O(K)
~~~

This bypasses the comparison-sorting lower bound because it exploits key representation instead of using only comparisons.

If K is huge relative to n, it is wasteful.

## Radix sort

Radix sort processes digits or bit groups.

For fixed-width keys and d passes:

~~~text
O(d * (n + base))
~~~

With constant-width machine integers, d can be treated as bounded, making practical behavior close to linear.

Correctness depends on digit order and stability of intermediate passes for least-significant-digit radix sorting.

Endianness in memory does not by itself define numeric digit order.

## Comparison-sorting lower bound

A comparison sort can be modeled as a decision tree.

Sorting n distinct elements requires distinguishing n! possible input permutations.

A binary comparison tree of height h has at most 2^h leaves.

Therefore:

~~~text
2^h >= n!
h >= log2(n!)
h = Omega(n log n)
~~~

Thus no comparison-only sorting algorithm can guarantee o(n log n) comparisons for arbitrary inputs.

Counting and radix techniques escape this bound by using additional structure of the key domain.

## Library qsort in PMM validation

tools/test_pmm_heap_smp.c collects physical page addresses allocated concurrently by several host threads.

It then calls:

~~~text
qsort(all, NCPU * PAGES_PER, sizeof(all[0]), cmp_u64)
~~~

and scans adjacent entries for duplicates.

Sorting makes duplicate detection simple:

~~~text
if all[i] == all[i - 1]:
    duplicate
~~~

This is host-test logic.

The source calls the C library qsort; it does not implement the sorting algorithm itself.

The C standard specifies observable qsort behavior but does not require a particular internal algorithm.

Therefore this chapter must not claim that ChrisOS implements quicksort merely because the API is named qsort.

## Documentation-versus-control-flow boundary

tools/run_doom_cmp_scan.py begins with a docstring saying it will binary-search the first PC where JIT state diverges.

At the reviewed revision, its executable body:

- decodes instruction starts;
- filters a hard-coded list of candidate PCs;
- invokes probe once for each candidate.

There is no lo/hi midpoint narrowing loop.

Accordingly, the file is not evidence of a current binary-search implementation.

This is a concrete example of the evidence rule: comments and names are weaker than current control flow.

## Sorting validation properties

Tests should validate more than one expected output.

For a sort:

- result is nondecreasing under comparator;
- output is a permutation of input;
- stable algorithms preserve equal-key relative order;
- empty and one-element inputs work;
- duplicates work;
- reverse-sorted input works;
- capacity and index arithmetic stay in bounds.

Permutation validation can use:

- reference multiset counts;
- hashes with caution;
- independent sorted copy;
- exact small-domain counts.

## Binary-search validation properties

For lower_bound over sorted a:

~~~text
all i < p: a[i] < key
all i >= p: a[i] >= key
~~~

For the editor's last-start-not-greater contract:

~~~text
a[p] <= x
and
p is final index or a[p+1] > x
~~~

Boundary cases include:

- one element;
- first position;
- last position;
- exact duplicate;
- query between entries;
- query below minimum or above maximum according to the API's clamp rules.

Property checks catch off-by-one errors better than a few hand-selected values.

## Concurrency

Sorting generally mutates an entire collection.

Concurrent readers require:

- exclusive ownership during mutation;
- copy-and-publish snapshots;
- versioning;
- external lock.

Binary search over an immutable sorted table is naturally read-only.

Searching a structure while another thread reorders or mutates it can violate the sortedness or lifetime invariant even if individual loads are atomic.

The ChrisC editor is not presented here as a concurrent text index. Its line-index correctness is analyzed within its current single-editor state model.

## Security and adversarial inputs

Algorithms exposed to untrusted data need worst-case analysis.

Risks include:

- quicksort quadratic behavior under adversarial pivots;
- comparator integer overflow;
- allocation overflow for merge buffers;
- malformed counts causing out-of-bounds binary search;
- pathological substring inputs causing O(NM) work;
- denial of service through repeated index invalidation/rebuild.

Defensive design can use introsort, bounded capacities, overflow-safe size arithmetic and complexity budgets.

## Current ChrisOS implementation boundary

At revision da3df29cb397932c43d32373871fb9380e688ade, the inspected source establishes:

- binary search in APPS/EDITOR/EDITOR.CC::line_for_pos over sorted line starts;
- direct forward/backward substring scanning in find_from;
- direct substring scanning over a gap buffer in edit_search;
- host-side use of library qsort in PMM SMP validation;
- a diagnostic file whose docstring says binary-search but whose body currently probes a fixed candidate list.

It does not establish native current implementations of:

- merge sort;
- quicksort;
- heapsort as a sorting routine;
- counting sort;
- radix sort;
- KMP or Boyer-Moore;
- a general binary-search library.

These algorithms are documented as foundations and design alternatives, not fabricated ChrisOS features.

## Validation model for this chapter

The deterministic checker accompanying this chapter verifies:

- insertion sort ordering and stability;
- merge sort ordering and stability;
- heapsort ordering;
- lower_bound and upper_bound contracts;
- greatest-index-not-above binary search used by the editor model;
- direct substring search behavior;
- permutation preservation;
- source anchors for line_for_pos, find_from and edit_search;
- qsort's status as an external host-library call;
- absence of an actual midpoint loop in run_doom_cmp_scan.py despite its docstring.

The checker validates deterministic examples and reviewed source contracts. It does not claim to test the host C library's internal qsort algorithm.

## Revision provenance

Implementation-facing statements were reconciled against ChrisOS main revision da3df29cb397932c43d32373871fb9380e688ade.

Reviewed source:

- APPS/EDITOR/EDITOR.CC;
- compiler/edit/editmodel.c;
- tools/test_pmm_heap_smp.c;
- tools/run_doom_cmp_scan.py.

The chapter deliberately distinguishes API name, comment intent and actual algorithmic control flow.
