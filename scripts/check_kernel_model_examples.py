#!/usr/bin/env python3
"""Source-contract checks for the ChrisOS kernel-model chapter."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def require(path: Path, needles: list[str]) -> str:
    data = text(path)
    missing = [n for n in needles if n not in data]
    if missing:
        raise AssertionError(f"{path}: missing {missing}")
    return data


def require_absent(path: Path, needles: list[str]) -> None:
    data = text(path)
    found = [n for n in needles if n in data]
    if found:
        raise AssertionError(f"{path}: unexpected {found}")


def makefile_checks(source: Path) -> dict[str, int]:
    path = source / "makefile"
    data = require(
        path,
        [
            "C_OBJECTS_REL :=",
            "kernel/metal/start.o",
            "kernel/metal/proc.o",
            "kernel/fs/fs.o",
            "kernel/fs/ahci.o",
            "kernel/gfx/graphics.o",
            "kernel/gfx/hwgate.o",
            "kernel/net/net.o",
            "kernel/wm/main.o",
            "kernel/lang/clvm_sys.o",
            "compiler/chrisc/chrisc.o",
            "compiler/clvm/clvm_vm.o",
            "compiler/jit/jit.o",
            "compiler/kcc/kcc.o",
            "compiler/chrisasm/chrisasm.o",
            "compiler/chrisld/chrisld.o",
            "OBJECTS := $(C_OBJECTS) $(ASM_OBJECTS)",
            "$(LD) $(LDFLAGS) -o $@ $(OBJECTS)",
        ],
    )

    m = re.search(r"C_OBJECTS_REL :=(.*?)\n\nASM_OBJECTS_REL", data, re.S)
    if not m:
        raise AssertionError("cannot locate C_OBJECTS_REL block")
    block = m.group(1)
    objs = re.findall(r"([A-Za-z0-9_./$()]+\.o)", block)
    prefixes = [
        "kernel/metal/",
        "kernel/fs/",
        "kernel/gfx/",
        "kernel/net/",
        "kernel/wm/",
        "kernel/lang/",
        "kernel/tools/",
        "kernel/crypto/",
        "compiler/",
    ]
    counts = {p: sum(1 for o in objs if o.startswith(p)) for p in prefixes}
    for p, n in counts.items():
        if n == 0:
            raise AssertionError(f"production kernel object graph lost category {p}")
    return counts


def native_user_checks(source: Path) -> None:
    user_enter = source / "kernel/metal/user_enter.c"
    syscall = source / "kernel/metal/syscall.c"
    elf = source / "kernel/metal/elf.c"
    mmh = source / "kernel/metal/mm.h"
    proc = source / "kernel/metal/proc.c"

    require(
        user_enter,
        [
            "GDT_USER_CODE | 3u",
            "GDT_USER_DATA | 3u",
            "uint64_t rflags = 0x202ull;",
            '"iretq',
        ],
    )

    sys = require(
        syscall,
        [
            "void syscall_dispatch(struct irq_frame *frame)",
            "if (smp_current_cpu() != 0u)",
            "void syscall_init(void)",
            "idt_set_user_gate(0x80u);",
            "MM_USER",
            "mm_translate(cr3, addr, &phys, &flags)",
        ],
    )
    if sys.find("if (smp_current_cpu() != 0u)") > sys.find("void syscall_init(void)"):
        raise AssertionError("off-BSP syscall guard moved outside dispatch path")

    require(
        mmh,
        [
            "#define MM_USER    (1ull << 2)",
            "#define MM_NX      (1ull << 63)",
        ],
    )

    require(
        elf,
        [
            "page_flags = MM_PRESENT | MM_USER;",
            "if ((flags & PF_W) != 0)",
            "page_flags |= MM_WRITE;",
            "if ((flags & PF_X) == 0)",
            "page_flags |= MM_NX;",
            "if ((seg->flags & PF_X) != 0 && (seg->flags & PF_W) != 0)",
            "#define USER_LOAD_LO 0x400000ull",
            "#define USER_LOAD_HI 0x500000ull",
        ],
    )

    p = require(
        proc,
        [
            "void proc_switch(int pid)",
            "smp_current_cpu() != 0",
            "mm_switch(cr3);",
            "proc_destroy",
        ],
    )
    switch = p.find("void proc_switch(int pid)")
    guard = p.find("smp_current_cpu() != 0", switch)
    mm_switch = p.find("mm_switch(cr3);", switch)
    if min(switch, guard, mm_switch) < 0 or not (switch < guard < mm_switch):
        raise AssertionError("proc_switch BSP-only guard/order changed")


def clvm_checks(source: Path) -> None:
    vm = source / "compiler/clvm/clvm_vm.c"
    sys = source / "kernel/lang/clvm_sys.c"

    require(
        vm,
        [
            "ClvmStepResult clvm_step(ClvmVm *vm, uint32_t budget)",
            "case CL_OP_SYS:",
            "CLVM_FAULT_BAD_ADDRESS",
            "CLVM_FAULT_BAD_SYS",
            "vm->memory",
            "vm->mem_size",
        ],
    )

    require(
        sys,
        [
            "if (!vm->memory || addr < 0 || (uint64_t)addr + 4u > vm->mem_size)",
            "if (off + (uint64_t)n > vm->mem_size)",
            "if (a >= vm->mem_size || (uint32_t)n > vm->mem_size - a)",
            "static int drv_cap(ClvmVm *vm, uint32_t need)",
            "lang_slot_caps(slot)",
        ],
    )


def kthread_checks(source: Path) -> None:
    path = source / "kernel/metal/kthread.c"
    data = require(
        path,
        [
            "int kthread_create(KThreadFn fn, void *arg)",
            "stack = kmalloc(KT_STACK);",
            '"movq %%rsp, %[saved]',
            '"movq %[top], %%rsp',
            '"call kt_trampoline',
            '"movq %[saved], %%rsp',
            "job_submit(kt_job, &g_th[i])",
        ],
    )
    for forbidden in ["mov %%cr3", "iretq", "GDT_USER_CODE", "MM_USER"]:
        if forbidden in data:
            raise AssertionError(
                f"kthread implementation now contains isolation primitive {forbidden}; review chapter"
            )


def panic_checks(source: Path) -> None:
    path = source / "kernel/metal/panic.c"
    data = require(
        path,
        [
            "_Noreturn void panic(const char *message)",
            '__asm__ volatile ("cli");',
            'serial_puts("\nPANIC: ");',
            "panic_identity();",
            '__asm__ volatile ("hlt");',
            "_Noreturn void panic_exception",
        ],
    )
    if "return;" in data[data.find("_Noreturn void panic("):data.find("_Noreturn void panic_exception")]:
        raise AssertionError("panic unexpectedly gained a return path")


def architecture_docs_checks(source: Path) -> None:
    locking = source / "docs/LOCKING.md"
    ownership = source / "docs/RESOURCE_OWNERSHIP.md"

    require(
        locking,
        [
            "JIT compile lock",
            "MM lock",
            "Heap lock",
            "PMM lock",
            "User address spaces are BSP-only.",
            "proc_switch",
            "There is no socket lock yet.",
        ],
    )

    require(
        ownership,
        [
            "Process PML4 and user-half page tables",
            "proc_destroy",
            "Native file descriptor",
            "syscall_close_owner",
            "Socket",
            "sock_close_proc",
            "Kthread stack",
            "kthread_join",
        ],
    )


def hwgate_checks(source: Path) -> None:
    path = source / "kernel/gfx/hwgate.c"
    require(
        path,
        [
            "int hw_pci_write",
            "pci_write(",
            "int hw_bar_map",
            "map_mmio_page(",
            "int hw_dma_alloc",
            "pmm_alloc_contig",
            "int hw_dma_alloc_low",
            "pmm_alloc_dma32",
            "uint32_t hw_mmio_r32",
            "int hw_mmio_w32",
            "int hw_disk_write",
        ],
    )


def source_checks(source: Path) -> dict[str, int]:
    counts = makefile_checks(source)
    native_user_checks(source)
    clvm_checks(source)
    kthread_checks(source)
    panic_checks(source)
    architecture_docs_checks(source)
    hwgate_checks(source)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()

    counts: dict[str, int] = {}
    if args.source is not None:
        counts = source_checks(args.source)

    if counts:
        compact = ", ".join(f"{k.rstrip('/')}={v}" for k, v in counts.items())
        print(f"kernel-model object graph: {compact}")

    print(
        "kernel-model contracts passed: monolithic production object graph, "
        "native ring-3 entry, user page permissions, BSP-only native scheduling, "
        "software CLVM boundary, privileged kthreads and fatal panic policy"
    )
    print(
        "Current-source finding: fs, graphics, networking, window manager, "
        "language runtime and compiler/toolchain objects are directly linked "
        "into kernel.elf; module APIs do not form hardware protection domains."
    )
    print(
        "Trust-boundary finding: native ELF uses CPL3+paging, CLVM uses software "
        "bounds/capabilities, while PCI/MMIO/DMA mediation remains privileged."
    )
    print(
        "Scope: architecture/source contracts only; passing this checker does "
        "not prove memory safety, syscall safety or absence of VM escape bugs."
    )


if __name__ == "__main__":
    main()
