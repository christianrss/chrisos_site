---
id: x86-instruction-encoding
lang: en
type: technical-chapter
volume: 02-computer-architecture
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - chrisvm/chris_arch.h
  - chrisvm/cpu/emulator/decode.c
  - chrisvm/cpu/emulator/operands.c
  - chrisvm/cpu/emulator/chriscpu.c
symbols:
  - ChrisInsn
  - chris_decode
  - read_modrm
  - imm_n
  - chris_format_insn
  - chris_eff_addr
  - chris_imm_sx
  - fetch_insn
depends_on:
  - machine-code
  - x86-registers-flags
related:
  - x86-64-memory-privilege
  - emulator-theory
---

# x86 instruction encoding and bounded decoding

## A grammar whose fields depend on earlier fields

An x86 decoder cannot split the input into fixed-size words and interpret each word independently. Prefixes influence width and register selection; the opcode determines whether an addressing byte or immediate is needed; addressing bits determine whether another byte or displacement follows. The instruction therefore has a conditional grammar. This chapter follows the legacy and REX forms implemented in the declared decoder. VEX, EVEX and the complete instruction-set extension space are outside this implementation-facing account.

The architectural maximum of fifteen bytes bounds one instruction. It does not authorize reading fifteen bytes from every starting address before determining the actual length. Input-buffer safety, instruction-length validity and guest-memory accessibility are three separate obligations. A decoder operating on already available bytes can check bounds correctly while its caller still fetches guest bytes too eagerly. `fetch_insn` currently performs that eager fetch; the datapath chapter documents the page-boundary consequence.

![Conditional instruction grammar](../../assets/diagrams/x86-decode-grammar.svg)

`ChrisInsn` normalizes the encoded input into operation, length, operand size, address size, prefix state, addressing fields, displacement and immediate information. Execution consumes that record rather than reinterpreting the byte stream. Normalization reduces duplicated parsing, but only if each field has an explicit invariant: a register-only operand must not accidentally trigger an effective-address calculation, and an absent base must not be confused with register zero.

## Prefix state and width selection

`chris_decode` starts with operand size four and address size eight, measured in bytes. It scans recognized prefixes while input remains and fewer than fourteen prefix bytes have been consumed. An operand-size override records a 16-bit preference; an address-size override records 32-bit addressing. A final REX.W selects 64-bit operands in the generic width calculation. Individual opcode families can then override this default, as PUSH and POP do for their usual 64-bit stack operands.

| Prefix | Decoder state | Important distinction |
|---|---|---|
| `66` | 16-bit operand preference | Does not change address size |
| `67` | 32-bit addressing | Does not by itself select 32-bit data |
| `f0` | `lock` set | Parsing does not prove legal atomic execution |
| `f2`, `f3` | Repeat selector | Meaning depends on the instruction family |
| Segment overrides | Consumed | Selected segment is not retained in `ChrisInsn` |
| `40` through `4f` | REX byte | Presence affects byte-register aliases |

In this parser, a later legacy prefix clears the stored REX byte, and a later REX replaces the preceding one. These are observed parser rules, not a declaration that every prefix permutation is architecturally legal for every opcode. Execution still needs operation-specific validation. A recognized LOCK prefix cannot turn an arbitrary register operation into a valid atomic memory instruction.

A REX byte has high nibble `0100` and low bits W, R, X and B. W requests width where applicable; R extends the ModR/M register field; X extends the SIB index; B extends an r/m, base or opcode-embedded register field according to the form. For `4d`, W, R and B are one and X is zero. Treating all four bits as a single register number would lose their distinct roles.

## ModR/M and opcode extensions

For a ModR/M byte m, the decoder extracts `mod = m >> 6`, `digit = (m >> 3) & 7` and `rm_field = m & 7`. The extended register number is `digit | (REX.R ? 8 : 0)`, while extended r/m uses REX.B. The unextended `digit` is retained because some opcode groups use those three bits to select an operation instead of a register. Extending a group selector as though it were a register would select the wrong instruction.

| mod bits | General interpretation | Additional displacement |
|---|---|---|
| `00` | Memory addressing | None except special forms |
| `01` | Memory addressing | Signed byte |
| `10` | Memory addressing | Signed 32-bit displacement |
| `11` | Register operand | None |

For `48 01 d8`, ModR/M `d8` is binary `11011000`: mod is three, reg is three and r/m is zero. The opcode's direction gives destination RAX and source RBX. REX.W supplies eight-byte operand size. No SIB, displacement or immediate follows, so length is three. This decomposition connects the encoded fields to the ADD path examined in the datapath chapter.

The table is a structural guide, not a complete list of legal addressing forms. Special low-field values introduce SIB or relative addressing. Mode also matters: the decoder is organized around its chosen 64-bit execution model and should not be presented as a general 16/32/64-bit decoder merely because it supports operand and address overrides.

## SIB and a worked effective address

With a memory operand and low r/m field four, `read_modrm` consumes a scale-index-base byte. Its upper two bits give a scale exponent; the next three select index; the low three select base. A scale field of two means multiplication by four, implemented as a left shift by two. REX.X and REX.B extend index and base independently.

Consider `48 8b 44 8d f0`. REX.W selects eight-byte data, `8b` selects a register destination from a register/memory source, and ModR/M `44` selects destination RAX, SIB addressing and an eight-bit displacement. SIB `8d` selects scale exponent two, RCX as index and RBP as base. The final byte `f0` is signed −16. With RBP = `0x6000` and RCX = `0x2000`, the effective address is `0x6000 + 4 × 0x2000 − 16 = 0xdff0`.

Computing that value does not load the addressed data. The operand helper subsequently requests eight bytes through virtual memory. Permission, mapping and device behavior belong to that access. A successful address fixture validates arithmetic and field interpretation without proving that the corresponding memory is readable or that its contents have a particular value.

The SIB low index field four means no index only when REX.X is absent. With REX.X, it denotes R12. A mod-zero SIB base field five means no base and requires a displacement. `no_index` and `no_base` preserve these exceptions explicitly. They prevent execution from accidentally adding an ordinary register because the raw bit field happens to resemble its index.

## RIP-relative addressing and a documented override gap

For mod zero, no SIB and low r/m field five, 64-bit addressing uses a signed 32-bit displacement relative to the next instruction. The bytes `48 8b 05 78 56 34 12` have length seven. At starting RIP `0x100000`, the address is `0x100007 + 0x12345678`. Using the starting RIP without adding seven would be wrong, even though every individual decoded field looked plausible.

The current decoder marks that form `rip_rel` only when address size is eight. With address size four, it still consumes a displacement but does not set `no_base` for this no-SIB special case. `chris_eff_addr` consequently follows its ordinary base path and adds the register selected by r/m before truncating to 32 bits. This is a source-observed inconsistency in the override path. The positive address fixtures intentionally do not certify that path as correct.

Segment overrides expose another end-to-end limitation. The parser consumes their bytes without retaining which segment was selected, and the effective-address helper does not add FS/GS bases. A field in `ChrisArchitectureState` cannot repair information discarded during decode. Correct support requires a representation change plus matching execution semantics and tests, not only assigning an MSR value.

## Immediates, sign extension and host representation

`imm_n` accepts encoded immediate widths of one, two, four or eight bytes and verifies that the requested bytes fit in `avail`. It records both numeric contents and `imm_bytes`. For eight bytes, it combines two 32-bit pieces. Preserving width is necessary because the executor decides whether to sign-extend the encoded quantity; storing only an already widened unsigned value would lose that distinction.

Operand width need not equal immediate width. A 64-bit arithmetic operation can carry a signed 32-bit immediate. A register-immediate MOV form can carry a full 64-bit immediate, while another MOV form sign-extends its shorter immediate. The decoder must derive immediate size from the selected opcode family, not allocate eight immediate bytes whenever REX.W is present. `chris_imm_sx` later provides signed widening for supported widths.

The `ru16` and `ru32` helpers use `memcpy` into host integers. This avoids unaligned typed-pointer loads and aliasing issues, but it interprets the copied bytes in host byte order. The implementation is therefore not automatically portable to a big-endian host. By contrast, ChrisASM's shift-and-mask emitters explicitly choose little-endian output. Portability must be inspected on both encoding and decoding sides.

## Consumed length, incomplete input and publication

The decoder constructs a local zero-initialized `ChrisInsn`. If a required field is unavailable, helpers return a negative result and the top-level function returns before copying the local record to the caller. A caller must treat a negative return as failure and must not inspect an old output record as if it described the attempted bytes. This local-then-publish pattern helps keep partial parse state from masquerading as a complete instruction.

Unsupported or invalid classifications differ from incomplete input. For `0f 0b`, the current decoder returns a two-byte record classified as `UD`; execution can then raise invalid opcode. When its consumed length would exceed fifteen, it classifies UD and caps the recorded length at fifteen. These behaviors describe this decoder's interface, not a promise that every illegal encoding has been recognized with the full hardware exception priority.

Success reports the length of one instruction, which can be less than the available input. For `48 8b 44 8d f0 90`, the first instruction consumes five bytes and leaves the final NOP for the next decode. Advancing by buffer length instead would skip an instruction. Treating every positive return as equal to the supplied length would incorrectly reject valid multi-instruction input.

## Complexity, formatting and validation boundaries

The supported grammar consumes a bounded number of bytes, uses a fixed-size local structure and allocates no heap storage. Its per-instruction work is bounded by the instruction-length limit and fixed dispatch structure; decoding a stream of N bytes at known boundaries is linear in the amount consumed. This does not establish the cost of finding code in arbitrary mixed code/data input, which needs control-flow and format information.

`chris_format_insn` produces debugging text, including abbreviated memory operands such as `[mem]`. It is not a lossless serialization that can reconstruct all original bytes or prefixes. Trace tooling should preserve raw bytes and length alongside the formatted string. A future decoded-instruction cache would additionally need rules for writes to code, mapping changes and invalidation; such a cache is not attributed to this parser.

The repository probe compiles the actual decoder and operand code with rejecting memory stubs. Twenty literal fixtures, all 69 proper truncations of those fixtures, 80 register cases, two invalid register indices, four effective-address cases and one UD classification passed. This exercises the stated contracts while leaving prefix legality, unsupported instruction families, fault priority, address-override gaps and guest execution outside its proof. Broader fuzzing and differential testing would complement these fixtures; they are future validation work rather than results claimed here.

Consult the [Intel instruction-set reference](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html) for normative encodings. The implementation findings above are revision-bound and distinguish parser mechanics, architectural requirements and unresolved behavior. That separation is what allows a later agent to update one field or helper without silently expanding the emulator's claimed compatibility.
