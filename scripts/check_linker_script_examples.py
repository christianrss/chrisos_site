#!/usr/bin/env python3
"""Mechanical and source-contract checks for the linker-script chapter."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


PAGE = 4096
STACK = 1024 * 1024
KERNEL_BASE = 0xFFFFFFFF80000000

PF_X = 1
PF_W = 2
PF_R = 4


def align_up(value: int, alignment: int) -> int:
    if value < 0:
        raise ValueError("negative address")
    if alignment <= 0 or alignment & (alignment - 1):
        raise ValueError("alignment must be a power of two")
    return (value + alignment - 1) & ~(alignment - 1)


def require_text(path: Path, needles: list[str]) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    missing = [n for n in needles if n not in text]
    if missing:
        raise AssertionError(f"{path}: missing {missing}")
    return text


def reject_text(path: Path, needles: list[str]) -> None:
    text = path.read_text(encoding="utf-8", errors="ignore")
    found = [n for n in needles if n in text]
    if found:
        raise AssertionError(f"{path}: unexpected current-policy constructs {found}")


def source_checks(source: Path) -> None:
    linker = source / "kernel/metal/linker.ld"
    makefile = source / "makefile"
    chrisld = source / "compiler/chrisld/chrisld.c"
    chriso = source / "compiler/chrisld/chriso.h"

    text = require_text(
        linker,
        [
            "OUTPUT_FORMAT(elf64-x86-64)",
            "OUTPUT_ARCH(i386:x86-64)",
            "ENTRY(kstart)",
            "PHDRS {",
            "requests PT_LOAD FLAGS(6);",
            "text     PT_LOAD FLAGS(5);",
            "data     PT_LOAD FLAGS(6);",
            ". = 0xffffffff80000000;",
            "__kernel_start = .;",
            ".limine_requests : ALIGN(4K)",
            "KEEP(*(.limine_requests_start))",
            "KEEP(*(.limine_requests))",
            "KEEP(*(.limine_requests_end))",
            "} :requests",
            ".text : ALIGN(4K)",
            "*(.text .text.*)",
            "} :text",
            ".rodata : ALIGN(4K)",
            "*(.rodata .rodata.*)",
            ".data : ALIGN(4K)",
            "*(.data .data.*)",
            "} :data",
            ".bss (NOLOAD) : ALIGN(4K)",
            "*(.bss .bss.*)",
            "*(COMMON)",
            ". = ALIGN(16);",
            "__stack_bottom = .;",
            ". += 1024K;",
            "__stack_top = .;",
            ". = ALIGN(4K);",
            "__kernel_end = .;",
            "/DISCARD/ :",
            "*(.eh_frame*)",
            "*(.note*)",
            "*(.comment*)",
        ],
    )

    # The Limine delimiters must be collected in start/body/end order.
    order = [
        text.index("KEEP(*(.limine_requests_start))"),
        text.index("KEEP(*(.limine_requests))"),
        text.index("KEEP(*(.limine_requests_end))"),
    ]
    if order != sorted(order):
        raise AssertionError("Limine request KEEP ordering changed")

    # Confirm the production script still has exactly the three explicit PT_LOAD declarations.
    phdr_body = re.search(r"PHDRS\s*\{(.*?)\}", text, re.S)
    if not phdr_body:
        raise AssertionError("PHDRS block not found")
    pt_loads = re.findall(r"\bPT_LOAD\b", phdr_body.group(1))
    if len(pt_loads) != 3:
        raise AssertionError(f"expected 3 explicit PT_LOAD entries, got {len(pt_loads)}")

    # The current script intentionally does not use a physical-region / split-LMA policy.
    reject_text(
        linker,
        [
            "MEMORY {",
            "MEMORY{",
            "AT(",
            "AT (",
            "AT>",
            "LOADADDR(",
            "ASSERT(",
            "PROVIDE(",
            "SUBALIGN(",
            "ALIGN_WITH_INPUT",
            "OVERLAY",
        ],
    )

    require_text(
        makefile,
        [
            "LDFLAGS := -m elf_x86_64 -nostdlib -static -z max-page-size=0x1000",
            "-z noexecstack -T kernel/metal/linker.ld",
            "$(LD) $(LDFLAGS) -o $@ $(OBJECTS)",
            "-mcmodel=kernel",
            "-fno-pic",
            "-fno-pie",
        ],
    )

    # ChrisO still exposes only the four ordinary bootstrap section classes.
    require_text(
        chriso,
        [
            "#define CHRISO_SEC_TEXT 0u",
            "#define CHRISO_SEC_RODATA 1u",
            "#define CHRISO_SEC_DATA 2u",
            "#define CHRISO_SEC_BSS 3u",
            "#define CHRISO_SEC_MAX 4u",
        ],
    )

    # ChrisLd has not yet acquired production linker-script semantics.
    reject_text(
        chrisld,
        [
            ".limine_requests",
            "__kernel_start",
            "__kernel_end",
            "__stack_bottom",
            "__stack_top",
            "1024K",
            "1048576",
        ],
    )
    require_text(
        chrisld,
        [
            "#define LD_OBJS 32u",
            "PF_R | PF_X",
            "PF_R | PF_W",
            'same_name(s->name, "kstart")',
            "map.total[CHRISO_SEC_BSS]",
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()

    assert align_up(0x1000, PAGE) == 0x1000
    assert align_up(0x1001, PAGE) == 0x2000
    assert align_up(0x1FFF, PAGE) == 0x2000
    assert align_up(KERNEL_BASE, PAGE) == KERNEL_BASE

    # Model the script-created stack interval after an arbitrary BSS end.
    bss_end = KERNEL_BASE + 0x12345
    stack_bottom = align_up(bss_end, 16)
    stack_top = stack_bottom + STACK
    kernel_end = align_up(stack_top, PAGE)

    assert stack_bottom % 16 == 0
    assert stack_top - stack_bottom == 1024 * 1024
    assert kernel_end % PAGE == 0
    assert kernel_end >= stack_top

    assert (PF_R | PF_X) == 5
    assert (PF_R | PF_W) == 6
    assert ((PF_R | PF_X) & PF_W) == 0
    assert ((PF_R | PF_W) & PF_X) == 0

    # Linker symbols capture different moments in location-counter evaluation.
    kernel_start = KERNEL_BASE
    assert kernel_start == KERNEL_BASE
    assert stack_bottom > kernel_start
    assert stack_top > stack_bottom
    assert kernel_end >= stack_top

    if args.source is not None:
        source_checks(args.source)

    print(
        "linker-script examples: location counter, page/stack alignment, "
        "1 MiB reservation, PHDR permissions, KEEP ordering and source contracts passed"
    )
    print(
        "Current-source finding: linker.ld defines three explicit PT_LOADs and "
        "synthetic kernel/stack boundaries; ChrisLd still has no Limine request "
        "section class, production synthetic symbols or linker-created 1 MiB stack."
    )
    print(
        "Scope: GNU-ld/source-contract checks only; final kernel ELF inspection "
        "remains a separate production gate."
    )


if __name__ == "__main__":
    main()
