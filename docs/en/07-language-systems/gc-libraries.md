---
id: gc-libraries
lang: en
type: technical-chapter
volume: 07-language-systems
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/gc/gc.h
  - compiler/gc/gc.c
  - compiler/cls/cls.h
  - compiler/cls/cls.c
  - compiler/cla/cla.h
  - compiler/cla/cla.c
  - compiler/il/il.h
  - compiler/il/il.c
  - compiler/chrisc/chrisc.c
  - compiler/chrisc/chrisc.h
  - compiler/lang_pipeline.c
  - kernel/lang/clvm_sys.c
  - kernel/metal/proc.c
  - kernel/metal/proc.h
  - tools/mk_clv.c
  - tools/test_cls.c
  - tools/test_cla_gc.c
symbols:
  - gc_init
  - gc_alloc
  - gc_root_reg
  - gc_request
  - gc_poll
  - gc_collect
  - gc_type_register
  - gc_type_lookup
  - cls_parse
  - cls_write
  - cls_runtime_init
  - cls_runtime_load
  - cls_runtime_reload
  - cls_runtime_resolve
  - cls_map_proc
  - cla_parse
  - cla_load_bytes
  - cla_resolve
depends_on:
  - clvm-memory
  - clvm-syscalls
  - clvm-interpreter
  - debugger
related:
  - chrisc-clvm
  - jit
  - native-toolchain
  - resource-lifetime
  - process-lifecycle
---

# Libraries, modules and garbage collection

## Scope

ChrisOS currently has several mechanisms that can all look like “libraries” from the source level but have different runtime semantics:

1. **ChrisC source composition** through `#include` and multi-file `.LST` compilation;
2. **CLS runtime libraries**, which package CLVM code, ABI metadata, exports, imports, type descriptions and optional data;
3. **CLA assemblies**, which package verified IL methods, references and managed-type metadata;
4. a small **garbage collector** shared by the managed/runtime experiments and exposed to CLVM through syscalls.

These mechanisms are related, but they are not one unified dynamic-linking system.

The source-composition path is the most complete path used by ordinary ChrisC applications. CLS provides loading, ABI checking, hot-reload state and process mapping infrastructure, but the current source does not yet connect normal ChrisC calls to `cls_runtime_resolve`. CLA provides an IL assembly container and verifier, but it is likewise an experimental managed-runtime layer rather than the normal application execution format.

The garbage collector is functional for explicitly registered host roots and simple object graphs, but current CLVM integration does not yet provide a complete managed root set.

![Libraries and GC layers](../../assets/diagrams/gc-libraries-en.svg)

## Compile-time source libraries

The ordinary ChrisC library model starts before runtime.

Applications can include source/header files such as:

    #include "LIB/STDIO.H"
    #include "LIB/STR.CC"

The compiler's preprocessing/expansion path reads included files through the configured `ChriscReadFn`.

In ChrisOS, `lang_pipeline.c` supplies `chrisc_fs_read`, so includes are resolved from the ChrisOS filesystem.

The compiler tracks included source files for diagnostics/source maps and limits nesting with:

    INCLUDE_DEPTH = 16

It also has include caching and `#pragma once` tracking.

This path is textual/source composition. It does not create a runtime library handle.

## Multi-file compilation

A `.LST` file is a list of translation-unit paths.

`lang_compile_list` reads those paths and calls `chrisc_compile_files_ex`.

The host-side `mk_clv` tool follows the same broad model.

For multiple ChrisC inputs, the compiler parses declarations across the listed units and emits one CLVM image.

This provides a practical static-library-like workflow:

    multiple .CC/.H sources
        -> one compiler state
        -> one CLVM code image

There is no runtime relocation step for those source files after the CLV is built.

## ChrisC ABI metadata

ChrisC carries a small library ABI version:

    abi_major
    abi_minor

The compiler defaults to:

    1.0

and source can set the ABI through the supported pragma, as used by `LIB/WIN.CC`:

    #pragma abi(1, 0)

The emitted `ChrisResult` also contains export metadata.

At the current revision, every defined function with a body and entry PC can become an export record, up to 64 entries.

For each exported function the compiler records:

- name;
- bytecode PC;
- argument count.

The compiler does not currently implement a source-level visibility system in which only explicitly marked functions become CLS exports.

## CLS: runtime library image

CLS is the current runtime-library container.

Its magic is:

    "CLS\0"

A `ClsImage` contains:

- library name;
- ABI major/minor;
- exports;
- imports;
- managed-type metadata;
- code section;
- data section.

Limits are fixed:

    CLS_MAX_EXPORTS = 64
    CLS_MAX_IMPORTS = 32
    CLS_MAX_TYPES   = 32
    CLS_MAX_LIBS    = 16
    CLS_MAX_CODE    = 512 KiB

The on-disk parser validates table counts and that code+data fit inside the supplied file.

## CLS exports

Each `ClsExport` stores:

    name
    sym_ver
    argc
    pc
    flags

`cls_find_export` searches by exact name.

A requested symbol version of zero acts as a wildcard; otherwise the export's `sym_ver` must match.

The runtime keeps a per-loaded-library `tramp[]` array.

At load/reload it copies each export PC into that array.

Despite the name, these are currently integer PC entries, not generated executable trampoline stubs.

## CLS imports

Each import describes:

    library name
    symbol name
    required ABI major
    required ABI minor
    symbol version

Before a new CLS image is accepted, `check_imports` requires every referenced library to already be loaded.

Compatibility rule:

    have_major == need_major
    have_minor >= need_minor

Then the requested export and symbol version must exist.

This is a useful load-time dependency check.

However, validation is not the same as linking.

The current loader does not patch CLVM call sites from the import table, and repository search shows `cls_runtime_resolve` has no call site outside its definition/declaration.

Therefore imports are currently validated metadata, not a complete executable dynamic-link path for ordinary ChrisC calls.

## Creating a CLS image

`tools/mk_clv.c` can compile a `.LST` as CLS:

    mk_clv LIB/WIN.LST --cls LIB/WIN

It compiles ChrisC first, then transfers `ChrisResult` export information into `ClsImage`.

The current writer sets:

- library ABI from ChrisResult;
- code bytes from compiled CLVM;
- each export's symbol version to 1;
- argument count from the compiler;
- export PC from generated bytecode.

The current `write_cls` path does not populate imports, managed types or data from ChrisC source metadata.

Those fields exist in the CLS format/runtime but are not yet generated by this ordinary build path.

## Loading CLS libraries

`cls_runtime_load` reads the complete file and passes it to the internal load path.

A new load:

1. parses the CLS image;
2. rejects code larger than CLS_MAX_CODE;
3. validates imports against already loaded libraries;
4. rejects duplicate library names;
5. allocates/copies the code buffer;
6. allocates/copies data when present;
7. installs image metadata;
8. populates export PC entries;
9. assigns and registers managed-type IDs;
10. increments the loaded-library count.

The runtime table is global.

Library IDs are slots in the fixed 16-entry table.

## Hot reload

`cls_runtime_reload` parses the new image first and finds an already loaded library by embedded library name.

If no existing library matches, reload behaves as a new load.

For an existing library, the major ABI must remain unchanged.

Code storage is reused when the old allocation is large enough; otherwise fresh code storage is allocated.

When the code allocation moves in freestanding builds, the runtime attempts to remap CLS libraries into every live process before freeing the old code buffer.

## Data preservation across reload

CLS reload has an intentional state-preservation rule.

Existing data storage is preserved when:

- data size is unchanged;
- ABI major is unchanged;
- the new ABI minor does not move backward.

If size changes or the new minor is lower than the old minor, the old data buffer is discarded and a fresh buffer is initialized from the image.

This is a simple hot-reload state policy.

It does not perform schema migration.

A same-sized data structure can still be semantically incompatible even when the ABI metadata permits preservation.

## Type metadata and reload gap

A new library receives a contiguous type-ID range beginning at `g_next_type_base`.

Each CLS type has:

    name
    size
    gc_bits

Those descriptors are registered with the GC.

However, `install_types` is called only for a new load.

On reload, the current loader updates `L->img` but does not re-register the library's type descriptions.

Therefore changing a type's size, `gc_bits`, count or ordering during reload can leave the GC registry describing the previous image.

The major-version check alone does not prevent this.

Hot reload should either freeze type layout for the lifetime of a library ID or atomically reconcile the GC type table.

## Process mapping

`cls_map_proc` maps loaded library code into each process beginning at:

    PROC_LIB_VIRT = 0x08000000

Each library receives a one-MiB virtual window based on its library slot.

Data is copied into a second region beginning eight MiB above PROC_LIB_VIRT.

The code mapping uses `proc_map_user(..., MM_PRESENT)`.

`proc_map_user` adds MM_USER automatically.

MM_WRITE is not requested for code pages, and MM_NX is not requested, so the intended page-table policy is user-readable/executable and not writable.

The data page is created with the normal process commit path and is writable.

## 32-KiB process-mapping ceiling

There is a mismatch between CLS image limits and process mapping.

CLS accepts:

    CLS_MAX_CODE = 512 KiB

but `cls_map_proc` computes code pages and then does:

    if (pages > 8)
        pages = 8

Eight 4-KiB pages map only 32 KiB.

Therefore a valid CLS image larger than approximately 32 KiB can be accepted and stored by the runtime while only the first portion is mapped into a process through this path.

This is a concrete integration limit.

The mapping loop should cover the complete validated code size or CLS_MAX_CODE should reflect the real executable mapping limit.

## Export-PC validation gap

`cls_parse` validates table framing but does not verify that each export PC is smaller than `code_size`.

`cls_runtime_resolve` can therefore return an export PC that is outside the loaded code section if a malformed but structurally valid CLS file supplies one.

Because ordinary call binding is not yet wired to this resolver, this is not currently the primary execution path, but it should still be validated at load time.

A future linker/call bridge must never trust an export PC solely because the enclosing CLS file parsed successfully.

## Current dynamic-call boundary

The runtime exposes:

    cls_runtime_resolve(lib, name, sym_ver, &pc, &lib_id)

but current source has no consumer of that resolver.

The CLVM syscall surface exposes `lib_load` and `lib_reload`, returning a library ID, but no matching general `lib_resolve` or `lib_call` builtin exists.

Thus CLS currently provides:

- loading;
- ABI/dependency validation;
- metadata;
- process mapping;
- reload bookkeeping;

but not a complete source-to-runtime dynamic function call ABI.

That distinction is essential when describing current implementation status.

## CLA managed assemblies

CLA is a separate assembly format for IL-oriented runtime experiments.

A `ClaImage` can hold:

- up to 64 methods;
- up to 32 types;
- up to 8 assembly references;
- an IL byte stream;
- assembly name/version metadata.

Up to eight CLA images can be loaded globally:

    CLA_MAX_ASM = 8

Each loaded assembly receives a private 64-KiB IL storage buffer.

## CLA verification

`cla_load_bytes` parses the image and verifies each method before accepting it.

For every method:

    rva + size <= il_size

must hold.

Then `il_verify` checks the method's IL against its signature.

Assembly references must resolve against assemblies that were already loaded.

This is closer to a managed module loader than CLS because it verifies per-method IL structure before installation.

The CLVM builtin `cla_load` reads a file into a bounded temporary buffer and calls `cla_load_bytes`.

## CLA dependency ordering

CLA reference resolution is load-order dependent.

When loading an image with references, `cla_resolve` searches only the assemblies already present in the global table.

There is no recursive dependency loader.

Therefore callers must load dependencies before dependents.

The same broad policy currently applies to CLS imports.

## Garbage collector architecture

The GC is a compact stop-the-world mark/sweep collector with a small nursery optimization.

Global limits are:

    GC_MAX     = 4096 objects
    GC_NURSERY = 65536 bytes
    roots      = 256 slots
    types      = 256 descriptors

Every object record stores:

    type_id
    size
    marked
    nurs
    payload

Object metadata lives in a global fixed table.

Payload storage is either:

- inside the static nursery for small allocations;
- or a heap allocation through malloc/kmalloc.

## Allocation

`gc_alloc(type_id, size)` normalizes a zero request to eight bytes.

If registered type metadata declares a larger size, the type size wins.

Small objects of at most 256 bytes use the nursery while enough nursery space remains.

Other objects use the backing allocator.

New payload is zero-filled.

When the object table reaches GC_MAX, allocation invokes a collection and retries table capacity.

Nursery exhaustion by itself does not trigger a collection.

Once the 64-KiB nursery fills, later small allocations fall back to the normal heap as long as object-table capacity remains.

## Roots

Roots are explicit host slots.

`gc_root_reg(void **slot)` stores the address of a pointer variable.

During collection, the collector reads the current pointer from each registered slot and marks it if it exactly equals a managed object's payload address.

This means a root is not the object pointer itself; it is the address of a variable that may later be updated when an object moves.

The root table has capacity 256.

There is no root-unregister API.

## Current root integration is incomplete

Repository search at the documented revision finds production implementation/declaration of `gc_root_reg`, but its actual use is visible only in `tools/test_cla_gc.c`.

The CLVM operand stack, CLVM guest memory, ChrisC globals, process stacks and TLS are not registered/scanned as GC roots by `gc_collect`.

This has a direct consequence for the CLVM `gc_alloc` builtin.

Syscall ID 70 allocates through the GC and returns the resulting **native pointer value** as an integer to the guest.

If the guest stores that value in CLVM memory or keeps it on the CLVM operand stack, the collector does not recognize those locations as roots.

An explicit `gc_collect` can therefore reclaim the object even though guest code still holds the pointer-like value.

The current GC integration must not be described as a complete managed-memory system for CLVM programs.

## Pointer-domain mismatch

The GC returns native host/kernel addresses.

Ordinary CLVM LOAD/STORE instructions expect guest offsets into `vm->memory`.

Therefore the result of `gc_alloc` is not interchangeable with the result of CLVM `malloc`.

This mismatch is documented in the memory and syscall chapters and is especially important here: even before root tracking is solved, managed references need a defined address representation that CLVM instructions can safely consume.

## Type-guided marking

GC type metadata carries a 32-bit `gc_bits` mask.

Bit N means pointer-sized field N should be considered a managed reference.

When metadata exists and `gc_bits != 0`, marking scans only those selected slots.

Otherwise the collector conservatively scans every pointer-sized position in the payload.

A candidate counts as a reference only when it exactly equals the payload start of an object currently present in the object table.

Interior pointers are not recognized.

## Complexity of marking

`is_ptr` performs a linear scan over all live objects.

For each candidate field it can therefore cost O(N).

If an object graph contains F candidate pointer fields, mark traversal can approach:

    O(F * N)

with N <= 4096.

For the current small experimental heap this is simple and predictable enough, but it does not scale like a hash table, address-ordered tree or page metadata lookup.

## Nursery promotion

During collection, a marked nursery object is copied into a fresh normal heap allocation.

Registered root slots that point directly to the old nursery address are updated to the promoted address.

The object's record is then retained with:

    nurs = 0

After sweeping, the nursery allocation cursor resets to zero.

This is a copying promotion phase combined with mark/sweep for non-nursery objects.

## Missing reference rewriting during promotion

The promotion implementation updates explicit root slots only.

It does **not** rewrite managed references stored inside other marked objects.

Consider:

    root -> object A -> nursery object B

The marker can discover B through A.

During sweep B is promoted to a new allocation.

The root is not pointing to B, so no root update occurs.

A's field still contains B's old nursery address.

Then:

    g_nused = 0

allows that nursery region to be reused.

The graph now contains a stale reference.

This is a major correctness gap in the current moving-nursery design.

Promotion needs a forwarding map plus a pointer-rewrite pass over all roots and live objects, or nursery objects must remain non-moving until a complete relocation algorithm exists.

## Promotion-OOM behavior

If allocation of promoted storage fails, current collection executes `continue` for that marked nursery object.

It does not preserve the object record in the compacted live prefix and does not repair a root that still points into the nursery.

The nursery cursor is still reset after the collection.

Therefore an OOM during promotion can silently invalidate a live object rather than reporting a controlled collection failure.

A collector used as a safety boundary needs an explicit failure policy.

## Collection triggers

There are three trigger concepts:

1. direct `gc_collect()`;
2. deferred request through `gc_request()` + `gc_poll()`;
3. automatic collection when the object table reaches GC_MAX.

ChrisOS installs `lang_safepoint` as the VM safepoint callback, and that function calls `gc_poll`.

The JIT also preserves the safepoint callback path.

However, repository search finds no current caller of `gc_request()` outside the GC implementation itself.

Therefore normal safepoints generally poll a request flag that is never set.

They do not currently create periodic collection by themselves.

The active automatic pressure trigger is object-table exhaustion, plus explicit `gc_collect` calls.

## Safepoints and stop-the-world semantics

The GC's global tables have no internal locking.

Collection mutates:

- object records;
- root pointers;
- nursery state;
- type metadata indirectly through library lifecycle.

The design therefore assumes coordinated execution rather than concurrent marking with mutators.

Safepoints provide a natural place for future stop-the-world coordination, but current `gc_poll` is only a request check.

There is no multi-thread handshake that proves every CLVM thread or kernel mutator has stopped before collection.

## Root-table lifetime

Because roots cannot be unregistered, a root registration is effectively permanent until `gc_init`.

Registering the address of a short-lived stack variable would become unsafe after that stack frame disappears.

The existing test keeps its root variable alive for the duration of collection.

A production API needs either:

- scoped root registration/unregistration;
- handles;
- shadow stacks;
- compiler-generated stack maps;
- or conservative scanning of a stable root region.

## Global initialization

`gc_init` resets objects, roots, nursery usage, requests and type metadata.

`cls_runtime_init` frees CLS code/data buffers, resets the library table, resets type-base allocation and calls `gc_type_clear`.

It does not call `gc_init`.

In normal startup, zero-initialized GC globals make the initial state usable, but the two reset APIs have different semantics.

Calling `cls_runtime_init` while managed objects remain alive would erase type metadata without clearing those objects/root registrations.

This lifecycle dependency should be made explicit if runtime reinitialization becomes a supported operation.

## CLS and GC type IDs

Every newly loaded CLS library gets:

    type_base = g_next_type_base

Its types receive consecutive IDs:

    type_base + 0
    type_base + 1
    ...

The global base then advances by the number of types, or at least one when the library declares none.

This prevents ordinary new-library type-ID collisions during a runtime session.

There is no reclamation/reuse of type-ID ranges because libraries are not unloaded individually.

## No library unload path

The public runtime provides load, reload, find, get, resolve, map and count.

There is no `cls_runtime_unload`.

Libraries persist until `cls_runtime_init`.

This simplifies pointer/ID stability but means:

- library slots cannot be reclaimed individually;
- code/data lifetime is process-wide/runtime-wide;
- type-ID ranges never return to the pool;
- dependency lifetime cannot currently be expressed.

With only 16 slots, long-running dynamic load workflows can exhaust the library table.

## Security and trust boundary

CLS and CLA files can come from the filesystem and therefore require defensive parsing.

Current positive properties include:

- fixed table-count limits;
- complete file-length checks for table and section framing;
- code-size limit;
- ABI/dependency checks;
- IL verification for CLA methods;
- bounded syscall path copies.

Important remaining gaps include:

- CLS export PCs not validated against code_size;
- no cryptographic authenticity/signature model;
- no complete import relocation/call verifier;
- only the first eight code pages mapped per process;
- runtime structures are global and not strongly isolated per application;
- GC native pointers do not form a safe CLVM reference model;
- moving nursery promotion does not rewrite object-to-object references.

## Validation evidence

`tools/test_cls.c` verifies:

- CLS write/parse round trip;
- ABI-major compatibility behavior;
- runtime load/reload when the temporary path is available;
- integration with GC type registration.

`tools/test_cla_gc.c` verifies:

- IL verification for a small method;
- GC allocation;
- root registration;
- survival of a rooted object across collection;
- reclamation after clearing that root;
- CLA write/load;
- basic assembly reference resolution.

ChrisC include and multi-file behavior is covered by dedicated include/application/compiler tests elsewhere in the host test suite.

These tests establish useful component behavior, but they do not yet cover the integration gaps identified above.

## Missing focused tests

High-value additions include:

- rooted A -> nursery B graph surviving promotion with A's field rewritten;
- promotion allocation failure;
- CLVM-held GC reference across explicit collection;
- root registration lifetime/unregistration;
- GC behavior with 256 roots and 4096 objects;
- CLS export PC >= code_size rejection;
- CLS mapping for code larger than 32 KiB;
- hot reload with changed type size/gc_bits;
- hot reload with preserved data and increasing ABI minor;
- import resolution followed by an actual executable cross-library call;
- exhaustion/recovery behavior for all 16 library slots;
- concurrent or multi-thread safepoint/collection behavior.

## Current limitations

At the documented revision:

- compile-time includes and `.LST` composition are more complete than runtime linking;
- every defined ChrisC function may be emitted as a CLS export;
- ordinary `mk_clv --cls` does not populate imports, types or data;
- CLS validates imports but does not patch normal ChrisC call sites;
- `cls_runtime_resolve` has no current consumer;
- CLS has no individual unload API;
- valid CLS code can be up to 512 KiB while process mapping caps code at eight pages/32 KiB;
- export PCs are not validated against the code section;
- reload does not update registered GC type metadata;
- GC roots are explicit host pointer slots and production CLVM roots are not integrated;
- GC references use native pointers rather than CLVM guest offsets;
- nursery promotion rewrites roots but not references inside live objects;
- promotion OOM has no safe recovery path;
- `gc_request` has no active caller, so safepoint polling does not currently schedule normal collections;
- root registrations cannot be removed;
- GC metadata and runtime tables are global and unprotected by collector-level locks;
- CLA dependency resolution is ordered and non-recursive.

## Roadmap boundary

A coherent future runtime could unify these pieces around one module contract:

    source/interface metadata
        -> versioned module image
        -> verified imports/exports/types
        -> stable call indirection
        -> process mapping
        -> managed root metadata
        -> hot reload / unload

Useful implementation steps include:

- generate explicit export/import/type metadata from ChrisC;
- add verified cross-library call stubs or a resolver opcode;
- validate all CLS export PCs and call targets;
- map the full accepted code section with explicit RX permissions;
- add unload with dependency and type-lifetime rules;
- preserve/reconcile GC type metadata on reload;
- introduce a real managed-reference representation for CLVM;
- use compiler stack maps or VM stack scanning for roots;
- add scoped root handles;
- implement forwarding and object-field rewriting for nursery promotion;
- define collection failure behavior;
- add stop-the-world coordination for CLVM threads;
- connect allocation pressure to `gc_request`/safepoints.

These are future directions until present in source and tests.

## Source map and revision

`compiler/gc/gc.c` and `gc.h` implement the object table, nursery, root table, type registry and collection algorithm.

`compiler/cls/cls.c` and `cls.h` implement the versioned CLS image, dependency checks, load/reload runtime, process mapping and GC type registration.

`compiler/cla/cla.c` and `cla.h` implement the IL assembly image and load-time method/reference validation.

`compiler/il/il.c` and `il.h` provide CLA method verification.

`compiler/chrisc/chrisc.c` and `chrisc.h` implement include expansion, multi-file compilation, ABI metadata and export collection.

`compiler/lang_pipeline.c` connects source compilation, CLS initialization, process mapping and GC safepoint polling.

`kernel/lang/clvm_sys.c` exposes `gc_alloc`, `gc_collect`, `cla_load`, `lib_load` and `lib_reload` to CLVM programs.

`tools/mk_clv.c`, `tools/test_cls.c` and `tools/test_cla_gc.c` provide the main build/test evidence for these runtime layers.

All current-behavior claims in this chapter were reconciled against ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.
