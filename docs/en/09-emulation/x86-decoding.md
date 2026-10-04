---
id: x86-decoding
lang: en
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chris_arch.h
  - chrisvm/cpu/common/state.c
  - chrisvm/cpu/emulator/decode.c
  - chrisvm/cpu/emulator/operands.c
  - chrisvm/cpu/emulator/chriscpu.c
  - chrisvm/cpu/emulator/execute.c
  - chrisvm/tests/test_chrisvm.c
  - chrisvm/Makefile
symbols:
  - ChrisInsn
  - chris_decode
  - read_modrm
  - imm_n
  - chris_format_insn
  - chris_imm_sx
  - chris_eff_addr
  - chris_read_gpr
  - chris_write_gpr
  - fetch_insn
depends_on:
  - emulator-theory
  - x86-instruction-encoding
  - x86-registers-flags
related:
  - emulator-flags
  - emulator-exceptions
  - chrisvm-chriscpu
---

# x86-64 instruction decoding in ChrisCPU

## Scope and evidence boundary

Instruction decoding is the boundary between a byte stream and an executable architectural intention. In ChrisCPU, the decoder does not execute instructions and does not directly read guest memory. It receives a byte buffer, classifies prefixes and opcode forms, parses ModR/M and SIB when required, extracts displacements and immediates, and writes a compact decoded record into ChrisInsn. The executor consumes that record later.

This separation matters for validation. A decoder can recognize the correct mnemonic while still producing an incorrect operand width, register extension, displacement, immediate, addressing mode, or instruction length. Execution can also be wrong even when parsing is correct. The current implementation therefore has to be treated as a parser plus an operand-description layer, not merely as a function that emits recognizable assembly text.

The implementation inspected here is ChrisOS main revision e05a17fd76333114a3fb5c2452f38ca747d4ac56. It is a deliberately bounded x86-64 subset for ChrisVM. It is not a complete Intel or AMD decoder and does not claim coverage of the full ISA.

## Runtime fetch contract

The interpreter helper fetch_insn reads exactly fifteen guest bytes before chris_decode is called. Fifteen bytes is the architectural maximum length of an x86 instruction. Each byte is obtained with chris_va_read using the execute-access class, beginning at the current RIP.

That design gives the decoder a fixed complete window, but fetch is eager rather than demand-driven. A short instruction located at the end of a mapped page may cause the interpreter to read from the following page even though the actual instruction does not need those bytes. If the next page is unmapped, protected, or side-effectful through the machine map, the extra access can affect behavior before decoding determines the true length. An incremental or page-aware fetch interface would avoid this class of unnecessary access, but would need an explicit incomplete-input protocol for prefixes, ModR/M, SIB, displacement and immediates.

The decoder itself accepts any positive available-byte count. It returns minus one when a required structural byte is absent. For a complete encoding that is unknown or classified as invalid in the implemented subset, the normal result is a positive length with the operation classified as CHRIS_OP_UD. That distinction allows truncation and invalid-opcode behavior to remain separate.

## ChrisInsn as the decoded intermediate representation

ChrisInsn is the intermediate record shared by decode and execute. It preserves semantic fields rather than merely copying the original bytes.

| Class | Representative fields | Meaning |
|---|---|---|
| operation | op, alu, shift_kind, unary, muldiv, flag_op, desc_op | semantic family selected by opcode or group |
| widths | os, asz, src_os | operand, address and extension-source sizes |
| prefixes | rex, rex_w/r/x/b, lock, rep | effective prefix state |
| ModR/M | mod, reg, rm, rm_field, digit, has_modrm | register/memory selection and opcode-group digit |
| SIB | scale, index, base, no_index, no_base, has_sib | indexed-address components |
| displacement | disp, has_disp, rip_rel | signed displacement and RIP-relative classification |
| immediate | imm, imm_bytes | raw immediate bits plus encoded width |
| control | cc, vector, form, cr_to_reg | condition, interrupt and operand-form metadata |
| length | len | bytes consumed by the instruction |

The representation deliberately distinguishes reg from digit. The ModR/M reg field is extended by REX.R when it names a register, while digit retains the original three bits for grouped opcodes. This prevents a REX extension from changing a group selector such as /0 into an unrelated operation.

The structure is small and stack-friendly. chris_decode clears a local instance, fills fields procedurally, assigns len, and copies it to the caller. No heap allocation is performed during decoding.

## Prefix scanning

is_prefix recognizes operand-size override 66, address-size override 67, LOCK F0, F2 and F3 repetition prefixes, legacy segment overrides 26/2E/36/3E/64/65, and REX bytes 40 through 4F.

The prefix loop consumes bytes only while the index remains below fourteen, preserving room for at least one opcode byte inside the fifteen-byte maximum.

The default operand size is 32 bits and the default address size is 64 bits. REX.W selects a 64-bit operand. The 66 prefix selects 16 bits when an effective REX.W is not present. The 67 prefix selects 32-bit addressing.

A notable detail is how REX is retained. If a legacy prefix appears after a REX byte, the stored REX state is cleared. A later REX can become effective again. This matches the long-mode requirement that the effective REX occupy the appropriate final prefix position rather than being treated as a freely commutative legacy prefix.

LOCK and REP state is preserved. Segment-override bytes are consumed, but their identity is not retained in ChrisInsn. That is a material limitation: accepting 64 or 65 does not mean general FS- or GS-relative addressing is implemented, because the execution layer cannot reconstruct which segment override was present.

## Operand and address sizes

After prefix processing, the normal operand width is selected as follows:

    effective REX.W -> 8 bytes
    otherwise 66   -> 2 bytes
    otherwise      -> 4 bytes

Address width is:

    67 present -> 4 bytes
    otherwise  -> 8 bytes

Instruction families can override those defaults. Byte operations use os equal to one. PUSH and POP default to an eight-byte stack operand and use two bytes with 66. Control-register transfers force an eight-byte operand. MOVSX and MOVZX use src_os to distinguish the source width from the destination width.

This width information is architecturally important. chris_write_gpr preserves unaffected bits for 8- and 16-bit writes, clears the upper 32 bits after a 32-bit general-register write, and replaces the whole register for a 64-bit write. A decoder that misclassifies os therefore changes guest-visible register semantics even when the opcode name is correct.

## High-byte registers and REX

Eight-bit register encoding has a special split in long mode. Without REX, register codes four through seven can denote AH, CH, DH and BH. With any effective REX prefix, the same numeric codes denote SPL, BPL, SIL and DIL.

ChrisInsn retains enough state for operands.c to implement this distinction. high8 selects the legacy high-byte aliases only when operand size is one, no REX is present, and the register code is in the range four through seven.

This also explains why a REX prefix whose W/R/X/B extension bits are all zero cannot simply be discarded. Prefix 40 still changes the interpretation of byte-register encodings.

## One-byte and two-byte opcode maps

The parser implements the primary one-byte map and a subset of the two-byte 0F map. Encountering 0F causes a second opcode byte to be consumed and switches to the two-byte dispatch path.

There is no parser for 0F 38, 0F 3A, VEX, XOP, or EVEX maps. General vector/SIMD decoding is therefore outside the current implementation.

Implemented families include:

| Family | Representative forms handled |
|---|---|
| integer ALU | ADD, OR, ADC, SBB, AND, SUB, XOR, CMP rows; groups 80-83; TEST |
| movement | MOV register/memory/immediate, MOVZX, MOVSX, LEA, XCHG |
| stack | PUSH, POP, PUSHF, POPF, LEAVE |
| control flow | short and near Jcc, JMP, CALL, RET |
| shifts/rotates | ROL, ROR, SHL, SHR, SAR through C0/C1/D0-D3 |
| unary/mul/div | NOT, NEG, INC, DEC, MUL, IMUL, DIV, IDIV and two-operand IMUL |
| port I/O | IN and OUT |
| interrupts | INT3, INT imm8, IRETQ |
| control/system | MOV CR, CPUID, RDMSR, WRMSR, SGDT/SIDT/LGDT/LIDT subset |
| conditional data | CMOVcc and SETcc |
| strings | STOS with REP state |
| flags | CLC, STC, CLI, STI, CLD, STD |
| miscellaneous | NOP and HLT |

Decoder recognition is not evidence that every prefix combination, privilege rule, exception condition, atomicity rule, or operand variation is implemented correctly. Those properties cross into execute.c and exception delivery.

## ModR/M parsing

read_modrm splits ModR/M into the architectural fields:

    bits 7..6 -> mod
    bits 5..3 -> reg or group digit
    bits 2..0 -> r/m

reg is extended with REX.R and rm with REX.B. The unextended middle field is separately retained as digit for opcode groups.

mod equal to three selects a register operand. Memory forms can consume a displacement:

- mod equal to one uses a signed 8-bit displacement;
- mod equal to two uses a signed 32-bit displacement;
- selected mod equal to zero encodings use a signed 32-bit displacement.

The decoder stores displacement in a signed 64-bit field. Eight- and thirty-two-bit displacement reads are sign-extended as they enter that field.

## RIP-relative addressing

With 64-bit address size, ModR/M mod 00 with r/m 101 is classified as RIP-relative. The decoder marks rip_rel and consumes a signed 32-bit displacement.

chris_eff_addr later calculates:

    effective address = current RIP + decoded length + displacement

The decoded length is essential because RIP-relative addressing is based on the address of the next instruction, not the first byte of the current instruction.

## SIB addressing

A memory operand with r/m field four consumes a SIB byte. The fields are scale in bits 7..6, index in bits 5..3, and base in bits 2..0. REX.X extends the index and REX.B extends the base.

The effective-address helper later combines:

    base + (index << scale) + displacement

subject to no_index, no_base and address-size handling.

Index field four without REX.X is classified as no index. Base field five with mod 00 is classified as no base in the SIB form. These flags prevent the executor from reading a general-purpose register when the encoding denotes an omitted component.

## A concrete address-size override limitation

The decoder records 32-bit address mode and chris_eff_addr masks the final effective address to thirty-two bits. This does not mean that every 32-bit ModR/M special case is implemented.

In particular, the non-SIB form mod 00, r/m 101 becomes RIP-relative only when address size is 64 bits. Under 32-bit addressing the architectural form is disp32 with no base. The current parser does not mark that no-base case explicitly, so the downstream effective-address path can include the register selected by rm instead of treating the encoding as displacement-only.

The current documentation probe verifies a simple 67 8B 00 address override, but it does not cover this non-SIB r/m-five special case. The correct compatibility claim is therefore partial 32-bit effective-address support, not complete address-size-override support.

## Immediate representation and sign extension

imm_n reads one, two, four or eight bytes into a raw 64-bit field and records the encoded byte width separately.

Sign extension is intentionally delayed. chris_imm_sx interprets the raw value according to imm_bytes. Relative branches, immediate PUSH forms and ALU forms use that helper when a narrower encoded immediate represents a wider signed value.

This matters for 64-bit forms whose encoding contains an imm32 that is sign-extended to the operation width. Keeping raw bits and encoded width separate avoids losing the distinction during parsing.

## Truncation, UD and UNIMPL

Structural truncation and architectural invalidity are distinct outcomes. If a required second opcode, ModR/M, SIB, displacement, or immediate is missing, the decoder returns minus one.

If the byte sequence is complete but unsupported or classified as invalid, the decoder can return a positive length with CHRIS_OP_UD. The documentation contract probe verifies 0F 0B as an explicit two-byte UD classification.

Some recognized but not implemented group members become CHRIS_OP_UNIMPL instead. This exposes a project-level distinction between an invalid encoding and an encoding the project recognizes but does not execute yet. That policy should remain consistent as coverage expands, because the guest-visible exception path depends on how execution treats each classification.

The final guard prevents an instruction from reporting a length above fifteen bytes.

## Decode-time versus execute-time legality

The decoder is not a complete architectural legality checker. Some restrictions are enforced later.

LOCK is a useful example. Decode records the prefix generically. execute.c applies lock_ok to selected ALU operations and rejects LOCK when the selected operand is a register or no ModR/M exists. Other instruction families do not all perform an equivalent legality check, and the current implementation does not establish general locked-memory atomicity.

Likewise, privileged instructions such as CLI, STI, MOV CR, RDMSR and WRMSR require execution-time privilege and state checks. Parsing their shape is not proof that they can legally execute at the current CPL.

## Formatting is diagnostic, not canonical disassembly

chris_format_insn emits compact text for tracing. It has dedicated formatting for ALU operations, Jcc, several MOV forms and STOS, and falls back to chris_op_name for other operations.

It is not a complete disassembler. It does not preserve or display every prefix, segment choice, address expression, or immediate interpretation. Trace text is useful for debugging but should not be treated as a lossless reconstruction of the original encoding.

## Complexity and memory behavior

chris_decode operates on at most fifteen relevant bytes. Prefix scanning, ModR/M, SIB, displacement and immediate parsing are bounded by that fixed maximum. Runtime is O(L) in instruction length with L no greater than fifteen, therefore constant with respect to guest-program size.

The decoder performs no heap allocation. Fixed-width reads use memcpy rather than potentially unaligned typed dereferences.

The larger interpreter cost occurs before parsing: eager fetch can perform fifteen guest virtual reads for every instruction, and each guest read can involve address translation. Decoder micro-optimization alone therefore does not remove the dominant boundary cost in some workloads.

## Validation evidence

The documentation repository includes scripts/check_instruction_contracts.py. That host probe compiles the actual state helper, decoder and operand helper from the checked-out ChrisOS source rather than reproducing the logic in Python.

It verifies:

- 20 literal instruction fixtures;
- 69 truncation cases;
- 80 register width and alias cases;
- two invalid register indices;
- four effective-address cases;
- one explicit UD classification.

The fixtures cover 16-, 32- and 64-bit operands, short and near branches, SIB, RIP-relative addressing, a basic address-size override, REX-extended registers, high-byte versus REX byte aliases, no-base/no-index SIB, NOP and HLT.

chrisvm/tests/test_chrisvm.c also performs 2,000 deterministic pseudo-random decoder calls. That loop verifies a safety property: return is either minus one or a positive length from one through fifteen, and insn.len matches the returned length. It does not independently prove that randomly decoded instructions have the correct x86 semantic meaning.

Integration tests execute literal byte streams that exercise ALU, MOV, calls, memory access, port I/O, exceptions, CPUID/MSR, multiplication/division, STOS and control flow. Those tests validate decode together with execution, memory and exception machinery.

## Current limitations

At the inspected revision, the decoder should be treated as a useful project-specific x86-64 subset with explicit compatibility boundaries:

- no VEX, EVEX, XOP, or general vector maps;
- no x87 decoding;
- no broad SSE/AVX instruction families;
- no three-byte opcode maps;
- only a small string-instruction subset;
- segment-override identity is discarded;
- no general FS/GS-relative addressing representation;
- incomplete 32-bit address-size special cases;
- incomplete LOCK legality and memory-atomicity modeling;
- prefix-combination legality is not exhaustively validated;
- many system and privileged instructions are absent;
- the formatter is not a full disassembler;
- random testing checks bounds, not ISA semantics;
- runtime fetch eagerly reads fifteen bytes and can cross a page unnecessarily.

These limits are compatibility boundaries, not documentation defects. They define concrete work required before ChrisCPU can claim broader binary compatibility.

## Hardening and expansion priorities

The highest-value next steps are:

1. add exact tests for every ModR/M and SIB special case under both 64- and 32-bit address sizes;
2. retain and execute FS/GS override semantics;
3. make fetch demand-driven or page-aware so short instructions do not require fifteen readable bytes;
4. separate opcode tables from procedural decoding as coverage grows;
5. add systematic legality validation for LOCK, REP and prefix combinations;
6. expand independent fixtures for every implemented opcode family and group digit;
7. add mutation/fuzz testing that compares decoding against a trusted external reference for the supported subset;
8. characterize UD versus UNIMPL policy consistently;
9. generate an explicit supported-ISA table from decoder tests rather than roadmap intent;
10. keep decode and execute coverage synchronized so every accepted form has defined guest-visible behavior.

## Revision note

This chapter documents ChrisCPU's decoder at ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56. At that revision the parser has a bounded fifteen-byte design, an explicit ChrisInsn representation, REX/ModR/M/SIB handling, integer/control/system subsets and host-side contract tests. It remains intentionally incomplete relative to the full x86-64 architecture.
