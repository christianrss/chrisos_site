#!/usr/bin/env python3
"""Explore a small x86-TSO teaching model used by the memory-model chapter.

This is deliberately not a hardware conformance test. It models:
- program-order instruction issue per CPU;
- one FIFO store buffer per CPU;
- store-to-load forwarding from the CPU's own newest matching pending store;
- nondeterministic draining of the oldest buffered store;
- a full fence that cannot retire until the local store buffer is empty.
"""

from collections import deque
from dataclasses import dataclass


MEM_KEYS = ("x", "y", "data", "ready")
MEM_INDEX = {name: i for i, name in enumerate(MEM_KEYS)}
REG_KEYS = ("r0", "r1")
REG_INDEX = {name: i for i, name in enumerate(REG_KEYS)}


@dataclass(frozen=True)
class State:
    memory: tuple[int, ...]
    pc: tuple[int, ...]
    buffers: tuple[tuple[tuple[str, int], ...], ...]
    registers: tuple[tuple[int, ...], ...]


def newest_buffered(buffer: tuple[tuple[str, int], ...], address: str):
    for item_address, value in reversed(buffer):
        if item_address == address:
            return value
    return None


def initial_state(cpu_count: int, initial_memory: dict[str, int]) -> State:
    return State(
        memory=tuple(initial_memory.get(name, 0) for name in MEM_KEYS),
        pc=tuple(0 for _ in range(cpu_count)),
        buffers=tuple(tuple() for _ in range(cpu_count)),
        registers=tuple(tuple(-1 for _ in REG_KEYS) for _ in range(cpu_count)),
    )


def execute_one(state: State, programs, cpu: int):
    pc = state.pc[cpu]
    if pc >= len(programs[cpu]):
        return None

    op = programs[cpu][pc]
    kind = op[0]

    if kind == "F" and state.buffers[cpu]:
        return None

    memory = list(state.memory)
    pcs = list(state.pc)
    buffers = [list(buf) for buf in state.buffers]
    registers = [list(regs) for regs in state.registers]

    if kind == "S":
        _, address, value = op
        buffers[cpu].append((address, value))
    elif kind == "L":
        _, address, register = op
        value = newest_buffered(tuple(buffers[cpu]), address)
        if value is None:
            value = memory[MEM_INDEX[address]]
        registers[cpu][REG_INDEX[register]] = value
    elif kind == "F":
        # The fence itself has no data effect. Its execution is enabled only
        # after every older local store has drained.
        pass
    else:
        raise AssertionError(f"unknown operation {kind}")

    pcs[cpu] += 1
    return State(
        tuple(memory),
        tuple(pcs),
        tuple(tuple(buf) for buf in buffers),
        tuple(tuple(regs) for regs in registers),
    )


def drain_one(state: State, cpu: int):
    if not state.buffers[cpu]:
        return None
    memory = list(state.memory)
    buffers = [list(buf) for buf in state.buffers]
    address, value = buffers[cpu].pop(0)
    memory[MEM_INDEX[address]] = value
    return State(
        tuple(memory),
        state.pc,
        tuple(tuple(buf) for buf in buffers),
        state.registers,
    )


def explore(programs, initial_memory=None):
    initial_memory = initial_memory or {}
    first = initial_state(len(programs), initial_memory)
    queue = deque([first])
    seen = {first}
    terminal = []

    while queue:
        state = queue.popleft()

        for cpu in range(len(programs)):
            nxt = execute_one(state, programs, cpu)
            if nxt is not None and nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)

        for cpu in range(len(programs)):
            nxt = drain_one(state, cpu)
            if nxt is not None and nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)

        programs_done = all(
            state.pc[cpu] == len(programs[cpu]) for cpu in range(len(programs))
        )
        buffers_empty = all(not buffer for buffer in state.buffers)
        if programs_done and buffers_empty:
            terminal.append(state)

    return seen, terminal


def reg(state: State, cpu: int, name: str) -> int:
    return state.registers[cpu][REG_INDEX[name]]


def store_buffering():
    programs = (
        (("S", "x", 1), ("L", "y", "r0")),
        (("S", "y", 1), ("L", "x", "r1")),
    )
    seen, terminal = explore(programs, {"x": 0, "y": 0})
    outcomes = {(reg(s, 0, "r0"), reg(s, 1, "r1")) for s in terminal}
    assert outcomes == {(0, 0), (0, 1), (1, 0), (1, 1)}
    return len(seen), outcomes


def store_buffering_with_fence():
    programs = (
        (("S", "x", 1), ("F",), ("L", "y", "r0")),
        (("S", "y", 1), ("F",), ("L", "x", "r1")),
    )
    seen, terminal = explore(programs, {"x": 0, "y": 0})
    outcomes = {(reg(s, 0, "r0"), reg(s, 1, "r1")) for s in terminal}
    assert (0, 0) not in outcomes
    assert outcomes == {(0, 1), (1, 0), (1, 1)}
    return len(seen), outcomes


def message_passing():
    programs = (
        (("S", "data", 42), ("S", "ready", 1)),
        (("L", "ready", "r0"), ("L", "data", "r1")),
    )
    seen, terminal = explore(programs, {"data": 0, "ready": 0})
    outcomes = {(reg(s, 1, "r0"), reg(s, 1, "r1")) for s in terminal}
    assert (1, 0) not in outcomes
    assert outcomes == {(0, 0), (0, 42), (1, 42)}
    return len(seen), outcomes


def main():
    sb_states, sb = store_buffering()
    fence_states, fenced = store_buffering_with_fence()
    mp_states, mp = message_passing()

    print(
        "memory-model examples passed: "
        f"SB states={sb_states} outcomes={sorted(sb)}; "
        f"SB+fence states={fence_states} outcomes={sorted(fenced)}; "
        f"MP states={mp_states} outcomes={sorted(mp)}"
    )
    print(
        "Scope: finite FIFO store-buffer teaching model only; "
        "no Intel/AMD/compiler/ChrisCPU conformance claim."
    )


if __name__ == "__main__":
    main()
