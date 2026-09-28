---
id: discrete-math-sets-relations-functions
lang: en
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - chrisvm/chris_arch.h
  - compiler/chrisld/chriso.h
  - compiler/chrisasm/chrisasm.c
  - chrisvm/cpu/emulator/flags.c
  - kernel/gfx/graphics.c
symbols:
  - ChrisArchitectureState
  - ChrisoImage
  - ChrisoRel
  - reg_index
  - add_sym
  - chris_cc_true
  - point_in_clip
depends_on:
  - boolean-algebra
  - number-systems-binary-arithmetic
related:
  - proof-invariants-induction
  - data-representation-layout
  - data-structures
  - graphs-union-find
---

# Discrete mathematics: sets, relations and functions

<div class="abstract">
Discrete systems are built from finite or countable collections, explicit relationships and state transformations. Sets describe domains of objects, Cartesian products construct state spaces, relations express connectivity or ordering, and functions model deterministic mappings from one domain to another. These ideas appear directly in operating-system and toolchain code: register indices form finite sets, object-file sections and symbols occupy bounded domains, relocation records relate one object to another, parsers implement partial functions from text to values, and predicates classify points or machine states. This chapter develops the mathematical language needed to state those contracts precisely before algorithms, invariants and proofs are introduced.
</div>

## Prerequisites and scope

Boolean algebra supplies predicates and logical connectives. Number systems supply finite integer domains and indexed bit vectors.

Discrete mathematics adds a language for collections and mappings.

~~~text
objects
  ↓
sets and membership
  ↓
products and relations
  ↓
functions and composition
  ↓
state spaces, graphs, tables and interfaces
~~~

The objective is not abstract notation for its own sake. A systems implementation becomes easier to reason about when it is clear which values belong to a domain, which pairs are permitted, whether a mapping is total, and which properties survive composition.

## Sets and membership

A set is a collection of distinct elements.

If x belongs to set A, write:

~~~text
x ∈ A
~~~

If it does not:

~~~text
x ∉ A
~~~

Two sets are equal when they have the same members, regardless of listing order.

For example:

~~~text
A = {0, 1, 2}
B = {2, 1, 0}
~~~

implies A = B.

Multiplicity does not matter in an ordinary set. That distinguishes sets from sequences, arrays and multisets.

## Finite domains

Systems software frequently operates over finite sets.

Examples include:

- register indices;
- CPU IDs;
- enum values;
- file descriptors currently allocated;
- object-file sections;
- page-frame numbers within a physical-memory limit;
- indices into fixed-capacity tables.

A finite set A has cardinality |A| equal to its number of elements.

If:

~~~text
G = {0, 1, ..., 15}
~~~

then:

~~~text
|G| = 16
~~~

Current ChrisArchitectureState stores sixteen general-purpose register slots in gpr[16]. The array provides a concrete finite indexed domain. It does not imply that every arbitrary integer is a valid register index.

## Subsets

A is a subset of B when every element of A is also in B:

~~~text
A ⊆ B
~~~

A proper subset additionally requires A ≠ B.

Subset reasoning appears whenever one domain is restricted by permissions or state.

For example, a set of enabled capabilities should be a subset of all capabilities defined by an ABI. A set of currently valid object indices must remain a subset of the allocated table range.

The empty set:

~~~text
∅
~~~

is a subset of every set.

## Set operations

For sets A and B:

Union contains elements in either set:

~~~text
A ∪ B
~~~

Intersection contains elements in both:

~~~text
A ∩ B
~~~

Difference contains elements in A but not B:

~~~text
A \ B
~~~

If a universe U is fixed, complement contains elements of U not in A:

~~~text
U \ A
~~~

These operations parallel Boolean OR, AND and NOT when sets are represented by bit masks.

## Sets as bit masks

For a small finite universe, membership can be represented by one bit per possible element.

Let U = {0,1,2,3}. The subset {0,2} can be represented as:

~~~text
0101₂
~~~

if bit i represents membership of i.

Then:

~~~text
union        ↔ bitwise OR
intersection ↔ bitwise AND
difference   ↔ AND with complement
~~~

This correspondence explains why flags and capability sets are often encoded as bit fields.

The encoding only works when the mapping from elements to bit positions is explicit.

## Power sets

The power set P(A) is the set of all subsets of A.

For a finite set with n elements:

~~~text
|P(A)| = 2^n
~~~

This connects directly to bit masks: an n-bit mask can encode 2^n possible subsets of an n-element universe.

For four independent Boolean options there are sixteen possible option sets.

State-space growth therefore becomes exponential when independent binary dimensions are combined.

## Ordered pairs and tuples

Sets are unordered, but systems state is often structured by position.

An ordered pair:

~~~text
(a, b)
~~~

is different from (b, a) unless a = b.

Tuples generalize this idea.

A CPU state can be viewed mathematically as a tuple containing register values, control registers, segment state, flags and other fields.

ChrisArchitectureState is a concrete C representation of such a product state. The mathematics does not require the implementation to store the tuple in any particular memory layout.

## Cartesian products

The Cartesian product of sets A and B is:

~~~text
A × B = {(a,b) | a ∈ A and b ∈ B}
~~~

If A and B are finite:

~~~text
|A × B| = |A|·|B|
~~~

Products construct state spaces.

If an instruction selector has 8 possible values and an operand-size selector has 4 possible values, the unconstrained product contains 32 pairs. An implementation may support only a subset of those pairs.

That distinction between the full product and the valid subset is a common source of input-validation rules.

## Relations

A binary relation R from A to B is a subset of A × B.

Write:

~~~text
a R b
~~~

when (a,b) belongs to R.

Relations model:

- graph edges;
- “symbol refers to section”;
- “relocation refers to symbol”;
- “process owns handle”;
- “page maps to frame”;
- “instruction may transition to state”.

A relation need not assign exactly one output to each input. That property belongs to functions.

## Relations in ChrisO

ChrisoImage contains a bounded symbol array and a bounded relocation array.

A ChrisoRel stores sym_index. Under a valid object-image contract, a relocation therefore establishes a relation between one relocation record and one symbol entry.

Mathematically, if:

~~~text
R = set of active relocation indices
S = set of active symbol indices
~~~

then the valid reference relation should satisfy:

~~~text
relates ⊆ R × S
~~~

and each active relocation record is expected to name an admissible symbol index according to the format validation rules.

The C field is a number. The mathematical meaning is a relation between indexed objects.

## Properties of relations

For a relation R on one set A, several properties are useful.

Reflexive:

~~~text
for every a ∈ A, a R a
~~~

Symmetric:

~~~text
a R b implies b R a
~~~

Antisymmetric:

~~~text
a R b and b R a imply a = b
~~~

Transitive:

~~~text
a R b and b R c imply a R c
~~~

These properties classify common structures.

They must be proved from the relation definition; naming a relation “order” or “equivalence” does not make the required laws true.

## Equivalence relations

An equivalence relation is reflexive, symmetric and transitive.

It partitions a set into equivalence classes.

Examples in computing can include:

- identifiers considered equal under a normalization rule;
- addresses equivalent under a page-offset relation;
- states equivalent with respect to some observation.

Equivalence depends on what is being observed.

Two machine states may be equivalent for a specific test even if hidden counters differ.

## Partial orders

A partial order is reflexive, antisymmetric and transitive.

Subset inclusion is a standard partial order:

~~~text
A ⊆ B
~~~

Not every pair must be comparable.

This matters in dependency systems. Two independent prerequisites can both precede a later chapter without one preceding the other.

A total order adds comparability for every pair.

Array indices and ordinary integer ordering provide total orders over their valid domains.

## Directed graphs as relations

A directed graph G = (V,E) consists of a vertex set V and edge relation:

~~~text
E ⊆ V × V
~~~

This turns graph theory into relation theory.

Reachability is not the same as direct adjacency. If E contains direct edges, reachability corresponds to the transitive closure of E.

Dependency graphs, call graphs, control-flow graphs and ownership graphs all use this distinction.

A cycle means an element can be reached again through one or more directed edges.

The curriculum dependency checker later uses precisely this style of graph reasoning: prerequisites form directed edges and cycles are invalid.

## Functions

A function f from A to B assigns exactly one element of B to every element of its domain A:

~~~text
f : A → B
~~~

For every a ∈ A there is exactly one f(a) ∈ B.

The codomain B can contain values that are never produced.

A function differs from a general relation because each domain element has one output.

## Total and partial functions

A total function is defined for every element of its declared domain.

A partial function is defined only for some inputs.

Many C interfaces are naturally modeled as partial functions even when the implementation expresses failure with a sentinel or error code.

Current ChrisASM reg_index maps recognized register-name strings to indices 0 through 15. For unrecognized strings it returns -1.

Mathematically, the successful mapping is a partial function:

~~~text
recognized register names ⇀ {0,...,15}
~~~

The C wrapper extends this with a failure result.

This distinction clarifies why arbitrary strings are not members of the successful domain.

## Predicates as functions

A predicate on set A is a function:

~~~text
P : A → {false,true}
~~~

point_in_clip is a concrete example.

Its input includes a point and rectangle parameters. Its Boolean result classifies whether the point belongs to the open/closed boundary convention implemented by the comparisons.

The reviewed implementation requires:

~~~text
clip_w > 0
clip_h > 0
x >= clip_x
y >= clip_y
x < clip_x + clip_w
y < clip_y + clip_h
~~~

This is a membership predicate for an axis-aligned half-open rectangle.

## chris_cc_true as a finite function

chris_cc_true masks cc with 15.

Therefore condition selection depends only on:

~~~text
cc mod 16
~~~

for the low four bits.

For a fixed flags word, the function maps one of sixteen condition classes to Boolean truth.

Its implementation extracts CF, PF, ZF, SF and OF and evaluates the selected condition.

This is a concrete finite function over machine-state attributes.

## Injective functions

A function is injective when distinct inputs never map to the same output:

~~~text
f(a1) = f(a2) implies a1 = a2
~~~

An injective mapping preserves distinctness.

An array index to storage-slot mapping is intended to be injective within the array: two different valid indices identify different element positions.

A hash function, by contrast, is generally not injective over a domain larger than its output space; collisions are unavoidable.

## Surjective functions

A function f : A → B is surjective when every element of B is produced by at least one input.

Surjectivity depends on the declared codomain.

A function can be surjective onto its image while not being surjective onto a larger codomain.

This matters when an enum reserves values that no current path generates.

## Bijections

A function is bijective when it is both injective and surjective.

A bijection has a well-defined inverse.

Finite binary encodings often seek bijections between valid bit patterns and semantic values.

For n-bit unsigned integers:

~~~text
{n-bit patterns}
↔
{0,...,2^n-1}
~~~

is a bijection.

Two's-complement signed interpretation is another bijection from the same patterns to a different integer range.

## Function composition

If:

~~~text
f : A → B
g : B → C
~~~

then:

~~~text
g ∘ f : A → C
~~~

is defined by:

~~~text
(g ∘ f)(a) = g(f(a))
~~~

Systems pipelines are compositions.

For example:

~~~text
source token
  ↓ parse
numeric value
  ↓ encode
byte sequence
~~~

Correct composition requires the output contract of the first stage to satisfy the input contract of the second.

An error sentinel is not automatically a valid member of the next stage's domain.

## Inverses

A bijective function f has inverse f^-1 such that:

~~~text
f^-1(f(a)) = a
~~~

Encoding/decoding pairs often aim for inverse behavior over the valid subset of representations.

Serialization can fail to be globally bijective when multiple byte sequences are accepted as equivalent or when reserved encodings exist.

Therefore “decode reverses encode” must state the valid domain and normalization rules.

## Images and preimages

For S ⊆ A, the image is:

~~~text
f(S) = {f(x) | x ∈ S}
~~~

For T ⊆ B, the preimage is:

~~~text
f^-1(T) = {x ∈ A | f(x) ∈ T}
~~~

Preimages are useful for validation.

A permission check can be understood as selecting the preimage of allowed states under a classification function.

No actual inverse function is required.

## Cardinality and the pigeonhole principle

If more than n objects are placed into n boxes, at least one box contains more than one object.

This elementary result explains unavoidable collision behavior.

If a table has 256 distinct slots, more than 256 simultaneously distinct objects cannot occupy unique slots without changing the representation or rejecting an insertion.

ChrisO sets CHRISO_SYM_MAX to 256 and CHRISO_REL_MAX to 512.

Current add_sym checks nsym against CHRISO_SYM_MAX before creating another symbol entry. The limit is an implementation capacity, not an assertion that the mathematical universe of symbols contains only 256 names.

## Finite-state spaces

A state represented by independent finite components belongs to a Cartesian product.

Suppose a toy state has:

- 4 operation values;
- 2 privilege levels;
- 8 register selectors.

The unconstrained state count is:

~~~text
4·2·8 = 64
~~~

Real machine state is vastly larger because registers carry wide bit vectors.

Finite does not mean small.

Explicit state-space reasoning is still useful because validation commonly restricts a large product to a much smaller legal subset.

## Sets versus sequences and arrays

A C array is ordered and permits duplicate values.

A mathematical set is unordered and contains unique members.

Therefore:

~~~text
[3,3,5]
~~~

as an array has length 3, while its set of values is:

~~~text
{3,5}
~~~

with cardinality 2.

Confusing these abstractions causes mistakes in duplicate detection, capacity reasoning and equality tests.

## Relations versus pointers

A pointer can implement one representation of a relation, but the concepts differ.

A linked-list next pointer represents an edge from one node to another.

An array index can represent the same kind of edge.

A symbol index in ChrisoRel represents a relation without containing a host pointer.

The mathematical relation survives representation changes.

This separation is important for persistent formats, emulators and cross-address-space structures.

## Error handling as domain restriction

Validation frequently converts a large raw input universe into a smaller accepted domain.

Conceptually:

~~~text
raw inputs
   ↓ validator
valid domain  ∪  error
~~~

A safe implementation should reject values outside the assumptions required by downstream functions.

Current add_sym rejects insertion once nsym reaches CHRISO_SYM_MAX.

Current reg_index rejects names outside its recognized set by returning -1.

These checks preserve domain boundaries.

## Memory ownership and concurrency

Sets, relations and functions are mathematical objects and have no memory ownership.

Their software representations do.

A relation stored as an array belongs to whatever subsystem owns that array. Concurrent modification requires synchronization appropriate to that representation.

Two threads may reason about the same abstract set while racing on an unsynchronized concrete table.

Mathematical determinism does not provide memory atomicity.

## Security boundary

Many security bugs can be expressed as domain errors:

- using an index not in the valid index set;
- treating a partial mapping as total;
- accepting a relation edge to an object outside the authorized set;
- composing interfaces whose domains do not match;
- assuming uniqueness where the representation permits collisions;
- failing to validate that a reference belongs to the active object set.

Explicit domains make those faults visible before implementation details obscure them.

## Performance considerations

Set and relation notation does not prescribe representation.

The same abstract set can be implemented as:

- bitset;
- sorted array;
- hash table;
- tree;
- linked structure.

The asymptotic and cache behavior differ.

Similarly, a relation can be stored as an adjacency matrix, adjacency lists, edge array or implicit predicate.

Representation selection belongs to data-structure and algorithm chapters.

This chapter supplies the semantic contract those representations must preserve.

## Validation evidence

The deterministic checker for this chapter validates:

- set union, intersection and difference over finite examples;
- power-set cardinality 2^n;
- Cartesian-product cardinality;
- reflexive, symmetric and transitive relation predicates;
- an equivalence relation;
- subset as a partial order;
- injective, surjective and bijective examples;
- function composition;
- finite register-index cardinality;
- current ChrisOS source anchors for gpr[16], CHRISO_SEC_MAX, CHRISO_SYM_MAX, ChrisoRel.sym_index, reg_index and point_in_clip.

The checker tests the documented examples and source boundary. It is not a theorem prover for arbitrary ChrisOS code.

## Current limitations

This chapter does not fully cover:

- graph algorithms;
- formal logic calculi;
- combinatorics beyond basic counting;
- probability;
- algebraic structures such as groups and rings;
- category theory;
- model checking;
- formal verification languages.

Those topics are introduced only when later systems material requires them.

## Roadmap boundary

The curriculum transition is:

~~~text
Boolean and finite numerical logic
    ↓
sets, products, relations and functions
    ↓
proof, invariants and induction
    ↓
representation and algorithms
~~~

The next chapter uses the domains defined here to state propositions about program state and prove that operations preserve required properties.

## Revision provenance

Implementation-facing statements were reconciled against ChrisOS main revision da3df29cb397932c43d32373871fb9380e688ade.

Reviewed sources:

- chrisvm/chris_arch.h;
- compiler/chrisld/chriso.h;
- compiler/chrisasm/chrisasm.c;
- chrisvm/cpu/emulator/flags.c;
- kernel/gfx/graphics.c.

Reviewed symbols:

- ChrisArchitectureState;
- ChrisoImage;
- ChrisoRel;
- reg_index;
- add_sym;
- chris_cc_true;
- point_in_clip.

The mathematical definitions are implementation-independent. ChrisOS examples are used only where the reviewed source provides a concrete finite domain, relation or mapping.
