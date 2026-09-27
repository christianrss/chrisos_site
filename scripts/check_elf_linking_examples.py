#!/usr/bin/env python3
"""Mechanical and source-contract checks for the ELF/linking chapter."""

from __future__ import annotations

import argparse
from pathlib import Path


U64_MAX = (1 << 64) - 1
I32_MIN = -(1 << 31)
I32_MAX = (1 << 31) - 1

ELF_EHDR_SIZE = 64
ELF_PHDR_SIZE = 56
EM_X86_64 = 62

PF_X = 1
PF_W = 2
PF_R = 4


def checked_add(a: int, b: int, limit: int = U64_MAX) -> int:
    if a < 0 or b < 0 or a > limit or b > limit:
        raise ValueError("operand outside range")
    if b > limit - a:
        raise OverflowError("addition wraps")
    return a + b


def load_zero_fill(filesz: int, memsz: int) -> int:
    if filesz < 0 or memsz < 0 or filesz > memsz:
        raise ValueError("invalid PT_LOAD sizes")
    return memsz - filesz


def aligned_congruence(offset: int, vaddr: int, align: int) -> bool:
    if align <= 0 or align & (align - 1):
        raise ValueError("alignment must be a power of two")
    return (offset & (align - 1)) == (vaddr & (align - 1))


def reloc64(symbol: int, addend: int) -> int:
    value = symbol + addend
    if not 0 <= value <= U64_MAX:
        raise OverflowError("R_X86_64_64 out of uint64")
    return value


def reloc_pc32(symbol: int, addend: int, place: int) -> int:
    value = symbol + addend - place
    if value < I32_MIN or value > I32_MAX:
        raise OverflowError("PC32 displacement out of range")
    return value & 0xFFFFFFFF


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
    linker = source / "kernel/metal/linker.ld"
    makefile = source / "makefile"
    chriso = source / "compiler/chrisld/chriso.h"
    chrisld = source / "compiler/chrisld/chrisld.c"
    chrisld_h = source / "compiler/chrisld/chrisld.h"
    user_elf = source / "kernel/metal/elf.c"

    require_text(
        linker,
        [
            "OUTPUT_FORMAT(elf64-x86-64)",
            "OUTPUT_ARCH(i386:x86-64)",
            "ENTRY(kstart)",
            "requests PT_LOAD FLAGS(6);",
            "text     PT_LOAD FLAGS(5);",
            "data     PT_LOAD FLAGS(6);",
            ". = 0xffffffff80000000;",
            "__kernel_start = .;",
            ".limine_requests : ALIGN(4K)",
            "KEEP(*(.limine_requests_start))",
            "KEEP(*(.limine_requests))",
            "KEEP(*(.limine_requests_end))",
            ".bss (NOLOAD) : ALIGN(4K)",
            "*(COMMON)",
            "__stack_bottom = .;",
            ". += 1024K;",
            "__stack_top = .;",
            "__kernel_end = .;",
            "*(.eh_frame*)",
            "*(.note*)",
            "*(.comment*)",
        ],
    )

    require_text(
        makefile,
        [
            "LDFLAGS := -m elf_x86_64 -nostdlib -static -z max-page-size=0x1000",
            "-z noexecstack -T kernel/metal/linker.ld",
            "$(LD) $(LDFLAGS) -o $@ $(OBJECTS)",
            "$(HOST_BIN)/stamp_kernel $@",
            "-mcmodel=kernel",
            "-fno-pic",
            "-fno-pie",
        ],
    )

    require_text(
        chriso,
        [
            "#define CHRISO_VERSION 2u",
            "#define CHRISO_SEC_TEXT 0u",
            "#define CHRISO_SEC_RODATA 1u",
            "#define CHRISO_SEC_DATA 2u",
            "#define CHRISO_SEC_BSS 3u",
            "#define CHRISO_BIND_LOCAL 0u",
            "#define CHRISO_BIND_GLOBAL 1u",
            "#define CHRISO_BIND_UNDEF 2u",
            "#define R_X86_64_64 1u",
            "#define R_X86_64_PC32 2u",
            "#define R_X86_64_PLT32 4u",
            "#define R_X86_64_32 10u",
            "#define R_X86_64_32S 11u",
            "uint32_t type;",
        ],
    )

    require_text(
        chrisld,
        [
            "#define ELF_CLASS_64 2u",
            "#define ELF_MACHINE_X86_64 62u",
            "#define ELF_PHDR_SIZE 56u",
            "#define ELF_EHDR_SIZE 64u",
            "#define LD_OBJS 32u",
            "int chrisld_link_objects(",
            "duplicate_globals(imgs, n)",
            "R_X86_64_PC32 || rel->type == R_X86_64_PLT32",
            "map.total[CHRISO_SEC_BSS]",
            "PF_R | PF_X",
            "PF_R | PF_W",
            'same_name(s->name, "kstart")',
            'same_name(s->name, "main")',
            "if ((flags & PF_W) && (flags & PF_X))",
            "if (vaddr < v2 + m2 && v2 < vaddr + memsz)",
        ],
    )

    # These production-linker semantics are still absent from ChrisLd.
    reject_text(
        chrisld,
        [
            ".limine_requests_start",
            "__stack_bottom",
            "__stack_top",
            "__kernel_start",
            "__kernel_end",
        ],
    )

    require_text(
        chrisld_h,
        [
            "#define CHRISLD_ELF_MAX (1024u * 1024u)",
        ],
    )

    require_text(
        user_elf,
        [
            "#define ELF_TYPE_EXEC 2u",
            "#define ELF_MACHINE_X86_64 62u",
            "#define PT_LOAD 1u",
            "#define PF_X 1u",
            "#define PF_W 2u",
            "#define USER_LOAD_LO 0x400000ull",
            "#define USER_LOAD_HI 0x500000ull",
            "if (seg->filesz > seg->memsz)",
            "if ((seg->flags & PF_X) != 0 && (seg->flags & PF_W) != 0)",
            "if ((seg->vaddr & (PMM_PAGE - 1ull)) != (seg->offset & (PMM_PAGE - 1ull)))",
            "if (segs_overlap(&segs[s], &seg))",
            "if (nseg == 0 || !exec_hit)",
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()

    assert ELF_EHDR_SIZE == 64
    assert ELF_PHDR_SIZE == 56
    assert EM_X86_64 == 62

    assert (PF_R | PF_W) == 6
    assert (PF_R | PF_X) == 5
    assert ((PF_R | PF_W) & PF_X) == 0
    assert ((PF_R | PF_X) & PF_W) == 0

    assert load_zero_fill(0x3000, 0x5000) == 0x2000
    try:
        load_zero_fill(0x5000, 0x3000)
    except ValueError:
        pass
    else:
        raise AssertionError("filesz > memsz accepted")

    assert aligned_congruence(0x1000, 0xFFFFFFFF80000000, 0x1000)
    assert aligned_congruence(0x1234, 0xFFFFFFFF80000234, 0x1000)
    assert not aligned_congruence(0x1000, 0xFFFFFFFF80000234, 0x1000)

    assert reloc64(0x1000, 0x20) == 0x1020
    assert reloc_pc32(0x401000, -4, 0x400FFC) == 0
    assert reloc_pc32(0x401000, -4, 0x400000) == 0xFFC

    try:
        reloc_pc32(0x90000000, 0, 0)
    except OverflowError:
        pass
    else:
        raise AssertionError("out-of-range PC32 accepted")

    assert checked_add(0x1000, 0x2000) == 0x3000
    try:
        checked_add(U64_MAX, 1)
    except OverflowError:
        pass
    else:
        raise AssertionError("uint64 range wrap accepted")

    if args.source is not None:
        source_checks(args.source)

    print(
        "ELF/linking examples: header constants, PT_LOAD flags, zero-fill, "
        "alignment congruence, relocation arithmetic and source contracts passed"
    )
    print(
        "Current-source finding: ChrisLd v2 now supports rodata/data/bss, "
        "multi-object resolution and relocations, but still lacks the production "
        "Limine-request segment, linker symbols and 1 MiB stack policy."
    )
    print(
        "Scope: mechanical and repository-contract checks only; no claim that "
        "ChrisLd currently links or boots the production kernel."
    )


if __name__ == "__main__":
    main()
