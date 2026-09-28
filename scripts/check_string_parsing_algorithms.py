#!/usr/bin/env python3
"""Deterministic checks for the string and parsing algorithms chapter."""

from __future__ import annotations

import argparse
from pathlib import Path

REVISION = "92fb561574bd929522ea005b9fd433138bea3236"


def direct_find(text: str, pattern: str) -> int:
    if pattern == "":
        return 0
    if len(pattern) > len(text):
        return -1
    for i in range(len(text) - len(pattern) + 1):
        j = 0
        while j < len(pattern) and text[i + j] == pattern[j]:
            j += 1
        if j == len(pattern):
            return i
    return -1


def kmp_prefix(pattern: str) -> list[int]:
    pi = [0] * len(pattern)
    j = 0
    for i in range(1, len(pattern)):
        while j > 0 and pattern[i] != pattern[j]:
            j = pi[j - 1]
        if pattern[i] == pattern[j]:
            j += 1
        pi[i] = j
    return pi


def kmp_find(text: str, pattern: str) -> int:
    if pattern == "":
        return 0
    pi = kmp_prefix(pattern)
    j = 0
    for i, ch in enumerate(text):
        while j > 0 and ch != pattern[j]:
            j = pi[j - 1]
        if ch == pattern[j]:
            j += 1
        if j == len(pattern):
            return i - len(pattern) + 1
    return -1


def eval_precedence(tokens):
    """Small precedence-climbing model for +, -, *, / with left associativity."""
    pos = 0
    precedence = {"+": 1, "-": 1, "*": 2, "/": 2}

    def primary():
        nonlocal pos
        value = int(tokens[pos])
        pos += 1
        return value

    def parse_bin(min_prec):
        nonlocal pos
        left = primary()
        while pos < len(tokens):
            op = tokens[pos]
            prec = precedence.get(op, 0)
            if prec < min_prec or prec == 0:
                break
            pos += 1
            right = parse_bin(prec + 1)
            if op == "+":
                left += right
            elif op == "-":
                left -= right
            elif op == "*":
                left *= right
            else:
                left //= right
        return left

    result = parse_bin(1)
    assert pos == len(tokens)
    return result


def parse_u64_model(text: str) -> int:
    base = 10
    i = 0
    if text.startswith(("0x", "0X")):
        base = 16
        i = 2
    if i == len(text):
        raise ValueError("missing digits")
    value = 0
    limit = (1 << 64) - 1
    for ch in text[i:]:
        if "0" <= ch <= "9":
            digit = ord(ch) - ord("0")
        elif "a" <= ch <= "f":
            digit = 10 + ord(ch) - ord("a")
        elif "A" <= ch <= "F":
            digit = 10 + ord(ch) - ord("A")
        else:
            raise ValueError("invalid digit")
        if digit >= base:
            raise ValueError("digit outside base")
        if value > (limit - digit) // base:
            raise OverflowError("u64 overflow")
        value = value * base + digit
    return value


def check_models():
    cases = [
        ("", "", 0),
        ("abc", "", 0),
        ("abc", "a", 0),
        ("abc", "c", 2),
        ("abc", "z", -1),
        ("aaaaab", "aaab", 2),
        ("short", "longer", -1),
        ("ababababac", "ababac", 4),
    ]
    for text, pattern, expected in cases:
        assert direct_find(text, pattern) == expected
        assert kmp_find(text, pattern) == expected

    assert kmp_prefix("ababaca") == [0, 0, 1, 2, 3, 0, 1]

    assert eval_precedence(["2", "+", "3", "*", "4"]) == 14
    assert eval_precedence(["20", "-", "5", "-", "3"]) == 12
    assert eval_precedence(["24", "/", "4", "*", "2"]) == 12

    assert parse_u64_model("0") == 0
    assert parse_u64_model("0xFF") == 255
    assert parse_u64_model("18446744073709551615") == (1 << 64) - 1
    try:
        parse_u64_model("18446744073709551616")
    except OverflowError:
        pass
    else:
        raise AssertionError("u64 overflow was not rejected")


def require(text: str, path: str, anchors):
    for anchor in anchors:
        if anchor not in text:
            raise AssertionError(f"{path}: missing reviewed anchor {anchor!r}")


def check_source_contract(source_root: Path):
    paths = {
        "kernel_string": "kernel/metal/string.c",
        "guest_string": "LIB/STRING.CC",
        "lexer": "kernel/gfx/shader/sh_lex.c",
        "parser": "kernel/gfx/shader/sh_parse.c",
        "shader_int": "kernel/gfx/shader/sh_int.h",
        "shader_pub": "kernel/gfx/shader/sh_pub.h",
        "kcc": "compiler/kcc/kcc.c",
        "asm": "compiler/chrisasm/chrisasm.c",
        "shader_test": "tools/test_shader.c",
    }
    src = {
        key: (source_root / path).read_text(encoding="utf-8")
        for key, path in paths.items()
    }

    require(src["kernel_string"], paths["kernel_string"], (
        "char *strstr(const char *haystack, const char *needle)",
        "while (*haystack)",
        "while (i < nlen && haystack[i] == needle[i])",
    ))
    require(src["guest_string"], paths["guest_string"], (
        "char *strstr(char *h, char *n)",
        "if (strncmp(h + i, n, ln) == 0)",
    ))
    require(src["lexer"], paths["lexer"], (
        "static int push_tok(ShComp *c, Tok t)",
        "if (c->ntok >= SH_TOK_MAX)",
        "int sh_lex(ShComp *c)",
        "if (c->src_len >= SH_SRC_MAX)",
        'sh_err(c, c->ntok - 1, "invalid token")',
        "end.kind = TK_EOF",
    ))
    require(src["parser"], paths["parser"], (
        "static int enter(ShComp *c)",
        "if (c->depth >= SH_NEST_MAX)",
        "static void sync_stmt(ShComp *c)",
        "static int parse_primary(ShComp *c)",
        "static int parse_unary(ShComp *c)",
        "static int parse_bin(ShComp *c, int min_prec)",
        "right = parse_bin(c, prec + 1)",
        "return parse_bin(c, 1)",
    ))
    require(src["shader_int"], paths["shader_int"], (
        "#define SH_TOK_MAX 768",
        "#define SH_AST_MAX 512",
        "#define SH_NEST_MAX 32",
    ))
    require(src["shader_pub"], paths["shader_pub"], (
        "#define SH_SRC_MAX 4096",
    ))
    require(src["kcc"], paths["kcc"], (
        "static int parse_expr(Val *out) {",
        "return parse_binary(out, 0);",
        "static int parse_binary(Val *out, int prec) {",
        "prec_of[matched] + 1",
    ))
    require(src["asm"], paths["asm"], (
        "static void skip_ws(const char **p)",
        "static int parse_ident(const char **p, char *out, int cap)",
        "static int parse_u64(const char **p, uint64_t *out)",
        "18446744073709551615ull - (uint64_t)d",
    ))
    require(src["shader_test"], paths["shader_test"], (
        "static void test_errors(void)",
        "invalid swizzle",
        "unsupported preprocessor",
    ))


def check_documents(root: Path):
    paths = [
        root / "docs/en/01-foundations/string-parsing-algorithms.md",
        root / "docs/pt-br/01-foundations/string-parsing-algorithms.md",
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        require(text, str(path), (
            REVISION,
            "strstr",
            "KMP",
            "Boyer-Moore",
            "sh_lex",
            "parse_bin",
            "parse_binary",
            "sync_stmt",
            "SH_TOK_MAX",
            "SH_AST_MAX",
            "SH_NEST_MAX",
            "parse_u64",
        ))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=".source")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    check_models()
    check_source_contract(Path(args.source))
    check_documents(root)

    print(
        "string/parsing checks passed: direct matching, KMP reference model, "
        "left-associative precedence climbing and u64 overflow rejection"
    )
    print(
        "source boundary passed: ChrisOS runtime strstr remains direct matching; "
        "shader lexing/parsing is bounded; KCC uses precedence parsing; "
        "ChrisASM validates numeric overflow"
    )


if __name__ == "__main__":
    main()
