#!/usr/bin/env python3
"""Executable arithmetic examples for the buses/MMIO/DMA chapter.

These checks validate the chapter's mechanical examples only. They are not
PCI, VirtIO, DMA, IOMMU, or hardware-conformance tests.
"""


def pci_cfg_addr(bus: int, device: int, function: int, offset: int) -> int:
    assert 0 <= bus <= 0xFF
    assert 0 <= device <= 31
    assert 0 <= function <= 7
    return (
        0x80000000
        | (bus << 16)
        | (device << 11)
        | (function << 8)
        | (offset & 0xFC)
    )


def bar_size32(raw_mask: int) -> int:
    address_mask = raw_mask & 0xFFFFFFF0
    return ((~address_mask) + 1) & 0xFFFFFFFF


def fits_dma32(start: int, length: int) -> bool:
    if start < 0 or length <= 0 or start > 0xFFFFFFFF:
        return False
    last = start + length - 1
    return last <= 0xFFFFFFFF


def split_u64(address: int):
    return address & 0xFFFFFFFF, (address >> 32) & 0xFFFFFFFF


def join_u64(lo: int, hi: int) -> int:
    return (lo & 0xFFFFFFFF) | ((hi & 0xFFFFFFFF) << 32)


def ata_prdt_count(byte_count: int, end_of_table: bool = True) -> int:
    assert 0 < byte_count < 0x80000000
    return byte_count | (0x80000000 if end_of_table else 0)


def align4(value: int) -> int:
    return (value + 3) & ~3


def virtq_layout(qsz: int):
    assert qsz >= 2 and (qsz & (qsz - 1)) == 0
    desc_bytes = qsz * 16
    avail_bytes = 4 + 2 * qsz + 2
    used_at = align4(desc_bytes + avail_bytes)
    used_bytes = 4 + 8 * qsz + 2
    return desc_bytes, used_at, used_at + used_bytes


def main():
    assert pci_cfg_addr(2, 5, 3, 0x14) == 0x80022B14
    assert pci_cfg_addr(0, 0, 0, 0x03) == 0x80000000

    assert bar_size32(0xFFFFF000) == 0x1000
    assert bar_size32(0xFFFF0000) == 0x10000

    assert fits_dma32(0xFFFFE000, 0x2000)
    assert not fits_dma32(0xFFFFF000, 0x2000)
    assert fits_dma32(0x00001000, 0x1000)
    assert not fits_dma32(0x100000000, 1)

    address = 0x123456789ABCDEF0
    lo, hi = split_u64(address)
    assert lo == 0x9ABCDEF0
    assert hi == 0x12345678
    assert join_u64(lo, hi) == address

    assert ata_prdt_count(0x2000) == 0x80002000

    for qsz in (4, 8, 256):
        desc_bytes, used_at, total = virtq_layout(qsz)
        assert desc_bytes == qsz * 16
        assert used_at % 4 == 0
        assert used_at >= desc_bytes + 4 + 2 * qsz + 2
        assert total > used_at

    assert virtq_layout(4) == (64, 80, 118)

    print(
        "bus/DMA examples: PCI config, BAR sizing, DMA32 boundary, "
        "64-bit address split, ATA PRDT and virtqueue layout passed"
    )
    print(
        "Scope: arithmetic/documentation model only; no PCI/VirtIO/DMA "
        "hardware-conformance claim."
    )


if __name__ == "__main__":
    main()
