#!/usr/bin/env python3
"""Deterministic checks for transmission-line and differential-signaling foundations."""

from __future__ import annotations

import argparse
import math
from pathlib import Path


REVISION = "da3df29cb397932c43d32373871fb9380e688ade"


def approx(a: float, b: float, rel: float = 1e-10, abs_tol: float = 1e-12) -> bool:
    return abs(a - b) <= max(abs_tol, rel * max(abs(a), abs(b), 1.0))


def reflection(z_load: float, z0: float) -> float:
    return (z_load - z0) / (z_load + z0)


def check_lossless_line() -> None:
    l_per_m = 250e-9
    c_per_m = 100e-12
    z0 = math.sqrt(l_per_m / c_per_m)
    vp = 1.0 / math.sqrt(l_per_m * c_per_m)
    length = 0.30
    delay = length / vp

    assert approx(z0, 50.0)
    assert approx(vp, 2.0e8)
    assert approx(delay, 1.5e-9)
    assert approx(2.0 * delay, 3.0e-9)


def check_reflections() -> None:
    z0 = 50.0
    assert approx(reflection(z0, z0), 0.0)
    assert approx(reflection(1.0e30, z0), 1.0, rel=1e-12)
    assert approx(reflection(0.0, z0), -1.0)

    z_load = 100.0
    gamma = reflection(z_load, z0)
    assert approx(gamma, 1.0 / 3.0)

    incident = 0.5
    v_load = incident * (1.0 + gamma)
    assert approx(v_load, 2.0 / 3.0)


def check_source_launch() -> None:
    vs = 1.0
    zs = 50.0
    z0 = 50.0
    launched = vs * z0 / (zs + z0)
    assert approx(launched, 0.5)

    # Matched source absorbs a returning wave.
    gamma_s = (zs - z0) / (zs + z0)
    assert approx(gamma_s, 0.0)


def check_vswr() -> None:
    gamma = 1.0 / 3.0
    vswr = (1.0 + abs(gamma)) / (1.0 - abs(gamma))
    assert approx(vswr, 2.0)
    assert approx((1.0 + 0.0) / (1.0 - 0.0), 1.0)


def check_differential_common() -> None:
    vp = 0.65
    vn = 0.35
    vdiff = vp - vn
    vcm = (vp + vn) / 2.0
    assert approx(vdiff, 0.30)
    assert approx(vcm, 0.50)

    reconstructed_p = vcm + vdiff / 2.0
    reconstructed_n = vcm - vdiff / 2.0
    assert approx(reconstructed_p, vp)
    assert approx(reconstructed_n, vn)

    # Common-mode perturbation preserves differential voltage when it couples equally.
    common_noise = 0.10
    assert approx((vp + common_noise) - (vn + common_noise), vdiff)


def check_quarter_wave_transform() -> None:
    z0 = 50.0
    z_load = 100.0
    zin = z0 * z0 / z_load
    assert approx(zin, 25.0)


def check_source_contract(source_root: Path) -> None:
    pci_c = (source_root / "kernel" / "metal" / "pci.c").read_text(encoding="utf-8")
    pci_h = (source_root / "kernel" / "metal" / "pci.h").read_text(encoding="utf-8")
    audit = (source_root / "docs" / "CURRENT_HARDWARE_AUDIT.md").read_text(encoding="utf-8")

    required_c = (
        "uint32_t pci_read",
        "void pci_write",
        "0xCF8",
        "0xCFC",
    )
    for anchor in required_c:
        if anchor not in pci_c:
            raise AssertionError(f"pci.c missing expected reviewed anchor {anchor!r}")

    for anchor in ("pci_read", "pci_write"):
        if anchor not in pci_h:
            raise AssertionError(f"pci.h missing expected declaration {anchor!r}")

    if "Nothing below is `PROVEN-HARDWARE`" not in audit:
        raise AssertionError("CURRENT_HARDWARE_AUDIT.md no longer carries the reviewed hardware-evidence boundary")


def check_documents(root: Path) -> None:
    filename = "transmission-lines-differential-signals.md"
    paths = {
        "en": root / "docs" / "en" / "01-foundations" / filename,
        "pt-br": root / "docs" / "pt-br" / "01-foundations" / filename,
    }

    required = (
        "Z0 = sqrt(L'/C')",
        "1/sqrt(L'C')",
        "Γ_L = (Z_L - Z0) / (Z_L + Z0)",
        "V_diff = V_p - V_n",
        "V_cm = (V_p + V_n) / 2",
        "Z_diff = 2 Z_odd",
        "pci_read",
        "pci_write",
        "kernel/metal/pci.c",
        "kernel/metal/pci.h",
        "docs/CURRENT_HARDWARE_AUDIT.md",
        "PCI Express Base Specification Revision 7.1",
        "IEEE 802.3-2022",
    )

    for lang, path in paths.items():
        text = path.read_text(encoding="utf-8")
        if REVISION not in text:
            raise AssertionError(f"{path}: missing reviewed revision")
        for anchor in required:
            if anchor not in text:
                raise AssertionError(f"{path}: missing {anchor!r}")
        if "sources:" not in text or "symbols:" not in text:
            raise AssertionError(f"{path}: missing source metadata")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=".source")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    source_root = Path(args.source)

    check_lossless_line()
    check_reflections()
    check_source_launch()
    check_vswr()
    check_differential_common()
    check_quarter_wave_transform()
    check_source_contract(source_root)
    check_documents(root)

    print(
        "transmission-line checks passed: Z0, propagation delay, reflections, "
        "source launch, VSWR, differential/common decomposition, quarter-wave "
        "transform and reviewed ChrisOS PCI source boundary"
    )
    print(
        "scope: deterministic equations/source anchors only; no TDR, VNA, eye, "
        "PCIe compliance, Ethernet compliance or physical-hardware claim"
    )


if __name__ == "__main__":
    main()
