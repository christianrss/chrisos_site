#!/usr/bin/env python3
"""Deterministic checks for noise, grounding and signal-integrity foundations."""

from __future__ import annotations

import argparse
import math
from pathlib import Path


REVISION = "da3df29cb397932c43d32373871fb9380e688ade"


def approx(a: float, b: float, rel: float = 1e-10, abs_tol: float = 1e-12) -> bool:
    return abs(a - b) <= max(abs_tol, rel * max(abs(a), abs(b), 1.0))


def check_static_noise_margin() -> None:
    voh = 2.4
    vih = 2.0
    vol = 0.4
    vil = 0.8
    nm_h = voh - vih
    nm_l = vil - vol
    assert approx(nm_h, 0.4)
    assert approx(nm_l, 0.4)
    assert nm_h > 0.0 and nm_l > 0.0


def check_inductive_reference_motion() -> None:
    inductance = 1e-9
    di_dt = 1e9
    voltage = inductance * di_dt
    assert approx(voltage, 1.0)


def check_coupling() -> None:
    cm = 0.5e-12
    dv_dt = 2e9
    coupled_current = cm * dv_dt
    assert approx(coupled_current, 1e-3)

    mutual_l = 2e-9
    di_dt = 0.25e9
    induced_voltage = mutual_l * di_dt
    assert approx(induced_voltage, 0.5)


def check_reflection() -> None:
    z0 = 50.0
    matched = (z0 - z0) / (z0 + z0)
    open_gamma = 1.0
    short_gamma = (0.0 - z0) / (0.0 + z0)
    assert approx(matched, 0.0)
    assert approx(open_gamma, 1.0)
    assert approx(short_gamma, -1.0)


def check_differential_common() -> None:
    vp = 0.65
    vn = 0.35
    vdiff = vp - vn
    vcm = (vp + vn) / 2.0
    assert approx(vdiff, 0.30)
    assert approx(vcm, 0.50)
    assert approx(vcm + vdiff / 2.0, vp)
    assert approx(vcm - vdiff / 2.0, vn)


def check_simultaneous_switching() -> None:
    l_shared = 0.5e-9
    outputs = 8
    delta_i = 20e-3
    delta_t = 0.2e-9
    delta_v = l_shared * outputs * delta_i / delta_t
    assert approx(delta_v, 0.4)


def check_cmrr() -> None:
    a_diff = 1.0
    a_cm = 0.01
    cmrr = abs(a_diff / a_cm)
    cmrr_db = 20.0 * math.log10(cmrr)
    assert approx(cmrr, 100.0)
    assert approx(cmrr_db, 40.0)


def check_source_contract(source_root: Path) -> None:
    pci_c = (source_root / "kernel" / "metal" / "pci.c").read_text(encoding="utf-8")
    pci_h = (source_root / "kernel" / "metal" / "pci.h").read_text(encoding="utf-8")
    readme = (source_root / "README.md").read_text(encoding="utf-8")

    for anchor in (
        "uint32_t pci_read",
        "void pci_write",
        "0xCF8",
        "0xCFC",
        "for (bus = 0; bus < 1; ++bus)",
        "for (slot = 0; slot < 32; ++slot)",
        "for (func = 0; func < 8; ++func)",
    ):
        if anchor not in pci_c:
            raise AssertionError(f"pci.c missing reviewed anchor {anchor!r}")

    for anchor in ("pci_read", "pci_write"):
        if anchor not in pci_h:
            raise AssertionError(f"pci.h missing reviewed declaration {anchor!r}")

    if "QEMU is the primary integration environment." not in readme or "Real-hardware support is not yet a general supported deployment target." not in readme:
        raise AssertionError("README.md no longer carries the reviewed physical-test boundary")


def check_documents(root: Path) -> None:
    filename = "noise-grounding-signal-integrity.md"
    paths = {
        "en": root / "docs" / "en" / "01-foundations" / filename,
        "pt-br": root / "docs" / "pt-br" / "01-foundations" / filename,
    }

    required = (
        "NM_H",
        "NM_L",
        "V_L = L · di/dt",
        "i_C = C_m · dV_a/dt",
        "Γ_L = (Z_L - Z_0) / (Z_L + Z_0)",
        "ΔV ≈ L_s · N · ΔI/Δt",
        "V_diff = V_p - V_n",
        "CMRR",
        "BER",
        "pci_read",
        "pci_write",
        "kernel/metal/pci.c",
        "kernel/metal/pci.h",
        "PCI Express Base Specification Revision 7.1",
        "IEEE 802.3-2022",
        "BIPM",
    )

    for lang, path in paths.items():
        text = path.read_text(encoding="utf-8")
        if REVISION not in text:
            raise AssertionError(f"{path}: missing reviewed revision")
        if "" in text:
            raise AssertionError(f"{path}: contains form-feed corruption")
        for anchor in required:
            if anchor not in text:
                raise AssertionError(f"{path}: missing {anchor!r}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=".source")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    source_root = Path(args.source)

    check_static_noise_margin()
    check_inductive_reference_motion()
    check_coupling()
    check_reflection()
    check_differential_common()
    check_simultaneous_switching()
    check_cmrr()
    check_source_contract(source_root)
    check_documents(root)

    print(
        "signal-integrity checks passed: static margins, Ldi/dt, capacitive/inductive "
        "coupling, reflections, differential/common decomposition, SSO, CMRR and "
        "reviewed ChrisOS PCI evidence boundary"
    )
    print(
        "scope: deterministic equations/source anchors only; no TDR, VNA, eye, BER, "
        "EMC, PCIe compliance or physical-hardware claim"
    )


if __name__ == "__main__":
    main()
