#!/usr/bin/env python3
"""Reproduce coherence chapter examples; this is not a hardware conformance test."""

from dataclasses import dataclass
from enum import Enum


class State(str, Enum):
    M = "M"
    E = "E"
    S = "S"
    I = "I"


@dataclass
class Line:
    state: State = State.I
    value: int = 0


class TwoCoreMESI:
    def __init__(self, memory_value=0):
        self.memory = memory_value
        self.lines = [Line(), Line()]
        self.ownership_transfers = 0
        self.invalidations = 0

    def check(self):
        states = [line.state for line in self.lines]
        assert states.count(State.M) <= 1
        assert states.count(State.E) <= 1
        if State.M in states:
            owner = states.index(State.M)
            assert all(i == owner or state == State.I for i, state in enumerate(states))
        if State.E in states:
            owner = states.index(State.E)
            assert all(i == owner or state == State.I for i, state in enumerate(states))
        shared = [line.value for line in self.lines if line.state == State.S]
        if shared:
            assert len(set(shared)) == 1

    def read(self, cpu):
        other = 1 - cpu
        mine = self.lines[cpu]
        peer = self.lines[other]
        if mine.state != State.I:
            self.check()
            return mine.value

        if peer.state == State.M:
            self.memory = peer.value
            peer.state = State.S
            mine.state = State.S
            mine.value = self.memory
        elif peer.state == State.E:
            peer.state = State.S
            mine.state = State.S
            mine.value = peer.value
        elif peer.state == State.S:
            mine.state = State.S
            mine.value = peer.value
        else:
            mine.state = State.E
            mine.value = self.memory

        self.check()
        return mine.value

    def write(self, cpu, value):
        other = 1 - cpu
        mine = self.lines[cpu]
        peer = self.lines[other]

        if mine.state == State.M:
            mine.value = value
            self.check()
            return

        if mine.state == State.E:
            mine.state = State.M
            mine.value = value
            self.check()
            return

        if peer.state != State.I:
            self.invalidations += 1
            peer.state = State.I

        if mine.state == State.I:
            mine.value = self.memory
        self.ownership_transfers += 1
        mine.state = State.M
        mine.value = value
        self.check()

    def evict(self, cpu):
        line = self.lines[cpu]
        if line.state == State.M:
            self.memory = line.value
        line.state = State.I
        self.check()


def test_basic_trace():
    m = TwoCoreMESI(0)
    assert m.read(0) == 0
    assert [x.state for x in m.lines] == [State.E, State.I]

    assert m.read(1) == 0
    assert [x.state for x in m.lines] == [State.S, State.S]

    m.write(0, 1)
    assert [x.state for x in m.lines] == [State.M, State.I]
    assert m.lines[0].value == 1

    assert m.read(1) == 1
    assert [x.state for x in m.lines] == [State.S, State.S]

    m.write(1, 2)
    assert [x.state for x in m.lines] == [State.I, State.M]
    assert m.read(0) == 2
    assert [x.state for x in m.lines] == [State.S, State.S]


def test_modified_evict():
    m = TwoCoreMESI(7)
    m.write(0, 9)
    assert m.memory == 7
    m.evict(0)
    assert m.memory == 9
    assert m.read(1) == 9


def test_false_sharing_ping_pong():
    # Two logical 32-bit counters share one modeled cache line.
    # Each write transfers ownership of the entire line.
    m = TwoCoreMESI(0)
    m.read(0)
    m.read(1)
    before = m.ownership_transfers

    for i in range(1, 6):
        m.write(0, i)
        m.write(1, 100 + i)

    transfers = m.ownership_transfers - before
    assert transfers == 10
    assert m.invalidations >= 10


def main():
    test_basic_trace()
    test_modified_evict()
    test_false_sharing_ping_pong()
    print("coherence examples: MESI stable-state invariants, intervention, eviction and false-sharing ping-pong passed")
    print("Scope: illustrative two-core model only; no Intel/AMD/QEMU/ChrisCPU conformance claim.")


if __name__ == "__main__":
    main()
