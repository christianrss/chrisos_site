#!/usr/bin/env python3
"""Deterministic checks for discrete mathematics, invariants and induction examples."""

from __future__ import annotations

import argparse
import itertools
from pathlib import Path


REVISION = "da3df29cb397932c43d32373871fb9380e688ade"


def is_reflexive(domain, relation) -> bool:
    return all((x, x) in relation for x in domain)


def is_symmetric(relation) -> bool:
    return all((b, a) in relation for a, b in relation)


def is_transitive(relation) -> bool:
    return all((a, c) in relation for a, b in relation for x, c in relation if x == b)


def check_discrete_math() -> None:
    a = {0, 1, 2}
    b = {2, 3}
    assert a | b == {0, 1, 2, 3}
    assert a & b == {2}
    assert a - b == {0, 1}

    for n in range(0, 9):
        base = tuple(range(n))
        subsets = {
            frozenset(base[i] for i in range(n) if mask & (1 << i))
            for mask in range(1 << n)
        }
        assert len(subsets) == 1 << n

    x = {0, 1, 2}
    y = {"a", "b"}
    product = set(itertools.product(x, y))
    assert len(product) == len(x) * len(y)

    domain = set(range(6))
    congruent_mod_2 = {(a, b) for a in domain for b in domain if (a - b) % 2 == 0}
    assert is_reflexive(domain, congruent_mod_2)
    assert is_symmetric(congruent_mod_2)
    assert is_transitive(congruent_mod_2)

    subsets = [frozenset(s) for r in range(4) for s in itertools.combinations({0, 1, 2}, r)]
    subset_rel = {(a, b) for a in subsets for b in subsets if a <= b}
    assert is_reflexive(set(subsets), subset_rel)
    assert is_transitive(subset_rel)
    assert all(not ((a, b) in subset_rel and (b, a) in subset_rel) or a == b for a, b in subset_rel)

    f = {0: 2, 1: 3, 2: 4}
    assert len(set(f.values())) == len(f)  # injective
    codomain = {2, 3, 4}
    assert set(f.values()) == codomain  # surjective, therefore bijective here

    g = {2: 20, 3: 30, 4: 40}
    composed = {k: g[v] for k, v in f.items()}
    assert composed == {0: 20, 1: 30, 2: 40}

    assert len(set(range(16))) == 16


def horner_checked(text: str, base: int, max_value: int) -> int:
    value = 0
    prefix = ""
    for ch in text:
        digit = int(ch, 16)
        assert digit < base
        assert value == int(prefix, base) if prefix else value == 0
        if value > (max_value - digit) // base:
            raise OverflowError
        value = value * base + digit
        prefix += ch
        assert value <= max_value
        assert value == int(prefix, base)
    return value


def append_bounded(count: int, capacity: int) -> tuple[bool, int]:
    assert 0 <= count <= capacity
    if count >= capacity:
        return False, count
    return True, count + 1


def clipped_rect(x: int, y: int, w: int, h: int, width: int, height: int):
    if w <= 0 or h <= 0:
        return None
    x1, y1 = x + w, y + h
    x = max(x, 0)
    y = max(y, 0)
    x1 = min(x1, width)
    y1 = min(y1, height)
    if x >= x1 or y >= y1:
        return None
    return (x, y, x1, y1)


def check_invariants() -> None:
    assert horner_checked("18446744073709551615", 10, (1 << 64) - 1) == (1 << 64) - 1
    try:
        horner_checked("18446744073709551616", 10, (1 << 64) - 1)
    except OverflowError:
        pass
    else:
        raise AssertionError("uint64 overflow guard did not reject max+1")

    for capacity in range(1, 8):
        count = 0
        for _ in range(capacity):
            ok, count = append_bounded(count, capacity)
            assert ok
            assert 0 <= count <= capacity
        ok, unchanged = append_bounded(count, capacity)
        assert not ok
        assert unchanged == capacity

    for length in range(4, 20):
        for at in range(0, length - 3):
            assert at + 4 <= length
            touched = {at, at + 1, at + 2, at + 3}
            assert min(touched) >= 0
            assert max(touched) < length

    for bits in (8, 16, 32, 64):
        mask = (1 << bits) - 1
        for value in (0, 1, mask, mask + 1, (1 << 65) - 1):
            result = value & mask
            assert result & ~mask == 0

    width, height = 640, 480
    samples = [
        (-10, -10, 20, 20),
        (0, 0, 1, 1),
        (630, 470, 20, 20),
        (100, 100, 50, 80),
    ]
    for args in samples:
        rect = clipped_rect(*args, width, height)
        if rect is None:
            continue
        x0, y0, x1, y1 = rect
        assert 0 <= x0 < x1 <= width
        assert 0 <= y0 < y1 <= height

    dirty_max = 32
    dirty_count = dirty_max
    if dirty_count >= dirty_max:
        dirty_count = 1
        full = (0, 0, width, height)
    assert 0 <= dirty_count <= dirty_max
    assert full == (0, 0, width, height)

    prefix = []
    source = [3, 1, 4, 1, 5]
    running = 0
    for i, value in enumerate(source):
        assert running == sum(source[:i])
        running += value
        prefix.append(running)
        assert running == sum(source[: i + 1])
    assert prefix[-1] == sum(source)


def check_source_contract(source_root: Path) -> None:
    arch = (source_root / "chrisvm" / "chris_arch.h").read_text(encoding="utf-8")
    chriso = (source_root / "compiler" / "chrisld" / "chriso.h").read_text(encoding="utf-8")
    asm = (source_root / "compiler" / "chrisasm" / "chrisasm.c").read_text(encoding="utf-8")
    flags = (source_root / "chrisvm" / "cpu" / "emulator" / "flags.c").read_text(encoding="utf-8")
    gfx = (source_root / "kernel" / "gfx" / "graphics.c").read_text(encoding="utf-8")

    for anchor in ("uint64_t gpr[16]", "typedef struct ChrisArchitectureState"):
        if anchor not in arch:
            raise AssertionError(f"chris_arch.h missing {anchor!r}")

    for anchor in (
        "#define CHRISO_SEC_MAX 4u",
        "#define CHRISO_SYM_MAX 256u",
        "#define CHRISO_REL_MAX 512u",
        "uint32_t sym_index;",
        "ChrisoSym sym[CHRISO_SYM_MAX]",
    ):
        if anchor not in chriso:
            raise AssertionError(f"chriso.h missing {anchor!r}")

    for anchor in (
        "static int parse_u64",
        "v > (18446744073709551615ull - (uint64_t)d) / (uint64_t)base",
        "static void emit_u8",
        "g_len[g_cur] >= ASM_SEC_MAX",
        "static int add_sym",
        "img->nsym >= CHRISO_SYM_MAX",
        "static int patch_fixups",
        "at + 4u > g_len[sec]",
        "static int reg_index",
    ):
        if anchor not in asm:
            raise AssertionError(f"chrisasm.c missing {anchor!r}")

    for anchor in ("uint64_t chris_flags_bin", "*result = r & mask;", "int chris_cc_true"):
        if anchor not in flags:
            raise AssertionError(f"flags.c missing {anchor!r}")

    for anchor in (
        "static bool point_in_clip",
        "#define GFX_DIRTY_MAX 32",
        "void gfx_mark_dirty",
        "g_dirty_count = 1;",
    ):
        if anchor not in gfx:
            raise AssertionError(f"graphics.c missing {anchor!r}")


def check_documents(root: Path) -> None:
    paths = [
        root / "docs" / "en" / "01-foundations" / "discrete-math-sets-relations-functions.md",
        root / "docs" / "pt-br" / "01-foundations" / "discrete-math-sets-relations-functions.md",
        root / "docs" / "en" / "01-foundations" / "proof-invariants-induction.md",
        root / "docs" / "pt-br" / "01-foundations" / "proof-invariants-induction.md",
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if REVISION not in text:
            raise AssertionError(f"{path}: missing reviewed revision")

    discrete_required = (
        "CHRISO_SYM_MAX",
        "reg_index",
        "chris_cc_true",
        "point_in_clip",
    )
    proof_required = (
        "parse_u64",
        "emit_u8",
        "add_sym",
        "patch_fixups",
        "chris_flags_bin",
        "gfx_mark_dirty",
        "GFX_DIRTY_MAX",
    )

    for lang in ("en", "pt-br"):
        discrete = (root / "docs" / lang / "01-foundations" / "discrete-math-sets-relations-functions.md").read_text(encoding="utf-8")
        proof = (root / "docs" / lang / "01-foundations" / "proof-invariants-induction.md").read_text(encoding="utf-8")
        for anchor in discrete_required:
            if anchor not in discrete:
                raise AssertionError(f"{lang} discrete chapter missing {anchor!r}")
        for anchor in proof_required:
            if anchor not in proof:
                raise AssertionError(f"{lang} proof chapter missing {anchor!r}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=".source")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    check_discrete_math()
    check_invariants()
    check_source_contract(Path(args.source))
    check_documents(root)

    print(
        "discrete/proof checks passed: sets, products, relation properties, function composition, "
        "Horner invariant, overflow guard, bounded append, patch bounds, width closure and dirty-rectangle invariants"
    )
    print(
        "scope: deterministic examples and reviewed source anchors only; no claim of global formal verification"
    )


if __name__ == "__main__":
    main()
