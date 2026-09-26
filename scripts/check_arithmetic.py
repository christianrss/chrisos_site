#!/usr/bin/env python3
"""Probe actual ChrisCPU flags against an independent integer-range model.

No guest boot or instruction-decoding coverage is implied. Requires a host C
compiler supporting unsigned __int128; all outputs are temporary.
"""
import argparse
import ctypes
import hashlib
from pathlib import Path
import random
import subprocess
import tempfile

STATUS = sum(1 << bit for bit in (0, 2, 4, 6, 7, 11))


def reference(op, a, b, width, incoming):
    modulus = 1 << width
    mask = modulus - 1
    a, b = a & mask, b & mask
    signed_a = a if a < modulus // 2 else a - modulus
    signed_b = b if b < modulus // 2 else b - modulus
    carry = incoming & 1 if op in ("ADC", "SBB") else 0
    if op in ("ADD", "ADC"):
        full = a + b + carry
        signed_full = signed_a + signed_b + carry
        auxiliary = (a % 16 + b % 16 + carry) >= 16
    elif op in ("SUB", "SBB", "CMP"):
        full = a - b - carry
        signed_full = signed_a - signed_b - carry
        auxiliary = (a % 16 - b % 16 - carry) < 0
    else:
        full = {"AND": a & b, "TEST": a & b,
                "OR": a | b, "XOR": a ^ b}[op]
        signed_full = 0
        auxiliary = False
    result = full % modulus
    values = {
        0: not 0 <= full < modulus,
        2: (result % 256).bit_count() % 2 == 0,
        4: auxiliary,
        6: result == 0,
        7: result >= modulus // 2,
        11: not -modulus // 2 <= signed_full < modulus // 2,
    }
    flags = (incoming & ~STATUS) | 2
    flags |= sum(int(value) << bit for bit, value in values.items())
    return result, flags


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(".source"))
    parser.add_argument("--cc", default="cc")
    args = parser.parse_args()
    root = args.source.resolve()
    src = root / "chrisvm/cpu/emulator/flags.c"
    if not src.is_file():
        parser.error(f"missing source: {src}")
    names = ("ADD", "ADC", "SUB", "SBB", "CMP", "AND", "TEST", "OR", "XOR")
    with tempfile.TemporaryDirectory(prefix="chris-arithmetic-") as tmp:
        tmp = Path(tmp)
        # Let the source header supply selectors instead of duplicating enum values.
        wrapper = tmp / "probe.c"
        wrapper.write_text('#include "chrisvm.h"\nint probe_op(int i) {\n'
                           'static const int ops[] = {' + ','.join('CHRIS_ALU_' + n for n in names)
                           + '}; return ops[i]; }\n', encoding="utf-8")
        libpath = tmp / "flags.so"
        subprocess.run([args.cc, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                        "-shared", "-fPIC", "-I", str(root / "chrisvm"),
                        str(src), str(wrapper), "-o", str(libpath)], check=True)
        lib = ctypes.CDLL(str(libpath))
        u64 = ctypes.c_uint64
        fn = lib.chris_flags_bin
        fn.argtypes = [ctypes.c_int, u64, u64, ctypes.c_int, u64, ctypes.POINTER(u64)]
        fn.restype = u64
        cc = lib.chris_cc_true
        cc.argtypes, cc.restype = [ctypes.c_int, u64], ctypes.c_int
        lib.probe_op.argtypes, lib.probe_op.restype = [ctypes.c_int], ctypes.c_int
        selectors = {n: lib.probe_op(i) for i, n in enumerate(names)}
        output = u64()
        count = 0

        def check(op, a, b, size, flags):
            nonlocal count
            expected_result, expected_flags = reference(op, a, b, size * 8, flags)
            actual = fn(selectors[op], a, b, size, flags, ctypes.byref(output))
            if (output.value, actual) != (expected_result, expected_flags):
                raise AssertionError((op, hex(a), hex(b), size, hex(flags),
                                      (hex(output.value), hex(actual)),
                                      (hex(expected_result), hex(expected_flags))))
            count += 1

        for op in names:
            carries = (0, 1) if op in ("ADC", "SBB") else (0,)
            for carry in carries:
                for a in range(256):
                    for b in range(256):
                        # Nonstatus bits and obsolete status deliberately populated.
                        check(op, a, b, 1, (0xA55A5AA5FFFE & ~1) | carry)

        rng = random.Random(20260926)
        for size in (2, 4, 8):
            sign = 1 << (size * 8 - 1)
            mask = 2 * sign - 1
            boundaries = (0, 1, 15, 16, sign - 1, sign, sign + 1, mask - 1, mask)
            for op in names:
                for a in boundaries:
                    for b in boundaries:
                        for carry in (0, 1):
                            check(op, a, b, size, 0xFFFFFFFFFFFFFFFE | carry)
                for _ in range(1000):
                    check(op, rng.getrandbits(64), rng.getrandbits(64), size,
                          rng.getrandbits(64))

        for bits in range(32):
            cf, pf, zf, sf, of = ((bits >> i) & 1 for i in range(5))
            flags = cf | (pf << 2) | (zf << 6) | (sf << 7) | (of << 11)
            predicates = (of, not of, cf, not cf, zf, not zf, cf or zf,
                          not cf and not zf, sf, not sf, pf, not pf,
                          sf != of, sf == of, zf or sf != of,
                          not zf and sf == of)
            for condition, expected in enumerate(predicates):
                assert bool(cc(condition, flags)) == bool(expected)
                assert bool(cc(condition + 16, flags)) == bool(expected)
        # The optional output must not change status computation.
        for op in names:
            expected = reference(op, 127, 1, 8, 0x202)[1]
            assert fn(selectors[op], 127, 1, 1, 0x202, None) == expected
        sha = hashlib.sha256(src.read_bytes()).hexdigest()
        print(f"PASS: {count} arithmetic cases; 1024 condition-code cases; 9 null outputs")
        print(f"flags.c SHA-256: {sha}")
        print("Scope: helper functions only; no decoder, guest boot or hardware timing coverage")


if __name__ == "__main__":
    main()
