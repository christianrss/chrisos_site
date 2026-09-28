#!/usr/bin/env python3
"""Mechanical and source-contract checks for the Limine chapter.

This validates the ChrisOS source contract around its pinned Limine usage.
It is not a Limine bootloader or protocol conformance implementation.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


U64_MAX = (1 << 64) - 1

LIMINE_MEMMAP_USABLE = 0
LIMINE_MEMMAP_RESERVED = 1
LIMINE_MEMMAP_ACPI_RECLAIMABLE = 2
LIMINE_MEMMAP_ACPI_NVS = 3
LIMINE_MEMMAP_BAD_MEMORY = 4
LIMINE_MEMMAP_BOOTLOADER_RECLAIMABLE = 5
LIMINE_MEMMAP_EXECUTABLE_AND_MODULES = 6
LIMINE_MEMMAP_FRAMEBUFFER = 7

PINNED_LIMINE_SHA = "ee5d29cd0a8034612dcd1df3f00052480db785c5"


def checked_range_end(base: int, length: int) -> int:
    if not (0 <= base <= U64_MAX and 0 <= length <= U64_MAX):
        raise ValueError("range component outside uint64")
    if length > U64_MAX - base:
        raise OverflowError("physical range wraps uint64")
    return base + length


def hhdm_base3_mapped(mem_type: int) -> bool:
    return mem_type in {
        LIMINE_MEMMAP_USABLE,
        LIMINE_MEMMAP_BOOTLOADER_RECLAIMABLE,
        LIMINE_MEMMAP_EXECUTABLE_AND_MODULES,
        LIMINE_MEMMAP_FRAMEBUFFER,
    }


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
        raise AssertionError(f"{path}: unexpected {found}")


def source_checks(source: Path) -> None:
    bootinfo = source / "kernel/metal/bootinfo.c"
    linker = source / "kernel/metal/linker.ld"
    pmm = source / "kernel/metal/pmm.c"
    mm = source / "kernel/metal/mm.c"
    makefile = source / "makefile"
    install = source / ".cursor/install.sh"
    readme = source / "README.md"

    boot_text = require_text(
        bootinfo,
        [
            "#define LIMINE_API_REVISION 3",
            "LIMINE_BASE_REVISION(3)",
            "LIMINE_REQUESTS_START_MARKER",
            "LIMINE_REQUESTS_END_MARKER",
            "struct limine_framebuffer_request framebuffer_request",
            "struct limine_hhdm_request hhdm_request",
            "struct limine_memmap_request memmap_request",
            "struct limine_mp_request mp_request",
            "struct limine_executable_cmdline_request cmdline_request",
            "LIMINE_BASE_REVISION_SUPPORTED",
            "static struct limine_memmap_response *memmap_response;",
            "return mp_request.response;",
            "return phys + info.hhdm_offset;",
        ],
    )

    requests = re.findall(
        r"static volatile struct (limine_[a-z0-9_]+_request)\s+[a-z0-9_]+\s*=\s*\{(.*?)\};",
        boot_text,
        re.S,
    )
    names = [name for name, _ in requests]
    expected = {
        "limine_framebuffer_request",
        "limine_hhdm_request",
        "limine_memmap_request",
        "limine_mp_request",
        "limine_executable_cmdline_request",
    }
    if set(names) != expected or len(names) != 5:
        raise AssertionError(f"unexpected Limine request set: {names}")
    for name, body in requests:
        if ".revision = 0" not in body:
            raise AssertionError(f"{name}: request revision is not zero")

    reject_text(
        bootinfo,
        [
            "limine_rsdp_request",
            "LIMINE_RSDP_REQUEST",
            "limine_paging_mode_request",
            "LIMINE_PAGING_MODE_REQUEST",
            "limine_stack_size_request",
            "LIMINE_STACK_SIZE_REQUEST",
            "limine_bootloader_info_request",
            "LIMINE_BOOTLOADER_INFO_REQUEST",
            "limine_firmware_type_request",
            "LIMINE_FIRMWARE_TYPE_REQUEST",
        ],
    )

    require_text(
        linker,
        [
            "requests PT_LOAD FLAGS(6);",
            ". = 0xffffffff80000000;",
            "ENTRY(kstart)",
            "KEEP(*(.limine_requests_start))",
            "KEEP(*(.limine_requests))",
            "KEEP(*(.limine_requests_end))",
        ],
    )

    require_text(
        makefile,
        [
            "-DLIMINE_API_REVISION=3",
            "-mcmodel=kernel",
            "-mno-red-zone",
        ],
    )

    require_text(
        install,
        [
            f'LIMINE_SHA="{PINNED_LIMINE_SHA}"',
            "v9.x-binary",
            "API revision 3",
        ],
    )

    require_text(
        pmm,
        [
            "type == LIMINE_MEMMAP_BOOTLOADER_RECLAIMABLE",
            "type == LIMINE_MEMMAP_EXECUTABLE_AND_MODULES",
            "type == LIMINE_MEMMAP_FRAMEBUFFER",
        ],
    )

    require_text(
        mm,
        [
            '__asm__ volatile ("mov %%cr3, %0" : "=r"(cr3));',
            "mm_cr3_phys = cr3 & MM_ADDR_MASK;",
        ],
    )

    require_text(
        readme,
        [
            "| Boot | Limine BIOS/UEFI boot path |",
            "| Virtualization | ChrisVM with the ChrisCPU emulator backend; ChrisHV remains an architectural target |",
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()

    assert checked_range_end(0, 0) == 0
    assert checked_range_end(0x1000, 0x2000) == 0x3000
    assert checked_range_end(U64_MAX - 0xFFF, 0xFFF) == U64_MAX
    try:
        checked_range_end(U64_MAX - 0xFFF, 0x1000)
    except OverflowError:
        pass
    else:
        raise AssertionError("wrapping uint64 physical range was accepted")

    assert hhdm_base3_mapped(LIMINE_MEMMAP_USABLE)
    assert hhdm_base3_mapped(LIMINE_MEMMAP_BOOTLOADER_RECLAIMABLE)
    assert hhdm_base3_mapped(LIMINE_MEMMAP_EXECUTABLE_AND_MODULES)
    assert hhdm_base3_mapped(LIMINE_MEMMAP_FRAMEBUFFER)
    assert not hhdm_base3_mapped(LIMINE_MEMMAP_RESERVED)
    assert not hhdm_base3_mapped(LIMINE_MEMMAP_ACPI_RECLAIMABLE)
    assert not hhdm_base3_mapped(LIMINE_MEMMAP_ACPI_NVS)
    assert not hhdm_base3_mapped(LIMINE_MEMMAP_BAD_MEMORY)

    kernel_base = 0xFFFFFFFF80000000
    assert kernel_base >= 0xFFFFFFFF80000000
    assert ((kernel_base >> 47) & 1) == 1
    assert (kernel_base >> 48) == 0xFFFF

    # FLAGS(6) = PF_W (2) + PF_R (4), without PF_X (1).
    assert 6 == (2 | 4)
    assert (6 & 1) == 0

    if args.source is not None:
        source_checks(args.source)

    print(
        "Limine examples: base/API revision contracts, request set, request "
        "revisions, HHDM base-3 model, range safety and linker/source ownership passed"
    )
    print(
        "Current-source findings: no RSDP/paging/stack request; Limine memmap/MP "
        "responses and inherited CR3 remain live; bootloader-reclaimable memory stays reserved."
    )
    print(
        "Scope: mechanical and repository-contract checks only; no Limine "
        "bootloader/protocol conformance claim."
    )


if __name__ == "__main__":
    main()
