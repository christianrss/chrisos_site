#!/usr/bin/env python3
"""Deterministic checks for hash tables, trees, binary heaps and tries."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

REVISION = "da3df29cb397932c43d32373871fb9380e688ade"


def fnv1a32(data: bytes) -> int:
    h = 2166136261
    for b in data:
        h ^= b
        h = (h * 16777619) & 0xFFFFFFFF
    return h


class LinearProbeTable:
    def __init__(self, cap: int) -> None:
        assert cap > 0 and cap & (cap - 1) == 0
        self.cap = cap
        self.slots = [0] * cap
        self.keys: list[str] = []

    def add_record(self, key: str) -> int:
        idx = len(self.keys)
        self.keys.append(key)
        return idx

    def insert(self, key: str, idx: int) -> bool:
        h = fnv1a32(key.encode())
        for i in range(self.cap):
            s = (h + i) & (self.cap - 1)
            v = self.slots[s]
            if v == 0:
                self.slots[s] = idx + 1
                return True
            if self.keys[v - 1] == key:
                return True
        return False

    def find(self, key: str) -> int:
        h = fnv1a32(key.encode())
        for i in range(self.cap):
            s = (h + i) & (self.cap - 1)
            v = self.slots[s]
            if v == 0:
                return -1
            if self.keys[v - 1] == key:
                return v - 1
        return -1


def colliding_keys(cap: int, count: int) -> list[str]:
    buckets: dict[int, list[str]] = {}
    i = 0
    while True:
        key = f"k{i}"
        b = fnv1a32(key.encode()) & (cap - 1)
        group = buckets.setdefault(b, [])
        group.append(key)
        if len(group) >= count:
            return group[:count]
        i += 1


def check_hash_models() -> None:
    assert fnv1a32(b"") == 2166136261
    assert fnv1a32(b"a") == 0xE40C292C
    assert fnv1a32(b"foobar") == 0xBF9CF968

    caps = {
        "def": (4096, 8192),
        "func": (4096, 8192),
        "typedef": (1024, 2048),
        "struct": (1024, 2048),
        "symbol": (16384, 32768),
        "const": (4096, 8192),
    }
    for max_items, cap in caps.values():
        assert cap & (cap - 1) == 0
        assert max_items / cap <= 0.5

    table = LinearProbeTable(8)
    keys = colliding_keys(8, 3)
    ids = [table.add_record(k) for k in keys]
    for key, idx in zip(keys, ids):
        assert table.insert(key, idx)
    for key, idx in zip(keys, ids):
        assert table.find(key) == idx
    assert table.find("definitely-absent") == -1

    # id zero must remain representable while slot zero means empty.
    t2 = LinearProbeTable(4)
    zero_id = t2.add_record("zero")
    assert zero_id == 0
    assert t2.insert("zero", zero_id)
    assert any(v == 1 for v in t2.slots)
    assert t2.find("zero") == 0


@dataclass
class TNode:
    value: int
    left: int = -1
    right: int = -1


def preorder(nodes: list[TNode], root: int) -> list[int]:
    if root == -1:
        return []
    assert 0 <= root < len(nodes)
    return [nodes[root].value] + preorder(nodes, nodes[root].left) + preorder(nodes, nodes[root].right)


def inorder(nodes: list[TNode], root: int) -> list[int]:
    if root == -1:
        return []
    assert 0 <= root < len(nodes)
    return inorder(nodes, nodes[root].left) + [nodes[root].value] + inorder(nodes, nodes[root].right)


def postorder(nodes: list[TNode], root: int) -> list[int]:
    if root == -1:
        return []
    assert 0 <= root < len(nodes)
    return postorder(nodes, nodes[root].left) + postorder(nodes, nodes[root].right) + [nodes[root].value]


def bst_insert(nodes: list[TNode], root: int, value: int) -> int:
    if root == -1:
        nodes.append(TNode(value))
        return len(nodes) - 1
    cur = root
    while True:
        if value < nodes[cur].value:
            if nodes[cur].left == -1:
                nodes.append(TNode(value))
                nodes[cur].left = len(nodes) - 1
                return root
            cur = nodes[cur].left
        else:
            if nodes[cur].right == -1:
                nodes.append(TNode(value))
                nodes[cur].right = len(nodes) - 1
                return root
            cur = nodes[cur].right


def tree_height(nodes: list[TNode], root: int) -> int:
    if root == -1:
        return -1
    return 1 + max(tree_height(nodes, nodes[root].left), tree_height(nodes, nodes[root].right))


def check_tree_models() -> None:
    nodes = [
        TNode(4, 1, 2),
        TNode(2, 3, 4),
        TNode(6),
        TNode(1),
        TNode(3),
    ]
    assert preorder(nodes, 0) == [4, 2, 1, 3, 6]
    assert inorder(nodes, 0) == [1, 2, 3, 4, 6]
    assert postorder(nodes, 0) == [1, 3, 2, 6, 4]

    bst: list[TNode] = []
    root = -1
    for value in range(8):
        root = bst_insert(bst, root, value)
    assert inorder(bst, root) == list(range(8))
    assert tree_height(bst, root) == 7  # sorted insert degenerates without balancing


class MinHeap:
    def __init__(self, values: list[int] | None = None) -> None:
        self.a = [] if values is None else list(values)
        if values is not None:
            for i in range((len(self.a) // 2) - 1, -1, -1):
                self._down(i)

    @staticmethod
    def parent(i: int) -> int:
        return (i - 1) // 2

    @staticmethod
    def left(i: int) -> int:
        return 2 * i + 1

    @staticmethod
    def right(i: int) -> int:
        return 2 * i + 2

    def _down(self, i: int) -> None:
        n = len(self.a)
        while True:
            l = self.left(i)
            r = self.right(i)
            smallest = i
            if l < n and self.a[l] < self.a[smallest]:
                smallest = l
            if r < n and self.a[r] < self.a[smallest]:
                smallest = r
            if smallest == i:
                return
            self.a[i], self.a[smallest] = self.a[smallest], self.a[i]
            i = smallest

    def push(self, value: int) -> None:
        self.a.append(value)
        i = len(self.a) - 1
        while i > 0:
            p = self.parent(i)
            if self.a[p] <= self.a[i]:
                return
            self.a[p], self.a[i] = self.a[i], self.a[p]
            i = p

    def pop(self) -> int:
        if not self.a:
            raise IndexError("empty heap")
        out = self.a[0]
        last = self.a.pop()
        if self.a:
            self.a[0] = last
            self._down(0)
        return out

    def valid(self) -> bool:
        for i in range(len(self.a)):
            l, r = self.left(i), self.right(i)
            if l < len(self.a) and self.a[i] > self.a[l]:
                return False
            if r < len(self.a) and self.a[i] > self.a[r]:
                return False
        return True


def check_heap_models() -> None:
    for i in range(1, 128):
        p = MinHeap.parent(i)
        assert MinHeap.left(p) == i or MinHeap.right(p) == i

    h = MinHeap()
    values = [9, 2, 7, 1, 8, 3, 6, 4, 5, 0]
    for v in values:
        h.push(v)
        assert h.valid()
    assert h.a[0] == 0
    assert [h.pop() for _ in values] == sorted(values)

    built = MinHeap(values)
    assert built.valid()
    assert [built.pop() for _ in values] == sorted(values)


@dataclass
class TrieNode:
    children: dict[str, "TrieNode"] = field(default_factory=dict)
    terminal: bool = False


class Trie:
    def __init__(self) -> None:
        self.root = TrieNode()

    def insert(self, key: str) -> None:
        n = self.root
        for ch in key:
            n = n.children.setdefault(ch, TrieNode())
        n.terminal = True

    def contains(self, key: str) -> bool:
        n = self.root
        for ch in key:
            if ch not in n.children:
                return False
            n = n.children[ch]
        return n.terminal

    def has_prefix(self, prefix: str) -> bool:
        n = self.root
        for ch in prefix:
            if ch not in n.children:
                return False
            n = n.children[ch]
        return True


def check_trie_models() -> None:
    t = Trie()
    for key in ("car", "cat", "net", "network"):
        t.insert(key)
    assert t.contains("car")
    assert t.contains("net")
    assert t.contains("network")
    assert not t.contains("ca")
    assert t.has_prefix("ca")
    assert t.has_prefix("netw")
    assert not t.has_prefix("dog")


def require(text: str, path: str, anchors: tuple[str, ...]) -> None:
    for anchor in anchors:
        if anchor not in text:
            raise AssertionError(f"{path}: missing reviewed anchor {anchor!r}")


def check_source_contract(source_root: Path) -> None:
    chrisc_path = "compiler/chrisc/chrisc.c"
    clvm_path = "compiler/clvm/clvm_format.c"
    cfs_path = "kernel/fs/cfs.c"
    heap_path = "kernel/metal/heap.c"

    chrisc = (source_root / chrisc_path).read_text(encoding="utf-8")
    clvm = (source_root / clvm_path).read_text(encoding="utf-8")
    cfs = (source_root / cfs_path).read_text(encoding="utf-8")
    heap = (source_root / heap_path).read_text(encoding="utf-8")

    require(chrisc, chrisc_path, (
        "#define NODE_MAX 131072",
        "#define SYM_MAX 16384",
        "#define HT_DEF_N 8192",
        "#define HT_FUNC_N 8192",
        "#define HT_TD_N 2048",
        "#define HT_ST_N 2048",
        "#define HT_SYM_N 32768",
        "#define HT_CONST_N 8192",
        "int left, right, third, next;",
        "uint16_t ht_sym[HT_SYM_N];",
        "static unsigned hash_str(const char *s)",
        "h = 2166136261u;",
        "h *= 16777619u;",
        "static int ht_find_grid",
        "static void ht_ins_grid",
        "(h + (unsigned)i) & (unsigned)(cap - 1)",
        "tab[s] = (uint16_t)(id + 1);",
        "static int sym_find_local",
        "for (i = c->nsyms - 1; i >= 0; --i)",
        "static int sym_find(Compiler *c, const char *name)",
        "static int node(Compiler *c, NodeKind k, Token *t)",
        "n->left = n->right = n->third = n->next = -1;",
        "static int gen_expr(Compiler *c, int id)",
    ))
    require(clvm, clvm_path, (
        "uint32_t clvm_fnv1a32",
        "uint32_t hash = 2166136261u;",
        "hash ^= data[i];",
        "hash *= 16777619u;",
        "CL_LOAD_CHECKSUM",
    ))
    require(cfs, cfs_path, (
        "static int dir_find(Cfs *fs",
        "for (b = 0; b < CFS_DIR_MAX_BLOCKS; b++)",
        "for (slot = 0; slot < CFS_DIRENTS_PER_SECTOR; slot++)",
        "static int walk_parent(Cfs *fs",
        "static int walk_full(Cfs *fs",
        "uint32_t cur = CFS_ROOT_INODE;",
    ))
    require(heap, heap_path, (
        "struct heap_block",
        "struct heap_arena",
        "static void *kmalloc_in_arenas",
        "for (i = 0; i < narenas; ++i)",
        "while (block_in_arena(&arenas[i], block)",
        "static void coalesce_forward",
        "void *kmalloc(uint64_t size)",
        "void kfree(void *ptr)",
    ))


def check_documents(root: Path) -> None:
    for lang in ("en", "pt-br"):
        for name in ("hash-tables.md", "trees-heaps-tries.md"):
            path = root / "docs" / lang / "01-foundations" / name
            text = path.read_text(encoding="utf-8")
            if REVISION not in text:
                raise AssertionError(f"{path}: missing reviewed revision")

        h = (root / "docs" / lang / "01-foundations" / "hash-tables.md").read_text(encoding="utf-8")
        require(h, "hash-tables", (
            "FNV-1a",
            "linear probing",
            "HT_SYM_N",
            "ht_find_grid",
            "ht_ins_grid",
            "sym_find_local",
            "clvm_fnv1a32",
        ))

        t = (root / "docs" / lang / "01-foundations" / "trees-heaps-tries.md").read_text(encoding="utf-8")
        require(t, "trees-heaps-tries", (
            "NODE_MAX",
            "gen_expr",
            "CFS_ROOT_INODE",
            "dir_find",
            "walk_full",
            "heap_block",
            "binary heap",
            "trie",
        ))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=".source")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    check_hash_models()
    check_tree_models()
    check_heap_models()
    check_trie_models()
    check_source_contract(Path(args.source))
    check_documents(root)

    print(
        "hash/tree/heap/trie checks passed: FNV-1a, linear probing, load bounds, "
        "tree traversals, BST degeneration, min-heap operations and trie prefixes"
    )
    print(
        "scope: deterministic models and reviewed source anchors; ChrisC AST is not "
        "classified as a BST, ChrisFS lookup is not a trie, and kernel heap.c is not a priority heap"
    )


if __name__ == "__main__":
    main()
