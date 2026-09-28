#!/usr/bin/env python3
"""Deterministic checks for sorting/searching and graph-algorithm chapters."""

from __future__ import annotations

import argparse
import heapq
from collections import deque
from pathlib import Path

REVISION = "da3df29cb397932c43d32373871fb9380e688ade"


def insertion_sort(items):
    a = list(items)
    for i in range(1, len(a)):
        x = a[i]
        j = i
        while j > 0 and x[0] < a[j - 1][0]:
            a[j] = a[j - 1]
            j -= 1
        a[j] = x
    return a


def merge_sort(items):
    a = list(items)
    if len(a) <= 1:
        return a
    mid = len(a) // 2
    left = merge_sort(a[:mid])
    right = merge_sort(a[mid:])
    out = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i][0] <= right[j][0]:
            out.append(left[i])
            i += 1
        else:
            out.append(right[j])
            j += 1
    out.extend(left[i:])
    out.extend(right[j:])
    return out


def heap_sort(values):
    h = list(values)
    heapq.heapify(h)
    return [heapq.heappop(h) for _ in range(len(h))]


def lower_bound(a, key):
    lo, hi = 0, len(a)
    while lo < hi:
        mid = lo + (hi - lo) // 2
        if a[mid] < key:
            lo = mid + 1
        else:
            hi = mid
    return lo


def upper_bound(a, key):
    lo, hi = 0, len(a)
    while lo < hi:
        mid = lo + (hi - lo) // 2
        if a[mid] <= key:
            lo = mid + 1
        else:
            hi = mid
    return lo


def editor_line_for_pos(starts, pos):
    assert starts
    lo, hi = 0, len(starts) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if starts[mid] <= pos:
            lo = mid
        else:
            hi = mid - 1
    return lo


def direct_find(text, pat, start=0):
    if not pat or start < 0:
        return -1
    for i in range(start, len(text) - len(pat) + 1):
        ok = True
        for j in range(len(pat)):
            if text[i + j] != pat[j]:
                ok = False
                break
        if ok:
            return i
    return -1


def check_sort_search_models():
    tagged = [(3, "A"), (1, "X"), (3, "B"), (2, "Y"), (3, "C")]
    expected = [(1, "X"), (2, "Y"), (3, "A"), (3, "B"), (3, "C")]
    assert insertion_sort(tagged) == expected
    assert merge_sort(tagged) == expected

    values = [9, 1, 8, 2, 7, 3, 6, 4, 5, 5]
    sorted_values = heap_sort(values)
    assert sorted_values == sorted(values)
    assert sorted(sorted_values) == sorted(values)

    a = [1, 2, 2, 2, 5, 8]
    assert lower_bound(a, 0) == 0
    assert lower_bound(a, 2) == 1
    assert upper_bound(a, 2) == 4
    assert lower_bound(a, 6) == 5
    assert upper_bound(a, 8) == 6

    starts = [0, 4, 10, 18]
    expected_lines = {
        0: 0,
        3: 0,
        4: 1,
        9: 1,
        10: 2,
        17: 2,
        18: 3,
        30: 3,
    }
    for pos, idx in expected_lines.items():
        got = editor_line_for_pos(starts, pos)
        assert got == idx
        assert starts[got] <= pos
        assert got == len(starts) - 1 or starts[got + 1] > pos

    assert direct_find("one two three two", "two", 0) == 4
    assert direct_find("one two three two", "two", 5) == 14
    assert direct_find("aaaaab", "aaab", 0) == 2
    assert direct_find("abc", "z", 0) == -1


def bfs(adj, source):
    dist = [-1] * len(adj)
    parent = [-1] * len(adj)
    q = deque([source])
    dist[source] = 0
    while q:
        u = q.popleft()
        for v in adj[u]:
            if dist[v] == -1:
                dist[v] = dist[u] + 1
                parent[v] = u
                q.append(v)
    return dist, parent


def dfs_reachable(adj, roots):
    seen = set()
    stack = list(roots)
    while stack:
        u = stack.pop()
        if u in seen:
            continue
        seen.add(u)
        stack.extend(adj.get(u, []))
    return seen


def has_directed_cycle(adj):
    n = len(adj)
    color = [0] * n

    def visit(u):
        color[u] = 1
        for v in adj[u]:
            if color[v] == 1:
                return True
            if color[v] == 0 and visit(v):
                return True
        color[u] = 2
        return False

    return any(color[u] == 0 and visit(u) for u in range(n))


def topo_kahn(adj):
    n = len(adj)
    indeg = [0] * n
    for u in range(n):
        for v in adj[u]:
            indeg[v] += 1
    q = deque(i for i, d in enumerate(indeg) if d == 0)
    out = []
    while q:
        u = q.popleft()
        out.append(u)
        for v in adj[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    return out if len(out) == n else None


def tarjan_scc(adj):
    n = len(adj)
    index = 0
    indices = [-1] * n
    low = [0] * n
    onstack = [False] * n
    stack = []
    comps = []

    def visit(v):
        nonlocal index
        indices[v] = low[v] = index
        index += 1
        stack.append(v)
        onstack[v] = True
        for w in adj[v]:
            if indices[w] == -1:
                visit(w)
                low[v] = min(low[v], low[w])
            elif onstack[w]:
                low[v] = min(low[v], indices[w])
        if low[v] == indices[v]:
            comp = []
            while True:
                w = stack.pop()
                onstack[w] = False
                comp.append(w)
                if w == v:
                    break
            comps.append(frozenset(comp))

    for v in range(n):
        if indices[v] == -1:
            visit(v)
    return set(comps)


def dijkstra(adj, source):
    inf = 10**18
    dist = [inf] * len(adj)
    dist[source] = 0
    pq = [(0, source)]
    while pq:
        du, u = heapq.heappop(pq)
        if du != dist[u]:
            continue
        for v, w in adj[u]:
            assert w >= 0
            cand = du + w
            if cand < dist[v]:
                dist[v] = cand
                heapq.heappush(pq, (cand, v))
    return dist


def bellman_ford(n, edges, source):
    inf = 10**18
    dist = [inf] * n
    dist[source] = 0
    for _ in range(n - 1):
        changed = False
        for u, v, w in edges:
            if dist[u] != inf and dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
                changed = True
        if not changed:
            break
    neg = any(
        dist[u] != inf and dist[u] + w < dist[v]
        for u, v, w in edges
    )
    return dist, neg


class DSU:
    def __init__(self, n):
        self.p = list(range(n))
        self.size = [1] * n

    def find(self, x):
        if self.p[x] != x:
            self.p[x] = self.find(self.p[x])
        return self.p[x]

    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        if a == b:
            return False
        if self.size[a] < self.size[b]:
            a, b = b, a
        self.p[b] = a
        self.size[a] += self.size[b]
        return True


def kruskal(n, edges):
    dsu = DSU(n)
    total = 0
    picked = []
    for w, u, v in sorted(edges):
        if dsu.union(u, v):
            total += w
            picked.append((u, v, w))
    return total, picked


def check_graph_models():
    adj = [[1, 2], [3], [3, 4], [5], [5], []]
    dist, parent = bfs(adj, 0)
    assert dist == [0, 1, 1, 2, 2, 3]
    v = 5
    path = []
    while v != -1:
        path.append(v)
        v = parent[v]
    path.reverse()
    assert path[0] == 0 and path[-1] == 5 and len(path) - 1 == 3

    named = {
        "host-gates": ["a", "b"],
        "a": ["c"],
        "b": ["d"],
        "c": ["host-gates"],
        "d": [],
    }
    assert dfs_reachable(named, ["host-gates"]) == {"host-gates", "a", "b", "c", "d"}

    dag = [[1, 2], [3], [3], []]
    cyclic = [[1], [2], [0]]
    assert not has_directed_cycle(dag)
    assert has_directed_cycle(cyclic)
    order = topo_kahn(dag)
    assert order is not None
    pos = {v: i for i, v in enumerate(order)}
    for u in range(len(dag)):
        for v in dag[u]:
            assert pos[u] < pos[v]
    assert topo_kahn(cyclic) is None

    scc_graph = [[1], [2], [0, 3], [4], [3, 5], []]
    comps = tarjan_scc(scc_graph)
    assert frozenset({0, 1, 2}) in comps
    assert frozenset({3, 4}) in comps
    assert frozenset({5}) in comps

    weighted = [
        [(1, 4), (2, 1)],
        [(3, 1)],
        [(1, 2), (3, 5)],
        [],
    ]
    assert dijkstra(weighted, 0) == [0, 3, 1, 4]

    edges = [(0, 1, 4), (0, 2, 5), (1, 2, -2), (2, 3, 3)]
    dist, neg = bellman_ford(4, edges, 0)
    assert dist == [0, 4, 2, 5] and not neg
    _, neg2 = bellman_ford(3, [(0, 1, 1), (1, 2, -2), (2, 1, -2)], 0)
    assert neg2

    mst_edges = [
        (1, 0, 1),
        (4, 0, 2),
        (2, 1, 2),
        (5, 1, 3),
        (1, 2, 3),
    ]
    total, picked = kruskal(4, mst_edges)
    assert total == 4
    assert len(picked) == 3


def require(text, path, anchors):
    for anchor in anchors:
        if anchor not in text:
            raise AssertionError(f"{path}: missing reviewed anchor {anchor!r}")


def check_source_contract(source_root):
    editor_path = "APPS/EDITOR/EDITOR.CC"
    model_path = "compiler/edit/editmodel.c"
    pmm_test_path = "tools/test_pmm_heap_smp.c"
    doom_scan_path = "tools/run_doom_cmp_scan.py"
    gates_path = "tools/check_test_gates.py"
    make_path = "makefile"

    editor = (source_root / editor_path).read_text(encoding="utf-8")
    model = (source_root / model_path).read_text(encoding="utf-8")
    pmm_test = (source_root / pmm_test_path).read_text(encoding="utf-8")
    doom_scan = (source_root / doom_scan_path).read_text(encoding="utf-8")
    gates = (source_root / gates_path).read_text(encoding="utf-8")
    makefile = (source_root / make_path).read_text(encoding="utf-8")

    require(editor, editor_path, (
        "int line_for_pos(int p)",
        "mid = (lo + hi + 1) / 2;",
        "if (g_line_starts[mid] <= p)",
        "hi = mid - 1;",
        "int find_from(int start, int dir)",
        "p = find_from(g_cur + 1, 1);",
        "p = find_from(g_cur - 1, -1);",
    ))
    require(model, model_path, (
        "int edit_search(int id, const char *pat, int from)",
        "for (i = from; i + n <= len; ++i)",
        "if (char_at(b, i + k) != pat[k])",
    ))
    require(pmm_test, pmm_test_path, (
        "static int cmp_u64",
        "qsort(all, NCPU * PAGES_PER, sizeof(all[0]), cmp_u64);",
        'fprintf(stderr, "duplicate phys',
    ))
    require(doom_scan, doom_scan_path, (
        '"""Binary-search first PC where JIT SP diverges from interpreter (via cmp2)."""',
        "candidates = [",
        "for pc in candidates:",
        "kind, out = probe(pc)",
    ))
    if "mid =" in doom_scan or "while lo" in doom_scan or "while hi" in doom_scan:
        raise AssertionError(
            f"{doom_scan_path}: now appears to contain midpoint narrowing; "
            "reconcile the chapter before accepting this source change"
        )

    require(gates, gates_path, (
        'ROOTS = ("host-gates",)',
        "rules.setdefault(name, [])",
        "rules[name].extend(deps)",
        "seen = set()",
        "stack = list(ROOTS)",
        "while stack:",
        "name = stack.pop()",
        "if name in seen:",
        "seen.add(name)",
        "stack.extend(rules.get(name, []))",
        "for name in sorted(rules):",
    ))
    require(makefile, make_path, (
        "host-gates:",
        "host-gate-audit:",
        "python3 tools/check_test_gates.py",
    ))


def check_documents(root):
    docs = {
        "sorting_en": root / "docs/en/01-foundations/sorting-searching.md",
        "sorting_pt": root / "docs/pt-br/01-foundations/sorting-searching.md",
        "graph_en": root / "docs/en/01-foundations/graph-algorithms.md",
        "graph_pt": root / "docs/pt-br/01-foundations/graph-algorithms.md",
    }
    texts = {k: p.read_text(encoding="utf-8") for k, p in docs.items()}
    for key, text in texts.items():
        if REVISION not in text:
            raise AssertionError(f"{docs[key]}: missing reviewed revision")

    for key in ("sorting_en", "sorting_pt"):
        require(texts[key], str(docs[key]), (
            "line_for_pos",
            "find_from",
            "edit_search",
            "qsort",
            "run_doom_cmp_scan.py",
            "lower_bound",
            "upper_bound",
        ))

    for key in ("graph_en", "graph_pt"):
        require(texts[key], str(docs[key]), (
            "check_test_gates.py",
            "host-gates",
            "stack",
            "seen",
            "Dijkstra",
            "Bellman-Ford",
            "Kruskal",
        ))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=".source")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    check_sort_search_models()
    check_graph_models()
    check_source_contract(Path(args.source))
    check_documents(root)

    print(
        "sort/graph algorithm checks passed: stable insertion/merge sorting, heap ordering, "
        "binary-search bounds, direct search, BFS/DFS, cycle/topological checks, SCC, "
        "Dijkstra, Bellman-Ford and Kruskal"
    )
    print(
        "source boundary passed: editor line lookup is binary search, editor text search is "
        "direct scanning, PMM validation calls host qsort, the DOOM scan script currently "
        "probes fixed candidates, and host-gate auditing is LIFO reachability"
    )


if __name__ == "__main__":
    main()
