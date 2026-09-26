---
id: boolean-algebra
lang: en
type: technical-chapter
volume: 01-foundations
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources: []
symbols: []
depends_on:
  - transistor-cmos
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

allow_write = supervisor ∨ user_permission

take_exception = fault_present ∧ exception_enabled

Real CPUs use much richer structures, but Boolean composition remains the basis of control logic.

## From algebra to circuits

Boolean algebra states what relation should hold; combinational logic determines how that relation is implemented using gates, propagation paths and physical constraints.

The next chapter introduces decoders, multiplexers, encoders, comparators and arithmetic building blocks, turning symbolic expressions into connected datapaths.
