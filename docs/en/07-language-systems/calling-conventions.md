---
id: calling-conventions
lang: en
type: technical-chapter
volume: 07-language-systems
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/kcc/kcc.c
  - compiler/chrisc/chrisc.c
  - compiler/clvm/clvm_vm.h
  - compiler/clvm/clvm_vm.c
  - compiler/il/il.h
  - compiler/il/il.c
  - compiler/jit/jit_compile.c
  - compiler/jit/jit_runtime.c
  - tools/test_kcc.c
  - tools/test_chrisc_c17.c
  - tools/test_chrisc_ptr_float.c
  - tools/test_editor_vi.c
symbols:
  - parse_args
  - arg_reg
  - parse_params
  - alloc_slot
  - temp_slot
  - epilogue
  - emit_return_address
  - FuncDef
  - gen_call
  - emit_call
  - chrisc_emit
  - ClvmVm
  - CLVM_STACK_MAX
  - CLVM_CALL_MAX
  - CL_OP_CALL
  - CL_OP_CALL32
  - CL_OP_CALLI
  - CL_OP_CALLT
  - CL_OP_RET
  - IL_ARG
depends_on:
  - intermediate-representation
  - native-codegen
related:
  - chrisc-clvm
  - clvm-bytecode
  - kcc
  - jit
---

# Calling conventions and stack frames

## Scope

A calling convention defines the contract between caller and callee: where arguments are placed, where results are returned, how the return address is preserved, which machine or virtual registers belong to whom, how stack alignment is maintained and what constitutes a function activation.

ChrisOS currently contains two materially different calling models.

The native KCC path uses an x86-64 register-and-stack convention whose integer and pointer argument order follows the familiar System V AMD64 register sequence.

The ChrisC/CLVM path is not a hardware ABI. It uses a VM operand stack, a separate return-address stack and compiler-managed guest-memory scratch areas for ordinary ChrisC arguments.

These contracts must not be described as interchangeable.

![Calling conventions in ChrisOS](../../assets/diagrams/calling-conventions-en.svg)

## Native KCC calling model

The KCC caller evaluates each argument expression and stores the resulting value into a temporary frame slot. After all arguments have been evaluated, it reloads them into call locations.

The first six argument positions use:

| Position | Register |
|---:|---|
| 0 | RDI |
| 1 | RSI |
| 2 | RDX |
| 3 | RCX |
| 4 | R8 |
| 5 | R9 |

This register order matches the integer/pointer argument order of the System V AMD64 ABI.

That similarity does not make the current KCC implementation a complete System V C ABI implementation. KCC currently supports a restricted C profile, does not implement the full floating-point argument classification rules, does not implement aggregate classification equivalent to a production ABI, and generates a deliberately simple fixed-frame backend.

The correct description is therefore: **SysV-like integer/pointer calling convention for the supported KCC subset**.

## Argument evaluation order

parse_args processes source arguments from left to right.

For every argument it:

1. parses the expression;
2. materializes the value;
3. stores RAX into a temporary slot;
4. continues to the next argument.

Only after the complete list has been parsed are the saved values moved into argument registers or stack slots.

This gives KCC a concrete left-to-right evaluation behavior at the current revision.

That behavior is an implementation fact, not a portable C-language guarantee that source should rely on across arbitrary compilers.

The temporary staging also prevents evaluation of later expressions from destroying values already computed in RAX.

## Stack arguments

Arguments after the first six are written by the caller into temporary outgoing stack space.

If there are n extra arguments:

    extra = n - 6
    slots = extra rounded up to an even count
    bytes = slots * 8

KCC subtracts that byte count from RSP, writes argument 6 at [rsp], argument 7 at [rsp+8], and so on, performs the call, then adds the same byte count back to RSP.

Rounding the outgoing area to an even number of eight-byte slots preserves 16-byte stack alignment when the surrounding generated frame is aligned.

The padding slot, when needed, is alignment space rather than an argument.

## Stack alignment

A generated function uses:

    push rbp
    mov rbp, rsp
    sub rsp, 2048

For a call entered with the expected x86-64 call alignment, CALL has already pushed an eight-byte return address. push rbp consumes another eight bytes, returning RSP to a 16-byte boundary. The 2048-byte subtraction preserves that alignment because 2048 is divisible by 16.

Outgoing stack-argument allocation is also a multiple of 16.

This gives the current generated call path a consistent alignment invariant for calls produced by KCC.

The project should still avoid claiming complete external ABI compatibility solely from this property; alignment is only one part of an ABI.

## Native frame layout

The current KCC stack frame is intentionally simple.

Conceptually:

    higher addresses

    [rbp + 24]   stack argument 7
    [rbp + 16]   stack argument 6
    [rbp +  8]   return address
    [rbp +  0]   saved caller RBP
    [rbp -  8]   local / saved register argument
    [rbp - 16]   local
       ...
    temporary spill region
       ...
    current RSP after fixed allocation

    lower addresses

alloc_slot assigns ordinary local slots at negative offsets. Every slot occupies at least eight bytes and is rounded to eight-byte alignment.

The ordinary local allocator is bounded by 1536 bytes.

Temporary expression slots use a separate negative-offset region beginning around -1600 and are reset at statement boundaries through g_ntemp.

The function reserves 2048 bytes, so both regions fit inside the generated frame model.

## Incoming register parameters

parse_params assigns the first six formal parameters ordinary local frame slots.

At function entry, KCC emits a move from the incoming argument register into RAX and then stores RAX into the parameter's frame slot.

Therefore later references to register parameters do not normally keep reading RDI, RSI or the other incoming registers. They read ordinary local memory.

This is a deliberate simplification.

It avoids needing to keep formal parameters live in specific machine registers across the function, but it introduces stores at entry and reloads later.

## Incoming stack parameters

Formal parameters after the sixth are not copied into negative local slots.

Their Sym.frame value is assigned:

    16 + (index - 6) * 8

which makes parameter 6 resolve at [rbp+16].

The layout follows directly from:

- saved RBP at [rbp];
- hardware return address at [rbp+8];
- first caller stack argument at [rbp+16].

The callee does not remove these arguments. The caller owns the outgoing area and restores RSP after the call.

## Return address

For native x86-64 calls, the processor's CALL instruction pushes the return instruction pointer.

KCC preserves that return address by keeping the conventional frame layout.

The supported builtin that exposes the current function's return address loads:

    [rbp + 8]

which confirms the generated frame model.

RET consumes the hardware return address after the epilogue restores RSP and RBP.

## Return values

Expression returns leave the computed value in RAX.

The return statement then emits the common epilogue:

    mov rsp, rbp
    pop rbp
    ret

The caller consequently receives supported scalar/pointer results in RAX.

A void return emits the epilogue without defining a language-level result value.

Native floating-point return conventions are not a supported general KCC contract at the documented revision because floating-point native value operations remain outside the subset.

## Direct and indirect native calls

A direct function call emits:

    call symbol

A function-pointer call evaluates the target, saves it, reloads it into RAX after preparing arguments, then emits:

    call rax

The argument locations are the same for both forms.

The difference is only how the control-transfer target is obtained.

This is important for ChrisAsm and ChrisLd: direct symbolic calls can become object relocations, while register-indirect calls have no link-time call-target relocation.

## Register ownership

Current KCC-generated expression code primarily uses volatile/caller-scratch registers such as RAX, RCX and RDX, plus the argument registers.

RBP is explicitly preserved as the frame pointer.

The generator does not currently operate a general register allocator that assigns long-lived values to RBX or R12-R15 and then emits a systematic callee-save set.

As a result, the current compiler avoids much of the complexity of callee-saved register management by simply not exploiting the broader register file aggressively.

Inline assembly must be treated carefully because it can escape assumptions made by the syntax-directed generator.

## KCC parameter and argument limits

KCC defines KCC_PARAM_MAX as 16.

Both parse_args and parse_params enforce this finite model.

This bounds temporary arrays and simplifies the compiler, but it is a compiler implementation limit rather than an architectural x86-64 limit.

The supported calling convention should therefore be understood together with the supported language subset.

## CLVM has two stacks, not a hardware call frame

ClvmVm contains:

    int64_t stack[CLVM_STACK_MAX]
    uint16_t sp

for operand values, and:

    uint32_t calls[CLVM_CALL_MAX]
    uint16_t csp

for return addresses.

At the current revision:

    CLVM_STACK_MAX = 256
    CLVM_CALL_MAX  = 64

The return stack is separate from the operand stack.

A function call does not push a hardware-style frame containing saved base pointer, locals and arguments.

CALL, CALL32 and CALLI only manipulate control-flow return state. Argument and local storage are separate concerns.

## CLVM direct calls

For CL_OP_CALL and CL_OP_CALL32, the interpreter:

1. decodes the relative target;
2. checks that call-stack capacity remains;
3. stores the current post-instruction PC into calls[csp];
4. increments csp;
5. marks a safepoint;
6. jumps to the target.

The saved value is only the return PC.

There is no operand-stack pointer snapshot and no local-variable frame record.

RET checks csp for underflow, decrements it and restores PC from calls[].

A call depth beyond 64 faults with CLVM_FAULT_CALL_OVERFLOW.

RET with an empty call stack faults with CLVM_FAULT_CALL_UNDERFLOW.

## CLVM indirect calls

CL_OP_CALLI takes its target from the operand stack.

The interpreter pops a 64-bit value, verifies that the target is within the bytecode image, saves the return PC in calls[], and assigns the target to vm->pc.

This provides function-pointer-style control transfer for ChrisC-generated code.

The target is an absolute bytecode offset, not a native host address.

That range check is an important VM integrity boundary.

## ChrisC argument transport

Ordinary ChrisC function arguments do not currently use CL_OP_LDARG.

Instead, the compiler reserves a guest-memory scratch area.

During chrisc_emit:

    icall_base = align8(mem_next)
    size       = FUNC_ARG_MAX * 8

FUNC_ARG_MAX is 16, so the ordinary call scratch area contains sixteen eight-byte slots.

A separate varargs region reserves another 32 eight-byte entries.

At a direct call site, ChrisC evaluates each argument and stores it into:

    icall_base + index * 8

using the appropriate store path.

For ordinary integer and pointer arguments this is a 64-bit slot.

By-value float scalars use the float store path.

Pointer values are always treated as pointer-width values even when they point to floats; this distinction is covered by the pointer/float regression tests.

## ChrisC callee entry

Each FuncDef records the guest-memory address assigned to every formal parameter.

When the compiler emits the start of a function, it first emits a SAFEPOINT and then copies each incoming value from the shared icall scratch slot to the formal parameter's fixed guest-memory address.

Conceptually:

    scratch arg 0 -> function parameter storage 0
    scratch arg 1 -> function parameter storage 1
    ...

The copy width depends on the recorded parameter width and float classification.

After those copies, the function body reads its ordinary parameter symbols like other guest-memory variables.

There is no CLVM activation-record allocation step corresponding to a native stack frame.

## ChrisC return-value convention

ChrisC functions return values on the VM operand stack.

A non-main return expression emits the expression so that one value remains on the operand stack, then emits RET.

A void return still pushes a zero before RET.

The compiler deliberately maintains the invariant that a normal function call leaves exactly one operand-stack value, even for void callees.

Callers that use a void function as a statement can then DROP that placeholder under the normal expression-statement rules.

main is special: its return expression is dropped and execution terminates with HALT rather than RET.

## Shared scratch areas and activation semantics

The current ChrisC convention does not create a private argument area per activation.

icall_base is one compiler-reserved scratch region shared by generated calls within the VM image.

The formal parameter storage associated with a function is also allocated in guest memory when the source is compiled, not dynamically allocated per invocation.

The CLVM return stack therefore provides nested **control-flow** activations, but it does not automatically provide independent per-call argument/local storage.

This distinction is critical.

General recursive or re-entrant execution requires per-activation storage for values that must survive a nested invocation. The current fixed-storage design cannot be described as a conventional recursive stack-frame model.

Similarly, when nested calls occur while constructing a later argument, the same shared incoming scratch area is reused. The compiler has protections for its AST argument-index bookkeeping, but the runtime call scratch is still a shared memory region.

Code that depends on arbitrary re-entrant C activation semantics should not be assumed safe without a dedicated regression test demonstrating the required case.

## Varargs in ChrisC

ChrisC reserves va_base immediately after the ordinary call scratch area.

Extra arguments to a variadic function are stored there in eight-byte slots.

va_start initializes a va_list-like variable to that base.

va_arg advances through that memory according to the compiler's supported representation.

This is a project-specific VM calling mechanism.

It is not the System V AMD64 varargs register-save-area ABI.

## CLVM IL argument/local opcodes

The CLVM instruction set also contains:

    LDARG
    LDLOC
    STLOC
    CALLT

ClvmVm has fixed arrays:

    il_arg[16]
    il_loc[32]

These belong to the small IL/CLA-oriented execution facilities documented with compiler/il and CLA.

They are not the transport used by ordinary ChrisC calls described above.

They also are not pushed and restored as independent arrays on every CALLT in the current VM state structure.

Documentation must therefore avoid presenting LDARG/LDLOC as if ChrisC were using a conventional managed per-method frame.

## Interpreter/JIT equivalence

The CLVM JIT implements the same call-stack state as the interpreter.

For CALL/CALL32 it checks csp, stores the next bytecode PC into the VM calls array and dispatches to the target.

CALLI pops the bytecode target, validates it against the image range, saves the return address and dispatches.

RET decrements csp and reloads vm->pc from calls[].

The generated host machine code is only an acceleration of the VM calling semantics. It does not replace them with the KCC native ABI.

This distinction is required for interpreter/JIT equivalence.

## Safepoints

CLVM call instructions mark safepoint state.

This allows runtime services such as GC or scheduler-related work to observe well-defined execution boundaries.

SAFEPOINT opcodes can also appear explicitly at function entries in ChrisC-generated code.

A VM call therefore participates in runtime coordination in a way that a simple native CALL instruction does not automatically provide.

## Fault containment

Calling-convention failures are handled differently in the two execution paths.

Native KCC code relies on x86-64 architectural call/return mechanics and on correct generated stack discipline. A malformed native stack can corrupt control flow directly.

CLVM validates call-stack overflow, call-stack underflow and indirect call target range and converts failures into ClvmFault state.

The VM value stack independently detects operand underflow and overflow.

This split reflects the broader protection difference between native execution and managed VM execution.

## Performance trade-offs

KCC's convention is inexpensive at the actual call boundary because the first six supported arguments use registers and RET uses hardware state.

Its simple backend, however, frequently spills values and immediately copies incoming register parameters into memory.

ChrisC/CLVM avoids host ABI dependence and keeps the virtual ISA simple, but argument passing through guest-memory scratch introduces extra VM loads/stores.

The CLVM return-address stack is cache-friendly and bounded, but fixed capacity limits maximum nested call depth.

A future per-activation CLVM frame would improve re-entrancy at the cost of more runtime state and frame management.

## Validation evidence

tools/test_kcc.c exercises function definitions, direct calls, pointer behavior and generated native assembly.

tools/test_chrisc_c17.c exercises ordinary ChrisC functions and language constructs.

tools/test_chrisc_ptr_float.c specifically protects the rule that a float pointer remains a 64-bit pointer when passed as an argument rather than being truncated through the scalar-float path.

tools/test_editor_vi.c contains interpreter/JIT regression coverage for CLVM call-stack overflow, validating that both engines fault consistently at the call-depth bound.

These tests support the contracts described here, but they should not be interpreted as proof of full System V ABI compatibility or unrestricted recursive ChrisC semantics.

## Current limitations

At the documented revision:

- KCC implements a focused SysV-like integer/pointer convention rather than the complete AMD64 ABI;
- KCC supports at most 16 source-level parameters/arguments in the current compiler arrays;
- native floating-point calling rules are not a general supported contract;
- KCC reserves a fixed 2048-byte frame instead of computing exact frame size;
- KCC does not perform general register allocation or systematic use of all callee-saved registers;
- ChrisC passes ordinary arguments through a shared guest-memory call scratch region;
- ChrisC formal/local storage is not represented as a private runtime frame per invocation;
- CLVM calls preserve return PCs but not complete activation records;
- CLVM return depth is bounded to 64;
- the CLVM operand stack is bounded to 256 values;
- IL argument/local arrays are fixed VM state, not a full per-call managed frame stack;
- native and CLVM calling conventions are separate contracts.

## Roadmap boundary

A future native backend could move from the current focused convention to a formally specified ABI profile with complete aggregate, floating-point, variadic and callee-save behavior.

A future CLVM calling model could introduce explicit activation records containing:

- return PC;
- operand-stack base;
- argument area;
- local area;
- varargs metadata;
- debug/source frame identity;
- GC roots;
- exception/unwind state.

That would make recursion and re-entrancy explicit rather than relying on fixed guest-memory locations.

Such changes would affect bytecode compatibility and interpreter/JIT behavior and therefore require versioned specification and differential tests.

They are future architecture until implemented.

## Source map and revision

The native calling path is implemented in compiler/kcc/kcc.c, especially parse_args, arg_reg, parse_params, alloc_slot, temp_slot, function prologue emission, epilogue and return handling.

The ChrisC argument and result contract is implemented in compiler/chrisc/chrisc.c through FuncDef, gen_call, emit_call, chrisc_emit and return generation.

The VM return-address and operand stacks are defined in compiler/clvm/clvm_vm.h and executed in compiler/clvm/clvm_vm.c.

The JIT's equivalent CALL/CALLI/RET state transitions are in compiler/jit/jit_compile.c.

All current-behavior claims in this chapter were reconciled against ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.
