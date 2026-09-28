#!/usr/bin/env python3
"""Deterministic checks for recursion, amortization and linear structures."""

from __future__ import annotations

import argparse
from pathlib import Path


REVISION = "da3df29cb397932c43d32373871fb9380e688ade"


def check_recurrences() -> None:
    c = 7
    d = 3
    t = d
    for n in range(1, 65):
        t = t + c
        assert t == d + n * c

    for n in range(1, 1025):
        x = n
        levels = 0
        while x > 1:
            x = (x + 1) // 2
            levels += 1
        assert levels <= 10 if n <= 1024 else True

    for n in range(1, 257):
        capacity = 1
        copies = 0
        size = 0
        while size < n:
            if size == capacity:
                copies += size
                capacity *= 2
            size += 1
        assert copies < 2 * n

    stack = []
    primitive_ops = 0
    for i in range(100):
        stack.append(i)
        primitive_ops += 1
    for k in (3, 7, 30, 100):
        take = min(k, len(stack))
        for _ in range(take):
            stack.pop()
            primitive_ops += 1
    assert primitive_ops <= 200


def check_bounded_depth_and_stack() -> None:
    max_depth = 32
    depth = 0
    for _ in range(max_depth):
        assert depth < max_depth
        depth += 1
    assert depth == max_depth
    assert not (depth < max_depth)
    while depth:
        depth -= 1
    assert depth == 0

    capacity = 256
    values: list[int] = []
    for i in range(capacity):
        assert len(values) < capacity
        values.append(i)
    assert len(values) == capacity
    for expected in reversed(range(capacity)):
        assert values
        assert values.pop() == expected
    assert not values


def traverse_index_list(next_idx: list[int], head: int) -> list[int]:
    out: list[int] = []
    seen: set[int] = set()
    i = head
    while i != -1:
        if i < 0 or i >= len(next_idx):
            raise ValueError("index outside node pool")
        if i in seen:
            raise ValueError("cycle")
        seen.add(i)
        out.append(i)
        i = next_idx[i]
    return out


class CountRing:
    def __init__(self, cap: int) -> None:
        self.cap = cap
        self.data = [None] * cap
        self.head = 0
        self.tail = 0
        self.count = 0

    def push(self, value: int) -> bool:
        if self.count == self.cap:
            return False
        self.data[self.tail] = value
        self.tail = (self.tail + 1) % self.cap
        self.count += 1
        return True

    def pop(self):
        if self.count == 0:
            return None
        value = self.data[self.head]
        self.head = (self.head + 1) % self.cap
        self.count -= 1
        return value


class ReservedSlotRing:
    def __init__(self, cap: int) -> None:
        self.cap = cap
        self.data = [None] * cap
        self.head = 0
        self.tail = 0
        self.lost = 0

    def push(self, value: int) -> bool:
        nxt = (self.head + 1) % self.cap
        if nxt == self.tail:
            self.lost += 1
            return False
        self.data[self.head] = value
        self.head = nxt
        return True

    def pop(self):
        if self.tail == self.head:
            return None
        value = self.data[self.tail]
        self.tail = (self.tail + 1) % self.cap
        return value


def check_linear_structures() -> None:
    base = 0x1000
    element_size = 24
    for i in range(64):
        assert base + i * element_size == 0x1000 + 24 * i

    assert traverse_index_list([1, 2, 3, -1], 0) == [0, 1, 2, 3]
    try:
        traverse_index_list([1, 2, 0], 0)
    except ValueError as exc:
        assert str(exc) == "cycle"
    else:
        raise AssertionError("cycle not rejected")

    jobs = CountRing(8)
    for i in range(8):
        assert jobs.push(i)
    assert not jobs.push(99)
    assert jobs.count == 8
    assert [jobs.pop() for _ in range(8)] == list(range(8))
    assert jobs.pop() is None
    assert jobs.count == 0

    events = ReservedSlotRing(64)
    for i in range(63):
        assert events.push(i)
    assert not events.push(63)
    assert events.lost == 1
    assert [events.pop() for _ in range(63)] == list(range(63))
    assert events.pop() is None

    for i in range(80):
        if not events.push(i):
            assert events.pop() is not None
            assert events.push(i)
    popped = []
    while True:
        value = events.pop()
        if value is None:
            break
        popped.append(value)
    assert popped == sorted(popped)


def require(text: str, path: str, anchors: tuple[str, ...]) -> None:
    for anchor in anchors:
        if anchor not in text:
            raise AssertionError(f"{path}: missing reviewed anchor {anchor!r}")


def check_source_contract(source_root: Path) -> None:
    sh_int_path = "kernel/gfx/shader/sh_int.h"
    sh_parse_path = "kernel/gfx/shader/sh_parse.c"
    clvm_h_path = "compiler/clvm/clvm_vm.h"
    clvm_c_path = "compiler/clvm/clvm_vm.c"
    job_h_path = "kernel/metal/job.h"
    job_c_path = "kernel/metal/job.c"
    input_path = "kernel/gfx/input.c"

    sh_int = (source_root / sh_int_path).read_text(encoding="utf-8")
    sh_parse = (source_root / sh_parse_path).read_text(encoding="utf-8")
    clvm_h = (source_root / clvm_h_path).read_text(encoding="utf-8")
    clvm_c = (source_root / clvm_c_path).read_text(encoding="utf-8")
    job_h = (source_root / job_h_path).read_text(encoding="utf-8")
    job_c = (source_root / job_c_path).read_text(encoding="utf-8")
    input_c = (source_root / input_path).read_text(encoding="utf-8")

    require(sh_int, sh_int_path, (
        "#define SH_AST_MAX 512",
        "#define SH_NEST_MAX 32",
        "int16_t next;",
        "Ast ast[SH_AST_MAX];",
        "int depth;",
    ))
    require(sh_parse, sh_parse_path, (
        "static int enter(ShComp *c)",
        "c->depth >= SH_NEST_MAX",
        "static void leave(ShComp *c)",
        "static int parse_unary(ShComp *c)",
        "e = parse_unary(c);",
        "right = parse_bin(c, prec + 1);",
        "c->ast[tail].next = (int16_t)",
        "static int node_new(ShComp *c",
    ))
    require(clvm_h, clvm_h_path, (
        "#define CLVM_STACK_MAX 256",
        "#define CLVM_CALL_MAX 64",
        "int64_t stack[CLVM_STACK_MAX];",
        "uint32_t calls[CLVM_CALL_MAX];",
    ))
    require(clvm_c, clvm_c_path, (
        "int clvm_vm_push64",
        "vm->sp == CLVM_STACK_MAX",
        "vm->stack[vm->sp++] = value",
        "int clvm_vm_pop64",
        "vm->sp == 0",
        "vm->stack[--vm->sp]",
        "sp > CLVM_STACK_MAX || csp > CLVM_CALL_MAX",
    ))
    require(job_h, job_h_path, ("#define JOB_QUEUE_CAP 1024u",))
    require(job_c, job_c_path, (
        "static Job g_queue[JOB_QUEUE_CAP];",
        "static uint32_t g_q_head;",
        "static uint32_t g_q_tail;",
        "static uint32_t g_q_count;",
        "spin_lock(&g_q_lock);",
        "g_q_count == JOB_QUEUE_CAP",
        "g_q_tail = (g_q_tail + 1u) % JOB_QUEUE_CAP;",
        "g_q_head = (g_q_head + 1u) % JOB_QUEUE_CAP;",
    ))
    require(input_c, input_path, (
        "#define INPUT_QUEUE_CAPACITY 64u",
        "static InputEvent g_queue[INPUT_QUEUE_CAPACITY];",
        "static void queue_push(InputEvent event)",
        "next = (head + 1u) % INPUT_QUEUE_CAPACITY",
        "if (next == g_queue_tail)",
        "++g_lost_events;",
        "bool input_next_event(InputEvent *event)",
        "g_queue_tail = (tail + 1u) % INPUT_QUEUE_CAPACITY;",
        "compiler_barrier();",
    ))


def check_documents(root: Path) -> None:
    names = (
        "recursion-recurrences-amortization.md",
        "arrays-lists-stacks-queues.md",
    )
    for lang in ("en", "pt-br"):
        for name in names:
            path = root / "docs" / lang / "01-foundations" / name
            text = path.read_text(encoding="utf-8")
            if REVISION not in text:
                raise AssertionError(f"{path}: missing reviewed revision")

    for lang in ("en", "pt-br"):
        rec = (root / "docs" / lang / "01-foundations" / names[0]).read_text(encoding="utf-8")
        linear = (root / "docs" / lang / "01-foundations" / names[1]).read_text(encoding="utf-8")
        require(rec, str(names[0]), (
            "SH_NEST_MAX",
            "SH_AST_MAX",
            "parse_unary",
            "parse_bin",
            "CLVM_STACK_MAX",
            "CLVM_CALL_MAX",
            "O(1)",
        ))
        require(linear, str(names[1]), (
            "JOB_QUEUE_CAP",
            "INPUT_QUEUE_CAPACITY",
            "CLVM_STACK_MAX",
            "CLVM_CALL_MAX",
            "queue_push",
            "input_next_event",
            "SH_AST_MAX",
            "Ast",
        ))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=".source")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    check_recurrences()
    check_bounded_depth_and_stack()
    check_linear_structures()
    check_source_contract(Path(args.source))
    check_documents(root)

    print(
        "recursion/linear-structure checks passed: recurrences, doubling amortization, "
        "bounded depth/stacks, index-linked traversal, count ring and reserved-slot FIFO ring"
    )
    print(
        "scope: deterministic models and reviewed source anchors only; no claim of a "
        "formal concurrent proof for the input queue"
    )


if __name__ == "__main__":
    main()
