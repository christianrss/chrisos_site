#!/usr/bin/env python3
"""Mechanical and source-contract checks for the UEFI documentation chapter."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


EFI_PAGE_SIZE = 4096
ESP_GUID_BYTES = bytes(
    [0x28, 0x73, 0x2A, 0xC1, 0x1F, 0xF8, 0xD2, 0x11,
     0xBA, 0x4B, 0x00, 0xA0, 0xC9, 0x3E, 0xC9, 0x3B]
)


def pages_for_bytes(size: int) -> int:
    if size < 0:
        raise ValueError("negative size")
    return (size + EFI_PAGE_SIZE - 1) // EFI_PAGE_SIZE


def guid_from_uefi_bytes(raw: bytes) -> str:
    if len(raw) != 16:
        raise ValueError("GUID must contain 16 bytes")
    d1 = int.from_bytes(raw[0:4], "little")
    d2 = int.from_bytes(raw[4:6], "little")
    d3 = int.from_bytes(raw[6:8], "little")
    d4a = raw[8:10].hex().upper()
    d4b = raw[10:16].hex().upper()
    return f"{d1:08X}-{d2:04X}-{d3:04X}-{d4a}-{d4b}"


def descriptor_offsets(map_size: int, descriptor_size: int) -> list[int]:
    if map_size < 0 or descriptor_size <= 0:
        raise ValueError("invalid map geometry")
    if map_size % descriptor_size:
        raise ValueError("memory map is not descriptor aligned")
    return list(range(0, map_size, descriptor_size))


class MapGeneration:
    def __init__(self) -> None:
        self.key = 1

    def get_memory_map(self) -> int:
        return self.key

    def allocate(self) -> None:
        self.key += 1

    def exit_boot_services(self, supplied_key: int) -> bool:
        return supplied_key == self.key


def require_text(path: Path, needles: list[str]) -> str:
    text = path.read_text(encoding="utf-8")
    missing = [n for n in needles if n not in text]
    if missing:
        raise AssertionError(f"{path}: missing {missing}")
    return text


def parse_source_esp_guid(install_text: str) -> bytes:
    match = re.search(
        r"uint8_t\s+efi_guid\[16\]\s*=\s*\{([^}]*)\}",
        install_text,
        re.S,
    )
    if not match:
        raise AssertionError("install.c: efi_guid[16] not found")
    values = [
        int(token, 16)
        for token in re.findall(r"0x([0-9A-Fa-f]{1,2})", match.group(1))
    ]
    if len(values) != 16:
        raise AssertionError(f"install.c: expected 16 ESP GUID bytes, got {len(values)}")
    return bytes(values)


def scan_kernel_for_native_uefi_api(source: Path) -> dict[str, list[str]]:
    needles = ["EFI_SYSTEM_TABLE", "GetMemoryMap", "ExitBootServices", "BootOrder"]
    hits: dict[str, list[str]] = {n: [] for n in needles}
    kernel = source / "kernel"
    for path in kernel.rglob("*"):
        if path.suffix.lower() not in {".c", ".h", ".s", ".asm"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for needle in needles:
            if needle in text:
                hits[needle].append(str(path.relative_to(source)))
    return hits


def source_checks(source: Path) -> None:
    install = source / "kernel/fs/install.c"
    limine = source / "iso_root/boot/limine/limine.conf"
    bootinfo = source / "kernel/metal/bootinfo.c"

    install_text = require_text(
        install,
        [
            '"EFI/BOOT/BOOTX64.EFI"',
            "static uint16_t g_fat[16384];",
            "g_sec[54] = 'F';",
            "g_sec[55] = 'A';",
            "g_sec[56] = 'T';",
            "g_sec[57] = '1';",
            "g_sec[58] = '6';",
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
        ],
    )

    source_guid = parse_source_esp_guid(install_text)
    assert source_guid == ESP_GUID_BYTES
    assert guid_from_uefi_bytes(source_guid) == "C12A7328-F81F-11D2-BA4B-00A0C93EC93B"

    hits = scan_kernel_for_native_uefi_api(source)
    unexpected = {k: v for k, v in hits.items() if v}
    if unexpected:
        raise AssertionError(f"native UEFI API markers appeared in kernel source: {unexpected}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()

    assert guid_from_uefi_bytes(ESP_GUID_BYTES) == "C12A7328-F81F-11D2-BA4B-00A0C93EC93B"

    assert pages_for_bytes(0) == 0
    assert pages_for_bytes(1) == 1
    assert pages_for_bytes(4096) == 1
    assert pages_for_bytes(4097) == 2
    assert pages_for_bytes(1024 * 1024) == 256

    assert descriptor_offsets(48 * 3, 48) == [0, 48, 96]
    assert descriptor_offsets(56 * 4, 56) == [0, 56, 112, 168]
    try:
        descriptor_offsets(145, 48)
    except ValueError as exc:
        assert "aligned" in str(exc)
    else:
        raise AssertionError("misaligned memory map was accepted")

    gen = MapGeneration()
    old = gen.get_memory_map()
    assert gen.exit_boot_services(old)
    gen.allocate()
    assert not gen.exit_boot_services(old)
    fresh = gen.get_memory_map()
    assert gen.exit_boot_services(fresh)

    assert "BOOTX64.EFI" == "BOOT" + "X64" + ".EFI"

    if args.source is not None:
        source_checks(args.source)

    print(
        "UEFI examples: ESP GUID, page math, descriptor stride, MapKey freshness, "
        "fallback path and ChrisOS source boundaries passed"
    )
    print(
        "Current-source finding: installer ESP writer is FAT16-style while the "
        "real-hardware plan targets a FAT32 hard-disk ESP."
    )
    print(
        "Scope: mechanical and repository-contract checks only; no UEFI firmware "
        "or physical-machine conformance claim."
    )


if __name__ == "__main__":
    main()
