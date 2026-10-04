---
id: clvm-spec
lang: en
type: specification
volume: 15-specifications
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/clvm/clvm.h
  - compiler/clvm/clvm_format.c
  - compiler/clvm/clvm_vm.h
  - compiler/clvm/clvm_vm.c
  - compiler/clvm/clasm.h
  - compiler/clvm/clasm.c
  - compiler/lang_pipeline.c
  - kernel/lang/clvm_sys.h
  - kernel/lang/clvm_sys.c
  - kernel/lang/clvm_sync.h
  - compiler/jit/jit.c
  - tools/test_clasm.c
  - tools/test_clasm_games.c
  - tools/test_clvm_sync.c
  - tools/test_fuzz_clvm.c
symbols:
  - clvm_parse
  - clvm_write_image
  - clvm_write_image_v2
  - clvm_vm_init
  - clvm_vm_set_memory
  - clvm_step
  - clvm_sys_dispatch
  - clvm_guest_malloc
  - clvm_guest_realloc
  - clvm_guest_setjmp
  - clvm_guest_longjmp
depends_on:
  - specifications-policy
  - clvm-bytecode
  - clvm-memory
  - clvm-syscalls
  - clvm-interpreter
related:
  - chrisc-clvm
  - jit
  - debugger
  - gc-libraries
---

# CLVM executable and virtual-machine specification

## Status

CLVM is the stack virtual machine used by the ChrisC execution pipeline.

This specification describes the executable container, interpreter state, bytecode encoding, memory model, control-flow rules, faults and system-call boundary implemented at ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

The current container format is **version 2**. The loader also accepts version 1.

## Architectural split

CLVM has three separate contracts that must not be conflated:

1. the serialized `.CLV` executable container;
2. the bytecode instruction set;
3. the runtime VM state and host syscall ABI.

The container tells the loader where code begins, where execution enters and how much guest memory is requested.

The bytecode defines deterministic stack-machine operations.

The host runtime provides scheduling, system services, graphics, files, networking, threads and other facilities through `SYS`.

## File magic

Every CLVM image starts with:

    43 4c 56 4d

or ASCII:

    C L V M

The loader rejects any other magic.

## Version constants

Current constants are:

    CLVM_VERSION    = 2
    CLVM_VERSION_V1 = 1

The v1 header is 16 bytes.

The v2 header is 24 bytes.

## Byte order

All multibyte integer fields in the container are explicitly encoded little-endian.

Instruction immediates and memory integer loads/stores are also little-endian.

This is part of the CLVM binary contract.

## Version-1 header

The v1 layout is:

| Offset | Size | Field |
|---:|---:|---|
| 0 | 4 | magic "CLVM" |
| 4 | 1 | version = 1 |
| 5 | 1 | flags |
| 6 | 2 | entry |
| 8 | 4 | code size |
| 12 | 4 | code checksum |

The code starts at offset 16.

The v1 entry point is limited to 16 bits.

The legacy writer also restricts code size to at most 65535 bytes.

## Version-2 header

The v2 layout is:

| Offset | Size | Field |
|---:|---:|---|
| 0 | 4 | magic "CLVM" |
| 4 | 1 | version = 2 |
| 5 | 1 | flags |
| 6 | 2 | reserved, currently zero |
| 8 | 4 | code size |
| 12 | 4 | code checksum |
| 16 | 4 | entry |
| 20 | 4 | memory hint |

The code starts at offset 24.

Version 2 expands both executable size and entry-point range and adds a memory-size hint.

## Code-size limit

The parser accepts at most:

    CLVM_MAX_CODE = 16 MiB

It additionally requires:

    code_size == file_size - header_size

A CLVM file therefore contains exactly one bytecode body after its header. Trailing payload is not part of the current format.

## Entry point

The entry is a byte offset into the code array.

The loader requires:

    entry < code_size

The interpreter initializes:

    pc = image.entry

No separate symbol table or entry-name lookup exists in the CLVM container.

## Flags

The only currently recognized image flag is:

    CLVM_FLAG_GAME = 0x01

Unknown flag bits are rejected by the parser.

The image flag is metadata for the host pipeline; it does not change core instruction decoding by itself.

## Memory hint

Version 2 adds:

    mem_hint

This requests a guest-memory capacity from the host pipeline.

A zero hint means "use the host default".

The core standalone VM initializer allocates:

    CLVM_MEMORY_SIZE = 1 MiB

The ChrisOS language pipeline may attach larger memory. Large generated programs can request tens of MiB; the current pipeline uses a 32 MiB hint for sufficiently large game images.

The memory hint is a request, not an address-space mapping description.

## Bytecode checksum

The container stores a 32-bit FNV-1a checksum of the code bytes.

Algorithm:

    hash = 2166136261
    for each byte:
        hash ^= byte
        hash *= 16777619

The parser rejects a checksum mismatch.

Header bytes are not included in this checksum.

## Loader rejection classes

The parser classifies failures as:

- null argument;
- file smaller than required header;
- bad magic;
- unsupported version;
- unsupported flags;
- invalid code size;
- entry outside bytecode;
- checksum mismatch;
- output-capacity failure for writers.

A valid image is fully size-checked before execution.

## Core VM state

The runtime VM contains:

- code pointer and code size;
- program counter;
- operand stack;
- call stack;
- linear guest memory;
- wake tick;
- executed-instruction counter;
- state/fault information;
- syscall callback and host context;
- print history;
- safepoint state;
- guest heap cursor;
- IL locals and arguments;
- TLS slots;
- thread-join state.

The serialized file does not contain this mutable runtime state.

## Operand stack

The operand stack has:

    CLVM_STACK_MAX = 256

entries.

Each stack entry is an `int64_t`.

Even opcodes historically defined around 32-bit values now execute on a 64-bit operand stack unless their semantics explicitly narrow to 32 bits.

Stack overflow and required-pop underflow are VM faults.

## DROP behavior

`DROP` is intentionally permissive in the current interpreter:

- if the stack is non-empty, it removes one value;
- if the stack is empty, it does nothing.

This differs from arithmetic/loads/calls that fault on missing operands.

Implementations matching current behavior must preserve that distinction.

## Call stack

The return-address stack has:

    CLVM_CALL_MAX = 64

entries.

Each entry is a 32-bit code offset.

`CALL`, `CALL32`, `CALLI` and `CALLT` push a return PC.

`RET` pops it.

Overflow and underflow are explicit faults.

## VM states

States are:

    READY
    RUNNING
    WAITING
    HALTED
    FAULTED

`clvm_step` transitions READY to RUNNING for a slice.

If the instruction budget expires normally, state returns to READY and the result is `CLVM_STEP_SLICE`.

WAITING yields without executing.

HALTED and FAULTED are terminal until host code deliberately changes state.

## Step results

A VM slice returns one of:

    CLVM_STEP_SLICE
    CLVM_STEP_YIELD
    CLVM_STEP_HALT
    CLVM_STEP_FAULT

This lets the host scheduler distinguish time slicing from guest termination or failure.

## Instruction accounting

Every successfully fetched opcode increments:

    vm->executed

In the freestanding kernel build, the interpreter also checks process-slice scheduling periodically.

At every 8192 executed instructions it may yield if `proc_slice_due()` reports that the process slice expired.

Safepoints and syscalls are additional scheduling boundaries.

## Opcode map

The current opcode space is contiguous from `0x00` through `0x47`.

### Core stack and integer operations

| Opcode | Mnemonic | Immediate | Effect |
|---:|---|---|---|
| 00 | NOP | — | no operation |
| 01 | PUSH | i32 | push sign-extended 32-bit constant |
| 02 | ADD | — | signed 64-bit stack addition |
| 03 | SUB | — | subtraction |
| 04 | MUL | — | multiplication |
| 05 | DIV | — | signed division |
| 06 | DUP | — | duplicate top |
| 07 | PRINT | — | pop into diagnostic print ring |
| 08 | HALT | — | halt VM |
| 0f | DROP | — | drop top if present |
| 10 | SWAP | — | exchange top two |
| 11 | EQ | — | equality |
| 12 | LT | — | signed less-than |
| 14 | MOD | — | signed remainder |
| 15 | NE | — | inequality |
| 16 | LE | — | signed <= |
| 17 | GT | — | signed > |
| 18 | GE | — | signed >= |
| 19 | NEG | — | arithmetic negation |
| 1d | UDIV | — | unsigned division |
| 1e | UMOD | — | unsigned remainder |
| 1f | ULT | — | unsigned < |
| 35 | AND | — | bitwise AND |
| 36 | OR | — | bitwise OR |
| 37 | XOR | — | bitwise XOR |
| 38 | SHL | — | shift left by count & 63 |
| 39 | SHR | — | logical right shift |
| 3a | SAR | — | arithmetic right shift |
| 3b | NOT | — | bitwise complement |
| 45 | ULE | — | unsigned <= |
| 46 | UGT | — | unsigned > |
| 47 | UGE | — | unsigned >= |

Binary operations pop `b`, then `a`, and push the result of the conceptual expression `a op b`.

## Division faults

Signed and unsigned division/remainder fault on zero divisor.

Signed `DIV` and `MOD` also fault on the two's-complement overflow case:

    INT64_MIN / -1

This avoids host-language undefined behavior crossing the VM boundary.

## Memory operations

| Opcode | Mnemonic | Width |
|---:|---|---:|
| 0d | LOAD | 4 bytes |
| 0e | STORE | 4 bytes |
| 1a | LOADB | 1 byte |
| 1b | STOREB | 1 byte |
| 26 | LOAD64 | 8 bytes |
| 27 | STORE64 | 8 bytes |
| 28 | FLOAD | 4 bytes |
| 29 | FSTORE | 4 bytes |

Guest addresses are integer byte offsets into the attached linear memory.

Negative addresses, absent memory and out-of-range accesses produce `CLVM_FAULT_BAD_ADDRESS`.

No instruction may directly dereference a host pointer.

## STORE stack order

For store operations, the current interpreter pops:

1. address;
2. value.

It then writes the value at the popped address.

Bytecode generators must follow this exact stack order.

## Linear memory

The VM exposes one byte-addressed linear memory region:

    memory[0 .. mem_size-1]

The region can be internally owned by the VM or externally attached by the host through `clvm_vm_set_memory`.

Changing attached memory clears the VM-owned flag and can release the prior owned allocation.

## Heap start

The guest bump allocator chooses its initial cursor from memory size:

- at least 16 MiB: 1 MiB;
- above 128 KiB: 64 KiB;
- otherwise: half of memory.

This deliberately leaves a low region available for globals, strings and static compiler data.

## Guest allocation

`clvm_guest_malloc` uses a simple bump allocator.

Allocated chunks include an eight-byte size prefix.

Allocation is aligned to eight bytes.

`free` currently succeeds but does not reclaim space.

`realloc` allocates a new block and copies the old payload.

Therefore guest heap semantics are not equivalent to a general-purpose reclaiming allocator.

## Control flow

Short control-flow instructions use signed 16-bit relative displacements:

    JMP
    JZ
    JNZ
    CALL

Long forms use signed 32-bit relative displacements:

    JMP32
    JZ32
    JNZ32
    CALL32

The displacement is relative to the PC **after** the immediate has been consumed.

Targets must remain inside:

    0 <= target < code_size

Otherwise execution faults with `CLVM_FAULT_BAD_JUMP`.

## Conditional branches

`JZ` / `JZ32` pop one value and branch when it equals zero.

`JNZ` / `JNZ32` pop one value and branch when it is nonzero.

The condition is consumed regardless of whether the branch is taken.

## Indirect and table calls

`CALLI` pops an absolute code offset from the operand stack.

It must be inside the code image.

`CALLT` carries a 32-bit absolute code offset as an immediate.

At this revision `CALLT` sets the PC directly after pushing the return address; unlike `CALLI`, its implementation does not perform an explicit range check before assigning the PC. An invalid value will subsequently fail instruction fetch.

This implementation detail matters for fault classification.

## Floating-point representation

CLVM floating operations use IEEE-754 single-precision bit patterns carried in the low 32 bits of stack entries.

Instructions are:

    FPUSH
    FLOAD
    FSTORE
    FADD
    FSUB
    FMUL
    FDIV
    FNEG
    FTOI
    ITOF
    FEQ
    FLT
    FLE

The VM reinterprets 32-bit integer bits as C `float`.

Results are returned as 32-bit float bit patterns, sign-extended through the 64-bit stack representation when pushed through current helpers.

## Float division

`FDIV` checks whether the decoded divisor equals `0.0f`.

If so, the VM raises the same divide-by-zero fault class used by integer division.

The interpreter therefore does not expose IEEE infinity generation for float division by zero.

## 64-bit immediate

`PUSH64` is opcode:

    0x25

followed by an eight-byte little-endian immediate.

It pushes that bit pattern as one 64-bit stack value.

## IL-oriented instructions

The VM includes a small group used by higher-level IL/runtime paths:

    LDARG index:u8
    STLOC index:u8
    LDLOC index:u8
    NEWOBJ size:u32
    LDFLD offset:u32
    STFLD offset:u32
    CALLT target:u32
    LDSTR address:u32
    SAFEPOINT

There are:

    16 IL argument slots
    32 IL local slots

Bad indexes fault as unknown/invalid opcode state in the current implementation.

## Object operations

`NEWOBJ` allocates guest memory using the VM heap and pushes the returned guest address.

A zero requested size is promoted to 16 bytes.

`LDFLD` and `STFLD` treat object references as guest-memory addresses plus a 32-bit field offset and operate on eight-byte fields.

There is no object-layout descriptor inside the VM instruction stream.

Object structure is therefore a compiler/runtime convention layered on linear memory.

## Safepoints

`SAFEPOINT` temporarily marks:

    vm->safepoint = 1

and invokes the optional host callback.

Calls, allocation and syscalls also create safepoint-like boundaries in current execution.

Safepoints support scheduler/GC/debug integration without making those subsystems intrinsic bytecode state.

## System-call instruction

`SYS` has no immediate operand.

It pops one value from the operand stack and interprets the low 32 bits as the syscall ID:

    id = pop()

Then it calls:

    vm->sys(vm, id, vm->sys_user)

A missing callback or nonzero callback return produces:

    CLVM_FAULT_BAD_SYS

## Syscall ABI ownership

The core VM does not define what syscall ID 1, 50 or 170 means.

Those meanings belong to the selected host callback.

In ChrisOS, the canonical kernel implementation is:

    clvm_sys_dispatch()

That dispatcher is therefore the current system-service ABI for ChrisOS-hosted CLVM programs.

## Current syscall surface

At this revision `clvm_sys_dispatch` contains **173 explicit syscall case IDs**.

The surface covers families including:

- 2D graphics and presentation;
- input, timing and sleep;
- 3D drawing, camera, textures and voxels;
- filesystem I/O;
- guest allocation and nonlocal jump support;
- GC;
- threads, join, mutexes, condition variables and TLS;
- sockets and DNS;
- checkpoint/hot reload;
- random and cryptographic primitives;
- audio;
- privileged driver I/O, PCI and MMIO;
- additional platform/runtime services.

The IDs are implemented as numeric `case` labels rather than a single public enum in the current source.

That is an ABI-maintenance risk: changing a numeric case can silently break already compiled CLV programs.

## Representative syscall IDs

Stable behavior must be reconciled against source. Representative IDs in this revision include:

| ID | Service |
|---:|---|
| 1 | put pixel |
| 2 | fill rectangle |
| 3 | line |
| 6 | clear surface |
| 10 | key state |
| 11 | current tick |
| 12 | sleep/wait |
| 13 | speaker tone |
| 30 | FPS estimate |
| 39 | viewport resize |
| 40 | viewport width |
| 41 | viewport height |
| 50 | file open |
| 51 | file close |
| 52 | file read |
| 53 | file write |
| 54 | file size/stat |
| 55 | file exists |
| 56 | guest malloc |
| 57 | guest free |
| 58 | setjmp |
| 59 | longjmp |
| 61 | guest realloc |
| 62 | thread create |
| 63 | thread join |
| 70 | GC allocation |
| 71 | GC collect |
| 127 | mutex lock |
| 128 | mutex unlock |
| 129 | condition wait |
| 130 | condition wake |
| 131 | TLS get |
| 132 | TLS set |
| 140–146 | socket/DNS family |
| 150 | random u32 |
| 151 | SHA-256 |
| 152 | AES-128 block encrypt |
| 153 | X25519 |
| 160 | AC97 audio write |
| 170–175 | privileged low-level driver services |

This table is descriptive, not a substitute for `clvm_sys_dispatch`.

## Syscall stack convention

Syscall arguments are passed on the operand stack.

The dispatcher pops them in service-specific order.

Results are normally pushed back to the same operand stack.

A syscall may also transition the VM to WAITING, after which `SYS` returns a yield result to the scheduler.

Therefore the syscall ABI includes stack shape and state-transition semantics, not just numeric IDs.

## Blocking syscalls

Sleep, join, mutex/condition waits, socket receive and IRQ waits can place a VM into WAITING.

Some blocking handlers re-push enough arguments plus the syscall ID so the operation can be retried after wakeup.

This is a cooperative continuation mechanism implemented above the core opcode decoder.

## Thread model

The ChrisOS host can create child CLVM instances that share:

- code bytes;
- linear guest memory;
- syscall callback/context.

Each child has independent:

- operand stack;
- call stack;
- PC;
- VM state;
- TLS array.

This means guest addresses are meaningful across threads of the same slot because the memory region is shared.

## Synchronization identity

The synchronization helper defines a mutex identity as:

    (slot_id, guest_address)

The same numeric guest address in two different application slots is not the same synchronization object.

This prevents accidental cross-application locking solely because address values coincide.

## TLS

Each VM has:

    16 TLS slots

of 64-bit values.

Current kernel syscalls expose indexed get/set operations.

TLS is per VM/thread state, not stored in linear guest memory unless software explicitly mirrors it there.

## setjmp/longjmp guest state

The runtime provides guest `setjmp`/`longjmp` helpers.

The saved record includes execution state such as PC, operand-stack depth, call-stack depth and stack contents.

The buffer resides in guest memory, so address-range validation is required.

This is a VM-specific continuation encoding and should not be treated as a native C ABI `jmp_buf`.

## Fault model

Defined VM faults are:

    PC
    OPCODE
    TRUNCATED
    STACK_UNDERFLOW
    STACK_OVERFLOW
    CALL_UNDERFLOW
    CALL_OVERFLOW
    DIV_ZERO
    DIV_OVERFLOW
    BAD_ADDRESS
    BAD_JUMP
    BAD_SYS

On fault:

    state = FAULTED
    fault = reason
    fault_pc = opcode PC

and the step result is `CLVM_STEP_FAULT`.

## Fault PC

The recorded `fault_pc` is the PC of the opcode being executed, captured before the opcode fetch advances the live PC.

This gives debuggers a stable location for the failing instruction.

## Truncated operands

If an opcode is present but its immediate bytes extend past the code image, the VM raises:

    CLVM_FAULT_TRUNCATED

This is distinct from fetching an opcode when PC itself is outside code, which raises:

    CLVM_FAULT_PC

## Unknown opcodes

Any byte not handled by the current switch raises:

    CLVM_FAULT_OPCODE

Even though the currently assigned opcode range is contiguous through `0x47`, future extensions must preserve version/compatibility expectations for old interpreters.

## Assembler contract

ChrisAsm's CLVM assembler compiles textual mnemonics and labels to this bytecode.

Current assembler bounds include:

    source <= 32768 bytes
    labels <= 128
    label name <= 24 bytes

These are assembler implementation limits, not intrinsic limits encoded in the `.CLV` file.

## Compiler pipeline

The ChrisC pipeline can generate CLVM bytecode and then package it as a CLV image.

For small programs it may still emit a v1 image when code/entry fit 16 bits and no memory hint is needed.

Otherwise it emits v2.

Therefore a current ChrisOS installation can legitimately contain both v1 and v2 CLV files.

## JIT relationship

The JIT is an alternative execution backend for supported CLVM bytecode.

It does not redefine the CLV file format.

The interpreter remains the semantic reference for opcode behavior unless a documented exception exists.

JIT syscall dispatch uses a trampoline carrying VM and host context.

Executable JIT pages are mapped into a dedicated kernel virtual range and handled with explicit TLB synchronization on teardown.

## Security boundary

CLVM bytecode is not native machine code.

Ordinary guest memory references are range-checked against the VM's linear memory.

System services are reachable only through the syscall callback.

However, the host syscall ABI includes privileged driver operations gated by host capability checks.

Therefore CLVM isolation depends on both:

1. interpreter memory/control-flow validation;
2. correct host-side capability enforcement.

A safe loader cannot compensate for an over-permissive syscall dispatcher.

## Determinism boundary

Core arithmetic, stack and linear-memory execution is largely deterministic for a fixed image and initial memory.

Syscalls deliberately cross that boundary into time, input, filesystem, network, audio, graphics and hardware state.

Tests that require deterministic replay should either stub the syscall callback or record external inputs.

## Compatibility requirements

The following are ABI-significant and must not change silently:

- CLVM magic;
- v1/v2 header layouts;
- little-endian encoding;
- checksum algorithm;
- opcode numeric assignments;
- operand immediate widths;
- stack effects;
- branch displacement base;
- fault conditions;
- syscall numeric meanings for published services.

Incompatible changes require either a new container/ISA version or an explicit compatibility mechanism.

## Current limitations

The current design has several limits:

- no explicit ISA-version field separate from container version;
- no section table;
- no read-only data section distinction;
- no code signing;
- no per-function metadata in the CLV container;
- no centrally declared syscall-number enum;
- fixed operand/call stack sizes;
- simple bump allocator with non-reclaiming free;
- host-dependent floating behavior through C `float`;
- partial interpreter/JIT parity must be validated continuously.

These are current properties, not promises about future architecture.

## Recommended next compatibility work

A future CLVM revision should consider:

1. separate container and ISA version numbers;
2. centralized syscall ID definitions;
3. machine-readable opcode metadata;
4. verifier pass for branch targets and stack effects before execution;
5. optional read-only/static-data sections;
6. explicit float semantics;
7. structured capability manifest in the executable;
8. deterministic syscall-test harness;
9. differential interpreter/JIT conformance tests;
10. signed or hashed provenance metadata for distributed CLV images.

## Conformance summary

A conforming CLVM v2 loader/interpreter must, at minimum:

- parse the 24-byte little-endian v2 header;
- validate magic, flags, size, entry and FNV-1a checksum;
- execute the defined opcode numbers with their exact immediate widths and stack effects;
- maintain a 64-bit operand stack and bounded call stack;
- range-check guest memory;
- validate relative and indirect branches according to current rules;
- enter explicit fault state on invalid execution;
- treat `SYS` as a host callback boundary;
- preserve scheduler-visible WAITING/HALTED/FAULTED states.

## Revision note

This specification was reconciled against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

The most important distinction is that CLVM is not merely a bytecode list: it is a versioned executable format plus a precise interpreter state machine plus a host ABI. Compatibility work must consider all three layers together.
