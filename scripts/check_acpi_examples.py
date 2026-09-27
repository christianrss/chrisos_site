#!/usr/bin/env python3
"""Mechanical examples for the ACPI platform chapter.

The checks validate checksum arithmetic, root-table geometry, MADT walking
and MCFG/ECAM address calculations. They are not an AML interpreter or an
ACPI firmware-conformance test.
"""

from dataclasses import dataclass


SDT_HEADER = 36


def checksum_ok(data: bytes) -> bool:
    return (sum(data) & 0xFF) == 0


def fix_checksum(data: bytearray, offset: int, length: int | None = None) -> None:
    if length is None:
        length = len(data)
    data[offset] = 0
    data[offset] = (-sum(data[:length])) & 0xFF


def build_rsdp_v2(xsdt: int) -> bytes:
    data = bytearray(36)
    data[0:8] = b"RSD PTR "
    data[9:15] = b"CHRIS "
    data[15] = 2
    data[16:20] = (0).to_bytes(4, "little")
    data[20:24] = len(data).to_bytes(4, "little")
    data[24:32] = xsdt.to_bytes(8, "little")
    fix_checksum(data, 8, 20)
    fix_checksum(data, 32, len(data))
    return bytes(data)


def validate_rsdp(data: bytes) -> bool:
    if len(data) < 20 or data[:8] != b"RSD PTR ":
        return False
    if not checksum_ok(data[:20]):
        return False
    revision = data[15]
    if revision >= 2:
        if len(data) < 36:
            return False
        length = int.from_bytes(data[20:24], "little")
        if length < 36 or length > len(data):
            return False
        if not checksum_ok(data[:length]):
            return False
    return True


def make_sdt(signature: bytes, payload: bytes, revision: int = 1) -> bytes:
    assert len(signature) == 4
    data = bytearray(SDT_HEADER + len(payload))
    data[0:4] = signature
    data[4:8] = len(data).to_bytes(4, "little")
    data[8] = revision
    data[10:16] = b"CHRIS "
    data[16:24] = b"CHRISOS "
    data[24:28] = (1).to_bytes(4, "little")
    data[28:32] = b"CHRS"
    data[32:36] = (1).to_bytes(4, "little")
    data[36:] = payload
    fix_checksum(data, 9)
    return bytes(data)


def sdt_entry_count(table_length: int, pointer_bytes: int) -> int:
    if table_length < SDT_HEADER:
        raise ValueError("table shorter than SDT header")
    payload = table_length - SDT_HEADER
    if pointer_bytes not in (4, 8) or payload % pointer_bytes:
        raise ValueError("root-table payload is not pointer aligned")
    return payload // pointer_bytes


@dataclass(frozen=True)
class MadtEntry:
    kind: int
    payload: bytes


def walk_madt_entries(blob: bytes) -> list[MadtEntry]:
    out = []
    off = 0
    while off < len(blob):
        if len(blob) - off < 2:
            raise ValueError("truncated MADT entry header")
        kind = blob[off]
        length = blob[off + 1]
        if length < 2:
            raise ValueError("invalid MADT entry length")
        end = off + length
        if end > len(blob):
            raise ValueError("MADT entry exceeds table")
        out.append(MadtEntry(kind, blob[off + 2:end]))
        off = end
    return out


def mcfg_bytes(start_bus: int, end_bus: int) -> int:
    if not (0 <= start_bus <= 0xFF and 0 <= end_bus <= 0xFF):
        raise ValueError("bus out of range")
    if end_bus < start_bus:
        raise ValueError("inverted MCFG bus range")
    return (end_bus - start_bus + 1) * 0x100000


def ecam_address(base: int, start_bus: int, end_bus: int,
                 bus: int, device: int, function: int, register: int) -> int:
    if not (start_bus <= bus <= end_bus):
        raise ValueError("bus outside MCFG allocation")
    if not (0 <= device < 32 and 0 <= function < 8 and 0 <= register < 0x1000):
        raise ValueError("invalid ECAM field")
    return (
        base
        + ((bus - start_bus) << 20)
        + (device << 15)
        + (function << 12)
        + register
    )


def main():
    rsdp = build_rsdp_v2(0x123456789ABC0000)
    assert validate_rsdp(rsdp)
    assert checksum_ok(rsdp[:20])
    assert checksum_ok(rsdp)

    bad = bytearray(rsdp)
    bad[12] ^= 1
    assert not validate_rsdp(bytes(bad))

    bad_ext = bytearray(rsdp)
    bad_ext[35] ^= 1
    assert checksum_ok(bytes(bad_ext[:20]))
    assert not validate_rsdp(bytes(bad_ext))

    xsdt_payload = (
        (0x1000).to_bytes(8, "little")
        + (0x2000).to_bytes(8, "little")
        + (0x3000).to_bytes(8, "little")
    )
    xsdt = make_sdt(b"XSDT", xsdt_payload)
    assert checksum_ok(xsdt)
    assert sdt_entry_count(len(xsdt), 8) == 3

    rsdt = make_sdt(b"RSDT", (0x1000).to_bytes(4, "little") * 2)
    assert checksum_ok(rsdt)
    assert sdt_entry_count(len(rsdt), 4) == 2

    try:
        sdt_entry_count(SDT_HEADER + 6, 8)
    except ValueError as exc:
        assert "pointer aligned" in str(exc)
    else:
        raise AssertionError("misaligned XSDT payload was accepted")

    madt_blob = bytes([
        0, 8, 1, 2, 3, 4, 5, 6,
        1, 12, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16,
        2, 10, 17, 18, 19, 20, 21, 22, 23, 24,
    ])
    entries = walk_madt_entries(madt_blob)
    assert [e.kind for e in entries] == [0, 1, 2]
    assert [len(e.payload) for e in entries] == [6, 10, 8]

    try:
        walk_madt_entries(bytes([1, 0]))
    except ValueError as exc:
        assert "length" in str(exc)
    else:
        raise AssertionError("zero-length MADT entry was accepted")

    try:
        walk_madt_entries(bytes([1, 8, 1, 2]))
    except ValueError as exc:
        assert "exceeds" in str(exc)
    else:
        raise AssertionError("truncated MADT entry was accepted")

    assert mcfg_bytes(0, 0) == 0x100000
    assert mcfg_bytes(0, 7) == 0x800000
    assert mcfg_bytes(32, 63) == 0x2000000

    try:
        mcfg_bytes(8, 7)
    except ValueError as exc:
        assert "inverted" in str(exc)
    else:
        raise AssertionError("inverted MCFG range was accepted")

    base = 0xE0000000
    assert ecam_address(base, 0, 255, 0, 0, 0, 0) == base
    assert ecam_address(base, 0, 255, 1, 0, 0, 0) == base + 0x100000
    assert ecam_address(base, 0, 255, 2, 5, 3, 0xABC) == (
        base + 0x200000 + 0x28000 + 0x3000 + 0xABC
    )

    synthetic = bytearray(make_sdt(b"TEST", b"payload"))
    assert checksum_ok(synthetic)
    synthetic[-1] ^= 0x55
    assert not checksum_ok(synthetic)
    fix_checksum(synthetic, 9)
    assert checksum_ok(synthetic)

    print(
        "ACPI examples: RSDP/SDT checksums, root-table geometry, MADT walk, "
        "MCFG sizing and ECAM arithmetic passed"
    )
    print(
        "Scope: mechanical documentation model only; no AML interpreter or "
        "ACPI firmware-conformance claim."
    )


if __name__ == "__main__":
    main()
