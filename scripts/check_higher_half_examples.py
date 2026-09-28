#!/usr/bin/env python3
"""Mechanical and source-contract checks for the higher-half-kernel chapter."""

from __future__ import annotations

import argparse
from pathlib import Path


U64 = 1 << 64
KERNEL_BASE = 0xFFFFFFFF80000000
MMIO_WINDOW = 0xFFFFFFFF90000000
MM_TEST_VIRT = 0xFFFFFFFF91000000
OLD_JIT_NEIGHBOR = 0xFFFFFFFF92000000
JIT_BASE = 0xFFFFFFFFC0000000


def signed64(value: int) -> int:
    value &= U64 - 1
    return value - U64 if value & (1 << 63) else value


def canonical48(value: int) -> bool:
    value &= U64 - 1
    bit47 = (value >> 47) & 1
    top = value >> 48
    return top == (0xFFFF if bit47 else 0)


def indices(value: int) -> tuple[int, int, int, int, int]:
    value &= U64 - 1
    return (
        (value >> 39) & 0x1FF,
        (value >> 30) & 0x1FF,
        (value >> 21) & 0x1FF,
        (value >> 12) & 0x1FF,
        value & 0xFFF,
    )


def require_text(path: Path, needles: list[str]) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    missing = [n for n in needles if n not in text]
    if missing:
        raise AssertionError(f"{path}: missing {missing}")
    return text


def source_checks(source: Path) -> None:
    linker = source / "kernel/metal/linker.ld"
    makefile = source / "makefile"
    bootinfo = source / "kernel/metal/bootinfo.c"
    mm = source / "kernel/metal/mm.c"
    pmm = source / "kernel/metal/pmm.c"
    gdt = source / "kernel/metal/gdt.c"
    jit = source / "compiler/jit/jit.c"
    readme = source / "README.md"
    chrisld = source / "compiler/chrisld/chrisld.c"

    require_text(
        linker,
        [
            ". = 0xffffffff80000000;",
            "__kernel_start = .;",
            "__kernel_end = .;",
            "ENTRY(kstart)",
        ],
    )

    require_text(
        makefile,
        [
            "-mcmodel=kernel",
            "-fno-pic",
            "-fno-pie",
            "-mno-red-zone",
            "-T kernel/metal/linker.ld",
        ],
    )

    require_text(
        bootinfo,
        [
            "info.hhdm_offset = hhdm->offset;",
            "return phys + info.hhdm_offset;",
        ],
    )

    require_text(
        mm,
        [
            "#define MMIO_WINDOW  0xffffffff90000000ull",
            "#define MM_TEST_VIRT 0xffffffff91000000ull",
            '__asm__ volatile ("mov %%cr3, %0" : "=r"(cr3));',
            "mm_cr3_phys = cr3 & MM_ADDR_MASK;",
            "return (uint64_t *)bootinfo_phys_to_virt(phys & MM_ADDR_MASK);",
            "fb_phys = mm_virt_to_phys(boot->fb_addr);",
            "for (i = 256; i < 512; ++i) {",
            "dst[i] = src[i];",
            '__asm__ volatile ("mov %0, %%cr3" : : "r"(cr3_phys) : "memory");',
        ],
    )

    require_text(
        pmm,
        [
            "extern char __kernel_start[];",
            "extern char __kernel_end[];",
            'serial_puts("pmm kernel_virt ");',
            "type == LIMINE_MEMMAP_EXECUTABLE_AND_MODULES",
            "mark_range_used(base, length);",
            "va = (volatile uint64_t *)bootinfo_phys_to_virt(a);",
        ],
    )

    require_text(
        gdt,
        [
            "extern unsigned char __stack_top[];",
            "tss.rsp0 = (uint64_t)__stack_top;",
        ],
    )

    jit_text = require_text(
        jit,
        [
            "#define JIT_VIRT_BASE 0xffffffffc0000000ull",
            "0xffffffff80000000 (PDPT[2])",
            "PDPT[3] is empty.",
        ],
    )

    # This deliberately records a current source-comment mismatch. If the
    # comment is corrected, this check should fail so the chapter is reviewed.
    if "PDPT[2]" not in jit_text or "PDPT[3]" not in jit_text:
        raise AssertionError("expected current JIT relative/stale PDPT comment")

    require_text(
        readme,
        [
            "| Kernel | x86-64 higher-half kernel; GDT/TSS, IDT, paging, PMM/heap, SMP, processes, timers and interrupts |",
            "| Virtualization | ChrisVM with the ChrisCPU emulator backend; ChrisHV remains an architectural target |",
        ],
    )

    require_text(
        chrisld,
        [
            'same_name(s->name, "kstart")',
            "wr64(elf, ph + 16u, vaddr);",
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()

    # Current four-level / 48-bit canonical boundaries.
    assert canonical48(0x0000000000000000)
    assert canonical48(0x00007FFFFFFFFFFF)
    assert not canonical48(0x0000800000000000)
    assert not canonical48(0xFFFF7FFFFFFFFFFF)
    assert canonical48(0xFFFF800000000000)
    assert canonical48(0xFFFFFFFFFFFFFFFF)

    assert canonical48(KERNEL_BASE)
    assert signed64(KERNEL_BASE) == -(1 << 31)
    assert KERNEL_BASE == ((U64 - (1 << 31)) & (U64 - 1))

    expected = {
        KERNEL_BASE: (511, 510, 0, 0, 0),
        MMIO_WINDOW: (511, 510, 128, 0, 0),
        MM_TEST_VIRT: (511, 510, 136, 0, 0),
        OLD_JIT_NEIGHBOR: (511, 510, 144, 0, 0),
        JIT_BASE: (511, 511, 0, 0, 0),
    }
    for address, want in expected.items():
        got = indices(address)
        if got != want:
            raise AssertionError(
                f"{address:#018x}: indices {got}, expected {want}"
            )

    assert JIT_BASE - KERNEL_BASE == 1 << 30
    assert ((KERNEL_BASE >> 30) & 0x1FF) == 510
    assert ((JIT_BASE >> 30) & 0x1FF) == 511

    # PML4 lower/upper split used by mm_clone_kernel_space.
    assert (0x00007FFFFFFFFFFF >> 39) & 0x1FF == 255
    assert (0xFFFF800000000000 >> 39) & 0x1FF == 256

    if args.source is not None:
        source_checks(args.source)

    print(
        "higher-half examples: canonical ranges, signed -2 GiB kernel base, "
        "PML4/PDPT/PD/PT decomposition and high-window boundaries passed"
    )
    print(
        "Current-source finding: mm_init adopts Limine CR3, page-table memory is "
        "edited through HHDM aliases, and process roots copy PML4[256..511]."
    )
    print(
        "Source-comment finding: jit.c labels the kernel/JIT 1-GiB slots as "
        "PDPT[2]/PDPT[3], while architectural indices are PDPT[510]/PDPT[511]."
    )
    print(
        "Scope: four-level/48-bit canonical arithmetic and repository contracts; "
        "no claim that LA57 or kernel-owned boot page tables are implemented."
    )


if __name__ == "__main__":
    main()
