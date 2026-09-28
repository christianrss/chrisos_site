---
id: recursion-recurrences-amortization
lang: en
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - kernel/gfx/shader/sh_int.h
  - kernel/gfx/shader/sh_parse.c
  - compiler/clvm/clvm_vm.h
  - compiler/clvm/clvm_vm.c
symbols:
  - ShComp
  - Ast
  - enter
  - leave
  - parse_primary
  - parse_unary
  - parse_bin
  - parse_expr
  - node_new
  - clvm_vm_push64
  - clvm_vm_pop64
  - ClvmVm
depends_on:
  - algorithmic-complexity
  - proof-invariants-induction
related:
  - data-structures
  - arrays-lists-stacks-queues
  - parsing
  - shader-frontend
---

# Recursion, recurrences and amortized analysis

<div class="abstract">
Recursion defines a computation in terms of smaller instances of the same computation. Recurrences model the cost of that self-reference, while amortized analysis distributes occasional expensive operations over an entire sequence rather than treating every operation independently. These tools are especially important in systems software because recursive control flow consumes stack space, parser nesting may be attacker-controlled, and an operation with good amortized cost can still have an unacceptable worst-case latency. This chapter develops recursive correctness, recurrence solving and aggregate/accounting/potential methods, then reconciles them with current ChrisOS source: the shader parser is recursive descent with an explicit nesting bound of 32, AST creation is bounded by 512 nodes, and CLVM maintains fixed-capacity operand and call stacks with explicit overflow/underflow checks.
</div>

## Prerequisites and scope

This chapter depends on algorithmic complexity and proof by induction.

Induction proves a property over recursively constructed objects. Recursion uses the same structure operationally.

A recursive algorithm requires:

- a domain of problem instances;
- one or more base cases;
- recursive cases that reduce the problem;
- a progress measure proving termination;
- a resource model for time and space.

Recurrence relations then describe how cost changes with input size.

Amortized analysis is related but distinct: it reasons about a sequence of operations whose individual costs can vary.

~~~text
recursive definition
      ↓
termination argument
      ↓
recurrence for cost
      ↓
asymptotic bound

operation sequence
      ↓
expensive and cheap steps
      ↓
aggregate/accounting/potential
      ↓
amortized bound
~~~

## Recursive definitions

A recursive definition refers to itself on smaller structure.

Factorial is the standard example:

~~~text
0! = 1
n! = n · (n-1)! for n > 0
~~~

The base case stops expansion. The recursive case decreases n.

Without a decreasing measure, a recursive definition can fail to terminate.

For data structures, recursive shape can replace numeric size. A tree algorithm may recurse on child subtrees, where each child contains fewer nodes than the original tree.

## Operational recursion

At runtime, a recursive function call usually creates another activation record.

An activation may contain:

- return address;
- saved registers;
- local variables;
- arguments or spilled values;
- alignment/padding required by the ABI.

For recursion depth d and frame size f, stack consumption is approximately:

~~~text
O(d · f)
~~~

plus ABI- and compiler-specific overhead.

That space is not abstract. In kernels, bootloaders, firmware and embedded systems, stack capacity is often fixed and comparatively small.

A mathematically terminating recursion can still fail operationally by exhausting its stack before reaching the base case.

## Base-case correctness

A recursive proof normally mirrors recursive code.

For function F(n):

1. prove the base case returns the required result;
2. assume the recursive call is correct for a smaller argument;
3. prove the current frame transforms that result into the correct result for n.

The induction hypothesis is valid only when recursive calls are made on instances covered by the measure.

A function that sometimes recurses on the same size does not satisfy the standard termination proof.

## Progress measures

A progress measure maps a state to a well-founded ordered set.

Common measures include:

- integer n decreasing toward zero;
- number of unprocessed tokens;
- remaining tree height;
- number of nodes not yet visited;
- interval length;
- nesting depth relative to a fixed limit.

A valid recursive step must move the measure toward termination.

For mutually recursive functions, the measure may need to cover the combined transition system rather than one function independently.

## Direct versus mutual recursion

Direct recursion occurs when F calls F.

Mutual recursion occurs when:

~~~text
F → G → H → F
~~~

Recursive-descent parsers commonly use mutual recursion because grammar nonterminals call one another.

Current ChrisOS shader parsing uses both patterns:

- parse_unary can call itself;
- parse_bin can call itself at stronger precedence;
- parse_primary can call parse_expr for parenthesized or indexed expressions;
- expression parsing calls lower-level parsing helpers.

The recursion therefore follows grammar structure rather than one single textbook recurrence.

## Recursive descent parsing

A recursive-descent parser assigns parser functions to grammar layers.

Conceptually:

~~~text
expression
  └─ binary-precedence
       └─ unary
            └─ primary
                 ├─ literal
                 ├─ identifier
                 ├─ call
                 ├─ constructor
                 └─ parenthesized expression
~~~

This organization makes precedence and syntactic nesting explicit.

It also makes parser stack depth proportional to syntactic nesting and recursive operator structure unless transformed into iteration.

## ChrisOS shader parser depth contract

Current sh_int.h defines:

~~~text
SH_NEST_MAX = 32
SH_AST_MAX  = 512
~~~

ShComp contains:

~~~text
int depth;
Ast ast[SH_AST_MAX];
int nast;
~~~

The parser's enter helper rejects another nested level when:

~~~text
depth >= SH_NEST_MAX
~~~

and records a nesting error.

Only after passing the check does it increment depth.

leave decrements depth when it is positive.

This is an explicit resource bound around parser recursion. It is stronger than relying on the host or kernel stack to fail naturally.

## Parser depth invariant

For successful enter/leave pairs, a useful invariant is:

~~~text
0 <= depth <= SH_NEST_MAX
~~~

A successful enter from depth < SH_NEST_MAX produces:

~~~text
depth' = depth + 1
~~~

A matching leave reduces it again.

The source does not establish that arbitrary future edits can never miss a leave on every failure path; that requires path-sensitive review or tests.

The current helpers nevertheless encode the intended bound directly.

## AST capacity as a second bound

Recursion depth and total syntax size are different resources.

A shallow expression may still create many nodes.

node_new checks:

~~~text
nast >= SH_AST_MAX
~~~

and rejects further nodes before indexing the AST array.

Thus the parser has at least two independent resource constraints:

| Resource | Bound |
|---|---:|
| recursive nesting | 32 |
| AST nodes | 512 |

A safe parser needs both kinds of limits when input size and nesting are externally controlled.

## Recursive binary-precedence parsing

parse_bin receives a minimum precedence and:

1. parses a unary/primary left operand;
2. inspects the next operator;
3. stops if precedence is below the required level;
4. consumes the operator;
5. recursively parses the right side with a stronger minimum precedence;
6. creates a binary AST node.

This form is a precedence-climbing recursive parser.

For a token stream of length n, ordinary successful parsing is intended to process tokens monotonically rather than restart from the beginning.

The relevant high-level cost is therefore linear in consumed tokens for the supported grammar, subject to bounded scans such as operator-table lookup and error recovery.

The recursion depth is not necessarily equal to n because precedence and nesting limits constrain the structure.

## Recursion and associativity

The choice of recursive threshold influences associativity.

Calling the right side with:

~~~text
prec + 1
~~~

causes operators at the same precedence to stay on the outer loop rather than be absorbed into the right recursive call.

That is the usual mechanism for left-associative operators in precedence climbing.

This is an example of recursion encoding semantics, not merely implementation style.

Changing the recurrence structure can change the parse tree.

## CLVM stack bounds

CLVM maintains two fixed-capacity arrays:

~~~text
stack[CLVM_STACK_MAX]   where CLVM_STACK_MAX = 256
calls[CLVM_CALL_MAX]    where CLVM_CALL_MAX = 64
~~~

with stack pointers sp and csp.

The operand stack is not the host C recursion stack. It is VM state.

Nevertheless, the same bounded-resource reasoning applies.

clvm_vm_push64 rejects a push when:

~~~text
sp == CLVM_STACK_MAX
~~~

and clvm_vm_pop64 rejects a pop when:

~~~text
sp == 0
~~~

The current longjmp restoration path also validates restored sp and csp against the two maxima.

## Recursive guest execution and host recursion

A virtual machine can represent guest call nesting without recursively calling the host interpreter.

That distinction matters.

A guest call can push a return PC into a VM-managed call stack and continue in an iterative dispatch loop.

Benefits include:

- explicit overflow checking;
- predictable guest depth limit;
- easier serialization of VM state;
- separation from host thread stack size.

Therefore “the guest program is recursive” does not imply “the host interpreter recursively calls itself for every guest frame.”

The current CLVM state model provides bounded explicit call storage.

## Recurrence relations

A recurrence defines a quantity using smaller instances.

Examples:

Linear recursion:

~~~text
T(n) = T(n-1) + c
~~~

Binary divide and conquer:

~~~text
T(n) = 2T(n/2) + cn
~~~

Halving recursion:

~~~text
T(n) = T(n/2) + c
~~~

A recurrence needs a base condition such as T(1) = c0.

Without the base case, the recurrence does not fully define the finite cost.

## Solving a linear recurrence

Consider:

~~~text
T(n) = T(n-1) + c
T(0) = d
~~~

Expand:

~~~text
T(n)
= T(n-1) + c
= T(n-2) + 2c
...
= T(0) + nc
= d + nc
~~~

Therefore:

~~~text
T(n) = Θ(n)
~~~

This pattern describes many recursive linear traversals.

The recursive and iterative implementations can have the same time complexity while differing in stack space.

## Halving recurrences

For:

~~~text
T(n) = T(n/2) + c
~~~

the argument can be halved only about log2(n) times before reaching 1.

Therefore:

~~~text
T(n) = Θ(log n)
~~~

Binary search is the canonical example.

The result assumes each recursive level performs constant additional work.

If each level scans an n-sized region, the recurrence changes.

## Divide-and-conquer recurrences

For:

~~~text
T(n) = aT(n/b) + f(n)
~~~

the total cost combines:

- number of recursive subproblems a;
- shrink factor b;
- non-recursive work f(n).

The Master Theorem classifies many regular recurrences by comparing f(n) with:

~~~text
n^(log_b a)
~~~

It does not apply to every recurrence.

Irregular splits, changing coefficients or data-dependent recursion may require substitution, recursion trees or other methods.

## Recursion trees

A recursion tree expands work by level.

For merge-sort-like recurrence:

~~~text
T(n) = 2T(n/2) + n
~~~

each level performs total Θ(n) work, while the tree has Θ(log n) levels.

Thus:

~~~text
T(n) = Θ(n log n)
~~~

The method makes it easier to see where work accumulates.

It also helps reason about parallelism because independent subtrees can potentially execute concurrently.

## Space recurrences

Time recurrences alone are insufficient for recursive systems code.

For depth-first recursion with one active child at a time:

~~~text
S(n) = S(smaller(n)) + frame_space
~~~

Space depends on maximum active depth, not total number of calls.

A full binary recursion can make exponentially many calls while still using only O(depth) active stack frames when subcalls return before siblings execute.

Time and peak space therefore need separate models.

## Tail recursion

A call is in tail position when its result becomes the caller's result with no remaining work.

Some compilers can transform tail recursion into a jump, eliminating additional stack frames.

This optimization is not guaranteed by the C language for arbitrary code, and a kernel design should not rely on it unless toolchain behavior is part of the validated contract.

An explicit loop communicates constant-stack intent more reliably across compilers.

## Recursion versus explicit stacks

Recursive traversal:

~~~text
visit(node):
    for child in children(node):
        visit(child)
~~~

can be transformed into an explicit stack:

~~~text
push(root)
while stack not empty:
    node = pop()
    push children
~~~

The iterative form moves control state from call frames into a data structure.

Advantages can include:

- explicit capacity;
- heap-backed growth if permitted;
- resumability;
- serialization;
- control over traversal order.

The trade-off is more manual state management.

## Amortized analysis

Amortized analysis bounds average cost per operation over a worst-case sequence.

It is not probabilistic average-case analysis.

If m operations have total cost at most:

~~~text
C(m)
~~~

then amortized cost is:

~~~text
C(m) / m
~~~

A single operation may still be much more expensive than the amortized bound.

That distinction matters for interrupt latency and real-time constraints.

## Aggregate method

The aggregate method computes the total cost of a sequence directly.

Consider a stack supporting PUSH, POP and MULTIPOP(k), where MULTIPOP removes up to k items.

An individual MULTIPOP can cost Θ(n).

Across a sequence of m operations starting from an empty stack, however, each element can be popped at most once after being pushed.

Therefore total pop work is bounded by total push work.

A sequence can have Θ(m) total primitive stack operations, yielding O(1) amortized cost per high-level operation under the standard model.

## Accounting method

The accounting method assigns an artificial charge to each operation.

Cheap operations may be overcharged; the surplus pays for future expensive operations.

For a dynamic array that doubles capacity:

- charge append more than its immediate one-slot write;
- store credit on existing elements;
- use accumulated credit when a resize copies them.

The accounting invariant requires credit never to become negative.

The result is a proof device, not a runtime banking mechanism.

## Potential method

The potential method associates a nonnegative potential Φ(state) with each data-structure state.

Amortized cost is:

~~~text
actual cost
+ Φ(after)
- Φ(before)
~~~

Summed over a sequence, intermediate potentials telescope:

~~~text
Σ amortized
=
Σ actual
+ Φ(final)
- Φ(initial)
~~~

If potential is bounded below and starts from a known value, amortized bounds follow.

Potential is useful when one scalar captures how much deferred work is stored in the current state.

## Dynamic-array doubling proof

Suppose capacity begins at 1 and doubles whenever an append finds the array full.

Resizes copy:

~~~text
1 + 2 + 4 + ... + 2^k
~~~

elements before reaching capacity around n.

The geometric sum is:

~~~text
2^(k+1) - 1 < 2n
~~~

Therefore n appends perform:

- n writes of new elements;
- fewer than 2n copies due to resizing.

Total work is O(n), so append is O(1) amortized.

The individual append that triggers a resize is still O(n).

## Growth factor trade-offs

Doubling is not the only geometric policy.

For factor g > 1:

- larger g reduces resize frequency;
- larger g increases unused capacity after growth;
- smaller g reduces slack but copies more often.

The amortized O(1) result depends on geometric growth, not specifically factor 2.

Linear growth such as “increase capacity by 1 every time” causes:

~~~text
1 + 2 + ... + n = Θ(n²)
~~~

total copying over n appends.

## Amortized complexity in systems code

An amortized guarantee is insufficient when one operation cannot tolerate the expensive step.

Examples include:

- hard interrupt paths;
- spinlock-held critical sections;
- scheduler hot paths;
- device submission paths with strict latency budgets.

Systems designs often prefer:

- fixed-capacity arrays;
- preallocated pools;
- rings;
- incremental rehashing;
- batched maintenance;
- background reclamation.

The objective is sometimes a stronger per-operation bound rather than the best aggregate memory efficiency.

## Failure and saturation

Recursive algorithms fail differently from amortized dynamic structures.

Recursive failure modes include:

- missing base case;
- non-decreasing argument;
- cyclic structure where acyclicity was assumed;
- host stack overflow;
- explicit nesting-limit rejection.

Dynamic/amortized structures may fail due to:

- allocation failure;
- capacity overflow;
- integer overflow in growth calculations;
- pointer invalidation after relocation;
- latency spike during resize.

Correct contracts state these failure conditions independently of asymptotic cost.

## Security implications

Input-controlled recursion is a denial-of-service boundary.

Adversarial input can attempt to maximize:

- nesting depth;
- AST node count;
- backtracking;
- error-recovery work;
- allocation pressure.

The reviewed shader parser limits both nesting and AST size.

Those limits reduce resource-exhaustion risk, but this chapter does not claim complete parser complexity protection against every malformed token sequence.

Similarly, VM stack limits convert unbounded guest nesting into explicit faults rather than allowing guest state to overrun fixed arrays.

## Concurrency

Recurrence analysis usually assumes one logical execution.

Parallel recursive algorithms require additional cost models:

- work: total operations;
- span: longest dependency chain;
- scheduling overhead;
- synchronization;
- memory-bandwidth contention.

Amortized analysis under concurrency also becomes harder because credits or potential may be associated with shared state.

A sequential amortized proof cannot silently be reused for a lock-free concurrent structure.

## Validation evidence

The chapter-specific deterministic checker validates:

- expansion of representative linear and halving recurrences;
- geometric-series cost for dynamic-array doubling;
- aggregate stack accounting;
- nonnegative potential in a simple growable-array model;
- bounded recursion-depth state transitions;
- bounded explicit stack push/pop;
- current source anchors for SH_NEST_MAX, SH_AST_MAX, enter, leave, recursive parse_unary/parse_bin behavior, CLVM_STACK_MAX and CLVM_CALL_MAX.

The checker validates the documented models and source boundary. It does not formally prove the complete parser or VM implementation.

## Current limitations

This chapter does not fully cover:

- Akra-Bazzi recurrence analysis;
- generating functions;
- randomized recurrences;
- parallel work/span schedulers;
- memoization and dynamic programming in depth;
- continuation-passing style;
- formal stack-usage verification;
- real-time response-time analysis.

Those topics can be added when later ChrisOS subsystems require them.

## Roadmap boundary

The curriculum transition is:

~~~text
complexity and proof
      ↓
recursion and recurrences
      ↓
amortized sequence analysis
      ↓
concrete arrays, lists, stacks and queues
      ↓
specialized structures and systems algorithms
~~~

The next chapter applies these models to linear data structures and distinguishes abstract operations from their actual ChrisOS representations.

## Revision provenance

Implementation-facing statements were reconciled against ChrisOS main revision da3df29cb397932c43d32373871fb9380e688ade.

Reviewed sources:

- kernel/gfx/shader/sh_int.h;
- kernel/gfx/shader/sh_parse.c;
- compiler/clvm/clvm_vm.h;
- compiler/clvm/clvm_vm.c.

Reviewed symbols:

- ShComp;
- Ast;
- enter;
- leave;
- parse_primary;
- parse_unary;
- parse_bin;
- parse_expr;
- node_new;
- ClvmVm;
- clvm_vm_push64;
- clvm_vm_pop64.

The source demonstrates explicit parser nesting and AST bounds plus VM-managed stack bounds. The general recurrence and amortized-analysis results are mathematical foundations and are not presented as claims that every ChrisOS subsystem uses those specific strategies.
