---
id: number-systems-binary-arithmetic
lang: en
type: technical-chapter
volume: 01-foundations
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - chrisvm/cpu/emulator/flags.c
  - chrisvm/chris_arch.h
  - compiler/chrisasm/chrisasm.c
  - kernel/gfx/graphics.c
symbols:
  - chris_flags_bin
  - chris_cc_true
  - ChrisArchitectureState
  - parse_u64
  - emit_u32
  - emit_u64
  - gfx_rgb
depends_on:
  - boolean-algebra
related:
  - arithmetic-circuits
  - data-representation-layout
  - machine-code
  - x86-registers-flags
---

# Number systems and binary arithmetic

<div class="abstract">
Computers operate on finite bit vectors interpreted under explicit numerical contracts. Positional notation, base conversion, unsigned ranges, two's-complement signed interpretation, modular arithmetic, carries, borrows, shifts, masks, sign extension and overflow are the mathematical layer connecting Boolean bits to machine arithmetic. This chapter develops that layer and reconciles it with current ChrisOS source: ChrisCPU masks arithmetic to operand widths and computes architectural status flags, ChrisASM parses decimal and hexadecimal constants and emits little-endian words, ChrisArchitectureState stores fixed-width architectural fields, and graphics code packs byte-sized color channels.
</div>

## Prerequisites and scope

The required prerequisite is Boolean algebra. Individual bits already have values 0 or 1 and Boolean operations have defined truth tables. This chapter adds numerical interpretation.

~~~text
Boolean bits
    ↓
ordered bit vector
    ↓
positional numerical interpretation
    ↓
finite-width arithmetic
    ↓
machine instructions and data formats
~~~

The same bit vector can represent an unsigned integer, a signed integer, a mask, an address, a color, an instruction field or opaque data. Arithmetic is valid only after interpretation and width are known.

## Positional notation

A base-b positional numeral with digits d_n ... d_1 d_0 represents:

~~~text
value = Σ d_i · b^i
~~~

where every digit satisfies 0 <= d_i < b.

For decimal:

~~~text
472 = 4·10² + 7·10¹ + 2·10⁰
~~~

For binary:

~~~text
101101₂
= 1·2⁵ + 0·2⁴ + 1·2³ + 1·2² + 0·2¹ + 1·2⁰
= 45
~~~

For hexadecimal:

~~~text
0x2D = 2·16 + 13 = 45
~~~

The numeral is notation. The mathematical integer is independent of the notation used to write it.

## Binary place values

For an n-bit vector b_(n-1)...b_0, the unsigned value is:

~~~text
U = Σ_(i=0)^(n-1) b_i 2^i
~~~

Bit i has weight 2^i.

| Bit | Weight |
|---:|---:|
| 7 | 128 |
| 6 | 64 |
| 5 | 32 |
| 4 | 16 |
| 3 | 8 |
| 2 | 4 |
| 1 | 2 |
| 0 | 1 |

The least significant bit has the smallest weight. The most significant bit has the largest positional weight in the fixed-width word.

## Powers of two and capacity

An n-bit vector has 2^n distinct patterns.

For unsigned interpretation:

~~~text
0 .. 2^n - 1
~~~

| Width | Patterns | Unsigned range |
|---:|---:|---:|
| 1 | 2 | 0..1 |
| 4 | 16 | 0..15 |
| 8 | 256 | 0..255 |
| 16 | 65,536 | 0..65,535 |
| 32 | 2^32 | 0..4,294,967,295 |
| 64 | 2^64 | 0..18,446,744,073,709,551,615 |

Width is part of the contract. The pattern 11111111 is 255 only under an 8-bit unsigned interpretation.

## Binary, hexadecimal and octal grouping

One hexadecimal digit corresponds to exactly four bits:

~~~text
0xA  = 1010₂
0x3F = 0011 1111₂
~~~

One octal digit corresponds to three bits:

~~~text
7₈ = 111₂
~~~

Hexadecimal aligns naturally with byte-oriented words because one byte is two hexadecimal digits.

## Decimal-to-base conversion

To convert a nonnegative integer to base b, repeatedly divide by b and collect remainders.

For 45 to binary:

~~~text
45 / 2 = 22 remainder 1
22 / 2 = 11 remainder 0
11 / 2 = 5  remainder 1
 5 / 2 = 2  remainder 1
 2 / 2 = 1  remainder 0
 1 / 2 = 0  remainder 1
~~~

Reading remainders upward gives 101101₂.

The algorithm requires O(log_b N) divisions for positive N.

## Horner evaluation

A numeral can be parsed without explicitly evaluating powers:

~~~text
value = 0
for digit in digits:
    value = value · base + digit
~~~

For k digits this requires O(k) arithmetic steps and O(1) auxiliary state.

Current ChrisASM parse_u64 follows this form for base 10 or 16 and checks for overflow before each multiply-add.

## Parsing overflow

With current value v, next digit d and maximum M, the new value would be:

~~~text
v_new = v·base + d
~~~

A safe precondition is:

~~~text
v <= (M - d) / base
~~~

ChrisASM uses this pattern with M = 18446744073709551615, which equals 2^64 - 1.

That is the parser's concrete contract, not a universal integer-parsing API.

## Fixed-width arithmetic as modular arithmetic

For an n-bit unsigned word:

~~~text
stored(a + b) = (a + b) mod 2^n
~~~

Example in eight bits:

~~~text
250 + 10 = 260
260 mod 256 = 4
~~~

The stored byte is 00000100.

The full mathematical result and the stored finite-width result are different objects.

## Carry

For unsigned addition:

~~~text
a + b = q·2^n + r
~~~

with 0 <= r < 2^n.

The stored result is r and q represents carry-out for two n-bit addends without another carry-in.

For 250 + 10:

~~~text
260 = 1·256 + 4
~~~

so the stored result is 4 and carry is 1.

## Subtraction and borrow

Finite-width subtraction also wraps modulo 2^n:

~~~text
stored(a - b) = (a - b) mod 2^n
~~~

Thus, in eight bits:

~~~text
0 - 1 mod 256 = 255
~~~

For unsigned interpretation, ordinary subtraction needs a borrow when a < b. Carry/borrow flag polarity is an ISA contract.

## Two's-complement signed interpretation

For an n-bit pattern with unsigned value U:

~~~text
signed(U) = U             if U < 2^(n-1)
signed(U) = U - 2^n       otherwise
~~~

The signed range is:

~~~text
-2^(n-1) .. 2^(n-1)-1
~~~

For eight bits:

~~~text
0x00 = 0
0x01 = 1
0x7F = 127
0x80 = -128
0xFF = -1
~~~

The bits do not change between signed and unsigned interpretations. The mapping changes.

## Negation in two's complement

For an n-bit word x:

~~~text
-x = (~x + 1) mod 2^n
~~~

Example:

~~~text
00000101 = 5
11111010 = bitwise complement
11111011 = -5 after adding 1
~~~

The minimum signed value has no positive counterpart at the same width. In eight bits, negating -128 cannot produce +128 as a representable signed 8-bit value.

## Signed overflow

Signed overflow differs from unsigned carry.

For addition, signed overflow occurs when both operands have the same sign and the stored result has the opposite sign.

Example:

~~~text
0x7F + 0x01 = 0x80
~~~

Unsigned 127 + 1 = 128 fits, so there is no unsigned carry. Signed 127 + 1 exceeds the signed 8-bit maximum, so signed overflow occurs.

## Carry and overflow are independent

| 8-bit operation | Result | Carry | Signed overflow |
|---|---:|---:|---:|
| 1 + 1 | 0x02 | 0 | 0 |
| 0xFF + 1 | 0x00 | 1 | 0 |
| 0x7F + 1 | 0x80 | 0 | 1 |
| 0x80 + 0x80 | 0x00 | 1 | 1 |

No single status bit answers both the unsigned and signed range questions.

## Sign extension

Sign extension preserves a signed value while increasing width.

~~~text
8-bit:
11111011 = -5

16-bit sign extension:
11111111 11111011 = -5
~~~

If the source sign bit is zero, new upper bits are zero. If the source sign bit is one, new upper bits are one.

## Zero extension

Zero extension preserves an unsigned value:

~~~text
8-bit:
11111011 = 251 unsigned

16-bit zero extension:
00000000 11111011 = 251
~~~

Zero-extending a negative signed pattern changes its signed numerical interpretation.

## Truncation

Reducing a bit-vector width keeps the low-order bits in ordinary modular reasoning:

~~~text
truncate_n(x) = x mod 2^n
~~~

Example:

~~~text
0x1234 truncated to 8 bits = 0x34
~~~

Truncation is safe only when loss of upper information is impossible or intended. Accidental narrowing of addresses, lengths or sizes is a correctness and security risk.


## Bitwise operations versus arithmetic

Bitwise operations act independently on bit positions:

~~~text
AND
OR
XOR
NOT
~~~

Arithmetic operations interpret the vector as a numerical word and propagate carries or borrows across positions.

For example:

~~~text
0011 + 0001 = 0100
0011 XOR 0001 = 0010
~~~

XOR is one-bit addition without carry, but multi-bit integer addition is not equivalent to XOR.

## Masks and fields

A mask selects or modifies bit fields.

To test bit k:

~~~text
value & (1 << k)
~~~

To set bit k:

~~~text
value | (1 << k)
~~~

To clear bit k:

~~~text
value & ~(1 << k)
~~~

To extract a field:

~~~text
field = (value >> shift) & mask
~~~

The operation is mechanical; semantic meaning comes from the field-layout contract.

## Left shift

For an unsigned n-bit word, left shift by k corresponds to multiplication by 2^k modulo the width when shifted-out bits are discarded:

~~~text
(x << k) mod 2^n
=
x · 2^k mod 2^n
~~~

Bits leaving the word are lost.

A language or ISA can impose additional rules for shift counts; those rules must be read from the actual execution contract.

## Logical right shift

Logical right shift inserts zeros at the high end.

For unsigned values:

~~~text
x >> k = floor(x / 2^k)
~~~

under the ordinary fixed-width interpretation.

## Arithmetic right shift

Arithmetic right shift of a negative two's-complement value replicates the sign bit under the usual x86 behavior.

~~~text
11110000 arithmetic >> 2
=
11111100
~~~

Logical and arithmetic right shifts are therefore different when the top bit is one.

## Rotations

A rotate moves shifted-out bits back into the opposite side.

~~~text
10000001 rotate-left 1
=
00000011
~~~

Rotation preserves bit population but is not ordinary multiplication or division.

## Fractional positional notation

Binary positional notation extends below the radix point.

~~~text
101.101₂
=
1·2² + 0·2¹ + 1·2⁰ + 1·2^-1 + 0·2^-2 + 1·2^-3
=
5.625
~~~

Not every decimal fraction has a finite binary representation. Decimal 0.1 repeats in binary, which is one source of representation error in floating-point computation.

## Fixed-point representation

A fixed-point word assigns an implicit scale.

If integer pattern I represents:

~~~text
value = I / 2^F
~~~

then F bits act as fractional precision.

Fixed-point arithmetic can reuse integer hardware, but the contract must define:

- scale;
- signedness;
- rounding;
- multiplication width;
- overflow behavior.

The current reviewed ChrisOS tree does not define one universal fixed-point ABI.

## Floating-point boundary

Floating-point represents sign, exponent and significand rather than a single fixed binary-point location.

It requires separate treatment of:

- normalized and subnormal numbers;
- infinities;
- NaNs;
- rounding;
- exceptions.

ChrisArchitectureState contains XMM byte storage, but that alone does not establish complete floating-point execution semantics in ChrisCPU.

## Endianness and significance are distinct

The 32-bit integer:

~~~text
0x12345678
~~~

has fixed numerical bit weights.

In little-endian memory its bytes appear at increasing addresses as:

~~~text
78 56 34 12
~~~

The numerical value remains 0x12345678 when loaded under the corresponding byte-order contract.

Endianness changes byte storage order; it does not redefine positional significance inside the abstract integer.

## ChrisArchitectureState and numerical width

Current ChrisOS main defines many architectural fields as uint64_t in ChrisArchitectureState.

The general-purpose register array is:

~~~text
uint64_t gpr[16]
~~~

and named fields such as rax, rcx and rip use 64-bit storage.

This does not mean every x86 operation is 64-bit. Instruction semantics select operand width, while the container remains wide enough to store architectural state.

Container width and active operand width are distinct contracts.

## ChrisCPU operand masks

The reviewed flags.c defines masks conceptually as:

~~~text
1 byte -> 0xFF
2 bytes -> 0xFFFF
4 bytes -> 0xFFFFFFFF
otherwise -> 0xFFFFFFFFFFFFFFFF
~~~

chris_flags_bin masks both operands before arithmetic.

For its expected operand-size values, the helper therefore models:

~~~text
8
16
32
64
~~~

bit arithmetic.

It is not an arbitrary-width integer library.

## ChrisCPU widened addition

For ADD and ADC, ChrisCPU uses an unsigned 128-bit host intermediate:

~~~text
wide = aa + bb + carry_in
~~~

It retains the low architectural-width bits and detects carry from the bits above the selected width.

This is a software technique for preserving the mathematical intermediate result long enough to derive a narrower architectural result and carry.

It does not mean an ordinary guest ADD architecturally produces a 128-bit destination.

## ChrisCPU signed-overflow predicates

For addition, current source computes a predicate equivalent to:

~~~text
((aa XOR r) AND (bb XOR r) AND sign_bit) != 0
~~~

For subtraction it uses:

~~~text
((aa XOR bb) AND (aa XOR r) AND sign_bit) != 0
~~~

These are Boolean expressions over finite-width two's-complement patterns.

They separate signed overflow from unsigned carry or borrow.

## Conditions and numerical interpretation

chris_cc_true uses different status combinations for unsigned and signed order.

Conceptually:

- CF participates in unsigned comparisons;
- SF and OF together participate in signed comparisons;
- ZF represents equality.

The same bits in a register can therefore be ordered differently depending on interpretation.

Signedness is not permanently attached to the stored pattern.

## ChrisASM numeric parsing

The reviewed parse_u64 accepts decimal text by default and hexadecimal text with 0x or 0X prefix.

It does not currently accept a 0b binary prefix in that function.

Each digit is accumulated by:

~~~text
v = v·base + d
~~~

after overflow checking.

This is a direct implementation of positional-numeral evaluation.

## ChrisASM little-endian emission

emit_u32 decomposes a value as:

~~~text
byte 0 = v & 0xFF
byte 1 = (v >> 8) & 0xFF
byte 2 = (v >> 16) & 0xFF
byte 3 = (v >> 24) & 0xFF
~~~

emit_u64 applies the same principle to eight bytes.

Thus:

~~~text
numerical interpretation
!=
byte-order encoding
~~~

A numerical value is first established, then serialized according to a byte-order contract.

## Graphics packing as positional arithmetic

gfx_rgb packs three byte-sized channels:

~~~text
(red << 16) | (green << 8) | blue
~~~

The fields occupy:

~~~text
bits 16..23  red
bits  8..15  green
bits  0..7   blue
~~~

Because they do not overlap, the same packed value can be expressed numerically as:

~~~text
red·2^16 + green·2^8 + blue
~~~

This is positional arithmetic applied to a software data layout.

## Initialization and control-flow boundary

Number systems have no runtime initialization.

The relevant software control flows are ordinary consumers of numerical contracts:

~~~text
assembly source text
    ↓
parse_u64
    ↓
uint64_t value
    ↓
emit_u32 / emit_u64
    ↓
encoded bytes
~~~

and:

~~~text
decoded operands
    ↓
chris_flags_bin
    ↓
width-masked result + status flags
    ↓
instruction execution state
~~~

The mathematics is stateless; the software paths using it are not.

## State and data structures

Relevant reviewed structures include:

- ChrisArchitectureState for architectural register/state storage;
- assembler static byte buffers and length counters;
- caller-owned result storage passed to chris_flags_bin;
- packed uint32_t color values produced by gfx_rgb.

The underlying integer interpretation remains a contract over bits.

No separate runtime object called a number system exists.

## Algorithms and complexity

The main algorithms in this chapter have explicit costs:

| Operation | Complexity |
|---|---:|
| parse k digits with Horner evaluation | O(k) |
| format positive integer N in base b | O(log_b N) digit extractions |
| fixed-width mask/shift on one machine word | O(1) at this abstraction |
| sign/zero extension of one native-width word | O(1) |
| arbitrary-precision arithmetic | outside this chapter |

ChrisASM parse_u64 uses O(k) time and O(1) auxiliary state for a bounded token.

## Memory ownership

Numerical values do not own memory; storage does.

In the reviewed code:

- ChrisArchitectureState is part of emulator CPU state;
- chris_flags_bin receives values and optionally writes through a caller-owned result pointer;
- parse_u64 writes to a caller-provided uint64_t;
- assembler emitters mutate assembler-owned static section buffers;
- gfx_rgb returns a value and allocates nothing.

The arithmetic rule and the ownership rule are separate.

## ABI and format boundary

Any stable ABI or persistent format must specify enough information to reconstruct the integer meaning:

- bit width;
- signedness;
- byte order;
- field position;
- scaling if fixed-point;
- reserved values;
- overflow or wrap expectations where relevant.

The phrase "integer field" is insufficient for a durable binary contract.

The data-representation chapter applies these rules to pointers, structures, object formats, filesystems and device layouts.

## Concurrency

Pure arithmetic on local values has no shared-state race.

A shared-memory update is a different problem.

~~~text
x = x + 1
~~~

is not automatically atomic because integer addition is mathematically well-defined.

The implementation performs a read, computes a value and writes a value unless an architectural atomic primitive or synchronization mechanism provides a stronger contract.

Therefore:

~~~text
arithmetic semantics
!=
memory atomicity
~~~

## Failure modes

| Error | Consequence |
|---|---|
| wrong width | truncation or wrong mask |
| wrong signedness | incorrect comparison/range |
| unchecked unsigned wrap | size/address error |
| incorrect sign extension | wrong negative value |
| incorrect zero extension | changed signed interpretation |
| bad shift count | language/ISA-specific fault or wrong result |
| wrong byte order | corrupted encoded value |
| parser overflow | invalid constant accepted or rejected incorrectly |
| mixed fixed-point scales | numerically plausible but wrong result |

The stored bits can look valid even when their interpretation is wrong.

## Security implications

Integer mistakes are a core systems-security boundary.

Common dangerous patterns include:

- allocation-size multiplication overflow;
- bounds-check truncation;
- signed/unsigned comparison mismatch;
- pointer narrowing;
- shift-derived mask errors;
- length addition wraparound.

Unsigned modular behavior can be deterministic and still be semantically unsafe.

Code controlling memory sizes or addresses should prove the range before relying on a finite-width result.

## Performance considerations

For native fixed-width integers, individual arithmetic operations are treated as constant-time at the algorithmic level used here, although actual instruction latency and throughput depend on the microarchitecture.

Base conversion is not constant in input length.

A k-digit parse is O(k), while formatting a positive integer N in base b takes O(log_b N) digit extraction steps.

Bit tricks should not replace clearer arithmetic merely because they appear lower level. Compiler output and measured performance are the relevant evidence for optimization.

## Current Intel architectural context

Intel's public Intel 64 and IA-32 Software Developer's Manual set was updated in September 2026 and the manual page lists version 093.

Volume 1 describes the basic architecture and programming environment; Volume 2 defines instruction semantics.

These manuals establish the architectural contracts for register widths, arithmetic, shifts and status flags on Intel 64/IA-32 processors.

ChrisCPU must be validated against the particular architectural semantics it intends to emulate rather than against generic intuition about binary arithmetic.

## Validation evidence for this chapter

The chapter-specific deterministic checker validates:

~~~text
101101₂ = 45
0x2D = 45

max unsigned n-bit value = 2^n - 1

(250 + 10) mod 256 = 4

signed_8(0xFF) = -1
signed_8(0x80) = -128

sign_extend_8_to_16(0xFB) = 0xFFFB
zero_extend_8_to_16(0xFB) = 0x00FB

unsigned left-shift modulo width

Horner parsing

RGB packing:
red·2^16 + green·2^8 + blue
~~~

The checker also verifies current source anchors in flags.c, chris_arch.h, chrisasm.c and graphics.c.

It does not claim complete x86 arithmetic conformance.

## Current limitations

This chapter intentionally does not attempt to fully cover:

- arbitrary-precision integer algorithms;
- IEEE 754 floating-point semantics;
- decimal floating-point;
- cryptographic multiprecision arithmetic;
- SIMD lane arithmetic;
- saturating arithmetic;
- the complete C integer-conversion model;
- every x86 arithmetic instruction.

Those belong to later or specialized treatments.

## Roadmap boundary

The curriculum transition is:

~~~text
logic levels
    ↓
Boolean algebra
    ↓
number systems and finite-width arithmetic
    ↓
data representation and layout
    ↓
combinational arithmetic circuits
    ↓
ISA-visible registers and machine code
~~~

The existing data-representation chapter depends on this chapter because width, signedness, masking and byte order require an explicit finite-bit numerical model.

## Revision provenance

Implementation-facing statements were reconciled against ChrisOS main revision da3df29cb397932c43d32373871fb9380e688ade.

Reviewed sources:

- chrisvm/cpu/emulator/flags.c;
- chrisvm/chris_arch.h;
- compiler/chrisasm/chrisasm.c;
- kernel/gfx/graphics.c.

Reviewed symbols:

- chris_flags_bin;
- chris_cc_true;
- ChrisArchitectureState;
- parse_u64;
- emit_u32;
- emit_u64;
- gfx_rgb.

The current Intel 64 and IA-32 Software Developer's Manual page was checked as the primary architectural reference; Intel lists the manual set as version 093 in September 2026. WG14 committee material was checked for contemporary C23 integer-representation context, but this chapter does not substitute committee discussion for a complete language-standard treatment.
