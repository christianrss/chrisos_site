---
id: clvm-interpreter
lang: en
type: technical-chapter
volume: 07-language-systems
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/clvm/clvm.h
  - compiler/clvm/clvm_vm.h
  - compiler/clvm/clvm_vm.c
  - compiler/chrisc/chrisc.c
  - compiler/lang_pipeline.c
  - compiler/lang_pipeline.h
  - compiler/jit/jit_compile.c
  - compiler/jit/jit_runtime.c
  - tools/test_editor_vi.c
  - tools/test_jit_vm.c
  - tools/test_chrisc_fn.c
  - tools/test_chrisc_float.c
  - tools/test_store64_copy.c
  - tools/test_doom_jit_diff.c
symbols:
  - clvm_step
  - clvm_vm_init
  - clvm_vm_push64
  - clvm_vm_pop64
  - clvm_vm_wait
  - clvm_vm_wake
  - clvm_fault_text
  - fetch
  - jump_rel16
  - jump_rel32
  - mem_ok
  - fail
  - lang_tick
  - lang_safepoint
  - jit_rt_exec_at_pc
  - jit_rt_run_range
depends_on:
  - clvm-bytecode
  - clvm-memory
  - clvm-syscalls
related:
  - jit
  - jit-memory
  - calling-conventions
  - debugger
  - process-lifecycle
---

# CLVM interpreter architecture and execution model

## Scope

The CLVM interpreter is the reference execution engine for CLV bytecode inside ChrisOS.

Its central function is:

    clvm_step(ClvmVm *vm, uint32_t budget)

The function does not run an application forever. It executes at most a bounded number of bytecode instructions and returns a scheduling result to its caller.

This matters because CLVM is integrated into the desktop/application scheduler rather than owning the machine.

The interpreter is therefore simultaneously:

- a bytecode decoder;
- a stack machine;
- a control-flow engine;
- a memory-access enforcement point;
- a syscall boundary;
- a cooperative execution slice;
- a debugger-friendly reference implementation;
- the semantic baseline against which the JIT is compared.

![CLVM interpreter loop](../../assets/diagrams/clvm-interpreter-en.svg)

This chapter focuses on execution semantics. The binary CLV format is documented in the bytecode chapter, guest RAM in the memory chapter, and service IDs in the syscall chapter.

## VM execution state

ClvmVm contains the complete interpreter-visible state for one execution context.

The core fields are:

| Field | Role |
|---|---|
| code / code_size | immutable bytecode payload and logical extent |
| pc | next bytecode address |
| stack[256] / sp | 64-bit operand stack |
| calls[64] / csp | return-PC stack |
| memory / mem_size | guest data memory |
| wake_tick | timer-wait target |
| executed | cumulative fetched-instruction counter |
| state | READY, RUNNING, WAITING, HALTED or FAULTED |
| fault / fault_pc | terminal VM fault record |
| sys / sys_user | host-service callback and context |
| print_ring[8] | recent PRINT values for diagnostics |
| safepoint / on_safepoint | safepoint state and callback |
| il_loc[32] | IL-style local slots |
| il_arg[16] | IL-style argument slots |
| tls[16] | small per-VM TLS storage |
| join_wait | thread-join runtime state |

Operand and call stacks are fixed-capacity arrays inside ClvmVm.

They are not guest-memory objects.

That separation prevents an ordinary guest STORE from directly rewriting the interpreter's stack pointer, call stack or fault fields.

## Initialization

clvm_vm_init installs the image:

    code      = image->code
    code_size = image->code_size
    pc        = image->entry

It clears both stacks, initializes one MiB of default guest RAM when allocation succeeds, resets execution/fault state, installs the syscall callback, clears IL locals/arguments and TLS, and chooses the initial bump-heap cursor.

The image entry point has already been checked by clvm_parse when a normal CLV file is loaded.

Direct host tests that construct ClvmImage manually are responsible for providing coherent code_size and entry fields.

## State machine

The public VM states are:

    READY
      |
      v
    RUNNING
     / |  \
    /  |   \
WAITING HALTED FAULTED
   |
   +---- wake ----> READY

clvm_step treats terminal and waiting states specially before execution begins.

- WAITING returns CLVM_STEP_YIELD.
- HALTED returns CLVM_STEP_HALT.
- FAULTED returns CLVM_STEP_FAULT.
- READY or RUNNING enters RUNNING and begins the loop.

At normal budget exhaustion, state is reset to READY and CLVM_STEP_SLICE is returned.

A YIELD therefore does not necessarily mean the VM is WAITING. A process-preemption yield may occur while state remains RUNNING.

The caller must inspect both result and state when that distinction matters.

## Step results

The scheduler-facing results are:

| Result | Meaning |
|---|---|
| CLVM_STEP_SLICE | budget exhausted without halt/fault/wait |
| CLVM_STEP_YIELD | execution should return to the scheduler |
| CLVM_STEP_HALT | HALT reached or VM already halted |
| CLVM_STEP_FAULT | terminal VM fault |

These are execution-engine outcomes, not source-language return values.

A ChrisC function returning normally does not by itself produce CLVM_STEP_HALT; generated program structure eventually reaches HALT at the program boundary.

## Decode loop

For each budget unit, clvm_step:

1. stores the current pc in op_pc;
2. fetches one opcode byte;
3. advances pc;
4. increments vm->executed;
5. performs a freestanding scheduling check;
6. dispatches the opcode in a switch;
7. fetches any immediate operand bytes required by that opcode;
8. mutates stack, memory, call state or VM state.

The fetch helper validates:

    pc <= code_size
    requested_count <= code_size - pc

and advances pc only after accepting the requested byte range.

The subtraction form avoids overflow in pc + count validation.

## Budget semantics

The budget is a maximum loop-iteration count, not a wall-clock duration.

One simple NOP and one expensive SYS each consume one interpreter budget unit even though their host cost can be very different.

This keeps the VM loop simple but means the scheduler's instruction budget is only an approximate fairness mechanism.

ChrisOS chooses different budgets in lang_tick:

    LANG_VM_BUDGET_UI   = 4,000,000
    LANG_VM_BUDGET_GAME = 20,000,000

UI programs can receive up to eight slices in one lang_tick pass, subject to time and process-slice checks.

Game-sized programs receive one larger slice.

Debugger single-step uses budget 1.

## Scheduler integration

lang_tick walks up to LANG_VM_SLOTS application slots in round-robin order.

For a process-backed CLVM it switches into the slot's process address space before executing the VM and restores PROC_KERNEL afterward.

When JIT is enabled and debugging is off, lang_tick invokes the compiled JIT function.

Otherwise it calls clvm_step.

This makes the interpreter the primary debug engine even on systems where normal execution prefers JIT.

A HALT or FAULT causes lang_tick to tear down the slot.

Faults are logged with pc, source line, sp, fault ID, fault_pc, csp, recent return addresses and top-of-stack value.

## Operand stack

The operand stack contains 256 signed 64-bit slots.

clvm_vm_push64 fails when:

    sp == CLVM_STACK_MAX

clvm_vm_pop64 fails when:

    sp == 0

Most opcodes translate those helper failures into explicit stack faults.

Examples:

- ADD requires two values and pushes one;
- NEG requires one and pushes one;
- LOAD consumes an address and pushes a value;
- STORE consumes address and value;
- conditional branches consume one condition;
- SYS consumes the service ID after source-level arguments have already been pushed.

The stack model is intentionally untyped at runtime.

Integer values, addresses, float bit patterns and service handles can occupy the same int64_t slot.

Type meaning comes from generated bytecode and the operation consuming the value.

## DROP is deliberately permissive

CL_OP_DROP behaves differently from most consuming operations.

Its implementation is:

    if (sp > 0)
        sp--

An empty DROP is therefore a no-op, not CLVM_FAULT_STACK_UNDERFLOW.

The native JIT implements the same policy.

This is part of current VM semantics and should not be “fixed” in only one engine without an ABI decision.

## 64-bit integer semantics

The main interpreter arithmetic path operates on int64_t values.

Signed and unsigned division/comparison families are separate.

UDIV, UMOD and unsigned comparisons reinterpret operands as uint64_t.

Shift counts are masked with:

    count & 63

SHR performs logical right shift by converting the left operand to uint64_t.

SAR uses signed right shift.

Division by zero produces CLVM_FAULT_DIV_ZERO.

Signed division of INT64_MIN by -1 produces CLVM_FAULT_DIV_OVERFLOW.

## Host-C overflow dependency

ADD, SUB, MUL, NEG and SHL are currently written using signed int64_t C expressions.

Examples include:

    a = a + b
    a = a * b
    -a
    a << (b & 63)

In ISO C, signed overflow and some signed left-shift cases are undefined behavior.

The intended VM behavior is effectively two's-complement machine arithmetic, and the native x86-64 JIT naturally wraps for many of these operations, but the interpreter source does not explicitly express wrapping through uint64_t.

This is a portability and interpreter/JIT-equivalence risk.

A stronger implementation should define wrapping semantics explicitly with unsigned arithmetic and convert back, or define checked overflow as a VM fault.

## Floating-point representation

Float opcodes use 32-bit IEEE-style bit patterns stored in 64-bit VM slots.

FPUSH pushes a 32-bit payload.

FLOAD/FSTORE transfer four bytes.

FADD, FSUB, FMUL and FDIV reinterpret low 32 bits as float, perform the native C float operation and push the resulting bit pattern.

FEQ, FLT and FLE push integer booleans.

ITOF converts an integer VM value to float.

FTOI converts float to an integer value.

FDIV explicitly faults on a zero-valued float divisor.

The interpreter does not establish a VM-specific floating rounding mode or NaN canonicalization policy.

Out-of-range float-to-integer conversion also inherits host C conversion behavior.

For deterministic cross-architecture execution, those edge semantics need stronger specification.

## Guest-memory operations

The interpreter itself enforces bounds for LOAD, STORE, LOAD64, STORE64, LOADB, STOREB, FLOAD, FSTORE and object-field operations.

mem_ok rejects:

- null backing memory;
- negative guest offsets;
- offsets greater than mem_size;
- lengths exceeding mem_size - offset.

The complete memory/ownership model is covered in the CLVM memory chapter.

From the interpreter perspective, the important invariant is:

    no ordinary data-memory opcode computes vm->memory + guest_offset
    before proving the complete accessed range is valid

## Control flow

CLVM supports:

- 16-bit relative JMP/JZ/JNZ/CALL;
- 32-bit relative JMP32/JZ32/JNZ32/CALL32;
- indirect absolute CALLI;
- absolute-immediate CALLT;
- RET.

Relative branch displacement is applied to pc after the instruction's immediate has been fetched.

A CALL records that post-instruction pc as the return address before transferring control.

RET restores the most recent saved return pc.

The call stack can contain 64 return addresses.

Recursion deeper than that faults with CLVM_FAULT_CALL_OVERFLOW.

RET at csp == 0 faults with CLVM_FAULT_CALL_UNDERFLOW.

## Branch target validation

jump_rel16 and jump_rel32 verify only:

    0 <= target < code_size

CALLI applies the same range rule.

They do not verify that target is the beginning of a decoded instruction.

A hand-crafted or corrupted bytecode stream can branch into the middle of a PUSH immediate or another multi-byte operand and have that byte interpreted as an opcode.

There is no whole-image control-flow verifier before execution.

This is a significant distinction from bytecode VMs that validate instruction boundaries and stack effects ahead of time.

The CLV file parser validates image framing, size, entry and checksum, not the internal control-flow graph.

## CALLT validation gap

CL_OP_CALLT fetches a 32-bit absolute target, checks only call-stack capacity, records the return pc, and assigns:

    vm->pc = read_u32(arg)

It does not validate that the target is below code_size.

An out-of-range CALLT therefore does not immediately produce CLVM_FAULT_BAD_JUMP.

The next opcode fetch fails and normally becomes CLVM_FAULT_PC.

An in-range but mid-instruction CALLT target is also accepted.

This should be aligned with CALLI/relative-call validation or handled by a verifier.

## STLOC diagnostic mismatch

LDARG and LDLOC separately check immediate availability and slot range.

STLOC currently combines immediate fetch and stack pop:

    if (!fetch(vm, 1, &arg) || !clvm_vm_pop64(vm, &a))
        return fail(... CLVM_FAULT_TRUNCATED ...)

If the bytecode contains a valid STLOC immediate but the operand stack is empty, the real condition is stack underflow, but the interpreter reports CLVM_FAULT_TRUNCATED.

That is a diagnostic-classification bug.

The checks should be separated so missing operand bytes yield TRUNCATED and missing stack values yield STACK_UNDERFLOW.

## IL-style locals and arguments

CLVM contains a small second execution vocabulary used by IL-oriented code paths.

The VM provides:

    il_arg[16]
    il_loc[32]

LDARG takes a one-byte slot and accepts 0-15.

LDLOC and STLOC accept 0-31.

These arrays live inside ClvmVm, not guest memory.

They are independent of the operand stack and are not dynamically allocated per source-language frame.

This is intentionally lightweight and should not be confused with a general unlimited activation-record system.

## Object-oriented helper opcodes

NEWOBJ allocates guest memory using clvm_guest_malloc.

A zero requested size becomes 16 bytes.

The resulting guest offset is pushed on the operand stack.

LDFLD/STFLD use a four-byte immediate field offset and access eight bytes at:

    object_base + field_offset

CALLT transfers to an absolute four-byte target.

LDSTR pushes a four-byte immediate as a pointer-like guest value; it does not itself validate or read the referenced memory.

These instructions support IL/object lowering without turning the VM into a fully managed runtime.

## Integer-overflow risk in field addressing

LDFLD and STFLD compute:

    a + (int64_t)off

before passing the result to mem_ok.

If a is near INT64_MAX, that signed addition can overflow before the bounds checker receives the address.

Normal compiler-generated guest pointers are small offsets, but adversarial bytecode can place arbitrary int64 values on the stack.

This is another place where range arithmetic should be written in overflow-safe unsigned form before the VM is treated as hardened against malicious bytecode.

## SYS boundary

SYS pops a 64-bit value and truncates it to int32_t service ID.

If no callback exists or the callback returns nonzero, the VM faults with CLVM_FAULT_BAD_SYS at the SYS opcode pc.

On successful dispatch the interpreter sets:

    vm->safepoint = 1

and then observes any state transition made by the service:

- WAITING -> CLVM_STEP_YIELD;
- HALTED -> CLVM_STEP_HALT;
- FAULTED -> CLVM_STEP_FAULT.

Argument marshalling and blocking-service issues are documented in the syscall chapter.

## Explicit safepoints

CL_OP_SAFEPOINT has stronger behavior than simply setting the safepoint flag.

The interpreter:

1. sets safepoint = 1;
2. invokes on_safepoint when non-null;
3. clears safepoint = 0;
4. in freestanding builds, checks whether a process slice is due.

lang_pipeline installs lang_safepoint, which calls gc_poll.

ChrisC emits SAFEPOINT at function entry.

Therefore ordinary generated function calls soon arrive at an explicit GC polling point.

The x86-64 JIT also emits a native safepoint callback sequence for CL_OP_SAFEPOINT.

## Safepoint flag on calls

CALL, CALL32, CALLI, NEWOBJ and successful SYS set safepoint = 1 in the interpreter, but they do not invoke on_safepoint directly and do not clear the flag in those cases.

Generated ChrisC functions begin with an explicit SAFEPOINT, which then executes the callback and clears the flag.

For manually assembled control flow that does not lead to a SAFEPOINT, safepoint can remain set longer than the field name might imply.

The flag is therefore not, by itself, a complete statement that the callback just ran.

## Instruction counter

vm->executed increments after the opcode byte is fetched and before opcode semantics execute.

It is cumulative across slices.

In freestanding builds, every 8192 fetched instructions the interpreter checks proc_slice_due.

The current location of that check creates an important correctness issue.

## Preemption-before-execution bug

The sequence is currently:

    fetch opcode -> pc advances
    executed++
    if ((executed & 8191) == 0 && proc_slice_due())
        return YIELD
    execute opcode

If proc_slice_due is true at that checkpoint, clvm_step returns before executing the already-fetched opcode.

Because pc has already advanced, the next call resumes at the following instruction.

The fetched instruction is skipped.

This is a concrete interpreter correctness bug under process preemption.

The scheduling check must occur before consuming the opcode, after executing it, or restore pc = op_pc before returning.

A regression test should force proc_slice_due exactly at an 8192-instruction boundary and verify that no instruction is lost.

## READY versus RUNNING on preemption

The early preemption return also bypasses the normal end-of-budget code:

    vm->state = CLVM_READY

so the VM can return CLVM_STEP_YIELD while state remains CLVM_RUNNING.

lang_tick can call clvm_step again because RUNNING is accepted as an executable state, so this is not immediately fatal.

However, result/state invariants are less clean than the public enum suggests.

A scheduler contract should explicitly define whether YIELD due to preemption leaves RUNNING or transitions back to READY.

## Wait and wake

clvm_vm_wait stores a wake tick and sets state WAITING.

clvm_vm_wake performs a wrap-safe 32-bit signed-difference test:

    (int32_t)(now - wake_tick) >= 0

and restores READY when the target time is reached.

Timer waiting therefore does not busy-loop inside clvm_step.

lang_tick calls clvm_vm_wake before running each slot.

Other blocking syscall families use additional process/runtime state and are covered in the syscall chapter.

## HALT

HALT is terminal for the VM instance.

The interpreter sets:

    state = CLVM_HALTED

and returns CLVM_STEP_HALT immediately.

Calling clvm_step again on the same instance returns HALT without fetching bytecode.

lang_tick treats HALT as application termination and tears the slot down.

There is no separate source-level process exit code stored by the interpreter.

## Fault model

fail records:

    vm->fault
    vm->fault_pc
    vm->state = CLVM_FAULTED

and returns CLVM_STEP_FAULT.

The defined fault classes are:

| Fault | Trigger |
|---|---|
| PC | cannot fetch next opcode / invalid execution pc |
| OPCODE | unknown opcode or invalid IL slot encoding |
| TRUNCATED | immediate operand bytes missing |
| STACK_UNDERFLOW | required operand missing |
| STACK_OVERFLOW | operand stack full |
| CALL_UNDERFLOW | RET without caller |
| CALL_OVERFLOW | call stack full |
| DIV_ZERO | integer or float divide-by-zero path |
| DIV_OVERFLOW | signed INT64_MIN / -1 |
| BAD_ADDRESS | guest memory access rejected |
| BAD_JUMP | checked branch/call target outside code |
| BAD_SYS | syscall callback absent/rejected |

Fault state is sticky: subsequent clvm_step calls return CLVM_STEP_FAULT without executing more bytecode.

## Null-VM failure-path bug

clvm_step begins with:

    if (vm == NULL || vm->code == NULL)
        return fail(vm, CLVM_FAULT_PC, 0)

But fail immediately writes through vm.

Therefore the vm == NULL branch does not safely return a VM fault; it dereferences a null pointer.

The code-null case is valid because vm exists.

The null-VM case is a host-side API bug and should return CLVM_STEP_FAULT without dereferencing, or reject null before calling fail.

Normal ChrisOS execution always passes a real ClvmVm, but the public C API should still have coherent null behavior.

## PRINT diagnostics

PRINT pops one VM value and records it in an eight-entry rolling ring.

Once full, older entries shift left and the newest value occupies index 7.

This is diagnostic state rather than user-visible console I/O.

Normal text output goes through service calls such as fwrite.

The JIT helper path for PRINT does not maintain the same print ring in jit_runtime.c, so PRINT diagnostics should not currently be assumed identical between all execution modes.

## Debugger interaction

Debug mode intentionally uses the interpreter.

A single-instruction step calls:

    clvm_step(vm, 1)

Line stepping repeatedly executes budget-1 slices until source-line/depth criteria are met or HALT/FAULT occurs.

The source map maintained by lang_pipeline maps bytecode PCs back to source file/line data.

The debugger can inspect:

- pc;
- stack values;
- call depth/return PCs;
- guest memory;
- fault state;
- recent syscall trace.

This is one reason preserving precise fault_pc semantics matters.

## Interpreter/JIT contract

The interpreter is not just a fallback for performance failure.

It is a semantic reference used in differential and focused tests.

The JIT directly emits native x86-64 for many opcodes and routes others through runtime helpers.

Both engines share the ClvmVm layout and must agree on:

- stack effects;
- branch/call targets;
- memory width and bounds;
- state transitions;
- fault categories;
- syscall behavior;
- safepoint callbacks;
- HALT/YIELD outcomes.

The upcoming JIT chapter documents native lowering details.

For the interpreter, the important rule is that any behavior relied upon by compiler-generated CLV should have an equivalent JIT behavior or an explicit unsupported boundary.

## Performance characteristics

The switch interpreter has O(1) dispatch work per simple opcode.

Memory operations are O(1) for their fixed 1/4/8-byte widths.

CALL/RET are O(1).

Relative branch validation is O(1).

PRINT is O(1) with a tiny fixed ring shift.

SYS cost is dominated by the called subsystem.

The interpreter does no decode cache or predecoded instruction table; immediates are decoded from bytecode every execution.

This makes it simple and observable but slower than JIT for hot loops.

## Cache and locality

The execution hot set consists primarily of:

- sequential code bytes;
- ClvmVm stack/call arrays;
- a small number of VM scalar fields.

Straight-line bytecode has good instruction-data locality.

Frequent guest LOAD/STORE behavior depends on application access patterns.

Because operand stack and call stack are fixed inside ClvmVm, their addresses remain stable and compact.

The switch dispatcher itself may incur branch-prediction cost across mixed opcode streams.

## Concurrency and reentrancy

clvm_step operates on one ClvmVm and does not use process-global decode state.

Separate VMs can therefore have separate operand stacks, call stacks and PCs.

However, callbacks reached through SYS and on_safepoint can access global kernel state.

A process-backed vm->memory pointer is valid in the intended address-space context, so lang_tick switches to the process before execution.

The interpreter cannot be treated as independent from scheduler/address-space discipline merely because its local decode loop is per-VM.

## Security boundary

The interpreter provides several useful containment properties:

- code reads are bounded by code_size;
- data-memory operations are bounded by mem_size;
- operand and call stacks have fixed limits;
- syscall entry is explicit;
- faults terminate further VM execution.

It is not yet a hardened bytecode sandbox.

Current gaps include:

- no instruction-boundary verifier;
- no pre-execution stack-effect verification;
- unchecked CALLT target;
- signed-overflow-sensitive interpreter arithmetic;
- overflow-sensitive field-address addition;
- null-VM host API bug;
- preemption path capable of skipping a fetched instruction;
- service-level issues documented in the syscall/memory chapters.

Security claims should therefore be scoped to the checks that actually exist.

## Validation evidence

tools/test_editor_vi.c exercises interpreter fallthrough behavior and verifies recursive call-stack overflow produces CLVM_FAULT_CALL_OVERFLOW. It also compares the same overflow condition with the JIT.

tools/test_jit_vm.c compiles a loop containing wait, runs interpreter and JIT paths, wakes yielded VMs, and compares resulting VM state.

tools/test_chrisc_fn.c exercises generated function calls, integer results and float arguments/results through the interpreter.

tools/test_chrisc_float.c validates floating multiplication and guest-memory result bits.

tools/test_store64_copy.c executes an explicit LOAD64/STORE64 sequence in both interpreter and JIT modes against a 32 MiB backing.

tools/test_doom_jit_diff.c performs step-oriented interpreter/JIT comparison over Doom-related bytecode paths.

The broader ChrisC test corpus exercises arrays, structures, pointer widths, calls, branches and generated code.

Dedicated adversarial tests are still needed for the specific gaps identified here.

## Missing focused tests

The inspected suite should be extended with tests for:

- clvm_step(NULL, budget);
- truncated immediate versus stack-underflow classification for STLOC;
- CALLT outside code_size;
- jumps into immediate bytes;
- exact 8192-boundary preemption with proc_slice_due asserted;
- signed 64-bit wrap semantics;
- field-address addition near INT64_MAX;
- explicit SAFEPOINT callback count;
- DROP on empty stack as a compatibility rule;
- PRINT-ring parity between interpreter and JIT if that diagnostic is intended to be shared.

## Current limitations

At the documented revision:

- the interpreter decodes bytecode on every execution rather than using a verified predecode;
- branch targets are range-checked but not instruction-boundary checked;
- CALLT does not range-check its absolute target;
- STLOC can report TRUNCATED for an operand-stack underflow;
- clvm_step(NULL, ...) follows a null-dereferencing failure path;
- the freestanding 8192-instruction preemption check can skip an already-fetched opcode;
- preemption YIELD can leave state RUNNING;
- signed arithmetic/left-shift semantics rely on host C behavior in overflow cases;
- object field-address addition can overflow before mem_ok;
- float edge semantics are not fully normalized across host architectures;
- CALL/NEWOBJ/SYS safepoint flag behavior is not equivalent to executing CL_OP_SAFEPOINT;
- PRINT diagnostic behavior is not clearly equivalent in JIT helper execution;
- there is no whole-program bytecode verifier for stack depth, types or control-flow targets.

## Roadmap boundary

A stronger interpreter architecture could add:

- a verifier that decodes every instruction once and builds an instruction-start bitmap;
- verified control-flow targets and stack effects;
- explicit wraparound integer helpers;
- overflow-safe address arithmetic;
- a corrected post-instruction preemption point;
- precise pending-syscall continuations;
- unified safepoint semantics;
- generated opcode metadata shared by assembler, interpreter, JIT and docs;
- exhaustive interpreter/JIT differential tests for all opcodes and faults;
- optional decode caching or direct-threaded dispatch for non-JIT builds.

Those are future changes until implemented and tested.

## Source map and revision

compiler/clvm/clvm_vm.h defines ClvmVm, state/fault/result enums and stack capacities.

compiler/clvm/clvm_vm.c implements initialization, stack helpers, state transitions, bounds checks and clvm_step.

compiler/clvm/clvm.h defines opcode numbers and CLV image metadata.

compiler/chrisc/chrisc.c emits CLVM instructions and inserts function-entry SAFEPOINT operations.

compiler/lang_pipeline.c integrates interpreter execution with process switching, debugging, budgets, safepoints and slot teardown.

compiler/jit/jit_compile.c and compiler/jit/jit_runtime.c provide the alternate JIT execution engine used for equivalence comparison.

All current-behavior claims in this chapter were reconciled against ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.
