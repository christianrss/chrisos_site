#!/usr/bin/env python3
"""Mechanical examples for the PCI/PCIe documentation chapter.

This checker validates address arithmetic and bounded parser examples only.
It is not a PCI-SIG compliance or hardware-conformance suite.
"""


def cfg1_address(bus: int, device: int, function: int, offset: int) -> int:
    assert 0 <= bus <= 0xFF
    assert 0 <= device <= 31
    assert 0 <= function <= 7
    assert 0 <= offset <= 0xFF
    return (
        0x80000000
        | (bus << 16)
        | (device << 11)
        | (function << 8)
        | (offset & 0xFC)
    )


def cfg1_fields(address: int):
    assert address & 0x80000000
    return (
        (address >> 16) & 0xFF,
        (address >> 11) & 0x1F,
        (address >> 8) & 0x07,
        address & 0xFC,
    )


def class_fields(classrev: int):
    return (
        (classrev >> 24) & 0xFF,
        (classrev >> 16) & 0xFF,
        (classrev >> 8) & 0xFF,
        classrev & 0xFF,
    )


def header_type_fields(value: int):
    return value & 0x7F, bool(value & 0x80)


def ecam_address(base: int, start_bus: int, bus: int,
                 device: int, function: int, register: int) -> int:
    assert start_bus <= bus <= 0xFF
    assert 0 <= device <= 31
    assert 0 <= function <= 7
    assert 0 <= register <= 0xFFF
    return (
        base
        + ((bus - start_bus) << 20)
        + (device << 15)
        + (function << 12)
        + register
    )


def memory_bar_base32(raw: int) -> int:
    assert (raw & 1) == 0
    return raw & 0xFFFFFFF0


def memory_bar_base64(low: int, high: int) -> int:
    assert (low & 1) == 0
    assert ((low >> 1) & 0x3) == 0x2
    return ((high & 0xFFFFFFFF) << 32) | (low & 0xFFFFFFF0)


def bar_size32(mask_readback: int) -> int:
    mask = mask_readback & 0xFFFFFFF0
    return ((~mask) + 1) & 0xFFFFFFFF


def walk_standard_caps(entries: dict[int, tuple[int, int]], first: int):
    seen = set()
    out = []
    ptr = first

    while ptr:
        if ptr < 0x40 or ptr > 0xFC or (ptr & 0x3):
            raise ValueError("capability pointer out of range/alignment")
        if ptr in seen:
            raise ValueError("capability cycle")
        if ptr not in entries:
            raise ValueError("capability pointer missing")

        seen.add(ptr)
        cap_id, nxt = entries[ptr]
        out.append((ptr, cap_id))
        ptr = nxt

        if len(out) > 48:
            raise ValueError("capability chain too long")

    return out


def virtio_notify(base: int, queue_notify_off: int, multiplier: int) -> int:
    assert queue_notify_off >= 0
    assert multiplier >= 0
    return base + queue_notify_off * multiplier


def main():
    a = cfg1_address(2, 5, 3, 0x14)
    assert a == 0x80022B14
    assert cfg1_fields(a) == (2, 5, 3, 0x14)
    assert cfg1_address(2, 5, 3, 0x17) == a

    assert class_fields(0x01060123) == (0x01, 0x06, 0x01, 0x23)
    assert class_fields(0x0C033010) == (0x0C, 0x03, 0x30, 0x10)

    assert header_type_fields(0x00) == (0, False)
    assert header_type_fields(0x80) == (0, True)
    assert header_type_fields(0x81) == (1, True)

    base = 0xE0000000
    zero = ecam_address(base, 0, 0, 0, 0, 0)
    assert zero == base
    assert ecam_address(base, 0, 0, 0, 1, 0) - zero == 0x1000
    assert ecam_address(base, 0, 0, 1, 0, 0) - zero == 0x8000
    assert ecam_address(base, 0, 1, 0, 0, 0) - zero == 0x100000
    assert ecam_address(base, 0, 2, 5, 3, 0xABC) == (
        base + 0x200000 + 0x28000 + 0x3000 + 0xABC
    )

    assert memory_bar_base32(0xFEBF0008) == 0xFEBF0000
    assert memory_bar_base64(0xABC00004, 0x00000012) == 0x00000012ABC00000
    assert bar_size32(0xFFFFF000) == 0x1000
    assert bar_size32(0xFFFF0000) == 0x10000

    chain = {
        0x40: (0x01, 0x50),
        0x50: (0x09, 0x60),
        0x60: (0x11, 0),
    }
    assert walk_standard_caps(chain, 0x40) == [
        (0x40, 0x01),
        (0x50, 0x09),
        (0x60, 0x11),
    ]

    try:
        walk_standard_caps({0x40: (1, 0x50), 0x50: (5, 0x40)}, 0x40)
    except ValueError as exc:
        assert "cycle" in str(exc)
    else:
        raise AssertionError("cycle was not rejected")

    try:
        walk_standard_caps({0x40: (1, 0x42)}, 0x40)
    except ValueError as exc:
        assert "range/alignment" in str(exc)
    else:
        raise AssertionError("misaligned capability pointer was not rejected")

    assert virtio_notify(0x10000000, 7, 4) == 0x1000001C
    assert virtio_notify(0x10000000, 3, 0x1000) == 0x10003000

    print(
        "PCI examples: CF8/BDF, class/header fields, ECAM strides, BARs, "
        "capability-chain safety and VirtIO notify arithmetic passed"
    )
    print(
        "Scope: mechanical documentation model only; no PCI-SIG or "
        "physical-hardware conformance claim."
    )


if __name__ == "__main__":
    main()
