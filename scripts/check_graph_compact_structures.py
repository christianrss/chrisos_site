#!/usr/bin/env python3
"""Deterministic checks for graph/DSU and compact systems data structures."""

from __future__ import annotations

import argparse
from collections import deque
from dataclasses import dataclass
from pathlib import Path

REVISION = "da3df29cb397932c43d32373871fb9380e688ade"


def connected_components(adj: list[list[int]]) -> list[int]:
    comp = [-1] * len(adj)
    cid = 0
    for start in range(len(adj)):
        if comp[start] != -1:
            continue
        q = deque([start])
        comp[start] = cid
        while q:
            u = q.popleft()
            for v in adj[u]:
                assert 0 <= v < len(adj)
                if comp[v] == -1:
                    comp[v] = cid
                    q.append(v)
        cid += 1
    return comp


def parent_chain_has_cycle(parent: list[int], start: int) -> bool:
    slow = fast = start
    while True:
        if not (0 <= slow < len(parent)):
            return False
        slow = parent[slow]
        for _ in range(2):
            if not (0 <= fast < len(parent)):
                return False
            fast = parent[fast]
        if slow == fast:
            # A self-parent root is termination, not corruption.
            return not (0 <= slow < len(parent) and parent[slow] == slow)


class DSU:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))
        self.size = [1] * n

    def find(self, x: int) -> int:
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, a: int, b: int) -> int:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return ra
        if self.size[ra] < self.size[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        self.size[ra] += self.size[rb]
        return ra


def check_graph_models() -> None:
    undirected = [
        [1],
        [0, 2],
        [1],
        [4],
        [3],
        [],
    ]
    comp = connected_components(undirected)
    assert comp[0] == comp[2]
    assert comp[3] == comp[4]
    assert comp[0] != comp[3]
    assert comp[5] not in (comp[0], comp[3])

    n = len(undirected)
    matrix = [[False] * n for _ in range(n)]
    for u, nbrs in enumerate(undirected):
        for v in nbrs:
            matrix[u][v] = True
    for u in range(n):
        for v in range(n):
            assert matrix[u][v] == (v in undirected[u])
            assert matrix[u][v] == matrix[v][u]

    directed = [[1], [], [1]]
    assert 1 in directed[0] and 0 not in directed[1]

    # Rooted parent chains terminate at a self-parent root.
    assert not parent_chain_has_cycle([0, 0, 1, 1], 3)
    # Corrupted parent relation: 1 -> 2 -> 3 -> 1.
    assert parent_chain_has_cycle([0, 2, 3, 1], 1)

    d = DSU(8)
    d.union(0, 1)
    d.union(2, 3)
    d.union(1, 2)
    d.union(4, 5)
    assert d.find(0) == d.find(3)
    assert d.find(0) != d.find(4)
    root = d.find(3)
    assert d.size[root] == 4

    # Force a non-flat chain, then verify compression.
    d2 = DSU(4)
    d2.parent = [0, 0, 1, 2]
    assert d2.find(3) == 0
    assert d2.parent[3] == 0
    assert d2.parent[2] == 0


class Bitmap:
    def __init__(self, nbits: int, one_means_used: bool = True) -> None:
        self.nbits = nbits
        self.one_means_used = one_means_used
        self.data = bytearray((nbits + 7) // 8)

    def _mask(self, i: int) -> tuple[int, int]:
        assert 0 <= i < self.nbits
        return i // 8, 1 << (i % 8)

    def raw(self, i: int) -> bool:
        b, m = self._mask(i)
        return bool(self.data[b] & m)

    def set_raw(self, i: int, value: bool) -> None:
        b, m = self._mask(i)
        if value:
            self.data[b] |= m
        else:
            self.data[b] &= (~m) & 0xFF

    def is_free(self, i: int) -> bool:
        bit = self.raw(i)
        return (not bit) if self.one_means_used else bit


def first_free_with_hint(bitmap: Bitmap, hint: int) -> int:
    n = bitmap.nbits
    for off in range(n):
        i = (hint + off) % n
        if bitmap.is_free(i):
            return i
    return -1


def first_contig_free(bitmap: Bitmap, count: int) -> int:
    run = 0
    start = 0
    for i in range(bitmap.nbits):
        if bitmap.is_free(i):
            if run == 0:
                start = i
            run += 1
            if run == count:
                return start
        else:
            run = 0
    return -1


class CountedRing:
    def __init__(self, cap: int) -> None:
        self.a: list[int | None] = [None] * cap
        self.cap = cap
        self.head = 0
        self.tail = 0
        self.count = 0

    def push(self, value: int) -> bool:
        if self.count == self.cap:
            return False
        self.a[self.tail] = value
        self.tail = (self.tail + 1) % self.cap
        self.count += 1
        return True

    def pop(self) -> int | None:
        if self.count == 0:
            return None
        value = self.a[self.head]
        self.head = (self.head + 1) % self.cap
        self.count -= 1
        assert value is not None
        return value


class OverwriteRing:
    def __init__(self, cap: int) -> None:
        self.a = [0] * cap
        self.cap = cap
        self.pos = 0
        self.length = 0

    def put(self, value: int) -> None:
        self.a[self.pos] = value
        self.pos = (self.pos + 1) % self.cap
        self.length = min(self.length + 1, self.cap)

    def copy_tail(self, cap: int) -> list[int]:
        n = min(self.length, cap)
        start = (self.pos + self.cap - n) % self.cap
        return [self.a[(start + i) % self.cap] for i in range(n)]


class LinkedFreeList:
    def __init__(self, n: int) -> None:
        self.next = list(range(1, n)) + [-1]
        self.head = 0 if n else -1

    def alloc(self) -> int:
        if self.head == -1:
            return -1
        out = self.head
        self.head = self.next[out]
        self.next[out] = -2
        return out

    def free(self, item: int) -> None:
        assert self.next[item] == -2
        self.next[item] = self.head
        self.head = item


@dataclass
class VaSlot:
    virt: int = 0
    pages: int = 0
    used: bool = False


class JitVaModel:
    def __init__(self, slots: int = 8, base: int = 0x100000, limit: int = 0x200000, page: int = 4096) -> None:
        self.slots = [VaSlot() for _ in range(slots)]
        self.next = base
        self.limit = limit
        self.page = page

    def alloc(self, pages: int) -> int:
        for s in self.slots:
            if s.virt and not s.used and s.pages == pages:
                s.used = True
                return s.virt
        size = pages * self.page
        if self.next + size > self.limit:
            return 0
        virt = self.next
        self.next += size
        for s in self.slots:
            if s.virt == 0:
                s.virt, s.pages, s.used = virt, pages, True
                return virt
        return 0

    def free(self, virt: int) -> None:
        for s in self.slots:
            if s.virt == virt:
                s.used = False
                return


def check_compact_models() -> None:
    used = Bitmap(20, one_means_used=True)
    used.set_raw(0, True)
    used.set_raw(1, True)
    used.set_raw(7, True)
    assert not used.is_free(0)
    assert used.is_free(2)
    assert first_free_with_hint(used, 0) == 2
    assert first_free_with_hint(used, 8) == 8
    assert first_contig_free(used, 3) == 2

    free_mask = Bitmap(8, one_means_used=False)
    for i in range(8):
        free_mask.set_raw(i, True)
    free_mask.set_raw(3, False)
    assert free_mask.is_free(2)
    assert not free_mask.is_free(3)

    ring = CountedRing(4)
    assert all(ring.push(v) for v in [10, 11, 12, 13])
    assert ring.head == ring.tail and ring.count == 4
    assert not ring.push(14)
    assert ring.pop() == 10
    assert ring.pop() == 11
    assert ring.push(14) and ring.push(15)
    assert [ring.pop(), ring.pop(), ring.pop(), ring.pop()] == [12, 13, 14, 15]
    assert ring.pop() is None

    log = OverwriteRing(4)
    for v in range(7):
        log.put(v)
    assert log.copy_tail(4) == [3, 4, 5, 6]
    assert log.copy_tail(2) == [5, 6]

    fl = LinkedFreeList(3)
    assert [fl.alloc(), fl.alloc(), fl.alloc(), fl.alloc()] == [0, 1, 2, -1]
    fl.free(1)
    assert fl.alloc() == 1

    va = JitVaModel()
    a = va.alloc(2)
    b = va.alloc(4)
    assert a and b and a != b
    va.free(a)
    assert va.alloc(4) != a  # exact-size policy: 2-page range cannot satisfy 4 pages
    va.free(b)
    assert va.alloc(4) == b


def require(text: str, path: str, anchors: tuple[str, ...]) -> None:
    for anchor in anchors:
        if anchor not in text:
            raise AssertionError(f"{path}: missing reviewed anchor {anchor!r}")


def check_source_contract(source_root: Path) -> None:
    paths = {
        "sh_int": "kernel/gfx/shader/sh_int.h",
        "sh_sem": "kernel/gfx/shader/sh_sem.c",
        "cfs": "kernel/fs/cfs.c",
        "cfs_h": "kernel/fs/cfs.h",
        "pmm": "kernel/metal/pmm.c",
        "pmm_h": "kernel/metal/pmm.h",
        "job": "kernel/metal/job.c",
        "job_h": "kernel/metal/job.h",
        "klog": "kernel/metal/klog.c",
        "jit": "compiler/jit/jit.c",
    }
    src = {k: (source_root / p).read_text(encoding="utf-8") for k, p in paths.items()}

    require(src["sh_int"], paths["sh_int"], (
        "#define SH_SCOPE_MAX 48",
        "int scope_parent[SH_SCOPE_MAX];",
    ))
    require(src["sh_sem"], paths["sh_sem"], (
        "static int scope_has",
        "s = c->scope_parent[s];",
        "static void push_scope",
        "c->scope_parent[id] = c->cur_scope;",
        "static void pop_scope",
        "c->cur_scope = c->scope_parent[c->cur_scope];",
    ))
    require(src["cfs"], paths["cfs"], (
        "static int dir_find(Cfs *fs",
        "static int walk_full(Cfs *fs",
        "uint32_t cur = CFS_ROOT_INODE;",
        "static int bitmap_set(Cfs *fs",
        "static int bitmap_get(Cfs *fs",
        "static int block_alloc(Cfs *fs",
        "start = fs->alloc_hint;",
        "fs->alloc_hint = i + 1u;",
        "static int block_free(Cfs *fs",
    ))
    require(src["cfs_h"], paths["cfs_h"], (
        "uint32_t alloc_hint;",
    ))
    require(src["pmm_h"], paths["pmm_h"], (
        "#define PMM_PAGE     4096ull",
        "#define PMM_MAX_PHYS (32ull * 1024ull * 1024ull * 1024ull)",
    ))
    require(src["pmm"], paths["pmm"], (
        "static uint8_t pmm_bitmap[PMM_BITMAP_BYTES];",
        "static uint64_t pmm_cursor;",
        "static uint32_t dma32_free;",
        "static int bitmap_is_used",
        "static void bitmap_set_used",
        "static void bitmap_set_free",
        "pmm_bitmap[index] = 0xffu;",
        "pmm_bitmap[byte] == 0xFFu",
        "phys = scan_usable_for_run(1u, pmm_cursor);",
        "if (phys < pmm_cursor)",
        "pmm_cursor = phys;",
        "if ((dma32_free & mask) == mask)",
        "dma32_free &= ~mask;",
        "dma32_free |=",
    ))
    require(src["job_h"], paths["job_h"], (
        "#define JOB_QUEUE_CAP 1024u",
    ))
    require(src["job"], paths["job"], (
        "static Job g_queue[JOB_QUEUE_CAP];",
        "static uint32_t g_q_head;",
        "static uint32_t g_q_tail;",
        "static uint32_t g_q_count;",
        "if (g_q_count == JOB_QUEUE_CAP)",
        "g_q_tail = (g_q_tail + 1u) % JOB_QUEUE_CAP;",
        "g_q_head = (g_q_head + 1u) % JOB_QUEUE_CAP;",
    ))
    require(src["klog"], paths["klog"], (
        "#define KLOG_CAP 8192u",
        "static char g_log[KLOG_CAP];",
        "static uint32_t g_pos;",
        "static uint32_t g_len;",
        "if (g_pos == KLOG_CAP)",
        "if (g_len < KLOG_CAP)",
        "start = (g_pos + KLOG_CAP - n) % KLOG_CAP;",
    ))
    require(src["jit"], paths["jit"], (
        "#define JIT_VA_SLOTS 128u",
        "typedef struct JitVa",
        "static JitVa g_jit_va[JIT_VA_SLOTS];",
        "g_jit_va[i].pages == pages",
        "g_jit_va[i].used = 1;",
        "static void jit_va_free",
        "g_jit_va[i].used = 0;",
    ))


def check_documents(root: Path) -> None:
    for lang in ("en", "pt-br"):
        for name in ("graphs-union-find.md", "bitmaps-rings-free-lists.md"):
            path = root / "docs" / lang / "01-foundations" / name
            text = path.read_text(encoding="utf-8")
            if REVISION not in text:
                raise AssertionError(f"{path}: missing reviewed revision")

        graph = (root / "docs" / lang / "01-foundations" / "graphs-union-find.md").read_text(encoding="utf-8")
        require(graph, "graphs-union-find", (
            "scope_parent",
            "scope_has",
            "push_scope",
            "pop_scope",
            "union",
            "path compression",
            "CFS_ROOT_INODE",
        ))

        compact = (root / "docs" / lang / "01-foundations" / "bitmaps-rings-free-lists.md").read_text(encoding="utf-8")
        require(compact, "bitmaps-rings-free-lists", (
            "pmm_bitmap",
            "dma32_free",
            "alloc_hint",
            "JOB_QUEUE_CAP",
            "KLOG_CAP",
            "JIT_VA_SLOTS",
            "jit_va_alloc",
            "jit_va_free",
        ))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=".source")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    check_graph_models()
    check_compact_models()
    check_source_contract(Path(args.source))
    check_documents(root)

    print(
        "graph/compact-structure checks passed: adjacency semantics, components, "
        "DSU union-by-size/path-compression, bitmap scans, counted and overwrite rings, "
        "free-list reuse and JIT exact-size VA reuse"
    )
    print(
        "scope: deterministic models and reviewed source anchors; shader scopes and ChrisFS "
        "paths are not classified as generic graphs/DSU, and JIT VA reuse is not a linked freelist"
    )


if __name__ == "__main__":
    main()
