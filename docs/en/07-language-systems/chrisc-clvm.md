---
id: chrisc-clvm
lang: en
type: technical-chapter
volume: 07-language-systems
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/chrisc/chrisc.c
  - compiler/clvm/clvm.h
  - compiler/clvm/clvm_format.c
  - compiler/clvm/clvm_vm.h
  - compiler/clvm/clvm_vm.c
  - compiler/lang_pipeline.h
  - compiler/lang_pipeline.c
  - compiler/jit/jit_compile.c
  - compiler/jit/jit_runtime.c
  - kernel/lang/clvm_sys.h
  - kernel/lang/clvm_sys.c
  - tools/test_chrisc_c17.c
  - tools/test_chrisc_fn.c
  - tools/test_chrisc_doom.c
  - tools/test_chrisc_ptr_float.c
  - tools/test_fuzz_clvm.c
  - tools/test_jit_vm.c
  - tools/test_jit_native.c
  - tools/test_editor_vi.c
symbols:
  - chrisc_compile_ex
  - chrisc_compile_files_ex
  - chrisc_emit
  - ClvmImage
  - clvm_parse
  - clvm_write_image
  - clvm_write_image_v2
  - ClvmVm
  - clvm_vm_init
  - clvm_vm_set_memory
  - clvm_step
  - clvm_guest_malloc
  - clvm_guest_realloc
  - lang_run_internal
  - lang_attach_slot_ram
  - lang_tick
  - lang_kill
  - clvm_sys_dispatch
  - clvm_sys_close_slot
  - clvm_threads_tick
depends_on:
  - compiler-pipeline
  - intermediate-representation
  - calling-conventions
related:
  - clvm-bytecode
  - clvm-memory
  - clvm-syscalls
  - clvm-interpreter
  - jit
  - debugger
  - gc-libraries
---

# ChrisC and the CLVM execution model

## Scope

ChrisC is a source language in the ChrisOS language subsystem. Its principal application path does not emit the same native ChrisO/ELF objects as KCC. ChrisC is compiled into CLVM bytecode, packaged in a CLV image and executed by a VM runtime that can interpret the bytecode or translate supported instructions through the CLVM JIT.

The complete active path is:

    ChrisC source
        ->
    preprocessing / parsing / semantic analysis
        ->
    ChrisC Node[] representation
        ->
    CLVM bytecode
        ->
    CLV image
        ->
    image validation
        ->
    LangSlot runtime instance
        ->
    interpreter or JIT
        ->
    CLVM syscall bridge
        ->
    kernel services and slot-owned resources

This architecture creates an execution contract that is independent of the KCC native calling convention and independent of raw x86-64 instruction encoding.

![ChrisC and CLVM execution path](../../assets/diagrams/chrisc-clvm-en.svg)

## Why a virtual-machine target exists

A VM target separates the language front end from the host processor ISA.

ChrisC only needs to lower to the CLVM instruction set. The runtime can then choose how to execute those instructions.

That design provides several useful properties:

- one compiler target for interpreted and JIT execution;
- explicit guest-memory addressing rather than direct source-level host pointers;
- a controlled syscall gateway;
- a compact instruction set that can be tested independently;
- source maps and debugger integration around bytecode PCs;
- an execution model usable by the in-system language environment;
- a path toward self-hosted compilation without requiring ChrisC to emit x86-64 directly.

The cost is that the VM itself becomes a compatibility boundary. Interpreter, JIT, bytecode format, compiler lowering and syscall bridge must agree on the same semantics.

## Compilation boundary

ChrisC compilation is implemented primarily in compiler/chrisc/chrisc.c.

The front end expands source, lexes, parses declarations and functions, performs semantic bookkeeping and constructs the fixed Node[] representation described in the compiler chapters.

chrisc_emit lowers the resulting program to a byte buffer of CLVM opcodes.

ChrisResult records, among other data:

- bytecode size;
- entry PC;
- diagnostics;
- source-map information.

The language pipeline calls chrisc_compile_files_ex for multi-file compilation and can install a yield callback with chrisc_set_yield. In the in-kernel compile path, that callback periodically invokes gc_poll and emits progress heartbeats so a long compilation is not treated as an opaque blocking operation.

## CLV image packaging

Raw bytecode is not normally the final file representation.

compiler/clvm/clvm_format.c wraps code in a CLV image containing a header and checksum.

Two versions are currently accepted.

Version 1 uses a 16-byte header and a 16-bit entry field.

Version 2 uses a 24-byte header, a 32-bit entry field and a 32-bit memory hint.

The common logical fields are:

| Field | Meaning |
|---|---|
| magic | ASCII CLVM |
| version | image format version |
| flags | known image flags |
| code size | bytecode payload length |
| checksum | FNV-1a over bytecode |
| entry | initial bytecode PC |
| memory hint | v2 requested guest-memory size |
| code | CLVM instruction bytes |

CLVM_MAX_CODE currently limits bytecode to 16 MiB.

The detailed byte layout and opcode encoding belong to the dedicated CLVM bytecode chapter; the architectural point here is that the runtime consumes a validated image rather than trusting an arbitrary byte buffer.

## Image selection during compilation

emit_game_clv chooses the image version according to generated program requirements.

A small program whose code and entry fit the v1 limits can use the v1 writer.

If code size or entry exceeds 65535, the pipeline selects v2.

The current pipeline also assigns a 32 MiB memory hint to sufficiently large generated images, specifically when code size exceeds 200000 bytes.

That heuristic exists for large workloads such as Doom-sized CLVM programs whose guest heap and static state exceed the one-megabyte default.

The resulting CLV file is written to the ChrisOS filesystem together with source-map output.

## Loader validation

clvm_parse performs structural validation before execution.

It rejects:

- null arguments;
- files smaller than the required header;
- incorrect magic;
- unsupported versions;
- unknown flags;
- zero, oversized or file-inconsistent code sizes;
- entry points outside the code payload;
- checksum mismatches.

The parser also verifies that the code payload occupies exactly the bytes following the selected header.

The checksum is FNV-1a over the bytecode.

This is corruption detection, not a cryptographic authenticity mechanism. A party capable of deliberately changing both code and checksum can create a different valid image.

Executable permission is handled separately by the runtime when ChrisFS permission metadata is available.

## Runtime ownership: LangSlot

A running application is represented by a LangSlot in compiler/lang_pipeline.c.

The slot owns or references the runtime state required to execute and display one language application, including:

- the loaded CLV file buffer;
- ClvmVm state;
- application name;
- VM memory and size;
- process association;
- graphics context and viewport state;
- JIT buffer and function pointer;
- debugger state and breakpoints;
- source-map tables;
- event queues;
- checkpoint data;
- task/window association;
- capability bits;
- teardown state.

This structure is the operational owner for the application lifecycle.

The VM is therefore not just an isolated ClvmVm object. Real desktop execution integrates the VM with graphics, process bookkeeping, debugger state, scheduling and slot-scoped kernel resources.

## Launch sequence

lang_run_internal performs the principal launch path.

The sequence is approximately:

1. detect an already running application with the same name and raise it instead of creating another instance;
2. find a free language slot;
3. allocate a file buffer if the slot does not yet have one;
4. read the CLV file;
5. enforce execute permission when the active filesystem supports that check;
6. parse and validate the CLV image;
7. create/prepare the application viewport;
8. initialize ClvmVm;
9. create an associated process record when possible;
10. attach guest RAM;
11. load the source map;
12. attempt JIT compilation when policy allows;
13. initialize debugger/runtime flags;
14. open the application window;
15. mark the slot active.

A failure in file loading, image parsing, viewport creation or guest-memory setup prevents the application from becoming a live slot.

## Initial VM state

clvm_vm_init initializes the execution machine from ClvmImage.

The initial state includes:

    pc  = image.entry
    sp  = 0
    csp = 0
    state = CLVM_READY

It installs the syscall callback and user context, clears fault state, clears IL local/argument arrays and initializes TLS entries.

The VM initially allocates the default CLVM_MEMORY_SIZE, currently 1 MiB.

In the desktop pipeline, that initial memory can then be replaced by the memory selected for the slot.

## Operand and return stacks

CLVM has a bounded operand stack:

    int64_t stack[256]

and a separate return-PC stack:

    uint32_t calls[64]

The operand stack carries arithmetic values, pointers represented as guest offsets, syscall arguments and function results.

The call stack carries bytecode return PCs.

This is not a native x86 stack frame.

As documented in the calling-conventions chapter, ordinary ChrisC formal parameters and locals are stored in guest memory, while CLVM calls preserve control-flow return state separately.

Stack overflow and underflow become VM faults rather than unchecked host-memory writes.

## Guest memory model

A CLVM address is interpreted as an offset into vm->memory.

The core VM checks ranges through mem_ok before load/store operations.

The check requires:

- a valid memory pointer;
- a nonnegative address;
- address not beyond mem_size;
- requested length no greater than the remaining range.

The syscall bridge uses equivalent explicit checks through helpers such as vm_bytes, vm_cstr, vm_copy_in and vm_copy_out.

This is a central invariant: guest offsets must be validated before becoming host pointers.

The VM memory model is covered in greater depth in the dedicated clvm-memory chapter.

## Process-backed memory

The desktop language pipeline can associate a slot with a ChrisOS process record.

For such a slot, lang_attach_slot_ram asks proc_set_vm for a VM region sized from the CLV memory hint or the one-megabyte default, whichever is larger.

It obtains the mapped VM pointer with proc_vm_ptr, marks the slot as using user-backed RAM, switches to the process context to initialize memory, then attaches that region to ClvmVm with clvm_vm_set_memory.

CLS library mappings can also be installed for the process.

This process association should not be confused with the CLVM guest address space itself. CLVM code still uses guest offsets and the interpreter/syscall bridge still enforce VM-specific memory semantics.

## Heap-backed fallback memory

If no process-backed region is available, the language pipeline can allocate VM RAM from the kernel heap.

It keeps a 64 MiB host-heap reserve when sizing the allocation.

The requested size begins with the image memory hint or default CLVM size, is never reduced below the one-megabyte default, and can be capped by available heap capacity.

Existing initial VM bytes are copied into the replacement allocation before clvm_vm_set_memory installs it.

The slot tracks whether the backing memory is process-owned or heap-owned so teardown does not free the wrong owner.

## Guest heap allocator

ClvmVm contains a simple bump-pointer allocator used by guest allocation services.

clvm_guest_malloc:

1. rejects invalid or extreme sizes;
2. adds an eight-byte allocation header;
3. rounds the total to eight-byte alignment;
4. checks the new allocation fits within mem_size;
5. writes the allocated span into the header;
6. advances heap_off;
7. returns the address immediately after the header.

Allocation itself is therefore O(1).

clvm_guest_free currently does not reclaim space; it returns success without moving heap_off or maintaining a free list.

clvm_guest_realloc allocates a new block and copies the previous payload up to the smaller relevant size, so its copy cost is O(n).

This is adequate as a simple current mechanism but can fragment effective guest capacity monotonically because freed space is not reused.

## Heap starting point

The heap does not always begin at the same fixed address.

clvm_vm_set_memory selects heap_off based on total memory size.

For memory of at least 16 MiB, heap_off starts at 1 MiB.

For memory above 128 KiB but below that threshold, it starts at 64 KiB.

For smaller spaces it begins halfway through memory.

The explicit reason in source is to keep the bump allocator away from static/global/string data used by large applications.

This remains a heuristic memory partition rather than a linker-described dynamic layout.

## Interpreter execution

clvm_step executes at most a supplied instruction budget.

For each instruction it:

1. records the opcode PC;
2. bounds-checks opcode fetch;
3. advances the program counter;
4. increments the executed counter;
5. decodes and applies the opcode semantics;
6. returns early on HALT, WAIT, fault or scheduler-yield conditions.

The operation is O(budget) for ordinary constant-time opcodes, excluding syscalls and operations whose cost depends on copied data.

The VM state machine includes READY, RUNNING, WAITING, HALTED and FAULTED states.

WAITING VMs yield until clvm_vm_wake observes the wake condition.

In freestanding execution, the interpreter can also yield when the process scheduler reports that a slice is due.

## Interpreter faults

Failures are stored in ClvmVm instead of being returned as raw host exceptions.

Fault categories include:

- program counter outside code;
- unknown opcode;
- truncated instruction operand;
- operand-stack underflow or overflow;
- call-stack underflow or overflow;
- division by zero;
- signed division overflow;
- invalid guest-memory address;
- invalid jump target;
- rejected syscall.

fail records the fault code and fault PC and transitions the VM to CLVM_FAULTED.

Once faulted, subsequent clvm_step calls immediately report the fault state.

## Runtime scheduling

lang_tick integrates active language slots into the desktop/runtime loop.

It first advances supporting services such as CLVM child threads, then walks slots in round-robin order.

A slot can be skipped if it is:

- being destroyed;
- paused by the debugger;
- blocked/non-runnable through its associated process.

The runtime wakes timed waits, enters the process context when applicable, runs a bounded amount of VM work and then returns to the kernel process context.

Large game-like slots receive a different slice policy from smaller UI slots.

This is bounded cooperative execution layered into the broader ChrisOS scheduling model rather than an unbounded run-to-completion call.

## Interpreter versus JIT selection

Normal desktop CLV launch attempts JIT execution when debugging is not active and JIT has not been globally disabled.

jit_compile_image is invoked after the image has been parsed and VM memory prepared.

If JIT compilation fails at launch, the runtime records the failure and uses the interpreter.

Debugger execution intentionally uses the interpreter so bytecode PCs and one-instruction stepping remain directly controllable.

Once a large application is already running in JIT mode, an unexpected runtime fault is not treated as a safe point for transparently restarting in the interpreter, because execution state may already be partially modified.

The dedicated JIT chapter documents translation and executable-memory mechanics.

## Semantic equivalence requirement

The interpreter and JIT operate on the same ClvmVm state.

The JIT must preserve:

- operand-stack semantics;
- call-stack semantics;
- VM PC behavior;
- memory checks;
- arithmetic edge cases;
- faults;
- syscall state transitions;
- HALT/YIELD behavior.

For example, native JIT implementations of CALL, CALLI and RET update the same vm->calls and vm->csp fields used by the interpreter.

This shared-state contract allows differential testing between engines.

## Syscall boundary

CL_OP_SYS transfers from bytecode execution to the registered ClvmSysFn.

In the desktop runtime that callback is clvm_sys_dispatch.

The syscall ID selects a kernel-side service. Arguments are usually popped from the operand stack and results are pushed back when the service has a result.

The current bridge covers broad categories including:

- 2D/3D graphics;
- files and storage;
- input and timing;
- audio;
- memory allocation;
- threads and synchronization;
- networking;
- cryptographic helpers;
- libraries/GC services;
- selected driver/hardware operations.

The numeric syscall ABI belongs to the dedicated syscall chapter.

## Guest-pointer validation at the syscall boundary

A syscall must not treat an integer supplied by the guest as an already-trusted kernel pointer.

Helpers in clvm_sys.c convert guest offsets only after checking vm->memory and vm->mem_size.

vm_cstr scans a string within the guest range and fails if no terminator fits inside the supplied output capacity and VM bounds.

vm_bytes validates the complete requested buffer length before returning a pointer.

copy helpers validate the complete range before transferring bytes.

This turns malformed guest pointers into syscall failure rather than direct unchecked access through the normal bridge.

Any syscall added in the future must preserve that invariant.

## Filesystem ownership and limits

The CLVM file layer tracks file objects in a bounded global table.

Each ClvmFile records its owning language slot.

Current bounds include:

    CLVM_FD_MAX       = 32
    CLVM_FD_PER_SLOT  = 8
    CLVM_FD_CAP       = 65536
    maximum buffered file size = 16 MiB

fd_owned verifies that an operation refers to a descriptor belonging to the caller's slot.

Small files can be buffered; larger files can use streaming behavior.

The bridge also rejects explicit .. path components in path_ok and consults filesystem permissions where applicable.

These checks are useful containment measures, but they should not be generalized into a claim that the current path parser implements a complete capability filesystem or all possible path-sandbox semantics.

## Capability-gated driver operations

A LangSlot contains capability bits.

Normal application paths receive no driver capabilities.

Paths recognized as system drivers receive CAP_DRIVER, which currently combines PCI, port I/O, MMIO, DMA, IRQ and disk-administration capability bits.

Hardware-oriented CLVM syscalls call drv_cap to verify that the current slot has the required capability before performing privileged driver operations.

This is an important distinction from ordinary graphics/filesystem application calls.

Capability assignment is path-driven in the current launcher, so it is a project policy mechanism rather than a cryptographic identity system.

## CLVM threads

The syscall bridge implements a lightweight CLVM thread facility.

The current limits are:

    CLVM_TH_MAX = 32 globally
    CLVM_TH_PER = 8 per slot

Creating a child thread allocates and zeroes another ClvmVm structure.

The child shares:

- bytecode pointer;
- bytecode size;
- guest memory pointer;
- guest memory size;
- syscall callback/context;
- associated process.

The child has independent VM execution state, including its operand stack, call stack and TLS array.

The initial function PC is supplied by the guest and one initial argument is pushed onto the child operand stack.

## Shared-memory concurrency

Because CLVM child VMs share the same guest-memory buffer, ordinary guest memory is shared state between threads.

This means concurrent mutation requires synchronization.

The syscall layer contains mutex/condition support through the CLVM synchronization subsystem and can place blocked child VMs into WAITING state.

clvm_threads_tick advances runnable child VMs with bounded interpreter slices and wakes a parent that is waiting to join a completed child.

The implementation is not equivalent to independent-process memory isolation: thread VMs intentionally share the guest address space.

## TLS

Each ClvmVm owns a small tls[16] array.

Because a child thread receives a newly zeroed ClvmVm, this TLS storage is per VM/thread rather than part of the shared guest-memory pointer.

Syscalls expose bounded indexed access to those TLS entries.

The array is a small project runtime facility rather than a full ELF TLS ABI.

## setjmp and longjmp

CLVM has guest setjmp/longjmp support in the VM runtime.

clvm_guest_setjmp writes into guest memory:

- current PC;
- operand stack depth;
- call stack depth;
- active operand-stack values;
- active return PCs.

clvm_guest_longjmp restores those values after validating saved stack depths against VM limits and pushes the longjmp result value.

This implementation shows why operand and call stacks are explicit VM state: nonlocal control transfer can snapshot and restore them deterministically.

It does not snapshot every possible external kernel resource or shared-memory mutation.

## Safepoints and runtime coordination

ChrisC emits SAFEPOINT at function entries, and call operations also mark safepoint state.

The desktop runtime installs lang_safepoint as the VM callback; the current callback polls GC.

Safepoints provide locations where runtime services can cooperate with execution without arbitrarily interrupting every instruction.

GC/library behavior has its own chapter because managed object/type metadata and CLS modules extend beyond the core VM mechanism described here.

## Source maps and debugging

ChrisResult source-map data is written alongside compiled CLV output.

At launch, lang_load_map reconstructs mappings from bytecode PCs to source lines and function names.

Debugger state in LangSlot stores breakpoints, stepping mode, last source line and watch information.

When debugging, lang_tick can execute one instruction at a time and use current vm.csp depth plus source-line transitions to implement step behavior.

Fault logging also reports bytecode PC, mapped line, operand-stack depth, fault code, fault PC and call-stack state.

This gives failures a source-oriented diagnostic path instead of exposing only raw VM offsets.

## Teardown and ownership

lang_kill is the authoritative slot teardown path.

It:

1. frees JIT executable memory when present;
2. releases slot VM RAM according to its ownership model;
3. releases graphics resources;
4. calls clvm_sys_close_slot;
5. frees the loaded CLV file buffer;
6. destroys the associated process;
7. clears slot activity, task identity, name and JIT pointers.

clvm_sys_close_slot then releases syscall-layer resources owned by the slot, including shader guest ownership, voxel ownership, input capture, sockets and file descriptors.

Dirty buffered files are flushed through the file-descriptor teardown path.

This explicit cleanup is required because many CLVM services allocate kernel-side resources that cannot be reclaimed simply by discarding ClvmVm.

## Hot reload

The language pipeline supports reloading the CLV bytes of an existing named slot.

It reparses the replacement image, copies it into slot-owned storage, reinitializes the VM, reattaches memory, restores selected checkpoint bytes and reloads source maps.

This is a development/runtime convenience, but it is not transparent process migration.

The VM execution state is reset, while only deliberately preserved checkpoint state is copied back.

Resources outside that checkpoint must obey their own lifecycle rules.

## Self-hosting direction already present

CLVM is also used as part of the project's compiler bootstrap path.

lang_disk_cc loads APPS/CC/CC.CLV, creates a process, assigns a 16 MiB VM region, initializes a ClvmVm and executes the compiler image through clvm_step.

The caller supplies source and destination paths through the application argument mechanism.

After the guest compiler halts, the resulting destination file is loaded and validated again with clvm_parse.

This is concrete evidence that CLVM is not merely a demonstration interpreter. It participates in the project's path toward running compiler tooling inside the system.

It does not by itself establish complete self-hosting of every ChrisOS component.

## Complexity and storage bounds

Important current bounds and costs include:

| Mechanism | Current behavior |
|---|---|
| image parse | O(code size), dominated by checksum |
| interpreter slice | O(instruction budget) excluding syscall-specific cost |
| operand stack | fixed 256 x 64-bit entries |
| return stack | fixed 64 x 32-bit PCs |
| default guest RAM | 1 MiB |
| maximum CLV code | 16 MiB |
| guest malloc | O(1) bump allocation |
| guest free | no reclamation |
| guest realloc | O(copied bytes) |
| thread table | 32 global entries, linear scans |
| file table | 32 entries, linear bounded scans |

These fixed limits make many operations predictable and avoid unbounded metadata allocation, while also placing hard ceilings on workloads.

## Validation evidence

The active execution path has several classes of tests.

tools/test_chrisc_c17.c compiles and executes a broad C17-oriented ChrisC subset through CLVM.

tools/test_chrisc_fn.c focuses on function behavior and VM results.

tools/test_chrisc_doom.c exercises large-program compiler/runtime cases.

tools/test_chrisc_ptr_float.c protects pointer-versus-float argument semantics.

tools/test_fuzz_clvm.c feeds varied input into the CLV parser and also validates writer/parser round trips.

tools/test_jit_vm.c and tools/test_jit_native.c exercise JIT behavior against VM semantics.

tools/test_editor_vi.c includes regression coverage for interpreter/JIT call-stack overflow behavior.

The documentation build validates source references and the broader repository CI runs the project test suite configured by the workflow.

None of these claims means every possible CLVM program or every hardware-backed syscall has been exhaustively verified.

## Current limitations

At the documented revision:

- CLVM has fixed operand and call stack capacities;
- default guest memory is one MiB unless runtime policy or an image hint increases it;
- guest malloc is a bump allocator and free does not reclaim space;
- the heap start is heuristic rather than described by a formal segmented image layout;
- ordinary ChrisC function storage is not a fully private per-activation frame model;
- the syscall ABI is broad and therefore increases the compatibility surface that interpreter, compiler and kernel must preserve;
- capability assignment for driver CLVs is path-based;
- threads share one guest-memory buffer and require explicit synchronization;
- the current runtime has bounded global thread and file tables;
- JIT compilation may fall back to interpretation at launch;
- debugging intentionally prefers interpretation;
- a runtime JIT fault is not automatically replayed through the interpreter;
- CLV checksum detects corruption but does not authenticate code;
- CLVM application isolation is a runtime/process integration model, not identical to the KCC native executable model.

## Roadmap boundary

Possible future improvements include:

- a formally versioned VM ABI specification covering bytecode, calls, syscalls and memory layout;
- per-activation ChrisC frames;
- a reclaiming guest allocator;
- stronger capability provenance than path classification;
- explicit verifier passes before execution;
- richer module/link metadata;
- more scalable thread/resource tables;
- structured exception/unwind state;
- stronger code-signing or trust policy where required;
- broader differential testing between interpreter and JIT;
- clearer separation between application, driver and managed-library profiles.

These are future directions unless and until corresponding source and tests exist.

## Source map and revision

ChrisC compilation and bytecode lowering are implemented in compiler/chrisc/chrisc.c.

CLV image structure and validation are defined by compiler/clvm/clvm.h and compiler/clvm/clvm_format.c.

The VM state machine, stacks, guest allocator and interpreter live in compiler/clvm/clvm_vm.h and compiler/clvm/clvm_vm.c.

Application lifecycle, VM-memory attachment, interpreter/JIT selection, source maps, scheduling and teardown are implemented in compiler/lang_pipeline.c.

The kernel service boundary and slot-owned CLVM resources are implemented in kernel/lang/clvm_sys.c.

All current-behavior claims in this chapter were reconciled against ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.
