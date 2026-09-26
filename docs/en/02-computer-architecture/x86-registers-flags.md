---
id: x86-registers-flags
lang: en
type: technical-chapter
volume: 02-computer-architecture
status: expanded
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - chrisvm/chris_arch.h
  - chrisvm/cpu/common/state.c
  - chrisvm/cpu/common/cpuid.c
  - chrisvm/cpu/emulator/operands.c
  - chrisvm/cpu/emulator/flags.c
  - chrisvm/cpu/emulator/execute.c
  - chrisvm/cpu/emulator/chriscpu.c
symbols:
  - ChrisArchitectureState
  - chris_arch_reset
  - chris_cpuid
  - chris_read_gpr
  - chris_write_gpr
  - chris_flags_bin
  - chris_cc_true
  - cr_ptr
  - msr_access
depends_on:
  - cpu-datapath-isa
  - arithmetic-circuits
  - registers-counters
related:
  - machine-code
  - x86-instruction-encoding
  - x86-64-memory-privilege
  - privilege-rings
---

# x86-64 registers, aliases and flags

## Architectural storage and software naming

A register name denotes a processor-visible storage location or a view of one. It does not specify how many physical storage cells implement that view. The sequential-circuit chapters explain storage elements; the datapath chapter explains how instructions select and transform values. Here the contract is the value software observes, including what happens to bits outside a selected subregister. That contract is essential for writing an emulator, compiler register allocator or context switch.

ChrisCPU represents sixteen general registers in a union containing `uint64_t gpr[16]` and named fields. The order is architectural encoding order rather than alphabetic order. Code using index one reads RCX, not RBX. The named and indexed views designate the same storage, so updating one changes the value observed through the other. This is a representation convenience inside the C implementation, not a separately serialized register bank.

| Index | 64-bit | 32-bit | 16-bit | Low byte with REX |
|---|---|---|---|---|
| 0 | RAX | EAX | AX | AL |
| 1 | RCX | ECX | CX | CL |
| 2 | RDX | EDX | DX | DL |
| 3 | RBX | EBX | BX | BL |
| 4 | RSP | ESP | SP | SPL |
| 5 | RBP | EBP | BP | BPL |
| 6 | RSI | ESI | SI | SIL |
| 7 | RDI | EDI | DI | DIL |
| 8–15 | R8–R15 | R8D–R15D | R8W–R15W | R8B–R15B |

An ABI assigns additional roles such as argument passing, result passing and preservation across calls. Those conventions do not make a register inherently incapable of holding another value. RSP is special for stack instructions, while an ABI may also designate RBP as a frame pointer. A compiler may omit a frame pointer under a suitable convention, but cannot ignore stack-instruction semantics. Architectural roles and calling-convention roles must be documented separately.

## Partial writes are state transformations

Let the old 64-bit value be `0x1122334455667788` and the input value be `0xaabbccdd`. The resulting storage depends on operand width:

| Write | Resulting 64-bit storage | Rule |
|---|---|---|
| 64-bit register | `0x00000000aabbccdd` | Replace all 64 bits with input |
| 32-bit subregister | `0x00000000aabbccdd` | Replace low 32 and clear high 32 |
| 16-bit subregister | `0x112233445566ccdd` | Replace low 16, preserve the rest |
| Low byte | `0x11223344556677dd` | Replace low 8, preserve the rest |
| Legacy high byte | `0x112233445566dd88` | Replace bits 15:8, preserve other bits |

The equal first two results are specific to this chosen input. A full-width input with nonzero upper bits distinguishes a 64-bit write from a 32-bit write. Algebraically, a partial low-w-bit replacement is `(old & ~mask) | (value & mask)`, where mask is 2ʷ − 1. A 32-bit write deliberately does not use the preservation formula. Applying one generic masking rule to every width would therefore implement the ISA incorrectly.

`chris_write_gpr` contains these branches explicitly. `chris_read_gpr` returns the selected portion masked to width. Both reject indices outside zero through fifteen. Their intended operand sizes are one, two, four and eight bytes; arbitrary size values are not a public validated instruction format. The decoder and callers must maintain that precondition. A helper's final full-width branch should not be mistaken for proof that every integer size argument is legal.

## High-byte aliases and the presence of REX

Without a REX prefix, byte-register codes four through seven name AH, CH, DH and BH, the second bytes of the first four registers. With any REX prefix, those codes name SPL, BPL, SIL and DIL. REX byte `40` has all extension bits clear but still changes byte-register interpretation. Removing it as apparently redundant can change program behavior.

The literal sequence `88 e0` moves AH into AL. `40 88 e0` moves SPL into AL. In both cases the ModR/M register field is four, but the selected storage differs. `high8` checks byte operand size, absence of REX and code range; `gpr_index8` maps the legacy high-byte code back to the first four storage slots. The write path replaces bits 15:8 when that predicate holds.

This aliasing is a compiler constraint as well as an emulator concern. A byte operation requiring REX for another operand cannot simultaneously name AH through the legacy encoding. Register allocation must consider encodability, not just whether two abstract values fit in available bits. A disassembler must also retain prefix context to print the correct register name.

## RFLAGS as independently meaningful fields

RFLAGS combines arithmetic status, execution control and system-related state. It is not one Boolean success result. The following table defines architectural roles, not a claim that every feature is completely implemented by ChrisCPU:

| Bits | Name | Role |
|---|---|---|
| 0 | CF | Carry or borrow for unsigned arithmetic |
| 2 | PF | Even parity of the low result byte |
| 4 | AF | Carry or borrow across bit 3 |
| 6 | ZF | Result equals zero at operation width |
| 7 | SF | Most significant result bit at operation width |
| 8 | TF | Single-step control |
| 9 | IF | Maskable-interrupt enable state |
| 10 | DF | Direction for string traversal |
| 11 | OF | Signed arithmetic overflow |
| 12–13 | IOPL | I/O privilege level |
| 14 | NT | Nested-task state |
| 16 | RF | Resume control for debugging |
| 17 | VM | Virtual-8086 mode state |
| 18 | AC | Alignment-check state in its architectural context |
| 19–20 | VIF, VIP | Virtual interrupt flag and pending state |
| 21 | ID | CPUID identification-related flag |

`write_status` clears and replaces CF, PF, AF, ZF, SF and OF, preserves the remaining incoming bits and forces bit one to one. PF is calculated from the low byte, even for a 64-bit arithmetic operation. ZF and SF use operand width. Preserving unrelated bits is an invariant: adding integers must not accidentally clear IF or DF. Conversely, preserving a field in this helper does not implement all instructions that can modify it.

`chris_flags_bin` computes a masked result and returns updated flags. ADD and ADC use a wider intermediate to obtain carry; subtraction compares unsigned operands for borrow and includes incoming carry for SBB. The arithmetic-circuits chapter derives the overflow equations. Logical operations in this helper choose AF equal to zero. Software must not promote that deterministic emulator choice into a general architectural guarantee for flags that the ISA leaves undefined.

## Conditional interpretation and signed order

`chris_cc_true` implements sixteen condition codes from CF, PF, ZF, SF and OF. Equality tests ZF. Unsigned below tests CF; unsigned above requires both CF and ZF clear. Signed less-than tests `SF != OF`; signed greater-than requires ZF clear and `SF == OF`. The overflow correction is necessary because the sign of a wrapped subtraction alone does not establish signed ordering.

For an eight-bit example, 127 minus −1 produces the wrapped bit pattern `0x80`. SF is one, but OF is also one; the signed less-than predicate is false, as required because 127 is greater than −1. Branches, conditional moves and SETcc consume these predicates in different ways. Producing the same Boolean predicate does not establish identical memory-access or fault behavior for those instruction families.

## Control flags and event timing

CLC and STC modify CF without recomputing the other arithmetic status bits. CLD and STD similarly change DF, which string operations consult to choose traversal direction. CLI and STI change IF in the inspected dispatcher; STI additionally sets `sti_delay`. The run loop consumes this delay before accepting a pending interrupt, so assigning IF alone would miss an execution-timing part of the instruction's contract. These controls do not make arithmetic status a single replaceable word: each instruction owns a specified subset of fields. They also illustrate why a snapshot of RFLAGS alone omits emulator event state held in `sti_delay` and `irq_pending`.

## RIP, RSP and context completeness

RIP identifies instruction flow; RSP identifies the stack position used by stack operations. Saving their numeric values without saving or preserving the referenced memory does not capture a runnable process. Likewise, the architectural structure contains control and descriptor state that influences how those values are interpreted. A context boundary must specify which state it owns, which state remains shared and which state is reconstructed.

`cpu_get` and `cpu_set` copy `ChrisArchitectureState`. This is an in-process representation operation with no field-by-field portable serialization. Host structure padding, integer representation, version evolution and omitted machine state matter if a persistent snapshot is desired. The copy also has no visible synchronization against a concurrently running CPU. A caller needs a quiescent execution boundary or a separately defined synchronization mechanism.

## Control registers, descriptors and MSRs

The model stores CR0, CR2, CR3, CR4 and CR8. `cr_ptr` returns pointers only for those register numbers; other numbers fail instruction handling. CR0 includes mode and write-protection controls, CR2 records a faulting linear address, CR3 supplies a page-table root, CR4 carries architectural extensions and CR8 represents task-priority control. This overview defines roles; detailed allowed-bit and transition rules belong to system architecture and must not be inferred from a 64-bit storage slot.

The MOVCR handler reads or writes the selected slot. A write identified as CR3 increments `tlb_gen`. A generation counter is bookkeeping, not proof of a modeled associative TLB, shootdown protocol or complete validation of reserved control bits. Source inspection of this handler does not show a CPL check before the transfer. The same scoped concern applies to the inspected MSR and CLI/STI dispatch paths. This is a concrete limitation of these paths, not a complete audit of every privilege boundary in the project.

`ChrisSeg` holds selector, base, limit and attributes. `ChrisDtr` holds base and limit for descriptor-table registers. These C structures are not packed architectural descriptors: code that loads or stores a descriptor-table operand explicitly handles a two-byte limit and eight-byte base. The architectural model also keeps TR and LDTR state. Merely retaining those values does not prove every task-switch or segment-validation rule is implemented.

`msr_access` selects an MSR using low ECX. Recognized slots include EFER, STAR, LSTAR, CSTAR, FMASK, FS base, GS base, kernel GS base and APIC base. A write combines EDX:EAX into 64 bits; a read returns the two halves. An unknown index raises a general-protection exception. The presence of LSTAR storage does not implement the SYSCALL instruction, and the presence of FS/GS base storage does not prove effective-address helpers add those bases.

## Reset, feature discovery and executable evidence

`chris_arch_reset` clears the structure, sets RFLAGS to two and CR0 to PE plus NE. This is the emulator's selected initial state; it must not be described as a bit-for-bit physical x86 power-on reset sequence. Boot construction adds the state needed by its own protocol. Resetting this structure also does not reset device memory or pending events outside it.

`chris_cpuid` returns deterministic virtual leaves and never forwards host CPUID. The vendor string is `ChrisCPU` followed by four spaces. Standard leaf one advertises TSC, MSR, PSE, APIC and CMOV, while omitting FPU and SSE. The extended leaf advertises long mode. Although the model reserves sixteen 16-byte XMM slots and stores EFER-related values, those fields do not justify advertising full vector or system-call execution. Feature discovery is a promise to guest software and must follow implemented behavior.

The instruction-contract probe verifies partial writes and readback for all sixteen indices at 16, 32 and 64 bits, plus byte aliases with and without REX: 80 cases in total. It also rejects two invalid register indices. The separate arithmetic probe checks arithmetic and condition-code behavior against independently calculated expectations. These tests passed on the declared revision. They do not validate guest context switching, exception delivery, every MSR restriction or concurrent snapshot safety; those require evidence at their respective interfaces.

The [Intel architecture manuals](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html) define normative register and privilege semantics. The source files listed above define the currently observed ChrisCPU representation and its limits. Future work must connect missing checks to explicit fault cases rather than treat a field's existence as completed architectural support.
