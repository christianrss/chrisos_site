#!/usr/bin/env python3
"""Deterministic checks for number systems and finite-width binary arithmetic."""

from __future__ import annotations

import argparse
from pathlib import Path


REVISION = "da3df29cb397932c43d32373871fb9380e688ade"


def to_signed(value: int, bits: int) -> int:
    mask = (1 << bits) - 1
    value &= mask
    sign = 1 << (bits - 1)
    return value if value < sign else value - (1 << bits)


def sign_extend(value: int, src_bits: int, dst_bits: int) -> int:
    signed = to_signed(value, src_bits)
    return signed & ((1 << dst_bits) - 1)


def horner(text: str, base: int) -> int:
    value = 0
    for ch in text:
        if "0" <= ch <= "9":
            digit = ord(ch) - ord("0")
        elif "A" <= ch <= "F":
            digit = 10 + ord(ch) - ord("A")
        elif "a" <= ch <= "f":
            digit = 10 + ord(ch) - ord("a")
        else:
            raise ValueError(ch)
        if digit >= base:
            raise ValueError(ch)
        value = value * base + digit
    return value


def check_math() -> None:
    assert int("101101", 2) == 45
    assert int("2D", 16) == 45
    assert (1 << 8) - 1 == 255
    assert (1 << 16) - 1 == 65535

    assert (250 + 10) % 256 == 4
    assert (0 - 1) % 256 == 255

    assert to_signed(0xFF, 8) == -1
    assert to_signed(0x80, 8) == -128
    assert to_signed(0x7F, 8) == 127

    assert sign_extend(0xFB, 8, 16) == 0xFFFB
    assert (0xFB & 0xFF) == 0x00FB

    x = 0x16
    assert ((x << 2) & 0xFF) == ((x * 4) % 256)
    assert (0xB0 >> 3) == 0x16

    assert horner("101101", 2) == 45
    assert horner("2D", 16) == 45
    assert horner("255", 10) == 255

    red, green, blue = 0x12, 0x34, 0x56
    packed_shift = (red << 16) | (green << 8) | blue
    packed_positional = red * (1 << 16) + green * (1 << 8) + blue
    assert packed_shift == packed_positional == 0x123456


def check_source_contract(source_root: Path) -> None:
    flags = (source_root / "chrisvm" / "cpu" / "emulator" / "flags.c").read_text(encoding="utf-8")
    arch = (source_root / "chrisvm" / "chris_arch.h").read_text(encoding="utf-8")
    asm = (source_root / "compiler" / "chrisasm" / "chrisasm.c").read_text(encoding="utf-8")
    gfx = (source_root / "kernel" / "gfx" / "graphics.c").read_text(encoding="utf-8")

    for anchor in (
        "static uint64_t size_mask",
        "static uint64_t sign_bit",
        "uint64_t chris_flags_bin",
        "unsigned __int128 wide",
        "int chris_cc_true",
    ):
        if anchor not in flags:
            raise AssertionError(f"flags.c missing reviewed anchor {anchor!r}")

    for anchor in (
        "typedef struct ChrisArchitectureState",
        "uint64_t gpr[16]",
        "uint64_t rip;",
    ):
        if anchor not in arch:
            raise AssertionError(f"chris_arch.h missing reviewed anchor {anchor!r}")

    for anchor in (
        "static int parse_u64",
        "base = 16",
        "v > (18446744073709551615ull - (uint64_t)d) / (uint64_t)base",
        "static void emit_u32",
        "static void emit_u64",
    ):
        if anchor not in asm:
            raise AssertionError(f"chrisasm.c missing reviewed anchor {anchor!r}")

    for anchor in (
        "uint32_t gfx_rgb",
        "((uint32_t)red << 16)",
        "((uint32_t)green << 8)",
    ):
        if anchor not in gfx:
            raise AssertionError(f"graphics.c missing reviewed anchor {anchor!r}")


def check_documents(root: Path) -> None:
    filename = "number-systems-binary-arithmetic.md"
    paths = (
        root / "docs" / "en" / "01-foundations" / filename,
        root / "docs" / "pt-br" / "01-foundations" / filename,
    )

    required = (
        "ChrisArchitectureState",
        "chris_flags_bin",
        "chris_cc_true",
        "parse_u64",
        "emit_u32",
        "emit_u64",
        "gfx_rgb",
        "2^n - 1",
        "0xFF",
        "0x80",
        "0xFFFB",
        "0x00FB",
        "Horner",
        "093",
        "flags.c",
        "chrisasm.c",
        "graphics.c",
    )

    for path in paths:
        text = path.read_text(encoding="utf-8")
        if REVISION not in text:
            raise AssertionError(f"{path}: missing reviewed revision")
        for anchor in required:
            if anchor not in text:
                raise AssertionError(f"{path}: missing {anchor!r}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=".source")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    source_root = Path(args.source)

    check_math()
    check_source_contract(source_root)
    check_documents(root)

    print(
        "number-system checks passed: base conversion, finite-width modular arithmetic, "
        "two's-complement interpretation, extension, shifts, Horner parsing, RGB packing "
        "and reviewed ChrisOS source anchors"
    )
    print(
        "scope: deterministic mathematical/source checks only; no claim of complete "
        "x86, C-language, floating-point or arbitrary-precision conformance"
    )


if __name__ == "__main__":
    main()
