---
id: proof-invariants-induction
lang: en
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - compiler/chrisasm/chrisasm.c
  - compiler/chrisld/chriso.h
  - chrisvm/cpu/emulator/flags.c
  - kernel/gfx/graphics.c
symbols:
  - parse_u64
  - emit_u8
  - add_sym
  - patch_fixups
  - chris_flags_bin
  - gfx_mark_dirty
depends_on:
  - discrete-math-sets-relations-functions
related:
  - algorithmic-complexity
  - recursion-recurrences-amortization
  - data-structures
  - systems-algorithms
---

# Proof, invariants and induction for systems

<div class="abstract">
Systems code is correct only when required properties remain true across every permitted transition. Proof techniques make those requirements explicit. Direct proof establishes a result from definitions, contradiction rules out impossible states, induction reasons over recursively or iteratively constructed objects, and invariants characterize properties preserved by loops, data structures and state machines. This chapter develops proof obligations in a form useful for operating systems, compilers and emulators, then applies them to concrete ChrisOS code: bounded numeric parsing, fixed-capacity symbol tables, relocation patching, finite-width arithmetic and dirty-rectangle tracking. The objective is not to claim formal verification of ChrisOS, but to show how implementation claims can be reduced to precise assumptions, preserved properties and executable checks.
</div>

## Prerequisites and scope

The previous chapter defines sets, relations and functions. Those concepts provide the language needed to state:

- a set of valid states;
- a transition relation between states;
- a predicate that must remain true;
- a function transforming input to output.

A proof answers whether a stated property follows from stated assumptions.

The basic pattern is:

~~~text
precondition
   ↓
operation or transition
   ↓
postcondition
~~~

An invariant strengthens this by requiring a property to remain true at multiple intermediate states, not only at entry and exit.

## Propositions

A proposition is a statement that is either true or false under a defined interpretation.

Examples:

~~~text
0 <= i < n
g_nloc <= ASM_LOCAL_MAX
result <= mask
every stored dirty rectangle lies inside the framebuffer
~~~

A proposition should be precise enough to evaluate.

“Index is safe” is not precise until the valid range and operation are specified.

## Implication

Many proof obligations have the form:

~~~text
P ⇒ Q
~~~

where P is a precondition and Q is a consequence.

For example:

~~~text
0 <= i < n
⇒
array[i] names an element inside an n-element array
~~~

The implication is only as strong as the model. It does not establish that the array pointer itself is valid, that concurrent code cannot free the object, or that n correctly reflects allocation size.

Proofs require complete assumptions.

## Necessary and sufficient conditions

A condition P is sufficient for Q when P implies Q.

P is necessary for Q when Q implies P.

Confusing these directions is a common engineering error.

A bounds check can be sufficient for one memory access while not being sufficient for object lifetime.

Similarly, a non-null pointer can be necessary for dereference in ordinary C code but is not sufficient to prove the pointer addresses a live object.

## Direct proof

A direct proof begins with assumptions and derives the result.

Example:

Given:

~~~text
0 <= x < 2^n
0 <= y < 2^n
r = (x + y) mod 2^n
~~~

by the definition of modulo:

~~~text
0 <= r < 2^n
~~~

Therefore r fits in n unsigned bits.

This is exactly the kind of argument behind width masking in finite arithmetic.

## Proof by cases

When behavior branches on a finite condition, prove each case separately.

For a signed two's-complement value, the interpretation rule has two cases:

~~~text
U < 2^(n-1)
U >= 2^(n-1)
~~~

A complete proof covers both.

Switch statements, enum dispatch, page-table level selection and error/result unions often invite proof by cases.

Missing a case is equivalent to leaving part of the input domain unproved.

## Contradiction

Proof by contradiction assumes the negation of the desired result and derives an impossibility.

For uniqueness, suppose two distinct valid keys are claimed to occupy the same slot under a supposedly injective mapping.

If the mapping definition implies equal outputs require equal inputs, the assumption of distinct inputs contradicts the definition.

Contradiction is especially useful for uniqueness, impossibility and cycle arguments.

## Contrapositive

The implication:

~~~text
P ⇒ Q
~~~

is logically equivalent to:

~~~text
not Q ⇒ not P
~~~

Sometimes the contrapositive is easier to prove.

For example, to establish that every accepted object reference lies inside the active symbol table, it may be simpler for a validator to reject every reference whose index is outside the active range.

The code then demonstrates the contrapositive of acceptance safety.

## Mathematical induction

Induction proves a property P(n) over natural-number-like construction.

Two obligations are required:

Base case:

~~~text
P(0)
~~~

Inductive step:

~~~text
P(k) ⇒ P(k+1)
~~~

Then P(n) holds for all n in the induction domain.

This is not circular reasoning. The step proves preservation from an arbitrary k, while the base establishes the first reachable case.

## Induction over sequences

Suppose an algorithm processes a sequence one element at a time.

To prove a property after processing all elements:

1. prove it before any element is processed;
2. assume it holds after k elements;
3. prove processing element k preserves it.

This form appears directly in parser loops, checksums, copying loops, symbol-table scans and state updates.

The loop-invariant method is induction expressed operationally.

## Strong induction

Strong induction assumes:

~~~text
P(0), P(1), ..., P(k)
~~~

to prove:

~~~text
P(k+1)
~~~

It is useful when a step depends on more than the immediately preceding size.

Recursive structures and recurrence relations often use this form.

Its logical power over natural numbers is equivalent to ordinary induction; the hypothesis is organized differently.

## Structural induction

Structural induction proves properties of recursively defined objects.

For an expression tree:

- prove the property for leaves;
- assume it holds for child subtrees;
- prove it for a parent node.

Abstract syntax trees, page-table trees, directory trees and type expressions can be reasoned about this way when their implementation actually follows a recursive structure.

The proof structure should match the data definition rather than be imposed by analogy.

## Loop invariants

A loop invariant I is a predicate expected to hold:

- before the first iteration;
- after every completed iteration;
- at loop termination.

A standard proof has three parts.

Initialization:

~~~text
precondition ⇒ I
~~~

Preservation:

~~~text
I and loop_guard and loop_body ⇒ I'
~~~

Termination use:

~~~text
I and not loop_guard ⇒ postcondition
~~~

The invariant alone does not prove termination. A separate progress argument may be required.

## Termination and variants

A variant is a quantity that moves monotonically toward a well-founded limit.

For a loop over i from 0 to n:

~~~text
n - i
~~~

decreases on each iteration and cannot decrease below zero.

This establishes termination if every iteration increments i and arithmetic cannot wrap in a way that violates the model.

Termination arguments matter in kernels because a correct invariant with a nonterminating loop can still hang the system.

## parse_u64: prefix invariant

ChrisASM parse_u64 reads one token digit at a time.

A useful loop invariant is:

~~~text
v equals the numerical value of the already-processed valid digit prefix
and
0 <= v <= UINT64_MAX
~~~

Initialization:

Before processing digits:

~~~text
v = 0
~~~

which is the value of the empty prefix.

Preservation:

For next digit d in base b, the parser first checks:

~~~text
v <= (UINT64_MAX - d) / b
~~~

Only then computes:

~~~text
v' = v·b + d
~~~

Therefore v' remains representable in uint64_t and equals the processed prefix extended by d.

At termination after all digits, v equals the full token value.

This is a real proof obligation represented directly by source checks.

## Why checking before multiplication matters

An unsafe pattern is:

~~~text
v = v·b + d
if v overflowed:
    fail
~~~

If the arithmetic already wrapped, information needed to detect the mathematical overflow may be lost.

The source precondition rearranges:

~~~text
v·b + d <= M
~~~

into:

~~~text
v <= (M - d) / b
~~~

for nonnegative values.

That transformation turns a potentially overflowing computation into a safe comparison before the state update.

## emit_u8: capacity invariant

ChrisASM maintains static section buffers of capacity ASM_SEC_MAX.

emit_u8 checks:

~~~text
g_cur is one of the initialized byte-buffer sections
and
g_len[g_cur] < ASM_SEC_MAX
~~~

before writing and incrementing length.

If the condition is false, it sets g_overflow and returns without writing.

A useful capacity invariant is:

~~~text
0 <= g_len[s] <= ASM_SEC_MAX
~~~

for each byte-backed section s under the intended state transitions.

When g_len[s] = ASM_SEC_MAX, no further byte is written.

This supports an out-of-bounds safety argument for the emitter path, assuming the length state itself has not been corrupted elsewhere.

## Fixed-capacity symbol tables

ChrisoImage allocates:

~~~text
sym[CHRISO_SYM_MAX]
~~~

and tracks nsym.

add_sym checks:

~~~text
img->nsym >= CHRISO_SYM_MAX
~~~

before appending.

A central invariant is:

~~~text
0 <= nsym <= CHRISO_SYM_MAX
~~~

For a successful append from nsym < max:

~~~text
new_nsym = old_nsym + 1
~~~

which remains <= max.

When at max, append fails.

The proof does not establish uniqueness of names by capacity alone. That requires the separate find_sym/update logic.

## Symbol uniqueness as a relational invariant

add_sym first searches for an existing name.

If one exists, it reuses or updates that entry subject to binding rules rather than appending a duplicate definition.

A candidate invariant is:

~~~text
among active symbol entries, no two independently defined entries represent the same accepted symbol identity
~~~

Proving that property fully requires analyzing name truncation, comparison rules, undefined-to-defined transitions and every writer of ChrisoImage.

This chapter does not claim that complete proof.

It illustrates an important rule: state an invariant no stronger than the reviewed evidence supports.

## patch_fixups: memory-safety obligations

patch_fixups processes each recorded local fixup.

Before writing four bytes it requires:

~~~text
id exists
target label is defined
target section equals fixup section
0 <= sec < 3
at + 4 <= g_len[sec]
~~~

The final condition proves that byte positions:

~~~text
at
at+1
at+2
at+3
~~~

all lie below g_len[sec].

This is a local memory-safety proof for the four-byte patch, assuming g_len[sec] itself does not exceed the actual section-buffer capacity.

The same function also computes the displacement:

~~~text
target_offset - (patch_offset + 4)
~~~

The range and cast to int32_t are separate semantic obligations from memory safety.

One proof does not automatically establish the other.

## chris_flags_bin: width invariant

For expected operand sizes, chris_flags_bin obtains a mask and computes:

~~~text
aa = a & mask
bb = b & mask
~~~

and stores:

~~~text
result = r & mask
~~~

A straightforward invariant is:

~~~text
result has no set bit outside the selected operand width
~~~

For mask M:

~~~text
result & ~M = 0
~~~

This remains true regardless of whether the mathematical operation generated higher bits.

Carry and overflow preserve information about effects not represented in the stored result.

## Distinguishing representation invariant from semantic correctness

The masked-result invariant proves only a representation property.

It does not prove:

- ADD uses correct carry semantics;
- SUB uses correct borrow polarity;
- every operand size is valid;
- signed overflow is correct;
- the decoder selected the right arithmetic operation.

A strong verification effort decomposes correctness into multiple independent obligations rather than treating one passing property as global correctness.

## gfx_mark_dirty: rectangle invariant

The graphics layer stores up to GFX_DIRTY_MAX dirty rectangles.

gfx_mark_dirty clips candidate coordinates against framebuffer bounds, rejects empty rectangles, merges touching rectangles, and if capacity is reached collapses the state to one full-screen rectangle.

A useful stored-rectangle invariant is:

~~~text
0 <= x0 < x1 <= framebuffer width
0 <= y0 < y1 <= framebuffer height
~~~

for every active dirty rectangle.

The clipping code establishes the boundary conditions before insertion.

The capacity logic maintains:

~~~text
0 <= g_dirty_count <= GFX_DIRTY_MAX
~~~

under normal transitions through gfx_mark_dirty.

## Full-screen fallback as invariant preservation

When g_dirty_count is already at capacity, appending another rectangle would violate the fixed-array bound.

Instead the function sets:

~~~text
g_dirty_count = 1
dirty[0] = full framebuffer
~~~

This loses precision but preserves correctness of repaint coverage.

The abstract property being preserved is not “dirty rectangles remain minimal.”

It is:

~~~text
every region requiring presentation is contained in the union of stored dirty rectangles
~~~

Replacing many rectangles by the entire screen maintains that coverage property while sacrificing performance.

This is a systems trade-off expressed as invariant weakening and cost increase.

## Safety versus liveness

Safety properties state that something bad never occurs.

Examples:

- no out-of-bounds write;
- count never exceeds capacity;
- invalid symbol index is not accepted.

Liveness properties state that something good eventually occurs.

Examples:

- a queued job eventually runs;
- a blocked thread eventually becomes runnable;
- dirty data is eventually presented.

A proof of safety does not prove liveness.

Deadlock-free memory bounds and starvation-free scheduling are different obligations.

## Local versus global invariants

A local invariant applies to one function or data structure.

A global invariant spans components.

Example local property:

~~~text
nsym <= CHRISO_SYM_MAX
~~~

Potential global property:

~~~text
every relocation's sym_index refers to an active symbol throughout linking
~~~

Global invariants are harder because every mutating path must preserve them.

Documentation should distinguish locally checked facts from architecture-wide claims.

## Representation invariants

A representation invariant characterizes valid concrete states of a data structure.

Examples:

~~~text
0 <= count <= capacity
head index is inside ring range
tree parent/child relation is acyclic
free-list nodes are not simultaneously allocated
~~~

Public operations should:

1. require the invariant at entry;
2. preserve it on success;
3. define what remains true on failure.

Partial failure paths are part of the proof obligation.

## Failure atomicity

An operation is failure-atomic with respect to some state if failure leaves that state unchanged or in a defined recoverable form.

Not every ChrisOS helper reviewed here is documented as failure-atomic.

For example, a function may set an overflow flag before the caller later rejects the aggregate assembly.

The relevant guarantee can therefore be:

~~~text
failure leaves an explicitly poisoned state that callers must reject
~~~

rather than full rollback.

Correct proof statements must match actual recovery behavior.

## Concurrency invalidates unstated sequential proofs

A proof over sequential transitions can fail under concurrent interleaving.

Suppose:

~~~text
count < capacity
~~~

is checked by two threads, both then increment count without synchronization.

Each thread's local sequential argument can appear valid while the combined execution exceeds the intended bound or overwrites the same slot.

Concurrent correctness requires atomic operations, locks or another synchronization model in the assumptions.

No mathematical proof should silently assume single-threaded execution when the implementation is shared.

## Inductive invariants for state machines

For transition system:

~~~text
S --T--> S'
~~~

predicate I is inductive when:

Initialization:

~~~text
all initial states satisfy I
~~~

Preservation:

~~~text
I(S) and T(S,S') imply I(S')
~~~

Then every reachable state satisfies I.

This method scales from loops to schedulers, protocol states, allocators and emulators.

The challenge is usually finding an invariant strong enough to imply the desired property but weak enough to be preserved.

## Strengthening an invariant

Suppose the desired postcondition is:

~~~text
output contains processed input prefix
~~~

A weak loop invariant stating only:

~~~text
i <= n
~~~

cannot prove it.

A stronger invariant might state:

~~~text
0 <= i <= n
and
output[0:i] equals transform(input[0:i])
~~~

The extra relationship carries the information needed for the final proof.

Invariants are therefore design artifacts, not merely assertions discovered after coding.

## Assertions and runtime checks

A runtime assertion checks one execution state.

A proof establishes a property over all states covered by its assumptions.

Assertions are still useful because they:

- detect violated assumptions;
- encode representation invariants;
- narrow fault location;
- provide executable documentation.

Testing samples executions; proof reasons over a domain.

The methods complement each other.

## Property-based and exhaustive testing

For small finite domains, exhaustive testing can evaluate every input.

For larger domains, property-based tests generate many examples of a general property.

Examples:

~~~text
mask(result) == result
decode(encode(x)) == x for valid x
count never exceeds capacity under generated operations
~~~

Passing tests increases evidence but does not become a proof unless the tested domain is exhaustive and the execution model matches the specification.

## Proof obligations at trust boundaries

Kernel and parser boundaries deserve explicit obligations.

For untrusted input, typical requirements include:

- length arithmetic cannot overflow;
- every index is in bounds before dereference;
- every decoded enum is validated before dispatch;
- object references point to active objects;
- failure paths do not leave privileged stale state;
- copying respects source and destination capacity.

Security review becomes more precise when each requirement is a proposition attached to a transition.

## Performance properties also need proof boundaries

Complexity claims are propositions about cost models.

A loop scanning n entries can justify O(n) comparisons if each iteration performs bounded work.

That does not prove constant wall-clock cost per iteration under caches, page faults or I/O.

Similarly, merging dirty rectangles can reduce later copy work while increasing insertion work.

Algorithmic proofs should state which operations count as unit cost.

The next complexity chapters formalize those models.

## Validation evidence

The deterministic checker associated with this chapter validates representative obligations:

- induction over prefix sums;
- loop-invariant preservation for Horner parsing;
- the pre-multiply uint64 overflow inequality;
- finite-capacity append preservation;
- four-byte patch bounds;
- width-mask closure;
- dirty-rectangle clipping and count bounds;
- full-screen fallback coverage.

It also verifies current source anchors for parse_u64, emit_u8, add_sym, patch_fixups, chris_flags_bin and gfx_mark_dirty.

The checker demonstrates documented properties over the modeled examples. It is not a formal proof of the whole ChrisOS codebase.

## Current limitations

This chapter does not provide:

- machine-checked proofs;
- Hoare logic in full formal detail;
- separation logic;
- temporal logic;
- model checking;
- SMT-based verification;
- concurrency logics;
- verified compilation;
- proof-carrying code.

Those methods can build on the same discipline of explicit state, assumptions and preserved predicates.

## Roadmap boundary

The proof discipline established here supports later chapters on:

- complexity;
- recurrences;
- data structures;
- memory allocators;
- schedulers;
- filesystems;
- parsers;
- virtual machines;
- concurrent algorithms.

Later chapters should state important representation and transition invariants directly instead of describing behavior only narratively.

## Revision provenance

Implementation-facing statements were reconciled against ChrisOS main revision da3df29cb397932c43d32373871fb9380e688ade.

Reviewed sources:

- compiler/chrisasm/chrisasm.c;
- compiler/chrisld/chriso.h;
- chrisvm/cpu/emulator/flags.c;
- kernel/gfx/graphics.c.

Reviewed symbols:

- parse_u64;
- emit_u8;
- add_sym;
- patch_fixups;
- chris_flags_bin;
- gfx_mark_dirty.

The examples establish local proof obligations supported by the inspected source. They do not claim global formal verification, complete concurrency correctness or proof of all callers.
