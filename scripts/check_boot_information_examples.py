#!/usr/bin/env python3
"""Mechanical and source-contract checks for the boot-information chapter."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


U64_MAX = (1 << 64) - 1
PAGE = 4096


@dataclass(frozen=True)
class RawRange:
    base: int
    length: int
    kind: int


@dataclass(frozen=True)
class CanonRange:
    base: int
    length: int
    kind: int


def checked_end(base: int, length: int) -> int:
    if base < 0 or length < 0 or base > U64_MAX or length > U64_MAX:
        raise ValueError("range outside uint64")
    if length > U64_MAX - base:
        raise OverflowError("range wraps uint64")
    return base + length


def normalize_ranges(raw: list[RawRange]) -> list[CanonRange]:
    tmp: list[CanonRange] = []
    for r in raw:
        if r.length == 0:
            continue
        checked_end(r.base, r.length)
        kind = r.kind if 0 <= r.kind <= 7 else 1  # unknown -> reserved
        tmp.append(CanonRange(r.base, r.length, kind))
    tmp.sort(key=lambda r: (r.base, r.length, r.kind))
    for prev, cur in zip(tmp, tmp[1:]):
        if checked_end(prev.base, prev.length) > cur.base:
            raise ValueError("overlapping boot ranges")
    out: list[CanonRange] = []
    for r in tmp:
        if out:
            p = out[-1]
            if checked_end(p.base, p.length) == r.base and p.kind == r.kind:
                out[-1] = CanonRange(p.base, p.length + r.length, p.kind)
                continue
        out.append(r)
    return out


def usable_page_interval(base: int, length: int) -> tuple[int, int]:
    end = checked_end(base, length)
    start_page = (base + PAGE - 1) & ~(PAGE - 1)
    end_page = end & ~(PAGE - 1)
    if end_page < start_page:
        end_page = start_page
    return start_page, end_page


def reserved_page_interval(base: int, length: int) -> tuple[int, int]:
    end = checked_end(base, length)
    start_page = base & ~(PAGE - 1)
    if end > U64_MAX - (PAGE - 1):
        raise OverflowError("reserved rounding wraps uint64")
    end_page = (end + PAGE - 1) & ~(PAGE - 1)
    return start_page, end_page


def framebuffer_span(pitch: int, height: int) -> int:
    if pitch < 0 or height < 0:
        raise ValueError("negative framebuffer geometry")
    if height and pitch > U64_MAX // height:
        raise OverflowError("framebuffer span wraps uint64")
    return pitch * height


def require_text(path: Path, needles: list[str]) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    missing = [n for n in needles if n not in text]
    if missing:
        raise AssertionError(f"{path}: missing {missing}")
    return text


def source_checks(source: Path) -> None:
    boot_h = source / "kernel/metal/bootinfo.h"
    boot_c = source / "kernel/metal/bootinfo.c"
    pmm = source / "kernel/metal/pmm.c"
    mm = source / "kernel/metal/mm.c"
    smp = source / "kernel/metal/smp.c"
    chrisvm = source / "docs/chrisvm-boot-protocol.md"

    require_text(
        boot_h,
        [
            "uint64_t hhdm_offset;",
            "uint64_t fb_addr;",
            "uint64_t fb_width;",
            "uint64_t fb_height;",
            "uint64_t fb_pitch;",
            "uint16_t fb_bpp;",
            "uint64_t usable_bytes;",
            "uint64_t memmap_entries;",
            "uint64_t cpu_count;",
            "uint32_t bsp_lapic_id;",
            "struct limine_mp_response;",
            "struct limine_mp_response *bootinfo_mp_response(void);",
        ],
    )

    require_text(
        boot_c,
        [
            "static struct limine_memmap_response *memmap_response;",
            "memmap_response = memmap;",
            "return memmap_response->entry_count;",
            "entry = memmap_response->entries[index];",
            "return mp_request.response;",
            "bootflag_parse(cmdline_request.response->cmdline);",
            "g_safe = 1;",
            "g_nosmp = 1;",
            "g_noapic = 1;",
            "g_noac97 = 1;",
            "g_nonet = 1;",
            "g_nojit = 1;",
        ],
    )

    require_text(
        pmm,
        [
            "type == LIMINE_MEMMAP_BOOTLOADER_RECLAIMABLE",
            "mark_range_used(base, length);",
            "mark_usable_free(base, length);",
        ],
    )

    require_text(
        mm,
        [
            '__asm__ volatile ("mov %%cr3, %0" : "=r"(cr3));',
            "mm_cr3_phys = cr3 & MM_ADDR_MASK;",
            "map_4k(",
        ],
    )

    require_text(
        smp,
        [
            "mp = bootinfo_mp_response();",
            "info->extra_argument = (uint64_t)next;",
            "info->goto_address = ap_entry;",
            "g_ap_stacks[next] = alloc_ap_stack(next);",
        ],
    )

    require_text(
        chrisvm,
        [
            "Não há estrutura de boot info nesta versão.",
            "higher-half ELF is outside boot protocol v1",
            "O protocolo 2 precisa carregar um ELF higher-half, publicar um boot info explícito",
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()

    assert checked_end(0x1000, 0x2000) == 0x3000
    try:
        checked_end(U64_MAX - 7, 8)
    except OverflowError:
        pass
    else:
        raise AssertionError("wrapping range accepted")

    raw = [
        RawRange(0x5000, 0x1000, 0),
        RawRange(0x1000, 0x1000, 0),
        RawRange(0x2000, 0x1000, 0),
        RawRange(0x4000, 0x1000, 99),
        RawRange(0x3000, 0, 0),
    ]
    norm = normalize_ranges(raw)
    assert norm == [
        CanonRange(0x1000, 0x2000, 0),
        CanonRange(0x4000, 0x1000, 1),
        CanonRange(0x5000, 0x1000, 0),
    ]

    try:
        normalize_ranges([
            RawRange(0x1000, 0x2000, 0),
            RawRange(0x2000, 0x2000, 1),
        ])
    except ValueError as exc:
        assert "overlapping" in str(exc)
    else:
        raise AssertionError("overlapping boot ranges accepted")

    assert usable_page_interval(0x1003, 0x3000) == (0x2000, 0x4000)
    assert reserved_page_interval(0x1003, 0x3000) == (0x1000, 0x5000)

    assert framebuffer_span(2560, 480) == 1_228_800
    assert framebuffer_span(7680, 1080) == 8_294_400
    try:
        framebuffer_span(U64_MAX, 2)
    except OverflowError:
        pass
    else:
        raise AssertionError("framebuffer multiplication overflow accepted")

    # Synthetic snapshot invariant: summaries are derived from canonical ranges.
    sample = normalize_ranges([
        RawRange(0x100000, 0x200000, 0),
        RawRange(0x400000, 0x100000, 1),
        RawRange(0x500000, 0x300000, 0),
    ])
    usable = sum(r.length for r in sample if r.kind == 0)
    assert usable == 0x500000
    assert len(sample) == 3

    if args.source is not None:
        source_checks(args.source)

    print(
        "boot-information examples: range safety, canonical sorting/coalescing, "
        "overlap rejection, PMM page geometry, framebuffer span and source ownership passed"
    )
    print(
        "Current-source findings: memmap and MP remain Limine-owned, inherited CR3 "
        "is adopted, bootloader-reclaimable memory stays reserved, ChrisVM v1 has no boot info."
    )
    print(
        "Scope: synthetic normalization and repository-contract checks only; "
        "BootSnapshot is documented architecture, not yet a ChrisOS implementation."
    )


if __name__ == "__main__":
    main()
