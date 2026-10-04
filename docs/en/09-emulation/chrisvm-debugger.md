---
id: chrisvm-debugger
lang: en
type: technical-chapter
volume: 09-emulation
status: maintained
reviewed_revision: e05a17fd76333114a3fb5c2452f38ca747d4ac56
sources:
  - chrisvm/chrisvm.h
  - chrisvm/machine/machine.h
  - chrisvm/machine/config.c
  - chrisvm/frontend/main.c
  - chrisvm/debug/trace.c
  - chrisvm/cpu/emulator/chriscpu.c
  - chrisvm/cpu/common/exceptions.c
symbols:
  - chris_dump_cpu
  - chris_trace_push
  - chris_trace_dump
  - CHRIS_EXIT_BREAK
depends_on:
  - chrisvm-boot
  - chrisvm-chriscpu
related:
  - determinism-replay
  - x86-decoding
---

# ChrisVM debugger and trace facilities

## Scope

ChrisVM currently provides a minimal host-side debugger around the ChrisCPU interpreter. It is designed for bring-up rather than source-level debugging.

The available facilities are:

- an interactive step/continue/register loop;
- one RIP breakpoint;
- instruction tracing;
- a 256-entry recent-instruction ring;
- CPU register dumps;
- terminal exit reasons such as break, exception and step limit.

There is no source mapping, symbol lookup, watchpoint engine, memory inspector, reverse execution, remote GDB protocol or multi-CPU debugger.

This chapter documents revision e05a17fd76333114a3fb5c2452f38ca747d4ac56.

## Enabling debug mode

The command-line parser accepts:

    --debug

When enabled, the frontend enters debug_loop instead of calling chris_run once for the full configured budget.

The debugger is interactive through standard input and writes its command help and state through stderr/logging.

Headless mode explicitly clears cfg.debug in the argument parser, so:

    --headless

disables the interactive debugger.

## Interactive commands

The current command set is:

    s       step
    c       continue
    r       registers
    q       quit
    b HEX   set breakpoint address

Commands are selected only by the first input character.

There is no structured parser, command history or expression syntax.

## Register command

The r command calls:

    chris_dump_cpu

The dump includes:

- RIP;
- RSP;
- RFLAGS;
- RAX;
- RCX;
- RDX;
- RBX;
- RSP;
- RBP;
- RSI;
- RDI;
- CR0;
- CR2;
- CR3;
- CR4.

The first eight GPRs are shown.

The current dump omits:

- R8-R15;
- CR8;
- segment state;
- GDTR/IDTR;
- EFER and MSRs;
- XMM state;
- CPL;
- exception diagnostics;
- pending interrupt state.

It is therefore a useful bring-up view, not a complete ChrisArchitectureState dump.

## Step

The s command clears cpu->halted and invokes:

    chris_run(machine, 1)

The ChrisCPU run loop executes at most one instruction and then normally returns CHRIS_EXIT_STEP_LIMIT if the CPU did not halt for another reason.

Afterward the debugger prints the CPU state again.

This reuses the normal interpreter rather than implementing a second single-step execution path.

## Continue

The c command clears cpu->has_break, clears halted and runs with the configured max_steps budget.

This behavior contains a significant interactive-breakpoint defect.

If a user first enters:

    b ADDRESS

the debugger sets has_break.

But entering c immediately afterward clears that flag before execution.

Therefore the interactive sequence "set breakpoint, continue until breakpoint" does not work as expected in the current source.

The breakpoint remains meaningful for one-instruction step runs or when configured before execution using --break.

This should be fixed before describing b/c as a conventional breakpoint workflow.

## Breakpoint mechanism

ChrisCPU has one breakpoint address:

    break_rip

plus:

    has_break

At the top of each interpreter-loop iteration, before instruction fetch:

    if has_break && RIP == break_rip
        exit_reason = CHRIS_EXIT_BREAK
        halted = 1

The instruction at the breakpoint address is not executed.

This is a software interpreter check, not an x86 debug-register breakpoint.

It does not use DR0-DR7 and is invisible to the guest.

## One breakpoint only

There is one break_rip field.

Setting another breakpoint replaces the previous address.

There is no list, enable/disable set, temporary breakpoint or conditional breakpoint.

A scalable debugger should move breakpoints out of one scalar field.

## Command-line breakpoint

The configuration parser accepts:

    --break=ADDRESS

This sets cfg.break_rip and cfg.has_break.

ChrisCPU copies those fields when the CPU object is created.

Unlike interactive c, a normal non-debug run does not automatically clear the configured breakpoint before execution.

Thus command-line breakpoints currently provide a more coherent "run until address" behavior than the interactive b/c sequence.

## Stale break exit state

cpu_run begins by clearing halted.

It resets exit_reason to CHRIS_EXIT_NONE only when the previous exit reason is not CHRIS_EXIT_BREAK.

Thus, resuming after a breakpoint can initially retain CHRIS_EXIT_BREAK while execution proceeds.

Normally a later terminal result overwrites it, such as step limit or HLT.

However, retaining a stale break reason complicates error classification because some executor failure handling only creates CHRIS_EXIT_EXCEPTION when exit_reason is CHRIS_EXIT_NONE.

A more robust resume contract should clear the break result when the user explicitly continues past it.

## Instruction trace output

When cfg.trace is enabled, each decoded instruction causes a line similar to:

    CPU0 #N RIP ADDRESS TEXT

before execution.

The trace uses:

- global interpreter step counter + 1;
- current RIP;
- chris_format_insn output.

It always labels the CPU as CPU0, consistent with the current single-CPU machine.

The textual formatter is diagnostic and not a complete disassembler.

## Recent-instruction ring

Regardless of the visible --trace option, each successfully decoded instruction is pushed into the internal trace ring by:

    chris_trace_push

The ring capacity is:

    CHRIS_TRACE_RING = 256

Each entry stores:

- RIP;
- decoded length, capped at 15;
- up to 15 raw bytes;
- formatted instruction text up to the fixed text buffer.

Thus recent execution history exists even when continuous trace printing is disabled.

This is useful for post-failure diagnostics.

## Ring overwrite behavior

ring_i increases monotonically.

ring_n grows until it reaches 256.

New entries overwrite old ones modulo the fixed ring size.

chris_trace_dump calculates the oldest retained logical index and emits entries in chronological order.

The ring-index expression uses a bit mask:

    index & (CHRIS_TRACE_RING - 1)

which is correct because the current capacity is 256, a power of two.

Changing CHRIS_TRACE_RING to a non-power-of-two value would break that assumption.

The constraint is not encoded as a compile-time assertion.

## Trace dump

chris_trace_dump emits:

    recent instructions:

followed by each retained entry's RIP and formatted text.

Although raw instruction bytes are stored in the ring, the current dump does not print them.

This loses useful forensic information when formatting is incomplete or decoding is under investigation.

A better dump should include the captured byte sequence.

## Automatic triple-fault trace

The exception path calls chris_trace_dump when exception delivery fails through the double-fault stage and ChrisVM enters CHRIS_EXIT_TRIPLE.

Therefore a terminal triple fault automatically reports recent decoded execution history through the machine log callback.

This is one of the strongest current uses of the ring.

There is no equivalent interactive command in debug_loop to dump the ring manually.

## CPU dump uses internal ChrisCPU state directly

chris_dump_cpu reads:

    m->cpu->arch

rather than backend get_state.

This shares the same abstraction leak documented in the architectural-state chapter.

It works for ChrisCPU.

A future ChrisHV whose authoritative guest state resides in VMCS/VMCB would require synchronization or backend-neutral state retrieval before debugger values can be trusted.

## Log callback

Trace and dump functions route output through:

    chris_log

ChrisMachine stores one callback and context.

The command-line frontend installs a callback that writes each line to stderr.

This decouples debugger generation from one output medium.

A GUI or test harness can install a different sink.

## Trace flags

ChrisConfig exposes:

- trace;
- trace_memory;
- trace_io;
- trace_mmio.

The inspected source actively uses trace for instruction lines.

trace_io has only partial output-side logging in the I/O execution helper.

trace_memory and trace_mmio are copied into ChrisCpu but no general trace implementation was found consuming them in the current source.

Thus the configuration surface is ahead of the implemented observability.

Debugger documentation must not claim complete memory/MMIO tracing.

## No memory examine command

debug_loop has no command to:

- read virtual memory;
- read physical memory;
- write memory;
- dump stack;
- inspect page tables.

The host API has RAM/physical helpers, but they are not exposed through the debugger interface.

For operating-system work, memory inspection is a high-value missing facility.

## No register editing

The interactive loop prints registers but has no command to modify them.

The library exposes some GPR/CR setters, but the terminal debugger does not use them.

There is also no generic full-state edit command.

## No symbol support

Breakpoints use numeric addresses parsed by strtoull.

There is no ELF symbol-table lookup.

A command such as:

    b function_name

is unsupported.

The loader also ignores section/symbol metadata, so symbol-aware debugging would require a separate host-side ELF metadata path.

## No source-level mapping

There is no DWARF parser, source file mapping or line table.

The debugger is machine-level.

This is consistent with the project's bring-up stage but limits compiler/toolchain debugging.

## No watchpoints

The physical and virtual memory paths do not consult debugger watchpoint state.

There is no read/write/access breakpoint facility.

Implementing watchpoints could be done in ChrisCPU through memory helpers before hardware debug-register fidelity is attempted.

## No x86 debug registers

ChrisArchitectureState does not currently expose DR0-DR7.

The guest cannot use a modeled architectural hardware-debug mechanism through ChrisVM.

Host breakpoints are emulator control state, not guest debug-register state.

This distinction matters for software that expects #DB behavior.

## No remote debugger protocol

ChrisVM does not expose a GDB remote stub in the inspected path.

There is no TCP debugger server or RSP packet implementation.

Such an interface would benefit from backend-neutral state, memory and breakpoint APIs first.

## Exit reasons

Debugger-relevant stop reasons include:

- CHRIS_EXIT_BREAK;
- CHRIS_EXIT_STEP_LIMIT;
- CHRIS_EXIT_HLT;
- CHRIS_EXIT_SHUTDOWN;
- CHRIS_EXIT_EXCEPTION;
- CHRIS_EXIT_TRIPLE;
- CHRIS_EXIT_UNMAPPED.

The interactive loop terminates automatically for HLT, shutdown, triple fault and exception.

It does not explicitly exit on CHRIS_EXIT_BREAK or CHRIS_EXIT_STEP_LIMIT, allowing further commands.

## Step counter

ChrisCPU increments cpu->steps once at the end of each interpreter iteration after decode/execute flow and IRQ consideration.

The visible instruction trace labels the next instruction with:

    steps + 1

This is a deterministic execution counter, not cycle timing.

The debugger can retrieve total steps through chris_steps.

## Breakpoint timing

The breakpoint check happens before instruction fetch.

Therefore if RIP equals break_rip:

- no fetch occurs;
- no trace-ring entry is added for that instruction;
- steps does not increment;
- TSC does not increment for the stopped instruction.

This is a clean host breakpoint boundary.

## Decoder failure and trace history

The ring push happens after a successful decode.

If instruction fetch or decoding fails before that point, the problematic instruction is not added as a newly formatted ring entry.

Previously executed history remains available.

For decode-debugging, recording raw fetched bytes before decode would provide better failure evidence.

## Debugger versus guest state

Debugger fields such as:

- break_rip;
- has_break;
- trace flags;
- trace ring;

live in ChrisCpu runtime state, not ChrisArchitectureState.

They should not be exposed to the guest as registers.

A deterministic VM snapshot intended to resume debugging, however, may need to preserve some of them separately from architectural state.

## Current test coverage

The main ChrisVM test suite relies heavily on run/exit inspection but does not provide a focused automated test of the interactive debug_loop.

The interpreter's breakpoint path is simple enough to test independently, but the interactive b/c defect demonstrates why terminal workflows also need coverage.

Useful tests should include:

- --break stopping before instruction execution;
- interactive b + c;
- step count;
- trace-ring wraparound;
- ring chronology;
- triple-fault dump;
- dump completeness;
- stale exit-reason resume behavior.

## Hardening priorities

The highest-value debugger work is:

1. fix interactive b + c so continue honors the selected breakpoint;
2. clear stale CHRIS_EXIT_BREAK state on intentional resume;
3. support multiple breakpoints;
4. add memory examine/write commands;
5. expose complete backend-neutral architectural state;
6. print raw bytes in trace dumps;
7. make trace-memory, trace-io and trace-mmio real and symmetric;
8. add manual ring-dump command;
9. add register-edit commands with explicit raw/debugger semantics;
10. add symbols and ELF metadata lookup;
11. add watchpoints;
12. build a backend-neutral debugger API before ChrisHV;
13. optionally add GDB RSP once state/memory/breakpoint primitives are stable;
14. test terminal debugger workflows automatically.

## Revision note

At revision e05a17fd76333114a3fb5c2452f38ca747d4ac56, ChrisVM has a useful low-level bring-up debugger: single stepping, CPU dumps, one host breakpoint, continuous instruction trace and a 256-entry recent-instruction ring used automatically on triple fault. The main immediate defect is the interactive continue command clearing the breakpoint that b just configured. The broader limitations are incomplete state visibility, no memory/symbol/watchpoint support and debugger code that still assumes ChrisCPU's internal cpu->arch representation.
