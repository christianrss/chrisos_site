---
id: toolchain-history
lang: en
type: technical-chapter
volume: 16-history
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/chrisc/chrisc.c
  - compiler/clvm/clvm_format.c
  - compiler/clvm/clvm_vm.c
  - compiler/jit/jit.c
  - compiler/jit/jit_compile.c
  - compiler/kcc/kcc.c
  - compiler/chrisasm/chrisasm.c
  - compiler/chrisld/chrisld.c
  - compiler/chrisld/chriso.c
  - compiler/lang_pipeline.c
  - kernel/tools/native_link.c
  - kernel/tools/chrismake.c
  - kernel/tools/chrisbuild.c
  - kernel/tools/editor_window.c
symbols:
  - chrisc_compile
  - clvm_parse
  - clvm_step
  - jit_compile
  - kcc_compile
  - chrisasm_assemble
  - chrisld_link_objects
depends_on:
  - architecture-history
related:
  - compiler-pipeline
  - chrisc-clvm
  - clvm-spec
  - jit
  - native-toolchain
  - kcc
  - chrisasm
  - chrisld
  - self-hosting-bootstrap
  - stage-compilers
---

# Native toolchain history

## Scope

ChrisOS did not acquire one monolithic compiler toolchain in a single step.

The current language stack is the result of several lines of development that initially solved different problems:

- ChrisC source compilation for interactive applications;
- CLVM bytecode execution;
- JIT translation of CLVM workloads;
- ChrisAsm and ChrisLd for native objects and ELF output;
- KCC for a restricted C-to-native path;
- in-system build/edit/run tooling;
- progressively stronger host gates for self-hosting claims.

This chapter reconstructs those lines from Git history and reconciles them with current source revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`.

## Why "self-hosted" needs a historical definition

The phrase "self-hosted" can describe different maturity levels.

For ChrisOS, at least five levels must be distinguished:

1. **editor-integrated compilation** — source can be compiled from the OS environment;
2. **native tool availability** — assembler/linker/compiler logic exists in the ChrisOS codebase;
3. **host-tested compiler subset** — the project compiler can compile selected ChrisOS translation units under test;
4. **bootstrap stage** — project tools can build meaningful native binaries from their own formats;
5. **full self-hosted kernel build** — the complete production kernel can be rebuilt and booted using the project-owned toolchain.

Historical commits crossed the first four boundaries incrementally.

At revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, the fifth boundary must still not be claimed.

## 18 September 2026 — ChrisC and CLVM become an application pipeline

The first major language-system milestone in the current history is:

    3042fcf2951b6681e8d58f662ac667f460229293

Message:

    feat: PASSO 05 — Editor: Save, Compile e Run

The commit added:

- `compiler/chrisc/chrisc.c`;
- CLVM assembler and format files;
- CLVM interpreter;
- the central language pipeline;
- editor integration.

The significance is broader than adding a parser.

It established an end-to-end development loop:

    edit ChrisC source
          |
          v
      compile
          |
          v
       CLVM image
          |
          v
      interpreter
          |
          v
      application window

This was the first strong form of "development inside ChrisOS".

## ChrisC was initially a VM-oriented language path

The early ChrisC pipeline did not attempt to produce the production kernel.

Its target was CLVM.

That made the first language architecture relatively controlled:

- bounded bytecode format;
- explicit virtual-machine state;
- host-managed syscalls;
- deterministic interpreter;
- application lifecycle inside the desktop.

The VM boundary reduced the number of x86-64 ABI and relocation problems that had to be solved before applications could compile and run.

## CLVM made the editor loop practical

The CLVM interpreter introduced a stable target for the editor/compiler loop.

Instead of generating native machine code immediately, the compiler could emit a project-owned bytecode.

That brought several advantages during rapid development:

- easy instruction validation;
- explicit faults;
- portable host testing;
- bounded guest memory;
- a direct place to implement scheduling/yield;
- a stable syscall boundary.

The later `clvm-spec` formalizes what began as this practical execution target.

## 19 September — JIT becomes the second CLVM execution path

Commit:

    431dfce847e414c2b0696c785e5a16db616839ccc

added the first JIT files:

- `jit.c`;
- `jit_compile.c`;
- `jit_emit.c`;
- headers and integration.

This created a second execution strategy:

    CLVM bytecode
       /      \
      v        v
 interpreter   JIT
               |
               v
            x86-64

Historically, this is important because the JIT was not a replacement for CLVM.

CLVM remained the semantic contract; the JIT was an acceleration backend.

## Interpreter-first semantics

That order shaped the current system.

The interpreter provides the clearest reference for:

- stack effects;
- memory semantics;
- faults;
- syscall boundaries;
- control-flow behavior.

The JIT must preserve those semantics while translating supported operations into executable x86-64.

This is a much safer architecture than allowing the JIT to become an independently defined language runtime.

## 19 September — the native bootstrap toolchain appears

A second major branch arrived with:

    7bfd60fbeb32e7ccac843c7f640012641c4754fc

Message:

    feat: fase16/23, build layout, and repo hygiene

The commit introduced:

- KCC;
- ChrisAsm;
- ChrisLd;
- ChrisO;
- host test drivers;
- ChrisBuild;
- expanded shell integration.

This is the point where ChrisOS gained a distinct native-toolchain lineage rather than relying only on ChrisC -> CLVM.

The conceptual pipeline became:

    restricted C
       |
       v
      KCC
       |
       v
   assembly text / native form
       |
       v
   ChrisAsm
       |
       v
    ChrisO
       |
       v
    ChrisLd
       |
       v
     ELF64

## ChrisO changes the architecture

The introduction of ChrisO was important because assembler and linker could now communicate through a project-owned object format.

That separated:

- source-language concerns;
- instruction encoding;
- symbol/relocation representation;
- final executable layout.

A native toolchain without an object boundary tends to collapse all of those into one program.

ChrisO made later multi-object linking possible.

## Early KCC was deliberately small

The first KCC should not be read through the capabilities of the current KCC.

It began as a restricted compiler.

That was intentional: the project could define a subset and grow it against real kernel source rather than pretending to implement ISO C immediately.

This design philosophy becomes explicit later when KCC starts failing closed on unsupported source.

## 20 September — ChrisC, CLVM and JIT expand rapidly

Commit:

    16ac03ecb3ae5625d0729ce78e88795f2208af33

was a large language/toolchain expansion.

It substantially enlarged ChrisC and CLVM, extended JIT compilation/runtime, added IL and GC support, and added `kernel/tools/native_link.c`.

This was the point where the VM-based and native-linking lines began to interact more closely.

The system was no longer only:

    source -> VM

It was becoming a language platform with:

- VM execution;
- JIT execution;
- native object/link support;
- in-kernel linking helpers;
- richer compiler semantics.

## Native link support inside the OS

`native_link.c` is historically significant because final linking was no longer only a host-side development operation.

ChrisOS gained logic for taking project-native objects and emitting runnable ELF inside the system.

That is a stronger self-hosting primitive than simply having a compiler source directory in the repository.

## ChrisMake adds build orchestration

Later on 20 September:

    dea12e87f0392e7d3402d0aa3213ea51de29b334

added ChrisMake.

This moved the project from isolated compile/run commands toward build orchestration.

A self-hosted environment requires more than compiler stages.

It also needs:

- dependency/order control;
- build recipes;
- file naming;
- diagnostics;
- repeated build behavior.

ChrisMake was an early answer to that layer.

## The toolchain grew under application pressure

Between 20 and 24 September, ChrisC and the language pipeline changed repeatedly while Doom, ChrisEditor, games and more complex applications were being integrated.

This period matters because it shows where language features came from.

They were not added only to satisfy synthetic parser tests.

They were driven by increasingly realistic application source.

That creates useful coverage, but also a risk: a compiler can become a collection of application-specific fixes unless its semantics and gates are tightened.

The next stages did exactly that.

## 24 September — relocation semantics mature

Commit:

    aa5186ac5281bebb15e26fb53a3757507b7276b7

fixed call relocations across objects.

The commit explicitly records that ChrisAsm emitted calls as:

    undefined symbol + R_X86_64_PLT32

and ChrisLd gained stronger multi-object behavior:

- apply call relocations;
- reject missing globals;
- reject duplicate globals;
- validate generated ELF;
- reject unknown assembler mnemonics.

This was a major jump in native-toolchain quality.

The linker was becoming an actual symbol-resolution component instead of a concatenation helper.

## Why call relocations matter

A single-file compiler can hide many linking problems.

Cross-object calls force the toolchain to define:

- symbol binding;
- undefined references;
- relocation type;
- addend;
- place address;
- duplicate-definition policy.

For a PC-relative call relocation:

[
value = S + A - P
]

where:

- (S) = resolved symbol address;
- (A) = addend;
- (P) = relocation place.

Getting this right is a prerequisite for scaling the compiler to real multi-file systems code.

## 24 September — KCC starts failing closed

One of the most important historical quality improvements was:

    89812c7888667dedb22081099dae2a22fac7c5b7

Message:

    kcc: reject source outside the level-0 subset

Before this change, skipped or unsupported input could be confused with successful compilation.

The commit made KCC:

- report file/line/column diagnostics;
- define a narrow level-0 subset;
- reject unsupported preprocessor/source constructs;
- fail the kernel gate when a real file could not be compiled.

This changed the meaning of a successful KCC test.

A passing result now represented accepted semantics, not silent omission.

## Fail-closed is a compiler correctness feature

For self-hosting work, rejection is often better than permissive miscompilation.

A compiler that says:

    unsupported

is inconvenient.

A compiler that silently generates wrong machine code can corrupt the kernel.

KCC's historical shift toward fail-closed behavior is therefore a reliability milestone, not merely a diagnostics improvement.

## 25 September — "Improve self hosted"

Commit:

    6087c38ce115ccd25b32f94a5488f7a9ac230902

greatly expanded KCC and ChrisAsm.

KCC changed by thousands of lines.

ChrisAsm gained much broader encoding support.

ChrisLd and tests were also extended.

This is the transition from a tiny demonstration compiler toward a tool that could be evaluated against real kernel translation units.

## Kernel files become the benchmark

After that expansion, KCC progress is best measured by which real `kernel/metal` files compile.

This is better evidence than counting language features.

A feature matters when it allows a production translation unit to cross the compiler without unsupported constructs or semantic mismatches.

The subsequent commits explicitly use that metric.

## KCC compiles the kernel log ring

Commit:

    a3a3340f5b4dfb1e1f899d40ffc930ee57838abd

added support needed for uninitialized global BSS arrays and compiled `klog.c`.

The host gate linked serial and klog with stubs.

This is a small-looking language change with large historical meaning:

> KCC was beginning to compile stateful kernel infrastructure rather than isolated expressions.

## Volatile MMIO becomes preserved

Commit:

    f0e59c3e0421583b653cbfa676a20e4b1de8fdef

added a critical systems-programming property:

- plain repeated stores could be optimized;
- `volatile uint32_t` loads/stores had to remain present;
- ChrisAsm gained the dword forms needed by that output.

For kernel compilation, `volatile` is not cosmetic.

It can represent externally observable device access.

Dropping or combining such operations can break hardware semantics.

This was therefore a real step from "C-like compiler" toward "systems C subset".

## More kernel C features follow

Commit:

    2611508a614b0507632ba776b9a017008b33b46b

added support for features required by `string.c`, `pit.c`, `meminfo.c` and related files:

- void pointers;
- `size_t`;
- named and packed structs;
- function pointers;
- seventh stack argument;
- unary minus;
- conditional operator.

The gate then compiled six metal translation units.

Again, the important metric was not syntax count but real kernel coverage.

## 14 metal files compile

Commit:

    30b24058dc800dbeb234f96e3e0a1661377104da

extended both ChrisAsm and KCC.

ChrisAsm gained instruction support and same-section local-label patching.

KCC added:

- `break`;
- `continue`;
- unary not;
- `sizeof`;
- `_Static_assert`;
- controlled inline asm forms.

The commit record says the host gate covered fourteen metal files.

It also states what remained unproven.

That explicit non-claim is historically important.

## Inline assembly becomes a closed subset

KCC did not attempt to parse arbitrary GCC inline assembly.

The accepted subset was deliberately closed around operations such as:

- `cli`;
- `sti`;
- `hlt`;
- `pause`;
- empty compiler barrier;
- port I/O.

Unsupported privileged assembly and `__sync` forms failed.

This approach traded generality for auditable code generation.

For a bootstrap compiler, that is a reasonable intermediate architecture.

## Local labels move out of ChrisO pressure

At the same stage, ChrisAsm began patching same-section `.L` branches directly.

That avoided consuming ChrisO symbol-table slots for compiler-generated local labels.

This shows the assembler/object-format boundary maturing in response to real compiler output.

Not every internal label needs to become a link-visible symbol.

## 25 September — KCC compiles every kernel/metal C file

The strongest KCC milestone in the current Git history is:

    aa591ccd3b414c2b0696c785e5a16db616839ccc

Message:

    feat: compile the metal kernel with KCC (#14)

The change added preprocessor and low-level support sufficient to host-compile every C file under `kernel/metal`.

The commit record mentions support for:

- `#if`, `#elif`, `defined`;
- function-like macros;
- token paste;
- line continuation;
- Limine include handling;
- CR2/CR3 operations;
- `invlpg`;
- `lidt`, `lgdt`;
- `lretq`, `iretq`;
- `str`;
- lock `cmpxchg` and `xadd`;
- fixed low-level sequences for selected context-switch/descriptor operations.

This is a substantial compiler milestone.

## What that milestone does not prove

The same commit explicitly says full self-hosting remained unproven.

It records limitations including:

- dozens of makefile translation units still failing;
- NASM IDT stubs;
- no complete Limine image produced by ChrisLd;
- float loads/stores still unsupported in KCC;
- privileged constructs outside the closed supported set.

Therefore the correct statement is:

> KCC host-compiles the complete `kernel/metal` C subset at that revision.

It is **not**:

> ChrisOS rebuilds its complete production kernel with KCC.

## Two compiler families now coexist

At this stage ChrisOS has at least two distinct source-language paths.

### ChrisC path

    ChrisC
      |
      v
    CLVM bytecode
      |
      +--> interpreter
      |
      +--> JIT

This path is application-oriented and tightly integrated with the desktop/runtime syscall model.

### KCC native path

    restricted C
      |
      v
     KCC
      |
      v
   ChrisAsm
      |
      v
    ChrisO
      |
      v
    ChrisLd
      |
      v
     ELF64

This path targets native execution and bootstrap/self-hosting goals.

They solve related but different problems.

## Why ChrisC and KCC should not be conflated

ChrisC is not simply an earlier name for KCC.

Their execution contracts differ.

ChrisC is tied to:

- CLVM semantics;
- runtime syscalls;
- managed guest memory conventions;
- optional JIT acceleration;
- application lifecycle.

KCC is tied to:

- x86-64 native code;
- ChrisAsm instruction encoding;
- ChrisO relocation/symbol rules;
- ChrisLd ELF generation;
- systems-programming subsets needed by kernel code.

Historical documentation must preserve that distinction.

## The language pipeline became an orchestration layer

`compiler/lang_pipeline.c` changed across many of these commits.

Its role grew beyond "call the compiler".

It became the integration point for:

- compile;
- image packaging;
- VM creation;
- JIT choice;
- program lifecycle;
- debugger hooks;
- application closure/restart;
- richer runtime state.

This mirrors the broader history: the toolchain became an operating-system subsystem, not merely a collection of host utilities.

## ChrisEditor tightens the development loop

By 25 September, commits were adding self-hosted program debugging from ChrisEditor.

That closes another loop:

    edit
      -> compile
      -> run
      -> debug
      -> edit

A development environment is more self-hosted when failures can be inspected inside the same environment that produced the binary.

This is different from full compiler bootstrap, but still an important systems milestone.

## Testing evolved with capability

Early toolchain progress could be demonstrated by producing output.

Later history added increasingly specific gates:

- assembler encoding tests;
- linker relocation tests;
- KCC subset tests;
- real kernel translation-unit compilation;
- rejection tests for unsupported constructs;
- native-link tests;
- CLVM fuzzing;
- JIT execution comparison;
- JIT benchmark/regression gates.

This changed the meaning of "supported".

A language feature without a gate became weaker evidence than one tied to a real translation unit and a negative test.

## Current architecture

At revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56`, the toolchain can be summarized as several connected layers.

### Application language path

    ChrisC source
        |
        v
      compiler
        |
        v
       CLVM
       /  \
      v    v
 interpreter JIT
      |      |
      +-- runtime/syscalls --+

### Native bootstrap path

    restricted C
        |
        v
       KCC
        |
        v
     ChrisAsm
        |
        v
      ChrisO
        |
        v
      ChrisLd
        |
        v
       ELF64

### In-system orchestration

    editor / shell / ChrisMake / ChrisBuild
              |
              v
      compile-link-run workflows

The history is the gradual connection of those layers.

## Historical milestones

| Date | Commit | Meaning |
|---|---|---|
| 2026-09-18 | `3042fcf` | ChrisC + CLVM + editor compile/run loop |
| 2026-09-19 | `431dfce` | JIT becomes a second CLVM execution path |
| 2026-09-19 | `7bfd60f` | KCC, ChrisAsm, ChrisLd and ChrisO arrive |
| 2026-09-20 | `16ac03e` | language/JIT expansion and in-kernel native linking |
| 2026-09-20 | `dea12e8` | ChrisMake adds build orchestration |
| 2026-09-24 | `89812c7` | KCC rejects unsupported level-0 source |
| 2026-09-24 | `aa5186a` | cross-object call relocations and stronger linker |
| 2026-09-25 | `6087c38` | major self-hosting expansion |
| 2026-09-25 | `a3a3340` | KCC compiles kernel log infrastructure |
| 2026-09-25 | `f0e59c3` | volatile MMIO semantics preserved |
| 2026-09-25 | `2611508` | six metal translation units compile |
| 2026-09-25 | `30b2405` | fourteen metal files compile; closed asm subset |
| 2026-09-25 | `aa591cc` | all `kernel/metal` C files host-compile with KCC |

The table summarizes architectural milestones, not every language fix.

## Architecture lessons

### A VM target accelerates early language development

CLVM let ChrisC become useful before native ABI/linking work was complete.

### Native bootstrap needs an object-format boundary

ChrisO separated assembler output from final linking and made multi-object evolution possible.

### Real source is a better compiler benchmark than feature lists

Counting supported syntax is less meaningful than compiling real kernel translation units under deterministic tests.

### Fail closed on unsupported semantics

KCC's level-0 rejection policy improved the reliability of every later success claim.

### Self-hosting is staged

An in-OS editor/compiler, a native linker, a kernel-subset compiler and a complete bootstrapped kernel are different milestones.

Documentation should name the exact stage reached.

## Superseded claims

Old snapshots can make several statements appear current when they are not:

- ChrisC is the only project language path;
- CLVM is interpreter-only;
- KCC silently skips unsupported source;
- ChrisAsm cannot represent cross-object calls;
- ChrisLd only links trivial objects;
- KCC only compiles toy fixtures;
- the entire kernel is already self-hosted.

The first six were superseded by later implementation.

The last remains an overclaim at the reviewed revision.

## Current limitation boundary

The strongest historical KCC gate says every `kernel/metal` C file can be host-compiled.

It simultaneously records that the full kernel build remains incomplete.

That limitation should be preserved until there is executable evidence for the complete bootstrap:

    project compiler
      -> all required kernel objects
      -> all assembly/stubs
      -> final boot image
      -> successful boot
      -> validation gates

Anything less is partial self-hosting.

## Revision note

This chapter was reconciled against ChrisOS revision `e05a17fd76333114a3fb5c2452f38ca747d4ac56` and the listed Git milestones.

Future entries should be added when the toolchain crosses a meaningful stage boundary: broader compiler semantics, new object/ABI compatibility, bootstrap-stage completion, full kernel link, or a verified self-hosted boot.
