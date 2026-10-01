---
id: clvm-syscalls
lang: en
type: technical-chapter
volume: 07-language-systems
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/chrisc/chrisc.c
  - compiler/clvm/clvm.h
  - compiler/clvm/clvm_vm.c
  - compiler/clvm/clvm_vm.h
  - compiler/jit/jit_runtime.c
  - compiler/lang_pipeline.c
  - compiler/lang_pipeline.h
  - kernel/lang/clvm_sys.c
  - kernel/lang/clvm_sys.h
  - kernel/metal/proc.c
  - kernel/metal/proc.h
  - kernel/net/sock.c
  - kernel/gfx/shader/sh_api.c
symbols:
  - builtins
  - builtin
  - clvm_sys_dispatch
  - clvm_sys_close_slot
  - vm_bytes
  - vm_cstr
  - vm_copy_in
  - vm_copy_out
  - guest_read
  - guest_write
  - sys_fopen
  - sys_fclose
  - sys_fread
  - sys_fwrite
  - fd_owned
  - drv_cap
  - vm_sync_slot
  - clvm_threads_tick
  - jit_rt_sys
depends_on:
  - clvm-bytecode
  - clvm-memory
related:
  - clvm-interpreter
  - calling-conventions
  - processes-syscalls
  - network-stack
  - shaders-csir
  - gc-libraries
---

# CLVM syscalls and host-service ABI

## Scope

CLVM bytecode is intentionally small. Most operating-system and application services are not encoded as dedicated VM opcodes. Instead, ChrisC lowers service calls to the generic `SYS` bytecode instruction and passes a numeric service ID.

The service boundary connects four layers:

    ChrisC source builtin
        -> numeric Builtin ID
        -> CL_OP_SYS
        -> clvm_sys_dispatch
        -> ChrisOS subsystem

This chapter documents that boundary as an ABI rather than as a catalog of convenience functions.

The critical properties are:

- how arguments and return values use the operand stack;
- how guest pointers are validated before kernel access;
- which resources are owned per slot;
- which services can block;
- how capabilities gate privileged hardware access;
- what errors become guest-visible return values versus VM faults;
- which parts of the current surface are internally inconsistent.

![CLVM syscall path](../../assets/diagrams/clvm-syscalls-en.svg)

## The `SYS` instruction

`CL_OP_SYS` has opcode `0x20`.

It has no immediate operand.

The syscall number is itself on the VM operand stack.

For a normal ChrisC builtin call, code generation evaluates arguments in source order, then pushes the builtin numeric ID, then emits `SYS`.

For a conceptual call:

    service(a, b, c)

the stack immediately before `SYS` is:

    ... | a | b | c | service_id

The core interpreter first pops service_id.

clvm_sys_dispatch then pops the service arguments in reverse order:

    c, b, a

This is why dispatcher cases frequently appear as:

    pop(c)
    pop(b)
    pop(a)

even though the source-level order is a, b, c.

A service with a result pushes that result back on the same operand stack.

A service declared void should leave no result.

## Dispatcher return code versus guest return value

Two different return channels exist.

The C return value of clvm_sys_dispatch is internal control status.

- `0` means the dispatcher completed the SYS operation from the VM engine's perspective.
- nonzero means the VM engine treats the service invocation as rejected.

In the interpreter:

    if sys(...) != 0
        -> CLVM_FAULT_BAD_SYS

That is separate from a guest-visible service result.

Many normal service failures therefore do this:

    push(-1)
    return 0

The VM continues running and the ChrisC program receives -1.

By contrast:

    return -1

without first translating the condition into a guest result causes the `SYS` instruction itself to fault.

This distinction is part of the ABI and should not be blurred.

## JIT equivalence

The JIT uses jit_rt_sys for generic SYS handling.

jit_rt_sys pops the syscall ID and calls the same vm->sys callback for ordinary services.

ID 1, the pixel primitive, has a specialized fast path in the JIT runtime.

For all other generic calls, the dispatcher remains the semantic authority.

Therefore changes to syscall argument order, result shape, resource ownership or blocking behavior must remain compatible with both the switch interpreter and generated native execution.

## Dispatcher precondition: graphics context

clvm_sys_dispatch currently begins by requiring:

    vm != NULL
    ctx != NULL
    ctx->pixels != NULL

If any is false, it returns -1 before examining the service ID.

This means the present syscall surface is not a headless generic kernel-service interface.

Even services that are logically unrelated to graphics—files, sockets, crypto, malloc, threads, hardware I/O—are routed through a dispatcher that requires a valid ClvmGfxCtx with pixels.

The normal desktop CLVM path satisfies this condition.

A future command-line/headless CLVM environment would need either a minimal context, dispatcher refactoring, or a separate service layer.

## Compiler registry

ChrisC describes services with:

    struct Builtin {
        name
        id
        argc
        returns
        ret_float
    }

The builtin table is a compile-time language ABI.

The `builtin(name)` lookup scans the table from beginning to end and returns the first matching name.

At the documented revision there are:

- 173 Builtin entries;
- 173 corresponding numeric dispatcher cases;
- 172 unique builtin names.

The difference is a duplicated name described later in this chapter.

## Service surface by subsystem

The table below groups the implemented registry. It is a map of the current surface, not a statement that every service has identical maturity.

| IDs | Subsystem | ChrisC builtin names |
|---|---|---|
| 1-6 | 2D drawing | pixel, rect, line, sprite, tilemap, clear |
| 10-13 | input/time/basic audio | key, ticks, wait, tone |
| 20-23 | 3D primitives | tri, mesh, transform, meshf |
| 30-41 | math/view/voxel | fps, sin, cos, cam, light, tex, voxel, voxel_get, world, viewport, screen_w, screen_h |
| 50-59, 61, 64-65 | files, allocation, nonlocal control, CLA | fopen, fclose, fread, fwrite, fsize, fexists, malloc, free, setjmp, longjmp, realloc, cla_load, fseek |
| 62-63 | threads | thrd_create, thrd_join |
| 70-73 | GC/framebuffer/palette | gc_alloc, gc_collect, fb_blit, setpal |
| 80-91 | mouse/events/surfaces | mouse_x, mouse_y, mouse_btn, ev_key, ev_text, fillrgb, text, glyph, surf_place, surf_move, surf_raise, surf_close |
| 92-112 | filesystem/apps/system | readdir, mkdir, unlink, rename, app_spawn, app_kill, app_count, app_info, sys_cc, sys_run, sys_make, disp_w, disp_h, sys_err, app_spawn_arg, app_arg, lib_load, lib_reload, isdir, kb_layout, kb_get |
| 113-126 | window state/telemetry/text | surf_resize, surf_minimize, surf_maximize, surf_restore, heap/PMM/frame/CFS/app metrics, app_raise, textruns |
| 127-134 | synchronization/TLS/state | mtx_lock, mtx_unlock, cnd_wait, cnd_signal, tls_get, tls_set, app_state, app_reload |
| 140-146 | sockets/DNS | sock_listen, sock_accept, sock_connect, sock_send, sock_recv, sock_close, dns_lookup |
| 150-153 | RNG/crypto | rng_u32, sha256, aes_encrypt, x25519 |
| 160 | PCM audio | pcm_write |
| 170-175 | low-level driver I/O | drv_outw, drv_inw, drv_outb, drv_inb, drv_irq, drv_pci |
| 180 | process heap | sbrk |
| 190-198 | scene/physics/animation | scene_add, scene_draw, phys_add, phys_step, anim_key, anim_apply, phys_x, phys_y, tex_ofs |
| 210-233 | PCI/MMIO/DMA/disk/GPU | pci_write, bar_map, mmio_r32/w32/r8/w8/r16/w16, dma_alloc/lo/hi/w32/r32, disk services, gpu_arm, gpu_ready |
| 240-243 | relative mouse | mouse_dx, mouse_dy, mouse_cap, mouse_rel |
| 250-251 | debugger | dbg_ctl, dbg_text |
| 260-274 | shader/program API | shader_make/ok/log/drop, prog_make/attach/link/ok/log/drop/uniloc/setf/samp, shader_vert, shader_frag |

The large numeric gaps are intentional consequences of subsystem growth; syscall IDs are not required to be contiguous.

## Float arguments

Most builtin arguments use integer stack values.

Float values are represented by their 32-bit bit pattern inside a VM stack slot.

The dispatcher helper pop_f pops an integer-sized VM value, reinterprets its low 32 bits as IEEE-754 float, and returns a native float.

ChrisC marks builtins with ret_float when code generation needs float result semantics.

The service ID itself remains integer.

## Guest pointers are offsets

Ordinary CLVM memory pointers are guest offsets into:

    vm->memory[0 .. vm->mem_size)

They are not arbitrary kernel C pointers.

A syscall that receives an address must validate it before dereferencing guest memory.

The dispatcher has several helpers for this.

### vm_bytes

vm_bytes validates an address and positive length and returns a pointer into guest RAM only after proving:

    address < mem_size
    length <= mem_size - address

This subtraction form avoids wraparound in address + length.

### vm_cstr

vm_cstr copies one byte at a time into a bounded kernel buffer.

It succeeds only when a NUL terminator is encountered before both the kernel capacity and guest-memory boundary.

This is used for many paths, shader sources/names and other text inputs.

### vm_copy_in and vm_copy_out

vm_copy_in copies a validated guest range into kernel-owned memory.

vm_copy_out copies kernel bytes into a validated guest range.

These helpers are preferable to directly holding a guest pointer while calling subsystems that may have different lifetime or blocking rules.

### guest_read and guest_write

The crypto, audio and some newer service families use uint64_t-offset helpers guest_read/guest_write.

They enforce the same basic complete-range requirement.

## Pointer-domain exceptions

Not every pointer-like service uses the ordinary guest-offset domain.

The current ABI contains at least three pointer domains.

### malloc

malloc returns an offset generated by clvm_guest_malloc.

That offset is directly usable by ordinary CLVM LOAD/STORE.

### gc_alloc

gc_alloc calls the kernel/compiler GC allocator and pushes the native pointer value cast to int64_t.

That is not a normal vm->memory offset.

Ordinary CLVM LOAD/STORE should not be assumed to dereference it safely.

### sbrk

sbrk calls proc_sbrk and returns a process virtual address in the process heap region beginning at PROC_HEAP_VIRT.

That is also distinct from the ordinary CLVM guest offset model.

The coexistence of guest offsets, managed native pointers and process virtual addresses is a current ABI complexity.

A stronger future ABI should tag or unify these representations rather than relying on the caller to know which operations accept which address class.

## File-descriptor model

CLVM implements a slot-owned file table in clvm_sys.c.

Important limits are:

    CLVM_FD_MAX = 32
    CLVM_FD_PER_SLOT = 8
    CLVM_FD_CAP = 65536
    CLVM_FD_MAX_BYTES = 16 MiB

Descriptors 0-2 are reserved by convention; fopen searches from descriptor 3.

fd_owned verifies that an opened descriptor belongs to the current graphics/application slot.

This prevents one ordinary CLVM slot from closing or reading another slot's buffered file descriptor.

stdout/stderr-style writes are a special case: fwrite to fd 1 or 2 copies validated guest bytes in chunks and mirrors them to serial output.

## fopen policy

sys_fopen:

1. copies the path from guest memory;
2. strips leading "./" segments;
3. rejects traversal-style `..` path components through path_ok;
4. enforces the per-slot descriptor limit;
5. checks CFS read/write permissions when CFS is available;
6. requires the target to already exist and be a file.

The current fopen does not create a missing file.

Small files are buffered in kernel memory.

Files larger than CLVM_FD_CAP use streaming reads instead.

Streaming descriptors reject the buffered fwrite path.

## Buffered write ownership

Buffered writes update the in-memory ClvmFile object and mark it dirty.

fd_free writes a dirty buffer back to the filesystem before releasing it.

clvm_sys_close_slot iterates all global descriptors and closes any descriptor owned by the slot.

Therefore slot teardown is part of filesystem durability for dirty CLVM buffers.

An abnormal path that bypassed clvm_sys_close_slot would risk losing buffered writes.

## Resource cleanup by slot

clvm_sys_close_slot currently performs several ownership cleanups:

- shader/program objects for the slot;
- voxel ownership;
- input capture;
- all sockets for the slot;
- all CLVM file descriptors for the slot.

This is a useful central lifecycle boundary.

However, the function does not iterate the global CLVM child-thread table.

That matters because child VMs are allocated separately and share parent code/memory.

If a slot is destroyed with live child CLVM threads, those entries are not visibly reclaimed by clvm_sys_close_slot at this revision.

lang_kill also releases slot RAM and later the CLV file backing.

A surviving child could therefore retain references to backing whose owner has been torn down.

This is a current lifecycle gap and should be fixed with explicit per-slot thread cancellation/join cleanup.

## Thread service model

The runtime supports up to:

    CLVM_TH_MAX = 32
    CLVM_TH_PER = 8

thrd_create allocates a new ClvmVm, copies the parent's code, memory, mem_size, sys callback, context and process identity, sets the child PC to the requested function, and pushes the thread argument onto the child operand stack.

Parent and child share guest RAM but have independent VM operand/call stacks.

The memory chapter documents the separate current bug that the child does not inherit/share the parent's heap_off allocator state.

thrd_join tracks a parent join_wait field and can put the parent into CLVM_WAITING until the child completes.

## Synchronization objects

mtx_lock/mtx_unlock and cnd_wait/cnd_signal use addresses inside shared guest RAM as synchronization-object locations.

A mutex word stores a small owner identity.

The runtime also records blocked child-thread metadata in g_th.

This design is lightweight but tightly couples synchronization correctness to the shared guest-memory model.

The guest is responsible for using valid aligned/appropriate storage locations and for following the expected lock protocol.

## Blocking services

Several services can transition a VM to CLVM_WAITING:

- wait;
- thrd_join;
- sock_recv when no data is currently available;
- drv_irq;
- mutex/condition paths.

wait is timer-oriented.

It sets wake_tick and returns YIELD from the VM engine until clvm_vm_wake observes that the requested time has arrived.

The other blocking handlers attempt a different convention: they push their original arguments and syscall ID back onto the operand stack before returning with VM state WAITING.

## Current retry-protocol inconsistency

The interpreter consumes the SYS opcode and advances vm->pc before calling the dispatcher.

When the dispatcher sets CLVM_WAITING, clvm_step returns CLVM_STEP_YIELD.

On wake, clvm_vm_wake changes state back to READY.

The inspected interpreter path does not rewind vm->pc to the SYS opcode.

The blocking handlers for sock_recv, thrd_join, drv_irq and synchronization calls restack arguments plus the syscall ID, apparently as preparation for a retry, but the next interpreter step resumes at the bytecode instruction after SYS.

The JIT generic syscall helper also invokes the dispatcher without establishing a visible retry-PC protocol.

Therefore the current source shows an incomplete continuation/retry contract for these restacked blocking syscalls.

This should be treated as a source-level correctness issue requiring dedicated regression tests and an explicit design, for example:

- rewind PC to the SYS instruction;
- store a pending syscall record outside the operand stack;
- or make the scheduler re-enter the pending syscall before normal bytecode execution.

Until then, blocking semantics beyond timer wait should not be described as fully settled.

## Socket ownership

Socket operations use vm_sync_slot to associate activity with an application slot.

sock_listen_for, sock_accept_for, sock_connect_for, sock_send_for, sock_recv_for and sock_close_for receive that owner.

clvm_sys_close_slot calls sock_close_slot, providing teardown of slot-owned sockets.

sock_send and sock_recv use a temporary 200-byte kernel buffer per dispatcher call.

Requested lengths above 200 are clamped.

Guest source/destination ranges are checked before copy.

A recv returning zero is interpreted as a condition that should block/retry rather than immediately exposing zero as an ordinary result.

That behavior is part of the retry inconsistency described above.

## DNS

dns_lookup copies a bounded guest C string into a 64-byte local name buffer and calls sock_dns.

The numeric IP result is pushed as an integer value.

The dispatcher currently discards the separate rc variable after the call and returns the resulting IP, with zero acting as the failure-like value.

## Cryptographic services

The current cryptographic surface includes:

- rng_u32;
- sha256;
- aes_encrypt;
- x25519.

These calls do not hand guest pointers directly into crypto implementations.

They copy fixed/bounded input into kernel-local arrays, run the primitive, then copy results back into validated guest memory.

sha256 accepts at most 256 bytes in one call.

AES operates on a 16-byte key/input/output block path.

x25519 copies 32-byte scalar and point values and writes a 32-byte result.

This copy-in/copy-out design is preferable to exposing mutable kernel operations directly over unchecked guest ranges.

## Graphics and surface ownership

Many early syscall IDs draw directly into the current ClvmGfxCtx pixel buffer.

sprite and tilemap validate guest-memory source extents before rendering.

Viewport changes can resize or allocate graphics slots.

Surface/window operations map the CLVM application to the desktop task/window model.

The dispatcher loads the slot's Gfx3DCtx at entry and uses a cleanup attribute to save it again when returning.

That avoids using another slot's 3D state as implicit global state for the call.

## Shader object ownership

Shader and program syscalls use fd_slot(user) as an owner key.

The shader subsystem receives this owner for compile, status, logs, deletion, program creation/linking and uniform/sampler operations.

clvm_sys_close_slot calls sh_guest_drop_owner(slot_id), giving this service family an explicit bulk-cleanup path.

Shader source is first copied from guest memory into a bounded kernel allocation before compilation.

Shader/program log functions copy results back through vm_copy_out.

## Application and filesystem administration

IDs 92-112 expose directory operations, application launch/kill/query, build/run helpers, library loading and keyboard configuration.

readdir copies a path into kernel memory, enumerates by index, then copies the selected name back to a guest destination.

mkdir, unlink and rename reject path traversal through path_ok.

app_spawn runs another CLVM path.

app_kill works through the task/slot model rather than arbitrary process memory.

sys_cc/sys_make can trigger compilation/build workflows from inside the environment; these are high-level OS services rather than traditional narrow POSIX syscalls.

## Hardware capabilities

Low-level hardware operations are capability-gated.

The capability bits are:

    CAP_PCI        = 1
    CAP_PORT_IO    = 2
    CAP_MMIO       = 4
    CAP_DMA        = 8
    CAP_IRQ        = 16
    CAP_DISK_ADMIN = 32

CAP_DRIVER is the union of all six.

Examples:

- pci_write requires CAP_PCI;
- bar_map requires CAP_MMIO;
- dma_alloc requires CAP_DMA;
- disk installation/metadata administration uses CAP_DISK_ADMIN;
- many raw MMIO, port, IRQ and disk operations require CAP_DRIVER.

This is substantially safer than exposing all hardware primitives to every CLVM application.

## Capability grant policy

The current launch policy assigns:

    CAP_DRIVER

when path_is_driver(name) recognizes a path containing the SYS/DRV pattern.

Other ordinary CLVM programs receive zero capabilities.

This is a pathname-based trust policy.

It is not cryptographic code identity, signature verification, a manifest-declared permission prompt or a CFS ACL-derived capability grant.

Therefore security depends on who can create/modify executable content under the recognized driver path and on the filesystem policy surrounding that location.

A hardened design should bind privilege to explicit authenticated metadata rather than only to a path convention.

## Hardware-service handles

MMIO and DMA services generally avoid handing raw physical addresses directly to arbitrary guest code.

bar_map returns a managed window/handle.

Subsequent mmio calls use a window ID plus offset.

DMA allocation similarly returns an ID and exposes operations such as dma_lo, dma_hi, dma_w32 and dma_r32.

This indirection gives the kernel a place to validate resource ownership and bounds.

The exact hwgate policy is separate from the CLVM syscall ABI, but the syscall boundary is responsible for capability checks before entering it.

## Disk service naming inconsistency

The compiler builtin registry contains two entries with the same source-level name:

    {"disk_sectors", 223, 0, 1, 0}
    {"disk_sectors", 233, 1, 1, 0}

Both numeric IDs have dispatcher cases.

However, builtin(name) performs a forward linear scan and returns the first matching name.

Therefore an ordinary ChrisC lookup of `disk_sectors` resolves to ID 223 with zero arguments.

The later one-argument ID 233 entry is not reachable through that same builtin name by normal lookup.

This is an ABI registry defect.

The two operations should have distinct names, or the intended one should replace the other explicitly.

## fclose stack-contract mismatch

The compiler table declares:

    {"fclose", 51, 1, 0, 0}

The `returns` field is zero, so ChrisC code generation treats fclose as a void builtin.

The dispatcher case for ID 51 nevertheless does:

    push(sys_fclose(...))

and returns success.

That leaves an extra operand-stack value for a call the compiler says produces no expression value.

This is a direct compiler/runtime ABI mismatch.

The fix should choose one contract:

- make fclose return a status and mark returns=1;
- or keep it void and stop pushing the dispatcher result.

A regression test should verify stack depth across repeated fclose calls.

## Error patterns

The dispatcher currently uses several guest-visible conventions:

| Pattern | Typical meaning |
|---|---|
| -1 | invalid resource, operation failure or permission/capability failure |
| 0 | false/not found/no result, or success for some operations |
| positive integer | handle, count, success flag, size or ID |
| service-specific | IP address, pointer-like value, timestamp, metric |

This is not a uniform errno ABI.

Some services use -1 for failure, others use zero.

Void services may not expose any guest result.

The source-level builtin signature is therefore part of interpreting each service's result.

## VM-fault boundary

Structural ABI failures can fault the VM.

Examples include:

- syscall ID missing from stack;
- handler argument underflow;
- invalid ID reaching default;
- helper/dispatcher path returning -1 instead of guest error.

In those cases the VM records CLVM_FAULT_BAD_SYS for the SYS operation.

By contrast, many anticipated operational failures are encoded as pushed -1/0 values and leave VM state runnable.

A debugger should display both the VM fault and recent syscall trace because the distinction matters.

## Syscall trace

The dispatcher maintains a ring of recent service IDs and slot IDs.

SYS_TRACE is 32.

Each invocation records:

    id
    slot

before entering the switch.

clvm_sys_trace retrieves recent entries.

The debugger exposes syscall trace text through the debugging API.

This is useful for diagnosing incorrect IDs, blocked operations, capability failures and stack-contract mismatches without tracing the complete interpreter.

## Performance

A syscall incurs at minimum:

1. operand-stack service-ID pop;
2. C callback dispatch;
3. switch lookup/branch;
4. argument pops;
5. subsystem work;
6. optional result push.

For drawing primitives, this overhead can matter when invoked per pixel or per tiny primitive.

The JIT therefore has a special case for pixel ID 1, but most services still cross the generic callback.

Buffer-oriented services reduce crossings by accepting guest ranges, for example sprite, tilemap, file I/O, PCM and crypto.

Copy-in/copy-out adds O(n) cost but provides a clearer protection boundary.

File buffering trades memory for fewer filesystem operations.

## Concurrency

Global syscall state includes:

- g_fds;
- g_th;
- palette storage;
- syscall trace ring;
- subsystem-global resources reached by the dispatcher.

Ownership is often expressed by slot IDs, but the dispatcher itself is not a purely reentrant stateless function.

CLVM scheduling is cooperative/sliced at the VM level, while ChrisOS itself can run on SMP.

Subsystem locking therefore matters for any service that reaches globally shared kernel state.

The syscall ABI should not imply stronger thread safety than the called subsystem actually provides.

## Validation evidence

The repository contains extensive tests for ChrisC code generation, CLVM interpreter behavior, JIT equivalence, filesystems, graphics, crypto and lower-level subsystems.

The compiler's builtins table and the dispatcher can be mechanically cross-checked: at this revision all 173 builtin numeric IDs have matching dispatcher cases.

The documentation build also validates source-symbol references and the overall technical corpus.

However, the inspected test set does not expose a dedicated host-side regression suite that directly drives clvm_sys_dispatch across all 173 service IDs.

In particular, dedicated tests should be added for:

- compiler/runtime stack balance for fclose;
- duplicate builtin-name detection;
- blocked syscall resume/retry semantics;
- teardown with live child CLVM threads;
- capability grant/rejection paths;
- invalid guest ranges for each buffer-bearing syscall family.

## Current limitations

At the documented revision:

- the syscall dispatcher requires a graphics context even for non-graphics services;
- the ABI has 173 entries but only 172 unique builtin names because disk_sectors is duplicated;
- ID 233's one-argument disk_sectors form is shadowed by the earlier source-level name;
- fclose is declared void by the compiler but pushes a result in the dispatcher;
- blocking syscall retry semantics are incomplete in the inspected interpreter/JIT contract;
- slot teardown does not visibly reclaim live child CLVM thread entries;
- guest-offset pointers coexist with native GC pointers and process-virtual sbrk pointers;
- capability grant for the full driver set is based on a SYS/DRV pathname convention;
- error returns are service-specific rather than one uniform errno model;
- syscall IDs are hard-coded in both compiler and dispatcher instead of generated from a single schema;
- there is no version-negotiated syscall capability table in the CLV image;
- no dedicated exhaustive dispatcher conformance test is evident.

## Roadmap boundary

A stronger syscall architecture could introduce one machine-readable service schema that generates:

- ChrisC builtin declarations;
- numeric ID constants;
- dispatcher prototypes;
- argument/return metadata;
- documentation tables;
- conformance tests.

It could also add:

- explicit syscall ABI versioning;
- typed pointer-domain descriptors;
- a uniform error/errno convention;
- headless service contexts;
- scheduler-owned pending-syscall records for blocking operations;
- automatic per-slot cleanup of threads and other handles;
- capability manifests signed or authenticated independently of pathname;
- duplicate-name/duplicate-ID build failures;
- generated stack-effect verification.

These are future directions until implemented in source.

## Source map and revision

compiler/chrisc/chrisc.c defines the Builtin registry, builtin lookup and SYS code generation.

compiler/clvm/clvm_vm.c defines core SYS execution and CLVM_FAULT_BAD_SYS behavior.

compiler/jit/jit_runtime.c provides the JIT-side generic SYS bridge.

kernel/lang/clvm_sys.c implements the service dispatcher, guest-memory marshalling, file/thread/socket state, capability checks and service-specific logic.

compiler/lang_pipeline.c and compiler/lang_pipeline.h define slot ownership, capability assignment and teardown integration.

All current-behavior claims in this chapter were reconciled against ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.
