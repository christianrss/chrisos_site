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
