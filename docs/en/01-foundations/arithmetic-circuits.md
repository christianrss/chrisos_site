---
id: arithmetic-circuits
lang: en
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
- chrisvm/cpu/emulator/flags.c
- chrisvm/chris_arch.h
- chrisvm/chrisvm.h
symbols:
- chris_flags_bin
- chris_cc_true
depends_on:
- boolean-algebra
- combinational-logic
related:
- data-representation-layout
- emulator-theory
- cpu-datapath-isa
---

# Adders, ALUs and finite-width arithmetic

## The mathematical object being implemented

An unsigned word of width w represents an integer from zero through 2^w − 1. Addition stored in that word is addition modulo 2^w: discard multiples of 2^w and retain the remainder. This is a statement about representation, not permission to discard overflow in an allocation size or address calculation. A caller must decide whether wrapping is intended. Carry and overflow flags provide information lost when the full mathematical result is reduced to a word.

The same bits can represent a signed two's-complement integer. If the high bit is zero, the signed value equals the unsigned value. Otherwise subtract 2^w. At eight bits, `0xff` represents unsigned 255 or signed −1. The adder does not need different sum gates for these interpretations. It does need different predicates to report whether the mathematical result fits the selected interpretation. Conflating these predicates is a common emulator defect.

ChrisOS contains a software model of arithmetic status in `chrisvm/cpu/emulator/flags.c`. That model describes architectural results, not a transistor netlist. The gate structures below explain how finite-width arithmetic can be constructed. They are not claims that ChrisCPU simulates individual gates, or that a physical host processor uses a particular carry topology.

## Deriving a full adder

For one bit position, let a and b be operand bits and c be incoming carry. There are eight possible inputs. The integer a + b + c ranges from zero to three. Its low bit becomes the sum s; its high bit becomes outgoing carry k.

| a | b | c | s | k |
|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 |
| 0 | 0 | 1 | 1 | 0 |
| 0 | 1 | 0 | 1 | 0 |
| 0 | 1 | 1 | 0 | 1 |
| 1 | 0 | 0 | 1 | 0 |
| 1 | 0 | 1 | 0 | 1 |
| 1 | 1 | 0 | 0 | 1 |
| 1 | 1 | 1 | 1 | 1 |

Define propagate p = a XOR b and generate g = a AND b. Then s = p XOR c and k = g OR (p AND c). Generate means the position emits a carry regardless of incoming carry. Propagate means an incoming carry passes through. If both operands are zero, the position kills incoming carry. These meanings explain the equations rather than merely furnishing an expression to memorize.

An n-bit ripple adder connects each k to the next c. Every stage is constant-sized, so area grows linearly with width. In the worst case, a carry affects all stages; for a fixed gate model its propagation depth is O(n). Adding one to a word of all ones is a useful example: the result is zero and the final carry is one. The individual sum outputs need not settle simultaneously.

![Carry construction and architectural status](../../assets/diagrams/arithmetic-contract.svg)

## Carry lookahead and the cost of parallelism

For adjacent groups, define a group to propagate only if every position propagates. A high group H combined with a low group L has P = P_H P_L and G = G_H OR (P_H G_L). Its outgoing carry is G OR (P c_in). This combination is associative: grouping three adjacent ranges in either order gives the same carry function. Associativity permits a tree or prefix network to compute carries with logarithmic logical depth instead of a linear chain.

Logical depth is only one constraint. A prefix network introduces more intermediate nodes, wiring, fanout and capacitance. A design with fewer gate levels may lose some advantage after physical placement and routing. Ripple, carry-select and several prefix organizations occupy different area, power and delay trade-offs. An emulator using a host `+` operator does not expose which of these structures the host employs. Its performance must be measured at the software boundary.

Carry-save addition solves another problem: reducing three operand words to two words without carrying across the entire width immediately. At each position, a full adder produces a sum bit and a carry for the next weight. Repeated reduction is useful for multiplication partial products; a final carry-propagating adder is still required. Carry-save representation is therefore an intermediate redundant representation, not a new interpretation of the final architectural register.

## Subtraction and borrow

Within a width w, a − b is equivalent to a + NOT(b) + 1 modulo 2^w. A shared adder can conditionally invert b and select the initial carry. A control bit for subtraction can drive XOR gates on every b bit and the low carry input. This yields arithmetic reuse without changing the meaning of the output word.

The final carry of this complemented addition is not the same polarity as an unsigned borrow indication. If unsigned a is smaller than unsigned b, subtraction requires a borrow. ChrisCPU's subtraction status uses that borrow convention for CF. For SBB with incoming CF = 1, borrow occurs when a ≤ b; otherwise it occurs when a < b. Testing `a < b + 1` in the original width would be wrong when b is the maximum word, because b + 1 itself wraps. The implementation compares a and b directly.

For eight bits, `0x00 − 0x01` gives `0xff`, CF = 1 and OF = 0. The unsigned result underflows, but signed zero minus one is representable. Conversely, `0x80 − 0x01` gives `0x7f`, CF = 0 and OF = 1: unsigned 128 minus one is fine, while signed −128 minus one is outside the range. The retained result alone cannot distinguish these cases.

## Signed overflow as a Boolean predicate

For addition, signed overflow occurs when operands have the same sign and the result has the opposite sign. In bit-vector form, `((a XOR r) AND (b XOR r) AND sign_bit) != 0` detects that case. For subtraction the operands must have different signs, and the result must differ in sign from a: `((a XOR b) AND (a XOR r) AND sign_bit) != 0`.

| Eight-bit operation | Result | CF | OF | Interpretation |
|---|---|---|---|---|
| `0x7f + 0x01` | `0x80` | 0 | 1 | 127 + 1 exceeds signed maximum |
| `0xff + 0x01` | `0x00` | 1 | 0 | −1 + 1 fits signed range |
| `0x80 + 0x80` | `0x00` | 1 | 1 | −128 + −128 does not fit |
| `0x80 - 0x01` | `0x7f` | 0 | 1 | Signed negative result wraps positive |

The sign bit SF reports the high bit of the stored result, not the sign of an unbounded mathematical result. After subtraction, SF XOR OF recovers the signed less-than predicate. Unsigned less-than instead uses CF. Equality uses ZF in both interpretations. This explains why `chris_cc_true` uses `sf != of` for condition 12, but CF for condition 2. A compiler selecting the wrong condition can produce correct-looking results on positive small integers and fail near a sign boundary.

## ChrisCPU's concrete interface

`chris_flags_bin(alu, a, b, os, flags, result)` receives operand size `os` in bytes. The intended widths are 1, 2, 4 and 8 bytes. It masks operands before computation, derives the sign bit from the width, optionally stores the result through a caller-owned pointer, and returns updated status. It allocates nothing and contains no shared mutable state. A null result pointer suppresses the store; it does not suppress flag calculation.

The helper assumes a valid width and ALU selector from its caller. It does not return a validation error. In particular, the mask helper defaults to 64 bits while the sign-bit expression depends on `os`; arbitrary widths cannot safely be passed as if this were a general public arithmetic service. The fallback logical operation is XOR. These are interface preconditions, not input sanitization guarantees. A decoder boundary must constrain the values before invoking this helper.

For ADD and ADC, the implementation widens the calculation to `unsigned __int128`, retains the low-width result, and obtains CF from bits above the operand width. Widening before addition is essential for a 64-bit guest operand: merely adding in `uint64_t` would lose carry before it could be tested. The host compiler must support this extension. For SUB, CMP and SBB, unsigned subtraction gives the modular result and comparisons give borrow. No signed host overflow is required to model signed guest overflow.

## Status ownership and preservation

`write_status` clears and replaces six bits while preserving the other incoming bits, then forces bit 1 to one. The preservation rule matters because arithmetic must not accidentally erase unrelated machine state. The table describes this helper's observable behavior at the reviewed revision.

| Bit | Name | Computation |
|---|---|---|
| 0 | CF | Carry for addition; borrow for subtraction |
| 2 | PF | Even parity of the least significant result byte |
| 4 | AF | Carry or borrow across the low nibble, from bit 4 of `a XOR b XOR r` |
| 6 | ZF | Width-masked result equals zero |
| 7 | SF | Width-selected high result bit |
| 11 | OF | Signed result outside the representable range |

Parity is reduced by successive XOR folds over one byte, so upper result bytes do not affect PF. For logical AND, TEST, OR and XOR, the helper sets CF, OF and AF to zero. That is the emulator's deterministic choice for AF; this chapter does not turn it into a universal x86 guarantee. CMP computes subtraction status, and TEST computes AND status. Whether an instruction writes an architectural destination is the executor's responsibility, outside this helper's contract.

The helper is reentrant for independent caller storage, but that does not make an entire CPU state safe for concurrent modification. Two host threads writing the same result pointer still need synchronization. Arithmetic flags and destination registers also need a coherent instruction-level update in the executor. A pure calculation routine cannot by itself provide precise exceptions or atomic memory operations.

## Multiplication, division and shifts in the larger ALU

Unsigned multiplication can be derived by writing b as the sum of its bits times powers of two. For every set bit b_i, add a shifted left by i. Two w-bit operands require up to 2w result bits. Truncation is a separate architectural decision. Array and tree multipliers implement parallel reductions; iterative shift-add designs reuse an adder over several steps. These constructions explain the design space without claiming a specific multiplier in ChrisCPU.

Unsigned division repeatedly selects quotient bits while maintaining a remainder. A correct completed operation satisfies a = q b + r and 0 ≤ r < b for nonzero b. Division by zero and an unrepresentable quotient require explicit architectural treatment. Signed division also has the exceptional minimum-value divided by −1 case in fixed width. Those operations are not implemented by `chris_flags_bin`; its result cannot serve as evidence for division semantics.

A shift discards bits at one edge and inserts bits at the other. Logical right shift inserts zeros; arithmetic right shift extends the sign bit. A barrel shifter can choose powers-of-two shifts through logarithmically many mux stages. Rotates recirculate discarded bits. Architectural count masking and flag behavior are additional rules: neither the mathematical shift nor the C host operator alone establishes the guest instruction contract.

## Validation and limits of the evidence

The repository includes a reproducible source probe, `scripts/check_arithmetic.py --source .source`. It compiles the actual `flags.c` into a temporary shared library and compares every eight-bit operand pair for ADD, ADC, SUB, SBB and CMP against an independent integer-range model. Both incoming carry values are checked for carry-consuming operations. Expected CF comes from unbounded unsigned range, OF from signed range, AF from low-nibble range, and PF from counting low-byte ones. It also checks logical operations, every condition-code predicate, preservation of unrelated flag bits and representative larger-width boundaries.

This probe establishes the tested helper behavior on the supplied source revision and host compiler. It does not execute decoded instructions, validate memory operands, boot a guest, characterize physical gate delays or prove the entire x86 instruction set. A passing helper probe is valuable precisely because its scope is explicit. Integration tests must separately establish that decoding, operand selection, writeback and exceptions use that arithmetic correctly.

## Further theoretical reading

[MIT 6.004 lecture notes](https://ocw.mit.edu/courses/6-004-computation-structures-spring-2009/pages/lecture-notes/) provide primary teaching material on combinational synthesis and multipliers. The derivations and implementation analysis above are specific to this chapter; the external material is a route to additional circuit design detail. Current implementation claims are tied to the source revision in the page metadata.
