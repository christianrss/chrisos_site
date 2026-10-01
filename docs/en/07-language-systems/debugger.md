---
id: debugger
lang: en
type: technical-chapter
volume: 07-language-systems
status: expanded
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - compiler/debug/cdbg.h
  - compiler/debug/cdbg.c
  - compiler/debug/dbg_session.h
  - compiler/debug/dbg_session.c
  - compiler/chrisc/chrisc.h
  - compiler/lang_pipeline.c
  - compiler/lang_pipeline.h
  - compiler/clvm/clvm_vm.h
  - compiler/clvm/clvm_vm.c
  - kernel/lang/clvm_sys.c
  - APPS/EDITOR/EDITOR.CC
  - tools/test_cdbg.c
  - tools/test_dbg_step.c
  - tools/test_editor_vi.c
symbols:
  - CdbgImage
  - cdbg_encode
  - cdbg_decode
  - cdbg_from_result
  - cdbg_line_at
  - cdbg_func_at
  - cdbg_parse_map_line
  - DbgSession
  - dbg_session_create
  - dbg_session_add_break
  - dbg_session_resolve
  - dbg_session_add_watch
  - dbg_step_should_pause
  - lang_write_map
  - lang_load_map
  - lang_begin_step
  - lang_debug_step
  - lang_debug_step_over
  - lang_debug_step_out
  - lang_debug_continue
  - lang_bp_toggle_line
  - lang_debug_ctl
  - lang_debug_text
depends_on:
  - clvm-interpreter
  - jit
  - chrisc-clvm
related:
  - clvm-syscalls
  - calling-conventions
  - process-lifecycle
  - native-toolchain
---

# Debugger, source maps and execution control

## Scope

ChrisOS contains a source-level debugger for ChrisC/CLVM applications, integrated with the ChrisOS Editor and the language runtime.

The debugger is not a conventional hardware debugger. It does not program x86 debug registers, patch INT3 instructions into native code or attach through ptrace. Its primary target is a ClvmVm instance.

The live path is:

    ChrisC compiler
        -> source/PC map
        -> .MAP sidecar
        -> LangSlot debug state
        -> interpreter single-step
        -> Editor dbg_ctl / dbg_text UI

A second, more structured architecture also exists:

    ChrisResult
        -> .CDBG binary metadata
        -> CdbgImage
        -> DbgSession

At the documented revision, that second path is implemented and unit-tested but is not yet the metadata/session mechanism used by the live lang_pipeline debugger.

![ChrisOS debugger architecture](../../assets/diagrams/debugger-en.svg)

This split is the most important fact for understanding the current debugger: the repository already contains the beginnings of a session-oriented debugger, while the production Editor path still uses older global/per-slot structures.

## Why debugging forces interpreter execution

A CLVM application normally prefers the JIT when available.

During a debug launch, Editor first enables g_want_debug through dbg_ctl, then invokes compilation and sys_run.

lang_run_internal observes g_want_debug and does not select the JIT.

The created slot receives:

    debug_on = g_want_debug
    paused   = g_want_debug

The Editor then clears the global launch flag.

Therefore g_want_debug is a launch-time policy flag, while LangSlot.debug_on is the persistent state of the newly created target.

The target remains interpreter-driven while debugging.

This matters because breakpoints and line stepping rely on calling clvm_step with a budget of one instruction.

## Debug launch sequence

The Editor's do_debug path is approximately:

1. save dirty source;
2. set debugger launch mode with dbg_ctl(1, 1);
3. compile the file;
4. derive the .CLV output path;
5. call sys_run;
6. clear the global debugger-launch flag;
7. mark the Editor UI as debugging;
8. query the current source line and follow it.

The target application starts paused.

The Editor is a separate CLVM application and controls the target through debug syscalls rather than directly sharing its ClvmVm structure.

## Guest debugger ABI

The ChrisC builtin table exposes:

    dbg_ctl(op, arg)  -> syscall 250
    dbg_text(kind, dst) -> syscall 251

Both return an integer status/value.

dbg_ctl is a numeric multiplexed control API.

The implemented opcodes are:

| op | Operation |
|---:|---|
| 0 | query whether any slot is paused |
| 1 | set debugger launch mode |
| 2 | step into |
| 3 | step over |
| 4 | step out |
| 5 | continue |
| 6 | detach |
| 7 | toggle source-line breakpoint |
| 8 | set memory-watch base address |
| 9 | current PC |
| 10 | current source line |
| 11 | operand-stack depth |
| 12 | stack value by depth |
| 13 | return PC by call depth |
| 14 | read 32-bit guest memory |
| 15 | read one guest byte |
| 16 | recent syscall ID |
| 17 | whether a process fault is recorded |
| 18 | recorded fault RIP/PC |
| 19 | guest-memory size |
| 20 | current watch address |

There is currently no shared typed enum exposed to guest ChrisC code and no debugger ABI version negotiation.

The meaning of these numeric operations is therefore defined by the implementation.

## Text debugger ABI

dbg_text requests a small formatted textual record.

Current kinds include:

| kind | Text |
|---:|---|
| 0 | line, PC, function, stack depth, breakpoint count and state |
| 1 | top stack values |
| 2 | first watched-memory hex row |
| 3 | second watched-memory hex row |
| 4 | pending breakpoint line numbers |
| 5 | recent syscall IDs |
| 6 | last process fault summary |

The kernel-side temporary buffer is 96 bytes.

The ABI takes only kind and destination address; it does not take destination capacity.

vm_copy_out verifies that the resulting byte range lies inside guest memory, but cannot know the size of the guest object supplied by the caller.

A future debugger ABI should include an explicit destination capacity.

## Source map generation

ChrisC records source mapping in ChrisResult.

The relevant limits are:

    CHRIS_MAP_MAX  = 8192
    CHRIS_FILE_MAX = 32

Each ChrisMapEnt contains:

    pc
    line
    file_id

ChrisResult also carries up to 64 exported function names, entry PCs and argument counts.

lang_write_map emits a text .MAP file next to the CLV image.

Line records have the form:

    0x<pc> <line> <file_id>

Function records have the form:

    F <name> <pc>

The file ID therefore exists in generated line metadata.

## Runtime .MAP ingestion

lang_load_map reads the text sidecar into:

    char buf[8192]

and asks fs_read for at most sizeof(buf) - 1 bytes.

The live debugger can therefore ingest at most 8191 bytes of text-map data per program.

This is far below the compiler-side theoretical CHRIS_MAP_MAX capacity for nontrivial programs.

A sufficiently large map is silently represented only by the prefix that fits this buffer.

The slot then stores parsed entries in:

    map_pc[CHRIS_MAP_MAX]
    map_line[CHRIS_MAP_MAX]
    map_file[CHRIS_MAP_MAX]

but the input buffer becomes the actual earlier limiting factor.

This can make later source lines unavailable to breakpoints and stepping even though the compiler generated them.

## Function-name map limits

The live LangSlot stores:

    fn_name[16][24]
    fn_pc[16]

Only 16 function records are loaded from .MAP.

Names are truncated to 23 characters plus NUL.

By contrast, ChrisResult can expose 64 functions with 31-character names, and CDBG_FUNCS is 64.

The live debugger therefore has a narrower function-symbol view than both compiler output and the structured CDBG design.

## PC-to-line lookup

lang_line_at scans source-map entries in increasing PC order and remembers the most recent entry satisfying:

    map_pc[i] <= pc

It stops at the first later PC.

Complexity is O(n) per lookup in the number of loaded map entries.

Line stepping calls this repeatedly after individual VM instructions.

For large maps this can become a material debugger overhead.

A binary search would reduce lookup to O(log n), and an index/cache could make sequential stepping close to O(1).

## File IDs are loaded but not used by the live debugger

map_file is populated by lang_load_map.

However, the main line-lookup, stepping and breakpoint code currently makes decisions using line number alone.

lang_line_at returns only uint16_t line.

lang_begin_step stores only last_line.

lang_arm_line searches:

    map_line[i] == requested_line

and takes the first matching entry.

The file ID is ignored.

As a result, multi-file programs can contain ambiguous source-line numbers.

For example, line 20 in SRC/MAIN.CC and line 20 in LIB/UTIL.CC are distinct source locations, but a pending line-20 breakpoint does not encode that distinction.

This is one of the major reasons the structured DbgBreak type already includes both file_id and line.

## Breakpoint representation in the live debugger

Each LangSlot contains:

    uint32_t breakpoints[32]
    int nbreak

These are resolved bytecode PCs.

The global pending set contains:

    int g_pend_line[32]
    int g_pend_n

Pending breakpoints are source-line numbers only.

When a debug target launches, each pending line is resolved through lang_arm_line.

lang_arm_line selects the first source-map PC for that line and places it into the slot's breakpoint array.

If one source line maps to multiple bytecode ranges, only the first matching PC is armed.

## Breakpoint check

Before executing the target in lang_tick, the debugger performs a linear scan over active breakpoint PCs.

If one equals vm.pc:

    paused = 1
    step_one = 0
    step_line = 0
    step_mode = NONE

and ordinary execution is skipped.

Checking is O(B), where B <= 32.

This is small enough for the current implementation.

No bytecode patching is required; the target code remains immutable.

## Continue re-hit behavior

A persistent breakpoint has an important current limitation.

Suppose execution stops with:

    vm.pc == breakpoint_pc

lang_debug_continue clears paused but does not move pc, disable the breakpoint once, or record an ignore-once token.

On the next lang_tick, the pre-execution breakpoint scan sees the same pc and pauses again before executing the instruction.

Therefore plain continue from a persistent breakpoint can immediately re-hit that same breakpoint.

Step operations can escape because step_line remains set, allowing the step path to execute despite the breakpoint scan setting paused.

A complete debugger needs one of the standard mechanisms:

- temporarily suppress the current breakpoint for one instruction;
- advance one instruction before re-enabling it;
- or represent breakpoint hit state with an ignore-once PC.

## Step modes

The helper dbg_step_should_pause defines three source-level policies.

Step in:

    pause when line != start_line

Step over:

    pause when depth <= start_depth
    and line != start_line

Step out:

    pause when depth < start_depth

Depth is ClvmVm.csp, the CLVM return-PC stack depth.

This makes the implementation compact and aligns step-over/out with source function calls implemented through the VM call stack.

## Step execution loop

lang_begin_step captures:

    last_line
    step_mode
    step_depth

and unpauses all debug_on slots.

lang_tick then executes the interpreter with budget 1 repeatedly.

The hard limits are:

    step in:   512 instructions
    over/out: 8192 instructions

After the loop, the slot is paused unconditionally.

Therefore a step command can stop because:

- the requested source/depth condition was satisfied;
- the VM halted;
- the VM faulted;
- or the instruction limit was exhausted.

The UI does not currently expose which of those reasons caused the pause.

## Waiting during source stepping

The stepping loop explicitly breaks only on HALT or FAULT before evaluating source/depth conditions.

CLVM_STEP_YIELD is not treated as an immediate loop terminator.

If a stepped instruction places the VM into WAITING, subsequent clvm_step calls return YIELD while no source progress occurs.

The loop can therefore consume its remaining 512/8192 iterations and then pause the target.

This is bounded, but it is not a scheduler-aware asynchronous stepping model.

A future implementation should suspend the step request and resume it after the target wakes rather than repeatedly calling a waiting VM.

## Global versus per-target control

Several control functions iterate over every slot with debug_on:

- step;
- step over;
- step out;
- continue;
- detach.

Inspection functions such as lang_debug_pc, lang_debug_stack, lang_debug_mem and lang_debug_fn generally select the first debug_on slot.

The live debugger therefore behaves like one global debugging context even though multiple LangSlot objects can technically be marked debug_on.

It does not provide a stable target/session identifier through dbg_ctl.

This is another area where DbgSession is architecturally ahead of the currently wired path.

## The DbgSession subsystem

compiler/debug/dbg_session.c implements a separate session abstraction.

Limits are:

    DBG_SESSION_MAX = 8
    DBG_BREAK_MAX   = 32
    DBG_WATCH_MAX   = 8

Each DbgSession records:

- owner;
- target slot;
- debugger state;
- step state;
- breakpoints;
- watch records;
- fault type and fault PC.

Access control is explicit:

    caller < 0 -> kernel access
    caller >= 0 -> caller must equal session owner

This is a useful ownership boundary for a future multi-client debugger.

## Structured breakpoints

DbgBreak contains:

    file_id
    line
    pc
    used
    enabled
    temporary
    resolved

dbg_session_resolve matches both file_id and line against a DbgMapRef array.

That solves the source-file ambiguity present in the live g_pend_line path.

Temporary breakpoints are removed automatically when dbg_session_on_pc hits them.

Persistent breakpoints remain.

The current live lang_pipeline debugger does not call these DbgSession functions.

At this revision, they are a tested subsystem waiting for integration rather than the actual session manager used by Editor debugging.

## Watch records versus the live watch display

DbgSession supports up to eight watches with typed kinds:

    DBG_WATCH_MEM
    DBG_WATCH_INT
    DBG_WATCH_FLOAT
    DBG_WATCH_PTR

The live debugger does not use that watch table.

LangSlot has only:

    uint32_t watch

and dbg_ctl op 8 assigns an address.

dbg_text kinds 2 and 3 display two eight-byte rows starting from that base.

No memory-write interception occurs.

The current Editor "watch" is therefore a memory viewer address, not a watchpoint that pauses execution on change or write.

## Reading guest memory

lang_debug_bytes and lang_debug_mem switch into the target process address space when user_ram is active.

They then read through vm.memory.

lang_debug_bytes:

- rejects missing target/destination/zero length;
- rejects a start address outside memory;
- clamps a read that crosses the end of guest memory;
- restores the previous process context.

lang_debug_mem reads four bytes but returns zero both for an invalid access and for a legitimate zero value.

dbg_ctl op 15 is less ambiguous for one byte because it returns -1 when the byte cannot be read.

A typed debugger API should return status separately from the inspected value.

## Operand and call-stack inspection

lang_debug_stack indexes from the top of the VM operand stack:

    index 0 -> top of stack

Out-of-range access returns zero.

lang_debug_call similarly indexes from the most recent return PC in vm.calls.

Again, zero is both a possible data value/PC sentinel and the invalid-access return.

The current UI favors compactness over an explicit result/status pair.

## Function lookup

lang_debug_fn scans the loaded function-start table and chooses the greatest function start <= pc.

It does not store or test function end addresses.

A PC after one function but before the next known start will still be labeled as the previous function.

With only 16 live function records, later functions may be unavailable altogether.

The structured CdbgFunc representation already contains both start and end and is better suited to precise function lookup.

## CDBG binary format

The structured CDBG sidecar begins with a 28-byte header containing:

    magic "CDBG"
    version
    ABI major/minor
    flags/reserved
    executable hash
    source hash
    file count
    line count
    function count
    reserved

It then serializes file records, line intervals and function records.

Limits declared in cdbg.h are:

    CDBG_FILES = 32
    CDBG_LINES = 256
    CDBG_FUNCS = 64
    CDBG_PATH  = 96
    CDBG_NAME  = 32

The binary representation is little-endian through explicit put_u16/put_u32 helpers.

## CDBG line records

Each CdbgLine contains:

    pc_start
    pc_end
    file_id
    line
    column

cdbg_from_result constructs pc_end from the next source-map entry, or code_end for the final entry.

This richer representation can distinguish source intervals rather than only source points.

However, cdbg_line_at currently selects the last entry with:

    pc_start <= pc

and does not test pc < pc_end.

For generated contiguous intervals this normally works.

For a CDBG image containing gaps, the lookup can attribute a PC in a gap to the previous line.

## CDBG generation/decoder count mismatch

There is a concrete limit mismatch.

cdbg_decode rejects:

    nlines > CDBG_LINES

where CDBG_LINES is 256.

But cdbg_from_result sets:

    lines = result->map_n

and only caps that value to 65535, not to CDBG_LINES.

It then serializes all those line records.

Therefore cdbg_from_result can generate a CDBG sidecar whose line count is greater than 256, while cdbg_decode refuses to load that same validly generated blob.

For real programs with more than 256 source-map entries, this makes the structured format internally inconsistent.

The generator and decoder must share one capacity rule, preferably a capacity that matches realistic ChrisC maps.

## CDBG hashes are currently zero in the live publication path

CdbgImage includes exec_hash and source_hash specifically to associate debug metadata with an executable/source version.

cdbg_from_result can compute an FNV hash when code bytes are supplied.

However, lang_write_map currently calls:

    cdbg_from_result(blob, cap, result, 0, 0, 0)

Thus:

    exec_hash   = 0
    source_hash = 0

for CDBG files written through that live path.

The fields exist in the format but do not currently protect against stale metadata/executable mismatch.

## CDBG is not loaded by lang_pipeline

At the documented revision, searches for cdbg_decode/cdbg_line_at/cdbg_func_at show those APIs in cdbg.c and tests, not in the live lang_pipeline loader.

lang_load_map reads .MAP.

The Editor debugger uses the LangSlot map arrays.

Therefore CDBG should be described as an implemented metadata format and future integration path, not as the current runtime source-mapping backend.

## Fault reporting

On a CLVM execution fault, lang_tick calls proc_record_fault using the target process ID and current VM PC, prints detailed VM state to serial, then tears down the slot.

The serial record includes:

- pc;
- source line;
- sp;
- vm.fault;
- vm.fault_pc;
- csp;
- return addresses;
- top of stack.

The UI-facing lang_debug_fault, however, reads proc_last_fault.

That process-level record provides cr2, pid and rip-like PC data.

It does not expose the full ClvmFault enum/fault_pc pair through dbg_ctl.

Because lang_tick kills the target after HALT/FAULT, the live LangSlot VM state is also lost for later interactive postmortem inspection.

A richer debugger should snapshot the target state before teardown.

## Syscall trace

clvm_sys_dispatch keeps a small ring of recent syscall IDs and slot IDs.

lang_debug_sys exposes it to the debugger.

dbg_text kind 5 formats up to six recent IDs.

This is particularly useful because many CLVM operations that appear source-level are ultimately host-service calls.

The trace is observational; it does not provide argument values or return values.

## Editor integration

The Editor exposes debugger commands and shortcuts for:

- debug launch;
- step in;
- step over;
- step out;
- continue;
- stop/detach;
- toggle breakpoint;
- inspect a memory address.

The gutter displays breakpoint/source-position state.

The debug panel requests status, stack and memory rows using dbg_text.

This keeps the debugger self-hosted within the ChrisOS application environment: a ChrisC program controls another ChrisC/CLVM target through the CLVM service ABI.

## Security and ownership

The live dbg_ctl/dbg_text service currently routes through global lang_debug_* functions.

It does not perform DbgSession owner checks.

Any CLVM program able to call those builtins can reach the global debugger control surface.

The DbgSession subsystem has an explicit owner model, but that model is not yet wired to the syscall path.

For a hardened multi-application environment, debugger access should require:

- a specific target identifier;
- session ownership;
- explicit attach authorization/capability;
- validated memory-inspection ranges;
- teardown when owner/target exits.

Debugging is inherently privileged because it can expose another program's memory and control execution.

## Complexity

Current live operations have small fixed limits but mostly linear algorithms.

| Operation | Complexity |
|---|---|
| breakpoint hit check | O(B), B <= 32 |
| source line lookup | O(M), M = loaded map entries |
| source-line breakpoint resolution | O(M) |
| function lookup | O(F), F <= 16 live |
| pending-breakpoint membership | O(P), P <= 32 |
| stack/call lookup | O(1) |
| watched memory read | O(n) bytes |
| DbgSession lookup | O(1) by session ID |
| DbgSession breakpoint resolve | O(B * M) |

The largest avoidable cost is repeated linear source-map lookup during instruction-by-instruction stepping.

## Concurrency

Debug state is largely global or embedded in LangSlot.

g_want_debug, g_pend_line, g_pend_watch and the DbgSession table are process-global kernel data.

There is no lock around the DbgSession table or live breakpoint globals in these modules.

The current usage model assumes serialized/cooperative control through the desktop/language scheduler.

That assumption should be revisited if multiple CPUs or concurrent debugger clients can mutate debugger state at the same time.

## Validation evidence

tools/test_cdbg.c validates:

- CDBG encode/decode round trip;
- file/line/function lookup;
- old and file-aware .MAP line parsing;
- multi-file ChrisC source mapping;
- diagnostic records.

tools/test_dbg_step.c validates:

- step-in, step-over and step-out pause rules;
- DbgSession ownership;
- file-aware breakpoint resolution;
- temporary/persistent breakpoint behavior;
- typed watch records;
- fault isolation between sessions.

tools/test_editor_vi.c validates interpreter call-stack overflow behavior and Editor-related generated control flow.

The general CLVM/JIT tests also provide the VM execution semantics that the debugger depends on.

The gap is integration: the richer DbgSession/CDBG tests do not prove that Editor's live debugger uses those abstractions, because it currently does not.

## Current limitations

At the documented revision:

- the live runtime uses text .MAP rather than CDBG;
- the .MAP reader is capped at 8191 bytes;
- live source lookup ignores file_id;
- breakpoints are pending by line number only;
- one source breakpoint arms only the first matching map PC;
- persistent breakpoint continue can immediately re-hit the same PC;
- step operations have hard 512/8192-instruction ceilings;
- stepping a WAITING VM can spend the remaining step loop repeatedly yielding;
- live control is global rather than target/session-addressed;
- inspection APIs select the first debug_on slot;
- live function metadata is limited to 16 names of 23 characters;
- CDBG generation can emit more than 256 lines but CDBG decode rejects more than 256;
- live CDBG sidecars are written with zero executable/source hashes;
- CdbgLine.pc_end is not enforced by cdbg_line_at;
- DbgSession ownership, typed watches and temporary breakpoints are not wired into lang_pipeline;
- the live "watch" is a memory-view address, not a hardware/software watchpoint;
- process fault UI does not preserve the full ClvmFault record after slot teardown;
- dbg_text has no destination-capacity argument;
- debugger syscalls have no explicit privilege/capability check or session owner.

## Roadmap boundary

The natural consolidation path is to make CDBG + DbgSession the single runtime debugger model.

That would allow:

- runtime loading and hash validation of CDBG;
- file-aware source breakpoints;
- target-addressed sessions;
- temporary breakpoints for continue/step-over;
- structured pause reasons;
- asynchronous stepping across WAITING states;
- postmortem VM snapshots;
- typed memory inspection with explicit status;
- true watchpoints based on write instrumentation;
- binary-search source lookup;
- full 64-function metadata;
- owner/capability checks at dbg_ctl attach;
- a versioned debugger protocol instead of magic numeric controls.

Those are future changes until integrated in source.

## Source map and revision

compiler/debug/cdbg.h and cdbg.c define the structured debug metadata format and lookup functions.

compiler/debug/dbg_session.h and dbg_session.c define session ownership, structured breakpoints, typed watches and step-policy helpers.

compiler/chrisc/chrisc.h defines compiler-side source map, diagnostic and exported-function metadata.

compiler/lang_pipeline.c implements the live debugger state, .MAP generation/loading, breakpoint handling, stepping, memory inspection and Editor-facing control functions.

kernel/lang/clvm_sys.c exposes dbg_ctl and dbg_text as CLVM syscalls 250 and 251.

APPS/EDITOR/EDITOR.CC implements the visible debugger workflow.

All current-behavior claims in this chapter were reconciled against ChrisOS revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.
