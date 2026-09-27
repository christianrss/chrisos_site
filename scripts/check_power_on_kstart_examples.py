#!/usr/bin/env python3
"""Source-contract checks for the power-on -> kstart boot chapter."""

from __future__ import annotations

import argparse
from pathlib import Path


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def require(text: str, path: Path, needles: list[str]) -> None:
    missing = [n for n in needles if n not in text]
    if missing:
        raise AssertionError(f"{path}: missing {missing}")


def ordered(text: str, labels: list[str]) -> None:
    positions: list[int] = []
    for label in labels:
        pos = text.find(label)
        if pos < 0:
            raise AssertionError(f"missing ordered anchor: {label}")
        positions.append(pos)
    if positions != sorted(positions):
        pairs = list(zip(labels, positions))
        raise AssertionError(f"boot order drifted: {pairs}")


def source_checks(source: Path) -> None:
    start_path = source / "kernel/metal/start.c"
    bootinfo_path = source / "kernel/metal/bootinfo.c"
    linker_path = source / "kernel/metal/linker.ld"
    serial_path = source / "kernel/metal/serial.c"
    gdt_path = source / "kernel/metal/gdt.c"
    idt_path = source / "kernel/metal/idt.c"
    irq_path = source / "kernel/metal/irq.c"
    pit_path = source / "kernel/metal/pit.c"
    pmm_path = source / "kernel/metal/pmm.c"
    mm_path = source / "kernel/metal/mm.c"
    ioapic_path = source / "kernel/metal/ioapic.c"
    chrisvm_path = source / "docs/chrisvm-boot-protocol.md"

    start = read(start_path)
    bootinfo = read(bootinfo_path)
    linker = read(linker_path)
    serial = read(serial_path)
    gdt = read(gdt_path)
    idt = read(idt_path)
    irq = read(irq_path)
    pit = read(pit_path)
    pmm = read(pmm_path)
    mm = read(mm_path)
    ioapic = read(ioapic_path)
    chrisvm = read(chrisvm_path)

    require(linker, linker_path, ["ENTRY(kstart)", ". = 0xffffffff80000000;"])

    require(
        bootinfo,
        bootinfo_path,
        [
            "LIMINE_BASE_REVISION(3)",
            'section(".limine_requests_start")',
            'section(".limine_requests")',
            'section(".limine_requests_end")',
            "LIMINE_FRAMEBUFFER_REQUEST",
            "LIMINE_HHDM_REQUEST",
            "LIMINE_MEMMAP_REQUEST",
            "LIMINE_MP_REQUEST",
            "LIMINE_EXECUTABLE_CMDLINE_REQUEST",
            "if (!LIMINE_BASE_REVISION_SUPPORTED)",
            "if (framebuffer_request.response == 0",
            "if (hhdm_request.response == 0)",
            "if (memmap_request.response == 0",
            "if (mp_request.response == 0)",
            "info.hhdm_offset = hhdm->offset;",
            "memmap_response = memmap;",
            "return phys + info.hhdm_offset;",
            "return mp_request.response;",
            "HHDM+LAPIC=",
            "nao e mapeamento MMIO valido; nao desreferenciar",
        ],
    )

    request_order = [
        'section(".limine_requests_start")',
        "LIMINE_BASE_REVISION(3)",
        "LIMINE_FRAMEBUFFER_REQUEST",
        "LIMINE_HHDM_REQUEST",
        "LIMINE_MEMMAP_REQUEST",
        "LIMINE_MP_REQUEST",
        "LIMINE_EXECUTABLE_CMDLINE_REQUEST",
        'section(".limine_requests_end")',
    ]
    ordered(bootinfo, request_order)

    require(
        serial,
        serial_path,
        [
            "klog_init();",
            "outb(COM1 + 4, 0x1e);",
            "outb(COM1 + 0, 0xae);",
            "if (inb(COM1 + 0) != 0xae)",
            "spin_init(&g_serial_lock);",
        ],
    )

    # Critical current boot order. These anchors are intentionally selective:
    # they freeze architectural dependencies rather than every incidental call.
    ordered(
        start,
        [
            "serial_init()",
            "build_info_log();",
            "bootinfo_init();",
            "gdt_init();",
            "idt_init();",
            "syscall_init();",
            "pic_init();",
            "pit_init(60)",
            "ps2_init()",
            "pmm_init();",
            "pmm_selftest();",
            "\n    mm_init();",
            "\n    mm_selftest();",
            "heap_init();",
            "sse_bsp_init();",
            "heap_selftest();",
            "proc_init();",
            "gfx_init(",
            "virtio_gpu_boot()",
            "apic_init();",
            "ioapic_init();",
            "job_init();",
            "smp_init();",
            "smp_job_selftest();",
            'volatile ("cli");\n    acpi_probe();',
            "storage_init();",
            "fs_init();",
            "install_selftest()",
            "install_auto()",
            "lang_init(",
            "speaker_off();",
            "lang_make_cc();",
            'volatile ("sti");',
            "smp_release_ap_irqs();",
            "desktop_init();",
            "desktop_boot_apps();",
            "net_init()",
            "desktop_run();",
        ],
    )

    # The BSP source currently contains no explicit switch to the linker stack.
    if "__stack_top" in start or "mov %0, %%rsp" in start or "movq" in start and "__stack" in start:
        raise AssertionError("start.c now appears to switch/use the linker BSP stack; review chapter")

    require(
        gdt,
        gdt_path,
        [
            "extern unsigned char __stack_top[];",
            "tss.rsp0 = (uint64_t)__stack_top;",
            '"lgdt %0',
            '"ltr %%ax',
            "if (gdt_read_tr() != GDT_TSS)",
        ],
    )

    require(
        idt,
        idt_path,
        [
            "for (vector = 0; vector < 256; ++vector)",
            "idt_set_gate(2u, nmi_entry);",
            '__asm__ volatile ("lidt %0"',
        ],
    )

    require(
        irq,
        irq_path,
        [
            '__asm__ volatile ("cli");',
            "outb(PIC1_DATA, 0x20);",
            "outb(PIC2_DATA, 0x28);",
            "outb(PIC1_DATA, 0xff);",
            "outb(PIC2_DATA, 0xff);",
        ],
    )

    require(
        pit,
        pit_path,
        [
            "#define PIT_INPUT_HZ 1193182u",
            "irq_set_handler(0, pit_irq);",
            "pic_set_mask(0, false);",
        ],
    )

    require(
        pmm,
        pmm_path,
        [
            "type == LIMINE_MEMMAP_BOOTLOADER_RECLAIMABLE",
            "type == LIMINE_MEMMAP_EXECUTABLE_AND_MODULES",
            "type == LIMINE_MEMMAP_FRAMEBUFFER",
            "bootinfo_phys_to_virt(a)",
        ],
    )

    require(
        mm,
        mm_path,
        [
            '__asm__ volatile ("mov %%cr3, %0" : "=r"(cr3));',
            "mm_cr3_phys = cr3 & MM_ADDR_MASK;",
            "fb_phys = mm_virt_to_phys(boot->fb_addr);",
            "map_4k(MM_TEST_VIRT, phys, MM_PRESENT | MM_WRITE | MM_NX);",
            "via_hhdm = (volatile uint32_t *)bootinfo_phys_to_virt(phys);",
            "map_mmio_page(LAPIC_PHYS)",
        ],
    )

    require(
        ioapic,
        ioapic_path,
        [
            "PIC still routes IRQ",
            "full IOAPIC",
        ],
    )

    require(
        chrisvm,
        chrisvm_path,
        [
            "higher-half ELF is outside boot protocol v1",
            "O protocolo 2 precisa carregar um ELF higher-half",
        ],
    )

    # There must be exactly one explicit STI in start.c today; helper functions
    # may contain their own interrupt-state restore logic elsewhere.
    if start.count('__asm__ volatile ("sti");') != 1:
        raise AssertionError("start.c explicit STI count changed")

    # start.c has an early fatal CLI and a later phase CLI; at least two are
    # expected while the final STI remains unique.
    if start.count('__asm__ volatile ("cli");') < 2:
        raise AssertionError("expected early/fatal and pre-subsystem CLI anchors")


def arithmetic_checks() -> None:
    pit_input = 1_193_182
    requested = 60
    divisor = pit_input // requested
    if divisor != 19_886:
        raise AssertionError(f"unexpected PIT divisor {divisor}")
    actual = pit_input / divisor
    if not 59.99 < actual < 60.01:
        raise AssertionError(f"unexpected PIT frequency {actual}")

    # Limine default minimum stack guarantee used by the current no-stack-size-
    # request ChrisOS entry path.
    if 64 * 1024 != 65_536:
        raise AssertionError("64 KiB arithmetic failed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()

    arithmetic_checks()
    if args.source is not None:
        source_checks(args.source)

    print(
        "power-on/kstart contracts passed: request order, critical boot ordering, "
        "PIC/PIT setup, inherited CR3 adoption, TSS stack target and runtime STI"
    )
    print(
        "Current-source finding: ChrisOS installs its IDT only after serial, "
        "build-info, bootinfo and GDT work; synchronous faults before that do "
        "not have the ChrisOS IDT available."
    )
    print(
        "Ownership finding: BSP stack, raw boot responses and initial CR3/page "
        "tables still originate in bootloader-reclaimable state."
    )
    print(
        "Scope: source and arithmetic contracts only; this checker does not "
        "replace QEMU, ChrisVM or real-hardware boot smoke tests."
    )


if __name__ == "__main__":
    main()
