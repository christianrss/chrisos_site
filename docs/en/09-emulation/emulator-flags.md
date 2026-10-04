---
id: emulator-flags
lang: en
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chris_arch.h
  - chrisvm/cpu/common/state.c
  - chrisvm/cpu/emulator/flags.c
  - chrisvm/cpu/emulator/execute.c
  - chrisvm/tests/test_chrisvm.c
symbols:
  - chris_flags_bin
  - chris_cc_true
  - write_status
  - parity_even
  - do_alu
  - do_shift
  - do_unary
  - mul_flags
depends_on:
  - x86-decoding
  - x86-registers-flags
  - number-systems-binary-arithmetic
related:
  - emulator-exceptions
  - chrisvm-chriscpu
---

# Arithmetic flags and condition evaluation in ChrisCPU

## Why flags are part of instruction semantics

For an x86 interpreter, arithmetic is not complete when the numeric destination is correct. Status flags are architectural outputs consumed by conditional branches, SETcc, CMOVcc, ADC, SBB, exception-sensitive code and many compiler-generated idioms. A wrong Carry Flag can corrupt multiword arithmetic. A wrong Overflow Flag can reverse a signed comparison. Incorrect Zero or Sign Flags can send control flow down a different path even when the preceding register value is numerically correct.

ChrisCPU centralizes the status calculation for ordinary binary ALU operations in flags.c. The helper chris_flags_bin receives the ALU selector, two operands, operand size, incoming RFLAGS and an optional result pointer. It returns an updated flags word and, when requested, the masked arithmetic result. chris_cc_true then maps the five condition-code inputs used by Jcc, CMOVcc and SETcc into the sixteen x86 condition predicates.

This chapter describes the implementation at ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56 and separates verified helper behavior from instruction-family behavior that is implemented elsewhere in execute.c.

## The modeled status subset

The ordinary ALU helper updates six status bits:

| Flag | Bit | Meaning in the helper |
|---|---:|---|
| CF | 0 | carry out for addition or borrow for subtraction |
| PF | 2 | even parity of the low result byte |
| AF | 4 | carry/borrow across bit 3 to bit 4 |
| ZF | 6 | masked result equals zero |
| SF | 7 | sign bit of the masked result |
| OF | 11 | signed overflow |

write_status first clears those six bits, computes their new values, preserves other bits from the incoming flags word, and forces bit 1 to one. The reset path in chris_arch_reset also initializes RFLAGS to two, matching the project invariant that the architecturally fixed bit remains set.

The helper does not rebuild RFLAGS from scratch. Preserving unrelated bits matters because arithmetic should not silently erase IF, DF or other modeled state.

## Width as part of the arithmetic domain

chris_flags_bin supports operand sizes of one, two, four and eight bytes. size_mask restricts operands and results to 8, 16, 32 or 64 bits. sign_bit selects the most significant bit of that width.

For width w, the unsigned arithmetic domain is modulo 2^w. A host 64-bit addition alone cannot expose the carry out of a 64-bit guest operation, so ADD and ADC use unsigned __int128 for the intermediate sum. The helper then masks the low w bits into the guest result and tests whether any bit remains above the guest width.

This is an important implementation boundary: host integer width is an implementation detail, while guest width defines the architecture. Every flag formula must use the guest width.

## Addition and ADC

For ADD, the wide intermediate is:

    wide = a + b

For ADC:

    wide = a + b + CF_in

Operands are masked before the operation. The result is the low w bits.

Carry is set when the wide unsigned value exceeds the guest-width range. For a 64-bit operation this is detected through the upper part of the 128-bit host intermediate.

Signed overflow is computed with the standard bitwise identity:

    OF = ((a XOR result) AND (b XOR result) AND sign_bit) != 0

For addition, overflow occurs when operands have the same sign and the result has a different sign. The expression encodes exactly that condition without converting the operands to a host signed type of the same width.

Auxiliary carry is:

    AF = ((a XOR b XOR result) AND 0x10) != 0

This captures the carry across the low nibble boundary.

ADC differs from ADD not only in the numeric result but also in all flags that depend on the incoming carry. The helper reads CF from the incoming flags word before the new status bits are written.

## Subtraction, CMP and SBB

SUB and CMP share the same arithmetic. CMP suppresses the destination write in execute.c but still produces the same flags as subtraction.

For SUB:

    result = a - b

For SBB:

    result = a - b - CF_in

The result is masked to the guest width.

x86 CF after subtraction represents unsigned borrow. Without incoming carry:

    CF = a < b

With SBB and incoming carry equal to one, the source side is effectively b + 1, so the implementation uses:

    CF = (a < b) OR (a == b)

which is equivalent to a <= b for the masked operands.

Signed overflow is:

    OF = ((a XOR b) AND (a XOR result) AND sign_bit) != 0

This detects subtraction where source and destination signs differ and the result sign is inconsistent with the mathematical signed result.

AF again uses the low-nibble XOR relation.

## Logical operations and TEST

AND, OR, XOR and TEST share the logic path. TEST suppresses the result write but updates status as an AND.

For these operations ChrisCPU:

- computes result normally;
- clears CF;
- clears OF;
- derives PF, ZF and SF from the result;
- writes AF as zero.

The last point is a project-specific deterministic choice. In x86, AF is undefined after these logical operations. Therefore a guest observing AF after AND, OR, XOR or TEST is outside a portable architectural contract. Documentation and tests should not elevate ChrisCPU's zero value into a general x86 guarantee.

## Parity

parity_even considers only the low result byte, as required by x86 PF semantics. It folds the byte through XOR shifts until one parity bit remains and returns true for an even count of set bits.

PF is therefore independent of operand width above the low byte. A 64-bit result and an 8-bit result with the same low byte have the same PF.

## Zero and sign

ZF is set when the result, after width masking, equals zero. SF is copied from the sign bit selected by the operand size.

Masking before those tests is essential. For example, an 8-bit operation whose host intermediate contains 0x100 has an architectural result of zero. ZF must reflect the 8-bit result, not the wider host intermediate.

## Condition-code evaluation

chris_cc_true uses CF, PF, ZF, SF and OF to implement the sixteen x86 condition selectors. The decoder stores the low four bits of the condition code for short Jcc, near Jcc, CMOVcc and SETcc.

| cc | Predicate | Common interpretation |
|---:|---|---|
| 0 | OF | overflow |
| 1 | not OF | no overflow |
| 2 | CF | below/carry |
| 3 | not CF | above-or-equal/no carry |
| 4 | ZF | equal/zero |
| 5 | not ZF | not equal/nonzero |
| 6 | CF or ZF | below-or-equal |
| 7 | not CF and not ZF | above |
| 8 | SF | sign |
| 9 | not SF | not sign |
| 10 | PF | parity |
| 11 | not PF | not parity |
| 12 | SF != OF | less, signed |
| 13 | SF == OF | greater-or-equal, signed |
| 14 | ZF or SF != OF | less-or-equal, signed |
| 15 | not ZF and SF == OF | greater, signed |

Unsigned comparisons depend on CF and ZF. Signed comparisons depend on the relationship between SF and OF, with ZF distinguishing equality. This is why overflow correctness is not an isolated arithmetic detail: it directly controls signed branches.

The helper masks cc with fifteen, so selector values that differ by sixteen evaluate identically. The host verification probe explicitly checks this aliasing.

## CMP, TEST, Jcc, CMOVcc and SETcc data flow

The decoder classifies CMP and TEST as ALU operations but execute.c sets write to false for those selectors. do_alu still reads both operands and calls chris_flags_bin, so the status result is architecturally visible while the destination remains unchanged.

Jcc calls chris_cc_true and updates RIP only when the predicate is true. CMOVcc and SETcc use the same predicate helper. This gives one condition truth table to all three instruction families rather than duplicating signed/unsigned comparison logic.

That centralization is valuable because a mismatch between Jcc and SETcc for the same flags state would be a serious semantic inconsistency.

## NEG, INC, DEC and NOT

Unary operations are implemented in execute.c using the binary flag helper where possible.

NEG computes zero minus the operand through CHRIS_ALU_SUB. This naturally produces the subtraction flag definitions. In particular, CF becomes set for every nonzero operand and clear for zero.

INC computes value plus one through the ADD helper, but x86 INC must preserve the incoming CF. The implementation saves CF, updates the other arithmetic flags, then restores the old CF.

DEC follows the same pattern with subtraction by one and restores CF afterward.

NOT simply inverts the operand and writes it back without changing flags.

These wrappers demonstrate an important emulator design principle: a reusable arithmetic primitive is useful only when instruction-specific exceptions to its flag behavior are re-applied explicitly.

## Multiplication flags

mul_flags handles the flags that ChrisCPU models for MUL and IMUL. It clears CF and OF, then sets both when the product does not fit in the narrow result criterion used by the instruction form.

For unsigned MUL, wide means that the upper half of the product is nonzero.

For signed IMUL, wide means that truncating the product to the operand width and sign-extending it back does not reproduce the full product.

Only CF and OF are modified by mul_flags. Other status flags retain their previous ChrisCPU values. Architecturally, several of those flags are undefined for MUL/IMUL. Their retained values are therefore deterministic implementation residue, not behavior software should rely on.

DIV and IDIV do not update status flags in the current executor. Their x86 status flags are undefined as well, so unchanged bits again must not be interpreted as a portable promise.

## Shift and rotate flag handling

do_shift implements ROL, ROR, SHL, SHR and SAR by iterating one bit at a time for the effective count. The count is masked to six bits for 64-bit operands and five bits for other widths. A masked count of zero leaves both destination and flags unchanged.

Each iteration records the bit shifted or rotated out as CF. For left shifts and rotates, the high bit leaves the operand; for right operations, bit zero leaves it.

After the loop, the current implementation uses the logical-AND flag helper to recompute PF, AF, ZF and SF from the final value, then restores the computed CF and conditionally OF.

This is a compact implementation, but the exact behavior must not be overstated. It contains compatibility gaps.

### Rotate status preservation gap

Architecturally, ROL and ROR affect CF and, for an effective count of one, OF. ZF, SF, PF and AF are not supposed to be recomputed by a rotate.

The current implementation does recompute those status bits because it calls chris_flags_bin on the rotated result before restoring CF and OF. A guest that depends on preexisting ZF, SF or PF surviving ROL/ROR can therefore observe different behavior from x86 hardware.

### Rotate count reduction gap

For 8- and 16-bit ROL/ROR, x86 applies count masking and then reduces the rotate count modulo the operand width. A full-width rotation can have an effective count of zero and must preserve flags.

ChrisCPU masks the count but then executes that many single-bit rotations without a second modulo-width reduction. The final numeric value can coincide after a whole-width rotation, but flags may still change. This is another observable compatibility gap.

### SHR overflow gap

For SHR with effective count one, x86 OF receives the original most significant bit. ChrisCPU currently computes the SHR OF test from the value after shifting. For a value whose original sign bit was one, that can lose the information required for the architectural OF result.

### ROR overflow gap

For ROR with effective count one, x86 OF is the XOR of the two most significant bits of the result. The current branch in do_shift does not calculate that formula and leaves OF clear.

### Undefined shift flags

For shift counts greater than one, OF is architecturally undefined. ChrisCPU clears it through the status rewrite and only sets it for selected count-one cases. AF after shifts is also undefined and is deterministically cleared through the logical-helper path. Those values are acceptable as internal deterministic choices but should not be used as conformance evidence.

## Direct flag-control instructions

The CHRIS_OP_FLAG execution path directly edits individual RFLAGS bits:

- CLC clears CF;
- STC sets CF;
- CLD clears DF;
- STD sets DF;
- CLI clears IF;
- STI sets IF and sets sti_delay.

sti_delay participates in interrupt delivery so that an external interrupt is not delivered immediately in the same execution point as STI. This is a separate control-flow contract from arithmetic flags, but it shares the same RFLAGS state.

Privilege checks for sensitive flag-control instructions are broader architectural concerns. Recognition and bit mutation alone do not establish complete CPL/IOPL behavior.

## PUSHF, POPF and IRETQ

PUSHF pushes a masked subset of the modeled RFLAGS. POPF accepts the 64-bit form in the current executor, masks the restored value, and forces bit one. IRETQ similarly restores a masked flags value while restoring control state.

The mask prevents arbitrary high host bits from becoming modeled flag state. However, the current implementation is not a claim of complete x86 privilege-sensitive POPF/IRET semantics. Those instructions interact with CPL, IOPL and other architectural restrictions that must be evaluated with exception and privilege handling.

## Reproducible arithmetic evidence

The documentation repository contains scripts/check_arithmetic.py. It compiles the actual ChrisCPU flags.c into a temporary host shared library and compares chris_flags_bin against an independent Python integer-range model.

The probe executes 752,270 arithmetic cases. Its exhaustive 8-bit phase covers every pair of byte operands for all nine modeled ALU selectors, including both incoming-carry states for ADC and SBB. For 16-, 32- and 64-bit widths it adds boundary values and deterministic random cases.

The reference model independently computes unsigned range overflow, signed range overflow, auxiliary carry/borrow, low-byte parity, zero and sign.

The same probe tests 1,024 condition-code cases: every combination of CF, PF, ZF, SF and OF, all sixteen condition selectors, and the selector aliases offset by sixteen. It also verifies nine calls where the result pointer is null, ensuring status calculation does not depend on result storage.

This is strong evidence for chris_flags_bin and chris_cc_true at the checked source revision. It is not evidence for the decoder, shift/rotate wrapper, multiplication wrapper, guest exception entry, full instruction retirement, timing or physical hardware.

## Existing integration evidence

chrisvm/tests/test_chrisvm.c includes explicit arithmetic boundaries. One test adds one to all-one 64-bit data and checks result zero, CF set, ZF set, SF clear, OF clear, PF set and AF set. Another adds one to the maximum signed 64-bit value and checks signed overflow without unsigned carry.

Instruction-level tests also execute ADD and inspect CF/ZF through the machine state. Multiplication tests check the product and CF for a wide result.

These tests connect helper logic to selected decoded/executed instructions, but they are intentionally narrower than the arithmetic probe.

## Current limitations and next hardening work

The central ADD/ADC/SUB/SBB/CMP/AND/OR/XOR/TEST helper has unusually broad reproducible coverage for this project, but flag correctness across the full emulator is not complete.

Priority work is:

1. correct ROL/ROR preservation of ZF, SF, PF and AF;
2. apply architectural modulo-width count reduction for rotates;
3. correct SHR count-one OF from the original sign bit;
4. implement ROR count-one OF from the top two result bits;
5. add dedicated shift/rotate contract probes across widths and counts;
6. test NEG, INC and DEC flag behavior exhaustively at 8 bits and by boundaries at larger widths;
7. add explicit tests for MUL/IMUL CF/OF fit rules for all operand sizes;
8. distinguish architecturally undefined flags from project-deterministic values in tests;
9. expand privilege-aware PUSHF/POPF/IRETQ and CLI/STI validation;
10. keep condition-code tests tied to the same source revision as flag computation.

## Revision note

At revision e05a17fd76333114a3fb5c2452f38ca747d4ac56, ChrisCPU has a source-verified binary ALU flag helper and a complete sixteen-condition predicate table for the modeled status bits. The independent host probe gives deep evidence for those helpers. Shift and rotate handling remains a separate, materially less complete compatibility boundary and must not inherit the helper's conformance confidence by association.
