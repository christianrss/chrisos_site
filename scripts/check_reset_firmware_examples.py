#!/usr/bin/env python3
"""Mechanical and source-contract checks for the reset/firmware chapter."""

from __future__ import annotations

import argparse
from pathlib import Path


KERNEL_BASE = 0xFFFFFFFF80000000


def reset_vector() -> int:
    cs_hidden_base = 0xFFFF0000
    eip = 0xFFF0
    return cs_hidden_base + eip


def ordinary_real_mode_address(segment: int, offset: int) -> int:
    return (segment << 4) + offset


def canonical_48(address: int) -> bool:
    address &= (1 << 64) - 1
    bit47 = (address >> 47) & 1
    upper = (address >> 48) & 0xFFFF
    return upper == (0xFFFF if bit47 else 0x0000)


def require_text(path: Path, needles: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise AssertionError(f"{path}: missing {missing}")


def source_checks(source: Path) -> None:
    linker = source / "kernel/metal/linker.ld"
    limine = source / "iso_root/boot/limine/limine.conf"
    bootinfo = source / "kernel/metal/bootinfo.c"
    start = source / "kernel/metal/start.c"
    gdt = source / "kernel/metal/gdt.c"

    require_text(
        linker,
        [
            "ENTRY(kstart)",
            ". = 0xffffffff80000000;",
            ".limine_requests_start",
            ".limine_requests",
            ".limine_requests_end",
            "__stack_bottom",
            "__stack_top",
        ],
    )
    require_text(
        limine,
        [
            "protocol: limine",
            "path: boot():/boot/kernel.elf",
        ],
    )
    require_text(
        bootinfo,
        [
            "framebuffer_request.response",
            "hhdm_request.response",
            "memmap_request.response",
            "mp_request.response",
            "info.hhdm_offset",
            "info.cpu_count",
            "info.bsp_lapic_id",
        ],
    )
    require_text(start, ["void kstart(void)", "bootinfo_init();"])
    require_text(gdt, ["extern unsigned char __stack_top[];", "tss.rsp0 = (uint64_t)__stack_top;"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()

    assert reset_vector() == 0xFFFFFFF0
    assert 0x100000000 - reset_vector() == 0x10

    ordinary = ordinary_real_mode_address(0xF000, 0xFFF0)
    assert ordinary == 0x000FFFF0
    assert ordinary != reset_vector()

    assert canonical_48(KERNEL_BASE)
    assert not canonical_48(0x0000800000000000)

    # ELF e_machine value for AMD x86-64.
    assert 62 == 0x3E

    # The current kernel base is 2 GiB below the top of the 64-bit address
    # space modulo 2^64, matching the common higher-half placement.
    assert ((1 << 64) - KERNEL_BASE) == 0x80000000

    if args.source is not None:
        source_checks(args.source)

    print(
        "reset/firmware examples: reset vector, real-mode contrast, "
        "higher-half canonicality and ChrisOS boot source contracts passed"
    )
    print(
        "Scope: arithmetic and repository contract checks only; no firmware, "
        "UEFI, Limine or physical-hardware conformance claim."
    )


if __name__ == "__main__":
    main()
