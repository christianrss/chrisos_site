---
id: chrisc-clvm
lang: en
type: technical-chapter
volume: 07-language-systems
status: maintained
reviewed_revision: da3df29cb397932c43d32373871fb9380e688ade
sources:
  - compiler/chrisc/chrisc.c
  - compiler/clvm/clvm_vm.c
  - compiler/lang_pipeline.c
  - kernel/lang/clvm_sys.c
symbols: []
depends_on:
  - compiler-pipeline
related:
  - native-toolchain
---

# ChrisC and the CLVM execution model

## Language path

ChrisC is the project language used for applications and parts of the self-hosting/tooling direction. Its principal managed execution path compiles source to CLVM bytecode rather than directly producing the same native kernel object path as KCC.

```text
ChrisC source
     ↓
ChrisC compiler / language pipeline
     ↓
CLVM image
     ↓
interpreter or JIT
     ↓
CLVM syscall bridge
     ↓
kernel services
```

## Why use a bytecode VM

A bytecode virtual machine provides a stable execution target smaller than a full hardware ISA. The language compiler can emit CLVM operations while the runtime chooses interpretation or JIT execution.

Benefits include controlled guest memory, instrumentation and an API designed specifically for ChrisC applications.

The cost is another execution layer whose semantics must remain consistent across interpreter, JIT and syscall bridge.

## Guest memory

CLVM addresses are guest offsets, not kernel pointers. Every syscall that receives an address must validate it against the VM memory contract before touching kernel memory.

This is a protection boundary even though the VM runtime itself executes in privileged kernel code.

## Interpreter and JIT

The interpreter reads bytecode operations and updates VM state directly. The JIT translates supported operations to native x86-64 code for faster execution.

Correctness requires semantic equivalence. If ADD, memory access or fault behavior differs between interpreter and JIT, application behavior can depend on the selected backend.

Differential tests are therefore especially valuable for VM/JIT systems.

## System calls

`kernel/lang/clvm_sys.c` connects VM programs to graphics, files, input, timing, audio and other services. This API is effectively the operating-system ABI for ChrisC applications.

Stable syscall numbers and argument layouts matter because compiled bytecode can outlive one source compilation.

## Slot ownership

Resources associated with a language slot need cleanup when that slot closes. File descriptors, shader handles, mouse capture and other state cannot remain globally reachable after the owning VM disappears.

This is why VM teardown belongs in the same architecture discussion as bytecode execution.

## Native and CLVM boundaries

ChrisC/CLVM is not equivalent to a native ring-3 process. A native process has a hardware page-table/privilege boundary; a CLVM application has a runtime-enforced guest-memory and syscall boundary.

Both can provide isolation properties, but through different mechanisms and failure modes.
