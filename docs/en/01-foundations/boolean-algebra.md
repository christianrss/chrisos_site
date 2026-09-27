---
id: boolean-algebra
lang: en
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
- chrisvm/cpu/emulator/flags.c
symbols:
- chris_cc_true
- write_status
depends_on:
  - logic-levels-noise-margins
related:
- combinational-logic
---

# Boolean algebra and logic representation

<div class="abstract">
Boolean algebra is the mathematical layer that separates digital reasoning from transistor voltages. It defines operations over two logical values, identities for transforming expressions, canonical representations and the distinction between logical equivalence and physical implementation. This chapter develops the algebra far enough to support gates, decoders, arithmetic circuits, instruction decoders and state machines.
</div>

## Logical values are an abstraction

The symbols 0 and 1 used in Boolean algebra are mathematical values. In hardware they are represented by voltage ranges, stored charge states, magnetic orientation or other physical encodings. The algebra deliberately ignores those details.

A Boolean variable can take one of two values. Common operations are:

| Name | Notation used here | Meaning |
|---|---|---|
| NOT | ¬A | complement |
| AND | A ∧ B | true only when both are true |
| OR | A ∨ B | true when at least one is true |
| XOR | A ⊕ B | true when inputs differ |
| NAND | ¬(A ∧ B) | complement of AND |
| NOR | ¬(A ∨ B) | complement of OR |

A gate implements one of these relations physically, but the relation itself is independent of the transistor topology.

## Truth tables

A truth table enumerates outputs for every combination of inputs. For two inputs there are four combinations.

| A | B | A ∧ B | A ∨ B | A ⊕ B |
|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | 0 | 0 |
| 0 | 1 | 0 | 1 | 1 |
| 1 | 0 | 0 | 1 | 1 |
| 1 | 1 | 1 | 1 | 0 |

Truth tables are complete but scale exponentially. A function of n independent Boolean variables has 2^n input combinations. Large systems therefore require algebraic, structural and algorithmic representations rather than explicit enumeration alone.

## Fundamental identities

Several identities permit expressions to be simplified without changing their logical function.

| Identity | Expression |
|---|---|
| identity | A ∧ 1 = A; A ∨ 0 = A |
| domination | A ∧ 0 = 0; A ∨ 1 = 1 |
| idempotence | A ∧ A = A; A ∨ A = A |
| complement | A ∧ ¬A = 0; A ∨ ¬A = 1 |
| involution | ¬(¬A) = A |
| commutative | A ∧ B = B ∧ A; A ∨ B = B ∨ A |
| associative | (A ∧ B) ∧ C = A ∧ (B ∧ C) |
| distributive | A ∧ (B ∨ C) = (A ∧ B) ∨ (A ∧ C) |

Boolean distributivity has a dual form in which OR distributes over AND, unlike ordinary arithmetic where addition does not distribute over multiplication.

These laws are not merely symbolic conveniences. Synthesis tools use equivalent transformations to change circuit area, logic depth, power and fan-out while preserving behavior.

## De Morgan's laws

De Morgan's laws connect complements of conjunction and disjunction:

¬(A ∧ B) = ¬A ∨ ¬B

¬(A ∨ B) = ¬A ∧ ¬B

They explain why NAND and NOR structures can replace AND/OR networks with inverted signals. They also matter when reasoning about active-low hardware signals. A line named RESET_N, for example, may assert reset when its electrical value is 0; De Morgan transformations help translate between positive and negative logic conventions.

## Principle of duality

Boolean algebra has a useful duality: interchanging AND with OR and 0 with 1 transforms valid identities into other valid identities.

For example:

A ∨ 0 = A

has the dual:

A ∧ 1 = A

Duality provides a systematic way to recognize symmetric properties and helps explain the complementary structure of CMOS pull-up and pull-down networks.

## Sum of products and product of sums

Any Boolean function can be represented in canonical forms.

A **minterm** is an AND term containing each variable or its complement. ORing the minterms for which the function is 1 yields a sum-of-products representation.

A **maxterm** is an OR term containing each variable or its complement. ANDing the maxterms corresponding to 0 outputs yields product of sums.

Canonical forms are often much larger than optimized circuits, but they establish completeness: an arbitrary finite truth table can be converted mechanically into a logic expression.

## Minterm example

Suppose F(A,B) is true only for input combinations 01 and 10. The corresponding minterms are:

¬A ∧ B

A ∧ ¬B

Therefore:

F = (¬A ∧ B) ∨ (A ∧ ¬B)

This is exactly XOR. The example shows how a truth table becomes an algebraic expression without guessing the result.

## Functional completeness

A set of logic operations is functionally complete if every Boolean function can be expressed using only operations from that set.

NOT + AND is complete when OR is constructed by De Morgan's law. NOT + OR is similarly complete. NAND alone is complete, as is NOR alone.

For NAND:

¬A = A NAND A

A ∧ B = ¬(A NAND B)

A ∨ B = (¬A) NAND (¬B)

This property is important physically because a cell library does not need an independent primitive for every logical function. Complex cells are introduced for efficiency, not because Boolean expressiveness requires them.

## XOR and parity

XOR deserves special attention because it represents addition modulo 2:

0 ⊕ 0 = 0
0 ⊕ 1 = 1
1 ⊕ 0 = 1
1 ⊕ 1 = 0

That makes XOR fundamental in adders, parity generation, checksums, linear feedback structures and many bit-manipulation algorithms.

For multiple inputs, XOR is 1 when an odd number of inputs are 1. This is parity behavior.

## Implication and equivalence

Digital conditions can also be expressed using implication and equivalence.

A → B is false only when A = 1 and B = 0. Algebraically:

A → B = ¬A ∨ B

Logical equivalence is true when both operands match:

A ↔ B = ¬(A ⊕ B)

Comparators and control logic frequently implement these concepts even if schematics use XOR, XNOR, AND and OR rather than implication symbols.

## Bit vectors

Computer hardware rarely manipulates isolated Boolean variables. Values are grouped into bit vectors.

An 8-bit vector contains bits b7 through b0. Depending on interpretation it may represent an unsigned integer, signed two's-complement integer, character, set of flags, part of an address or opaque binary data.

The Boolean layer does not assign meaning to the vector. Meaning comes from the next abstraction: encoding.

This separation is crucial in operating systems. The same 64-bit pattern can be treated as an address, an integer, a page-table entry or a collection of capability flags depending on context.

## Boolean algebra versus arithmetic algebra

The notation 0 and 1 can cause confusion. In Boolean algebra:

1 ∨ 1 = 1

but in integer arithmetic:

1 + 1 = 2

XOR behaves like one-bit addition without carry. AND participates in carry generation. Arithmetic circuits therefore combine Boolean operations to realize ordinary integer arithmetic.

Understanding this distinction prevents mistakes when moving between source-language operators, machine instructions and mathematical expressions.

## Logic minimization

Equivalent Boolean expressions can differ dramatically in hardware cost. Minimization attempts to reduce gate count, logic depth or another cost measure.

For small problems, Karnaugh maps provide a geometric method. For larger functions, algorithms such as Quine-McCluskey or synthesis heuristics operate on symbolic representations.

Optimization is constrained by physical concerns. An expression with fewer literal terms may have larger fan-out or worse timing. Modern synthesis therefore targets technology libraries and timing constraints rather than minimizing abstract gate count alone.

## Don't-care conditions

Some input combinations may be impossible or irrelevant. A decoder for decimal digits, for example, may receive a four-bit encoding where only 0000 through 1001 are valid. Remaining combinations can be marked don't-care, allowing simplification.

Don't-care assumptions are contracts. If supposedly impossible states occur because of faults, asynchronous transitions or future extensions, an aggressively optimized circuit may produce any output for those states.

The same systems principle appears in software: undefined or unreachable states enable optimization but become dangerous when assumptions are violated.

## Boolean reasoning in CPU control

Instruction decoders, privilege checks and control signals are large Boolean functions over opcode bits, mode bits and current state.

Conceptually:

decode_ADD = opcode_match ∧ valid_mode ∧ ¬fault

select_result = operation_valid ∧ destination_enabled

take_exception = fault_present ∧ exception_enabled

Real CPUs use much richer structures, but Boolean composition remains the basis of control logic.

## From algebra to circuits

Boolean algebra states what relation should hold; combinational logic determines how that relation is implemented using gates, propagation paths and physical constraints.

The next chapter introduces decoders, multiplexers, encoders, comparators and arithmetic building blocks, turning symbolic expressions into connected datapaths.

## Shannon decomposition turns a function into selection

Fix a variable X in a Boolean function F. Define F_0 as the remaining function when X = 0 and F_1 when X = 1. Then F = (NOT X AND F_0) OR (X AND F_1). Exactly one branch is enabled for each Boolean value of X. The equation is therefore a proof of equivalence, not a heuristic: substituting either value reproduces the original function's corresponding row subset.

For F = A XOR B, choosing X = A gives F_0 = B and F_1 = NOT B. A mux selecting B or its complement implements XOR. Repeating decomposition creates a decision tree. Sharing identical residual functions can compress that tree into a decision graph, although variable order can dramatically change its size. A compact Boolean expression and a compact decision graph are not guaranteed to coincide.

This decomposition also clarifies why a hardware mux does not mean “run one software branch.” Both input circuits can physically evaluate, while the select signal controls which value reaches the output. In C, a conditional expression evaluates only its selected value expression. Functional agreement on pure Boolean inputs does not imply agreement on side effects, exceptions, bus traffic or evaluation cost.

## Bit-vector masks and preservation proofs

To replace selected bits in a word, define a mask M with ones exactly at the positions to replace. Then new = (old AND NOT M) OR (value AND M). At a position where M is zero, the expression reduces to old; where M is one, it reduces to value. This bitwise proof establishes both the update and the preservation of all other positions. It is stronger than checking one hexadecimal example.

`write_status` in ChrisCPU's `flags.c` uses this principle by clearing the status-bit set before inserting newly computed flags. Bit 1 is then forced to one explicitly. The distinction between preserved, replaced and forced bits is part of the interface. A mask with one accidental extra bit could silently alter interrupt control or another unrelated field even when the arithmetic result is correct.

Logical `&&` and `||` in C normalize truth values and short-circuit evaluation. Bitwise `&` and `|` operate on all bit positions and do not provide that short-circuit contract. Thus `pointer && pointer->field` can guard the dereference, while replacing `&&` with `&` does not preserve safety. Algebraic rewrites of pure propositions cannot be applied blindly to expressions that perform memory accesses or mutate state.

## Conditions implemented by ChrisCPU

`chris_cc_true` extracts CF, PF, ZF, SF and OF from an incoming flag word and selects a predicate using `cc & 15`. Complementary conditions form adjacent pairs. For example, unsigned-below-or-equal is CF OR ZF, while unsigned-above is NOT CF AND NOT ZF. De Morgan's law proves they are complements for every flag combination, including combinations not normally produced by one particular arithmetic instruction.

| Relation after comparison | Predicate | Opposite |
|---|---|---|
| Unsigned below | CF | NOT CF |
| Equal | ZF | NOT ZF |
| Unsigned below or equal | CF OR ZF | NOT CF AND NOT ZF |
| Signed less | SF XOR OF | SF equals OF |
| Signed less or equal | ZF OR (SF XOR OF) | NOT ZF AND (SF equals OF) |

These are concrete predicates from the inspected helper, not a complete permission or exception policy. Signed comparison needs OF because the sign of a wrapped subtraction alone is insufficient. The derivation is developed in [Arithmetic circuits](arithmetic-circuits.md). The reproducible arithmetic probe checks all 32 combinations of the five relevant flags against all sixteen conditions, including the selector's low-four-bit behavior. That establishes this finite Boolean mapping; it does not establish the correctness of a decoder choosing the condition or of a branch executor applying its destination.
